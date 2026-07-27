# conversion-technologies — agent context

## What this repo is

Generates Calliope-compatible technology YAML configs for heat-producing
energy conversion technologies — heat pumps, boilers, combined heat and
power (CHP) — from household to community scale. Sibling to `UU-BUEM/weather`
and `UU-BUEM/occupancy` (same packaging/tooling conventions).

Feeds into a [Calliope](https://github.com/calliope-project/calliope) energy
system model as per-technology YAML files under a `techs:` key.

## Operating rules for Claude Code

- **Load only what's relevant.** This file is always loaded; `.claude/<category>/{open,resolved}.md`
  is loaded only when working on that category (`boiler`, `heat_pump`, `combined_heat_and_power`).
  Check `resolved.md` before proposing a change — it lists decisions already made, "do not re-raise."
- **Keep docs current in the same commit** as the code change they describe.
- **Summarize file changes** at the end of each turn (or state "No files were updated").

## Repository layout

```text
src/conversion_technologies/
├── core/
│   ├── technology.py     # TechnologySpec: the version-agnostic tech model;
│   │                     #   __post_init__ enforces common bounds
│   ├── carriers.py       # carrier name constants (electricity, heat, ambient_heat, ...)
│   ├── registry.py       # register_technology() / get_technology() / all_technologies()
│   ├── validation.py     # require_range() / require_positive_costs() /
│   │                     #   require_scale_capacity() -- called from source, not tests
│   ├── csv_loader.py     # load_technology_rows() (reads technologies.csv +
│   │                     #   costs.csv, joined, or the CONVERSION_TECH_PARAMS_DIR
│   │                     #   override; blanks -> None) + passthrough_params()
│   │                     #   (row -> TechnologySpec.params)
│   └── data_loader.py    # importlib.resources JSON loader (used by config/ only)
├── calliope_export/
│   ├── modern.py          # -> conversion, flow_* naming (current Calliope; the
│   │                      #   only exporter -- legacy_v051 was removed, see
│   │                      #   .claude/resolved.md)
│   └── writer.py          # ruamel.yaml dump: one tech or several combined into one `techs:` file
├── config/                # ExportConfig: which techs / schema / output dir for a batch run
├── new/                   # candidate technologies -- THIS package's focus
│   ├── technologies.csv    # capacity/lifetime/efficiency/COP inputs -- THE input file
│   ├── costs.csv             # every cost_* column, joined to technologies.csv by key
│   ├── boiler/{generic,specific}
│   ├── heat_pump/{generic,specific}
│   └── combined_heat_and_power/{generic,specific}
├── existing/              # OUT OF SCOPE: fireplace.py, a bottom-up occupancy+weather
│                          #   driven simulation of already-installed stock. Different
│                          #   modeling paradigm; do not fold this into new/'s pattern
│                          #   without an explicit decision to do so (see .claude/resolved.md).
├── cli.py, __main__.py, __init__.py, settings.py
```

## Data flow

`technologies.csv` row (joined with its `costs.csv` row) →
`new/<category>/specific/__init__.py`'s `_build(row)` (applies a
`generic/*.py` formula if the category has one, e.g. COP; validates
technology-specific bounds via `core.validation`) → `TechnologySpec`
(validates common bounds in `__post_init__`) → `registry` →
`calliope_export.modern.export()` → `calliope_export.writer.write_techs_yaml()`
→ YAML file(s).

## Extension points

**A new variant of a carrier that already has a constant in `core/carriers.py`**
(e.g. a hydrogen boiler) needs a `technologies.csv` + `costs.csv` row,
nothing else — see the docstring at the top of `core/csv_loader.py` and the
category `specific/__init__.py` files for the exact columns each category
reads.

**A new Calliope parameter** (a cost/constraint not modeled yet): add a
column (to `costs.csv` if it's a `cost_*` parameter, `technologies.csv`
otherwise) under the exact name current Calliope uses -- `modern.py` needs
no change, it passes every `TechnologySpec.params` entry through under its
own key already (see "Hard conventions" #7 below).

**A genuinely new category** (different carrier topology/formula):

1. Add its rows to `technologies.csv` + `costs.csv` (new `category` value,
   whatever columns it needs -- blank cells elsewhere are fine).
2. Write `new/<category>/specific/__init__.py`: filter CSV rows for that
   category, validate technology-specific bounds via `core.validation`
   (see the three existing files for the pattern -- each is ~60-80 lines),
   build a `TechnologySpec` per row. Pass every column not consumed by a
   formula through `core.csv_loader.passthrough_params(row,
   formula_columns=...)` into `TechnologySpec.params`.
3. Shared math (COP curves, efficiency derating, dispatch-factor splits)
   goes in `new/<category>/generic/`, never duplicated per variant.
4. Import the category package from `new/__init__.py`.

## Hard conventions (do not violate)

1. **No hardcoded numeric defaults in Python.** Every technology's fixed
   parameters live in `new/technologies.csv` + `new/costs.csv`, loaded via
   `core.csv_loader.load_technology_rows`. Python only does *derivations*
   (final COP from design temps + quality factor, CHP alpha/beta
   validation) -- never invents or hardcodes a parameter value itself.
2. **`TechnologySpec` is the only source of truth.** The exporter
   translates field names/shapes to Calliope's schema; it never invents data.
3. **Registry pattern for extensibility** — no `if/elif` chains dispatching
   on technology name anywhere.
4. **Validation lives in source, not tests.** Common engineering bounds
   (lifetime, cost_flow_cap, cost_interest_rate, every populated cost > 0)
   are enforced in `TechnologySpec.__post_init__`; technology-specific
   bounds (boiler efficiency, heat pump quality factor + computed COP,
   per-scale capacity ceilings, CHP dispatch factors) are enforced by each
   category's `specific/__init__.py` before it constructs a
   `TechnologySpec`. Tests check that bad input is *rejected*
   (`pytest.raises(ValueError)`); they must never be the only place a bound
   is enforced -- if you're about to write an `assert` on a bound in a
   test, the check belongs in source first.
5. `from __future__ import annotations` + dataclasses (no pydantic) + `pathlib`, matching siblings.
6. src-layout + setuptools-scm; never hand-edit `src/conversion_technologies/_version.py`.
7. **CSV column names ARE `modern` exporter output keys, dynamically.**
   Only `TechnologySpec`'s always-required fields (`flow_cap_max`,
   `lifetime`, `cost_flow_cap`) and structural columns (category/variant/
   scale/name/color/carrier_in/carrier_in_2) are named explicitly anywhere.
   Everything else lives in `TechnologySpec.params` and `modern.py` emits
   it by iterating that dict -- **never add a new `if tech.<field> is not
   None: body["..."] = ...` line to `modern.py`**; if you find yourself
   about to, the value belongs in `params` instead.

## Dev commands

```powershell
ruff format .
ruff check src/ tests/
mypy src
pytest
python validate.py
```

## Known limitations / follow-ups

See `.claude/open.md` (cross-cutting) and `.claude/<category>/open.md`
(per-category). Notably: the `modern` exporter's per-carrier
`flow_in_eff`/`flow_out_eff` approach covers every technology currently in
this package (fixed linear ratios), but genuinely alternative/either-or
carrier choices would need hand-written Calliope "user-defined math" — not
implemented here, flagged in `docs/calliope_schema_mapping.md`.
