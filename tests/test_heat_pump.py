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
    # heat out / electricity in must equal the technology's own COP
    cop = tech.carriers_out[HEAT]
    assert tech.carriers_in[AMBIENT_HEAT] == pytest.approx(cop - 1.0)


def test_geothermal_heat_pump_uses_ground_heat() -> None:
    tech = get_technology("heat_pump_geothermal_building")
    assert GROUND_HEAT in tech.carriers_in
    assert tech.carriers_in[ELECTRICITY] == 1.0


def test_geothermal_cop_exceeds_air_source_cop_at_same_scale() -> None:
    air = get_technology("heat_pump_electric_household")
    ground = get_technology("heat_pump_geothermal_household")
    assert ground.carriers_out[HEAT] > air.carriers_out[HEAT]
