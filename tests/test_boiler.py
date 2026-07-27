from __future__ import annotations

import pytest

from conversion_technologies import new  # noqa: F401
from conversion_technologies.core.carriers import (
    BIOMASS,
    ELECTRICITY,
    HEAT,
    NATURAL_GAS,
)
from conversion_technologies.core.registry import get_technology
from conversion_technologies.new.boiler.generic.thermal_efficiency import (
    derated_efficiency,
)
from conversion_technologies.new.boiler.specific import _build


def _valid_row(**overrides: object) -> dict:
    row = {
        "category": "boiler",
        "variant": "electric",
        "scale": "household",
        "name": "Test boiler",
        "color": "#000000",
        "carrier_in": "electricity",
        "carrier_in_2": None,
        "flow_cap_min": None,
        "flow_cap_max": 10.0,
        "lifetime": 20.0,
        "efficiency": 0.95,
        "part_load_factor": None,
        "cost_flow_cap": 100.0,
        "cost_om_annual": None,
        "cost_flow_in": None,
        "cost_flow_out": None,
        "cost_interest_rate": 0.10,
    }
    row.update(overrides)
    return row


def test_electric_boiler_is_near_unity_efficiency() -> None:
    tech = get_technology("boiler_electric_household")
    assert tech.carriers_in == {ELECTRICITY: 1.0}
    assert tech.carriers_out[HEAT] > 0.95
    assert tech.variant == "electric"
    # electricity's own cost is left to a separate supply tech, not this one
    assert "cost_flow_in" not in tech.params
    assert tech.params["cost_interest_rate"] == pytest.approx(0.10)


def test_gas_boiler_uses_natural_gas() -> None:
    tech = get_technology("boiler_gas_building")
    assert tech.carriers_in == {NATURAL_GAS: 1.0}
    assert HEAT in tech.carriers_out
    assert tech.variant == "gas"
    assert tech.params["cost_flow_in"] == pytest.approx(0.04)


def test_biomass_boiler_uses_biomass() -> None:
    tech = get_technology("boiler_biomass_community")
    assert tech.carriers_in == {BIOMASS: 1.0}
    assert tech.flow_cap_max > 0
    assert tech.variant == "biomass"
    assert tech.params["cost_flow_in"] == pytest.approx(0.035)


@pytest.mark.parametrize("scale", ["household", "building", "community"])
def test_all_boiler_scales_build_a_valid_spec(scale: str) -> None:
    for base, variant in (
        ("boiler_electric", "electric"),
        ("boiler_gas", "gas"),
        ("boiler_biomass", "biomass"),
    ):
        tech = get_technology(f"{base}_{scale}")
        assert tech.scale == scale
        assert tech.category == "boiler"
        assert tech.variant == variant
        assert tech.lifetime > 0
        assert tech.cost_flow_cap > 0
        assert "flow_ramping" not in tech.params  # not modeled for boilers


def test_build_rejects_efficiency_below_the_engineering_bound() -> None:
    with pytest.raises(ValueError, match="efficiency"):
        _build(_valid_row(efficiency=0.5))


def test_build_rejects_efficiency_above_the_engineering_bound() -> None:
    with pytest.raises(ValueError, match="efficiency"):
        _build(_valid_row(efficiency=1.0))


def test_build_rejects_capacity_above_the_scale_ceiling() -> None:
    with pytest.raises(ValueError, match="ceiling"):
        _build(_valid_row(scale="household", flow_cap_max=100_000.0))


def test_build_accepts_a_valid_row() -> None:
    tech = _build(_valid_row())
    assert tech.id == "boiler_electric_household"


def test_derated_efficiency_bonus_is_capped_at_one() -> None:
    assert derated_efficiency(0.99, part_load_factor=0.5) <= 1.0


def test_derated_efficiency_full_load_is_unchanged() -> None:
    assert derated_efficiency(0.9, part_load_factor=1.0) == pytest.approx(0.9)


def test_derated_efficiency_rejects_out_of_range_inputs() -> None:
    with pytest.raises(ValueError):
        derated_efficiency(1.5)
    with pytest.raises(ValueError):
        derated_efficiency(0.9, part_load_factor=0.0)
