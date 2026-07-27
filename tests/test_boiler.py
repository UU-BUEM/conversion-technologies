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


def test_electric_boiler_is_near_unity_efficiency() -> None:
    tech = get_technology("boiler_electric_household")
    assert tech.carriers_in == {ELECTRICITY: 1.0}
    assert tech.carriers_out[HEAT] > 0.95


def test_gas_boiler_uses_natural_gas() -> None:
    tech = get_technology("boiler_gas_building")
    assert tech.carriers_in == {NATURAL_GAS: 1.0}
    assert HEAT in tech.carriers_out


def test_biomass_boiler_uses_biomass() -> None:
    tech = get_technology("boiler_biomass_community")
    assert tech.carriers_in == {BIOMASS: 1.0}
    assert tech.flow_cap_max > 0


@pytest.mark.parametrize("scale", ["household", "building", "community"])
def test_all_boiler_scales_build_a_valid_spec(scale: str) -> None:
    for base in ("boiler_electric", "boiler_gas", "boiler_biomass"):
        tech = get_technology(f"{base}_{scale}")
        assert tech.scale == scale
        assert tech.category == "boiler"
        assert tech.lifetime > 0
        assert tech.cost_flow_cap > 0


def test_derated_efficiency_bonus_is_capped_at_one() -> None:
    assert derated_efficiency(0.99, part_load_factor=0.5) <= 1.0


def test_derated_efficiency_full_load_is_unchanged() -> None:
    assert derated_efficiency(0.9, part_load_factor=1.0) == pytest.approx(0.9)


def test_derated_efficiency_rejects_out_of_range_inputs() -> None:
    with pytest.raises(ValueError):
        derated_efficiency(1.5)
    with pytest.raises(ValueError):
        derated_efficiency(0.9, part_load_factor=0.0)
