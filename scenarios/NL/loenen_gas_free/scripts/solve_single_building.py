"""Phase 5a: solve the real Loenen gas-free scenario for ONE building.

Per-building decomposition rationale: see
docs/phase5_per_building_decomposition.md. In short, this scenario's
real `nodes/nodes.yaml` has no `links:` (no cross-building transmission).
The only storage tech, an electric vehicle's battery
(`ev_battery_household`), is node-local: it couples one building's
timesteps, never two buildings. With no shared variable across nodes, the full
N-node model is block-diagonal by node: solving it as one combined
problem is mathematically equivalent to solving each node's
single-building, full-year problem independently and summing results.
This script does exactly one block; `solve_all_buildings.py` runs every
block, in parallel, and sums them.

Uses this repo's own real `calliope_export` output (0.7.0 `flow_*`
schema, the real `ratio_math.py`-generated carrier-ratio math) -- not a
simplified stand-in schema. Requires `calliope==0.7.0` and CBC: use the `scenario_env` conda environment
(`conda env create -f infrastructure/env/scenario_env.yml`; Python 3.12,
CBC via `coincbc`), verified to reproduce the earlier `.venv_calliope_check/`
results exactly.

Usage (from the scenario root, scenarios/NL/loenen_gas_free/):
    python scripts/solve_single_building.py bldg_8
    python scripts/solve_single_building.py bldg_8 --out outputs/per_building/bldg_8.json
    python scripts/solve_single_building.py bldg_8 --no-cooling   # heating-only variant

``--no-cooling`` solves the heating-only variant from the *same* node
files: it drops the node's ``demand_cool`` and every ``chiller_*`` tech
(and the cooling data table), so both variants share identical heating
inputs and differ only by the cooling service. ``--no-biomass`` likewise
drops every biomass technology and the pellet supply (an all-electric
gas-free variant), testing the unconstrained-biomass assumption
(constraints.md 7). ``--ev {smart,uncontrolled,v2g,none}`` selects the
electric-vehicle variant for a building that has one (docs/phase6_ev.md).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import calliope
import pandas as pd
from ruamel.yaml import YAML

SCENARIO_ROOT = Path(__file__).resolve().parent.parent
_yaml = YAML()
_yaml.default_flow_style = False
_yaml.width = 4096


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        _yaml.dump(data, fh)


def _is_cooling_tech(tech_id: str) -> bool:
    return tech_id == "demand_cool" or tech_id.startswith("chiller_")


def _is_biomass_tech(tech_id: str) -> bool:
    return "biomass" in tech_id


def _apply_building_scale_fallback(node: dict, peak_heat_kw: float) -> None:
    """Re-apply build_nodes.py's building-scale fallback for THIS variant.

    build_nodes.py gives a node the building-scale heat techs when its peak
    heat demand exceeds 90 % of the combined household-scale ceiling -- but
    evaluates that with every household tech present. Once a variant removes
    some (``--no-biomass`` drops the 15 kW pellet boiler: 75 -> 60 kW), the
    same rule must be evaluated on what remains, or dwellings with a 61-64 kW
    peak are infeasible. Same rule, same 90 % margin, applied per variant.
    """
    from build_nodes import _BUILDING_TECH_IDS, _TECHS_EXPORT_PATH, _cap

    techs = _yaml.load(_TECHS_EXPORT_PATH.open(encoding="utf-8"))["techs"]
    household_heat = [
        t
        for t in node["techs"]
        if t.endswith("_household") and t.startswith(("boiler_", "heat_pump_", "chp_"))
    ]
    ceiling = sum(_cap(techs[t]) for t in household_heat)
    if peak_heat_kw > 0.9 * ceiling:
        for t in _BUILDING_TECH_IDS:
            if not _is_biomass_tech(t):
                node["techs"].setdefault(t, {})


def _node_column(csv_path: Path, node: str) -> pd.DataFrame | None:
    """``node``'s column of a wide data-table CSV, or ``None`` if the CSV
    has no such column (e.g. an EV table for a building without an EV)."""
    if node not in pd.read_csv(csv_path, index_col=0, nrows=0).columns:
        return None
    index_name = pd.read_csv(csv_path, nrows=0).columns[0]
    return pd.read_csv(csv_path, index_col=0, usecols=lambda c: c in (index_name, node))


def _apply_ev_variant(
    node: dict, ev: str, data_tables: dict, nodes_dir: str = "nodes"
) -> None:
    """Switch the node's EV technologies to one variant, in place.

    ``smart`` (default): the nodes.yaml wiring -- charger, battery, driving
    demand, away charging -- so the optimiser schedules charging.
    ``uncontrolled``: occupancy's charging-on-plug-in profile as a fixed
    electricity demand instead (the baseline). ``v2g``: smart plus the
    vehicle-to-grid discharger, with the same availability series as the
    charger. ``none``: no EV at all.
    """
    from build_nodes import _EV_CHARGER, _EV_NODE_TECH_IDS, _EV_V2G

    if ev not in EV_VARIANTS:
        raise ValueError(f"ev variant must be one of {EV_VARIANTS}, got {ev!r}")
    has_ev = _EV_CHARGER in node["techs"]
    if not has_ev or ev in ("smart",):
        return
    if ev in ("uncontrolled", "none"):
        node["techs"] = {
            t: v for t, v in node["techs"].items() if t not in _EV_NODE_TECH_IDS
        }
    if ev == "uncontrolled":
        node["techs"]["demand_ev_uncontrolled"] = {}
        data_tables["data_tables"]["loenen_ev_uncontrolled"] = {
            "table": f"{nodes_dir}/ev_uncontrolled.csv",
            "rows": "timesteps",
            "columns": "nodes",
            "add_dims": {
                "techs": "demand_ev_uncontrolled",
                "inputs": "sink_use_equals",
            },
        }
    if ev == "v2g":
        node["techs"][_EV_V2G] = {}
        availability = dict(data_tables["data_tables"]["loenen_ev_availability"])
        availability["add_dims"] = {
            "techs": _EV_V2G,
            "inputs": "flow_out_max_relative",
        }
        data_tables["data_tables"]["loenen_ev_v2g_availability"] = availability


#: EV variants accepted by --ev (see _apply_ev_variant).
EV_VARIANTS = ("smart", "uncontrolled", "v2g", "none")


def build_single_building_model(
    building_node: str,
    work_dir: Path,
    cooling: bool = True,
    biomass: bool = True,
    ev: str = "smart",
    nodes_dir: str = "nodes",
) -> Path:
    """Write a one-node model into ``work_dir`` that imports this
    scenario's real tech export / additional_math, and solves only
    ``building_node``'s own full-year demand. Returns the model.yaml path.

    Every variant works by removing (or adding) techs at the node; a data
    table is then kept only if its tech is still at the node and its CSV
    has this node's column, so the per-variant table bookkeeping lives in
    one place. A table without ``columns`` (no node dimension, e.g. the
    hourly grid price) applies to every node and is copied whole.

    ``nodes_dir`` is the build_nodes.py output folder under the scenario
    root (``nodes`` by default; e.g. ``nodes_day_ahead`` for a build with
    the hourly grid price).
    """
    nodes_root = SCENARIO_ROOT / nodes_dir
    nodes_full = _yaml.load((nodes_root / "nodes.yaml").open(encoding="utf-8"))
    if building_node not in nodes_full["nodes"]:
        raise ValueError(f"'{building_node}' not found in {nodes_dir}/nodes.yaml")
    node = dict(nodes_full["nodes"][building_node])
    data_tables = _yaml.load((nodes_root / "data_tables.yaml").open(encoding="utf-8"))
    if not cooling:
        node["techs"] = {
            t: v for t, v in node["techs"].items() if not _is_cooling_tech(t)
        }
    if not biomass:
        heat = _node_column(nodes_root / "demand_heat.csv", building_node)
        assert heat is not None
        node["techs"] = {
            t: v for t, v in node["techs"].items() if not _is_biomass_tech(t)
        }
        _apply_building_scale_fallback(node, float(heat[building_node].max()))
    _apply_ev_variant(node, ev, data_tables, nodes_dir)
    single_node = {"nodes": {building_node: node}}
    _write_yaml(work_dir / "nodes.yaml", single_node)

    (work_dir / nodes_dir).mkdir(parents=True, exist_ok=True)
    kept: dict = {}
    for key, table in data_tables["data_tables"].items():
        if table["add_dims"]["techs"] not in node["techs"]:
            continue
        source = SCENARIO_ROOT / table["table"]
        if "columns" not in table:
            (work_dir / table["table"]).write_bytes(source.read_bytes())
            kept[key] = table
            continue
        column = _node_column(source, building_node)
        if column is None:
            continue
        column.index.name = ""
        column.to_csv(work_dir / table["table"])
        kept[key] = table
    _write_yaml(work_dir / nodes_dir / "data_tables.yaml", {"data_tables": kept})

    model_yaml = {
        "config": {
            "init": {
                "name": f"Loenen gas-free single-building solve ({building_node})",
                "calliope_version": "0.7.0",
                "math_paths": {
                    "additional_math": str(
                        SCENARIO_ROOT
                        / "technologies/export/loenen_gas_free_techs.additional_math.yaml"
                    ).replace("\\", "/")
                },
                "extra_math": ["additional_math"],
                "mode": "base",
            },
            "build": {},
            "solve": {"solver": "cbc"},
        },
        "import": [
            str(
                SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.yaml"
            ).replace("\\", "/"),
            str(nodes_root / "demand_techs.yaml").replace("\\", "/"),
            "nodes.yaml",
            f"{nodes_dir}/data_tables.yaml",
        ],
    }
    model_path = work_dir / "model.yaml"
    _write_yaml(model_path, model_yaml)
    return model_path


def solve(
    building_node: str,
    work_dir: Path,
    cooling: bool = True,
    biomass: bool = True,
    ev: str = "smart",
    nodes_dir: str = "nodes",
) -> dict:
    model_path = build_single_building_model(
        building_node,
        work_dir,
        cooling=cooling,
        biomass=biomass,
        ev=ev,
        nodes_dir=nodes_dir,
    )
    t0 = time.time()
    m = calliope.read_yaml(str(model_path))
    m.build()
    m.solve()
    elapsed = time.time() - t0

    flow_cap = m.results["flow_cap"].to_dataframe().reset_index()
    cost = m.results["cost"].to_dataframe().reset_index()

    def _annual(var: str) -> dict[str, float]:
        """Annual energy (kWh, hourly timesteps) per tech|carrier, NaN/zero dropped."""
        df = m.results[var].sum("timesteps").to_dataframe(name=var).reset_index()
        return {
            f"{r['techs']}|{r['carriers']}": float(r[var])
            for _, r in df.iterrows()
            if r[var] == r[var] and abs(r[var]) > 1e-6
        }

    return {
        "building": building_node,
        "solved_in_s": round(elapsed, 2),
        "total_cost": float(cost["cost"].sum()),
        "cost_by_tech": {
            str(t): float(v)
            for t, v in cost.groupby("techs")["cost"].sum().items()
            if v == v and abs(v) > 1e-9
        },
        "flow_cap": {
            f"{r['techs']}|{r['carriers']}": float(r["flow_cap"])
            for _, r in flow_cap.iterrows()
            if r["flow_cap"]
            == r["flow_cap"]  # drop NaN (tech/carrier combos that don't apply)
        },
        "flow_out_annual_kwh": _annual("flow_out"),
        "flow_in_annual_kwh": _annual("flow_in"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("building", help="Node id, e.g. bldg_8 (see nodes/nodes.yaml)")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write result JSON here (default: print to stdout)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Scratch dir for the generated one-node model (default: a temp dir under outputs/)",
    )
    parser.add_argument(
        "--no-cooling", action="store_true", help="Heating-only variant (drop cooling)"
    )
    parser.add_argument(
        "--no-biomass", action="store_true", help="All-electric variant (drop biomass)"
    )
    parser.add_argument(
        "--ev",
        choices=EV_VARIANTS,
        default="smart",
        help="EV variant for a building that has one (default: smart charging)",
    )
    parser.add_argument(
        "--nodes-dir",
        default="nodes",
        help="build_nodes.py output folder under the scenario root (default: nodes)",
    )
    args = parser.parse_args()

    work_dir = args.work_dir or (
        SCENARIO_ROOT / "outputs/per_building" / args.building / "_model"
    )
    result = solve(
        args.building,
        work_dir,
        cooling=not args.no_cooling,
        biomass=not args.no_biomass,
        ev=args.ev,
        nodes_dir=args.nodes_dir,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
        print(f"Wrote {args.out}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
