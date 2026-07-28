from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conversion_technologies import new  # noqa: F401  (registers technologies)
from conversion_technologies.new.heat_pump.weather_cop import (
    build_cop_data_tables,
    compute_hourly_cop,
    export_weather_cop,
)


def test_compute_hourly_cop_matches_carnot_formula() -> None:
    index = pd.date_range("2018-01-01", periods=3, freq="h")
    temps = pd.Series([2.0, 5.0, 10.0], index=index)
    cop = compute_hourly_cop(
        temps, sink_temp_c=45.0, quality_factor=0.45, tech_id="test"
    )
    assert len(cop) == 3
    assert cop.iloc[0] < cop.iloc[2]  # colder source -> lower COP


def test_compute_hourly_cop_rejects_a_nan_hour() -> None:
    index = pd.date_range("2018-01-01", periods=2, freq="h")
    temps = pd.Series([2.0, 50.0], index=index)  # 50C source > 45C sink for one hour
    with pytest.raises(ValueError, match="NaN"):
        compute_hourly_cop(temps, sink_temp_c=45.0, quality_factor=0.45, tech_id="test")


def test_compute_hourly_cop_rejects_an_out_of_bound_value() -> None:
    index = pd.date_range("2018-01-01", periods=1, freq="h")
    temps = pd.Series([44.99], index=index)  # near-zero sink/source gap -> absurd COP
    with pytest.raises(ValueError, match="out of range"):
        compute_hourly_cop(temps, sink_temp_c=45.0, quality_factor=1.0, tech_id="test")


def test_build_cop_data_tables_shape() -> None:
    block = build_cop_data_tables(
        "heat_pump_electric_household",
        "ambient_heat",
        flow_out_eff_csv="a.csv",
        flow_in_eff_csv="b.csv",
    )
    tables = block["data_tables"]
    out_entry = tables["heat_pump_electric_household_flow_out_eff"]
    in_entry = tables["heat_pump_electric_household_flow_in_eff"]
    assert out_entry["add_dims"]["carriers"] == "heat"
    assert out_entry["add_dims"]["inputs"] == "flow_out_eff"
    assert in_entry["add_dims"]["carriers"] == "ambient_heat"
    assert in_entry["add_dims"]["inputs"] == "flow_in_eff"
    assert "nodes" not in out_entry["add_dims"]  # this package has no node concept


def test_export_weather_cop_end_to_end(tmp_path: Path) -> None:
    index = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:00:00", freq="h")
    rng = np.random.default_rng(0)
    # heat_pump_electric_household's design sink is 45C -- stay well under it
    # everywhere so every hour yields a finite, in-range COP.
    temps = (
        8.0
        + 5.0 * np.sin(np.linspace(0, 2 * np.pi, len(index)))
        + rng.normal(0, 0.1, len(index))
    )
    weather_csv = tmp_path / "weather.csv"
    pd.DataFrame({"T": temps}, index=index).rename_axis("datetime").to_csv(weather_csv)

    output_dir = tmp_path / "out"
    paths = export_weather_cop(
        "heat_pump_electric_household", weather_csv, output_dir, year=2018
    )
    assert paths["flow_out_eff_csv"].exists()
    assert paths["flow_in_eff_csv"].exists()
    assert paths["data_tables_yaml"].exists()

    cop = pd.read_csv(paths["flow_out_eff_csv"], index_col=0)["flow_out_eff"]
    assert len(cop) == 8760
    assert (cop >= 1).all() and (cop <= 20).all()

    flow_in = pd.read_csv(paths["flow_in_eff_csv"], index_col=0)["flow_in_eff"]
    assert flow_in.iloc[0] == pytest.approx(cop.iloc[0] - 1.0)


def test_export_weather_cop_rejects_a_non_heat_pump_id(tmp_path: Path) -> None:
    index = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:00:00", freq="h")
    weather_csv = tmp_path / "weather.csv"
    pd.DataFrame({"T": [5.0] * len(index)}, index=index).rename_axis("datetime").to_csv(
        weather_csv
    )
    with pytest.raises(ValueError, match="input carrier"):
        export_weather_cop(
            "boiler_gas_household", weather_csv, tmp_path / "out", year=2018
        )
