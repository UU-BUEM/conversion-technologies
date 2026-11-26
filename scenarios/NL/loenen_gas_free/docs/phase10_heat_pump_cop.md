# Phase 10: hourly heat pump COP vs a fixed COP (method)

Status 2026-11-26: implemented; region (1,260 dwellings) and pilot (20
members) solved for the full year in three COP variants. Results are kept
out of the repository until published (local `docs/private/`, git-ignored).

## Question

How much does the choice of heat pump COP model change a cost-optimal
heating mix, when everything else (demand, prices, technologies) stays the
same: a fixed COP every hour, or one that follows the outdoor temperature?

## Three variants

| Variant | Air-source COP | `build_nodes.py --cop` |
| --- | --- | --- |
| `design` | constant: the design-point COP every hour (3.30 household, 2.99 building) | `design` |
| `hourly_matched` | hourly Carnot COP, quality factor recalibrated so the heat-weighted seasonal COP equals the design COP | `hourly_matched` (default) |
| `hourly` | hourly Carnot COP with the design-point quality factor | `hourly` |

- **Fixed COP.** `COP = eta * T_sink / (T_sink - T_source)` at the design
  point (source 2 degC, sink 45 degC), with `eta` in `technologies.csv`
  chosen so the COP equals the Danish Energy Agency's annual average.
- **Hourly COP.** The same formula at each hour's 2 m air temperature
  (UU-BUEM `weather`, MERRA-2 2018, 52.12 N 6.03 E, the cell of the demand
  and PV runs), through the package's `weather-cop` CLI
  (`scripts/build_hp_cop.py`). The sink stays at 45 degC.
- **Why the matched variant.** The catalog COP is an annual average.
  Evaluating the design-point `eta` hour by hour gives a different
  (in a mild climate, higher) heat-weighted seasonal COP, so comparing it
  with the fixed COP would mix two effects: the hourly shape and a change in
  level. `weather-cop --match-seasonal-cop HEAT_CSV` scales the series by one
  factor so the seasonal COP, `sum(Q) / sum(Q / COP)` weighted by the 1,260
  dwellings' summed hourly heat demand, equals the design COP. COP is
  proportional to `eta`, so this is a recalibrated `eta`; the shape is
  unchanged. `design` vs `hourly_matched` isolates the effect of timing,
  `hourly_matched` vs `hourly` the effect of the level. The factor is in
  `heat_pump_cop_2018_matched/summary.json`.
- **Ground-source heat pumps** keep their fixed COP in every variant: the
  weather module has no ground temperature, and the ground stays near its
  10 degC design temperature.

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
Checked on the loaded model: hourly values with the override, a flat
design COP without.

## Limitations

- Fixed 45 degC sink temperature in every hour (no weather-compensated flow
  temperature, no defrost penalty below about 5 degC); both would lower the
  COP in cold hours and are not modeled.
- Heat pump capacity is not derated at low temperature.
- One weather cell for the whole village; one weather year (2018).
- Ground-source COP stays fixed (no ground temperature data).
- Pellets are unconstrained and inexpensive, so pellet boilers keep most
  of the heat in every variant.

## Reproduce

Scenario root; `scenario_env` (Library/bin on PATH), a Gurobi licence for
`--solver gurobi` (or `cbc`, much slower).

```bash
python scripts/build_hp_cop.py                     # heat_pump_cop_2018/         (hourly)
python scripts/build_hp_cop.py --match-seasonal    # heat_pump_cop_2018_matched/ (hourly_matched)
python scripts/build_nodes.py --hourly-parquet data/loenen_single_dwelling_hourly_cool26_ev20.parquet \
    --out-dir nodes_day_ahead --cop hourly_matched            # default; or --cop hourly / design
python scripts/build_nodes.py ... --out-dir nodes_day_ahead_design --cop design
python scripts/solve_all_buildings.py --workers 16 --solver gurobi --ev smart \
    --nodes-dir nodes_day_ahead --out outputs/v5/<variant>/all_buildings_results.json \
    --per-building-dir outputs/v5/<variant>/per_building
python scripts/compare_cop_variants.py design=outputs/v5/day_ahead_ev_smart_design_cop \
    hourly_matched=outputs/v5/day_ahead_ev_smart_matched_cop \
    hourly=outputs/v5/day_ahead_ev_smart_hourly_cop --out docs/private/cop_comparison_v5.csv
```

About 70 minutes per region variant (16 workers, one Gurobi thread each).
Pilot: `build_community.py --solver gurobi` (it builds with the default
`--cop`) and `solve_independent.py --solver gurobi`.
