"""The grid package every source writes, plus shared helpers.

A grid package is a directory with:

``transformers.csv``
    One row per MV/LV station: ``trafo_id``, ``name``, ``latitude``,
    ``longitude`` (WGS84), ``rated_kva``, ``n_transformers``, ``peak_kw``,
    ``nbl_limit_kw``, ``peak_date``, ``data`` (``rated`` when the source
    gives a rating, ``geometry_only`` otherwise), ``source_id``.
``building_grid_map.csv``
    One row per building: ``building_feature_id``, ``bag_pand_id``,
    ``latitude``, ``longitude``, ``trafo_id``, ``feeder_id``,
    ``network_distance_m`` (cable length from the station),
    ``connection_distance_m`` (building centroid to the nearest cable),
    ``method`` (how the building was assigned, see ``METHODS``).
``lv_lines.geojson``
    Low-voltage cables in WGS84 with ``trafo_id``/``feeder_id``/
    ``cable_type`` (null when the source has no cable types), if the
    source has cables.
``manifest.json``
    Source, inputs, licence notes, counts and the assumptions made.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer

TRANSFORMER_COLUMNS = [
    "trafo_id",
    "name",
    "latitude",
    "longitude",
    "rated_kva",
    "n_transformers",
    "peak_kw",
    "nbl_limit_kw",
    "peak_date",
    "data",
    "source_id",
]
MAP_COLUMNS = [
    "building_feature_id",
    "bag_pand_id",
    "latitude",
    "longitude",
    "trafo_id",
    "feeder_id",
    "network_distance_m",
    "connection_distance_m",
    "method",
]
METHODS = {
    "lv_network": "shortest path along the low-voltage cables to a station",
    "provided": "assignment given by the user",
    "pylovo": "building is in a pylovo grid (polygon or nearest pylovo building)",
    "euclidean": "nearest station by straight-line distance (no cables available)",
    "euclidean_fallback": "no cable within reach, or its cable network has no station",
}

_TO_RD = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
_TO_WGS = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)


def to_rd(lon: Any, lat: Any) -> tuple[np.ndarray, np.ndarray]:
    """WGS84 lon/lat -> Dutch RD New x/y (metres)."""
    x, y = _TO_RD.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.asarray(x), np.asarray(y)


def to_wgs(x: Any, y: Any) -> tuple[np.ndarray, np.ndarray]:
    """RD New x/y -> WGS84 lat/lon (note the order: lat first)."""
    lon, lat = _TO_WGS.transform(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return np.asarray(lat), np.asarray(lon)


def load_buildings(path: Path) -> pd.DataFrame:
    """Buildings with ``building_feature_id``, ``bag_pand_id``, ``latitude``,
    ``longitude`` (buem's region summary Parquet, or any CSV with those
    columns), plus RD ``x``/``y``."""
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    needed = ["building_feature_id", "bag_pand_id", "latitude", "longitude"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path}: missing {missing}. buem's run_region_hourly.py writes these to its "
            "summary since 2026-11-25; rerun Phase 1."
        )
    df = df[needed].copy()
    if df[["latitude", "longitude"]].isna().any().any():
        raise ValueError(f"{path}: some buildings have no coordinates")
    df["x"], df["y"] = to_rd(df["longitude"], df["latitude"])
    return df.reset_index(drop=True)


def bbox_rd(
    buildings: pd.DataFrame, buffer_m: float
) -> tuple[float, float, float, float]:
    return (
        float(buildings["x"].min() - buffer_m),
        float(buildings["y"].min() - buffer_m),
        float(buildings["x"].max() + buffer_m),
        float(buildings["y"].max() + buffer_m),
    )


def nearest_station(
    points_xy: np.ndarray, stations_xy: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Index of and distance to the nearest station for each point."""
    from scipy.spatial import cKDTree

    dist, idx = cKDTree(stations_xy).query(points_xy)
    return np.asarray(idx), np.asarray(dist)


@dataclass
class GridPackage:
    source: str
    transformers: pd.DataFrame
    building_map: pd.DataFrame
    lines: list[dict[str, Any]] | None = None  # GeoJSON features, WGS84
    inputs: dict[str, Any] = field(default_factory=dict)
    licence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for name, df, cols in (
            ("transformers", self.transformers, TRANSFORMER_COLUMNS),
            ("building_map", self.building_map, MAP_COLUMNS),
        ):
            missing = [c for c in cols if c not in df.columns]
            if missing:
                raise ValueError(f"{name}: missing columns {missing}")
        if self.transformers["trafo_id"].duplicated().any():
            raise ValueError("transformers: duplicate trafo_id")
        if self.building_map["building_feature_id"].duplicated().any():
            raise ValueError("building_map: a building is assigned twice")
        unknown = set(self.building_map["trafo_id"].dropna()) - set(
            self.transformers["trafo_id"]
        )
        if unknown:
            raise ValueError(f"building_map: unknown trafo_id(s) {sorted(unknown)[:5]}")
        bad = set(self.building_map["method"]) - set(METHODS)
        if bad:
            raise ValueError(f"building_map: unknown method(s) {sorted(bad)}")

    def summary(self) -> dict[str, Any]:
        bm, tr = self.building_map, self.transformers
        per_trafo = bm.groupby("trafo_id").size()
        return {
            "n_transformers": int(len(tr)),
            "n_transformers_rated": int((tr["data"] == "rated").sum()),
            "n_transformers_serving_buildings": int(per_trafo.size),
            "n_buildings": int(len(bm)),
            "n_buildings_unassigned": int(bm["trafo_id"].isna().sum()),
            "buildings_by_method": {
                k: int(v) for k, v in bm["method"].value_counts().items()
            },
            "buildings_per_serving_transformer": {
                "median": float(per_trafo.median()) if len(per_trafo) else None,
                "max": int(per_trafo.max()) if len(per_trafo) else None,
            },
            "n_lv_lines": None if self.lines is None else len(self.lines),
        }

    def write(self, out_dir: Path) -> Path:
        self.validate()
        out_dir.mkdir(parents=True, exist_ok=True)
        self.transformers[TRANSFORMER_COLUMNS].to_csv(
            out_dir / "transformers.csv", index=False
        )
        self.building_map[MAP_COLUMNS].to_csv(
            out_dir / "building_grid_map.csv", index=False
        )
        if self.lines is not None:
            (out_dir / "lv_lines.geojson").write_text(
                json.dumps({"type": "FeatureCollection", "features": self.lines}),
                encoding="utf-8",
            )
        manifest = {
            "source": self.source,
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "inputs": self.inputs,
            "licence": self.licence,
            "assumptions": self.assumptions,
            "methods": METHODS,
            "summary": self.summary(),
            **self.extra,
        }
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        return out_dir


def line_feature(
    coords_rd: Iterable[tuple[float, float]], properties: dict[str, Any]
) -> dict[str, Any]:
    """A GeoJSON LineString feature in WGS84 from RD coordinates."""
    xy = np.asarray(list(coords_rd), dtype=float)
    lat, lon = to_wgs(xy[:, 0], xy[:, 1])
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [round(float(a), 7), round(float(b), 7)]
                for a, b in zip(lon, lat, strict=True)
            ],
        },
        "properties": properties,
    }
