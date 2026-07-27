# Open items — heat_pump

- COP is currently a single design-point value per catalog technology
  (`carnot_cop` at one source/sink temperature pair), not a real
  temperature-weighted seasonal average. `generic/cop_calculation.py`'s
  `carnot_cop` now accepts an array of source temperatures directly (e.g. a
  real hourly `T` series from the weather module's
  `CsvWeatherData.extract_weather_columns()` -- see resolved.md), but no
  catalog builder (`electric_heat_pump.py`, `geothermal_heat_pump.py`) wires
  a real weather source in yet; they still use one fixed design-point
  temperature pair from `data/defaults.json`. Deliberately deferred (see
  resolved.md "weather-integration-scope") -- builders must stay zero-arg
  for the registry, so wiring a real series in would need a new,
  non-catalog entry point, not a change to the existing builders.
- No water-source (surface water/wastewater) heat pump variant yet.
- Design source/sink temperatures in `data/defaults.json` are NL-climate
  assumptions (2C air / 10C ground design source, 45C low-temp sink) --
  revisit per project/climate.
- Defrost/icing losses (air-source COP derates near 0-5C in humid
  conditions) are not modeled. The weather module's harmonised `RH` output
  would be the relevant input if this is ever added -- flagged, not
  implemented, since it needs a cited derating curve, not a guess.
