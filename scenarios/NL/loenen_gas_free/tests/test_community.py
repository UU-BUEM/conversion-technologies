"""Tests for the energy-community pilot (scripts/community/).

Run in scenario_env (with Library/bin on PATH) from the repository root:

    python -m pytest scenarios/NL/loenen_gas_free/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "community"))

from build_community import station_limits  # noqa: E402
from select_members import _quotas, draw  # noqa: E402


def _candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "building_feature_id": range(1, 31),
            "feeder_id": ["F1"] * 20 + ["F2"] * 8 + [None] * 2,
        }
    )


def test_quotas_are_proportional_and_sum_to_n():
    quota = _quotas(pd.Series({"F1": 20, "F2": 8, "unassigned": 2}), 10)
    assert quota.sum() == 10
    assert quota["F1"] == 7 and quota["F2"] == 3  # 6.67 -> 7, 2.67 -> 3


def test_draw_is_seeded_stratified_and_unique():
    a = draw(_candidates(), 10, seed=1)
    b = draw(_candidates(), 10, seed=1)
    c = draw(_candidates(), 10, seed=2)
    assert a["building_feature_id"].tolist() == b["building_feature_id"].tolist()
    assert a["building_feature_id"].tolist() != c["building_feature_id"].tolist()
    assert a["building_feature_id"].is_unique and len(a) == 10
    assert (a["feeder_id"] == "F1").sum() == 7


def test_draw_rejects_more_members_than_candidates():
    with pytest.raises(ValueError):
        draw(_candidates(), 31, seed=1)


def test_station_limits_subtract_non_member_load(tmp_path):
    times = pd.date_range("2018-01-01 00:30", periods=3, freq="h")
    grid = pd.DataFrame(
        {"building_feature_id": [1, 2, 3, 9], "trafo_id": ["S", "S", "S", "T"]}
    )
    grid.to_csv(tmp_path / "building_grid_map.csv", index=False)
    pd.DataFrame({"trafo_id": ["S", "T"], "rated_kva": [100.0, 50.0]}).to_csv(
        tmp_path / "transformers.csv", index=False
    )

    def hourly(ids, kw):
        rows = [
            {"building_feature_id": b, "time": t, "elec_kW": kw, "ev_kW": 1.0}
            for b in ids
            for t in times
        ]
        return pd.DataFrame(rows)

    hourly([1, 2], 4.0).to_parquet(tmp_path / "single.parquet")  # 1 is a member
    hourly([3], 9.0).to_parquet(tmp_path / "background.parquet")
    members = pd.DataFrame({"building_feature_id": [1]})
    limits, meta = station_limits(
        "S",
        members,
        tmp_path,
        tmp_path / "single.parquet",
        tmp_path / "background.parquet",
        power_factor=1.0,
    )
    # non-members: building 2 (4 + 1) and background 3 (9 + 1) = 15 kW
    np.testing.assert_allclose(limits["import_kW"], 85.0)
    np.testing.assert_allclose(limits["export_kW"], 115.0)
    assert meta["n_non_members"] == 2
