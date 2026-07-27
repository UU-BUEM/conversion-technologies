from __future__ import annotations

import numpy as np
import pytest

from conversion_technologies import new  # noqa: F401
from conversion_technologies.core.carriers import (
    AMBIENT_HEAT,
    ELECTRICITY,
    GROUND_HEAT,
    HEAT,
)
from conversion_technologies.core.registry import get_technology
from conversion_technologies.new.heat_pump.generic.cop_calculation import carnot_cop
from conversion_technologies.new.heat_pump.specific import _build


def _valid_row(**overrides: object) -> dict:
    row = {
        "category": "heat_pump",
        "variant": "electric",
        "scale": "household",
        "name": "Test heat pump",
        "color": "#000000",
        "carrier_in": "electricity",
        "carrier_in_2": "ambient_heat",
        "flow_cap_min": None,
        "flow_cap_max": 10.0,
        "lifetime": 18.0,
        "efficiency": 0.45,
        "part_load_factor": None,
        "design_source_temp_c": 2.0,
        "design_sink_temp_c": 45.0,
        "cost_flow_cap": 900.0,
        "cost_om_annual": None,
        "cost_flow_in": None,
        "cost_flow_out": None,
        "cost_interest_rate": 0.10,
    }
    row.update(overrides)
    return row


def test_carnot_cop_matches_hand_calculation() -> None:
    # COP = eta * T_sink_K / (T_sink_K - T_source_K)
    cop = carnot_cop(t_source_c=2.0, t_sink_c=45.0, carnot_efficiency=0.45)
    expected = 0.45 * (45.0 + 273.15) / ((45.0 + 273.15) - (2.0 + 273.15))
    assert cop == pytest.approx(expected)


def test_carnot_cop_rejects_non_positive_temperature_gap_for_scalar_input() -> None:
    with pytest.raises(ValueError):
        carnot_cop(t_source_c=50.0, t_sink_c=45.0, carnot_efficiency=0.45)


def test_carnot_cop_rejects_out_of_range_efficiency() -> None:
    with pytest.raises(ValueError):
        carnot_cop(t_source_c=2.0, t_sink_c=45.0, carnot_efficiency=1.5)


def test_carnot_cop_accepts_an_array_of_temperatures() -> None:
    # e.g. a real hourly 'T' series from the weather module's CsvWeatherData.
    t_series = np.array([2.0, 5.0, 10.0])
    cop = carnot_cop(t_series, t_sink_c=45.0, carnot_efficiency=0.45)
    assert cop.shape == (3,)
    assert cop[0] == pytest.approx(carnot_cop(2.0, 45.0, 0.45))
    # colder source -> smaller sink/source gap -> lower COP
    assert cop[0] < cop[2]


def test_carnot_cop_array_input_returns_nan_when_source_exceeds_sink() -> None:
    t_series = np.array([2.0, 50.0])  # 50C source > 45C sink for one entry
    cop = carnot_cop(t_series, t_sink_c=45.0, carnot_efficiency=0.45)
    assert np.isfinite(cop[0])
    assert np.isnan(cop[1])


def test_electric_heat_pump_uses_ambient_heat_and_electricity() -> None:
    tech = get_technology("heat_pump_electric_household")
    assert set(tech.carriers_in) == {ELECTRICITY, AMBIENT_HEAT}
    assert tech.carriers_in[ELECTRICITY] == 1.0
    assert list(tech.carriers_out) == [HEAT]
    assert tech.variant == "electric"
    # heat out / electricity in must equal the technology's own COP
    cop = tech.carriers_out[HEAT]
    assert tech.carriers_in[AMBIENT_HEAT] == pytest.approx(cop - 1.0)


def test_geothermal_heat_pump_uses_ground_heat() -> None:
    tech = get_technology("heat_pump_geothermal_building")
    assert GROUND_HEAT in tech.carriers_in
    assert tech.carriers_in[ELECTRICITY] == 1.0
    assert tech.variant == "geothermal"


def test_geothermal_cop_exceeds_air_source_cop_at_same_scale() -> None:
    air = get_technology("heat_pump_electric_household")
    ground = get_technology("heat_pump_geothermal_household")
    assert ground.carriers_out[HEAT] > air.carriers_out[HEAT]


def test_heat_pumps_have_no_fuel_cost_or_ramping_by_default() -> None:
    for tech_id in ("heat_pump_electric_household", "heat_pump_geothermal_building"):
        tech = get_technology(tech_id)
        assert "cost_flow_in" not in tech.params
        assert "flow_ramping" not in tech.params
        assert tech.params["cost_interest_rate"] == pytest.approx(0.10)


def test_build_rejects_a_quality_factor_above_the_carnot_limit() -> None:
    with pytest.raises(ValueError, match="efficiency"):
        _build(_valid_row(efficiency=1.5))


def test_build_rejects_a_computed_cop_above_the_sanity_bound() -> None:
    # A near-zero sink/source gap drives COP arbitrarily high -- must be caught.
    with pytest.raises(ValueError, match="cop"):
        _build(_valid_row(efficiency=1.0, design_source_temp_c=44.9))


def test_build_rejects_capacity_above_the_scale_ceiling() -> None:
    with pytest.raises(ValueError, match="ceiling"):
        _build(_valid_row(scale="household", flow_cap_max=100_000.0))


def test_build_accepts_a_valid_row() -> None:
    tech = _build(_valid_row())
    assert tech.id == "heat_pump_electric_household"
