# Open items — combined_heat_and_power

- Only natural gas and biomass CHP are implemented; no hydrogen-ready or
  micro-CHP (Stirling engine) variant yet.
- `alpha`/`beta` in `data/defaults.json` are treated as fixed per
  technology/scale; real CHP units often have a controllable operating
  range (varying power:heat ratio at part load) -- not modeled.
