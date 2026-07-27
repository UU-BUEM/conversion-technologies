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
│   ├── technology.py     # TechnologySpec: the version-agnostic tech model
│   ├── carriers.py       # carrier name constants (electricity, heat, ambient_heat, ...)
│   ├── registry.py       # register_technology() / get_technology() / all_technologies()
│   └── data_loader.py    # importlib.resources JSON loader
├── calliope_export/
│   ├── legacy_v051.py    # -> conversion_plus (Calliope v0.5.1)
│   ├── modern.py         # -> conversion, flow_* naming (current Calliope)
│   └── writer.py         # ruamel.yaml dump to a standalone `techs:` file
├── config/               # ExportConfig: which techs / schema / output dir for a batch run
├── new/                  # candidate technologies -- THIS package's focus
│   ├── boiler/{generic,specific,data}
│   ├── heat_pump/{generic,specific,data}
│   └── combined_heat_and_power/{generic,specific,data}
├── existing/             # OUT OF SCOPE: fireplace.py, a bottom-up occupancy+weather
│                         #   driven simulation of already-installed stock. Different
│                         #   modeling paradigm; do not fold this into new/'s pattern
│                         #   without an explicit decision to do so (see .claude/resolved.md).
├── cli.py, __main__.py, __init__.py, settings.py
```

## Data flow

`specific/*.py` builder (reads `data/defaults.json`, optionally a `generic/*.py`
formula) → `TechnologySpec` → `registry` → `calliope_export.{legacy_v051,modern}.export()`
→ `calliope_export.writer.write_technology_yaml()` → one YAML file per technology.

## Extension points

Adding a technology = 3 steps, nothing else changes:

1. Add its default capacity/cost/lifetime/efficiency (per scale: `household`,
   `building`, `community`) to the category's `data/defaults.json`.
2. Write `new/<category>/specific/<name>.py`: a `_build(scale)` function
   returning a `TechnologySpec`, registered per scale via
   `register_technology(f"<id>_{scale}", partial(_build, scale))`.
3. Import that module from `new/<category>/specific/__init__.py`.

Shared math (COP curves, efficiency derating, power-to-heat splits) goes in
`new/<category>/generic/`, never duplicated across `specific/` modules.

## Hard conventions (do not violate)

1. **No hardcoded numeric defaults in Python.** Capacity/cost/efficiency
   live in `data/*.json`, loaded via `core.data_loader.load_json_resource`.
2. **`TechnologySpec` is the only source of truth.** Exporters translate
   field names/shapes per Calliope schema; they never invent data.
3. **Registry pattern for extensibility** — no `if/elif` chains dispatching
   on technology name anywhere.
4. **Dual schema support is intentional**, not a placeholder — see
   `docs/calliope_schema_mapping.md` for why (Calliope's schema changed
   substantially between v0.5.1 and current; chasing every release would be
   fragile, so the internal model stays version-agnostic).
5. `from __future__ import annotations` + dataclasses (no pydantic) + `pathlib`, matching siblings.
6. src-layout + setuptools-scm; never hand-edit `src/conversion_technologies/_version.py`.

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
