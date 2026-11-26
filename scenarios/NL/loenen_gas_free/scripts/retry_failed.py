"""Re-solve the buildings a solve_all_buildings.py run reported as failed, and
merge the successes back into that run's results JSON.

Typical failures are CBC ``-stop`` timeouts from running many solver
processes at once (docs/phase5_per_building_decomposition.md, section 7),
which succeed when retried with few workers.

Usage (from scripts/)::

    python retry_failed.py ../outputs/v2_sourced/heating_only/all_buildings_results.json --no-cooling
    python retry_failed.py ../outputs/v2_sourced/heating_and_cooling/all_buildings_results.json
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
from solve_all_buildings import _solve_one
from solve_single_building import EV_VARIANTS, SCENARIO_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("--no-cooling", action="store_true")
    parser.add_argument("--no-biomass", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--ev",
        choices=EV_VARIANTS,
        default=None,
        help="EV variant of the original run (default: read from the results JSON)",
    )
    parser.add_argument(
        "--nodes-dir",
        default=None,
        help="Nodes folder of the original run (default: read from the results JSON)",
    )
    parser.add_argument(
        "--also-ev-nodes",
        action="store_true",
        help=(
            "Also re-solve every building with an EV (e.g. after an EV wiring "
            "change), replacing its earlier result"
        ),
    )
    args = parser.parse_args()

    data = json.loads(args.results.read_text())
    failed = [f["building"] for f in data["failures"]]
    if args.also_ev_nodes:
        nodes_dir_ = args.nodes_dir or data.get("nodes_dir", "nodes")
        ev_csv = SCENARIO_ROOT / nodes_dir_ / "ev_drive.csv"
        ev_nodes = list(pd.read_csv(ev_csv, index_col=0, nrows=0).columns)
        failed = sorted(set(failed) | set(ev_nodes))
    if not failed:
        print("no failures to retry")
        return
    # Re-solve exactly the original run's variant: its nodes folder (e.g. the
    # day-ahead price build) and EV variant are recorded in the results JSON.
    nodes_dir = args.nodes_dir or data.get("nodes_dir", "nodes")
    ev = args.ev or next(
        (v for v in EV_VARIANTS if data.get("variant", "").endswith(f"_ev_{v}")),
        "smart",
    )
    print(f"retrying {len(failed)} building(s): ev={ev}, nodes_dir={nodes_dir}")
    per_building_dir = args.results.parent / "per_building"
    n = len(failed)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        retried = list(
            pool.map(
                _solve_one,
                failed,
                [per_building_dir] * n,
                [not args.no_cooling] * n,
                [not args.no_biomass] * n,
                [ev] * n,
                [nodes_dir] * n,
            )
        )

    still_failed = [r for r in retried if "error" in r]
    redone = set(failed)
    data["per_building"] = [
        r for r in data["per_building"] if r["building"] not in redone
    ]
    data["per_building"].extend(r for r in retried if "error" not in r)
    data["failures"] = still_failed
    data["n_solved"] = len(data["per_building"])
    data["n_failed"] = len(still_failed)
    data["region_total_cost"] = sum(r["total_cost"] for r in data["per_building"])
    data["retried"] = failed
    args.results.write_text(json.dumps(data, indent=2))
    print(
        f"retried {len(failed)}: {len(failed) - len(still_failed)} solved, "
        f"{len(still_failed)} still failed; region total {data['region_total_cost']:.2f}"
    )


if __name__ == "__main__":
    main()
