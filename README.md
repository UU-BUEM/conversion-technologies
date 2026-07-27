# conversion-technologies

[![CI](https://github.com/UU-BUEM/conversion-technologies/actions/workflows/ci.yml/badge.svg)](https://github.com/UU-BUEM/conversion-technologies/actions/workflows/ci.yml)

Calliope-compatible technology YAML configs for heat-producing energy
conversion technologies — heat pumps, boilers, and combined heat and power
(CHP) — from a single household up to a community scale.

Part of the `UU-BUEM` sibling package family, alongside
[`weather`](https://github.com/UU-BUEM/weather) and
[`occupancy`](https://github.com/UU-BUEM/occupancy).

## What this does

Each technology (e.g. "air-source electric heat pump, building scale") is
defined once as a version-agnostic `TechnologySpec` — carriers in/out,
capacity, efficiency, cost, lifetime — and exported to a Calliope technology
YAML file. Two Calliope schemas are supported:

- `modern` (default): current Calliope, `base_tech: conversion`, `flow_*` naming.
- `legacy_v051`: [Calliope v0.5.1](https://calliope.readthedocs.io/en/v0.5.1/user/configuration_reference.html#abstract-base-technologies), `parent: conversion_plus`.

See [`docs/calliope_schema_mapping.md`](docs/calliope_schema_mapping.md) for
the full attribute mapping and known limitations.

## Quickstart

```powershell
.\setup.ps1                      # creates the conversion_env conda environment
conversion-technologies info
conversion-technologies list
conversion-technologies export heat_pump_electric_household -o outputs/hp.yaml
conversion-technologies export-all --schema legacy_v051 -o outputs/
```

## Repository layout

```text
src/conversion_technologies/
├── core/               # TechnologySpec, carrier constants, registry
├── calliope_export/    # legacy_v051 and modern YAML exporters
├── config/             # batch export scenario config
├── new/                # candidate technologies (this package's focus)
│   ├── boiler/{generic,specific,data}
│   ├── heat_pump/{generic,specific,data}
│   └── combined_heat_and_power/{generic,specific,data}
└── existing/            # out of scope: bottom-up simulation of incumbent stock (e.g. fireplace.py)
```

## Adding a new technology

1. Add default parameters (capacity, cost, efficiency, per scale) to the
   category's `data/defaults.json`.
2. Write a `specific/<name>.py` module that builds a `TechnologySpec` per
   scale and calls `register_technology(...)`.
3. Import that module from the category's `specific/__init__.py`.

No changes are needed anywhere else — the CLI and both exporters work off
the registry automatically.

## Docker

```powershell
docker compose -f infrastructure/container/docker-compose.yml build
docker compose -f infrastructure/container/docker-compose.yml run conversion-technologies
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CONVERSION_TECH_OUTPUT_DIR` | `outputs/` | Default directory for `export`/`export-all` output. |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development workflow and
[`CLAUDE.md`](CLAUDE.md) for the architecture/agent-context reference.
