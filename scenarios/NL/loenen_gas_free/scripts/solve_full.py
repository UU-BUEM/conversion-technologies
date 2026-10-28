"""Phase 4: build and solve the real, full 1,260-node Loenen gas-free model.

Separate from the smoke test -- this is the actual scenario deliverable.
Requires a real Calliope 0.7.0 install (see docs/phase4_solve.md for how
this repo's own validation environment, `.venv_calliope_check/`, was set
up) and CBC on PATH (conda-installed in buem_env on this machine; not a
scenario-specific dependency).

Usage (from the scenario root, scenarios/NL/loenen_gas_free/):
    python scripts/solve_full.py
"""
from __future__ import annotations

import time

import calliope


def main() -> None:
    t0 = time.time()
    model = calliope.read_yaml("model.yaml")
    t_load = time.time()
    print(f"LOADED in {t_load - t0:.1f}s")

    model.build()
    t_build = time.time()
    print(f"BUILT in {t_build - t_load:.1f}s")

    model.solve()
    t_solve = time.time()
    print(f"SOLVED in {t_solve - t_build:.1f}s")

    print("=== cost (summed over nodes/techs) ===")
    print(float(model.results["cost"].sum()))
    model.to_netcdf("outputs/loenen_gas_free_results.nc")
    print("Wrote outputs/loenen_gas_free_results.nc")


if __name__ == "__main__":
    main()
