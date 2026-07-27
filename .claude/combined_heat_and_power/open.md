# Open items — combined_heat_and_power

- Only natural gas and biomass CHP are implemented; no hydrogen-ready or
  micro-CHP (Stirling engine) variant yet.
- `alpha`/`beta` in `technologies.csv` are treated as fixed per
  technology/scale; real CHP units often have a controllable operating
  range (varying power:heat ratio at part load) -- not modeled.
- `flow_ramping` is a single flat value per variant (1.0 for gas, 0.3 for
  biomass), an illustrative guess at relative flexibility, not sourced from
  a specific unit's spec sheet.
- `flow_cap_max` is now validated against the shared per-scale capacity
  ceiling (`new/combined_heat_and_power/specific/__init__.py`, via
  `core.validation.require_scale_capacity`) -- same generous, typo-catching
  bounds as boiler/heat_pump, not CHP-specific. See root
  `.claude/resolved.md` "validation-in-source".
