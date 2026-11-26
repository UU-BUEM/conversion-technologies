"""Compare two solve_all_buildings.py results files building by building,
e.g. the smart-charging and uncontrolled EV variants (docs/phase6_ev.md).

Usage (from the scenario root)::

    python scripts/compare_ev_variants.py \\
        outputs/v4/heating_and_cooling_ev_smart/all_buildings_results.json \\
        outputs/v4/heating_and_cooling_ev_uncontrolled/all_buildings_results.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import pandas as pd

SCENARIO_ROOT = Path(__file__).resolve().parent.parent


def _per_building(path: Path) -> tuple[pd.DataFrame, dict]:
    data = json.loads(path.read_text())
    rows = []
    for r in data["per_building"]:
        grid = sum(
            v
            for k, v in r["flow_out_annual_kwh"].items()
            if k.startswith("supply_grid_electricity|")
        )
        rows.append(
            {"building": r["building"], "cost": r["total_cost"], "grid_kwh": grid}
        )
    return pd.DataFrame(rows).set_index("building"), data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path, help="results JSON, e.g. smart")
    parser.add_argument("b", type=Path, help="results JSON, e.g. uncontrolled")
    args = parser.parse_args()

    a, data_a = _per_building(args.a)
    b, data_b = _per_building(args.b)
    ev_nodes = set(
        pd.read_csv(SCENARIO_ROOT / "nodes/ev_drive.csv", index_col=0, nrows=0).columns
    )
    for name, data in ((args.a, data_a), (args.b, data_b)):
        print(
            f"{name.parent.name}: {data['n_solved']}/{data['n_buildings_requested']} "
            f"solved, {data['n_failed']} failed, region cost "
            f"{data['region_total_cost']:,.0f} EUR/yr, {data['wall_clock_s'] / 60:.0f} min"
        )
    both = a.merge(b, left_index=True, right_index=True, suffixes=("_a", "_b"))
    both["d_cost"] = both["cost_a"] - both["cost_b"]
    both["d_grid"] = both["grid_kwh_a"] - both["grid_kwh_b"]
    both["has_ev"] = both.index.isin(ev_nodes)
    for has_ev, group in both.groupby("has_ev"):
        label = "EV buildings" if has_ev else "non-EV buildings"
        print(
            f"{label} (n={len(group)}): cost a-b total {group.d_cost.sum():,.2f} EUR/yr, "
            f"per building median {statistics.median(group.d_cost):.2f}, "
            f"range {group.d_cost.min():.2f}..{group.d_cost.max():.2f}; "
            f"grid a-b total {group.d_grid.sum():,.0f} kWh/yr"
        )
    print(
        f"Region grid import: a {both.grid_kwh_a.sum() / 1000:,.0f} MWh, "
        f"b {both.grid_kwh_b.sum() / 1000:,.0f} MWh"
    )


if __name__ == "__main__":
    main()
