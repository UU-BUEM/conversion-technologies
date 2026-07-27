# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
