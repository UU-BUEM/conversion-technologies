"""Hourly air-source heat pump COP wiring (build_hp_cop.py, build_nodes.py --cop)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SCENARIO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCENARIO_ROOT / "scripts"))

import build_nodes  # noqa: E402

COP_DIR = SCENARIO_ROOT / "heat_pump_cop_2018"


def test_overrides_null_both_cop_scalars_for_every_air_source_heat_pump():
    techs = build_nodes.cop_overrides()[build_nodes.HOURLY_COP_SCENARIO]["techs"]
    assert set(techs) == set(build_nodes._HP_COP_TECHS)
    for params in techs.values():
        assert params == {"flow_out_eff": None, "carrier_flow_ratio_in": None}


def test_model_scenario_selects_the_override_only_when_present(tmp_path):
    with_override = tmp_path / "a.yaml"
    with_override.write_text("overrides:\n  hourly_cop:\n    techs: {}\n")
    without = tmp_path / "b.yaml"
    without.write_text("config: {}\n")
    assert build_nodes.model_scenario(with_override) == "hourly_cop"
    assert build_nodes.model_scenario(without) is None


@pytest.mark.skipif(not COP_DIR.exists(), reason="run scripts/build_hp_cop.py first")
@pytest.mark.parametrize("tech", build_nodes._HP_COP_TECHS)
def test_cop_series_are_consistent(tech):
    cop = pd.read_csv(COP_DIR / f"{tech}_flow_out_eff.csv", index_col=0)["flow_out_eff"]
    ratio = pd.read_csv(COP_DIR / f"{tech}_carrier_flow_ratio_in.csv", index_col=0)[
        "carrier_flow_ratio_in"
    ]
    assert len(cop) == 8760
    assert list(cop.index) == list(ratio.index)
    assert ((cop - 1.0 - ratio).abs() < 1e-9).all()  # ambient draw = COP - 1
    assert cop.between(1.0, 20.0).all()
    assert cop.index[0] == "2018-01-01 00:30:00"  # the demand tables' stamps
