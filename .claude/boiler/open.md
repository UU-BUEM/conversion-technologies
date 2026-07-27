# Open items — boiler

- Default capacity/cost/efficiency figures in `technologies.csv` are
  indicative order-of-magnitude literature values (NL residential/utility
  context), not sourced from a specific dataset — replace with project-
  specific figures before using outputs for real analysis.
- `cost_flow_in` (fuel cost) for gas/biomass boilers is a single flat
  illustrative value, same reasoning — see `.claude/resolved.md`
  "new-cost-fields".
- No hybrid (boiler + heat pump) or hydrogen-ready boiler variant yet.
- Nameplate `efficiency` is now validated at `0.8 <= efficiency <= 0.99`
  and `flow_cap_max` against the shared per-scale capacity ceiling (both in
  `new/boiler/specific/__init__.py`, via `core.validation`) -- see root
  `.claude/resolved.md` "validation-in-source" for the full rationale.
