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
from conversion_technologies.new.combined_heat_and_power.generic.alpha_beta import (
    power_to_heat_ratio,
    validate_dispatch_factors,
)


def test_power_to_heat_ratio_is_alpha_over_beta() -> None:
    assert power_to_heat_ratio(alpha=0.36, beta=0.54) == pytest.approx(0.36 / 0.54)


def test_validate_dispatch_factors_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        validate_dispatch_factors(alpha=1.5, beta=0.5)
    with pytest.raises(ValueError):
        validate_dispatch_factors(alpha=0.0, beta=0.5)
    with pytest.raises(ValueError):
        validate_dispatch_factors(alpha=0.6, beta=0.6)  # sums to > 1.0


def test_gas_chp_produces_electricity_and_heat_from_natural_gas() -> None:
    tech = get_technology("chp_gas_building")
    assert tech.carriers_in == {NATURAL_GAS: 1.0}
    assert set(tech.carriers_out) == {ELECTRICITY, HEAT}
    assert tech.primary_carrier_out == ELECTRICITY


def test_biomass_chp_produces_electricity_and_heat_from_biomass() -> None:
    tech = get_technology("chp_biomass_community")
    assert tech.carriers_in == {BIOMASS: 1.0}
    assert set(tech.carriers_out) == {ELECTRICITY, HEAT}


def test_chp_dispatch_factors_are_used_directly_as_carrier_ratios() -> None:
    tech = get_technology("chp_gas_household")
    assert tech.carriers_out[ELECTRICITY] == pytest.approx(0.3375)
    assert tech.carriers_out[HEAT] == pytest.approx(0.5625)


def test_chp_total_efficiency_never_exceeds_one() -> None:
    for tech_id in ("chp_gas_household", "chp_biomass_household"):
        tech = get_technology(tech_id)
        assert sum(tech.carriers_out.values()) <= 1.0
