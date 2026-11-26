"""Roof faces -> PV arrays and the building's PV potential.

Input: a building's roof faces as buem exports them (``roof_faces`` in
buem's region summary): ``[{"id", "tilt", "azimuth", "area_m2"}]``, tilt 0 =
flat, azimuth clockwise from north (180 = south). buem supplies the
geometry only; which faces carry PV and how much is decided here.

Rules (parameters per technology in ``technologies.csv``, assumptions
documented in ``docs/sources/parameter_sources.csv``):

- a face smaller than ``min_face_area_m2`` (dormers, ridges) is skipped;
- a face flatter than ``flat_roof_max_tilt`` gets a rack at
  ``flat_roof_tilt``, facing ``flat_roof_azimuth``;
- a pitched face pointing more than ``max_azimuth_from_south_deg`` away
  from south (i.e. towards north) is skipped;
- each remaining face can hold ``area x roof_usable_fraction x
  kwp_per_m2`` kWp.

A building's profile is the capacity-weighted mean of its faces' profiles:
the optimiser sizes one PV capacity per building, spread over the usable
faces in proportion to their potential (it does not fill the best face
first).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from conversion_technologies.generation_technologies.pv.pvwatts import (
    PVArray,
    array_defaults,
    pv_capacity_factors,
)
from conversion_technologies.generation_technologies.pv.specific import pv_row


@dataclass(frozen=True)
class RoofPV:
    """The PV a roof can carry: one array per usable face (``capacity_kw``
    = that face's potential) and their total."""

    arrays: tuple[PVArray, ...]

    @property
    def max_capacity_kwp(self) -> float:
        return sum(array.capacity_kw for array in self.arrays)


def _azimuth_from_south(azimuth: float) -> float:
    return abs(((azimuth - 180.0) + 180.0) % 360.0 - 180.0)


def roof_pv(
    faces: Iterable[Mapping[str, Any]], technology_id: str = "pv_rooftop_household"
) -> RoofPV:
    """The arrays ``faces`` can carry under ``technology_id``'s rules."""
    row = pv_row(technology_id)
    defaults = array_defaults(row)
    arrays = []
    for position, face in enumerate(faces):
        area = face.get("area_m2")
        tilt = face.get("tilt")
        if area is None or tilt is None or float(area) < float(row["min_face_area_m2"]):
            continue
        tilt = float(tilt)
        if tilt < float(row["flat_roof_max_tilt"]):
            tilt, azimuth = (
                float(row["flat_roof_tilt"]),
                float(row["flat_roof_azimuth"]),
            )
        else:
            if face.get("azimuth") is None:
                continue
            azimuth = float(face["azimuth"]) % 360.0
            if _azimuth_from_south(azimuth) > float(row["max_azimuth_from_south_deg"]):
                continue
        capacity = (
            float(area) * float(row["roof_usable_fraction"]) * float(row["kwp_per_m2"])
        )
        arrays.append(
            PVArray(
                id=str(face.get("id", f"face_{position}")),
                tilt=min(tilt, 90.0),
                azimuth=azimuth,
                capacity_kw=capacity,
                **defaults,
            )
        )
    return RoofPV(tuple(arrays))


def building_capacity_factor(
    weather: pd.DataFrame,
    latitude: float,
    longitude: float,
    roof: RoofPV,
    *,
    elevation_m: float = 0.0,
) -> pd.Series:
    """The building's AC output per kWp: its faces' profiles weighted by
    their potential. All zeros when the roof has no usable face."""
    if not roof.arrays:
        return pd.Series(0.0, index=weather.index, name="pv_capacity_factor")
    factors = pv_capacity_factors(
        weather, latitude, longitude, roof.arrays, elevation_m=elevation_m
    )
    weights = pd.Series({array.id: array.capacity_kw for array in roof.arrays})
    combined = factors.mul(weights, axis=1).sum(axis=1) / weights.sum()
    return combined.rename("pv_capacity_factor")
