"""Solve the ``independent`` pilot variant one member at a time, and sum.

With no links, no shared asset and no station limit the independent model
is block-diagonal by member (as in ``docs/phase5_per_building_decomposition.md``),
so 20 one-member models give exactly the 20-member result, much faster and
with far less memory. Each member is built by ``build_community.build``
(``mode="independent"``) and solved by ``solve_community.solve_model``.

Writes ``<out>/<node>/`` per member and ``<out>/results.json`` with the sums:
total and per-technology cost, built capacities, annual energy, and the
station exchange from the hourly sum of every member's import and export
(coincident peak).

Usage (scenario_env with Library/bin on PATH, scenario root)::

    python scripts/community/solve_independent.py --station MSR5000927 --workers 4
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_community import DATA, build  # noqa: E402


def _one(station: str, row: dict, out: Path) -> dict:
    from solve_community import solve_model

    node_dir = out / row["node"]
    node_dir.mkdir(parents=True, exist_ok=True)
    members_csv = node_dir / "member.csv"
    pd.DataFrame([row]).to_csv(members_csv, index=False)
    build(station, node_dir, mode="independent", members_csv=members_csv)
    return solve_model(node_dir)


def _add(total: dict, part: dict) -> None:
    for key, value in part.items():
        total[key] = round(total.get(key, 0.0) + value, 6)


def aggregate(results: list[dict], out: Path) -> dict:
    agg: dict = {
        "mode": "independent (sum of one-member models)",
        "n_members": len(results),
        "termination": sorted({r["termination"] for r in results}),
        "solved_in_s_sum": round(sum(r["solved_in_s"] for r in results), 1),
        "total_cost_eur": 0.0,
        "cost_by_tech_eur": {},
        "flow_cap_total_kw": {},
        "storage_cap_total_kwh": {},
        "annual_kwh": {},
    }
    for r in results:
        if r["termination"] != "optimal":
            continue
        agg["total_cost_eur"] += r["total_cost_eur"]
        for key in (
            "cost_by_tech_eur",
            "flow_cap_total_kw",
            "storage_cap_total_kwh",
            "annual_kwh",
        ):
            _add(agg[key], r[key])
    exchange = sum(
        pd.read_csv(Path(r["model_dir"]) / "exchange_hourly.csv", index_col=0)
        for r in results
        if r["termination"] == "optimal"
    )
    agg["station_exchange"] = {
        "import_peak_kw": float(exchange["import_kW"].max()),
        "export_peak_kw": float(exchange["export_kW"].max()),
        "hours_importing": int((exchange["import_kW"] > 1e-3).sum()),
        "hours_exporting": int((exchange["export_kW"] > 1e-3).sum()),
    }
    exchange.to_csv(out / "exchange_hourly.csv")
    agg["per_member_cost_eur"] = {
        Path(r["model_dir"]).name: r.get("total_cost_eur") for r in results
    }
    return agg


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--station", required=True)
    parser.add_argument("--members", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    members_csv = args.members or DATA / "community" / args.station / "members.csv"
    members = pd.read_csv(members_csv)
    out = args.out or DATA / "community" / args.station / "independent_split"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_one, args.station, row, out): row["node"]
            for row in members.to_dict("records")
        }
        for fut in as_completed(futures):
            r = fut.result()
            print(
                f"{futures[fut]}: {r['termination']} in {r['solved_in_s']} s",
                flush=True,
            )
            results.append(r)
    agg = aggregate(results, out)
    (out / "results.json").write_text(json.dumps(agg, indent=2))
    print(
        json.dumps(
            {k: v for k, v in agg.items() if k != "per_member_cost_eur"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
