"""Tests for step 2 helpers (envelope retrofit region, PV nodes parsing).

Run in scenario_env from the repository root:

    python -m pytest scenarios/NL/loenen_gas_free/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_pv_potential import _nodes_kwp  # noqa: E402
from build_retrofit_region import retrofit  # noqa: E402


def _tabula() -> pd.DataFrame:
    codes = [
        "NL.N.SFH.03.Gen.ReEx.001.001",
        "NL.N.SFH.03.Gen.ReEx.001.002",
        "NL.N.SFH.03.Gen.ReEx.001.003",
        # newest era: TABULA NL has no standard (002) package
        "NL.N.SFH.06.Gen.ReEx.001.001",
        "NL.N.SFH.06.Gen.ReEx.001.003",
    ]
    return pd.DataFrame({"id": range(1, len(codes) + 1), "Code_BuildingVariant": codes})


def _buildings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "building_feature_id": [1, 2, 3, 4, 5],
            "is_residential": [True, True, True, True, False],
            "tabula_variant_code": [
                "NL.N.SFH.03.Gen.ReEx.001.001",
                "NL.N.SFH.03.Gen.ReEx.001.003",
                "NL.N.SFH.06.Gen.ReEx.001.001",
                "NL.N.SFH.03.Gen.ReEx.001.002",
                None,
            ],
            "tabula_variant_code_id": [1, 3, 4, 2, None],
            "refurbishment_variant": [1, 3, 1, 2, 1],
        }
    )


def test_standard_lifts_never_lowers_and_keeps_era_without_package():
    out, stats = retrofit(_buildings(), _tabula(), 2)
    assert out["refurbishment_variant"].tolist() == [2, 3, 1, 2, 1]
    assert out["tabula_variant_code_id"].tolist()[:4] == [2, 3, 4, 2]
    assert pd.isna(out["tabula_variant_code_id"].iloc[4])  # service building
    assert stats["changed"] == 1
    assert stats["kept_no_tabula_package"] == 1


def test_advanced_lifts_everyone_to_three():
    out, stats = retrofit(_buildings(), _tabula(), 3)
    assert out["refurbishment_variant"].tolist()[:4] == [3, 3, 3, 3]
    assert out["tabula_variant_code"].iloc[2] == "NL.N.SFH.06.Gen.ReEx.001.003"
    assert stats["changed"] == 3


def test_rejects_unknown_target():
    with pytest.raises(ValueError):
        retrofit(_buildings(), _tabula(), 1)


def test_nodes_kwp_reads_cli_yaml(tmp_path):
    path = tmp_path / "nodes.yaml"
    path.write_text(
        "nodes:\n"
        "  bldg_71:\n"
        "    techs:\n"
        "      pv_rooftop_household:\n"
        "        flow_cap_max:\n"
        "          data: 4.945\n"
        "          index: electricity\n"
        "  '134':\n"
        "    techs:\n"
        "      pv_rooftop_household:\n"
        "        flow_cap_max:\n"
        "          data: 11.447\n",
        encoding="utf-8",
    )
    assert _nodes_kwp(path) == {"bldg_71": 4.945, "134": 11.447}
