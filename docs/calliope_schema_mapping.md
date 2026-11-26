# Calliope schema mapping

This package keeps one version-agnostic internal model
(`conversion_technologies.core.technology.TechnologySpec`) and translates it
to Calliope YAML only at export time
(`conversion_technologies.calliope_export.modern` for the technology body,
`conversion_technologies.calliope_export.ratio_math` for the accompanying
custom math a multi-carrier technology needs -- see "Carrier ratio math"
below -- and `conversion_technologies.new.heat_pump.weather_cop` for a real,
weather-driven COP profile instead of the catalog's fixed design point, see
"Weather-driven COP profiles" below). This document is the reference for
what the exporter does and why, the cost-column reference, the heat pump
efficiency naming decision, units/currency/the Calliope version this
targets, and known limitations.

(An earlier version of this package also shipped a `legacy_v051` exporter
targeting [Calliope v0.5.1](https://calliope.readthedocs.io/en/v0.5.1/user/configuration_reference.html#abstract-base-technologies).
It was removed once it was clear only current Calliope was actually in use
— see `.claude/resolved.md`. The internal model stayed version-agnostic
regardless, so a second exporter is still just one new module away if a
v0.5.1 need ever comes back.)

## Attribute mapping

**Fixed fields** — every technology has these, so they're named explicitly
on `TechnologySpec`:

| Concept | Internal (`TechnologySpec`) | `modern` (current Calliope) |
| --- | --- | --- |
| Tech kind | *(implicit: >1 carrier each side is possible)* | `base_tech: conversion` |
| Input carrier(s) | `carriers_in: dict[carrier, ratio]` | `carrier_in`: single string, or list if >1 |
| Output carrier(s) | `carriers_out: dict[carrier, ratio]` | `carrier_out`: single string, or list if >1 |
| Input efficiency/ratio | *(ratio value in `carriers_in`)* | `flow_in_eff`: scalar if 1 carrier, else `{data, index, dims: carriers}` |
| Output efficiency/ratio | *(ratio value in `carriers_out`)* | `flow_out_eff`: scalar if 1 carrier, else `{data, index, dims: carriers}` |
| Capacity | `flow_cap_max` | `flow_cap_max` |
| Lifetime | `lifetime` | `lifetime` |
| Investment cost | `cost_flow_cap` | `cost_flow_cap: {data, index: monetary, dims: costs}` |
| Provenance note | `notes` | `_comment` |

**Dynamic fields** — every other non-blank `technologies.csv`/`costs.csv`
column not consumed by a category's own formula (see each category's
`_FORMULA_COLUMNS` in its `specific/__init__.py`) lands in
`TechnologySpec.params`, keyed by its exact column name, and `modern.py`
iterates `params` emitting each key **unchanged** -- `key.startswith("cost_")`
gets the `{data, index: monetary, dims: costs}` wrapper, everything else is
written as-is. There is no lookup table to keep in sync; a CSV column *is*
the output key. This is why the columns already use Calliope's own naming
(`cost_flow_cap`, `flow_ramping`, ...) rather than an arbitrary internal
vocabulary — see `CLAUDE.md` "Hard conventions" #7.

## Cost columns (`costs.csv`), confirmed against Calliope's math docs

Fetched directly from `calliope.readthedocs.io/en/latest/math/base/` (not
guessed): every `cost_*` name below is a real, current Calliope parameter.

| Column | Meaning | Units | Calliope reference |
| --- | --- | --- | --- |
| `cost_flow_cap` | Investment cost | currency/kW installed | "investment costs associated with the nominal/rated capacity" |
| `cost_om_annual` | Fixed O&M cost | currency/kW/year | annual fixed O&M per unit installed capacity -- **note**: an earlier version of this column was misnamed `cost_flow_om_annual` (not a real Calliope key); renamed once the real name was confirmed |
| `cost_flow_in` | Variable cost per unit *consumed* (e.g. fuel price) | currency/kWh in | "operating cost per unit of inflow" |
| `cost_flow_out` | Variable cost per unit *produced* (e.g. output-linked maintenance) | currency/kWh out | "operating cost per unit of outflow" |
| `cost_storage_cap` | Investment cost of storage energy capacity (stationary batteries) | currency/kWh of storage | "cost per unit `storage_cap`" (Calliope 0.7.0 `math/base.yaml` parameter schema) |
| `cost_interest_rate` | Discount/interest rate for cost annualisation -- not a currency cost | fraction, e.g. `0.0225` | "interest rate for annuity calculation" |

**Fuel is priced once, on the supply side.** The bundled `costs.csv` leaves
`cost_flow_in` blank for every technology: a fuel or electricity price
belongs on the model's *supply* technology for that carrier (a Calliope model
always needs one), and repeating it on the conversion technology would charge
it twice. `cost_flow_out` carries only output-linked variable O&M where the
source gives one (DEA district-heating chapters). Every bundled value and
its source: [`parameter_sources.md`](parameter_sources.md).

`cost_flow_in` and `cost_flow_out` are kept as two distinct columns rather
than merged into one "variable cost," because Calliope itself treats them
as distinct parameters (input-linked vs. output-linked). Not currently
used: `cost_om_annual_investment_fraction` (fixed cost as a fraction of
investment instead of currency/kW/year) and `cost_depreciation_rate` (an
alternative to interest-rate-based annuity) -- both real Calliope
parameters, add as new columns if a project needs them.

## Capacity is per carrier

Calliope 0.7 creates one `flow_cap` decision variable **per carrier** of a
technology -- inputs included -- and its base math applies capacity
parameters to each of them: `flow_cap_max`/`flow_cap_min` bound every
carrier's `flow_cap`, `cost_investment_flow_cap` is computed `foreach
carriers`, and `cost_operation_fixed` is `sum(cost_om_annual * flow_cap,
over=carriers)`. Written as plain scalars (as this exporter did until
2026-11-10), a pellet boiler's `flow_cap_max: 15` therefore capped its
*pellet input* at 15 kW (so heat at 15 x 0.84 = 12.6 kW), and investment and
fixed O&M were charged on the input capacity as well as the output
capacity -- roughly doubling the capital cost of every conversion
technology.

`modern.py` now indexes `flow_cap_max`, `flow_cap_min`, `cost_flow_cap` and
`cost_om_annual` on the technology's **primary output carrier**, the same
shape Calliope's own `urban_scale` example uses:

```yaml
flow_cap_max: {data: 15.0, index: heat, dims: carriers}
cost_flow_cap: {data: 542.7, index: [[monetary, heat]], dims: [costs, carriers]}
```

Input-carrier capacities are then unbounded and cost-free, so they simply
follow the flows. Every catalogue value is per kW of primary output
(`docs/parameter_sources.md`), so this is the shape that makes the numbers
mean what they say. Regression test:
`tests/test_calliope_export.py::test_capacity_parameters_never_apply_to_input_carriers`.

## Heat pump efficiency

`technologies.csv`'s `efficiency` column is shared between boiler (plain
thermal efficiency on a net/LHV basis, 0.8-1.10 -- condensing units exceed
1.0 on that basis) and heat pump (the Carnot quality/2nd-law
factor, 0-1) -- one column name across the whole table rather than a
heat-pump-only `carnot_efficiency`. For heat pumps this is **not** the COP;
it is the input to `new/heat_pump/generic/cop_calculation.py`'s
`carnot_cop`, which computes the actual/final COP as
`efficiency * T_sink_K / (T_sink_K - T_source_K)`. Both are validated
separately in `new/heat_pump/specific/__init__.py`: `efficiency` itself
against `0 < efficiency <= 1` (a heat pump's quality factor thermodynamically
cannot exceed the Carnot limit), and the *computed* COP against
`1 <= cop <= 20` (a sanity bound on the technology's actual real-world
performance, catching a design-temperature/efficiency combination that
would imply an unrealistic heat pump).

## Carrier ratio math (`calliope_export/ratio_math.py`)

Calliope's current release removed `conversion_plus`, `carrier_tiers`, and
`carrier_ratios` from the base technology schema entirely (see its
[migration guide](https://github.com/calliope-project/calliope/blob/main/docs/migrating.md):
"implement via custom math"). This package expresses a fixed ratio between
carriers on the same side of the conversion (heat pump COP, CHP alpha/beta)
via **per-carrier efficiency** (`flow_in_eff`/`flow_out_eff` with
`dims: carriers`) against the technology's single shared internal flow
variable, in `modern.py`'s tech body.

**That alone is not sufficient — it was checked against Calliope's own base
math, not just assumed.** Calliope's `conversion` base constraint,
`balance_conversion` (`calliope/src/calliope/math/base.yaml`), is:

```text
sum(flow_out_inc_eff, over=carriers) == sum(flow_in_inc_eff, over=carriers)
```

a *sum* across carriers on each side, not a per-carrier equation. Working
through CHP's actual numbers (`carriers_in={gas: 1.0}`,
`carriers_out={electricity: alpha, heat: beta}`) shows why this matters: the
intended physics is `flow_out[electricity] = alpha * flow_in[gas]` and
`flow_out[heat] = beta * flow_in[gas]`. Substituting into the unmodified
balance —

```text
flow_out[electricity]/alpha + flow_out[heat]/beta == flow_in[gas]/eff_gas
flow_in[gas] + flow_in[gas] == flow_in[gas]/eff_gas
```

— demands **twice** the fuel actually consumed. It isn't just that the
ratio is unenforced; the base balance is wrong the moment both output
carriers have a real (non-default) efficiency, which is exactly what
`modern.py` gives them. Heat pump's input side has the same problem: the
"intended" 1 : (COP−1) electricity/ambient-heat split doesn't even satisfy
the unmodified balance equation.

The fix, generated by `ratio_math.build_ratio_math()` for every technology
with more than one carrier on one side (structurally — no per-technology-name
branching): restrict the balance to each side's *primary* carrier only
(`TechnologySpec.primary_carrier_in`/`primary_carrier_out`, already set by
every category builder), and tie each secondary carrier to that primary with
its own equality constraint:

```yaml
# for heat_pump_electric_household (primary_carrier_in=electricity, secondary=ambient_heat)
constraints:
  link_flow_in_carriers:
    where: carrier_flow_ratio_in
    equations:
      - where: "[heat_pump_electric_household] in techs"
        expression: >-
          flow_in[carriers=ambient_heat]
          == flow_in[carriers=electricity] * carrier_flow_ratio_in
  balance_conversion:  # REPLACES the base constraint -> keep it for every other tech
    where: >-
      base_tech==conversion AND NOT include_storage==true
      AND NOT [heat_pump_electric_household] in techs
    equations:
      - expression: >-
          sum(flow_out_inc_eff, over=carriers)
          == sum(flow_in_inc_eff, over=carriers)
  balance_conversion_primary_carriers:
    where: >-
      base_tech==conversion AND NOT include_storage==true
      AND [heat_pump_electric_household] in techs
    equations:
      - where: "[heat_pump_electric_household] in techs"
        expression: >-
          flow_out_inc_eff[carriers=heat]
          == flow_in_inc_eff[carriers=electricity]
```

**A constraint in a math file that has the same name as a base-math
constraint replaces it; it does not narrow it.** Until 2026-11-09 the
generated `balance_conversion` override listed only the multi-carrier
technologies, which silently removed the conversion balance from every
single-carrier conversion technology (all boilers, the electric and
reversible chillers): they could deliver output with zero input. Found on a
real `calliope==0.7.0` solve (a Loenen building whose boilers delivered
34,583 kWh of heat while the grid and pellet supply technologies delivered
none), fixed by keeping the base expression verbatim for every *other*
conversion technology (the `NOT [...] in techs` branch above) and moving the
primary-carrier balance into its own constraint. Regression test:
`tests/test_ratio_math.py::test_balance_override_keeps_the_base_balance_for_every_other_conversion_tech`.
Calliope's own urban-scale example keeps the same default branch.

`carrier_flow_ratio_in`/`carrier_flow_ratio_out` are derived straight from
the existing `carriers_in`/`carriers_out` ratios (`secondary / primary`) — no
new CSV column. This mirrors the pattern Calliope's own team uses in their
official CHP example
(`calliope/src/calliope/example_models/urban_scale/additional_math.yaml`:
`heat_to_power_ratio` + a `link_chp_outputs` equality constraint + a
`balance_conversion` override that keeps the default equation for every other
technology), generalised to work for the
input side too (heat pump) instead of only the output side (CHP).

**Where each tech's actual ratio *value* lives — confirmed against a real
`calliope==0.7.0` install (2026-10-23), not just cross-checked against the
docs like the rest of this section originally was**: `additional_math.yaml`'s
`parameters:` block only ever *declares* `carrier_flow_ratio_in`/`_out`
(`default`/`title`/`description` metadata) — Calliope 0.7.0's real
math-file `Parameters` schema rejects an indexed `data`/`index`/`dims`
block there (`extra_forbidden`). The actual per-tech scalar value is set
directly on that tech's own body in the *model definition* instead
(`ratio_math.carrier_flow_ratios(tech)`, called from `modern.export()` and
merged into the tech body — e.g. `heat_pump_electric_household:
{..., carrier_flow_ratio_in: 2.33, ...}`), where Calliope does accept an
arbitrary extra scalar tech attribute. The `where:` clauses above also use
Calliope's real tech-matching syntax, `"[tech_id] in techs"` — an earlier
version of this section (and of `ratio_math.py` itself) used `techs=tech_id`,
which fails real math-string parsing. Both caught and fixed by validating
a real `export-all` output end-to-end (model load + `m.build()`) against
an installed Calliope, not by further reading Calliope's own docs — see
`scenarios/NL/loenen_gas_free/docs/phase4_solve.md` for the full trace of
each failure and fix.

`export`/`export-all` write this alongside the techs YAML automatically as
`additional_math.yaml` (or `<stem>.additional_math.yaml` next to a combined/
single file) — pass `--no-custom-math` to skip it. **Boiler needs none of
this** (one carrier per side, so its balance is already just that carrier)
and `ratio_math.build_ratio_math()` returns `None` for an all-boiler export.

This still covers only fixed-ratio multi-carrier sides, not genuinely
alternative/either-or carriers (what v0.5.1 called `carrier_tiers` — e.g.
"burn either natural gas or hydrogen, whichever is available"). No
technology in this package needs that; if one ever does, it requires
different hand-written "user-defined math" than the above. See
`.claude/open.md`.

**Verified against a real Calliope install (2026-10-23)**, not just
algebraically: a real `export-all` output (15 non-gas technologies,
Loenen gas-free scenario) both loads (`calliope.read_yaml`) and builds
(`m.build()`) successfully against an installed `calliope==0.7.0` — see
"Where each tech's actual ratio *value* lives" above and
`scenarios/NL/loenen_gas_free/docs/phase4_solve.md` for the two real bugs
that verification caught and fixed. **Still not verified**: an actual
numeric *solve* (`m.solve()`) — blocked in that same pass by an unrelated
Pyomo/HiGHS solver-backend compatibility bug in the validation
environment, not by anything in this package's generated YAML. Spot-check
both the tech YAML and the accompanying `additional_math.yaml` against
`calliope==0.7.0` (the decided target) before relying on it for a real
solve -- the Loenen scenario does exactly this.

## Weather-driven COP profiles (`new/heat_pump/weather_cop.py`)

The catalog's heat pump COP (`heat_pump_electric_*`/`heat_pump_geothermal_*`
in the registry) is always a single fixed design-point value — see "Heat
pump efficiency" above. `new/heat_pump/weather_cop.py` is a separate,
opt-in path that computes a *real* hourly COP from an actual 2 m
outdoor-air temperature series instead, for whoever wants a time-varying
`flow_out_eff`/`flow_in_eff` rather than the design-point scalar. It does
**not** change the registry or the `modern`/`ratio_math` exporters — the
catalog stays design-point-only by design (`.claude/heat_pump/resolved.md`
"weather-integration-scope").

The temperature series comes from the sibling
[`weather`](https://github.com/UU-BUEM/weather) package's own
`get_point_weather(latitude, longitude, year, provider="era5-land",
data_dir=None)` (column `T`) — a real per-location fetch of an already-processed archive
(it does not download/process data itself; raises `FileNotFoundError` if
nothing's been processed yet for that `(provider, year)`). `weather` is a
**compulsory** runtime dependency of this package (`pyproject.toml`,
`infrastructure/env/conversion_env.yml`), matching how
[`UU-BUEM/buem`](https://github.com/UU-BUEM/buem) treats the same
dependency — no CSV/local-file fallback exists. Installed as
`weather[pointquery]` (not `weather[pointquery,solar]` like `buem` — COP
only needs `T`, no irradiance), which is the *lightweight* extra
(`xarray`+`netcdf4`, opening an already-processed point) rather than
`weather`'s much heavier `pipeline` extra (cfgrib/dask/eccodes/pyproj/scipy,
needed only to *produce* archives from raw provider sources, not query
them) — `dask` is still needed and conda-installed explicitly alongside it,
since `weather`'s point-query path uses `xr.open_mfdataset` internally
without declaring `dask` in its own `pointquery` extra (confirmed against
`buem`'s own environment spec, which hits the same gap).

Calliope allows *any* parameter to vary over the `timesteps` dimension,
loaded via a top-level `data_tables:` block referencing a CSV (see
[Calliope's Data tables docs](https://calliope.readthedocs.io/en/latest/basic/data_tables/)).
`weather_cop.export_weather_cop()` (also exposed as the `weather-cop` CLI
subcommand, taking `--latitude`/`--longitude`/`--year`/`--provider`/
`--data-dir`) does this end to end:

1. `weather.get_point_weather(latitude, longitude, year, provider=...,
   data_dir=...)` returns an hourly, tz-naive `T`/`GHI`/`DHI`/`DNI`
   DataFrame; only `T` (2 m air temperature, °C) is used. **Not**
   ground/soil temperature — `weather` has none, see the geothermal note
   below.
2. `carnot_cop()` (`new/heat_pump/generic/cop_calculation.py` — already
   array-capable, unchanged) is applied elementwise using the same design
   sink temperature and quality factor `technologies.csv` already has for
   that technology (re-read from the CSV, not retyped by the caller), then
   checked against the same `[1, 20]` sanity bound the design-point COP is
   checked against — per-hour now, not once, and any NaN hour (source
   temperature met/exceeded the sink temperature) raises rather than being
   written silently into a Calliope data table.
3. Two CSVs (`<id>_flow_out_eff.csv` = COP on `heat`,
   `<id>_carrier_flow_ratio_in.csv` = COP − 1, the free source heat per kWh
   of electricity that `ratio_math.py`'s `link_flow_in_carriers` reads;
   the ambient carrier's `flow_in_eff` is not read by that math, so it is
   not varied -- changed 2026-11-26, it used to be)
   and a `data_tables:` YAML block referencing them are written.

```yaml
data_tables:
  heat_pump_electric_household_flow_out_eff:
    table: heat_pump_electric_household_flow_out_eff.csv
    rows: timesteps
    add_dims: {techs: heat_pump_electric_household, carriers: heat, inputs: flow_out_eff}
  heat_pump_electric_household_carrier_flow_ratio_in:
    table: heat_pump_electric_household_carrier_flow_ratio_in.csv
    rows: timesteps
    add_dims: {techs: heat_pump_electric_household, inputs: carrier_flow_ratio_in}
```

Two single-column CSVs rather than one shared multi-column file: Calliope's
`data_tables` column-selection syntax for picking one of several value
columns out of one file wasn't something this could be verified against a
running Calliope install, so this uses the simplest documented shape
instead of guessing at a more compact one.

**Seasonal level (`--match-seasonal-cop HEAT_CSV`).** The design-point
quality factor is calibrated so the *fixed* COP equals the source's annual
average; applied hour by hour it gives a higher heat-weighted seasonal COP
in a mild climate. With hourly heat demand as
weights, `--match-seasonal-cop` scales the series by one factor so that
`sum(Q) / sum(Q / COP)` equals the design COP -- a recalibrated quality
factor, the hourly shape unchanged -- and records it in
`<id>_cop_calibration.json`. Use it when comparing against a fixed-COP
model, so the comparison isolates the timing effect.

**The tech export's scalar COP masks these tables.** Calliope 0.7.0 gives a
value defined in YAML precedence over a data table, and an `import:` cannot
redefine a key, so with the exported tech file loaded as is the model keeps
the flat design COP (checked: the loaded `flow_out_eff` is a constant 3.30).
Set the two scalars to null in a named override and select it when reading:

```yaml
overrides:
  hourly_cop:
    techs:
      heat_pump_electric_household: {flow_out_eff: null, carrier_flow_ratio_in: null}
```

`calliope.read_yaml("model.yaml", scenario="hourly_cop")` then loads the hourly
values. The Loenen scenario does this in `scripts/build_nodes.py`
(`--cop hourly`).

Two things this deliberately does **not** attempt to fix:

- **`nodes` is left out of every `add_dims` block.** This package has no
  concept of a Calliope node/location — it only ever emits `techs:` bodies
  (and now `additional_math.yaml`). Whoever places this technology in an
  actual model must add the right node mapping; the generated YAML's
  `_comment` says so.
- **Geothermal stays design-point-only, permanently.** The `weather`
  package has no ground/soil temperature output anywhere (only 2 m air
  temperature) — confirmed by direct inspection of its source, not an
  oversight. `weather-cop` works for any registered heat pump id
  structurally (exactly 2 input carriers), but there is no real data source
  to point it at for `heat_pump_geothermal_*`.

## Units, currency, and Calliope version

Calliope is explicitly unit/currency-agnostic ("no restrictions on the units
used in model definitions... usually kW and kWh, alongside a currency like
USD... the responsibility of the modeler to ensure consistency" — Calliope's
own docs). This package's convention, used consistently and stated here
once rather than left implicit (changed from USD to EUR2025 on 2026-11-09,
when every value was replaced by a sourced one -- all sources publish in EUR):

| Quantity | Unit | Where |
| --- | --- | --- |
| Currency | EUR, real 2025 prices, excluding VAT and other taxes | every `cost_*` column/parameter (converted from each source's price year with the euro-area HICP -- see [`parameter_sources.md`](parameter_sources.md)) |
| Interest rate | real (inflation-corrected) | `cost_interest_rate` (Dutch social discount rate, 2.25 %) |
| Power / capacity | kW | `flow_cap_max` and everything scaled against it |
| Energy | kWh | `cost_flow_in`/`cost_flow_out`, any `data_tables` timeseries value |
| Timestep | 1 hour | matches `weather`'s and `occupancy`'s native resolution exactly — `weather.get_point_weather()`'s own contract returns an hourly series, trusted rather than re-validated here (`weather-cop` is the one place a real timeseries enters this package) |

**Calliope version**: this package targets **`calliope==0.7.0`** -- decided
(EnerPlanET developers confirmed it repeatedly; `.claude/resolved.md`
"calliope-0.7.0-decided"). 0.7 **shipped as a full stable release** on PyPI as of
2026-10-23 (`pip install calliope==0.7.0` — confirmed working, see
`scenarios/NL/loenen_gas_free/docs/phase4_solve.md`). This updates earlier
guidance here that named `0.7.0.dev8`/`dev7` as the latest available —
that was true when first written but is now stale; `pip install calliope`
with no version pin still resolves to old, incompatible `0.6.10`
(`conversion_plus`/`carrier_ratios` schema), so an exact pin (`==0.7.0`) is
still needed in the *consuming* model repo, just not a dev pre-release
anymore. This package itself takes no `calliope` runtime dependency — it
only ever writes YAML text — so nothing here pins a version; this is
guidance for whoever builds the model that imports this package's output.

## Cooling technologies (`new/chiller/`)

The `chiller` category adds three variants, all sharing one
`specific/__init__.py` builder: `electric` (compression chiller / AC,
electricity in, cooling out), `absorption` (heat in, plus a small parasitic
electricity draw, cooling out), and `heat_pump_reversible` (electricity in,
cooling out -- a reversible unit in cooling mode, kept as its own catalog
row with its own sourced cost and COP rather than sharing capacity with a
`heat_pump` row; it is **not** a literal dual-mode
technology with shared installed capacity, since Calliope's
alternative/either-or carrier support (`carrier_tiers`/`carrier_ratios`) is
removed in current Calliope and not modeled here anyway -- see root
`.claude/open.md`'s first item).

`cop` is a plain `technologies.csv` column, read directly -- unlike
`heat_pump`'s Carnot-cycle-derived COP, there is no design-temperature
formula here (cooling-mode delta-T isn't modeled), so a formula would be
inventing precision the category doesn't have. Per-variant sanity bounds are
enforced in `chiller/specific/__init__.py`: `electric` and
`heat_pump_reversible` are electricity-driven vapor-compression cycles (COP
> 1 by definition, bounded 2-8 and 1.5-8 respectively); `absorption` is
heat-driven (COP < 1 by definition, bounded 0.4-1.3). The bundled `cop`
values are *in-situ seasonal* COPs: Heat Roadmap Europe's standard SEER of
units sold in 2025, times 0.7 (HRE D3.2 §4.4: real installations reach
60-80 % of the standard SEER) -- see [`parameter_sources.md`](parameter_sources.md).

`absorption`'s two input carriers (`heat` + a small `electricity` ratio via
`aux_electricity_ratio`) are structurally identical to `heat_pump`'s
electricity+ambient_heat case -- `calliope_export/ratio_math.py`'s
`len(carriers) > 1` check already generates the needed `additional_math.yaml`
entry for it with no new code (see "Carrier ratio math" above). `electric`
and `heat_pump_reversible` have one carrier per side, like `boiler`, so need
no custom math.

Capacity ceilings and capacity costs apply to the primary output carrier
(cooling) for every chiller variant -- see "Capacity is per carrier" above
-- so a combined household ceiling is a plain sum of `flow_cap_max`.

Out of scope here (see `.claude/chiller/open.md`): which real heat source
feeds an `absorption` row (community waste heat, a CHP byproduct, etc.) is a
scenario-level node-wiring decision; an hourly cooling demand profile
(`scenarios/`'s current `cooling_kWh` is annual-only) and any
individual-vs-community competition between cooling (or heating) sources are
`scenarios/`/`buem` work, not this package's. Same not-validated-against-a-
running-Calliope-solve caveat as everywhere else in this doc applies to the
`cooling` carrier wiring too.

## Electric vehicles (`new/ev/`)

How the EV is split over occupancy, buem, this repo and a scenario, and
where each constraint (SOC, capacity, efficiency, availability) is set:
[`ev_architecture.md`](ev_architecture.md).

### Is an EV a conversion, demand or flexibility technology?

All three, which is why it is not one Calliope technology. From the grid's
point of view an EV is a **flexible demand**: the energy needed for
driving is fixed, but when it is drawn is free within the hours the car is
plugged in. With vehicle-to-grid it becomes **storage** seen from the
grid. Physically it is three parts, each with a Calliope base technology,
linked by their own carrier `ev_electricity` (energy on the car's side of
the charger):

| Part | Catalogue technology | `base_tech` | Carriers |
| --- | --- | --- | --- |
| Charger | `ev_charger_ac_household`, `ev_charger_ac_building`, `ev_charger_dc_community` | `conversion` | electricity → ev_electricity, efficiency 0.92-0.93 |
| Bidirectional charger, discharge side | `ev_v2g_household` | `conversion` | ev_electricity → electricity |
| Traction battery | `ev_battery_household` | `storage` | ev_electricity, 60 kWh fixed, 10% reserve |
| Driving | none (scenario data) | `demand` | ev_electricity, `sink_use_equals` = occupancy `ev_drive_kwh` |
| Charging away from home | none (scenario data) | `supply` | ev_electricity, `source_use_equals` = occupancy `ev_away_charging_kwh` x away efficiency |

The flexibility is not a parameter: it emerges from the battery storing
energy between when it is charged and when it is driven. Because the
driving demand is drawn from the battery, the state of charge needed before
each trip is enforced without any explicit "SOC at departure" constraint.

### Availability: charging only while plugged in

Calliope 0.7.0's base math has a lower bound `flow_out_min_relative` but no
time-varying upper bound on output relative to capacity. Every technology
with `TechnologySpec.time_varying_availability` (the chargers and the V2G
discharger) therefore gets a custom-math constraint, written to the same
`additional_math.yaml` as the carrier-ratio math
(`calliope_export/availability_math.py`):

```yaml
flow_out <= flow_cap * timestep_resolution * flow_out_max_relative
```

`flow_out_max_relative` is a per-node, per-timestep fraction the scenario
supplies as a data table, from occupancy's `ev_plugged_in` column. **Supply
it for every availability-bound technology at a node.** Its declared default
is 1 (always available), so a V2G discharger without the series will
happily discharge a car that is not there. A real solve made exactly this
mistake when only the charger got the series.

### Scenario wiring (per building)

- `ev_battery_household`: give the battery a start and an end. Preferred:
  `cyclic_storage: false`, `storage_initial` = the simulated car's level
  before the first timestep, and `storage_final_min` = its level in the
  last timestep (custom math `storage_final_level_min`,
  `calliope_export/storage_math.py`, written with every export that has a
  storage technology). The simulated year is then a feasible solution and
  the optimised car is the same car. Fallback: `cyclic_storage: true` with
  a free start. Without either, the optimiser drains the "free" initial
  charge. Do **not** combine `cyclic_storage: true` with `storage_initial`:
  the battery must then hold that exact level in the last timestep,
  infeasible when the car is away or nearly empty then (48 of 264 Loenen
  EV households in a first full run).
- An **existing** wallbox: fix its capacity with node-level
  `flow_cap_min` = `flow_cap_max` (car side, e.g. 7.4 kW x 0.92 = 6.81 kW).
  Left free, the optimiser buys the smallest charger that delivers the
  week's energy (0.27 kW in the test below), which is a sizing study, not
  smart charging.
- The battery size (`storage_cap_max`/`storage_cap_min`, 60 kWh) and the
  charger efficiency (0.92) are the same defaults occupancy's EV model
  uses. If one is changed for a building, change both, so the uncontrolled
  baseline and the optimisation describe the same car.
- Per-building decomposition stays exact: the battery is node-local, so it
  couples one building's timesteps, not buildings. A shared community
  battery or a grid link between buildings would not.

### Costs

| Technology | Cost | Basis |
| --- | --- | --- |
| AC home charger | 150 EUR2025/kW (about EUR 2,000 incl. VAT installed, 11 kW) | ANWB, derived |
| AC building charge points | 150 EUR2025/kW | proxy of the household value |
| DC community hub | 204 EUR2025/kW, charger only | Virta, proxy; grid connection extra |
| V2G discharge side | 350 EUR2025/kW premium over a unidirectional charger | assumption |
| V2G battery wear | 0.046 EUR2025 per kWh discharged | BNEF 2024 pack price / 2,000 cycles |
| Battery | none | the car is bought for mobility |

Battery wear is priced on the V2G discharger, not on the battery: smart
charging without discharging does not change the battery's total
throughput (the same driving energy passes through it), so only discharging
to the grid adds wear. Whether DC fast charging wears batteries
measurably faster than AC is contested in the literature, so no extra wear
cost is put on `ev_charger_dc_community`. Electricity and public-charging
prices go on the scenario's supply technologies, as for every other
category.

### Verified in a real `calliope==0.7.0` solve

One household (occupancy `working_couple`, seed 7), one January week, a
time-of-use grid price (0.30 EUR/kWh from 07:00 to 23:00, 0.15 overnight),
CBC solver:

| Check | Result |
| --- | --- |
| Charging while unplugged (`ev_plugged_in` = 0) | 0.000 kWh |
| Hours above capacity x availability | 0 |
| Grid energy to the charger, smart vs. occupancy's uncontrolled profile | 59.0 vs. 59.0 kWh |
| Charging cost, smart vs. uncontrolled | EUR 8.86 vs. EUR 14.90 (all smart charging in cheap hours) |
| Battery minimum / end | 6.0 kWh (reserve) / 54.0 kWh (= start) |
| With V2G: energy back to the home, discharge while unplugged | 23.3 kWh, 0.000 kWh |

## Stationary batteries (`new/battery/`)

`battery_lithium_ion_household` and `battery_lithium_ion_community`:
Calliope `storage` on `electricity`, sized freely in energy (`storage_cap`,
kWh, priced by `cost_storage_cap`) and power (`flow_cap`, kW). Unlike the EV
traction battery they are investments, so a missing `cost_storage_cap` is
rejected.

| Column | Meaning |
| --- | --- |
| `efficiency` | one-way efficiency, exported as both `flow_in_eff` and `flow_out_eff` (round trip = efficiency squared) |
| `storage_cap_max` | per-node ceiling on usable energy (kWh) |
| `flow_cap_per_storage_cap_max` | C-rate limit (kW per kWh); required, otherwise a battery whose power is free (household) could charge fully in one hour |
| `storage_loss` | self-discharge per hour (Calliope's unit), from DEA's %/day |
| `cost_storage_cap` | investment per kWh (`costs.csv`) |
| `cost_flow_cap` | investment per kW, only where the source splits it (community; DEA power conversion system). A home battery is sold per usable kWh with inverter and installation, so it has none. |

Sources: Danish Energy Agency storage datasheet, sheet 180 (utility scale,
May 2025) for the community battery; energievergelijk.nl installed prices
(fixed 10 kWh system) for the home battery. At DEA's costs a 1 MW / 2 MWh
battery is about EUR 581k against the Thomassen (Loenen) battery's reported
EUR 375k -- see `parameter_sources.csv`.

**Grid export is not a package technology.** Like grid import
(`supply_grid_electricity`), selling electricity is a market
transaction priced in the scenario (convention #8: electricity is priced
once, on the market techs), so the export sink lives in the scenario's
`demand_techs.yaml`.

## Generation technologies (`generation_technologies/`)

A generation technology is a Calliope `supply` tech
(`TechnologySpec.base_tech == "supply"`): no `carrier_in`, one
`carrier_out`, and `source_unit` from the spec. Rooftop PV uses
`source_unit: per_cap` with `flow_out_eff: 1.0`; its `source_use_max`
(AC output per kWp per hour, losses included) is scenario data written by
`generation_technologies.pv.profiles`. Capacity, cost and lifetime fields
map exactly as for conversion techs (indexed on `electricity`). Method,
consistency with EnerPlanET's pysam-pv, and the roof layout:
[`generation_technologies.md`](generation_technologies.md).

## occupancy is out of scope

`occupancy`'s `total_power_kwh` (hourly household/building electricity
demand — no community scale, no heat/hot-water output) is not wired into
anything here, and this package does not export a Calliope `demand`
technology for it. Reasons this stays a documentation note rather than a
feature: a heat pump's electricity draw is normally a Calliope-optimizer
decision, not an exogenous profile — `occupancy`'s output would become a
*separate* `demand` technology's `sink_use_equals`, sharing a node with the
conversion technologies here, not an input wired to one of them; and this
package's own scope is conversion technologies specifically (`occupancy`
itself has zero Calliope integration today). Whoever builds the full model
wires `occupancy`'s CSV to a hand-written `demand` tech themselves. Separately:
neither `weather` nor `occupancy` produce a **heat demand** profile at all
(`occupancy`'s `CHANGELOG.md` explicitly excludes thermal loads) — an actual
Calliope model still needs one from elsewhere to have anything for the heat
pump/boiler/CHP technologies here to usefully dispatch against.

The same holds for the EV technologies above: this package defines the
charger, discharger and battery, while occupancy's EV time series
(`ev_plugged_in`, `ev_drive_kwh`, `ev_away_charging_kwh`) reach a model
only as scenario data tables. Neither package imports the other.
