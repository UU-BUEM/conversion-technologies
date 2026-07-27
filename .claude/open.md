# Open items (cross-cutting)

- [modern-exporter] No technology here needs Calliope's removed
  `carrier_tiers`/`carrier_ratios` (alternative/either-or carriers) — if one
  ever does, it requires hand-written "user-defined math"; not implemented.
  See `docs/calliope_schema_mapping.md`.
- [modern-exporter] `carrier_in`/`carrier_out` list-vs-scalar and per-carrier
  `flow_in_eff`/`flow_out_eff` (`dims: carriers`) syntax was inferred from
  Calliope's public docs/examples, not validated against a running Calliope
  install — spot-check against whatever Calliope version is actually pinned
  in a downstream model repo before relying on the `modern` schema output.
  (Cost parameter names -- `cost_flow_cap`, `cost_om_annual`,
  `cost_flow_in`, `cost_flow_out`, `cost_interest_rate` -- *are* now
  confirmed against Calliope's math docs; this item is about carrier/
  efficiency syntax specifically, not costs.)
- [existing] `existing/fireplace.py` (occupancy+weather-driven simulation of
  incumbent stock) is untouched and out of scope — see resolved.md.
- [csv-input] `CONVERSION_TECH_PARAMS_DIR` replaces the whole
  technologies.csv + costs.csv pair for a run; it does not merge
  cell-by-cell with the bundled defaults, and it can't be set via a CLI
  flag (registration happens at import time). If per-invocation switching
  or partial-row overrides become a real need, that requires deferring
  registration until the CLI explicitly triggers it — a bigger change, not
  attempted here.
- [dynamic-params] `modern.py`'s passthrough assumes every non-blank,
  non-structural, non-formula column is a literal Calliope parameter name
  and belongs in the YAML output as-is. There is no guard against adding a
  purely-for-humans reference column (e.g. "manufacturer") -- it would
  incorrectly show up as a bogus Calliope key. Not a problem today (every
  current column is a real parameter), but worth a comment/prefix
  convention (e.g. `_manufacturer`) if a human-only column is ever needed.
- [capacity-ceilings] `core.validation.DEFAULT_CAPACITY_CEILINGS_KW`
  (household 100 kW / building 2,000 kW / community 50,000 kW) is one
  shared, deliberately generous set of sanity bounds applied to all three
  categories. If a category's real-world scale genuinely differs (e.g. a
  community-scale CHP plant plausibly exceeds a community-scale heat pump
  array), `require_scale_capacity` already accepts a per-call `ceilings`
  override -- not used yet since no current technology needs it.
