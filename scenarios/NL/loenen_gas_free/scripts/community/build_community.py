"""Workflow step 6 (pilot): one Calliope model for the members on one station.

Members come from ``select_members.py``. The model reuses ``build_nodes.py``
on the members' own Phase 1 demand, so heating, cooling and EV handling are
exactly those of the per-building runs, and adds:

- at every member: rooftop PV (``pv_rooftop_household``, up to the roof's
  own potential, hourly ``source_use_max`` from ``build_pv_potential.py``)
  and a home battery (``battery_lithium_ion_household``);
- grid export (``demand_grid_export``): a demand tech with a negative
  ``cost_flow_in``, the hourly NL day-ahead price (``energy_prices.csv``);

and then, per ``--mode``:

``community`` (default)
    One extra node, ``community``, holding the station's grid connection
    (import ``supply_grid_electricity``, export ``demand_grid_export``) and
    a community battery (``battery_lithium_ion_community``). Every member
    is linked to it (``base_tech: transmission``, lossless, not limited:
    the LV cable is not the bottleneck modelled here). Unless
    ``--no-station-limit``, the station's capacity left after the
    non-members is enforced hourly: import <= limit - non-member load,
    export <= limit + non-member load. Non-members keep their present-day
    electricity (appliances + uncontrolled EV charging, buem/occupancy
    Phase 1); they are not optimised.
``independent``
    The same members without sharing: grid import and export at each
    member, no links, no community battery, no station limit. The
    difference to ``community`` is the value (or cost) of the community.

Station limit: Liander's per-transformer limit (``transformers.csv``
``rated_kva``, which Liander's list labels kW) times ``--power-factor``
(default 1.0: the limit is taken as active power, as Liander publishes it).

Costs are the system perspective (no taxes, no subsidies), as in every
other run of this scenario. Output: ``<out>/model.yaml`` plus its inputs.

Usage (scenario_env, scenario root)::

    python scripts/community/build_community.py --station MSR5000927
    python scripts/community/build_community.py --station MSR5000927 --mode independent
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from ruamel.yaml import YAML

SCENARIO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCENARIO_ROOT / "scripts"))

import build_nodes  # noqa: E402

DATA = SCENARIO_ROOT / "data"
TECHS_YAML = SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.yaml"
MATH_YAML = (
    SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.additional_math.yaml"
)
PV_TECH = "pv_rooftop_household"
HOME_BATTERY = "battery_lithium_ion_household"
COMMUNITY_BATTERY = "battery_lithium_ion_community"
IMPORT = "supply_grid_electricity"
EXPORT = "demand_grid_export"
COMMUNITY_NODE = "community"
MODES = ("community", "independent")
# Solver -> Calliope build backend. HiGHS runs through Calliope's own highspy
# backend: Pyomo's HiGHS interfaces fail on Calliope 0.7.0 models (Pyomo 6.9.4
# and 6.10.1, docs/phase9_community_pilot.md "Solver"). Same optimum as CBC.
SOLVERS = {"highs": "highs", "cbc": "pyomo", "gurobi": "gurobi"}
# HiGHS options: interior point without crossover. The default dual simplex
# had no feasible point after ~40 min on the 20-member full year; IPM needs a
# few dozen iterations whatever the horizon (one week: same optimum).
SOLVER_OPTIONS = {
    "highs": {"solver": "ipm", "run_crossover": "off"},
    "cbc": {},
    # Gurobi through Calliope's native backend (needs gurobipy + a licence):
    # barrier without crossover. One-week test: same optimum, 0.6 s barrier.
    "gurobi": {"Method": 2, "Crossover": 0, "Threads": 8},
}

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.width = 4096


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        _yaml.dump(data, fh)


def _posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def _electric_by_building(path: Path, ids: set[int]) -> pd.DataFrame:
    """Present-day electricity (appliances + uncontrolled EV), kW, wide."""
    df = pd.read_parquet(
        path,
        columns=["building_feature_id", "time", "elec_kW", "ev_kW"],
        filters=[("building_feature_id", "in", sorted(ids))],
    )
    df["kW"] = df["elec_kW"] + df["ev_kW"]
    return df.pivot(index="time", columns="building_feature_id", values="kW")


def station_limits(
    station: str,
    members: pd.DataFrame,
    grid_dir: Path,
    hourly: Path,
    background_hourly: Path,
    power_factor: float,
) -> tuple[pd.DataFrame, dict]:
    """Hourly import/export limits at the station for the members (kW)."""
    grid = pd.read_csv(grid_dir / "building_grid_map.csv")
    trafo = pd.read_csv(grid_dir / "transformers.csv").set_index("trafo_id")
    rated = trafo.loc[station, "rated_kva"]
    if pd.isna(rated):
        raise ValueError(f"{station} has no published rating")
    limit_kw = float(rated) * power_factor
    on_station = set(grid.loc[grid["trafo_id"] == station, "building_feature_id"])
    non_members = on_station - set(members["building_feature_id"])
    parts = [_electric_by_building(hourly, non_members)]
    parts.append(_electric_by_building(background_hourly, non_members))
    load = pd.concat(parts, axis=1)
    missing = non_members - set(load.columns)
    if missing:
        raise ValueError(f"{len(missing)} non-members have no Phase 1 demand")
    nm = load.sum(axis=1)
    limits = pd.DataFrame(
        {
            "import_kW": (limit_kw - nm).clip(lower=0.0),
            "export_kW": limit_kw + nm,
        }
    )
    limits.index = limits.index.astype(str)
    limits.index.name = "timesteps"
    meta = {
        "station": station,
        "limit_kw": limit_kw,
        "power_factor": power_factor,
        "n_non_members": len(non_members),
        "non_member_peak_kw": round(float(nm.max()), 1),
        "non_member_annual_mwh": round(float(nm.sum()) / 1000, 1),
        "min_import_headroom_kw": round(float(limits["import_kW"].min()), 1),
    }
    return limits, meta


def build(
    station: str,
    out: Path,
    mode: str = "community",
    station_limit: bool = True,
    power_factor: float = 1.0,
    subset: tuple[str, str] | None = None,
    hourly: Path = DATA / "loenen_single_dwelling_hourly_cool26_ev20.parquet",
    background_hourly: Path = DATA / "loenen_background_cool26_ev20_hourly.parquet",
    grid_dir: Path = DATA / "step2/grid/dso_liander",
    pv_dir: Path = DATA / "step2/pv",
    members_csv: Path | None = None,
    solver: str = "highs",
) -> Path:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if solver not in SOLVERS:
        raise ValueError(f"solver must be one of {sorted(SOLVERS)}")
    members_csv = members_csv or DATA / "community" / station / "members.csv"
    members = pd.read_csv(members_csv)
    member_ids = set(members["building_feature_id"])
    out.mkdir(parents=True, exist_ok=True)

    # 1. The members' own nodes, exactly as the per-building runs build them.
    subset_parquet = out / "member_hourly.parquet"
    pd.read_parquet(
        hourly, filters=[("building_feature_id", "in", sorted(member_ids))]
    ).to_parquet(subset_parquet)
    build_nodes.build(subset_parquet, out / "nodes", grid_price="day_ahead")
    nodes = _yaml.load((out / "nodes" / "nodes.yaml").open(encoding="utf-8"))
    tables = _yaml.load((out / "nodes" / "data_tables.yaml").open(encoding="utf-8"))

    # 2. PV and home battery at every member.
    pv = pd.read_csv(pv_dir / "pv_rooftop_household_source_use_max.csv", index_col=0)
    kwp = members.set_index("node")["max_kwp"].fillna(0.0)
    pv_nodes = [n for n in members["node"] if kwp[n] > 0]
    pv[pv_nodes].rename_axis("timesteps").to_csv(out / "nodes" / "pv_source.csv")
    for node in members["node"]:
        techs = nodes["nodes"][node]["techs"]
        techs[HOME_BATTERY] = {}
        if node in pv_nodes:
            techs[PV_TECH] = {
                "flow_cap_max": {
                    "data": round(float(kwp[node]), 3),
                    "index": "electricity",
                    "dims": "carriers",
                }
            }
    tables["data_tables"]["loenen_pv_source"] = {
        "table": "nodes/pv_source.csv",
        "rows": "timesteps",
        "columns": "nodes",
        "add_dims": {"techs": PV_TECH, "inputs": "source_use_max"},
    }

    # 3. Export price: the hourly day-ahead price as revenue.
    price = pd.read_csv(build_nodes._GRID_PRICE_PATH, index_col=0)
    export_price = (-price["day_ahead_eur_per_mwh"] / 1000.0).rename("cost_flow_in")
    export_price.rename_axis("timesteps").to_csv(out / "nodes" / "export_price.csv")
    tables["data_tables"]["loenen_export_price"] = {
        "table": "nodes/export_price.csv",
        "rows": "timesteps",
        "add_dims": {"techs": EXPORT, "inputs": "cost_flow_in", "costs": "monetary"},
    }
    community_techs: dict = {
        EXPORT: {
            "base_tech": "demand",
            "name": "Grid electricity export",
            "carrier_in": "electricity",
            "comment": (
                "cost_flow_in = -NL day-ahead price 2018 (revenue per kWh "
                "exported, system perspective; energy_prices.csv "
                "demand_grid_export)."
            ),
        }
    }

    meta: dict = {"station": station, "mode": mode, "n_members": len(members)}
    if mode == "independent":
        for node in members["node"]:
            nodes["nodes"][node]["techs"][EXPORT] = {}
    else:
        for node in members["node"]:
            del nodes["nodes"][node]["techs"][IMPORT]
            community_techs[f"link_{node}"] = {
                "base_tech": "transmission",
                "name": f"LV link {node} - {COMMUNITY_NODE}",
                "carrier_in": "electricity",
                "carrier_out": "electricity",
                "link_from": node,
                "link_to": COMMUNITY_NODE,
                "flow_cap_max": 1000,
                "flow_out_eff": 1.0,
            }
        nodes["nodes"][COMMUNITY_NODE] = {
            "techs": {IMPORT: {}, EXPORT: {}, COMMUNITY_BATTERY: {}}
        }
        if station_limit:
            limits, limit_meta = station_limits(
                station, members, grid_dir, hourly, background_hourly, power_factor
            )
            meta["station_limit"] = limit_meta
            limits[["import_kW"]].rename(columns={"import_kW": COMMUNITY_NODE}).to_csv(
                out / "nodes" / "station_import_limit.csv"
            )
            limits[["export_kW"]].rename(columns={"export_kW": COMMUNITY_NODE}).to_csv(
                out / "nodes" / "station_export_limit.csv"
            )
            tables["data_tables"]["loenen_station_import"] = {
                "table": "nodes/station_import_limit.csv",
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": IMPORT, "inputs": "source_use_max"},
            }
            tables["data_tables"]["loenen_station_export"] = {
                "table": "nodes/station_export_limit.csv",
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": EXPORT, "inputs": "sink_use_max"},
            }
        else:
            meta["station_limit"] = None

    _write_yaml(out / "nodes.yaml", nodes)
    _write_yaml(out / "community_techs.yaml", {"techs": community_techs})
    _write_yaml(out / "data_tables.yaml", tables)
    init: dict = {
        "name": f"Loenen energy community pilot, {station} ({mode})",
        "calliope_version": "0.7.0",
        "math_paths": {"additional_math": _posix(MATH_YAML)},
        "extra_math": ["additional_math"],
        "mode": "base",
    }
    if subset:
        init["subset"] = {"timesteps": list(subset)}
        meta["subset"] = list(subset)
    model = {
        "config": {
            "init": init,
            "build": {"backend": SOLVERS[solver]},
            "solve": {"solver": solver, "solver_options": SOLVER_OPTIONS[solver]},
        },
        "import": [
            _posix(TECHS_YAML),
            "nodes/demand_techs.yaml",
            "community_techs.yaml",
            "nodes.yaml",
            "data_tables.yaml",
        ],
    }
    _write_yaml(out / "model.yaml", model)
    meta["members"] = list(members["node"])
    meta["pv_nodes"] = pv_nodes
    (out / "build.json").write_text(json.dumps(meta, indent=2))
    return out / "model.yaml"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--station", required=True)
    parser.add_argument("--mode", choices=MODES, default="community")
    parser.add_argument("--no-station-limit", action="store_true")
    parser.add_argument("--power-factor", type=float, default=1.0)
    parser.add_argument(
        "--solver",
        choices=sorted(SOLVERS),
        default="highs",
        help="highs (default; Calliope's own HiGHS backend) or cbc (Pyomo backend)",
    )
    parser.add_argument(
        "--subset",
        nargs=2,
        metavar=("START", "END"),
        default=None,
        help="time subset for a quick test, e.g. 2018-01-08 2018-01-14",
    )
    parser.add_argument("--members", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    tag = args.mode + ("_nolimit" if args.no_station_limit else "")
    if args.subset:
        tag += f"_{args.subset[0]}_{args.subset[1]}"
    if args.solver != "highs":
        tag += f"_{args.solver}"
    out = args.out or DATA / "community" / args.station / tag
    path = build(
        args.station,
        out,
        mode=args.mode,
        station_limit=not args.no_station_limit,
        power_factor=args.power_factor,
        subset=tuple(args.subset) if args.subset else None,
        members_csv=args.members,
        solver=args.solver,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
