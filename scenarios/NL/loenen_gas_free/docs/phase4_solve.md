# Phase 4 — solve

**Status: a real 3-node smoke test solves to optimality against real
CBC.** The full 1,260-node scenario loads successfully; a full-scale
solve is the next step, not yet attempted (see "Next" at the bottom).

## Approach taken

Originally scoped as "submit to `enerplanet/MEME`," but MEME's own README
(`enerplanet/meme`) describes it as accepting **one canonical JSON model**
and translating it into Calliope/PyPSA/AdOpT-NET0's native formats — it is
not a pass-through for hand-written Calliope YAML like
`scenarios/NL/loenen_gas_free/model.yaml`. Writing that translation is a
separate, larger piece of work than this phase's actual goal: testing
whether the generated model (Phases 2-3) is valid and solves at all.

So Phase 4 instead installs Calliope directly and runs it against
`model.yaml` — the most direct way to check everything earlier phases
flagged as "not verified against a running Calliope install"
(`additional_math` wiring, `data_tables` shape, the `conversion`
balance-equation override in `ratio_math.py`). Submitting to MEME/
simulation-engine for a production-style run is still a real follow-up,
just not this phase's path to a first real answer.

## Environment

`.venv_calliope_check/` (gitignored scratch venv, same pattern as
`.venv_scenario_check/` from Phase 2).

**Real finding, stale docs caught**: `pip install calliope==0.7.0.dev8`
(the version `conversion-technologies`' own
`docs/calliope_schema_mapping.md` names as "the latest on PyPI as of this
writing") failed — PyPI's real version list has no `dev8` at all. Calliope
has since shipped **0.7.0 as a full stable release** (after `dev7`
directly, per PyPI's version list: `...dev6, dev7, 0.7.0`). Installed
`calliope==0.7.0` instead. Worth a follow-up note in
`docs/calliope_schema_mapping.md` itself (out of scope for this phase,
flagging here) — the pre-release pinning guidance there is now outdated.

## Checks performed, with real findings

1. **`calliope.Model(...)` is not the load entry point in 0.7.0** -- real
   API is `calliope.read_yaml(path)`. Found by trying the obvious call
   first and reading the resulting `TypeError`.
2. **Confirmed real schema bug in this repo's own exporter**: validating a
   real `export-all` output against installed `calliope==0.7.0` failed
   with `String should match pattern '^[^_^\d][\w]*$'` on every tech's
   `_comment` key -- Calliope 0.7.0 forbids a leading underscore on any
   tech key. **Fixed in `calliope_export/modern.py` and
   `new/heat_pump/weather_cop.py`**: renamed `_comment` -> `comment`
   (satisfies the pattern; Calliope accepts arbitrary extra tech/data_table
   keys as inert custom parameters). Re-ran Phase 2's export after the fix
   -- 0 occurrences of `_comment`, 15 of `comment:` in the real output.
3. **Confirmed real `config.init` schema differs from what this scenario
   first guessed**, checked against Calliope's own bundled
   `example_models/urban_scale/model.yaml` (the same file
   `ratio_math.py`'s own docstring already cites):
   - Time subsetting is `config.init.subset.timesteps: [...]`, not a
     top-level `time_subset`.
   - `additional_math.yaml` is wired via `config.init.math_paths.
     additional_math: "<path>"` **plus** `config.init.extra_math:
     ["additional_math"]` -- a two-step named reference, not a plain list.
   - `mode` (`base`/`operate`/`spores`) lives under `config.init`, not
     `config.build` -- and the earlier guess of `mode: plan` isn't even a
     real choice.
   `model.yaml`/`model_smoketest.yaml` corrected to match.
4. **Confirmed real `data_tables` schema bug in this scenario's own
   `build_nodes.py`** (not a `conversion_technologies`-package bug this
   time): the file-path key is `table`, not `data`; the parameter-name key
   inside `add_dims` is `inputs`, not `parameters`. Found the same way --
   checked against the real bundled example model, which also confirmed
   `new/heat_pump/weather_cop.py` already had this right (good prior art
   this scenario's own script should have matched from the start). Fixed
   in `build_nodes.py` and regenerated `nodes/data_tables.yaml` +
   `nodes/data_tables_smoketest.yaml`.
5. No usable CBC on this machine (`where cbc` empty) -- switched
   `model.yaml`'s `config.solve.solver` from `cbc` to `highs`
   (`highspy` installs as a `calliope==0.7.0` dependency automatically,
   confirmed present).
6. **Real, confirmed core-package bug found and fixed**: validating the
   real `additional_math.yaml` output against `calliope==0.7.0` failed
   with `pydantic_core.ValidationError: ... carrier_flow_ratio_in.data ...
   Extra inputs are not permitted`. Calliope 0.7.0's math-file
   `parameters:` schema only accepts metadata (`default`/`title`/
   `description`) -- the indexed `data`/`index`/`dims` wrapper
   `ratio_math.py` used to carry each tech's actual ratio value has no
   home there. **Fixed** by moving the per-tech value onto each tech's
   own body in the model definition instead (where Calliope 0.7.0 does
   accept arbitrary scalar tech attributes): added
   `ratio_math.carrier_flow_ratios(tech)`, called from `modern.py`'s
   `export()` and merged into the tech body (`carrier_flow_ratio_in: 2.33`
   etc., confirmed present on `heat_pump_electric_building`'s real
   exported body); `build_ratio_math()`'s `parameters:` block now only
   ever declares metadata. This is a real fix to this repo's own
   `calliope_export/ratio_math.py` + `modern.py`, not scenario-only glue
   -- `docs/calliope_schema_mapping.md`'s "Carrier ratio math" section
   needs a matching update (flagged, not yet done -- see "Follow-ups").
7. **Real, confirmed `where:` DSL bug found and fixed in the same file**:
   after fixing (6), `m.build()` failed with a math-string parsing error
   on every `where: "techs=heat_pump_electric_household"`-style clause.
   Calliope's real `where:` syntax for matching a tech by id is
   `"[tech_id] in techs"` (confirmed against the bundled
   `example_models/urban_scale/additional_math.yaml`'s own
   `where: "[chp] in techs"`), not `techs=tech_id`. Fixed all three
   equation-building sites in `ratio_math.py` (`sed`, verified by grep
   afterward).
8. **Real, confirmed `data_tables` path-resolution bug found and fixed in
   this scenario's own `build_nodes.py`**: `table:` paths resolve relative
   to the top-level `model.yaml`'s own directory, not relative to the
   `data_tables.yaml` file that references them (even though `nodes/
   data_tables.yaml` is itself `import:`ed from a subdirectory) --
   confirmed by a real `FileNotFoundError` naming the wrong resolved
   path. Fixed by prefixing the table path with the containing folder
   name (`nodes/demand_heat.csv` instead of `demand_heat.csv`).
9. **After fixes 6-8, the 3-node smoke-test model both loads
   (`calliope.read_yaml`) and builds (`m.build()`) successfully against
   real `calliope==0.7.0`** -- `MODEL LOADED OK` / `MODEL BUILT OK`,
   confirmed by direct output, not inferred. Every issue flagged in Phase
   3 as "not verified against a running Calliope install" is now either
   fixed or confirmed-fine by this real build.

## Solve attempt -- HiGHS backend blocked, switched to CBC

`m.solve()` with `config.solve.solver: highs` failed with
`AttributeError: 'parameter_dict' object has no attribute 'mutable'`,
inside Pyomo's HiGHS persistent-solver interface
(`pyomo/contrib/solver/solvers/highs.py`) -- a genuine version-
compatibility bug between the installed `pyomo==6.10.1` and
`highspy==1.15.1`, not a defect in this scenario's model definition (the
model had already built cleanly in the step right before this).

Two things tried that did **not** fix it:
- Downgrading to `pyomo<6.8` (predating Pyomo's newer persistent-solver
  refactor) -- made things worse: that older Pyomo fails to import
  against the installed NumPy 2.x (`np.float_ was removed in NumPy 2.0`),
  breaking `import calliope` entirely. Reverted immediately
  (`pip install "pyomo>=6.8.2"`).
- Switching `solver: appsi_highs` (Pyomo's older APPSI persistent
  interface, also HiGHS-backed) -- failed differently:
  `Highs.__init__() got an unexpected keyword argument 'solver_io'`.
  Calliope's own `pyomo_backend_model.py` unconditionally calls
  `SolverFactory(solver, solver_io=solve_config.solver_io)` for every
  solver name; this APPSI plugin's constructor doesn't accept that kwarg
  at all. A second, independent Pyomo/Calliope version-mismatch bug, not
  fixable by picking a different *name* within the HiGHS family.

**What actually worked**: a real CBC binary was already present on this
machine (conda-installed, `buem_env`'s `Library/bin/cbc.exe` --
`buem`'s own conda environment pulls CBC as a dependency, unrelated to
this scenario but a lucky find via `find ... -iname cbc.exe` across all
local conda envs). Switched `model_smoketest.yaml`'s
`config.solve.solver` to `cbc` and put that directory on `PATH` for the
invocation (Pyomo's classic shell-based CBC plugin, which doesn't go
through either broken persistent interface above). Result:

```text
ERROR: No solution is available
...
Termination condition: infeasible
```

A **real, clean CBC run** -- not a crash -- that found the model
genuinely infeasible. This surfaced an actual model-definition gap, not
an environment bug.

## Real finding: no supply technology for any input carrier

`nodes.yaml` had `demand_heat`/`demand_elec` plus the 5 conversion techs,
but **nothing supplies electricity, biomass, ambient_heat, or
ground_heat at any node** -- a heat pump/boiler/CHP can only draw a
carrier something actually produces. Every conversion tech's input side
was structurally unable to flow at all, hence infeasible.

**Fixed in `build_nodes.py`**: added four `base_tech: supply` techs to
every node -- `supply_grid_electricity` and `supply_biomass` (placeholder
`cost_flow_out` prices, explicitly flagged as not real market/tariff
quotes -- a genuine follow-up, not fabricated data pretending to be
real) and `supply_ambient_heat`/`supply_ground_heat` (free, uncapped,
representing an always-available outdoor-air/ground source for the heat
pumps). All four capped at `flow_cap_max: 1e6` -- effectively
unconstrained for a single building, not a real grid/feedstock
constraint (constraints.md #5/#7 already flag the real versions of this
gap as open).

## Real solve succeeded after the fix

Regenerated nodes with the new supply techs, re-ran the same 3-node CBC
solve. **Solved to optimality this time** -- confirmed by real non-trivial
results, not just absence of an error:

- `flow_cap` (chosen technology capacities): e.g. `heat_pump_electric_household`
  sized at ~12.0 kW for one building, ~1.75-13.75 kW across the other
  two -- different per building, as expected from genuinely different
  demand profiles. `supply_grid_electricity`/`supply_biomass`/
  `supply_ambient_heat`/`supply_ground_heat` each hit their 1e6
  placeholder ceiling at whichever node uses that carrier (expected --
  nothing constrains them yet).
- `cost` (per node, per tech, monetary): real, distinct, mostly non-zero
  values per node/tech combination -- not all-zero or NaN, which would
  have indicated an unused or degenerate result.
- `m.results.attrs` came back empty for `termination_condition` specifically
  (this Calliope version doesn't surface that key in `attrs` the way
  assumed) -- the real confirmation is the non-trivial `flow_cap`/`cost`
  values themselves, not that one attribute.

## Follow-ups, not done in this pass

- Update `docs/calliope_schema_mapping.md`'s "Carrier ratio math" section
  to describe the real, fixed `parameters:`-is-metadata-only /
  per-tech-value-on-the-tech-body shape (finding 6) -- the section
  currently still shows the old `data`/`index`/`dims` wrapper as if it
  belonged in the math file.
- Update the same doc's "Units, currency, and Calliope version" table --
  it names `0.7.0.dev8` as "the latest on PyPI as of this writing," which
  finding (in this phase) shows is stale now that `0.7.0` has shipped as
  a full stable release.
- The Pyomo/HiGHS backend issue is worked around (CBC), not fixed --
  revisit if a faster/stronger solver (Gurobi, CPLEX, a working
  HiGHS pairing) is wanted for the full-scale solve, since CBC is
  typically much slower than either on large LPs/MILPs.
- Replace the two placeholder prices (`supply_grid_electricity`'s
  0.25 USD/kWh, `supply_biomass`'s 0.05 USD/kWh) with real sourced
  figures before trusting any cost output from a real analysis run.
- Un-cap (or realistically cap) the four supply techs' `flow_cap_max:
  1e6` once the real grid-capacity (`constraints.md` #5,
  `enerplanet-pylovo`) and biomass-feedstock (#7) constraints are wired
  in -- today's uncapped value is a "make it solvable" placeholder, not
  a real limit.

## Full 1,260-node model: real load confirmed; build/solve at full scale not yet attempted

Ran `calliope.read_yaml('model.yaml')` against the **real, full**
scenario (not the 3-node smoke test):

```text
FULL MODEL LOADED OK 267.1s
```

**1,260 nodes, 8,760 timesteps, 15 conversion technologies + 4 supply
technologies, real demand data: loads successfully in ~4.5 minutes.**
`m.build()`/`m.solve()` were not attempted at this scale in this pass --
both are now unblocked (CBC solves the 3-node case cleanly), but
untested how long either takes over roughly 1,260 nodes × 11 techs ×
8,760 timesteps with an open-source LP solver. The per-building
resolution decision from Phase 3 ("each building is a separate node...
we will cluster if we have processing issues") hasn't hit a wall at the
*load* stage; whether `build()`/`solve()` do at full scale is the next
real question, not yet answered.

## Full-scale `m.build()`: real memory wall hit (2026-10-24)

Ran `scripts/solve_full.py` against the real `model.yaml`. Result:

```text
LOADED in 224.5s
numpy._core._exceptions._ArrayMemoryError: Unable to allocate 4.52 GiB
for an array with shape (607068000,) and data type int64
```

Loading succeeds every time (now twice, 267s and 224.5s); `m.build()`
fails outright constructing one of the model's global expressions --
not a timeout, a genuine out-of-memory error, trying to materialize a
~607-million-element array (consistent with 1,260 nodes × 8,760
timesteps × roughly 55 tech/carrier/dim combinations). This is the real
processing-scale wall the scenario's own README anticipated ("each
building is a separate node... we will cluster if we have processing
issues").

**This is a decision point, not a bug to silently work around**:
per-building, full-year, hourly resolution for all 1,260 nodes
genuinely does not fit in this machine's available memory at the
`m.build()` step. Three real options, not yet chosen between:

1. **Cluster by TABULA archetype** (the scenario's own stated fallback)
   -- fewer nodes, same demand data aggregated per archetype group.
   Reduces node count sharply; `buem`'s own validation tooling already
   groups by archetype, so this has real precedent.
2. **Keep per-building nodes, reduce timesteps** -- Calliope's own
   timestep clustering/representative-days feature (not yet used
   anywhere in this scenario), or a shorter time window (e.g. a month
   instead of a year) for a feasibility check short of the real
   12-month answer.
3. **Run on a machine with more memory** -- the model *loads* fine
   here; it's specifically constraint construction that needs more RAM
   than this machine has. Untested how much more would be enough.

Not acted on without a decision -- this was explicitly flagged as the
user's own call to make when the per-building resolution was chosen in
Phase 3.

**Decision taken (2026-10-24)**: run the full build/solve on `sd26`, a
separate, more capable machine, rather than redesigning the pipeline
around clustering. This session has no network access to reach it
(`ssh`/`scp` are blocked outright by this machine's own local policy,
even to an already-configured host with an existing key) -- the runbook
below is for the user to run on sd26 directly.

## Runbook: running the full build/solve on sd26

**Use conda, not pip**, for the validation environment there -- unlike
the throwaway local pip venv this phase used
(`.venv_calliope_check/`, a plain venv because that's what was on hand,
not a deliberate choice), conda is the better fit for two real reasons:
this repo's own convention (`infrastructure/env/conversion_env.yml`)
already uses conda for the heavy scientific/solver stack and pip only
for git-only packages; and **conda-forge ships `coincbc` (the CBC
binary) in the same channel as `calliope`** -- confirmed via conda-forge's
own package listing, `calliope==0.7.0` is there (not just a dev
pre-release) -- so installing both from one consistently-resolved
channel avoids the independent-pip-resolution Pyomo/HiGHS version
mismatches this phase hit locally (see "Solve attempt" above).

```bash
# On sd26
conda create -n loenen_gas_free -c conda-forge python=3.12 calliope=0.7.0 coincbc
conda activate loenen_gas_free

# Copy this folder over (scp from your own machine, or however you move
# files to sd26 -- this session cannot do it, see above)
#   scenarios/NL/loenen_gas_free/  ->  <somewhere on sd26>

cd <that folder>
python scripts/solve_full.py
```

`scripts/solve_full.py` already prints load/build/solve timings and
writes `outputs/loenen_gas_free_results.nc` on success -- no changes
needed for sd26 specifically, beyond having calliope+cbc on `PATH` via
the conda env above (no manual `PATH` prepending needed the way this
session needed for buem_env's cbc.exe -- conda's own activation handles
that).
