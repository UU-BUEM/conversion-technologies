"""Phase 5b: solve the real Loenen gas-free scenario for every building,
independently and in parallel, then sum to the region-wide answer.

Valid because of the same block-diagonal structure
`solve_single_building.py` relies on -- see
docs/phase5_per_building_decomposition.md. Each worker process runs
`solve_single_building.solve()` for one node; results are independent by
construction (no shared state, no coordination needed between workers).

Usage (from the scenario root, scenarios/NL/loenen_gas_free/):
    python scripts/solve_all_buildings.py --workers 16
    python scripts/solve_all_buildings.py --workers 16 --limit 50  # smoke test
    python scripts/solve_all_buildings.py --workers 16 --ev uncontrolled  # EV baseline
    python scripts/solve_all_buildings.py --workers 12 --no-cooling         --out outputs/heating_only/all_buildings_results.json         --per-building-dir outputs/heating_only/per_building
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ruamel.yaml import YAML
from solve_single_building import EV_VARIANTS, SCENARIO_ROOT, solve

_yaml = YAML()


def _all_building_ids(nodes_dir: str = "nodes") -> list[str]:
    nodes_full = _yaml.load(
        (SCENARIO_ROOT / nodes_dir / "nodes.yaml").open(encoding="utf-8")
    )
    return list(nodes_full["nodes"].keys())


def _solve_one(
    building: str,
    per_building_dir: Path,
    cooling: bool,
    biomass: bool = True,
    ev: str = "smart",
    nodes_dir: str = "nodes",
    solver: str = "cbc",
) -> dict:
    work_dir = per_building_dir / building / "_model"
    try:
        return solve(
            building,
            work_dir,
            cooling=cooling,
            biomass=biomass,
            ev=ev,
            nodes_dir=nodes_dir,
            solver=solver,
            threads=1,
        )
    except Exception as exc:  # noqa: BLE001 -- one building's failure must not kill the batch
        return {"building": building, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workers", type=int, default=8, help="Parallel worker processes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only solve the first N buildings (smoke test)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=SCENARIO_ROOT / "outputs/all_buildings_results.json",
        help="Combined results JSON (per-building results + region total)",
    )
    parser.add_argument(
        "--per-building-dir",
        type=Path,
        default=SCENARIO_ROOT / "outputs/per_building",
        help="Scratch dir for each building's one-node model (default: outputs/per_building)",
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
        help="EV variant for buildings that have one (default: smart charging)",
    )
    parser.add_argument(
        "--nodes-dir",
        default="nodes",
        help="build_nodes.py output folder under the scenario root (default: nodes)",
    )
    parser.add_argument(
        "--solver",
        choices=("cbc", "highs", "gurobi"),
        default="cbc",
        help="cbc (default, Pyomo backend), highs or gurobi (Calliope's native backends)",
    )
    args = parser.parse_args()

    buildings = _all_building_ids(args.nodes_dir)
    if args.limit:
        buildings = buildings[: args.limit]

    print(f"Solving {len(buildings)} buildings with {args.workers} parallel workers...")
    t0 = time.time()
    results: list[dict] = []
    failures: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _solve_one,
                b,
                args.per_building_dir,
                not args.no_cooling,
                not args.no_biomass,
                args.ev,
                args.nodes_dir,
                args.solver,
            ): b
            for b in buildings
        }
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if "error" in r:
                failures.append(r)
                print(f"[{i}/{len(buildings)}] {r['building']}: FAILED -- {r['error']}")
            else:
                results.append(r)
                print(
                    f"[{i}/{len(buildings)}] {r['building']}: cost={r['total_cost']:.2f}"
                )

    elapsed = time.time() - t0
    region_total_cost = sum(r["total_cost"] for r in results)
    summary = {
        "nodes_dir": args.nodes_dir,
        "variant": ("heating_only" if args.no_cooling else "heating_and_cooling")
        + ("_no_biomass" if args.no_biomass else "")
        + ("" if args.ev == "smart" else f"_ev_{args.ev}"),
        "n_buildings_requested": len(buildings),
        "n_solved": len(results),
        "n_failed": len(failures),
        "wall_clock_s": round(elapsed, 1),
        "region_total_cost": region_total_cost,
        "per_building": results,
        "failures": failures,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))
    print(
        f"\n{len(results)}/{len(buildings)} solved in {elapsed:.1f}s wall-clock. "
        f"Region total cost: {region_total_cost:.2f}. Wrote {args.out}"
    )
    if failures:
        print(
            f"WARNING: {len(failures)} building(s) failed -- see '{args.out}' for details"
        )


if __name__ == "__main__":
    main()
