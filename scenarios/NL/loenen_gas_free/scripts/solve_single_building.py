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
simplified stand-in schema. Requires a real `calliope==0.7.0` install
(same as `scripts/solve_full.py`; see docs/phase4_solve.md for how this
repo's own `.venv_calliope_check/` was set up) and CBC on PATH.

Usage (from the scenario root, scenarios/NL/loenen_gas_free/):
    python scripts/solve_single_building.py bldg_8
    python scripts/solve_single_building.py bldg_8 --out outputs/per_building/bldg_8.json
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


def build_single_building_model(building_node: str, work_dir: Path) -> Path:
    """Write a one-node model into ``work_dir`` that imports this
    scenario's real tech export / additional_math, and solves only
    ``building_node``'s own full-year demand. Returns the model.yaml path.
    """
    nodes_full = _yaml.load((SCENARIO_ROOT / "nodes/nodes.yaml").open(encoding="utf-8"))
    if building_node not in nodes_full["nodes"]:
        raise ValueError(f"'{building_node}' not found in nodes/nodes.yaml")
    single_node = {"nodes": {building_node: nodes_full["nodes"][building_node]}}
    _write_yaml(work_dir / "nodes.yaml", single_node)

    heat = pd.read_csv(SCENARIO_ROOT / "nodes/demand_heat.csv", index_col=0)[[building_node]]
    elec = pd.read_csv(SCENARIO_ROOT / "nodes/demand_elec.csv", index_col=0)[[building_node]]
    cool = pd.read_csv(SCENARIO_ROOT / "nodes/demand_cool.csv", index_col=0)[[building_node]]
    heat.index.name = ""
    elec.index.name = ""
    cool.index.name = ""
    (work_dir / "nodes").mkdir(parents=True, exist_ok=True)
    heat.to_csv(work_dir / "nodes/demand_heat.csv")
    elec.to_csv(work_dir / "nodes/demand_elec.csv")
    cool.to_csv(work_dir / "nodes/demand_cool.csv")

    data_tables = _yaml.load((SCENARIO_ROOT / "nodes/data_tables.yaml").open(encoding="utf-8"))
    _write_yaml(work_dir / "nodes/data_tables.yaml", data_tables)

    model_yaml = {
        "config": {
            "init": {
                "name": f"Loenen gas-free single-building solve ({building_node})",
                "calliope_version": "0.7.0",
                "math_paths": {
                    "additional_math": str(
                        (SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.additional_math.yaml")
                    ).replace("\\", "/")
                },
                "extra_math": ["additional_math"],
                "mode": "base",
            },
            "build": {},
            "solve": {"solver": "cbc"},
        },
        "import": [
            str((SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.yaml")).replace("\\", "/"),
            str((SCENARIO_ROOT / "nodes/demand_techs.yaml")).replace("\\", "/"),
            "nodes.yaml",
            "nodes/data_tables.yaml",
        ],
    }
    model_path = work_dir / "model.yaml"
    _write_yaml(model_path, model_yaml)
    return model_path


def solve(building_node: str, work_dir: Path) -> dict:
    model_path = build_single_building_model(building_node, work_dir)
    t0 = time.time()
    m = calliope.read_yaml(str(model_path))
    m.build()
    m.solve()
    elapsed = time.time() - t0

    flow_cap = m.results["flow_cap"].to_dataframe().reset_index()
    cost = m.results["cost"].to_dataframe().reset_index()
    return {
        "building": building_node,
        "solved_in_s": round(elapsed, 2),
        "total_cost": float(cost["cost"].sum()),
        "flow_cap": {
            f"{r['techs']}|{r['carriers']}": float(r["flow_cap"])
            for _, r in flow_cap.iterrows()
            if r["flow_cap"] == r["flow_cap"]  # drop NaN (tech/carrier combos that don't apply)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("building", help="Node id, e.g. bldg_8 (see nodes/nodes.yaml)")
    parser.add_argument(
        "--out", type=Path, default=None, help="Write result JSON here (default: print to stdout)"
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Scratch dir for the generated one-node model (default: a temp dir under outputs/)",
    )
    args = parser.parse_args()

    work_dir = args.work_dir or (SCENARIO_ROOT / "outputs/per_building" / args.building / "_model")
    result = solve(args.building, work_dir)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
        print(f"Wrote {args.out}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
