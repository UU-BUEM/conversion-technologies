"""Workflow step 5: choose the energy-community members on one station.

Default: a **seeded synthetic draw** of ``--n`` single-dwelling buildings
(the buildings with Calliope models) behind one MV/LV station, stratified by
LV feeder (members per feeder proportional to its dwellings, largest
remainder), uniform within a feeder. The same seed always gives the same
members; rerun with other seeds for the sensitivity the workflow asks for.

Override: ``--member-list`` with a CSV of ``building_feature_id`` or
``bag_pand_id`` values (a real, anonymised list). It must stay in the
git-ignored ``data/`` folder.

Output ``data/community/<station>/members.csv``: one row per member with
its node name, feeder, EV ownership and rooftop PV potential, plus
``selection.json`` (rule, seed, counts).

Usage (scenario_env, scenario root)::

    python scripts/community/select_members.py --station MSR5000927 --n 20 --seed 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCENARIO_ROOT = Path(__file__).resolve().parents[2]
DATA = SCENARIO_ROOT / "data"


def _quotas(sizes: pd.Series, n: int) -> pd.Series:
    """Members per stratum, proportional to its size (largest remainder)."""
    exact = sizes / sizes.sum() * n
    quota = np.floor(exact).astype(int)
    short = n - int(quota.sum())
    # Ties in the remainder go to the larger stratum, then by name, so the
    # quotas never depend on sort stability.
    ranking = pd.DataFrame(
        {"remainder": (exact - quota).round(9), "size": sizes, "name": sizes.index}
    )
    order = ranking.sort_values(
        ["remainder", "size", "name"], ascending=[False, False, True]
    ).index
    quota.loc[order[:short]] += 1
    return quota.clip(upper=sizes)


def draw(candidates: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """``n`` candidates, stratified by ``feeder_id`` (NaN = its own stratum)."""
    if n > len(candidates):
        raise ValueError(f"asked for {n} members, only {len(candidates)} candidates")
    rng = np.random.default_rng(seed)
    strata = candidates.assign(stratum=candidates["feeder_id"].fillna("unassigned"))
    quota = _quotas(strata.groupby("stratum").size(), n)
    picks = []
    for stratum, k in quota.items():
        pool = strata[strata["stratum"] == stratum].sort_values("building_feature_id")
        picks.append(pool.iloc[np.sort(rng.choice(len(pool), size=k, replace=False))])
    chosen = pd.concat(picks)
    if len(chosen) < n:  # a stratum was smaller than its quota
        rest = strata.drop(chosen.index).sort_values("building_feature_id")
        extra = rng.choice(len(rest), size=n - len(chosen), replace=False)
        chosen = pd.concat([chosen, rest.iloc[np.sort(extra)]])
    return chosen.drop(columns="stratum").sort_values("building_feature_id")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--station", required=True)
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--member-list", type=Path, default=None)
    parser.add_argument(
        "--grid-map",
        type=Path,
        default=DATA / "step2/grid/dso_liander/building_grid_map.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DATA / "loenen_single_dwelling_summary_cool26_ev20.parquet",
        help="buem summary of the buildings that have Calliope models",
    )
    parser.add_argument(
        "--pv", type=Path, default=DATA / "step2/pv/pv_building_potential.csv"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    grid = pd.read_csv(args.grid_map)
    summary = pd.read_parquet(
        args.summary, columns=["building_feature_id", "bag_pand_id", "has_ev"]
    )
    pv = pd.read_csv(args.pv)[["building_feature_id", "max_kwp", "kwh_per_kwp"]]
    candidates = (
        grid[grid["trafo_id"] == args.station]
        .drop(columns=["bag_pand_id"])
        .merge(summary, on="building_feature_id")  # single dwellings only
        .merge(pv, on="building_feature_id", how="left")
    )
    if candidates.empty:
        raise ValueError(f"no single-dwelling buildings on station {args.station}")

    if args.member_list is not None:
        listed = pd.read_csv(args.member_list, dtype=str)
        key = (
            "building_feature_id" if "building_feature_id" in listed else "bag_pand_id"
        )
        wanted = set(listed[key])
        members = candidates[candidates[key].astype(str).isin(wanted)]
        missing = len(wanted) - len(members)
        if missing:
            raise ValueError(
                f"{missing} listed members are not single dwellings on {args.station}"
            )
        rule = f"provided list ({args.member_list.name})"
    else:
        members = draw(candidates, args.n, args.seed)
        rule = "seeded draw, stratified by LV feeder, uniform within a feeder"

    members = members.assign(node=[f"bldg_{b}" for b in members["building_feature_id"]])
    out = args.out or DATA / "community" / args.station
    out.mkdir(parents=True, exist_ok=True)
    cols = [
        "building_feature_id",
        "node",
        "bag_pand_id",
        "feeder_id",
        "method",
        "has_ev",
        "max_kwp",
        "kwh_per_kwp",
    ]
    members[cols].to_csv(out / "members.csv", index=False)
    meta = {
        "station": args.station,
        "rule": rule,
        "seed": None if args.member_list else args.seed,
        "n_members": len(members),
        "n_candidates": len(candidates),
        "members_by_feeder": members["feeder_id"]
        .fillna("unassigned")
        .value_counts()
        .to_dict(),
        "members_with_ev": int(members["has_ev"].sum()),
        "candidates_with_ev": int(candidates["has_ev"].sum()),
        "member_pv_potential_kwp": round(float(members["max_kwp"].sum()), 1),
    }
    (out / "selection.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
