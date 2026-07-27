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
