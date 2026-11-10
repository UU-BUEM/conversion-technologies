# Scenario: Loenen gas-free neighborhood

**Status: full pipeline runs end to end** (demand -> nodes -> per-building
solves -> summary). Current results: `outputs/v3/` (sourced prices,
26 degC cooling setpoint, fixed conversion balance); everything earlier is
superseded -- see `docs/phase5_per_building_decomposition.md`'s note.
This folder exists so the scenario has a home while it's small; split into its
own repo once it outgrows living alongside `conversion-technologies`' own
package code (tracked as an open decision, not yet taken).

## What this scenario is

A per-building (not clustered — see "Resolution" below) Calliope model of
Loenen (1,260 single-dwelling buildings for this first pass — see
"Resolution" below) in which every technology that burns
`natural_gas` is excluded, so the optimizer must meet 100% of heat demand
from non-gas conversion technologies this repo's registry already defines
(`heat_pump_electric_*`, `heat_pump_geothermal_*`, `boiler_biomass_*`,
`boiler_electric_*`, `combined_heat_and_power_biomass_*`) plus whatever
exogenous supply (grid electricity, PV, district heat) the node definitions
add. See `constraints.md` for the exact constraint set.

## Where each input comes from (cross-repo)

| Input | Source | Status |
| --- | --- | --- |
| Building geometry, TABULA archetype | `buem`'s `src/buem/data/buildings/netherlands/Loenen/` | Already checked in |
| Per-building hourly heat demand | `buem`'s `scripts/run_region_hourly.py`, via `scripts/run_demand_with_cooling_setpoint.py` (cooling setpoint 26 degC instead of buem's 21 degC default; `constraints.md` 10) | `data/loenen_single_dwelling_hourly_cool26.parquet` (1,260 buildings x 8,760 h). Cooling demand is still high (median 10.5 MWh/yr, peak 16 kW per dwelling) -- buem likely lacks summer ventilative cooling; treat cooling results as indicative |
| Energy prices | `energy_prices.csv` (Eurostat electricity excl. taxes; Danish Energy Agency pellet factor price) | Sourced, system perspective (`constraints.md` 8) |
| Per-household electricity/occupancy profile | `occupancy` (via `buem`'s `AttributeBuilder`, or called standalone) | `buem` already depends on it; standalone per-building export not yet scripted |
| Weather (Loenen point) | `weather`, provider `merra-2` (default) or `era5-land` (needs the documented Jan-2018 boundary patch — see `buem`'s CLAUDE.md "Independent validation folder") | Available |
| Conversion technology YAML + carrier-ratio math | *this repo*, `calliope_export.modern`/`ratio_math`, scoped to the non-gas `technology_ids` this scenario selects | This repo already does this; scenario-level filtering is new (see below) |
| Per-node technology placement + demand wiring + Calliope `nodes:`/`locations:` | **New — this scenario's own job.** `modern.py` deliberately emits only `techs:` bodies, no `nodes:` concept (see `docs/calliope_schema_mapping.md` "occupancy is out of scope" / weather-cop's `nodes` note) | Done for 1,260 nodes — `scripts/build_nodes.py`, see `docs/phase3_nodes.md` |
| Model execution (solve) | `scenario_env` conda env (`infrastructure/env/scenario_env.yml`: Python 3.12, `calliope==0.7.0`, CBC) (`enerplanet/MEME` deferred -- it expects its own canonical JSON, not raw Calliope YAML) | Combined 1,260-node model hits a memory wall at `build()` (see `docs/phase4_solve.md`/`phase4b_solve_0610_sizing.md`). Solved instead per-building (`scripts/solve_all_buildings.py`, see `docs/phase5_per_building_decomposition.md`): both variants (`--no-cooling` = heating only) solved for all 1,260 buildings; `scripts/summarize_results.py` writes each variant's `summary.csv` (energy, shares, capacities, costs per technology) |

## Resolution: per-building nodes, not archetype clusters

Each Loenen building is its own Calliope node, each with its own
heat/DHW/electricity-demand timeseries and its own technology choice. This
was an explicit choice over archetype clustering, made because the
scenario needs to let the optimizer (or a later equity/robustness
analysis) decide *which specific households* get which replacement
technology, not just a cluster-level mix. If per-building resolution turns
out to be computationally intractable at full-year hourly resolution,
re-cluster then — not preemptively.

**Scoped to single-dwelling buildings for the first pass (2026-10-23)**:
real counts from `buem`'s building source put Loenen at 1,335 residential
buildings, 1,260 single-dwelling and 75 multi-unit (2-19 dwellings each).
Phase 1 onward uses just the 1,260 single-dwelling population — the
original "~1,600 households" estimate conflated building and dwelling
counts; see `docs/phase1_demand.md` "Resolution 2." The 75 multi-unit
buildings are deferred, not dropped, pending a decision on whether a node
is one building (lumped demand) or one dwelling (needs per-unit
disaggregation).

## Layout

```text
scenarios/NL/loenen_gas_free/
├── README.md              # this file
├── constraints.md         # gas-free constraint set (hard/soft, how each is enforced)
├── data/                  # per-building buem/occupancy/weather inputs (gitignored)
├── technologies/          # ExportConfig + generated techs.yaml / additional_math.yaml
├── nodes/                 # node, demand-tech, data_tables YAML + demand CSVs
│                          #   (generated by scripts/build_nodes.py; CSVs gitignored)
├── scripts/
│   ├── build_nodes.py           # scenario-only glue, not part of the package
│   ├── solve_full.py            # Phase 4: full-model attempt (docs/phase4_solve.md)
│   ├── solve_single_building.py # Phase 5: solve ONE node (docs/phase5_*.md)
│   └── solve_all_buildings.py   # Phase 5: parallel driver, sums to a region total
├── model.yaml             # top-level Calliope model: technologies/ + nodes/
└── outputs/               # solve results (gitignored)
```

See `docs/phase4_solve.md` / `docs/phase4b_solve_0610_sizing.md` for the
full-model build/memory-scaling investigation, and
`docs/phase5_per_building_decomposition.md` for why/how this scenario is
solved per-building instead.

## Superseded results (`outputs/v2_sourced/`, 2026-11-10 -- capacity bug)

> Invalid: the exporter then applied capacity ceilings and capacity costs to
> input carriers too (repo `CHANGELOG.md` [Unreleased]). Kept for the record;
> current results are in `outputs/v3/` (section below once complete).

Sourced prices (system perspective, `constraints.md` 8), 26 degC cooling
setpoint, fixed conversion balance. All 1,260 buildings solved in both
variants (8 CBC contention timeouts re-solved with `scripts/retry_failed.py`);
per-building heat, cooling, electricity and pellet balances close to
<1e-8 relative. Per-technology tables: `outputs/v2_sourced/*/summary.csv`.

| | Heating only | Heating + cooling |
| --- | --- | --- |
| Annual system cost (incl. appliance electricity) | EUR 8.23 M (median EUR 4,663 per dwelling) | EUR 10.32 M (median EUR 6,783) |
| Heat 47.8 GWh: pellet boiler / air HP / ground HP / electric boiler | 83 % / 9.7 % / 3.0 % / 4.0 % | unchanged |
| Cooling 15.6 GWh: reversible HP / compression chiller | -- | 72 % / 28 % |
| Grid electricity | 7.92 GWh | 11.17 GWh (+41 %) |
| Pellets | 47.4 GWh | unchanged |

Reading: at system prices excluding taxes, pellet heat (~EUR 0.076/kWh) is
no dearer than air-source heat pump heat (~EUR 0.079/kWh) at about a third of
the investment per kW, so heat pumps (358 dwellings) only add capacity where
the household pellet boiler hits its per-node ceiling (`flow_cap_max` binds on
the boiler's *input* carrier: 15 kW pellets = 12.6 kW heat). The result
therefore rests on two assumptions worth testing next: unconstrained biomass
supply (`constraints.md` 7) and the per-node scale ceilings. Cooling demand
(median 10.5 MWh/yr, 16 kW peak per dwelling, even at 26 degC) still looks
high for Dutch dwellings -- likely missing summer ventilative cooling in buem.

`--no-biomass` (on `solve_single_building.py`/`solve_all_buildings.py`/
`retry_failed.py`) solves an all-electric gas-free variant without any
biomass technology or pellet supply, to test the unconstrained-biomass
assumption (results: "Current results" below).

## Current results (`outputs/v3/`, 2026-11-10)

Sourced prices (system perspective), 26 degC cooling setpoint, fixed
conversion balance, capacity limits and capacity costs on each technology's
output carrier only. All 1,260 buildings solved in all three variants
(CBC contention timeouts re-solved with `scripts/retry_failed.py`); per-
building heat, cooling, electricity and pellet balances close to <3e-8
relative. Per-technology tables: `outputs/v3/*/summary.csv`.

| | Heating, biomass allowed | Heating, all-electric | Heating + cooling |
| --- | --- | --- | --- |
| Annual system cost (incl. appliance electricity) | EUR 6.43 M (median EUR 3,801/dwelling) | EUR 7.53 M (+17 %; median +EUR 837) | EUR 8.29 M (+29 %) |
| Heat 47.8 GWh | pellet boiler 82 %, ground HP 12.4 %, air HP 3.5 %, electric boiler 2.1 % | ground HP 63 %, air HP 34 %, electric boiler 3 % | as biomass allowed |
| Cooling 15.6 GWh | -- | -- | reversible HP 73 %, compression chiller 27 % |
| Grid electricity | 7.36 GWh | 19.17 GWh (x2.6) | 10.63 GWh |

Reading: with biomass allowed, heat pumps (363 dwellings) are installed only
where the household pellet boiler is at its 15 kW (heat) ceiling -- median
heat demand 71 MWh/yr vs. 18 MWh/yr elsewhere -- so the mix rests on
unconstrained biomass supply and on the per-node ceilings. The all-electric
variant prices that assumption: +17 % annual cost.

All-electric variant and the building-scale fallback: without the pellet
boiler the household-scale heat ceiling drops from 75 to 60 kW, so
`solve_single_building.py --no-biomass` re-applies `build_nodes.py`'s
fallback rule (building-scale techs when peak heat > 90 % of the household
ceiling) to what remains -- 10 dwellings with 54-64 kW peaks.
