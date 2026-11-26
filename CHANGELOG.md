# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Loenen: solver comparison** (scenario): `scripts/benchmark_solvers.py`
  times CBC (Pyomo), HiGHS (simplex, interior point) and Gurobi (barrier),
  the latter two through Calliope's native backends, on identical
  per-building models. 60 dwellings: all optimal, objectives within 8e-9;
  median solve 27.4 / 14.4 / 10.7 / 3.7 s. See
  `scenarios/NL/loenen_gas_free/docs/solver_comparison.md`.

## [0.7.0] - 2026-11-26

### Added

- `weather-cop --match-seasonal-cop HEAT_CSV` (`export_weather_cop(...,
  match_seasonal_heat=...)`, `seasonal_cop()`, `match_seasonal_cop()`):
  scales the hourly COP so its heat-weighted seasonal COP equals the
  design-point COP (one factor = a recalibrated Carnot quality factor), and
  writes `<id>_cop_calibration.json`. Without it the design-point quality
  factor shifts the seasonal COP away from the fixed-COP value.
- **Loenen: fixed vs hourly heat pump COP**, region and pilot (scenario):
  `build_nodes.py --cop hourly_matched` (new default) | `hourly` | `design`;
  `build_hp_cop.py --match-seasonal`; `compare_cop_variants.py`;
  `solve_all_buildings.py --solver` (Gurobi/HiGHS native backends; solver
  settings shared in `build_nodes.py`); per-building re-solve with the new
  demand (`outputs/v5`), three COP variants. Method:
  `scenarios/NL/loenen_gas_free/docs/phase10_heat_pump_cop.md`.

- **Loenen: hourly air-source heat pump COP** (scenario):
  `scripts/build_hp_cop.py` (`weather-cop` CLI, MERRA-2 2018 at the demand
  and PV weather point) -> `heat_pump_cop_2018/`; `build_nodes.py --cop
  hourly` (default; `design` reproduces v3/v4) wires `flow_out_eff[heat]`
  and `carrier_flow_ratio_in` per hour through the `hourly_cop` override
  (Calliope 0.7.0 lets YAML values beat data tables). See `scenarios/NL/loenen_gas_free/docs/phase9_community_pilot.md`.

### Changed

- `weather-cop` writes the hourly `carrier_flow_ratio_in` (COP - 1, the free
  source heat per kWh of electricity that `ratio_math.py` reads) instead of
  `flow_in_eff` on the ambient carrier, which that math ignores; output
  `<id>_carrier_flow_ratio_in.csv`, `build_cop_data_tables(...,
  carrier_flow_ratio_in_csv=...)`.

## [0.6.0] - 2026-11-26

### Changed

- **weather dependency back to UU-BUEM/weather** (`v1.11.0`), the module
  EnerPlanET uses, instead of `enerplanet/weather` v2.5.0 (introduced in
  v0.5.0). PV profiles call `get_point_weather(..., wind=True)`: PVWatts
  needs the 10 m wind speed for the module temperature (not wind power).
  `weather-cop` calls `get_point_weather(...)` and reads `T`. Same MERRA-2
  archive, so the Loenen PV potential is identical (every roof's kWh/kWp
  unchanged). Update an environment with
  `conda env update -f infrastructure/env/conversion_env.yml`.

### Added

- **Loenen community pilot results** (scenario only): full year, 20
  members on one station. Community EUR 60,435/yr vs independent
  EUR 64,532/yr (-6.3%), 65.3 vs 49.6 kWp PV, one 121 kWh community battery
  instead of 37 kWh at homes, import 27.6 vs 45.7 MWh; the station limit
  does not bind. `build_community.py --solver gurobi` (Calliope's native
  Gurobi backend, barrier); HiGHS default now runs interior point without
  crossover. `solve_community.py` reports peaks in kW per time step length.
  See `scenarios/NL/loenen_gas_free/docs/phase9_community_pilot.md`.

## [0.5.0] - 2026-11-26

### Added

- **Stationary batteries** (`new/battery/`): `battery_lithium_ion_household`
  and `battery_lithium_ion_community`, Calliope `storage` on electricity,
  sized in energy and power. New columns: `flow_cap_per_storage_cap_max`,
  `storage_loss` (`technologies.csv`), `cost_storage_cap` (`costs.csv`);
  every other row leaves them blank. Community costs from the Danish Energy
  Agency storage datasheet (sheet 180, May 2025, EUR2020 -> 2025): 239
  EUR/kWh + 103 EUR/kW, 9.9 EUR/kW/yr, 91% round trip, 20 years. Home
  battery: 522 EUR per usable kWh installed, excl. VAT (energievergelijk.nl,
  fixed 10 kWh system), 81.5% round trip, 15 years. Grid export stays a
  scenario tech, like grid import. See `docs/calliope_schema_mapping.md`
  "Stationary batteries".
- **Loenen scenario: measures catalogue and energy-community design**
  (scenario only, no package change). `scenarios/NL/loenen_gas_free/measures/`
  is a sourced inventory of loenenenergie.nl (25 measures, 12 subsidy schemes,
  6 shared assets, context), validated and converted to JSON by
  `scripts/build_measures_json.py`. `docs/energy_community_workflow.md` sets out
  the region → energy-community workflow: a provided network or pylovo grid,
  simulation, flexibility, a community filter, a per-feeder Calliope model and
  a power-flow re-check.
- **Loenen scenario: grid model (energy-community step 1)**, scenario only.
  `scripts/build_grid.py` builds one grid package, the same format for every
  source. It assigns each building to an MV/LV station and an LV feeder. The
  source is the first available of:
  - a provided network;
  - the DSO's open data (Liander: cable and station geometry, CC BY 4.0, plus
    the per-transformer ratings and peaks list, which may not be
    redistributed);
  - a synthetic grid from the enerplanet-pylovo API, with a cross-check
    against the DSO.

  Buildings are traced along the LV cable geometry. For Loenen: 1,229 of
  1,260 buildings over 42 stations and 103 feeders. `scenario_env.yml` gains
  shapely, pyproj, networkx, scipy and pytest; scenario tests are in
  `scenarios/NL/loenen_gas_free/tests/`. See `docs/phase7_grid.md`.

- **Loenen energy community, step 2: demand and supply per station**
  (scenario only, no package change). Envelope-retrofit region copies
  (`scripts/build_retrofit_region.py`, TABULA variant 2/3), 138 background
  buildings (multi-unit and service), an EV-50% run, rooftop PV potential
  for every roof plus the Thomassen roof calibrated to 800 MWh/yr
  (`scripts/build_pv_potential.py`, via the `pv-profile` CLI), all summed
  per Liander station (`scripts/build_step2_profiles.py`). The modelled
  present-day electric peak agrees closely with Liander's measured
  station peaks (figures kept local: licensed). Phase 1 wrapper gains `--region-dir`, `--ids-file`,
  `--window-ach`; `build_grid.py --buildings` takes several files. All
  Phase 1 runs use buem's window fix (TABULA glazing share, window shading)
  and `--window-ach 3`: cooling 10.3 -> 1.8 MWh per dwelling. See
  `docs/phase8_demand_supply.md`.
- **Loenen energy community, steps 5-6: community pilot** (scenario only).
  `scripts/community/`: `select_members.py` (seeded draw stratified by
  feeder, or a provided list), `build_community.py` (members via
  `build_nodes.py`, plus rooftop PV, home battery, grid export
  `demand_grid_export` at the day-ahead price; modes independent /
  community / community with an hourly station limit), `solve_community.py`.
  Pilot: 20 members on station MSR5000927. `energy_prices.csv` gains the
  export row; `references.csv` gains the Energy-Charts day-ahead source.
  `solve_independent.py` solves the independent variant exactly as one
  model per member. `build_community.py --solver` defaults to `highs`
  through Calliope's own HiGHS backend (`config.build.backend: highs`): same
  optimum as CBC on the one-week test, 2.6x faster. Pyomo's HiGHS
  interfaces fail on Calliope 0.7.0 models with Pyomo 6.10.1 and 6.9.4; the
  `highspy` comment in `scenario_env.yml` now says so.
  See `docs/phase9_community_pilot.md`.

- **Generation technologies** (`generation_technologies/`, own
  `technologies.csv`/`costs.csv`; CLI alias `pv`): rooftop photovoltaics
  `pv_rooftop_household` and `pv_rooftop_building` as Calliope `supply`
  technologies (`source_unit: per_cap`, `flow_out_eff` 1, `flow_cap` in
  kWp). Costs and lifetime from THD-Spatial-AI/OpenTech-DB
  (`solar_pv_distributed`, USD2024 -> EUR2025). See
  `docs/generation_technologies.md`.
- **PV profiles** (`generation_technologies/pv/`): hourly AC output per
  kWp from NREL PVWatts v8 via NREL-PySAM 7.1.1, identical to
  EnerPlanET's PV service (enerplanet/pysam-pv): `tests/test_pv.py`
  checks it against a pinned copy of the service's `simulate.py` on its
  MERRA-2 2018 test weather. Weather from the `weather` package's
  curated variables (`T`, `DHI`, `DNI`, `WS_10M`; weather >= 2.0). Roof
  faces (as buem exports them) -> arrays and per-building potential
  (`pv/roof.py`); Calliope `source_use_max` data table and node
  placement (`pv/profiles.py`); CLI `pv-profile`. NREL-PySAM is the
  optional extra `pv` (conda: `nrel::nrel-pysam`).
- **Supply technologies**: `TechnologySpec.base_tech` accepts `supply`
  (no input carrier, one output carrier, `source_unit`); the `modern`
  exporter writes a `supply` body.
- `tests/test_parameter_sources.py` also covers
  `generation_technologies/`, including text-valued settings.
- **Electric-vehicle category** (`new/ev/`, CLI alias `ev`): AC home
  charger, AC building charge points, DC community fast-charging hub,
  vehicle-to-grid discharger and the vehicle's traction battery, linked by
  a new `ev_electricity` carrier. Driving demand and charging away from
  home are scenario data (from the occupancy package's EV model), not
  catalogue technologies. Costs: home charger from ANWB (derived), DC hub
  from Virta (proxy, charger only), V2G battery wear from BloombergNEF's
  2024 pack price over an assumed 2,000 cycles; the battery itself has no
  investment cost. See `docs/calliope_schema_mapping.md` "Electric
  vehicles".
- **Storage technologies**: `TechnologySpec.base_tech` (`conversion` or
  `storage`); the `modern` exporter writes a `storage` body. New
  `technologies.csv` columns `storage_cap_max`, `storage_cap_min`,
  `storage_discharge_depth`. `cost_flow_cap` is optional for storage only.
- **Time-varying availability**: technologies with
  `TechnologySpec.time_varying_availability` get a custom-math constraint
  `flow_out <= flow_cap * timestep_resolution * flow_out_max_relative`
  (`calliope_export/availability_math.py`), written into the same
  `additional_math.yaml` as the carrier-ratio math. Calliope 0.7.0 has no
  built-in time-varying upper bound. Verified in a real `calliope==0.7.0`
  solve: no charging or discharging while the car is unplugged.
- **Loenen scenario: electric vehicles** (`scenarios/NL/loenen_gas_free`,
  `docs/phase6_ev.md`). Phase 1 rerun with 20% EV ownership; EV nodes get
  the home charger (capacity fixed to the household's wallbox), battery,
  driving demand and away charging; `solve_single_building.py`/
  `solve_all_buildings.py` take `--ev smart|uncontrolled|v2g|none`. Data
  tables are now kept per node only when their tech is at the node.
- **Loenen scenario: hourly grid price** (`scripts/build_grid_price.py`,
  `grid_price_nl_2018.csv`): Eurostat flat price plus the hourly deviation
  of the 2018 NL day-ahead price (Energy-Charts / SMARD.de, CC BY 4.0).
  `build_nodes.py --grid-price day_ahead` (default; `flat` reproduces
  earlier runs) and `--nodes-dir` on the solve scripts. With it, smart EV
  charging saves EUR 45/yr for a sample household.

## [0.4.1] - 2026-11-10

### Fixed

- **Capacity limits and capacity costs now apply to the primary output
  carrier only.** Calliope 0.7 creates one `flow_cap` per carrier (inputs
  included) and applies `flow_cap_max`/`flow_cap_min`, `cost_flow_cap` and
  `cost_om_annual` to every one of them. Exported as scalars, a 15 kW pellet
  boiler was capped at 15 kW of *pellets* (12.6 kW heat), and investment and
  fixed O&M were charged on input and output capacity alike (about double
  for boilers and heat pumps). `modern.py` now indexes them on the primary
  output carrier, as Calliope's own examples do. Invalidates the v0.4.0
  Loenen results (`outputs/v2_sourced`).

### Changed

- **Breaking (environment):** the `weather` dependency is now the
  EnerPlanET line, `enerplanet/weather` v2.5.0 (`pointquery,solar`
  extras), instead of `UU-BUEM/weather@main`. Its `get_point_weather`
  requires naming the variables; `weather-cop` now asks for `["T"]`, the
  PV profiles for `["T", "DHI", "DNI", "WS_10M"]`. Update an existing
  environment with `conda env update -f infrastructure/env/conversion_env.yml`.
- Calliope target fixed at `calliope==0.7.0` (decided; the 0.6.10 question
  is closed).
- `infrastructure/env/scenario_env.yml`: Python 3.11 -> 3.12 (`calliope==0.7.0`
  requires Python >=3.12, so the env could not be created). The `scenario_env`
  conda env now builds and reproduces the earlier venv's solves exactly.
- `validate.py` no longer needs `conda` on PATH: it uses `CONDA_EXE` or runs
  the env's own interpreter from `~/.conda/envs/<name>`.
- `scenarios/*/*/nodes/*.csv` are no longer tracked (regenerated by
  `build_nodes.py`; they were at GitHub's 100 MB file limit).
- `.gitattributes` added (LF in the repository; CRLF for `.bat`/`.ps1`).
- Loenen solver: the building-scale fallback is re-evaluated per variant
  (`--no-biomass` removes the 15 kW pellet boiler, so dwellings with a
  61-64 kW peak now get building-scale heat pumps instead of being
  infeasible). Results rerun as `outputs/v3/` (all 1,260 buildings feasible
  in every variant); the scenario README reports them.
- Markdown lint clean (`.markdownlint.json`): the inline SVG in
  `architecture_for_enerplanet.md` moved to
  `docs/figures/per_building_decomposition.svg`; over-long lines wrapped.

## [0.4.0] - 2026-11-10

### Fixed

- **Single-carrier conversion technologies no longer produce output for
  free.** The generated `additional_math.yaml` overrode Calliope's
  `balance_conversion` with a constraint listing only the multi-carrier
  technologies -- and a same-named math constraint *replaces* the base one,
  so every boiler and single-input chiller lost its conversion balance and
  could deliver heat/cooling with zero fuel or electricity input. Found on a
  real `calliope==0.7.0` solve of the Loenen scenario. `balance_conversion`
  now keeps Calliope's base summed balance for every other conversion
  technology, and the primary-carrier balance moved to its own
  `balance_conversion_primary_carriers` constraint. **Every Loenen result
  produced before this fix is invalid** (boiler fuel was never paid for).

### Changed

- **Every technical and economic parameter is now sourced.** The
  placeholder values in `new/technologies.csv` and `new/costs.csv` were
  replaced by values from the Danish Energy Agency technology catalogues
  (individual heating, April 2026; electricity and district heating, August
  2026), Heat Roadmap Europe D3.2 (cooling), RVO's ISDE heat pump list
  (household heat pump capacity ceilings), and the Dutch social discount
  rate (2.25 % real). Provenance for every value is in
  `docs/sources/parameter_sources.csv`, enforced by
  `tests/test_parameter_sources.py`; see `docs/parameter_sources.md`.
- **BREAKING: cost currency is now EUR (real 2025 prices, excluding VAT and
  taxes)**, previously USD. All sources publish in EUR.
- **BREAKING: `cost_flow_in` (fuel cost) is no longer set on any bundled
  technology.** Fuel and electricity are priced once, on the model's supply
  technology; the old values double-counted fuel wherever a supply
  technology also priced it.
- Boiler efficiency bound widened from 0.8-0.99 to 0.8-1.10 (net/LHV
  basis: condensing units exceed 1.0); reversible heat pump COP bound from
  1.5-5 to 1.5-8 (same vapour-compression ceiling as the electric chiller).

- **BREAKING: `weather-cop` now fetches weather data directly from the
  `weather` package instead of reading a pre-exported CSV.** `v0.3.0`'s
  `weather-cop --csv PATH --year YYYY [--temperature-column T]
  [--max-missing-fraction 0.0]` becomes `weather-cop --latitude LAT
  --longitude LON --year YYYY [--provider era5-land] [--data-dir PATH]`,
  calling `weather.get_point_weather()` (a real per-location fetch of an
  already-processed archive) directly. `weather` is now a **compulsory**
  runtime dependency (`pyproject.toml`, `infrastructure/env/
  conversion_env.yml`), matching how `UU-BUEM/buem` treats the same
  dependency -- `core/weather_series.py` (the CSV-reading module `v0.3.0`
  added) and its tests are removed entirely, no CSV path remains. See
  `docs/calliope_schema_mapping.md` "Weather-driven COP profiles".

### Added

- `docs/sources/`: `references.csv`, `parameter_sources.csv`, and the Dutch
  heat pump market database `rvo_isde_heat_pumps_2026-11.csv` (2,843 ISDE-
  eligible models: heat output, subsidy, refrigerant/GWP) plus a summary.
- `tools/rvo_heat_pumps_to_csv.py`: rebuilds the RVO database from RVO's
  monthly Excel release.

## [0.3.0] - 2026-07-28

### Fixed

- **Multi-carrier technologies (heat pump, CHP) now export the Calliope
  math a solve actually needs to respect their fixed carrier ratio.**
  Calliope's base `balance_conversion` constraint sums flow across carriers
  on each side rather than pinning them individually -- worked through with
  real numbers, the previous `flow_in_eff`/`flow_out_eff`-only export left
  a heat pump's COP-implied electricity/ambient-heat split unenforced, and
  made CHP's base balance double-count fuel input once both output
  carriers had a real efficiency. `export`/`export-all` now also write an
  `additional_math.yaml` (`calliope_export.ratio_math.build_ratio_math`,
  default on, `--no-custom-math` to skip) generalising the fix Calliope's
  own official CHP example uses. See `docs/calliope_schema_mapping.md`
  "Carrier ratio math" for the full derivation; not yet verified against a
  running Calliope solve.

### Added

- **`weather-cop` CLI command** (`new.heat_pump.weather_cop.
  export_weather_cop`): a real hourly heat pump COP from an actual weather
  temperature CSV, exported as Calliope `data_tables:` YAML -- separate
  from, and does not change, the registry's fixed design-point COP. New
  `core.weather_series` module reads/validates/aligns the hourly CSV
  (own lightweight reader, not a dependency on the `weather` package).
- Explicit units/currency/timestep convention (USD, kW, kWh, 1 hour) and
  the exact Calliope version this package's schema targets, both previously
  implicit -- see `docs/calliope_schema_mapping.md` "Units, currency, and
  Calliope version".

### Changed

- Added `pandas>=2.0,<3` as a dependency (for the `weather-cop` command's
  timeseries handling only -- the rest of the package is unaffected).

## [0.2.0] - 2026-07-27

### Removed

- **`legacy_v051` exporter deleted entirely** (`calliope_export/legacy_v051.py`,
  its registration in `calliope_export/__init__.py`, and all its tests) --
  only the current Calliope "flow" schema (`modern`) is supported now.
  `export`/`export-all --schema` no longer accept `legacy_v051`; the
  `--schema` flag still exists for forward compatibility (a future Calliope
  release could need a new exporter) but currently has one valid value.
- `technologies.ods` (an interim two-sheet spreadsheet draft) -- superseded
  by the two-CSV design described below before it was ever the primary
  input format.

### Fixed

- `core.csv_loader` now reads `technologies.csv`/`costs.csv` (and any
  `CONVERSION_TECH_PARAMS_DIR` override) with `utf-8-sig`, not `utf-8`. A
  UTF-8 BOM -- which Excel writes by default saving CSV on Windows, and
  which PowerShell's `Set-Content -Encoding utf8` also writes -- silently
  renamed the `category` header and broke every row lookup.
- Corrected a wrong Calliope cost parameter name: the CSV column and
  exported YAML key were `cost_flow_om_annual`, which does not exist in
  Calliope's schema. Confirmed against Calliope's math docs and renamed to
  the real key, `cost_om_annual`, everywhere (CSV header, docs). No
  exporter code change was needed -- the dynamic `params` passthrough
  picked up the renamed column automatically, which is the point of that
  design.

### Changed

- **Input is now two linked CSVs**, `new/technologies.csv` (identity,
  capacity, lifetime, efficiency/COP/dispatch-factor inputs) and
  `new/costs.csv` (every `cost_*` value), joined by
  `(category, variant, scale)` -- replaces the three per-category
  `data/defaults.json` files (deleted). One row per technology + scale per
  file, spreadsheet-editable (Excel, LibreOffice Calc, or any text editor);
  blank cells mean "not applicable to this row." The 7 per-variant
  `specific/*.py` files (e.g. `electric_boiler.py`, `gas_chp.py`) were
  replaced by 3 category `specific/__init__.py` files that build
  `TechnologySpec`s directly from the joined rows. A `costs.csv` row with
  no matching `technologies.csv` row (e.g. a typo in `variant`) now raises
  `ValueError` at load time instead of being silently dropped.
- Env var renamed `CONVERSION_TECH_PARAMS_FILE` -> `CONVERSION_TECH_PARAMS_DIR`
  to reflect that it now points at a *directory* containing both
  `technologies.csv` and `costs.csv`, not a single file. Use your own values
  without touching the package: point it at a directory holding your own
  copies of both files before running the CLI (replaces the whole pair for
  that run; must be set before the process starts, since technologies
  register at import time).
- **CSV columns pass straight through to `modern` output, by name, with no
  code changes.** `TechnologySpec` now only names the fields every
  technology always has (`flow_cap_max`, `lifetime`, `cost_flow_cap`, plus
  identity/carrier fields); everything else (`flow_cap_min`,
  `cost_om_annual`, `cost_flow_in`, `cost_flow_out`, `cost_interest_rate`,
  `flow_ramping`, and any future parameter) lives in a new
  `TechnologySpec.params: dict[str, float]`, populated generically by
  `core.csv_loader.passthrough_params()`. `modern.py` iterates `params`
  instead of hardcoding one `if tech.<field> is not None: ...` line per
  parameter -- add a CSV column, or rename one to track a future Calliope
  release, and no Python changes anywhere.
- Heat pump `technologies.csv` column `carnot_efficiency` renamed to
  `efficiency` (same column name boiler already uses for its nameplate
  efficiency). It's still the Carnot quality factor (0-1), not the COP --
  see `docs/calliope_schema_mapping.md` "Heat pump efficiency".

### Added

- `export-all --category` (aliases `hp`/`boiler`/`chp`) and `list --category`,
  filtering by `TechnologySpec.category`.
- `export-all --config path.json`, consuming `config.ExportConfig`/
  `load_export_config` (previously unwired) for an exact `technology_ids` +
  `schema` + `output_dir` scenario.
- `export-all -o name.yaml` combines every matched technology into one
  `techs:` document (`calliope_export.writer.write_techs_yaml`); `-o dir/`
  still writes one file per technology. Decided by the output path's suffix.
- `TechnologySpec.variant` (e.g. `"electric"`, `"geothermal"`, `"gas"`,
  `"biomass"`) plus `--variant` (matches `variant`, case-insensitive) and
  `--scale` filters on `list`/`export-all`, combinable with `--category` --
  e.g. `export-all --category hp --variant electric` for every scale of the
  air-source electric heat pump.
- **Validation now lives in source, not just tests.** New
  `core/validation.py` with reusable checkers
  (`require_range`, `require_positive_costs`, `require_scale_capacity`),
  called from `TechnologySpec.__post_init__` for bounds every technology
  shares (`0 < lifetime < 50`, `0 < cost_flow_cap < inf`,
  `0 < cost_interest_rate < 0.4`, every `cost_*` value `> 0`) and from each
  category's `specific/__init__.py` for technology-specific bounds:
  `0.8 <= boiler.efficiency <= 0.99`; heat pump `0 < efficiency <= 1`
  (Carnot quality factor) *and* `1 <= cop <= 20` (the derived COP, checked
  separately since a quality factor near 1 at a small source/sink gap can
  still produce an unrealistic COP); CHP dispatch factors unchanged
  (already validated). Tests now only assert that out-of-range input raises
  `ValueError` -- they no longer define the bound themselves.
- Per-scale capacity ceilings (`core.validation.DEFAULT_CAPACITY_CEILINGS_KW`
  -- household 100 kW / building 2,000 kW / community 50,000 kW), enforced
  on `flow_cap_max` in all three categories' `specific/__init__.py` via
  `require_scale_capacity`. These are deliberately generous, typo-catching
  sanity bounds shared across categories, not literal engineering limits --
  see `.claude/resolved.md` "validation-in-source" for why household is
  100 kW rather than the 5,000 kW originally suggested (5,000 kW is
  utility-scale, not household-scale; using it as the household ceiling
  would defeat the point of a sanity check).

## [0.1.0] - 2026-07-27

### Fixed

- `.gitignore`'s unanchored `env/` and `data/` patterns matched at any
  depth, silently excluding `infrastructure/env/conversion_env.yml` (broke
  CI) and every `new/*/data/defaults.json` plus
  `config/data/default_scenario.json` (broke the package itself -- these
  are read via `importlib.resources` at import time). Anchored both to the
  repo root.

### Changed

- Heat pump `carnot_cop` now accepts a scalar or an array of source
  temperatures directly (e.g. a real hourly `T` series from the weather
  module), replacing the separate `seasonal_cop_curve` function.
- CHP technologies are now specified via energy-hub dispatch factors
  `alpha` (electrical efficiency) and `beta` (thermal efficiency) instead
  of `total_efficiency` + `power_to_heat_ratio` (mathematically
  equivalent, standard energy-hub notation).

### Added

- Initial package scaffold: `TechnologySpec` internal model, registry, and
  dual Calliope exporters (`legacy_v051`, `modern`).
- Boiler technologies: electric, natural gas, biomass — household/building/community scale.
- Heat pump technologies: air-source electric, ground-source geothermal — with
  a shared Carnot-based COP calculation.
- Combined heat and power technologies: natural gas, biomass — with a shared
  power-to-heat efficiency split.
- CLI (`conversion-technologies`): `info`, `list`, `export`, `export-all`.
- Packaging, Docker/Apptainer container, conda environment (`conversion_env`),
  and CI/CD matching the `weather`/`occupancy` sibling packages.
