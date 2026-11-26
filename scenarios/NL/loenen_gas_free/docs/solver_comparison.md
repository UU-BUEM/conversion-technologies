# Solver comparison: CBC, HiGHS and Gurobi with Calliope 0.7.0

Status 2026-11-26. All solvers reach the same optimum; they differ by an
order of magnitude in time, and only Gurobi solved the full-year community
model.

## How each solver is reached

| Solver | Calliope 0.7.0 route | Setting |
| --- | --- | --- |
| CBC | Pyomo backend (`build.backend: pyomo`) | default |
| HiGHS | Calliope's native backend (`build.backend: highs`) | simplex (HiGHS default) or interior point without crossover |
| Gurobi | Calliope's native backend (`build.backend: gurobi`) | barrier without crossover; academic licence |

HiGHS through Pyomo does not work with Calliope 0.7.0 models (Pyomo 6.10.1
and 6.9.4: `highs` raises `'parameter_dict' object has no attribute
'mutable'`, `appsi_highs` rejects Calliope's `solver_io` argument), so
HiGHS is used only through the native backend.

## 1. Per-building models (60 dwellings, identical models)

`scripts/benchmark_solvers.py --n 60 --workers 8` (seed 1): one-node
models, full year hourly (8,760 steps), heating and cooling, smart EV
charging, day-ahead price, hourly heat pump COP. One thread per model and 8
models in parallel for every solver, run one solver after the other.

| Solver | Optimal | Solve time median | p90 | max | Total (60) | Speed-up vs CBC (median of per-model ratios) | Build time median |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CBC | 60/60 | 27.4 s | 31.9 s | 35.2 s | 1,661 s | 1.0 | 17.5 s |
| HiGHS simplex | 60/60 | 14.4 s | 22.3 s | 25.0 s | 861 s | 1.8 | 27.8 s |
| HiGHS interior point | 60/60 | 10.7 s | 14.8 s | 18.0 s | 681 s | 2.5 | 28.0 s |
| Gurobi barrier | 60/60 | 3.7 s | 4.9 s | 6.0 s | 233 s | 7.3 | 20.3 s |

- Objectives agree to within a relative 8e-9 (reference: Gurobi).
- "Build" is reading the YAML and building the optimisation problem in
  Calliope. For these small models it is as long as or longer than the
  solve, and the native backends build more slowly than Pyomo (20-28 s vs
  17.5 s). End to end per model: about 45 s (CBC), 42 s (HiGHS simplex),
  39 s (HiGHS interior point), 24 s (Gurobi); wall time for the 60 models:
  408, 402, 364 and 246 s.
- The full region (1,260 dwellings, 16 workers, Gurobi) takes about 70
  minutes; with CBC about 1.6 hours (v4 runs).

## 2. Community model (21 nodes, linked)

Pilot station MSR5000927: 20 members linked to a hub with a community
battery and the station limit (`docs/phase9_community_pilot.md`).

| | CBC (Pyomo) | HiGHS (native) | Gurobi (native) |
| --- | --- | --- | --- |
| One week (8-14 Jan): objective | EUR 1,584.8356 | EUR 1,584.8356 | EUR 1,584.8356 |
| One week: solver time | 109 s | 42 s (simplex); 44 s (interior point, with crossover) | 0.6 s (barrier) |
| Full year | no result in 12 h (stopped) | simplex: no feasible point in 40 min; interior point: not converged in about 4 h | optimal in 14-20 min (build and solve, 855-1,166 s over four runs) |
| Memory to build the full year | about 17 GB | about 7.6 GB | not measured |

The gap widens with model size: 1.8-2.5x (HiGHS) and 7x (Gurobi) on one
building, but only Gurobi solves the coupled 21-node year at all.

## Recommendation

- **Open source:** HiGHS through Calliope's native backend, interior point
  without crossover (`build_community.py --solver highs`, the default),
  about 2.5x faster than CBC on one-building models. For large coupled
  models (communities of ~200 members) plan time aggregation (typical
  days) or grouping per station; HiGHS did not solve the 20-member
  full year in 4 h.
- **With a licence:** Gurobi through the native backend, 7x faster than
  CBC per building and the only one that solved the community year.
- **Avoid** CBC for anything coupled, and HiGHS through Pyomo altogether.

## Reproduce

```bash
python scripts/benchmark_solvers.py --n 60 --workers 8 --out outputs/solver_benchmark
python scripts/build_community.py --station MSR5000927 --subset 2018-01-08 2018-01-14 --solver cbc|highs|gurobi
python scripts/community/solve_community.py data/community/MSR5000927/<dir>
```

Machine: Windows 11, 64 GB RAM; Calliope 0.7.0, Pyomo 6.10.1, CBC
(coincbc), highspy 1.15.1, Gurobi 14.0.0.
