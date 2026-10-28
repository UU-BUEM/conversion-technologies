# Phase 4b — sizing probe against calliope==0.6.10 (separate from Phase 4)

**Status: findings stand; the version question has a real contradiction,
not yet reconciled.** An EnerPlanET developer confirmed (2026-10-28) that
production targets **Calliope 0.7.0**. That conflicts directly with this
doc's own finding below -- `enerplanet/simulation-engine`'s actual,
committed `webservice.dockerfile` pins `calliope==0.6.10`, not 0.7.0. One
of these is stale -- leading hypothesis (2026-10-28, from the user, not
independently confirmed): the developer's own local/dev environment has
already moved to 0.7.0, while `webservice.dockerfile` reflects what's
actually deployed, which hasn't been updated to match yet. Still worth
confirming directly (e.g. does `simulation-engine`'s `main`/deploy branch
have a newer, unmerged 0.7.0 Dockerfile change) before fully retiring the
0.6.10 path. Everything below
about 0.6.10's own scaling behavior remains correct and useful background
regardless of which version turns out to be the real target; it's the
*target* question, not these findings, that's still open. This was a
second, independent investigation track, run in parallel with Phase 4's
(`docs/phase4_solve.md`) `calliope==0.7.0` work -- it does not replace or
modify anything there.

## Why this track exists

Phase 4 diagnosed a real `m.build()` memory wall against `calliope==0.7.0`
(see `docs/phase4_solve.md` "Full-scale `m.build()`: real memory wall hit").
Checking `enerplanet/simulation-engine` (the production service this
scenario is meant to run inside) found its `webservice.docker/
webservice.dockerfile` pins a dedicated venv to:

```
numpy>=1.23.0,<1.24.0  pandas>=1.5.0,<2.0.0  xarray>=2022.3.0,<2023.0.0
calliope==0.6.10  highspy
```

**Not 0.7.0.** Calliope 0.6.x and 0.7.x have different backend-construction
code (0.7 introduced a new string-expression `where:`/`equations:` parser;
0.6.x uses an older Pyomo `ConcreteModel`-building path) and a different
model-definition schema (`locations`/`energy_cap_max`/`energy_eff`/
`run.mode`, not `nodes`/`flow_cap_max`/`flow_in_eff`/`config.init.mode`).
Memory/time behavior measured against 0.7.0 does not necessarily transfer
to 0.6.10, and this repo's own `calliope_export/modern.py` currently emits
0.7.0-schema YAML that 0.6.10 very likely cannot even load as-is -- a
separate compatibility question from sizing. See the status note at the
top of this document: an EnerPlanET developer has since confirmed 0.7.0,
which conflicts with this Dockerfile pin -- not yet reconciled.

## Environment

`conda` env `calliope_0610` (Python 3.11, matching production's
`python:3.11-bookworm` base image), **not** a plain pip venv like Phase
4's `.venv_calliope_check/` -- deliberately matching
`enerplanet/simulation-engine`'s exact pin set as closely as possible on
this machine. `cbc.exe` reused from `buem_env`'s conda install (same
source Phase 4 used), prepended onto `PATH` per-invocation rather than
globally.

Real package versions actually installed (from `pip install`'s resolver,
not assumed):

```
calliope-0.6.10 numpy-1.23.5 pandas-1.5.3 xarray-2022.3.0 pyomo-6.4.4
highspy-1.15.1 pyarrow-14.0.2 (downgraded from 26.0.0 -- needs numpy<2.0)
```

## Scenario used for this probe -- NOT a faithful translation

`generate_scenario.py` (in a scratch dir, not committed) builds an N-node
model in Calliope 0.6.10's real schema (confirmed against calliope's own
bundled `example_models/urban_scale/{model.yaml,model_config/techs.yaml,
model_config/locations.yaml}`, same pattern Phase 4 used for 0.7.0):
same node count and real per-building heat/elec demand magnitudes as the
real scenario (from `data/loenen_single_dwelling_hourly.parquet`), same
rough tech count per node (2 demand + 5 "household" conversion techs + 2
supply techs). **The 5 conversion techs are simple single-carrier
`parent: conversion` stand-ins, not `conversion_plus` with
`carrier_ratios`** -- this probe is testing *scale/memory behavior*, not
reproducing `ratio_math.py`'s real multi-carrier business logic. Good
enough to answer "how does 0.6.10 scale with node count", not a substitute
for a real translated export.

## Finding 1: `calliope.Model(path)` is cheap; `m.run(build_only=True)` is where memory grows

0.6.10's API has no separate `.build()` -- `calliope.Model(...)`
constructs quickly (12.2s for 100 nodes/8760 timesteps), and backend
construction happens inside `.run()`. Confirmed `run()` takes a real
`build_only=True` kwarg (`calliope/backend/run.py`) that stops short of
invoking the solver -- used here the same way Phase 4 used `m.build()`.

## Finding 2: same qualitative memory-growth shape as 0.7.0, at 100 nodes

Watched with the same psutil-based hard-cap watchdog pattern Phase 4 used
(kills the child process if it crosses a memory/time cap -- see that
doc's caveats about *why* a watchdog, not an unsupervised run, after two
uncontrolled climbs past 50GB on 0.7.0).

100 nodes, full year (8,760 timesteps), `run(build_only=True)`:

```
CONSTRUCTED in 12.2s
[climbs steadily, no plateau, t=300s -> 6.00 GB, MEM CAP hit]
```

Slower growth rate than the equivalent 0.7.0 test (which hit 6GB in
~120s, not ~300s), but **the same shape**: steady, unbounded-looking
climb with no plateau, not a fixed one-time allocation. A longer run (up
to 30GB/900s cap) was started to check whether it eventually plateaus --
result below once it completes.

**900s/30GB-cap run result**: still climbing at the 900s cutoff --
**12.15 GB peak, no plateau reached.** Growth wasn't perfectly smooth
(brief flat stretches of ~100-150s at a few points, e.g. steady at 9.82GB
from t=686s to t=711s, then resumed climbing) but the overall trend over
the full 15 minutes is clearly upward, not converging. 100 nodes, full
year, took 15 real minutes without finishing backend construction.

## Interpretation so far (provisional -- longer run not yet back)

**Confirmed, not just provisional now**: the memory-growth problem is
**not** specific to Calliope 0.7.0's newer string-expression parser (the
thing Phase 4 specifically blamed). 0.6.10's structurally different,
older Pyomo-`ConcreteModel`-building code shows the same unbounded-looking
shape -- at just **100 nodes**, full year, it never plateaued even after
**15 real minutes** and 12.15 GB. That points toward something more
fundamental than either Calliope generation's own code: plausibly a
general characteristic of building a dense per-node/per-timestep Pyomo
model at this scale (full scenario is 1,260+ nodes x 8,760 timesteps --
12x more nodes than this probe even reached, before timing out).

**Practical conclusion**: switching Calliope versions is very unlikely to
fix this on its own. Reducing problem size (fewer nodes via clustering,
and/or fewer timesteps via representative periods) is the load-bearing
lever regardless of which Calliope generation `enerplanet` ends up
running -- confirmed empirically now across *both* versions, not assumed.

## Finding 3: full node count (~1,260) + 1-week timesteps actually completes `build_only`

Per the user's direction ("do temporal clustering first for a short
period, say 1 week"): regenerated the scenario with **all** real nodes
(`generate_scenario.py all 2018-01-01 2018-01-07` -- 1,260 nodes, 144
timesteps instead of 8,760) and re-ran the same watchdog-capped
`run(build_only=True)` probe (40GB/900s cap).

```
CONSTRUCTED in 62.1s
BUILD_ONLY RUN done in 184.1s
peak RSS: 4.60 GB
exit code: 0 -- completed cleanly, not killed by either cap
```

**This is a real, positive result, not a capped/inconclusive one.**
Unlike every full-year test (100 nodes or 1,260), this one actually
finished: no unbounded climb, no plateau-then-resume pattern, a modest
bounded peak (4.60 GB) well within reach of ordinary hardware, done in
about 3 minutes end-to-end including data load. Memory also visibly
dropped back down (to 1.52 GB) immediately after completion, consistent
with a real finish rather than a watchdog kill.

**This directly answers the open question from Finding 2's
interpretation**: temporal clustering (reducing timesteps) *alone*, with
**no spatial/node clustering at all**, is sufficient to get the full
real node count through backend construction successfully under
`calliope==0.6.10`. Node count was never actually the problem by itself;
the full year's 8,760 timesteps was.

## Finding 4: CBC solve attempt -- slow, not conclusively hung

Removed `build_only=True` for the same full-node, 1-week model, still
`solver: cbc`. Build completed at the same 62-132s as before; the solve
step then held memory stable around **~10.1-10.2 GB for 8+ minutes**
(no further growth -- genuinely solving, not leaking) but did **not**
converge within the 900s cap. Killed by the time cap, not the memory
cap. Inconclusive on CBC's real wall-clock cost -- would need a longer
run to know if/when it finishes.

## Finding 5: HiGHS (`appsi_highs`) solves the same model to optimality in ~8 minutes total

Per the user's direction ("try HiGHS first"): replicated
`enerplanet/simulation-engine`'s own documented Pyomo patch (its
`webservice.dockerfile` patches `pyomo/contrib/appsi/base.py`'s
`LegacySolver` class for `calliope==0.6.10` + `highspy` compatibility --
accepts/ignores the `solver_io` kwarg, adds `warmstart`/`**kwargs` to
`solve()`, exposes `self.name`) onto this env's own
`pyomo==6.4.4` install, byte-for-byte the same patch production uses.
Sanity-checked first against calliope's own bundled `urban_scale`
example (`run.solver: appsi_highs`) -- solved to `optimal` in 0.02s real
solver time, confirming the patch works before trusting it on the real
scenario.

Then re-ran the full-node (~1,260), 1-week model with `run.solver:
appsi_highs` instead of `cbc`:

```
CONSTRUCTED in 62.5s
LP has 3,834,180 rows; 4,018,140 cols; 10,197,180 nonzeros
[dual simplex, ~1.23M iterations]
Model status: Optimal
Simplex iterations: 1,229,791
HiGHS run time: 133.52s
RUN done in 487.0s total (~8 minutes, build + solve + postsolve)
cost sum: 107016.9698425587
peak RSS: 16.56 GB
exit code: 0 -- completed cleanly, genuinely solved, not killed
```

**This is the first genuinely complete, successful full-scale result in
either investigation track (0.7.0 or 0.6.10).** Full real node count,
real demand data, actually optimal, in well under 10 minutes, with a
memory footprint (16.56 GB peak) that's well within reach of ordinary
hardware and far below `enerplanet/simulation-engine`'s own provisioned
48GB/container limit (`docker-compose.unltd.yaml`).

**Answers the user's original solver question directly**: CBC did not
converge in 900s on this same problem (Finding 4) while HiGHS solved it
in 133.5s of actual solver time -- a real, measured difference, not a
guess, on the exact same LP. Given `enerplanet/simulation-engine`'s own
production Dockerfile already carries this exact HiGHS+patch setup
alongside CBC, this isn't even introducing a new dependency -- it's using
a solver path production has already provisioned for.

## Finding 6: 1-month window does NOT scale linearly from 1-week -- didn't finish in 30 min

Per the user's follow-up ("do for 1 month with HiGHS"): same full node
count (~1,260), same `appsi_highs` solver, 720 timesteps (2018-01-01 to
2018-01-31) instead of 144 (~5x more).

```
CONSTRUCTED in 63.8s
Running HiGHS 1.15.1 ...
[nothing further printed -- no "LP has N rows" line, unlike the 1-week
 run where that line appeared almost immediately]
peak RSS: 50.40 GB, still climbing when killed
TIME CAP (1800s / 30 min) hit -- killed, not a clean finish
```

**This is a materially different, worse outcome than 1-week's clean
success**, not just "slower by ~5x." The process never even reached
HiGHS's own presolve/solve phase (no "LP has rows/cols/nonzeros" line) --
it was still inside Pyomo's model-to-HiGHS translation step after 30
minutes, climbing toward 50GB. For comparison, the 1-week run's entire
build+solve+postsolve finished in 487s with that same translation step
essentially instant.

**Interpretation**: time/memory cost is scaling worse than linearly with
timestep count for this model -- 5x more timesteps produced a `>13x`
longer run that still hadn't reached the solver, not a ~5x longer one.
This is consistent with Finding 2/3's earlier full-year results (which
never finished either) -- there's a real breakdown point somewhere
between 1 week and 1 month of timesteps at full node count, not a smooth
degradation.

**Practical read**: brute-forcing longer windows (1 month, let alone a
full year) at full per-building node resolution is not the right lever.
The 1-week result (Finding 5) stays the one clean, fully-solved reference
point. Next step, if longer time coverage is needed, should be Calliope's
own time-series clustering (representative weeks/days spread across the
year) rather than a contiguous longer window -- not yet tried.

## Finding 7: the scenario is structurally separable by node -- a combined LP was never necessary

User's observation, checked and confirmed against the real scenario
files before acting on it: `nodes/nodes.yaml` has **no `links:` section**
(no cross-building transmission techs, unlike calliope's own bundled
`urban_scale` example, which links locations via `power_lines`/
`heat_pipes`) and **no storage tech anywhere** in
`technologies/export/loenen_gas_free_techs.yaml` (every tech is
`base_tech: conversion`, `demand`, or `supply`). Timesteps within one
node are only linked through that node's own capacity-sizing variables
(`energy_cap`/`flow_cap`, chosen once per node per tech, constraining
every timestep of that node); nothing links one node's variables to
another's.

**This means the full 1,260-node, full-year problem is mathematically
block-diagonal by node** -- solving it as one combined LP is
*equivalent* to solving each of the 1,260 single-building, full-year
problems independently and summing the results. The giant combined LP
every earlier finding in this doc struggled with was never the only way
to get the real, full-resolution answer.

**Verified directly**: generated a 1-node, full-year (8,760 timesteps)
scenario and solved it with `appsi_highs`:

```
CONSTRUCTED in 0.9s
LP has 183,979 rows; 192,741 cols; 490,589 nonzeros
HiGHS run time: 4.57s
RUN done in 26.6s
Model status: Optimal
cost sum: 3670.2905307244973
peak RSS: 0.99 GB
```

**One building's full-year problem is tiny and fast** -- 27s wall clock,
under 1GB, a world apart from the combined-LP attempts. Running all
~1,260 buildings this way, independently and in parallel (no shared
state, no coordination needed between them -- an embarrassingly parallel
workload), would get the **full year, full per-building hourly
resolution, no time-series clustering needed at all** -- something
neither the combined-LP approach (never finished at full year) nor
time-clustering (only covers a window) could do on its own.

**Verified with real concurrent execution, not just extrapolated**
(`parallel_test.py`, same scratch dir): ran N independent processes each
solving the same single-building full-year model concurrently (this
machine has 22 logical cores), measuring real wall-clock time for the
whole batch.

```
8 concurrent solves:  each ~29-31s solo-equivalent, batch finished in 44.9s wall-clock
16 concurrent solves: each ~41-48s (slower per-solve due to contention),
                      batch finished in 60.6s wall-clock
```

Real parallelism, not linear slowdown -- 16x the sequential work finished
in ~2.3x one solve's solo time, not 16x. Extrapolating from the 16-way
batch: `ceil(1260/16) = 79` batches x 60.6s ~= **80 minutes for the
entire scenario**, full year, full per-building hourly resolution, no
time-series clustering needed at all. This machine has 22 cores; on
`enerplanet/simulation-engine`'s own provisioned containers (6 CPU/48GB
per `docker-compose.unltd.yaml`), the real batch size/throughput would
differ and should be measured there directly before trusting this
number for production sizing -- the *architecture* (per-building
parallel decomposition) is now confirmed sound, the exact wall-clock on
production hardware is not yet measured.

## Follow-ups

- Finish the 900s/30GB-cap run above; record whether it plateaus.
- Sweep node count (100 -> ~400 -> ~800 -> full ~1,600) under 0.6.10 the
  same way Phase 4 swept under 0.7.0, to see if the growth *rate* (not
  just eventual peak) scales linearly or worse with node count.
- Once the colleague confirms enerplanet's real pinned Calliope version,
  revisit whether this probe's findings (or Phase 4's) are the ones that
  actually matter for provisioning `enerplanet`'s simulation containers
  (their `docker-compose.unltd.yaml` currently caps each simulation
  container's memory at 48G/6 CPU -- worth comparing against whatever
  this probe's real peak turns out to be once it's not watchdog-capped).
- If this track is pursued further, decide whether to invest in a real
  0.6.10-schema export path (parallel to `calliope_export/modern.py`) --
  not done here; this probe's scenario is a scale stand-in only.
