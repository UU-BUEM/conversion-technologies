"""Hourly PV output per kW of DC capacity: NREL PVWatts v8 through NREL-PySAM.

Kept identical to EnerPlanET's PV service (``enerplanet/pysam-pv``,
``pv_service/simulate.py``) so that a profile computed here and one served
there are the same numbers:

- the same PySAM module (``Pvwattsv8``) and version (NREL-PySAM 7.1.1);
- the same weather variables (``T``, ``DHI``, ``DNI``, ``WS_10M``) with
  timestamps read as UTC (``tz = 0``) at whatever minute they sit
  (MERRA-2 stamps at half past);
- the same filling of missing values (irradiance -> 0, temperature and
  wind -> previous value, or the first valid one at the start);
- the same system-design mapping and defaults (losses 0.14, DC/AC ratio
  1.1, inverter efficiency 0.96, ``standard`` module, ``roof`` mounting),
  read here from ``generation_technologies/technologies.csv``;
- the same handling of a leap year (each calendar year runs without
  29 February, and that day runs on its own).

``tests/test_pv.py`` checks this against a pinned copy of pysam-pv's own
``simulate.py`` on its MERRA-2 2018 test weather.

Weather comes from the UU-BUEM ``weather`` package's
``get_point_weather(..., wind=True)`` (:func:`fetch_weather`); the 10 m
wind speed only sets the module temperature. Nothing here downloads or
derives weather.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: Weather variables PVWatts reads, by the ``weather`` package's names.
WEATHER_VARIABLES = ("T", "DHI", "DNI", "WS_10M")
_IRRADIANCE = ("DHI", "DNI")

#: PVWatts ``module_type`` and ``array_type`` codes (as in pysam-pv).
MODULE_TYPES = {"standard": 0, "premium": 1, "thin_film": 2}
MOUNTINGS = {"open_rack": 0, "roof": 1}


@dataclass(frozen=True)
class PVArray:
    """One PV array: a roof (or wall) face with its modules and inverter.

    ``capacity_kw`` is the DC nameplate. ``tilt`` in degrees from
    horizontal, ``azimuth`` clockwise from north (180 = south).
    """

    id: str
    tilt: float
    azimuth: float
    capacity_kw: float = 1.0
    losses: float = 0.14
    dc_ac_ratio: float = 1.1
    inverter_efficiency: float = 0.96
    module_type: str = "standard"
    mounting: str = "roof"

    def __post_init__(self) -> None:
        checks = (
            ("capacity_kw", self.capacity_kw, 0.001, 100_000),
            ("tilt", self.tilt, 0, 90),
            ("azimuth", self.azimuth, 0, 360),
            ("losses", self.losses, 0, 0.99),
            ("dc_ac_ratio", self.dc_ac_ratio, 0.5, 2.0),
            ("inverter_efficiency", self.inverter_efficiency, 0.9, 0.995),
        )
        for name, value, lo, hi in checks:
            if not lo <= value <= hi:
                raise ValueError(
                    f"PV array {self.id!r}: {name}={value} outside [{lo}, {hi}]."
                )
        if self.module_type not in MODULE_TYPES:
            raise ValueError(
                f"PV array {self.id!r}: module_type must be one of {sorted(MODULE_TYPES)}."
            )
        if self.mounting not in MOUNTINGS:
            raise ValueError(
                f"PV array {self.id!r}: mounting must be one of {sorted(MOUNTINGS)}."
            )


def array_defaults(row: dict[str, Any]) -> dict[str, Any]:
    """The PVWatts settings of a ``technologies.csv`` PV row, as
    :class:`PVArray` keyword arguments."""
    return {
        "losses": float(row["losses"]),
        "dc_ac_ratio": float(row["dc_ac_ratio"]),
        "inverter_efficiency": float(row["inverter_efficiency"]),
        "module_type": str(row["module_type"]),
        "mounting": str(row["mounting"]),
    }


def fetch_weather(
    latitude: float,
    longitude: float,
    year: int,
    *,
    provider: str = "era5-land",
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """``T``, ``DHI``, ``DNI``, ``WS_10M`` for one location and year from the
    UU-BUEM ``weather`` package (``get_point_weather(..., wind=True)``,
    weather >= 1.11: T, GHI, DHI, DNI plus the 10 m wind speed)."""
    from weather import get_point_weather

    try:
        return get_point_weather(
            latitude,
            longitude,
            year,
            provider=provider,
            data_dir=data_dir,
            wind=True,
        )
    except TypeError as exc:
        raise ImportError(
            "PV profiles need the 10 m wind speed from the weather "
            "package (get_point_weather(..., wind=True), weather >= 1.11) "
            "for the module temperature; the installed weather is older. "
            "Pass a weather "
            "DataFrame with T, DHI, DNI and WS_10M to pv_capacity_factors() "
            "instead."
        ) from exc


def _filled(weather: pd.DataFrame) -> tuple[dict[str, list[float]], int]:
    """pysam-pv's null filling: irradiance -> 0; temperature and wind -> the
    previous value, or the first valid one at the start."""
    missing = [name for name in WEATHER_VARIABLES if name not in weather]
    if missing:
        raise ValueError(
            f"PV profile needs weather variables {list(WEATHER_VARIABLES)}; "
            f"missing {missing}."
        )
    values: dict[str, list[float]] = {}
    filled = 0
    for name in WEATHER_VARIABLES:
        series = pd.to_numeric(weather[name], errors="raise").astype(float)
        nulls = int(series.isna().sum())
        filled += nulls
        if name in _IRRADIANCE:
            series = series.fillna(0.0)
        else:
            if series.notna().sum() == 0:
                raise ValueError(f"weather variable {name} has no values")
            series = series.ffill().fillna(series.dropna().iloc[0])
        values[name] = series.tolist()
    return values, filled


def _run(
    latitude: float,
    longitude: float,
    elevation_m: float,
    stamps: Sequence[pd.Timestamp],
    values: dict[str, list[float]],
    positions: list[int],
    array: PVArray,
) -> list[float]:
    import PySAM.Pvwattsv8 as pvwatts

    chosen = [stamps[i] for i in positions]
    pick = lambda name: [values[name][i] for i in positions]  # noqa: E731
    model = pvwatts.new()
    model.SolarResource.solar_resource_data = {
        "lat": latitude,
        "lon": longitude,
        "tz": 0,
        "elev": elevation_m,
        "year": [s.year for s in chosen],
        "month": [s.month for s in chosen],
        "day": [s.day for s in chosen],
        "hour": [s.hour for s in chosen],
        "minute": [s.minute for s in chosen],
        "dn": pick("DNI"),
        "df": pick("DHI"),
        "tdry": pick("T"),
        "wspd": pick("WS_10M"),
    }
    design = model.SystemDesign
    design.system_capacity = array.capacity_kw
    design.tilt = array.tilt
    design.azimuth = array.azimuth
    design.array_type = MOUNTINGS[array.mounting]
    design.module_type = MODULE_TYPES[array.module_type]
    design.dc_ac_ratio = array.dc_ac_ratio
    design.inv_eff = array.inverter_efficiency * 100
    design.losses = array.losses * 100
    model.execute()
    ac_w = model.Outputs.ac
    if len(ac_w) != len(positions):
        raise RuntimeError(
            f"PVWatts returned {len(ac_w)} values for {len(positions)} hours of array {array.id}"
        )
    return [max(0.0, w / 1000) for w in ac_w]


def _run_groups(stamps: Sequence[pd.Timestamp]) -> list[list[int]]:
    """Consecutive positions per (year, is 29 February), as pysam-pv runs
    them: PVWatts drops one day of a leap-year series."""
    groups: list[list[int]] = []
    last_key: tuple[int, bool] | None = None
    for position, stamp in enumerate(stamps):
        key = (stamp.year, (stamp.month, stamp.day) == (2, 29))
        if key != last_key:
            groups.append([])
            last_key = key
        groups[-1].append(position)
    return groups


def simulate_ac_kw(
    weather: pd.DataFrame,
    latitude: float,
    longitude: float,
    array: PVArray,
    *,
    elevation_m: float = 0.0,
) -> pd.Series:
    """AC output in kW of ``array`` for every weather timestamp.

    ``weather`` has a ``DatetimeIndex`` read as UTC (tz-naive, or tz-aware
    and converted) and the columns ``T`` (degC), ``DHI``, ``DNI`` (W/m2)
    and ``WS_10M`` (m/s).
    """
    index = pd.DatetimeIndex(weather.index)
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    stamps = list(index)
    values, _ = _filled(weather)
    ac: list[float] = []
    for positions in _run_groups(stamps):
        ac.extend(
            _run(latitude, longitude, elevation_m, stamps, values, positions, array)
        )
    return pd.Series(ac, index=weather.index, name=array.id)


def pv_capacity_factors(
    weather: pd.DataFrame,
    latitude: float,
    longitude: float,
    arrays: Iterable[PVArray],
    *,
    elevation_m: float = 0.0,
) -> pd.DataFrame:
    """AC output per kW of DC capacity (kW/kWp) per array, one column each:
    pysam-pv's ``capacity_factor``."""
    columns = {}
    for array in arrays:
        unit = PVArray(**{**array.__dict__, "capacity_kw": 1.0})
        columns[array.id] = simulate_ac_kw(
            weather, latitude, longitude, unit, elevation_m=elevation_m
        )
    frame = pd.DataFrame(columns, index=weather.index)
    return frame.clip(lower=0.0).astype(np.float64)
