"""Benchmark solvers on identical per-building models (Calliope 0.7.0).

Draws a seeded sample of buildings, builds each one-building model once per
solver configuration (``solve_single_building.build_single_building_model``)
and times reading + building and solving separately. Every configuration
runs one thread per model and the same number of models in parallel, so
the timings compare like with like. The objective of every solve is
checked against the reference configuration (Gurobi barrier, if present).

Configurations:

- ``cbc``: CBC through Calliope's Pyomo backend (the scenario's default);
- ``highs_simplex``: Calliope's native HiGHS backend, HiGHS's default
  (dual simplex);
- ``highs_ipm``: native HiGHS, interior point without crossover;
- ``gurobi``: native Gurobi backend, barrier without crossover (needs a
  licence).

Writes ``<out>/benchmark_runs.csv`` (one row per building and
configuration) and ``<out>/benchmark_summary.csv``.

Usage (scenario_env, scenario root)::

    python scripts/benchmark_solvers.py --n 40 --workers 8 --out outputs/solver_benchmark
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_nodes  # noqa: E402
from solve_all_buildings import _all_building_ids  # noqa: E402
from solve_single_building import build_single_building_model  # noqa: E402

SCENARIO_ROOT = Path(__file__).resolve().parent.parent

# name -> (solver, backend options, extra solver options)
CONFIGS = {
    "cbc": ("cbc", {}),
    "highs_simplex": ("highs", {"solver": "simplex", "threads": 1}),
    "highs_ipm": ("highs", {"solver": "ipm", "run_crossover": "off", "threads": 1}),
    "gurobi": ("gurobi", {"Method": 2, "Crossover": 0, "Threads": 1}),
}
REFERENCE = "gurobi"


def _run(building: str, config: str, work_root: Path, nodes_dir: str) -> dict:
    import calliope
    from ruamel.yaml import YAML

    solver, options = CONFIGS[config]
    work_dir = work_root / config / building
    model_path = build_single_building_model(
        building, work_dir, ev="smart", nodes_dir=nodes_dir, solver=solver
    )
    # Exact options for the benchmark (not the scenario defaults).
    yaml = YAML()
    model = yaml.load(model_path.open(encoding="utf-8"))
    model["config"]["solve"]["solver_options"] = dict(options)
    with model_path.open("w", encoding="utf-8") as fh:
        yaml.dump(model, fh)
    row = {"building": building, "config": config}
    try:
        t0 = time.perf_counter()
        m = calliope.read_yaml(
            str(model_path), scenario=build_nodes.model_scenario(model_path)
        )
        m.build()
        t1 = time.perf_counter()
        m.solve()
        t2 = time.perf_counter()
        row.update(
            build_s=t1 - t0,
            solve_s=t2 - t1,
            termination=str(getattr(m.runtime, "termination_condition", "?")),
            objective=float(m.results["cost"].sum(skipna=True)),
        )
    except Exception as exc:  # noqa: BLE001 -- a failure is a result here
        row.update(termination=f"error: {type(exc).__name__}: {exc}"[:200])
    return row


def summarise(runs: pd.DataFrame) -> pd.DataFrame:
    ref = runs[runs.config == REFERENCE].set_index("building")["objective"]
    runs = runs.copy()
    runs["rel_diff_vs_ref"] = (
        runs["objective"] - runs["building"].map(ref)
    ).abs() / runs["building"].map(ref).abs()
    rows = []
    for config, g in runs.groupby("config", sort=False):
        ok = g[g.termination == "optimal"]
        rows.append(
            {
                "config": config,
                "models": len(g),
                "optimal": len(ok),
                "solve_s_median": ok.solve_s.median(),
                "solve_s_p90": ok.solve_s.quantile(0.9),
                "solve_s_max": ok.solve_s.max(),
                "solve_s_total": ok.solve_s.sum(),
                "build_s_median": ok.build_s.median(),
                "max_rel_objective_diff_vs_ref": ok.rel_diff_vs_ref.max(),
            }
        )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--nodes-dir", default="nodes_day_ahead")
    parser.add_argument("--configs", nargs="+", default=list(CONFIGS))
    parser.add_argument(
        "--out", type=Path, default=SCENARIO_ROOT / "outputs/solver_benchmark"
    )
    args = parser.parse_args(argv)
    buildings = sorted(_all_building_ids(args.nodes_dir))
    sample = sorted(random.Random(args.seed).sample(buildings, args.n))
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for config in args.configs:  # one configuration at a time: equal load
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [
                pool.submit(_run, b, config, args.out / "models", args.nodes_dir)
                for b in sample
            ]
            for fut in as_completed(futures):
                rows.append(fut.result())
        print(f"{config}: {time.perf_counter() - t0:.0f} s wall", flush=True)
        pd.DataFrame(rows).to_csv(args.out / "benchmark_runs.csv", index=False)
    runs = pd.DataFrame(rows)
    summary = summarise(runs)
    summary.to_csv(args.out / "benchmark_summary.csv", index=False)
    with pd.option_context("display.float_format", "{:,.4g}".format):
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
