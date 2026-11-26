# Electric vehicles across the modules: architecture

How the EV is split over four packages, what passes between them, and
where each constraint is set. The method of the behaviour model is in
occupancy's `docs/ev/design.md`. The Calliope mapping of the technologies
is in [`calliope_schema_mapping.md`](calliope_schema_mapping.md),
"Electric vehicles".

## 1. Who owns what

| Module | Owns | Does not own |
| --- | --- | --- |
| **occupancy** | EV *behaviour*: ownership (`has_ev`), trips, presence coupling, state of charge (SOC) over time, plug-in decision, uncontrolled home charging, away charging. Outputs hourly series. | Costs, sizing, optimised charging, battery degradation |
| **buem** | Carries the EV series through, per building, next to the thermal results. Keeps EV charging **out** of the internal heat gains (`elecLoad`). Exports the hourly parquet. | EV logic of its own |
| **conversion-technologies** (this repo) | EV *technologies* as Calliope techs: chargers, V2G discharger, traction battery, with efficiencies, capacities, lifetimes and costs. The availability constraint (custom math). | Behaviour, time series |
| **Scenario** (`scenarios/NL/loenen_gas_free`) | Wiring: which building gets which EV techs, the data tables, prices, the charging variant, solving. | Parameters of either package |
| **Calliope 0.7.0** | The optimisation: when to charge (smart), whether to buy V2G, at least cost | — |

No package imports another across this chain: occupancy is called by
buem; everything after buem passes through files.

## 2. Data flow

```text
occupancy (Python API, called inside buem)
  ElectricityConsumptionProfile(has_ev, ev_config)
    -> ev_charging_kw, ev_plugged_in, ev_drive_kwh, ev_away_charging_kwh, ev_soc, ...
    -> total_power_kwh  (appliances only: EV excluded)
        |
        v
buem  scripts/run_region_hourly.py   (scenario: scripts/run_demand_with_cooling_setpoint.py)
  per building: Q_heat_kW, Q_cool_kW, dhw_kW, elec_kW (= elecLoad, no EV),
                ev_kW, ev_plugged_in, ev_drive_kW, ev_away_kW
    -> data/loenen_single_dwelling_hourly_cool26_ev20.parquet
        |
        v
scenario  scripts/build_nodes.py  (--grid-price day_ahead|flat)
  + technologies/export/   <- conversion-technologies CLI (technologies/export_config.json):
                              tech YAML + additional_math.yaml (carrier ratios, EV availability)
  -> nodes[_day_ahead]/nodes.yaml          EV techs only at the 264 EV nodes
  -> nodes[_day_ahead]/data_tables.yaml + CSVs:
       ev_plugged_in.csv   -> ev_charger_ac_household.flow_out_max_relative
       ev_drive.csv        -> demand_ev_driving.sink_use_equals
       ev_away.csv (x 0.93)-> supply_ev_away.source_use_equals
       ev_uncontrolled.csv -> demand_ev_uncontrolled.sink_use_equals (baseline variant)
        |
        v
scenario  scripts/solve_all_buildings.py --ev {smart|uncontrolled|v2g|none} --nodes-dir ...
  one Calliope 0.7.0 model per building (exact: the EV battery is node-local), CBC
  -> outputs/v4/<variant>/all_buildings_results.json
  -> scripts/summarize_results.py, scripts/compare_ev_variants.py
```

Column names along the chain:

| occupancy | buem parquet | Calliope (scenario) |
| --- | --- | --- |
| `ev_charging_kw` (grid side) | `ev_kW` | `demand_ev_uncontrolled` (uncontrolled variant); peak sets the wallbox size |
| `ev_plugged_in` (fraction of hour) | `ev_plugged_in` | `flow_out_max_relative` of charger and V2G |
| `ev_drive_kwh` (battery side) | `ev_drive_kW` | `demand_ev_driving` |
| `ev_away_charging_kwh` (grid side) | `ev_away_kW` | `supply_ev_away` (x DC efficiency 0.93 to battery side) |
| `total_power_kwh` | `elec_kW` | appliance electricity demand |
| `ev_stored_kwh` (battery energy, end of hour) | `ev_stored_kWh` | battery `storage_initial` (level before the first hour) and `storage_final_min` (last hour) |
| `ev_soc`, `ev_at_home` | not exported | not used: Calliope computes its own SOC in between |

## 3. The energy system per EV household (smart variant)

```text
grid (electricity) --[ev_charger_ac_household: 0.92, cap fixed, x ev_plugged_in(t)]--> ev_electricity
                                                                                         |
supply_ev_away (fixed, from occupancy) --------------------------------------------------+
                                                                                         |
       ev_battery_household (60 kWh, 10% reserve, starts and ends at the simulated car's levels)
                                                                                         |
                                                   demand_ev_driving (fixed, from occupancy)
v2g variant only:  ev_electricity --[ev_v2g_household: 0.90, x ev_plugged_in(t)]--> electricity
```

The optimiser decides only *when* the charger runs (and, with V2G, when
the battery feeds the house). The driving energy, the away charging and
the hours the car is connected are fixed inputs from occupancy.

## 4. Is there EV optimisation in Calliope?

Yes, in two of the four variants:

| `--ev` | What Calliope optimises | Result, 2018 NL day-ahead price, 264 EVs |
| --- | --- | --- |
| `uncontrolled` | nothing: occupancy's charging profile is a fixed demand | baseline |
| `smart` | charging timing within the connected hours | EUR 11,392/yr cheaper in total (median EUR 43.20 per EV), same energy within 2.9 kWh |
| `v2g` | smart + whether to buy a bidirectional charger and when to discharge | spot checks only: V2G never bought at 2018 prices |
| `none` | no EV at all | reference |

The battery and the household wallbox are not sized: the car and its
charger already exist (wallbox `flow_cap_min = flow_cap_max`, cost 0).
Sizing is possible by freeing those bounds, but then the optimiser picks
the smallest charger that still delivers the energy.

## 5. Where each technical constraint is set

The SOC exists twice: occupancy simulates it to produce the uncontrolled
behaviour; Calliope re-optimises it in the smart and V2G variants. The two
must describe the same car, so shared values are kept equal by hand.

| Constraint | occupancy (`households/data/ev.json`) | Calliope (this repo / scenario) | Shared? |
| --- | --- | --- | --- |
| Battery capacity | `vehicle.battery_capacity_kwh` 60 | `ev_battery_household` `storage_cap_min/max` 60 (`new/technologies.csv`) | yes, keep equal |
| Minimum SOC (reserve) | `battery.soc_min` 0.1 | `storage_discharge_depth` 0.1 (`new/technologies.csv`) | yes, keep equal |
| Home charging target | `battery.soc_target_home` 0.9 | none: the optimiser fills only what is needed, up to 100% | no |
| SOC at departure | implicit: trip energy drawn from the battery | implicit: `demand_ev_driving` must be met from the battery | same idea |
| Charger power | `charging_modes.slow.power_kw` 7.4, capped by `vehicle.max_ac_power_kw` 11 | node `flow_cap_min = flow_cap_max` = peak `ev_kW` x 0.92 (`build_nodes.py`); catalogue max 11 kW | yes, derived from occupancy |
| Charging efficiency | `charging_modes.slow.efficiency` 0.92 | charger `flow_out_eff` 0.92 | yes, keep equal |
| Away (DC) efficiency | `charging_modes.fast.efficiency` 0.93 | `ev_charger_dc_community` 0.93, applied to `ev_away.csv` | yes, keep equal |
| Charge taper near full | `taper_start_soc`, `taper_end_fraction` | none (linear model) | no |
| Plugged-in hours | simulated (`plug_in.*`, trips) | `flow_out_max_relative` = `ev_plugged_in` (custom math, `calliope_export/availability_math.py`) | input |
| Start and end of year | warm-up period (`simulation.warmup_days`); the year's simulated levels are exported as `ev_stored_kWh` | `cyclic_storage: false`; `storage_initial` = simulated level on 1 January; `storage_final_min` = simulated level on 31 December, as a lower bound (`build_nodes.py`, constraint `storage_final_level_min` in `calliope_export/storage_math.py`) | yes, from occupancy |
| Battery losses | none at rest | battery efficiency 1.0; losses sit on the chargers | same |
| V2G discharge | not modelled | `ev_v2g_household` 0.90, availability-bound, 350 EUR/kW + 0.046 EUR/kWh wear (`new/costs.csv`) | Calliope only |

**Start and end of year.** The battery starts at the simulated car's
level and must end at least at its simulated level. occupancy's own year
is then always a feasible solution, and the smart variant describes
exactly the same car as the uncontrolled one: same start, same end, same
driving. The final-level bound is a general custom constraint for every
storage technology (`storage_final_min`, a fraction of `storage_cap`;
default 0 = not set).

**Do not set `storage_initial` together with `cyclic_storage: true`.**
Calliope then forces the battery to that level in the year's last hour as
well, which is infeasible when the car is away or nearly empty on 31
December. It made 48 of 264 EV households infeasible in the first full
run. Without `ev_stored_kWh` in the Phase 1 data, `build_nodes.py` falls
back to a cyclic battery with a free starting level.

## 6. Changing a parameter

| To change | Edit | Then |
| --- | --- | --- |
| Behaviour (trips, plug-in, km, ownership) | occupancy `ev_config` overrides (JSON), or `ev.json` | rerun Phase 1, `build_nodes.py`, solves |
| Battery size, reserve or charger efficiency | **both** occupancy `ev_config` and `new/technologies.csv` | re-export technologies; rerun Phase 1, `build_nodes.py`, solves |
| Wallbox power | occupancy `charging_modes.slow.power_kw` | rerun Phase 1 (`build_nodes.py` reads the new peak) |
| Costs | `new/costs.csv` (+ `docs/sources/`) | re-export technologies; re-solve |
| Grid price | `scripts/build_grid_price.py` / `energy_prices.csv` | `build_nodes.py --grid-price ...`; re-solve |
| Charging variant | `--ev` on the solve scripts | re-solve only |

A survey-based Loenen parameter set goes in one occupancy override file.
If it changes the battery, the reserve or the efficiencies, the same
values go into `new/technologies.csv`.

## 7. Not covered yet

- Service-building and workplace charging (shared charge points,
  `ev_charger_ac_building`); the technologies exist, the behaviour model
  does not.
- More than one car per household; multi-day trips.
- Battery degradation from smart charging or DC fast charging (only V2G
  discharge carries a wear cost).
- Distribution-grid limits (transformer, feeder): needs a network model
  and a combined multi-building solve instead of one model per building.
