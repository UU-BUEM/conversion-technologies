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
    match_seasonal_cop,
    seasonal_cop,
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
        flow_out_eff_csv="a.csv",
        carrier_flow_ratio_in_csv="b.csv",
    )
    tables = block["data_tables"]
    out_entry = tables["heat_pump_electric_household_flow_out_eff"]
    ratio_entry = tables["heat_pump_electric_household_carrier_flow_ratio_in"]
    assert out_entry["add_dims"]["carriers"] == "heat"
    assert out_entry["add_dims"]["inputs"] == "flow_out_eff"
    # The ratio math reads carrier_flow_ratio_in (COP - 1), per technology.
    assert ratio_entry["add_dims"] == {
        "techs": "heat_pump_electric_household",
        "inputs": "carrier_flow_ratio_in",
    }
    assert "nodes" not in out_entry["add_dims"]  # this package has no node concept


def _synthetic_weather_df(year: int = 2018) -> pd.DataFrame:
    index = pd.date_range(f"{year}-01-01 00:00:00", f"{year}-12-31 23:00:00", freq="h")
    rng = np.random.default_rng(0)
    # heat_pump_electric_household's design sink is 45C -- stay well under it
    # everywhere so every hour yields a finite, in-range COP.
    temps = (
        8.0
        + 5.0 * np.sin(np.linspace(0, 2 * np.pi, len(index)))
        + rng.normal(0, 0.1, len(index))
    )
    return pd.DataFrame({"T": temps, "GHI": 0.0, "DHI": 0.0, "DNI": 0.0}, index=index)


def test_export_weather_cop_end_to_end(tmp_path: Path, monkeypatch) -> None:
    calls = {}

    def fake_get_point_weather(
        latitude,
        longitude,
        year,
        *,
        provider="era5-land",
        data_dir=None,
    ):
        calls["args"] = (latitude, longitude, year, provider, data_dir)
        return _synthetic_weather_df(year)

    monkeypatch.setattr(
        "conversion_technologies.new.heat_pump.weather_cop.get_point_weather",
        fake_get_point_weather,
    )

    output_dir = tmp_path / "out"
    paths = export_weather_cop(
        "heat_pump_electric_household",
        output_dir,
        latitude=52.09,
        longitude=5.12,
        year=2018,
    )
    assert calls["args"] == (52.09, 5.12, 2018, "era5-land", None)
    assert paths["flow_out_eff_csv"].exists()
    assert paths["carrier_flow_ratio_in_csv"].exists()
    assert paths["data_tables_yaml"].exists()

    cop = pd.read_csv(paths["flow_out_eff_csv"], index_col=0)["flow_out_eff"]
    assert len(cop) == 8760
    assert (cop >= 1).all() and (cop <= 20).all()

    ratio = pd.read_csv(paths["carrier_flow_ratio_in_csv"], index_col=0)[
        "carrier_flow_ratio_in"
    ]
    assert ratio.iloc[0] == pytest.approx(cop.iloc[0] - 1.0)


def test_export_weather_cop_rejects_a_non_heat_pump_id(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "conversion_technologies.new.heat_pump.weather_cop.get_point_weather",
        lambda *args, **kwargs: _synthetic_weather_df(),
    )
    with pytest.raises(ValueError, match="input carrier"):
        export_weather_cop(
            "boiler_gas_household",
            tmp_path / "out",
            latitude=52.09,
            longitude=5.12,
            year=2018,
        )


def test_match_seasonal_cop_hits_the_target_and_keeps_the_shape() -> None:
    index = pd.date_range("2018-01-01", periods=4, freq="h")
    cop = pd.Series([2.0, 3.0, 4.0, 6.0], index=index)
    heat = pd.Series([4.0, 2.0, 1.0, 0.0], index=index)  # cold hours weigh most
    scaled, factor = match_seasonal_cop(cop, heat, target=3.3)
    assert seasonal_cop(scaled, heat) == pytest.approx(3.3)
    assert (scaled / cop).round(12).nunique() == 1  # one factor: shape kept
    assert factor == pytest.approx(3.3 / seasonal_cop(cop, heat))


def test_seasonal_cop_is_heat_weighted() -> None:
    index = pd.date_range("2018-01-01", periods=2, freq="h")
    cop = pd.Series([2.0, 4.0], index=index)
    heat = pd.Series([2.0, 2.0], index=index)
    # 4 kWh heat for 1 + 0.5 kWh electricity
    assert seasonal_cop(cop, heat) == pytest.approx(4.0 / 1.5)


def test_export_weather_cop_matches_the_design_seasonal_cop(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "conversion_technologies.new.heat_pump.weather_cop.get_point_weather",
        lambda *args, **kwargs: _synthetic_weather_df(),
    )
    weather = _synthetic_weather_df()
    heat = (20.0 - weather["T"]).clip(lower=0.0).rename("heat_kW")
    heat_csv = tmp_path / "heat.csv"
    heat.rename_axis("timesteps").to_csv(heat_csv)
    paths = export_weather_cop(
        "heat_pump_electric_household",
        tmp_path / "out",
        latitude=52.1,
        longitude=6.0,
        year=2018,
        match_seasonal_heat=heat_csv,
    )
    cop = pd.read_csv(paths["flow_out_eff_csv"], index_col=0)["flow_out_eff"]
    cop.index = heat.index
    import json

    calibration = json.loads(paths["calibration_json"].read_text())
    assert seasonal_cop(cop, heat) == pytest.approx(calibration["design_cop"])
    assert calibration["seasonal_cop_after"] == pytest.approx(calibration["design_cop"])


def test_export_weather_cop_rejects_weights_missing_hours(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "conversion_technologies.new.heat_pump.weather_cop.get_point_weather",
        lambda *args, **kwargs: _synthetic_weather_df(),
    )
    short = _synthetic_weather_df()["T"].iloc[:100].rename("heat_kW")
    heat_csv = tmp_path / "heat.csv"
    short.rename_axis("timesteps").to_csv(heat_csv)
    with pytest.raises(ValueError, match="do not cover"):
        export_weather_cop(
            "heat_pump_electric_household",
            tmp_path / "out",
            latitude=52.1,
            longitude=6.0,
            year=2018,
            match_seasonal_heat=heat_csv,
        )
