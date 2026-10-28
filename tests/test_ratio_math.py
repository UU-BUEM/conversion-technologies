from __future__ import annotations

import pytest

from conversion_technologies import new  # noqa: F401  (registers technologies)
from conversion_technologies.calliope_export.ratio_math import (
    build_ratio_math,
    carrier_flow_ratios,
)
from conversion_technologies.core.registry import all_technologies, get_technology
from conversion_technologies.core.technology import TechnologySpec


def _spec(**overrides: object) -> TechnologySpec:
    fields: dict[str, object] = dict(
        id="test_tech",
        name="Test",
        category="heat_pump",
        variant="electric",
        scale="household",
        carriers_in={"electricity": 1.0},
        carriers_out={"heat": 1.0},
        flow_cap_max=10.0,
        lifetime=18,
        cost_flow_cap=900.0,
        primary_carrier_in="electricity",
        primary_carrier_out="heat",
    )
    fields.update(overrides)
    return TechnologySpec(**fields)  # type: ignore[arg-type]


def test_single_carrier_technologies_need_no_math() -> None:
    boiler = get_technology("boiler_gas_household")
    assert build_ratio_math([boiler]) is None


def test_heat_pump_gets_an_input_side_link_and_a_balance_override() -> None:
    tech = get_technology("heat_pump_electric_household")
    math = build_ratio_math([tech])
    assert math is not None
    assert "carrier_flow_ratio_in" in math["parameters"]
    assert "carrier_flow_ratio_out" not in math["parameters"]

    # The numeric ratio itself lives on each tech's own body (set by
    # modern.py via carrier_flow_ratios()), not in build_ratio_math()'s
    # parameters block -- Calliope 0.7.0's math-file `parameters:` schema
    # only accepts metadata (default/title/description), so the actual
    # value can't live there. See carrier_flow_ratios()'s own docstring.
    expected_ratio = tech.carriers_in["ambient_heat"] / tech.carriers_in["electricity"]
    assert carrier_flow_ratios(tech)["carrier_flow_ratio_in"] == pytest.approx(expected_ratio)

    link_eqs = math["constraints"]["link_flow_in_carriers"]["equations"]
    assert any(
        eq["where"] == f"[{tech.id}] in techs"
        and "flow_in[carriers=ambient_heat]" in eq["expression"]
        and "flow_in[carriers=electricity]" in eq["expression"]
        for eq in link_eqs
    )

    balance_eqs = math["constraints"]["balance_conversion"]["equations"]
    assert any(
        eq["where"] == f"[{tech.id}] in techs"
        and "flow_out_inc_eff[carriers=heat]" in eq["expression"]
        and "flow_in_inc_eff[carriers=electricity]" in eq["expression"]
        for eq in balance_eqs
    )
    assert "link_flow_out_carriers" not in math["constraints"]


def test_chp_gets_an_output_side_link_and_a_balance_override() -> None:
    tech = get_technology("chp_gas_household")
    math = build_ratio_math([tech])
    assert math is not None
    assert "carrier_flow_ratio_out" in math["parameters"]
    assert "carrier_flow_ratio_in" not in math["parameters"]

    expected_ratio = tech.carriers_out["heat"] / tech.carriers_out["electricity"]
    assert carrier_flow_ratios(tech)["carrier_flow_ratio_out"] == pytest.approx(expected_ratio)

    link_eqs = math["constraints"]["link_flow_out_carriers"]["equations"]
    assert any(
        eq["where"] == f"[{tech.id}] in techs"
        and "flow_out[carriers=heat]" in eq["expression"]
        and "flow_out[carriers=electricity]" in eq["expression"]
        for eq in link_eqs
    )
    assert "link_flow_in_carriers" not in math["constraints"]


def test_mixed_export_only_lists_technologies_that_need_math() -> None:
    boiler = get_technology("boiler_gas_household")
    hp = get_technology("heat_pump_electric_household")
    math = build_ratio_math([boiler, hp])
    assert math is not None
    balance_eqs = math["constraints"]["balance_conversion"]["equations"]
    assert {eq["where"] for eq in balance_eqs} == {f"[{hp.id}] in techs"}


def test_every_registered_multi_carrier_technology_is_covered() -> None:
    techs = list(all_technologies().values())
    math = build_ratio_math(techs)
    assert math is not None
    covered = {
        eq["where"] for eq in math["constraints"]["balance_conversion"]["equations"]
    }
    expected = {
        f"[{t.id}] in techs"
        for t in techs
        if len(t.carriers_in) > 1 or len(t.carriers_out) > 1
    }
    assert covered == expected
    assert expected  # sanity: today's catalog does have multi-carrier technologies


def test_missing_primary_carrier_raises() -> None:
    tech = _spec(
        carriers_in={"electricity": 1.0, "ambient_heat": 2.0}, primary_carrier_in=None
    )
    with pytest.raises(ValueError, match="primary_carrier_in"):
        build_ratio_math([tech])


def test_more_than_one_secondary_carrier_raises() -> None:
    tech = _spec(
        carriers_in={"electricity": 1.0, "ambient_heat": 2.0, "hydrogen": 0.5},
        primary_carrier_in="electricity",
    )
    with pytest.raises(ValueError, match="secondary carriers"):
        build_ratio_math([tech])


def test_zero_primary_ratio_raises() -> None:
    # build_ratio_math() itself only looks at *which* carriers are present
    # (to generate constraint structure); the actual ratio value -- and
    # this bound -- is computed by carrier_flow_ratios(), which modern.py
    # calls separately to set the value on each tech's own body. See its
    # docstring for why the two are split.
    tech = _spec(
        carriers_in={"electricity": 0.0, "ambient_heat": 2.0},
        primary_carrier_in="electricity",
    )
    with pytest.raises(ValueError, match="zero flow ratio"):
        carrier_flow_ratios(tech)


def test_negative_ratio_raises() -> None:
    tech = _spec(
        carriers_in={"electricity": 1.0, "ambient_heat": -2.0},
        primary_carrier_in="electricity",
    )
    with pytest.raises(ValueError, match="out of range"):
        carrier_flow_ratios(tech)
