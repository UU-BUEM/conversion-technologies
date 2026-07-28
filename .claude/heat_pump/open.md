# Open items — heat_pump

- **No ground/soil temperature data source exists, permanently.** The
  weather module has no ground/soil temperature output anywhere (only 2 m
  air temperature) -- confirmed by direct inspection of its source, not an
  oversight. `heat_pump_geothermal_*`'s `design_source_temp_c` therefore
  stays a fixed, non-weather-driven assumption even though
  `new/heat_pump/weather_cop.py` (see resolved.md "weather-cop-entry-point")
  works for any registered heat pump id structurally -- there is simply
  nothing to point it at for the geothermal variant. Would need a real
  soil-temperature data source added to `weather` (or elsewhere) first, not
  a code change here.
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
