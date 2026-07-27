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
- [existing] `existing/fireplace.py` (occupancy+weather-driven simulation of
  incumbent stock) is untouched and out of scope — see resolved.md.
