"""Phase 3: assemble per-building Calliope nodes for the Loenen gas-free scenario.

Joins Phase 1's per-building hourly demand (buem, via
``scripts/run_region_hourly.py`` in the ``buem`` repo) with Phase 2's
non-gas technology catalog (this repo's ``export-all`` output) into a
single Calliope model: one node per building, a ``demand_heat``/
``demand_elec`` tech per node fed by wide-format ``data_tables`` CSVs, and
every household-scale non-gas conversion technology available at every
node for the optimizer to size.

Not run as part of this package's own test suite or CLI -- this is
scenario-specific glue, not a reusable ``conversion_technologies`` feature
(see this package's own ``docs/calliope_schema_mapping.md``, "occupancy is
out of scope": nodes/demand wiring is explicitly left to whoever builds
the full model).

Usage
-----
    python scenarios/NL/loenen_gas_free/scripts/build_nodes.py \\
        --hourly-parquet scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_hourly.parquet \\
        --out-dir scenarios/NL/loenen_gas_free/nodes
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd
from ruamel.yaml import YAML

SCENARIO_ROOT = Path(__file__).resolve().parent.parent
_TECHS_EXPORT_PATH = SCENARIO_ROOT / "technologies/export/loenen_gas_free_techs.yaml"

_ENERGY_PRICES_PATH = SCENARIO_ROOT / "energy_prices.csv"

# Technologies whose catalogue cost is only a *proxy* taken from a much
# larger plant (household/building biomass CHP from DEA's 3 MW_e pellet
# CHP; household/building absorption chillers from HRE's 500 kW unit, which
# HRE itself calls prohibitively expensive at small sizes) are deliberately
# left out: a large-plant cost would make them look artificially cheap. See
# docs/sources/parameter_sources.csv (basis = proxy) and constraints.md.
_HOUSEHOLD_TECH_IDS = [
    "boiler_electric_household",
    "boiler_biomass_household",
    "heat_pump_electric_household",
    "heat_pump_geothermal_household",
]

# Phase 5 real finding: 18 of 1,260 buildings have a peak heat demand
# (50-64 kW) above what the household-scale techs' combined flow_cap_max
# can ever supply (52 kW -- the sum of the five ceilings above), so their
# single-node model is *proven infeasible*, not merely hard to solve --
# see docs/phase5_per_building_decomposition.md's follow-up note and
# outputs/retry_failed_results.json. Fix: give any node whose own peak
# heat demand exceeds that combined household ceiling the building-scale
# techs too (added, not substituted, so the optimizer still mixes
# household + building equipment freely); every other node is unaffected.
_BUILDING_TECH_IDS = [
    "boiler_electric_building",
    "boiler_biomass_building",
    "heat_pump_electric_building",
    "heat_pump_geothermal_building",
]

# Cooling, added alongside the heating techs above. Same household/building
# fallback pattern: every node gets the household-scale chiller options;
# any node whose own peak cooling demand exceeds the combined household
# chiller capacity (with the same 10% safety margin used for heat below)
# also gets the building-scale chiller options.
_HOUSEHOLD_CHILLER_TECH_IDS = [
    "chiller_electric_household",
    "chiller_heat_pump_reversible_household",
]
_BUILDING_CHILLER_TECH_IDS = [
    "chiller_electric_building",
    "chiller_heat_pump_reversible_building",
]

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.width = 4096


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        _yaml.dump(data, fh)


def _energy_prices() -> dict[str, float]:
    """Supply-tech energy prices (EUR2025/kWh) from ``energy_prices.csv``.

    Each row there names its source and conversion (system perspective:
    excluding taxes, levies, subsidies and VAT) -- no price is hardcoded here.
    """
    with _ENERGY_PRICES_PATH.open(newline="", encoding="utf-8-sig") as fh:
        return {
            row["supply_tech"]: float(row["cost_flow_out_eur_per_kwh"])
            for row in csv.DictReader(fh)
        }


def _cap(tech_body: dict) -> float:
    """A tech's ``flow_cap_max`` in kW of its primary output carrier.

    The export indexes it on that carrier (``{data, index, dims: carriers}``),
    because Calliope 0.7 would otherwise apply a scalar ceiling to every
    carrier -- inputs included -- capping e.g. a 15 kW pellet boiler at
    15 kW of *pellets* (12.6 kW heat). See the repo's
    docs/calliope_schema_mapping.md "Capacity is per carrier".
    """
    cap = tech_body["flow_cap_max"]
    return float(cap["data"]) if isinstance(cap, dict) else float(cap)


def _household_heat_cap_total() -> float:
    """Combined max heat output of the household-scale heat-producing techs.

    Read from this scenario's own real techs export, not hardcoded, so it
    always matches whatever technologies.csv/costs.csv currently say.
    """
    techs = _yaml.load(_TECHS_EXPORT_PATH.open(encoding="utf-8"))["techs"]
    return sum(_cap(techs[tech_id]) for tech_id in _HOUSEHOLD_TECH_IDS)


def _household_cool_cap_total() -> float:
    """Combined max cooling output of the household-scale chiller techs.

    With ``flow_cap_max`` indexed on each chiller's primary output carrier
    (cooling), it bounds cooling output directly for every variant, so the
    combined ceiling is a plain sum. (Before 2026-11-10 the ceiling was a
    scalar that also bound an absorption chiller's *heat input*, which made
    its real cooling ceiling ``flow_cap_max * cop`` -- see
    .claude/chiller/resolved.md "cool-cap-margin-fix", now superseded.)
    """
    techs = _yaml.load(_TECHS_EXPORT_PATH.open(encoding="utf-8"))["techs"]
    return sum(_cap(techs[tech_id]) for tech_id in _HOUSEHOLD_CHILLER_TECH_IDS)


def build(hourly_parquet: Path, out_dir: Path) -> None:
    df = pd.read_parquet(
        hourly_parquet,
        columns=[
            "building_feature_id",
            "time",
            "Q_heat_kW",
            "dhw_kW",
            "elec_kW",
            "Q_cool_kW",
        ],
    )
    df["heat_kW"] = df["Q_heat_kW"] + df["dhw_kW"]
    # buem's own sign convention: Q_cool_kW <= 0 (a negative net heat flow),
    # never positive -- confirmed directly against this parquet (max() is
    # exactly 0.0 for every building). Calliope's sink_use_equals wants a
    # positive consumption rate, same as demand_heat/demand_elec below.
    df["cool_kW"] = (-df["Q_cool_kW"]).clip(lower=0)

    building_ids = sorted(df["building_feature_id"].unique().tolist())
    node_names = [f"bldg_{bid}" for bid in building_ids]

    heat_wide = df.pivot(index="time", columns="building_feature_id", values="heat_kW")
    elec_wide = df.pivot(index="time", columns="building_feature_id", values="elec_kW")
    cool_wide = df.pivot(index="time", columns="building_feature_id", values="cool_kW")
    heat_wide.columns = [f"bldg_{c}" for c in heat_wide.columns]
    elec_wide.columns = [f"bldg_{c}" for c in elec_wide.columns]
    cool_wide.columns = [f"bldg_{c}" for c in cool_wide.columns]
    heat_wide.index.name = "timesteps"
    elec_wide.index.name = "timesteps"
    cool_wide.index.name = "timesteps"

    out_dir.mkdir(parents=True, exist_ok=True)
    heat_csv = out_dir / "demand_heat.csv"
    elec_csv = out_dir / "demand_elec.csv"
    cool_csv = out_dir / "demand_cool.csv"
    heat_wide.to_csv(heat_csv)
    elec_wide.to_csv(elec_csv)
    cool_wide.to_csv(cool_csv)

    prices = _energy_prices()

    # Calliope's sink_use_equals convention is a positive consumption rate;
    # demand techs draw it in via carrier_in -- see Calliope's own
    # urban_scale example model for the same shape this mirrors.
    demand_techs = {
        "techs": {
            "demand_heat": {
                "base_tech": "demand",
                "name": "Heat demand (space heating + DHW)",
                "carrier_in": "heat",
                "comment": (
                    "sink_use_equals = buem's Q_heat_kW + dhw_kW, per building "
                    "(scenarios/NL/loenen_gas_free/docs/phase1_demand.md). Not "
                    "verified against a running Calliope solve -- see this "
                    "repo's docs/calliope_schema_mapping.md caveat on "
                    "additional_math, which applies here too."
                ),
            },
            "demand_elec": {
                "base_tech": "demand",
                "name": "Electricity demand (appliances; cooking already included)",
                "carrier_in": "electricity",
                "comment": (
                    "sink_use_equals = buem's elec_kW (occupancy's elecLoad). "
                    "No Loenen building in this population cooks with gas "
                    "(verified: cooking_gas_kW sums to 0 for all 1,260 "
                    "buildings), so no separate cooking carrier is modeled."
                ),
            },
            "demand_cool": {
                "base_tech": "demand",
                "name": "Cooling demand (space cooling)",
                "carrier_in": "cooling",
                "comment": (
                    "sink_use_equals = -buem's Q_cool_kW, clipped to >= 0 "
                    "(buem's own sign convention: Q_cool_kW <= 0, a negative "
                    "net heat flow). See conversion_technologies' chiller "
                    "category (docs/calliope_schema_mapping.md 'Cooling "
                    "technologies') for the electric/absorption/reversible-"
                    "heat-pump options this demand is met by. Not verified "
                    "against a running Calliope solve -- same caveat as "
                    "demand_heat above."
                ),
            },
            # Real finding (Phase 4): without a supply tech for every carrier
            # the conversion techs consume, the model is infeasible -- a
            # heat pump/boiler/CHP can only draw a carrier that something
            # actually produces. Prices (EUR2025/kWh, system perspective:
            # excluding taxes, levies, subsidies and VAT) come from
            # energy_prices.csv, which names each one's source; ambient_heat/
            # ground_heat are free and uncapped (their collector cost is in
            # the heat pump investment).
            "supply_grid_electricity": {
                "base_tech": "supply",
                "name": "Grid electricity import",
                "carrier_out": "electricity",
                "flow_cap_max": 1e6,
                "cost_flow_out": {
                    "data": prices["supply_grid_electricity"],
                    "index": "monetary",
                    "dims": "costs",
                },
                "comment": "EUR/kWh; Eurostat nrg_pc_204, NL household band DC, excl. taxes and levies, 2025 mean (energy_prices.csv).",
            },
            "supply_biomass": {
                "base_tech": "supply",
                "name": "Biomass (wood pellet) fuel supply",
                "carrier_out": "biomass",
                "flow_cap_max": 1e6,
                "cost_flow_out": {
                    "data": prices["supply_biomass"],
                    "index": "monetary",
                    "dims": "costs",
                },
                "comment": "EUR/kWh; DEA SOEB25 consumer-level wood pellet factor price 2025, DKK->EUR (energy_prices.csv).",
            },
            "supply_ambient_heat": {
                "base_tech": "supply",
                "name": "Free ambient (outdoor-air) heat source",
                "carrier_out": "ambient_heat",
                "flow_cap_max": 1e6,
                "cost_flow_out": {
                    "data": prices["supply_ambient_heat"],
                    "index": "monetary",
                    "dims": "costs",
                },
            },
            "supply_ground_heat": {
                "base_tech": "supply",
                "name": "Free ground heat source",
                "carrier_out": "ground_heat",
                "flow_cap_max": 1e6,
                "cost_flow_out": {
                    "data": prices["supply_ground_heat"],
                    "index": "monetary",
                    "dims": "costs",
                },
            },
        }
    }
    _write_yaml(out_dir / "demand_techs.yaml", demand_techs)

    _SUPPLY_TECH_IDS = [
        "supply_grid_electricity",
        "supply_biomass",
        "supply_ambient_heat",
        "supply_ground_heat",
    ]

    household_heat_cap_total = _household_heat_cap_total()
    # Empirical finding: 4 of the 1,260 nodes sit just *under* the nameplate
    # household cap (~50 kW vs. a 52 kW cap) yet were still proven
    # infeasible on a real solve -- ratio-math/efficiency losses eat into
    # the nameplate ceiling before it is ever reached. A 10% safety margin
    # (tested against all 18 originally-infeasible nodes) catches those
    # too; see outputs/retry_failed_results.json.
    peak_heat_by_node = heat_wide.max()
    oversized_nodes = set(
        peak_heat_by_node[peak_heat_by_node > 0.9 * household_heat_cap_total].index
    )
    if oversized_nodes:
        print(
            f"{len(oversized_nodes)} node(s) exceed the household-scale combined "
            f"heat capacity ({household_heat_cap_total} kW) at their own peak "
            "demand -- adding building-scale techs for those nodes too: "
            f"{sorted(oversized_nodes)}"
        )

    # Same oversizing-margin pattern as heat, applied to cooling: a node
    # whose own peak cooling demand exceeds the combined household-scale
    # chiller capacity (10% margin, same reasoning as heat's margin above --
    # ratio-math/efficiency losses eat into the nameplate ceiling) also gets
    # the building-scale chiller options, in addition to (not instead of)
    # the household ones.
    household_cool_cap_total = _household_cool_cap_total()
    peak_cool_by_node = cool_wide.max()
    oversized_cool_nodes = set(
        peak_cool_by_node[peak_cool_by_node > 0.9 * household_cool_cap_total].index
    )
    if oversized_cool_nodes:
        print(
            f"{len(oversized_cool_nodes)} node(s) exceed the household-scale "
            f"combined chiller capacity ({household_cool_cap_total} kW) at "
            "their own peak cooling demand -- adding building-scale chiller "
            f"techs for those nodes too: {len(oversized_cool_nodes)} node(s)"
        )

    nodes = {
        "nodes": {
            node: {
                "techs": {
                    "demand_heat": {},
                    "demand_elec": {},
                    "demand_cool": {},
                    **{tech_id: {} for tech_id in _HOUSEHOLD_TECH_IDS},
                    **(
                        {tech_id: {} for tech_id in _BUILDING_TECH_IDS}
                        if node in oversized_nodes
                        else {}
                    ),
                    **{tech_id: {} for tech_id in _HOUSEHOLD_CHILLER_TECH_IDS},
                    **(
                        {tech_id: {} for tech_id in _BUILDING_CHILLER_TECH_IDS}
                        if node in oversized_cool_nodes
                        else {}
                    ),
                    **{tech_id: {} for tech_id in _SUPPLY_TECH_IDS},
                }
            }
            for node in node_names
        }
    }
    _write_yaml(out_dir / "nodes.yaml", nodes)

    # Real Calliope 0.7.0 data_tables schema (confirmed against calliope's
    # own bundled example_models/urban_scale/model.yaml, not guessed): the
    # file-path key is `table`, and add_dims' parameter-name key is
    # `inputs`, not `data`/`parameters`.
    # `table:` resolves relative to the top-level model.yaml's own
    # directory (confirmed by a real FileNotFoundError, not assumed) --
    # not relative to this data_tables.yaml file's own directory (nodes/),
    # even though model.yaml imports it from there.
    data_tables = {
        "data_tables": {
            "loenen_demand_heat": {
                "table": f"{out_dir.name}/{heat_csv.name}",
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": "demand_heat", "inputs": "sink_use_equals"},
            },
            "loenen_demand_elec": {
                "table": f"{out_dir.name}/{elec_csv.name}",
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": "demand_elec", "inputs": "sink_use_equals"},
            },
            "loenen_demand_cool": {
                "table": f"{out_dir.name}/{cool_csv.name}",
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": "demand_cool", "inputs": "sink_use_equals"},
            },
        }
    }
    _write_yaml(out_dir / "data_tables.yaml", data_tables)

    print(f"Wrote {len(node_names)} nodes to {out_dir}")
    print(
        f"Heat demand CSV: {heat_csv} ({heat_wide.shape[0]} timesteps x {heat_wide.shape[1]} nodes)"
    )
    print(
        f"Elec demand CSV: {elec_csv} ({elec_wide.shape[0]} timesteps x {elec_wide.shape[1]} nodes)"
    )
    print(
        f"Cool demand CSV: {cool_csv} ({cool_wide.shape[0]} timesteps x {cool_wide.shape[1]} nodes)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hourly-parquet", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.hourly_parquet, args.out_dir)


if __name__ == "__main__":
    main()
