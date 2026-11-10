"""Summarise a solve_all_buildings.py results JSON into region-level tables.

For each variant, writes ``summary.csv`` next to the results JSON, with one
row per (technology family, output carrier):

* ``n_buildings``: buildings that installed it (any scale);
* ``capacity_kw``: installed capacity, summed over buildings;
* ``energy_mwh`` and ``share_of_carrier``: annual output and its share of
  that carrier's total supply;
* ``cost_keur``: annualised cost (investment annuity + O&M) of that family.

It also prints headline numbers: total and median annual cost per building,
and grid electricity and pellet use.

Usage::

    python scripts/summarize_results.py outputs/v2_sourced/heating_only/all_buildings_results.json
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def family(tech_id: str) -> str:
    """'boiler_biomass_household' -> 'boiler_biomass' (scale suffix dropped)."""
    for scale in ("_household", "_building", "_community"):
        if tech_id.endswith(scale):
            return tech_id[: -len(scale)]
    return tech_id


def summarise(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    rows = data["per_building"]
    n_bldg: dict[tuple, set] = defaultdict(set)
    cap: dict[tuple, float] = defaultdict(float)
    energy: dict[tuple, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    for r in rows:
        for key, v in r["flow_out_annual_kwh"].items():
            tech, carrier = key.split("|")
            if tech.startswith("demand"):
                continue
            energy[(family(tech), carrier)] += v
        for key, v in r["flow_cap"].items():
            tech, carrier = key.split("|")
            if tech.startswith(("demand", "supply")) or v <= 1e-3:
                continue
            # output-side capacity only (flow_cap also lists input carriers)
            if carrier in ("heat", "cooling") or (
                tech.startswith("chp") and carrier == "electricity"
            ):
                cap[(family(tech), carrier)] += v
                n_bldg[(family(tech), carrier)].add(r["building"])
        for tech, v in r["cost_by_tech"].items():
            cost[family(tech)] += v

    totals: dict[str, float] = defaultdict(float)
    for (fam, carrier), v in energy.items():
        if not fam.startswith("supply"):
            totals[carrier] += v

    out = []
    for key in sorted(set(energy) | set(cap)):
        fam, carrier = key
        out.append(
            {
                "technology": fam,
                "carrier": carrier,
                "n_buildings": len(n_bldg.get(key, ())),
                "capacity_kw": round(cap.get(key, 0.0), 1),
                "energy_mwh": round(energy.get(key, 0.0) / 1000, 1),
                "share_of_carrier": (
                    round(energy.get(key, 0.0) / totals[carrier], 4)
                    if totals.get(carrier) and not fam.startswith("supply")
                    else ""
                ),
                "cost_keur": round(cost.get(fam, 0.0) / 1000, 1),
            }
        )
    with (path.parent / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)

    costs = [r["total_cost"] for r in rows]
    print(
        f"{path}: {data['n_solved']}/{data['n_buildings_requested']} solved, "
        f"{data['n_failed']} failed, wall clock {data['wall_clock_s'] / 3600:.2f} h"
    )
    print(
        f"  region annual cost: EUR {sum(costs) / 1e6:.3f} M; per building median "
        f"EUR {statistics.median(costs):,.0f} (P10 {sorted(costs)[len(costs) // 10]:,.0f}, "
        f"P90 {sorted(costs)[9 * len(costs) // 10]:,.0f})"
    )
    for o in out:
        if o["share_of_carrier"] != "" or o["technology"].startswith("supply"):
            print(
                f"  {o['technology']:32} {o['carrier']:12} n={o['n_buildings']:5} "
                f"E={o['energy_mwh']:9.1f} MWh share={o['share_of_carrier']} "
                f"cost={o['cost_keur']} kEUR"
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path, nargs="+")
    for p in parser.parse_args().results:
        summarise(p)


if __name__ == "__main__":
    main()
