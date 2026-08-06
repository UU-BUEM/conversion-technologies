# Resolved / BY-DESIGN (cross-cutting)

- [calliope-version] SUPERSEDED: originally kept the internal
  `TechnologySpec` model version-agnostic and exported via two schema
  modules (`legacy_v051`, `modern`), to hedge against not knowing which
  Calliope release was actually in use. Once it was clear only current
  Calliope was in use, `legacy_v051.py` was removed entirely (its tests,
  the `--schema legacy_v051` CLI choice, and the dual-schema doc sections
  all went with it) — see [legacy-v051-removed] below. The internal model
  stayed version-agnostic regardless (that part of the reasoning didn't
  change), so a second exporter is still just one new module away.
- [legacy-v051-removed] Removed `calliope_export/legacy_v051.py` and
  everything referencing it (tests, CLI `--schema` choice, dual-schema
  sections of `CLAUDE.md`/`docs/calliope_schema_mapping.md`). If a v0.5.1
  need ever comes back, `git log` has the original implementation to
  resurrect rather than rewrite from scratch.
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
- [validation-in-source] BY-DESIGN: engineering-bound validation (lifetime,
  cost sanity, boiler efficiency, heat pump COP, per-scale capacity
  ceilings, CHP dispatch factors) lives in `core/validation.py` +
  `TechnologySpec.__post_init__` + each category's `specific/__init__.py`
  -- **not in `tests/`**. Reason (explicit user correction): tests must
  check that bad input is rejected, they must never be the sole place a
  bound is enforced. `core/validation.py` provides `require_range`,
  `require_positive_costs`, `require_scale_capacity` -- generic, reusable
  across categories. Common bounds (every technology): `0 < lifetime < 50`,
  `cost_flow_cap > 0`, `0 < cost_interest_rate < 0.4` (only checked if
  present -- it's optional), every populated `params` key starting with
  `cost_` (except `cost_interest_rate`) must be `> 0`. Technology-specific:
  boiler `0.8 <= efficiency <= 0.99`; heat pump `efficiency` (quality
  factor) `0 < efficiency <= 1` and the *computed* COP `1 <= cop <= 20`
  (see [heat-pump-efficiency-rename] below); CHP `alpha`/`beta` via the
  pre-existing `validate_dispatch_factors`. Per-scale capacity ceilings
  (`DEFAULT_CAPACITY_CEILINGS_KW` in `core/validation.py`: household 100
  kW, building 2,000 kW, community 50,000 kW) apply to all three
  categories -- deliberately generous sanity bounds to catch a data-entry
  typo (a stray digit), not tight engineering limits; a real household
  heat pump is 3-20 kW, the 100 kW ceiling is ~5x that on purpose. The
  user's own example ("household HP shouldn't exceed 5000 kW") was
  intentionally not used literally -- 5000 kW is far too large even as a
  sanity ceiling for a single dwelling; flagged rather than silently
  applied, see CHANGELOG.
- [heat-pump-efficiency-rename] BY-DESIGN: `technologies.csv`'s heat pump
  `carnot_efficiency` column was renamed to `efficiency`, sharing its name
  with boiler's plain thermal efficiency column (fewer distinct column
  names in the schema, per explicit user request). It is **not** the COP
  -- it's the Carnot quality/2nd-law factor (0-1) fed into
  `cop_calculation.carnot_cop`. Validated at two separate points: the raw
  `efficiency` input against `0 < efficiency <= 1` (thermodynamic limit),
  and the *derived* COP against `1 <= cop <= 20` (a real-world sanity
  bound on the technology's actual performance). See
  `docs/calliope_schema_mapping.md` "Heat pump efficiency".
- [cost-taxonomy] Confirmed against Calliope's actual math docs (fetched
  live, not guessed) that `cost_flow_cap`, `cost_flow_in`, `cost_flow_out`,
  `cost_interest_rate` are genuine, distinct current-Calliope parameters,
  and that the package's "fixed O&M" column was **misnamed**
  (`cost_flow_om_annual` is not a real Calliope key) -- renamed to the
  confirmed real name, `cost_om_annual`. Kept all 5 columns distinct
  (rejected merging `cost_flow_in`/`cost_flow_out` into one "O&M" column)
  since Calliope itself treats input-linked and output-linked variable
  cost as different parameters. See `docs/calliope_schema_mapping.md`
  "Cost columns" for the full reference table now that it's confirmed.
- [csv-two-files] BY-DESIGN: split `technologies.csv` into
  `technologies.csv` (technical/capacity/efficiency inputs) +
  `costs.csv` (every `cost_*` column), joined by
  `(category, variant, scale)` in `core/csv_loader.load_technology_rows`.
  Matches the user's own idea (a "costs" sheet split out from a
  "technologies" sheet in a `.ods` workbook they prototyped) but as two
  plain CSVs rather than one multi-sheet `.ods`/`.xlsx` -- avoids a new
  parsing dependency (`odfpy`/`openpyxl`) and keeps git diffs readable
  (`.ods` is a zip/binary format; every edit would show as "binary file
  changed," not which cell changed). `technologies.ods` (the user's
  prototype) was removed once this was implemented. `costs.csv` repeats
  `category`/`variant`/`scale`/`name`/`color` for readability on its own;
  those are dropped on merge (`technologies.csv`'s copy is authoritative).
  A `costs.csv` row with no matching `technologies.csv` row raises
  `ValueError` immediately (catches a spelling mismatch between the two
  files) rather than silently producing a technology with missing costs.
- [csv-params-dir] BY-DESIGN: the override environment variable was
  renamed `CONVERSION_TECH_PARAMS_FILE` -> `CONVERSION_TECH_PARAMS_DIR`
  (now a folder containing both `technologies.csv` and `costs.csv`, since
  there are two files to override together). Still **replaces the whole
  pair** for a run, does not merge cell-by-cell with the bundled defaults
  (registration happens once at import time, before any CLI arg parsing,
  so a per-invocation `--params` flag isn't feasible without a bigger
  lazy-registration rework -- see open.md if that's ever wanted).
- [dependencies] BY-DESIGN: `ruamel.yaml` was added (not in `weather`/`occupancy`)
  because comment-preserving, readable YAML output is this package's actual
  deliverable. No pydantic — dataclasses match sibling convention.
- [cli-category-filter] `--category` (aliases `hp`/`boiler`/`chp`) added to
  `list` and `export-all`; `export-all`'s `--config path.json` now consumes
  `ExportConfig` (its `technology_ids` overrides `--category`/`--variant`/
  `--scale` if given). `export-all -o <dir>/` still writes one file per
  technology; `-o name.yaml` combines every matched technology into a
  single `techs:` document via `calliope_export.writer.write_techs_yaml` —
  decided by the output path's suffix, not a separate flag.
- [technology-variant] BY-DESIGN: added `TechnologySpec.variant` (required
  field, right after `category`) — a short lowercase string identifying the
  specific technology within its category (`"electric"`, `"geothermal"`,
  `"gas"`, `"biomass"`), set explicitly by every category builder. Before
  this it only existed implicitly inside the `id` string (e.g.
  `heat_pump_electric_household`), which meant "every scale of just the
  electric heat pump" had no way to be selected without listing exact ids.
  The CLI's `--variant` flag matches this field (case-insensitive) --
  named `--variant` (not `--type`, an earlier iteration used that name but
  it was changed on request to avoid confusion with the internal field
  name). `--category`/`--variant`/`--scale` combine with AND in
  `cli._filter_technologies`.
- [dynamic-params] BY-DESIGN: `TechnologySpec` only names the fields every
  technology always has (`flow_cap_max`, `lifetime`, `cost_flow_cap`, plus
  identity/carrier fields); every other Calliope parameter
  (`flow_cap_min`, `cost_om_annual`, `cost_flow_in`, `cost_flow_out`,
  `cost_interest_rate`, `flow_ramping`, and anything added later) lives in
  `TechnologySpec.params: dict[str, float]`, populated by
  `core.csv_loader.passthrough_params(row, formula_columns=...)` -- every
  non-blank column not consumed by a category's own formula, keyed by its
  exact column name. `modern.py` iterates `params` generically (any
  `cost_*` key gets the cost-block wrapper, everything else is written
  as-is) -- **no per-field code should ever be added to `modern.py` for a
  new parameter** (see `CLAUDE.md` "Hard conventions" #7). Reason: the
  user wanted "adding a CSV row/column just works" and "column names
  aren't hardcoded in multiple places," so a future Calliope rename is one
  CSV-column edit, not a hunt through `technology.py` + 3 builders +
  (formerly) 2 exporters. Verified live: added a column (`cost_om_frac`)
  that exists in no Python file anywhere, and it appeared correctly in
  `modern` YAML output.
- [csv-bom-fix] Fixed while verifying the above: `core.csv_loader` reads
  with `utf-8-sig` (not `utf-8`) -- a UTF-8 BOM (which Excel writes by
  default saving CSV on Windows, and which PowerShell's `Set-Content
  -Encoding utf8` also writes) silently renamed the `category` header,
  breaking every row lookup. Real bug, not just a test artifact — anyone
  editing the CSVs in Excel on Windows would have hit it. Covered by a
  regression test (`test_csv_loader.py`).
- [repo] Pushed to `github.com/UU-BUEM/conversion-technologies` (public,
  `main` branch). The first CI run failed in 8s because `.gitignore`'s
  unanchored `env/`/`data/` patterns had silently excluded
  `infrastructure/env/conversion_env.yml` and every `data/defaults.json` --
  fixed and re-pushed (see CHANGELOG "Fixed"); check `gh run list --repo
  UU-BUEM/conversion-technologies` if a future push mysteriously fails fast
  again, since an unanchored gitignore pattern is an easy repeat mistake
  when adding a new nested `data/` or `env/` directory.
- [ratio-math-fix] BY-DESIGN: `calliope_export/ratio_math.py` generates the
  Calliope "additional math" (a `link_flow_in_carriers`/
  `link_flow_out_carriers` equality constraint + a scoped
  `balance_conversion` override) a real solve needs to actually respect a
  multi-carrier technology's fixed carrier ratio -- per explicit user
  request ("fix everything"), not left as documentation-only. Verified
  algebraically against Calliope's own base math (`balance_conversion` sums
  across carriers, it doesn't pin their split) and cross-checked against
  Calliope's own official CHP example, which needs the same two-part fix
  (`heat_to_power_ratio` + `link_chp_outputs` + a `balance_conversion`
  override) -- generalised here to be driven structurally (`len(carriers) >
  1` on either side) instead of hardcoded per technology name, and
  symmetric for the input side (heat pump) as well as the output side
  (CHP). Boiler is untouched (one carrier per side). Driven entirely off
  `TechnologySpec.carriers_in`/`carriers_out`/`primary_carrier_in`/
  `primary_carrier_out` -- no new CSV column. `export`/`export-all` write it
  automatically as `additional_math.yaml` (default on; `--no-custom-math`
  opts out) -- a correctness fix, not an opt-in nicety. Full derivation:
  `docs/calliope_schema_mapping.md` "Carrier ratio math". Not validated
  against a running Calliope solve (none available here) -- stated
  explicitly wherever this is documented, not silently assumed correct.
- [weather-series-own-reader] SUPERSEDED (2026-07-28): originally
  `core/weather_series.py` (a new `pandas` dependency) read the weather CSV
  contract `weather.export.export_single_point_csv()` documents, with zero
  dependency on the `weather` package itself -- reasoning at the time:
  `weather` pulls in netCDF4/xarray/cfgrib/eccodes/dask/pyproj/scipy, a
  footprint disproportionate to one temperature column, and both packages
  being local/same-org/same-machine meant no network/API layer was needed
  either way. Reversed once the user pointed at a real, working precedent
  in `UU-BUEM/buem` that integrates with `weather` far more tightly than
  this reasoning assumed was warranted -- see [weather-real-dependency]
  below for what replaced it. The "no network/API layer, local data
  transfer" half of the original reasoning was never in question and still
  holds; only the "avoid the `weather` package itself" half was wrong.
- [weather-real-dependency] BY-DESIGN: `weather` is now a **compulsory**
  runtime dependency (`pyproject.toml`, `infrastructure/env/
  conversion_env.yml`), installed as `weather[pointquery] @
  git+https://github.com/UU-BUEM/weather.git@main` -- matches exactly how
  `UU-BUEM/buem` treats this same dependency (confirmed by reading
  `buem`'s `pyproject.toml`/`infrastructure/env/buem_env.yml` directly, not
  guessed), as opposed to how `buem` treats `occupancy` (an optional extra
  with a guarded import + synthetic fallback) -- the user explicitly chose
  the "compulsory, like buem" option even though only the narrow
  `weather-cop` command needs it, over a leaner optional-extra split.
  `new/heat_pump/weather_cop.py` calls `weather.get_point_weather(lat, lon,
  year, provider=..., data_dir=...)` directly (module-level import, not
  lazy/guarded -- matches `buem`'s `weather_cache.py:30`), replacing
  `core/weather_series.py`'s CSV path entirely (deleted, along with its
  test) rather than keeping both -- also an explicit user choice. `weather`
  now uses a `pointquery`/`pipeline` extras split (`pointquery` = just
  `xarray`+`netcdf4`, lightweight; `pipeline` = the heavy
  cfgrib/dask/eccodes/pyproj/scipy stack, only needed to *produce* archives,
  not query them) -- this package installs `weather[pointquery]` only (not
  `[pointquery,solar]` like `buem` -- no irradiance/pvlib need for COP).
  `infrastructure/env/conversion_env.yml` additionally conda-installs
  `dask` explicitly alongside `xarray`/`netcdf4`, even though `weather`'s
  own `pointquery` extra doesn't declare it -- `weather`'s point-query path
  uses `xr.open_mfdataset` internally and needs it at runtime regardless;
  confirmed by finding the same gap called out in `buem_env.yml`'s own
  comments, not discovered independently. `get_point_weather()`'s own
  contract (hourly, complete, tz-naive `T`/`GHI`/`DHI`/`DNI` for one
  location/year) is trusted rather than re-validated on this package's
  side, matching how `buem` uses it -- no reindex/coverage-check layer was
  rebuilt after deleting `core/weather_series.py`'s `align_to_year`.
- [occupancy-out-of-scope] BY-DESIGN: `occupancy`'s `total_power_kwh` is not
  wired into anything here, and this package does not export a Calliope
  `demand` technology for it -- stays conversion-technologies only, per
  explicit user decision. A heat pump's electricity draw is a
  Calliope-optimizer decision, not normally an exogenous profile;
  `occupancy`'s output would become a *separate* `demand` tech's
  `sink_use_equals` sharing a node with the technologies here, hand-wired
  by whoever builds the full model -- not something this package generates.
  `occupancy` itself has zero Calliope integration and no community scale.
  Documented, not implemented: `docs/calliope_schema_mapping.md`
  "occupancy is out of scope".
- [stale-version-file] Not a bug in this repo's config, confirmed by
  investigation: `conversion-technologies info`/`--version` reported
  `0.1.1.dev2+g7dad1f93d...` (referencing old commit `7dad1f9`) despite
  `v0.2.0` already being tagged and `git describe --tags` correctly
  resolving to it. `src/conversion_technologies/_version.py` is
  `setuptools_scm`-generated at *install* time (correctly gitignored, not
  tracked -- see `.gitignore`'s "setuptools-scm generated version file"
  entry); it does not regenerate itself just because a new commit or tag
  lands. Fix: re-run `pip install -e . --no-deps` (same command
  `CONTRIBUTING.md`'s dev setup already documents) to recompute it from
  current git state. If the working tree has uncommitted changes when you
  do this, expect a `devN+g<hash>.d<date>` version (e.g.
  `0.2.1.dev0+g24a2d4e89.d20260728`), not a bare `X.Y.Z` -- that's
  `setuptools_scm`'s "guess-next-dev" + "node-and-date" schemes working as
  intended (CONTRIBUTING.md "Releasing"), not a second bug; a clean `X.Y.Z`
  only shows with a clean tree exactly at that tag.
- [units-currency-convention] BY-DESIGN: this package's units, stated
  explicitly for the first time (previously implicit): USD for every
  `cost_*` value, kW for capacity/flow, kWh for energy, 1-hour timestep.
  Calliope itself is confirmed unit/currency-agnostic (fetched from its own
  docs) -- this is a stated modeler convention, not a Calliope requirement,
  and matches `weather`'s and `occupancy`'s native hourly resolution
  exactly (no resampling needed when wiring either in). See
  `docs/calliope_schema_mapping.md` "Units, currency, and Calliope
  version", which also states the exact Calliope version/pin this package
  targets (`0.7.0.devN`, pre-release -- bare `pip install calliope` resolves
  to incompatible old `0.6.10`).
