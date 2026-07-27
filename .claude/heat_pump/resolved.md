# Resolved / BY-DESIGN — heat_pump

- BY-DESIGN: the free heat-source carrier (`ambient_heat`/`ground_heat`) is
  modeled as a second input carrier with ratio `(COP - 1)`, and electricity
  as the primary input with ratio `1.0`, so `heat_out / electricity_in ==
  COP` exactly. This mirrors how Calliope v0.5.1's `conversion_plus` example
  models a heat pump in its own docs.
- BY-DESIGN: `carnot_cop` is one function accepting either a scalar or an
  array-like source temperature (numpy elementwise), not two separate
  functions. The `T` column of the weather module's
  `CsvWeatherData.extract_weather_columns()` (2 m air temperature, deg C) is
  the harmonised cross-provider output the array form is meant to consume --
  it originates from COSMO-REA6's raw `T_2M`, ERA5-Land's `t2m` and
  MERRA-2's `T2M`, each already converted from Kelvin to Celsius by the
  weather module itself, so no unit conversion is needed on this side.
- [weather-integration-scope] BY-DESIGN: the catalog builder
  (`new/heat_pump/specific/__init__.py`'s `_build`) stays zero-argument
  (called via `functools.partial(_build, row)`, no external inputs beyond
  the CSV row) and keeps using a fixed design-point COP -- registration
  happens at import time with no arguments, matching `core.registry`'s
  builder contract. Computing a real seasonal-average COP from an actual
  weather time series is left as a downstream/notebook use of
  `carnot_cop`'s array form, not wired into the registry. See open.md if
  this needs to become a first-class feature.
