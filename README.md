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
capacity, efficiency, cost, lifetime — and exported to current-Calliope
(`base_tech: conversion`, `flow_*` naming) technology YAML. Engineering
bounds (lifetime, cost sanity checks, boiler efficiency, heat pump COP,
per-scale capacity ceilings, ...) are enforced when a technology is built,
not left to be caught by tests — an out-of-range value in the input CSVs
raises a clear error immediately.

See [`docs/calliope_schema_mapping.md`](docs/calliope_schema_mapping.md) for
the full attribute mapping and known limitations.

## Quickstart

```powershell
.\setup.ps1                      # creates the conversion_env conda environment
conversion-technologies info
conversion-technologies list                                       # every registered technology
conversion-technologies list --category hp                         # aliases: hp, boiler, chp
conversion-technologies list --category hp --variant electric      # electric only, all scales
conversion-technologies list --scale household                     # any category, household scale only

# one technology -> one file
conversion-technologies export heat_pump_electric_household -o outputs/hp.yaml

# only electric heat pumps (all scales) -> one combined file
conversion-technologies export-all --category hp --variant electric -o outputs/heat_pump_electric.yaml

# a whole category -> one combined file (path ends in .yaml/.yml)
conversion-technologies export-all --category hp -o outputs/heat_pump.yaml

# everything -> one file per technology (path is a directory)
conversion-technologies export-all -o outputs/

# an exact list of technologies + schema + output, from a JSON scenario file
conversion-technologies export-all --config my_scenario.json
```

`export`'s `technology_id` is always an exact registry ID
(`conversion-technologies list` to see them). `export-all`'s three filters
combine with AND and are all optional: `--category` (`hp`/`boiler`/`chp`),
`--variant` (the specific variant within a category, e.g. `electric`/
`geothermal`/`gas`/`biomass`), and `--scale` (`household`/`building`/
`community`). `--category hp --variant electric` = every scale of the
air-source electric heat pump; add `--scale household` to narrow to exactly
one technology. See "Input, output, and getting results" below for the full
picture.

## Input, output, and getting results

**Input is two spreadsheets**, one row per technology *and* deployment scale
(household/building/community):

- [`new/technologies.csv`](src/conversion_technologies/new/technologies.csv) --
  capacity, lifetime, and efficiency/COP/dispatch-factor inputs.
- [`new/costs.csv`](src/conversion_technologies/new/costs.csv) -- every
  `cost_*` column, joined back to `technologies.csv` by
  `(category, variant, scale)`. Split out on request, so the cost picture
  for a technology can be reviewed/edited on its own without scrolling past
  every technical column.

Open either in Excel or any text editor; blank cells mean "not applicable to
this technology" (e.g. `alpha`/`beta` are blank for every boiler row). No
Python or JSON editing needed to change a number. **Editing in LibreOffice
Calc**: it will prompt "Use CSV format!" on save -- click it. That warning
exists because CSV can't hold multiple sheets/formulas/formatting, none of
which these files use, so nothing is lost.

**Cost columns, plainly** (see `docs/calliope_schema_mapping.md` for the
full reference):

| Column | Meaning | Units |
| --- | --- | --- |
| `cost_flow_cap` | Investment cost | currency / kW installed |
| `cost_om_annual` | Fixed O&M cost | currency / kW / year, regardless of use |
| `cost_flow_in` | Variable cost per unit *consumed* (e.g. fuel price) | currency / kWh in |
| `cost_flow_out` | Variable cost per unit *produced* (e.g. output-linked maintenance) | currency / kWh out |
| `cost_interest_rate` | Discount rate for cost annualisation -- not a currency cost | fraction, e.g. `0.10` |

**You don't need to touch the package to use your own values.** Copy both
CSVs into one folder, edit them, and point the package at that folder:

```powershell
$env:CONVERSION_TECH_PARAMS_DIR = "C:\path\to\my_params"
conversion-technologies list
```

Both files must keep the same columns; this replaces the *whole* pair for
that run, it does not merge cell-by-cell with the bundled defaults. This
has to be set before the CLI runs (technologies are registered once, at
import time), so an env var -- not a `--params` flag -- is how it's wired.

Each category's `new/<category>/specific/__init__.py` reads its own rows
and builds a `TechnologySpec`, registered under an id like
`heat_pump_electric_household` -- **validating engineering bounds as it
does** (an out-of-range CSV value raises `ValueError` immediately, it does
not silently register a bad technology). `conversion-technologies list`
shows every registered id with its category, scale, and capacity; every
`TechnologySpec` also carries `category` (`heat_pump`), `variant`
(`electric`/`geothermal`/`gas`/`biomass` — the `--variant` filter matches
this) and `scale`, which is how `--category`/`--variant`/`--scale` narrow
things down without needing to know exact IDs.

**Column names are not hardcoded in the exporter.** Every column that isn't
part of a technology's identity (`category`/`variant`/`scale`/`name`/
`color`/`carrier_in`) or fed into a category's own formula (see below) is
carried through to the YAML output under its *exact column name*, with no
per-field code anywhere. Add a column, and it shows up in the output
automatically; rename a column to track a future Calliope release, and the
output key renames itself -- nothing in `modern.py` or any builder needs to
change.

The one thing the CSV can't express is a *transformation* — e.g. a heat
pump's actual/final COP isn't a fixed number, it's computed from the design
temperatures and quality factor you provide:
`final_cop = efficiency * T_sink_K / (T_sink_K - T_source_K)`, where
`efficiency` is the Carnot quality/2nd-law factor (0-1, shares its column
name with boiler's plain thermal efficiency -- see
`docs/calliope_schema_mapping.md` "Heat pump efficiency") and `T_source` is
the CSV's `design_source_temp_c` (a fixed design point today;
`new/heat_pump/generic/cop_calculation.py`'s `carnot_cop` also accepts a real
hourly temperature array — e.g. the weather module's harmonised `T` column,
originally COSMO-REA6's `T_2M`/ERA5-Land's `t2m`/MERRA-2's `T2M` — for anyone
who wants a real seasonal COP rather than one design point). That kind of
*calculation and its bounds-checking* stays in Python
(`new/<category>/specific/__init__.py` + `new/<category>/generic/`); the
*inputs* to it live entirely in the CSV.

If you want to run a *specific, named export* (rather than a filtered set
or "everything"), write a small JSON scenario file and pass `--config`:

```json
{
  "technology_ids": ["heat_pump_electric_household", "boiler_gas_building"],
  "schema": "modern",
  "output_dir": "outputs/my_scenario"
}
```

(see `src/conversion_technologies/config/data/default_scenario.json` for the
full shape — an empty `technology_ids` list means "everything". Its
`technology_ids`, if non-empty, overrides `--category`/`--variant`/`--scale`.)

**Output** is Calliope-ready YAML, written to disk by the CLI. A few ways to
get it, depending on how much you want in one file:

| Want | Command |
| --- | --- |
| One technology | `conversion-technologies export <technology_id> -o path.yaml` |
| One variant, one file, all scales | `conversion-technologies export-all --category hp --variant electric -o heat_pump_electric.yaml` |
| One category, one file | `conversion-technologies export-all --category hp -o heat_pump.yaml` |
| One category, one file per tech | `conversion-technologies export-all --category hp -o some_dir/` |
| Everything, or an exact scenario | `conversion-technologies export-all [--config scenario.json]` |

Whether `-o`/`--output` produces one combined file or one file per
technology is decided by its suffix: `.yaml`/`.yml` combines everything
matched into a single `techs:` document; anything else is treated as a
directory (created if missing) with one `<id>.yaml` file per technology.
If a filter combination matches nothing, the CLI exits with status 1 and
prints the `--variant` values that *do* exist for the given `--category`.

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
├── core/                 # TechnologySpec, carrier constants, registry,
│                         #   CSV loader, engineering-bound validation
├── calliope_export/      # modern (current Calliope) YAML exporter
├── config/               # batch export scenario config
├── new/                  # candidate technologies (this package's focus)
│   ├── technologies.csv   # capacity/lifetime/efficiency/COP inputs -- THE input file
│   ├── costs.csv           # every cost_* column, joined to technologies.csv by key
│   ├── boiler/{generic,specific}
│   ├── heat_pump/{generic,specific}
│   └── combined_heat_and_power/{generic,specific}
└── existing/              # out of scope: bottom-up simulation of incumbent stock (e.g. fireplace.py)
```

## Adding a new technology (or a new parameter)

**A new variant of a carrier that already has a constant in `core/carriers.py`**
(e.g. a hydrogen boiler, since `HYDROGEN` already exists) needs **no Python
at all** — add one row per scale to `technologies.csv` (+ `costs.csv`) with
the new `variant` name and the right `carrier_in`.

**A new Calliope parameter** (a cost or constraint this package doesn't
have yet) also needs **no Python** — add a column under the exact name
current Calliope expects (to `costs.csv` if it's a `cost_*` parameter,
`technologies.csv` otherwise), fill it in for the rows it applies to, leave
it blank elsewhere. It appears in the exported YAML automatically.

**A genuinely new category** (different carrier topology or formula, e.g.
a solar thermal collector):

1. Add its rows to `technologies.csv` (new `category` value).
2. Write `new/<category>/specific/__init__.py`: filter the CSV rows for
   that category and build a `TechnologySpec` per row (see the existing
   three category `__init__.py` files for the pattern).
3. If it needs its own formula (like heat pump COP or CHP dispatch
   factors), add it to `new/<category>/generic/`.
4. Import the category package from `new/__init__.py`.

No changes are needed anywhere else — the CLI and exporter work off the
registry automatically.

## Docker

```powershell
docker compose -f infrastructure/container/docker-compose.yml build
docker compose -f infrastructure/container/docker-compose.yml run conversion-technologies
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CONVERSION_TECH_OUTPUT_DIR` | `outputs/` | Default directory for `export`/`export-all` output. |
| `CONVERSION_TECH_PARAMS_DIR` | *(bundled CSVs)* | Absolute path to a folder with your own `technologies.csv` + `costs.csv`, replacing the bundled defaults entirely. Must be set before the CLI runs. |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development workflow and
[`CLAUDE.md`](CLAUDE.md) for the architecture/agent-context reference.
