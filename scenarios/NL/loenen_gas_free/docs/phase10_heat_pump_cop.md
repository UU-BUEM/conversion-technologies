# Phase 10: hourly heat pump COP vs a fixed COP

Status 2026-11-26: done. Region (1,260 dwellings) and pilot (20 members)
solved for the full year with three COP variants.

## Question

How much does the choice of heat pump COP model change a cost-optimal
heating mix, when everything else (demand, prices, technologies) stays the
same: a fixed COP every hour, or one that follows the outdoor temperature?

## Three variants

| Variant | Air-source COP | Seasonal COP (heat-weighted) | `build_nodes.py --cop` |
| --- | --- | --- | --- |
| `design` | 3.30 every hour (household; 2.99 building) | 3.30 | `design` |
| `hourly_matched` | Carnot COP at the hourly outdoor temperature, quality factor recalibrated | **3.30**, same as `design` | `hourly_matched` (default) |
| `hourly` | Carnot COP at the hourly outdoor temperature, design-point quality factor | 3.51 | `hourly` |

- **Fixed COP.** `COP = eta * T_sink / (T_sink - T_source)` at the design
  point (source 2 degC, sink 45 degC), with `eta` (0.446 household) chosen in
  `technologies.csv` so the COP equals the Danish Energy Agency's annual
  average (3.30).
- **Hourly COP.** The same formula at each hour's 2 m air temperature
  (UU-BUEM `weather`, MERRA-2 2018, 52.12 N 6.03 E, the cell of the demand
  and PV runs), through the package's `weather-cop` CLI
  (`scripts/build_hp_cop.py`). The sink stays at 45 degC.
- **Why the matched variant.** With the design-point `eta`, the hourly COP's
  heat-weighted seasonal value is 3.51 for Loenen's 2018 weather, 6 % above
  the fixed 3.30 (its unweighted hourly mean, 4.4, counts summer hours with
  little heat demand). Comparing that series with the fixed COP mixes two
  effects: the hourly shape and a higher level. `weather-cop
  --match-seasonal-cop HEAT_CSV` scales the series by one factor (0.940) so
  the seasonal COP, `sum(Q) / sum(Q / COP)` weighted by the 1,260 dwellings'
  summed hourly heat demand, equals the design COP. COP is proportional to
  `eta`, so this is a recalibrated `eta` (0.446 -> 0.419); the shape is
  unchanged. `design` vs `hourly_matched` isolates the effect of timing;
  `hourly_matched` vs `hourly` the effect of the level.
- **Ground-source heat pumps** keep their fixed COP (3.55) in every variant:
  the weather module has no ground temperature, and the ground stays near
  its 10 degC design temperature.

| Air-source, household | min | mean (hourly) | max | seasonal (heat-weighted) |
| --- | --- | --- | --- | --- |
| `hourly` | 2.61 | 4.43 | 12.12 | 3.51 |
| `hourly_matched` | 2.45 | 4.17 | 11.39 | 3.30 |

## How it enters the model

A heat pump's COP enters Calliope through two parameters, both made hourly:
`flow_out_eff` on `heat` (heat per kWh of electricity, in
`balance_conversion_primary_carriers`) and `carrier_flow_ratio_in`
(ambient heat per kWh of electricity, COP - 1, in `link_flow_in_carriers`).
Calliope 0.7.0 gives a YAML value precedence over a data table, and an
`import:` cannot redefine a key, so the tech export's scalar COP would
silently win. `build_nodes.py` therefore writes an `hourly_cop` override
setting both scalars to null (`cop_overrides.yaml`), the model writers
embed it, and the solvers select it (`build_nodes.model_scenario`).
Checked on the loaded model: hourly values with the override, a flat 3.30
without.

## Region results (1,260 dwellings, full year)

New demand (buem window fix, `--window-ach 3`), day-ahead electricity
price, smart EV charging, Gurobi; every building solved in every variant.
Table: `results/cop_comparison_v5.csv` (`scripts/compare_cop_variants.py`).

| | `design` | `hourly_matched` | `hourly` |
| --- | --- | --- | --- |
| System cost, EUR M/yr | 5.846 | 5.832 (-0.24 %) | 5.811 (-0.60 %) |
| Median cost per dwelling, EUR/yr | 3,773 | 3,773 | 3,770 |
| Heat share: pellet boiler | 90.0 % | 88.2 % | 81.9 % |
| Heat share: air-source heat pump | 1.6 % | 8.3 % | 16.6 % |
| Heat share: ground-source heat pump | 6.8 % | 2.1 % | 0.2 % |
| Heat share: electric boiler | 1.6 % | 1.5 % | 1.3 % |
| Dwellings with an air-source heat pump | 98 | 490 | 1,260 |
| Dwellings with a ground-source heat pump | 188 | 51 | 3 |
| Air-source capacity, MW | 0.28 | 0.67 | 1.17 |
| Realized seasonal COP, air-source (heat / electricity) | 3.30 | 3.69 | 3.88 |
| Pellets, GWh | 41.7 | 40.8 | 37.9 |
| Grid electricity, GWh | 6.38 | 6.49 | 7.01 |

Heat demand is 38.9 GWh in every variant.

**Reading.**

- **Timing alone multiplies the air-source share by five** (1.6 % to 8.3 %
  of heat, 98 to 490 dwellings) at an unchanged seasonal COP. Heat pumps
  run in the mild hours and the pellet boiler covers the cold ones, so the
  heat pumps realize a seasonal COP of 3.69 although the hourly series
  averages 3.30 over the heating demand. A fixed COP cannot represent this
  split: every hour is equally good or bad.
- **Air-source displaces ground-source.** Ground-source keeps a flat 3.55,
  which no longer beats an air-source unit used only in favorable hours.
  The total heat pump share still rises (8.3 % to 10.4 %).
- **The level matters as much again.** Without recalibration (seasonal COP
  3.51 instead of 3.30) the air-source share doubles once more, to 16.6 %,
  and every dwelling installs one. Uncalibrated hourly COPs therefore
  overstate the effect of temperature-dependent COP by about half.
- **Costs barely change** (-0.24 %): the COP model changes which
  technologies are built far more than the total system cost.

## Pilot results (20 members, station MSR5000927, full year)

| | `design` | `hourly_matched` | `hourly` |
| --- | --- | --- | --- |
| Independent: total cost, EUR/yr | 64,532 | 64,321 | 64,144 |
| Independent: air-source heat pumps, kW | 0 | 7.8 | 10.9 |
| Community: total cost, EUR/yr | 60,435 | 60,064 | 59,834 |
| Community: air-source heat pumps, kW | 0 | 11.5 | 14.4 |
| Community: ground-source heat pumps, kW | 6.7 | 0 | 0 |
| Saving from sharing | 6.3 % | 6.6 % | 6.7 % |

The community finding holds in every variant. (Independent `design` was
solved with CBC, all others with Gurobi; all optimal.)

## Limitations

- Fixed 45 degC sink temperature in every hour (no weather-compensated flow
  temperature, no defrost penalty below about 5 degC); both would lower the
  COP in cold hours and are not modeled.
- Heat pump capacity is not derated at low temperature.
- One weather cell for the whole village; one weather year (2018).
- Ground-source COP stays fixed (no ground temperature data).
- Pellets are unconstrained and cheap (0.064 EUR/kWh), so pellet boilers
  keep most of the heat in every variant.

## Reproduce

Scenario root; `scenario_env` (Library/bin on PATH), Gurobi licence for
`--solver gurobi` (or `cbc`, much slower).

```bash
python scripts/build_hp_cop.py                     # heat_pump_cop_2018/        (hourly)
python scripts/build_hp_cop.py --match-seasonal    # heat_pump_cop_2018_matched/ (hourly_matched)
python scripts/build_nodes.py --hourly-parquet data/loenen_single_dwelling_hourly_cool26_ev20.parquet \
    --out-dir nodes_day_ahead --cop hourly_matched            # default; or --cop hourly / design
python scripts/build_nodes.py ... --out-dir nodes_day_ahead_design --cop design
python scripts/solve_all_buildings.py --workers 16 --solver gurobi --ev smart \
    --nodes-dir nodes_day_ahead --out outputs/v5/<variant>/all_buildings_results.json \
    --per-building-dir outputs/v5/<variant>/per_building
python scripts/compare_cop_variants.py design=outputs/v5/day_ahead_ev_smart_design_cop \
    hourly_matched=outputs/v5/day_ahead_ev_smart_matched_cop \
    hourly=outputs/v5/day_ahead_ev_smart_hourly_cop --out results/cop_comparison_v5.csv
```

About 70 minutes per region variant (16 workers, one Gurobi thread each).
Pilot: `data/community/MSR5000927/run_pilot_cop.sh` (the `hourly` variant)
and `outputs/run_v5_matched.sh`.
