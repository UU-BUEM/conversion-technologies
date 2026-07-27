# Calliope schema mapping

This package keeps one version-agnostic internal model
(`conversion_technologies.core.technology.TechnologySpec`) and translates it
to Calliope YAML only at export time
(`conversion_technologies.calliope_export.modern`). This document is the
reference for what the exporter does and why, the cost-column reference,
the heat pump efficiency naming decision, and known limitations.

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

## Known limitation: carrier ratios

Calliope's current release removed `conversion_plus`, `carrier_tiers`, and
`carrier_ratios` from the base technology schema entirely (see its
[migration guide](https://github.com/calliope-project/calliope/blob/main/docs/migrating.md):
"implement via custom math"). For every technology in this package, a
fixed ratio between carriers on the same side of the conversion (heat pump
COP, CHP power-to-heat ratio) is expressed instead via **per-carrier
efficiency** (`flow_in_eff`/`flow_out_eff` with `dims: carriers`) against
the technology's single shared internal flow variable — which reproduces a
fixed-ratio relationship for every technology currently defined here.

This does **not** cover genuinely alternative/either-or carriers (what
v0.5.1 called `carrier_tiers` — e.g. "burn either natural gas or hydrogen,
whichever is available"). No technology in this package needs that yet; if
one ever does, it requires hand-written Calliope "user-defined math," which
is out of scope for the `modern` exporter. See `.claude/open.md`.

The exact `modern`-schema key names (`flow_in_eff`, `dims: carriers`, etc.)
were taken from Calliope's public docs/examples rather than validated
against a running Calliope model — spot-check exported YAML against whatever
Calliope version is actually pinned in the consuming model repo.
