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
| `cost_interest_rate` | Discount/interest rate for cost annualisation -- not a currency cost | fraction, e.g. `0.10` | "interest rate for annuity calculation" |

`cost_flow_in` and `cost_flow_out` are kept as two distinct columns rather
than merged into one "variable cost," because Calliope itself treats them
as distinct parameters (input-linked vs. output-linked). Not currently
used: `cost_om_annual_investment_fraction` (fixed cost as a fraction of
investment instead of currency/kW/year) and `cost_depreciation_rate` (an
alternative to interest-rate-based annuity) -- both real Calliope
parameters, add as new columns if a project needs them.

## Heat pump efficiency

`technologies.csv`'s `efficiency` column is shared between boiler (plain
thermal efficiency, 0.8-0.99) and heat pump (the Carnot quality/2nd-law
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
      - where: techs=heat_pump_electric_household
        expression: flow_in[carriers=ambient_heat] == flow_in[carriers=electricity] * carrier_flow_ratio_in
  balance_conversion:  # overrides the base equation, scoped per affected tech
    where: base_tech==conversion AND NOT include_storage==true
    equations:
      - where: techs=heat_pump_electric_household
        expression: flow_out_inc_eff[carriers=heat] == flow_in_inc_eff[carriers=electricity]
```

`carrier_flow_ratio_in`/`carrier_flow_ratio_out` are derived straight from
the existing `carriers_in`/`carriers_out` ratios (`secondary / primary`) — no
new CSV column. This mirrors the pattern Calliope's own team uses in their
official CHP example
(`calliope/src/calliope/example_models/urban_scale/additional_math.yaml`:
`heat_to_power_ratio` + a `link_chp_outputs` equality constraint + the same
kind of scoped `balance_conversion` override), generalised to work for the
input side too (heat pump) instead of only the output side (CHP).

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

**Caveat, stated plainly**: this was derived algebraically from Calliope's
published base math and cross-checked against its own official example —
not verified against a running Calliope solve (none is available in this
environment). Spot-check both the tech YAML and the accompanying
`additional_math.yaml` against whatever Calliope version is actually pinned
in the consuming model repo before relying on it for real analysis.

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
data_dir=None)` — a real per-location fetch of an already-processed archive
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
3. Two CSVs (`<id>_flow_out_eff.csv` = COP, `<id>_flow_in_eff.csv` = COP − 1)
   and a `data_tables:` YAML block referencing them are written.

```yaml
data_tables:
  heat_pump_electric_household_flow_out_eff:
    table: heat_pump_electric_household_flow_out_eff.csv
    rows: timesteps
    add_dims: {techs: heat_pump_electric_household, carriers: heat, inputs: flow_out_eff}
  heat_pump_electric_household_flow_in_eff:
    table: heat_pump_electric_household_flow_in_eff.csv
    rows: timesteps
    add_dims: {techs: heat_pump_electric_household, carriers: ambient_heat, inputs: flow_in_eff}
```

Two single-column CSVs rather than one shared multi-column file: Calliope's
`data_tables` column-selection syntax for picking one of several value
columns out of one file wasn't something this could be verified against a
running Calliope install, so this uses the simplest documented shape
instead of guessing at a more compact one.

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
once rather than left implicit:

| Quantity | Unit | Where |
| --- | --- | --- |
| Currency | USD | every `cost_*` column/parameter |
| Power / capacity | kW | `flow_cap_max` and everything scaled against it |
| Energy | kWh | `cost_flow_in`/`cost_flow_out`, any `data_tables` timeseries value |
| Timestep | 1 hour | matches `weather`'s and `occupancy`'s native resolution exactly — `weather.get_point_weather()`'s own contract returns an hourly series, trusted rather than re-validated here (`weather-cop` is the one place a real timeseries enters this package) |

**Calliope version**: this package's `flow_*`/`conversion` schema targets
Calliope **0.7**, which is still pre-release. `pip install calliope` with no
version pin resolves to old, incompatible `0.6.10`
(`conversion_plus`/`carrier_ratios` schema) — pin an exact `0.7.0.devN`
(`0.7.0.dev7` was the latest on PyPI as of this writing; GitHub `main` was
ahead at `0.7.0.dev8`, unreleased) or install from `main` in the *consuming*
model repo. This package itself takes no `calliope` runtime dependency — it
only ever writes YAML text — so nothing here pins a version; this is
guidance for whoever builds the model that imports this package's output.

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
