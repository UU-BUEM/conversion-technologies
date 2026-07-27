# Calliope schema mapping

This package keeps one version-agnostic internal model
(`conversion_technologies.core.technology.TechnologySpec`) and translates it
to a specific Calliope YAML schema only at export time
(`conversion_technologies.calliope_export`). This document is the reference
for what each exporter does and why, and its known limitations.

## Why two schemas

Calliope's technology definition schema changed substantially between the
[v0.5.1 docs](https://calliope.readthedocs.io/en/v0.5.1/user/configuration_reference.html#abstract-base-technologies)
the user linked and the current release on
[GitHub](https://github.com/calliope-project/calliope) (see
[`docs/migrating.md`](https://github.com/calliope-project/calliope/blob/main/docs/migrating.md)
upstream). Rather than pick one and risk the whole package going stale on
the next Calliope release, every technology is defined once against the
internal model and each exporter is a self-contained, independently
replaceable translation.

## Attribute mapping

| Concept | Internal (`TechnologySpec`) | `legacy_v051` (Calliope v0.5.1) | `modern` (current Calliope) |
| --- | --- | --- | --- |
| Tech kind | *(implicit: >1 carrier each side is possible)* | `parent: conversion_plus` | `base_tech: conversion` |
| Input carrier(s) | `carriers_in: dict[carrier, ratio]` | `carrier_in`, `carrier_in_2`, `carrier_in_3` (max 3, each `{carrier: ratio}`) | `carrier_in`: single string, or list if >1 |
| Output carrier(s) | `carriers_out: dict[carrier, ratio]` | `carrier_out`, `carrier_out_2`, `carrier_out_3` (max 3) | `carrier_out`: single string, or list if >1 |
| Input efficiency/ratio | *(ratio value in `carriers_in`)* | encoded directly as the carrier_in tier's value | `flow_in_eff`: scalar if 1 carrier, else `{data, index, dims: carriers}` |
| Output efficiency/ratio | *(ratio value in `carriers_out`)* | encoded directly as the carrier_out tier's value | `flow_out_eff`: scalar if 1 carrier, else `{data, index, dims: carriers}` |
| Primary carrier (costing) | `primary_carrier_out` | `primary_carrier_out` (required) | not applicable in the same way; omitted |
| Capacity | `flow_cap_max` / `flow_cap_min` | `constraints["e_cap.max"/"e_cap.min"]` | `flow_cap_max` / `flow_cap_min` |
| Lifetime | `lifetime` | `constraints.lifetime` | `lifetime` |
| Investment cost | `cost_flow_cap` | `costs.monetary.e_cap` | `cost_flow_cap: {data, index: monetary, dims: costs}` |
| Fixed O&M | `cost_flow_om_annual` | `costs.monetary.om_annual` | `cost_flow_cap_annual: {...}` |
| Variable cost | `cost_flow_out` | `costs.monetary.om_var` | `cost_flow_out: {...}` |
| Provenance note | `notes` | `_comment` | `_comment` |

## Known limitation: the `modern` exporter and carrier ratios

Calliope's current release removed `conversion_plus`, `carrier_tiers`, and
`carrier_ratios` from the base technology schema entirely (see
`docs/migrating.md` upstream: "implement via custom math"). For every
technology in this package, a fixed ratio between carriers on the same side
of the conversion (heat pump COP, CHP power-to-heat ratio) is expressed
instead via **per-carrier efficiency** (`flow_in_eff`/`flow_out_eff` with
`dims: carriers`) against the technology's single shared internal flow
variable — which reproduces a fixed-ratio relationship for every technology
currently defined here.

This does **not** cover genuinely alternative/either-or carriers (what
v0.5.1 called `carrier_tiers` — e.g. "burn either natural gas or hydrogen,
whichever is available"). No technology in this package needs that yet; if
one ever does, it requires hand-written Calliope "user-defined math," which
is out of scope for the `modern` exporter. See `.claude/open.md`.

The exact `modern`-schema key names (`flow_in_eff`, `dims: carriers`, etc.)
were taken from Calliope's public docs/examples rather than validated
against a running Calliope model — spot-check exported YAML against whatever
Calliope version is actually pinned in the consuming model repo.
