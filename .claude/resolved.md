# Resolved / BY-DESIGN (cross-cutting)

- [calliope-version] BY-DESIGN: keep the internal `TechnologySpec` model
  version-agnostic and export via two schema modules (`legacy_v051`,
  `modern`) rather than targeting one Calliope release. Reason: Calliope
  renamed nearly every technology attribute and removed `conversion_plus`
  between v0.5.1 (the docs the user linked) and the current release; chasing
  each release inside every technology definition would be fragile. Adding a
  third schema means adding one exporter module, not touching any technology.
- [existing-vs-new] BY-DESIGN: `existing/fireplace.py` (bottom-up,
  occupancy+weather-driven simulation of already-installed stock) is a
  different modeling paradigm from `new/`'s top-down Calliope tech-config
  generation and is out of scope for this package's initial build. Do not
  merge the two patterns without an explicit decision to do so.
- [cop-placement] BY-DESIGN: COP calculation (`cop_calculation.py`) lives
  under `new/heat_pump/generic/`, not `new/boiler/generic/` where an empty
  placeholder file originally existed in the hand-sketched skeleton — COP is
  a heat-pump-specific concept. The original stray file was removed.
- [tests-location] BY-DESIGN: tests live at root `tests/`, not
  `src/conversion_technologies/tests/`. Reason: `weather`'s in-package tests/
  folder mixes real pytest unit tests with CLI-runner scripts named
  `test_*.py`, which its own `tests/README.md` has to disambiguate — avoided
  here by following `occupancy`'s root-level convention instead.
- [dependencies] BY-DESIGN: `ruamel.yaml` was added (not in `weather`/`occupancy`)
  because comment-preserving, readable YAML output is this package's actual
  deliverable. No pydantic — dataclasses match sibling convention.
- [cli-category-filter] `--category` (aliases `hp`/`boiler`/`chp`) added to
  `list` and `export-all`; `export-all`'s `--config path.json` now consumes
  `ExportConfig` (its `technology_ids` overrides `--category` if both given).
  `export-all -o <dir>/` still writes one file per technology; `-o
  name.yaml` combines every matched technology into a single `techs:`
  document via `calliope_export.writer.write_techs_yaml` — decided by the
  output path's suffix, not a separate flag.
- [repo] Pushed to `github.com/UU-BUEM/conversion-technologies` (public,
  `main` branch). The first CI run failed in 8s because `.gitignore`'s
  unanchored `env/`/`data/` patterns had silently excluded
  `infrastructure/env/conversion_env.yml` and every `data/defaults.json` --
  fixed and re-pushed (see CHANGELOG "Fixed"); check `gh run list --repo
  UU-BUEM/conversion-technologies` if a future push mysteriously fails fast
  again, since an unanchored gitignore pattern is an easy repeat mistake
  when adding a new nested `data/` or `env/` directory.
