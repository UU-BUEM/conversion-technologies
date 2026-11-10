"""Phase 5a: solve the real Loenen gas-free scenario for ONE building.

Per-building decomposition rationale: see
docs/phase5_per_building_decomposition.md. In short, this scenario's
real `nodes/nodes.yaml` has no `links:` (no cross-building transmission)
and no storage tech anywhere in `technologies/export/
loenen_gas_free_techs.yaml` -- every tech is `base_tech: conversion`,
`demand`, or `supply`. With no shared variable across nodes, the full
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
(constraints.md 7).
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


def build_single_building_model(
    building_node: str, work_dir: Path, cooling: bool = True, biomass: bool = True
) -> Path:
    """Write a one-node model into ``work_dir`` that imports this
    scenario's real tech export / additional_math, and solves only
    ``building_node``'s own full-year demand. Returns the model.yaml path.
    """
    nodes_full = _yaml.load((SCENARIO_ROOT / "nodes/nodes.yaml").open(encoding="utf-8"))
    if building_node not in nodes_full["nodes"]:
        raise ValueError(f"'{building_node}' not found in nodes/nodes.yaml")
    node = dict(nodes_full["nodes"][building_node])
    if not cooling:
        node["techs"] = {
            t: v for t, v in node["techs"].items() if not _is_cooling_tech(t)
        }
    heat = pd.read_csv(SCENARIO_ROOT / "nodes/demand_heat.csv", index_col=0)[
        [building_node]
    ]
    if not biomass:
        node["techs"] = {
            t: v for t, v in node["techs"].items() if not _is_biomass_tech(t)
        }
        _apply_building_scale_fallback(node, float(heat[building_node].max()))
    single_node = {"nodes": {building_node: node}}
    _write_yaml(work_dir / "nodes.yaml", single_node)

    elec = pd.read_csv(SCENARIO_ROOT / "nodes/demand_elec.csv", index_col=0)[
        [building_node]
    ]
    cool = pd.read_csv(SCENARIO_ROOT / "nodes/demand_cool.csv", index_col=0)[
        [building_node]
    ]
    heat.index.name = ""
    elec.index.name = ""
    cool.index.name = ""
    (work_dir / "nodes").mkdir(parents=True, exist_ok=True)
    heat.to_csv(work_dir / "nodes/demand_heat.csv")
    elec.to_csv(work_dir / "nodes/demand_elec.csv")
    cool.to_csv(work_dir / "nodes/demand_cool.csv")

    data_tables = _yaml.load(
        (SCENARIO_ROOT / "nodes/data_tables.yaml").open(encoding="utf-8")
    )
    if not cooling:
        data_tables["data_tables"].pop("loenen_demand_cool", None)
    _write_yaml(work_dir / "nodes/data_tables.yaml", data_tables)

    model_yaml = {
        "config": {
            "init": {
                "name": f"Loenen gas-free single-building solve ({building_node})",
                "calliope_version": "0.7.0",
                "math_paths": {
                    "additional_math": str(
                        (
                            SCENARIO_ROOT
                            / "technologies/export/loenen_gas_free_techs.additional_math.yaml"
                        )
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
                (SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.yaml")
            ).replace("\\", "/"),
            str((SCENARIO_ROOT / "nodes/demand_techs.yaml")).replace("\\", "/"),
            "nodes.yaml",
            "nodes/data_tables.yaml",
        ],
    }
    model_path = work_dir / "model.yaml"
    _write_yaml(model_path, model_yaml)
    return model_path


def solve(
    building_node: str, work_dir: Path, cooling: bool = True, biomass: bool = True
) -> dict:
    model_path = build_single_building_model(
        building_node, work_dir, cooling=cooling, biomass=biomass
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
    args = parser.parse_args()

    work_dir = args.work_dir or (
        SCENARIO_ROOT / "outputs/per_building" / args.building / "_model"
    )
    result = solve(
        args.building,
        work_dir,
        cooling=not args.no_cooling,
        biomass=not args.no_biomass,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
        print(f"Wrote {args.out}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
