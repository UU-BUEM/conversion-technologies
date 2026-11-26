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
# Hourly grid price (scripts/build_grid_price.py): the flat Eurostat price
# plus the 2018 NL day-ahead price's hourly deviation from its mean.
_GRID_PRICE_PATH = SCENARIO_ROOT / "grid_price_nl_2018.csv"
GRID_PRICE_CHOICES = ("day_ahead", "flat")

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

# Electric vehicles (docs/phase6_ev.md). Only nodes whose household owns an
# EV in the Phase 1 data (buem/occupancy, 20% ownership for Loenen) get
# them: the home charger (availability-bound, capacity fixed to the
# household's existing wallbox), the car's battery, the
# driving demand and the away-from-home charging, all on the
# ev_electricity carrier. The V2G discharger and the uncontrolled-charging
# baseline are variants switched on by solve_single_building.py.
_EV_CHARGER = "ev_charger_ac_household"
_EV_BATTERY = "ev_battery_household"
_EV_V2G = "ev_v2g_household"
# Read only for its charging efficiency (what reaches the battery when the
# car charges away from home); never placed at a node.
_EV_AWAY_CHARGER = "ev_charger_dc_community"
_EV_NODE_TECH_IDS = [_EV_CHARGER, _EV_BATTERY, "demand_ev_driving", "supply_ev_away"]
# Columns Phase 1 writes for the EV (buem scripts/run_region_hourly.py).
_EV_COLUMNS = ["ev_kW", "ev_plugged_in", "ev_drive_kW", "ev_away_kW"]
# Battery energy at the end of each hour (occupancy's simulated car), when
# Phase 1 exported it. The model's battery then starts the year at the
# simulated car's level (storage_initial, cyclic_storage false) and must end
# it at least at the simulated level (storage_final_min, custom math in
# conversion-technologies' calliope_export/storage_math.py). The simulated
# year is then itself a feasible solution, and smart and uncontrolled
# charging describe exactly the same car. Without the column the battery is
# cyclic with a free starting level. Never combine cyclic_storage with
# storage_initial: that forces the battery to the starting level in the
# year's last hour too, infeasible for a household whose car is away, or low
# and unplugged, on the evening of 31 December (48 households in the first
# full run).
_EV_STORED_COLUMN = "ev_stored_kWh"
# Slack on the final level, kWh: the hourly series pass through float32 CSV
# values, so the simulated year reproduces its own end level only to about
# 1e-3 kWh.
_EV_FINAL_LEVEL_SLACK_KWH = 0.01

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


def _flow_out_eff(tech_id: str) -> float:
    """A single-output tech's ``flow_out_eff`` from this scenario's export."""
    techs = _yaml.load(_TECHS_EXPORT_PATH.open(encoding="utf-8"))["techs"]
    return float(techs[tech_id]["flow_out_eff"])


def _storage_cap(tech_id: str) -> float:
    """A storage tech's fixed capacity (``storage_cap_max``, kWh)."""
    techs = _yaml.load(_TECHS_EXPORT_PATH.open(encoding="utf-8"))["techs"]
    return float(techs[tech_id]["storage_cap_max"])


def _ev_wide(df: pd.DataFrame, column: str, ev_nodes: list[str]) -> pd.DataFrame:
    wide = df.pivot(index="time", columns="building_feature_id", values=column)
    wide.columns = [f"bldg_{c}" for c in wide.columns]
    wide.index.name = "timesteps"
    return wide[ev_nodes]


def build(hourly_parquet: Path, out_dir: Path, grid_price: str = "day_ahead") -> None:
    if grid_price not in GRID_PRICE_CHOICES:
        raise ValueError(f"grid_price must be one of {GRID_PRICE_CHOICES}")
    import pyarrow.parquet as pq

    available = set(pq.read_schema(hourly_parquet).names)
    has_ev_columns = all(c in available for c in _EV_COLUMNS)
    has_ev_stored = has_ev_columns and _EV_STORED_COLUMN in available
    df = pd.read_parquet(
        hourly_parquet,
        columns=[
            "building_feature_id",
            "time",
            "Q_heat_kW",
            "dhw_kW",
            "elec_kW",
            "Q_cool_kW",
            *(_EV_COLUMNS if has_ev_columns else []),
            *([_EV_STORED_COLUMN] if has_ev_stored else []),
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
                **(
                    {
                        "cost_flow_out": {
                            "data": prices["supply_grid_electricity"],
                            "index": "monetary",
                            "dims": "costs",
                        },
                        "comment": "EUR/kWh; Eurostat nrg_pc_204, NL household band DC, excl. taxes and levies, 2025 mean (energy_prices.csv).",
                    }
                    if grid_price == "flat"
                    else {
                        "comment": (
                            "cost_flow_out is hourly, from the loenen_grid_price data "
                            "table: Eurostat flat price (energy_prices.csv) + the 2018 NL "
                            "day-ahead price's deviation from its mean "
                            "(grid_price_nl_2018.csv, scripts/build_grid_price.py)."
                        ),
                    }
                ),
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
            "demand_ev_driving": {
                "base_tech": "demand",
                "name": "EV driving energy (drawn from the car's battery)",
                "carrier_in": "ev_electricity",
                "comment": (
                    "sink_use_equals = Phase 1's ev_drive_kW (occupancy's "
                    "ev_drive_kwh, battery side). Because it is met from the "
                    "battery, the charge needed before each trip is enforced "
                    "without an explicit departure-SOC constraint."
                ),
            },
            "supply_ev_away": {
                "base_tech": "supply",
                "name": "EV charging away from home (workplace / public)",
                "carrier_out": "ev_electricity",
                "flow_cap_max": 1e6,
                "cost_flow_out": {
                    "data": prices["supply_ev_away"],
                    "index": "monetary",
                    "dims": "costs",
                },
                "comment": (
                    "source_use_equals = Phase 1's ev_away_kW (grid side) x the "
                    "DC charger's efficiency: a fixed amount reaching the "
                    "battery while the car is away (energy_prices.csv note)."
                ),
            },
            "demand_ev_uncontrolled": {
                "base_tech": "demand",
                "name": "EV home charging, uncontrolled (baseline variant)",
                "carrier_in": "electricity",
                "comment": (
                    "sink_use_equals = Phase 1's ev_kW: occupancy's charging on "
                    "plug-in, no flexibility. Used only by solve_single_building.py "
                    "--ev-uncontrolled, in place of the EV charger/battery/"
                    "driving/away techs."
                ),
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

    # Electric vehicles: only nodes whose household owns one in Phase 1.
    ev_nodes: list[str] = []
    ev_tables: dict[str, pd.DataFrame] = {}
    ev_node_techs: dict[str, dict] = {}
    if has_ev_columns:
        drive_by_node = df.groupby("building_feature_id")["ev_drive_kW"].sum()
        ev_nodes = sorted(f"bldg_{b}" for b, v in drive_by_node.items() if v > 0)
        charger_eff = _flow_out_eff(_EV_CHARGER)
        away_eff = _flow_out_eff(_EV_AWAY_CHARGER)
        charging = _ev_wide(df, "ev_kW", ev_nodes)
        ev_tables = {
            "ev_plugged_in": _ev_wide(df, "ev_plugged_in", ev_nodes),
            "ev_drive": _ev_wide(df, "ev_drive_kW", ev_nodes),
            "ev_away": _ev_wide(df, "ev_away_kW", ev_nodes) * away_eff,
            "ev_uncontrolled": charging,
        }
        battery_cap = _storage_cap(_EV_BATTERY)
        if has_ev_stored:
            stored = _ev_wide(df, _EV_STORED_COLUMN, ev_nodes)
            # Level before the first hour = level after it minus that
            # hour's net inflow (home charging and away charging on the
            # battery side, minus driving): the battery balance Calliope
            # uses, which occupancy's simulation closes exactly.
            first_net = (
                charging.iloc[0] * charger_eff
                + ev_tables["ev_away"].iloc[0]
                - ev_tables["ev_drive"].iloc[0]
            )
            start_kwh = stored.iloc[0] - first_net
            end_kwh = stored.iloc[-1] - _EV_FINAL_LEVEL_SLACK_KWH
        for node in ev_nodes:
            # The household's existing wallbox, from its own uncontrolled
            # charging peak (grid side), converted to the car side the
            # export's capacity is measured on: fixed, not optimised.
            car_side_kw = round(float(charging[node].max()) * charger_eff, 4)
            capacity = {
                "data": car_side_kw,
                "index": "ev_electricity",
                "dims": "carriers",
            }
            # The wallbox already exists (the uncontrolled baseline charges
            # through it too), so its investment is sunk: zero it here, or
            # only the smart variant would pay for it and look ~EUR 80/yr
            # dearer than the baseline for the same charger.
            sunk = {
                "data": 0,
                "index": [["monetary", "ev_electricity"]],
                "dims": ["costs", "carriers"],
            }
            ev_node_techs[node] = {
                _EV_CHARGER: {
                    "flow_cap_min": capacity,
                    "flow_cap_max": dict(capacity),
                    "cost_flow_cap": sunk,
                },
                _EV_BATTERY: (
                    {
                        "cyclic_storage": False,
                        "storage_initial": round(
                            float(start_kwh[node]) / battery_cap, 8
                        ),
                        "storage_final_min": round(
                            max(float(end_kwh[node]), 0.0) / battery_cap, 8
                        ),
                    }
                    if has_ev_stored
                    else {"cyclic_storage": True}
                ),
                "demand_ev_driving": {},
                "supply_ev_away": {},
            }
        print(f"{len(ev_nodes)} of {len(node_names)} node(s) have an electric vehicle")
        print(
            "EV battery start/end: "
            + (
                "simulated car's levels (storage_initial, storage_final_min)"
                if has_ev_stored
                else "cyclic, free start (Phase 1 has no ev_stored_kWh)"
            )
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
                    **ev_node_techs.get(node, {}),
                }
            }
            for node in node_names
        }
    }
    _write_yaml(out_dir / "nodes.yaml", nodes)

    ev_csvs: dict[str, Path] = {}
    for name, table in ev_tables.items():
        ev_csvs[name] = out_dir / f"{name}.csv"
        table.to_csv(ev_csvs[name])

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
    if ev_nodes:
        # Every availability-bound tech at a node needs this series: the
        # custom math's default of 1 would otherwise let it run while the
        # car is away. solve_single_building.py adds the same table for
        # the V2G discharger when that variant is on.
        for key, csv_name, tech, param in (
            (
                "loenen_ev_availability",
                "ev_plugged_in",
                _EV_CHARGER,
                "flow_out_max_relative",
            ),
            ("loenen_ev_driving", "ev_drive", "demand_ev_driving", "sink_use_equals"),
            ("loenen_ev_away", "ev_away", "supply_ev_away", "source_use_equals"),
        ):
            data_tables["data_tables"][key] = {
                "table": f"{out_dir.name}/{ev_csvs[csv_name].name}",
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": tech, "inputs": param},
            }
    if grid_price == "day_ahead":
        # One series for every node: no `columns`, so no node dimension.
        price_csv = out_dir / "grid_price.csv"
        pd.read_csv(_GRID_PRICE_PATH, index_col=0)[["cost_flow_out"]].to_csv(price_csv)
        data_tables["data_tables"]["loenen_grid_price"] = {
            "table": f"{out_dir.name}/{price_csv.name}",
            "rows": "timesteps",
            "add_dims": {
                "techs": "supply_grid_electricity",
                "inputs": "cost_flow_out",
                "costs": "monetary",
            },
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
    parser.add_argument(
        "--grid-price",
        choices=GRID_PRICE_CHOICES,
        default="day_ahead",
        help="Hourly NL day-ahead-shaped grid price (default) or the flat price (v3)",
    )
    args = parser.parse_args()
    build(args.hourly_parquet, args.out_dir, grid_price=args.grid_price)


if __name__ == "__main__":
    main()
