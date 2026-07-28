# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
