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

from solve_all_buildings import _solve_one


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("--no-cooling", action="store_true")
    parser.add_argument("--no-biomass", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    data = json.loads(args.results.read_text())
    failed = [f["building"] for f in data["failures"]]
    if not failed:
        print("no failures to retry")
        return
    per_building_dir = args.results.parent / "per_building"
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        retried = list(
            pool.map(
                _solve_one,
                failed,
                [per_building_dir] * len(failed),
                [not args.no_cooling] * len(failed),
                [not args.no_biomass] * len(failed),
            )
        )

    still_failed = [r for r in retried if "error" in r]
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
