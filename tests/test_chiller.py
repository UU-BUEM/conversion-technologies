from __future__ import annotations

import pytest

from conversion_technologies import new  # noqa: F401
from conversion_technologies.core.carriers import COOLING, ELECTRICITY, HEAT
from conversion_technologies.core.registry import get_technology
from conversion_technologies.new.chiller.specific import _build


def _valid_row(**overrides: object) -> dict:
    row = {
        "category": "chiller",
        "variant": "electric",
        "scale": "household",
        "name": "Test chiller",
        "color": "#000000",
        "carrier_in": "electricity",
        "carrier_in_2": None,
        "flow_cap_min": None,
        "flow_cap_max": 8.0,
        "lifetime": 15.0,
        "cop": 3.2,
        "aux_electricity_ratio": None,
        "cost_flow_cap": 500.0,
        "cost_om_annual": None,
        "cost_flow_in": None,
        "cost_flow_out": None,
        "cost_interest_rate": 0.10,
    }
    row.update(overrides)
    return row


def test_electric_ac_uses_electricity_only() -> None:
    tech = get_technology("chiller_electric_household")
    assert set(tech.carriers_in) == {ELECTRICITY}
    assert tech.carriers_in[ELECTRICITY] == 1.0
    assert tech.carriers_out == {COOLING: pytest.approx(3.2)}
    assert tech.variant == "electric"


def test_heat_pump_reversible_uses_electricity_only() -> None:
    tech = get_technology("chiller_heat_pump_reversible_household")
    assert set(tech.carriers_in) == {ELECTRICITY}
    assert COOLING in tech.carriers_out


def test_absorption_chiller_uses_heat_and_parasitic_electricity() -> None:
    tech = get_technology("chiller_absorption_household")
    assert set(tech.carriers_in) == {HEAT, ELECTRICITY}
    assert tech.carriers_in[HEAT] == 1.0
    assert 0 < tech.carriers_in[ELECTRICITY] < 1
    assert COOLING in tech.carriers_out
    assert tech.carriers_out[COOLING] < 1.0  # absorption COP < 1 by definition


def test_build_rejects_electric_cop_below_one() -> None:
    with pytest.raises(ValueError, match="cop"):
        _build(_valid_row(cop=0.9))


def test_build_rejects_absorption_cop_above_its_sanity_bound() -> None:
    with pytest.raises(ValueError, match="cop"):
        _build(
            _valid_row(
                variant="absorption",
                carrier_in="heat",
                carrier_in_2="electricity",
                aux_electricity_ratio=0.03,
                cop=1.5,
            )
        )


def test_build_rejects_capacity_above_the_scale_ceiling() -> None:
    with pytest.raises(ValueError, match="ceiling"):
        _build(_valid_row(scale="household", flow_cap_max=100_000.0))


def test_build_accepts_a_valid_row() -> None:
    tech = _build(_valid_row())
    assert tech.id == "chiller_electric_household"
