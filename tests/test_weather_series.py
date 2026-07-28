from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from conversion_technologies.core.weather_series import (
    align_to_year,
    read_hourly_series,
)


def _write_csv(
    path: Path, index: pd.DatetimeIndex, values: list[float], column: str = "T"
) -> None:
    pd.DataFrame({column: values}, index=index).rename_axis("datetime").to_csv(path)


def test_read_hourly_series_happy_path(tmp_path: Path) -> None:
    index = pd.date_range("2018-01-01", periods=5, freq="h")
    path = tmp_path / "weather.csv"
    _write_csv(path, index, [1.0, 2.0, 3.0, 4.0, 5.0])
    series = read_hourly_series(path, column="T")
    assert len(series) == 5
    assert series.iloc[0] == pytest.approx(1.0)


def test_read_hourly_series_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        read_hourly_series(tmp_path / "missing.csv", column="T")


def test_read_hourly_series_missing_column_raises(tmp_path: Path) -> None:
    index = pd.date_range("2018-01-01", periods=3, freq="h")
    path = tmp_path / "weather.csv"
    _write_csv(path, index, [1.0, 2.0, 3.0], column="T")
    with pytest.raises(ValueError, match="GHI"):
        read_hourly_series(path, column="GHI")


def test_read_hourly_series_rejects_irregular_spacing(tmp_path: Path) -> None:
    index = pd.DatetimeIndex(
        ["2018-01-01 00:00", "2018-01-01 01:00", "2018-01-01 03:00"]
    )
    path = tmp_path / "weather.csv"
    _write_csv(path, index, [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="not uniformly 1 hour apart"):
        read_hourly_series(path, column="T")


def test_read_hourly_series_rejects_duplicate_timestamps(tmp_path: Path) -> None:
    index = pd.DatetimeIndex(
        ["2018-01-01 00:00", "2018-01-01 00:00", "2018-01-01 01:00"]
    )
    path = tmp_path / "weather.csv"
    _write_csv(path, index, [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="duplicate timestamps"):
        read_hourly_series(path, column="T")


def test_read_hourly_series_normalises_a_tz_aware_index(tmp_path: Path) -> None:
    index = pd.date_range("2018-01-01", periods=3, freq="h", tz="UTC")
    path = tmp_path / "weather.csv"
    _write_csv(path, index, [1.0, 2.0, 3.0])
    series = read_hourly_series(path, column="T")
    assert series.index.tz is None


def test_align_to_year_rejects_incomplete_coverage_by_default(tmp_path: Path) -> None:
    index = pd.date_range("2018-01-01", periods=3, freq="h")
    series = pd.Series([1.0, 2.0, 3.0], index=index)
    with pytest.raises(ValueError, match="covers only"):
        align_to_year(series, 2018)


def test_align_to_year_accepts_a_complete_non_leap_year() -> None:
    index = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:00:00", freq="h")
    series = pd.Series(range(len(index)), index=index, dtype=float)
    aligned = align_to_year(series, 2018)
    assert len(aligned) == 8760
    assert not aligned.isna().any()


def test_align_to_year_handles_leap_years() -> None:
    index = pd.date_range("2020-01-01 00:00:00", "2020-12-31 23:00:00", freq="h")
    series = pd.Series(range(len(index)), index=index, dtype=float)
    aligned = align_to_year(series, 2020)
    assert len(aligned) == 8784


def test_align_to_year_allows_partial_coverage_within_tolerance() -> None:
    full_index = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:00:00", freq="h")
    partial_index = full_index[:-10]  # missing the last 10 hours
    series = pd.Series(range(len(partial_index)), index=partial_index, dtype=float)
    aligned = align_to_year(series, 2018, max_missing_fraction=0.01)
    assert len(aligned) == 8760


def test_align_to_year_rejects_out_of_range_max_missing_fraction() -> None:
    index = pd.date_range("2018-01-01", periods=3, freq="h")
    series = pd.Series([1.0, 2.0, 3.0], index=index)
    with pytest.raises(ValueError, match="max_missing_fraction"):
        align_to_year(series, 2018, max_missing_fraction=1.5)
