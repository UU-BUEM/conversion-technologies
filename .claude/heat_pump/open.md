# Open items — heat_pump

- COP is currently a single design-point value per catalog technology
  (`carnot_cop` at one source/sink temperature pair), not a real
  temperature-weighted seasonal average. `generic/cop_calculation.py`'s
  `carnot_cop` now accepts an array of source temperatures directly (e.g. a
  real hourly `T` series from the weather module's
  `CsvWeatherData.extract_weather_columns()` -- see resolved.md), but the
  category builder (`new/heat_pump/specific/__init__.py`) doesn't wire a
  real weather source in yet; it uses one fixed design-point temperature
  pair per `technologies.csv` row. Deliberately deferred (see resolved.md
  "weather-integration-scope") -- registration happens at import time with
  no arguments, so wiring a real series in would need a new, non-catalog
  entry point, not a change to the existing builder.
- No water-source (surface water/wastewater) heat pump variant yet.
- Design source/sink temperatures in `technologies.csv` are NL-climate
  assumptions (2C air / 10C ground design source, 45C low-temp sink) --
  revisit per project/climate.
- Defrost/icing losses (air-source COP derates near 0-5C in humid
  conditions) are not modeled. The weather module's harmonised `RH` output
  would be the relevant input if this is ever added -- flagged, not
  implemented, since it needs a cited derating curve, not a guess.
- `technologies.csv`'s `carnot_efficiency` column was renamed to
  `efficiency` (shared name with boiler); it's the Carnot quality factor,
  not the COP. Both the quality factor and the *computed* COP are now
  validated (`0 < efficiency <= 1` and `1 <= cop <= 20` respectively) --
  see root `.claude/resolved.md` "heat-pump-efficiency-rename" and
  `docs/calliope_schema_mapping.md` "Heat pump efficiency".
