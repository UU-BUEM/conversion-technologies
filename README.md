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
conversion-technologies list                                  # every registered technology
conversion-technologies list --category hp                    # aliases: hp, boiler, chp

# one technology -> one file
conversion-technologies export heat_pump_electric_household -o outputs/hp.yaml

# a whole category -> one combined file (path ends in .yaml/.yml)
conversion-technologies export-all --category hp -o outputs/heat_pump.yaml

# everything -> one file per technology (path is a directory)
conversion-technologies export-all --schema legacy_v051 -o outputs/

# an exact list of technologies + schema + output, from a JSON scenario file
conversion-technologies export-all --config my_scenario.json
```

`--technology_id` (singular `export`) always takes an exact registry ID
(`conversion-technologies list` to see them); `--category` (plural
`export-all`) takes `hp`/`boiler`/`chp` and matches every scale. See
"Input, output, and getting results" below for the full picture.

## Input, output, and getting results

**Input** is not a file you author from scratch — every technology already
has a default configuration bundled with the package:
`src/conversion_technologies/new/<category>/data/defaults.json` holds one
entry per technology *and* per deployment scale (`household`/`building`/
`community`): capacity, cost, lifetime, and efficiency/COP parameters. A
`specific/<name>.py` module reads its entry and builds a `TechnologySpec`,
registered under an id like `heat_pump_electric_household`.
`conversion-technologies list` shows every registered id with its category,
scale, and capacity.

If you want to run a *specific, named export* (rather than one technology
or "everything"), write a small JSON scenario file and pass `--config`:

```json
{
  "technology_ids": ["heat_pump_electric_household", "boiler_gas_building"],
  "schema": "modern",
  "output_dir": "outputs/my_scenario"
}
```

(see `src/conversion_technologies/config/data/default_scenario.json` for the
full shape — an empty `technology_ids` list means "everything").

**Output** is Calliope-ready YAML, written to disk by the CLI. Three ways to
get it, depending on how much you want in one file:

| Want | Command |
| --- | --- |
| One technology | `conversion-technologies export <technology_id> -o path.yaml` |
| One category, one file | `conversion-technologies export-all --category hp -o heat_pump.yaml` |
| One category, one file per tech | `conversion-technologies export-all --category hp -o some_dir/` |
| Everything, or an exact scenario | `conversion-technologies export-all [--config scenario.json]` |

Whether `-o`/`--output` produces one combined file or one file per
technology is decided by its suffix: `.yaml`/`.yml` combines everything
matched into a single `techs:` document; anything else is treated as a
directory (created if missing) with one `<id>.yaml` file per technology.

If you don't need a file on disk at all (e.g. you're scripting further
processing in Python), skip the CLI and call the library directly:

```python
from conversion_technologies import new  # noqa: F401  (registers technologies)
from conversion_technologies.calliope_export import EXPORTERS
from conversion_technologies.core.registry import get_technology

tech = get_technology("heat_pump_electric_household")
body = EXPORTERS["modern"].export(tech)  # a plain dict, no YAML/file involved
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
| --- | --- | --- |
| `CONVERSION_TECH_OUTPUT_DIR` | `outputs/` | Default directory for `export`/`export-all` output. |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development workflow and
[`CLAUDE.md`](CLAUDE.md) for the architecture/agent-context reference.
