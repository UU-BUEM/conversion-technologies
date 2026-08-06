# Resolved / BY-DESIGN — heat_pump

- BY-DESIGN: the free heat-source carrier (`ambient_heat`/`ground_heat`) is
  modeled as a second input carrier with ratio `(COP - 1)`, and electricity
  as the primary input with ratio `1.0`, so `heat_out / electricity_in ==
  COP` exactly. This mirrors how Calliope v0.5.1's `conversion_plus` example
  models a heat pump in its own docs.
- BY-DESIGN: `carnot_cop` is one function accepting either a scalar or an
  array-like source temperature (numpy elementwise), not two separate
  functions. `weather.get_point_weather()`'s `T` column (2 m air
  temperature, deg C, already converted from Kelvin and harmonised across
  COSMO-REA6/ERA5-Land/MERRA-2 by `weather` itself) is the array form's
  real-world consumer -- see [weather-cop-entry-point] below.
- [weather-integration-scope] BY-DESIGN: the catalog builder
  (`new/heat_pump/specific/__init__.py`'s `_build`) stays zero-argument
  (called via `functools.partial(_build, row)`, no external inputs beyond
  the CSV row) and keeps using a fixed design-point COP -- registration
  happens at import time with no arguments, matching `core.registry`'s
  builder contract. A real, weather-driven COP is deliberately a *separate*
  entry point instead -- see [weather-cop-entry-point] below -- not a
  change to this builder or the registry contract.
- [weather-cop-entry-point] BY-DESIGN: real hourly COP from an actual
  weather time series is now a first-class feature
  (`new/heat_pump/weather_cop.py`, also the `weather-cop` CLI subcommand),
  per explicit user request -- but implemented as the "new, non-catalog
  entry point" [weather-integration-scope] above anticipated, not by giving
  the registry builder arguments. It re-derives the design sink temperature
  and quality factor from `technologies.csv` for the requested id (same
  source `_build` reads, not retyped by the caller) rather than adding new
  `TechnologySpec` fields for them. Calls `weather.get_point_weather(lat,
  lon, year, provider=...)` directly -- `weather` is a **compulsory**
  runtime dependency of this package (`pyproject.toml`, `infrastructure/
  env/conversion_env.yml`), matching how `UU-BUEM/buem` treats the same
  dependency. SUPERSEDES an earlier version of this decision that read a
  CSV via a since-deleted `core.weather_series` module with zero dependency
  on `weather` itself, reversed once the `buem` precedent was found -- see
  root `.claude/resolved.md` "weather-real-dependency". See open.md: this
  only ever applies to the air-source (`electric`) variant in practice,
  since there is no ground-temperature data source for `geothermal`.
