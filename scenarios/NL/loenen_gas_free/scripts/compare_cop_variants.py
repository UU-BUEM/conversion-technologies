"""Compare per-building results across heat pump COP variants (fixed design
COP vs hourly COP), region-wide.

Reads each variant's ``all_buildings_results.json`` (``solve_all_buildings.py``)
and writes one table: total and median cost per dwelling, the share of heat
from each heating family, installed heat pump capacity and the number of
dwellings that install one, the electricity drawn by heat pumps and by all
heating, grid electricity, and pellet use. Heat pump seasonal COP is
reported as delivered heat over their electricity (heat-weighted, from the
solved flows).

Usage (scenario root)::

    python scripts/compare_cop_variants.py \\
        design=outputs/v5/day_ahead_ev_smart_design_cop \\
        hourly=outputs/v5/day_ahead_ev_smart_hourly_cop \\
        hourly_matched=outputs/v5/day_ahead_ev_smart_matched_cop \\
        --out outputs/v5/cop_comparison.csv
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd

HEAT_FAMILIES = {
    "boiler_biomass": "pellet boiler",
    "heat_pump_electric": "air-source HP",
    "heat_pump_geothermal": "ground-source HP",
    "boiler_electric": "electric boiler",
}


def _family(tech: str) -> str | None:
    for prefix, name in HEAT_FAMILIES.items():
        if tech.startswith(prefix):
            return name
    return None


def summarise(results_json: Path) -> dict:
    data = json.loads(results_json.read_text())
    rows = data["per_building"]
    heat: dict[str, float] = defaultdict(float)
    elec_in: dict[str, float] = defaultdict(float)
    cap: dict[str, float] = defaultdict(float)
    n_with: dict[str, int] = defaultdict(int)
    grid = pellets = 0.0
    for b in rows:
        seen: set[str] = set()
        for key, kwh in b["flow_out_annual_kwh"].items():
            tech, carrier = key.split("|")
            fam = _family(tech)
            if fam and carrier == "heat":
                heat[fam] += kwh
            if tech == "supply_grid_electricity":
                grid += kwh
            if tech == "supply_biomass":
                pellets += kwh
        for key, kwh in b["flow_in_annual_kwh"].items():
            tech, carrier = key.split("|")
            fam = _family(tech)
            if fam and carrier == "electricity":
                elec_in[fam] += kwh
        for key, kw in b["flow_cap"].items():
            tech, carrier = key.split("|")
            fam = _family(tech)
            if fam and carrier == "heat" and kw > 0.01:
                cap[fam] += kw
                seen.add(fam)
        for fam in seen:
            n_with[fam] += 1
    total_heat = sum(heat.values())
    costs = [b["total_cost"] for b in rows]
    out = {
        "buildings_solved": len(rows),
        "buildings_failed": len(data.get("failures", [])),
        "total_cost_meur": sum(costs) / 1e6,
        "median_cost_per_dwelling_eur": statistics.median(costs),
        "heat_gwh": total_heat / 1e6,
        "grid_electricity_gwh": grid / 1e6,
        "pellets_gwh": pellets / 1e6,
        "heating_electricity_gwh": sum(elec_in.values()) / 1e6,
    }
    for fam in HEAT_FAMILIES.values():
        out[f"heat_share_{fam}"] = heat[fam] / total_heat if total_heat else 0.0
        out[f"capacity_mw_{fam}"] = cap[fam] / 1e3
        out[f"dwellings_with_{fam}"] = n_with[fam]
    for fam in ("air-source HP", "ground-source HP"):
        out[f"seasonal_cop_{fam}"] = (
            heat[fam] / elec_in[fam] if elec_in[fam] > 0 else float("nan")
        )
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("variants", nargs="+", help="name=results_dir")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    table = {}
    for item in args.variants:
        name, folder = item.split("=", 1)
        table[name] = summarise(Path(folder) / "all_buildings_results.json")
    df = pd.DataFrame(table)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out)
    with pd.option_context("display.float_format", "{:,.4g}".format):
        print(df.to_string())


if __name__ == "__main__":
    main()
