"""Grid from a network the user provides (first tier).

``--provided-dir`` holds, in order of preference:

``transformers.csv`` (required)
    ``trafo_id``, ``latitude``, ``longitude`` (WGS84); optional ``name``,
    ``rated_kva``, ``n_transformers``, ``peak_kw``, ``nbl_limit_kw``,
    ``peak_date``.
``building_grid_map.csv`` (optional, best)
    The real assignment: ``trafo_id`` plus ``building_feature_id`` or
    ``bag_pand_id``; optional ``feeder_id``. Used as given.
``lv_cables.geojson`` (optional)
    LV cable routes (LineString/MultiLineString), WGS84 lon/lat or
    EPSG:28992 (detected from the coordinate range). Buildings are traced
    along them exactly as for the DSO tier.

With neither of the optional files, buildings go to the nearest station
in a straight line (``euclidean``). A full pandapower network
(``net.json``) is not read yet: pandapower needs older pandas/numpy than
the Calliope environment allows, so it gets its own environment in
step 3.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from grid.common import TRANSFORMER_COLUMNS, GridPackage, nearest_station, to_rd
from grid.lv_trace import TraceSettings, trace


def available(provided_dir: Path | None) -> bool:
    return provided_dir is not None and (provided_dir / "transformers.csv").exists()


def _read_cables(path: Path) -> list[np.ndarray]:
    gj = json.loads(path.read_text(encoding="utf-8"))
    lines: list[np.ndarray] = []
    for feature in gj.get("features", []):
        geom = feature.get("geometry") or {}
        if geom.get("type") == "LineString":
            lines.append(np.asarray(geom["coordinates"], dtype=float)[:, :2])
        elif geom.get("type") == "MultiLineString":
            lines.extend(np.asarray(c, dtype=float)[:, :2] for c in geom["coordinates"])
    if not lines:
        raise ValueError(f"{path}: no LineString features")
    if np.abs(np.vstack(lines)).max() <= 180:  # lon/lat -> RD
        lines = [np.column_stack(to_rd(line[:, 0], line[:, 1])) for line in lines]
    return lines


def build(
    buildings: pd.DataFrame, provided_dir: Path, settings: TraceSettings
) -> GridPackage:
    tr = pd.read_csv(provided_dir / "transformers.csv", dtype={"trafo_id": str})
    missing = [c for c in ("trafo_id", "latitude", "longitude") if c not in tr.columns]
    if missing:
        raise ValueError(f"{provided_dir / 'transformers.csv'}: missing {missing}")
    for col in TRANSFORMER_COLUMNS:
        if col not in tr.columns:
            tr[col] = None
    tr["data"] = np.where(tr["rated_kva"].notna(), "rated", "geometry_only")
    tr["source_id"] = tr["source_id"].fillna("provided")
    tr["x"], tr["y"] = to_rd(tr["longitude"], tr["latitude"])

    ids = buildings[["building_feature_id", "bag_pand_id", "latitude", "longitude"]]
    map_path = provided_dir / "building_grid_map.csv"
    cable_path = provided_dir / "lv_cables.geojson"
    extra: dict = {}
    if map_path.exists():
        given = pd.read_csv(map_path, dtype={"trafo_id": str, "bag_pand_id": str})
        key = (
            "building_feature_id"
            if "building_feature_id" in given.columns
            else "bag_pand_id"
        )
        cols = [key, "trafo_id"] + (
            ["feeder_id"] if "feeder_id" in given.columns else []
        )
        bm = ids.merge(given[cols], on=key, how="left")
        bm["method"] = np.where(
            bm["trafo_id"].notna(), "provided", "euclidean_fallback"
        )
        lost = bm["trafo_id"].isna()
        if lost.any():
            xy = buildings.set_index("building_feature_id").loc[
                bm.loc[lost, "building_feature_id"], ["x", "y"]
            ]
            idx, _ = nearest_station(xy.to_numpy(), tr[["x", "y"]].to_numpy())
            bm.loc[lost, "trafo_id"] = tr["trafo_id"].to_numpy()[idx]
        bm = bm.assign(network_distance_m=None, connection_distance_m=None)
        bm["feeder_id"] = bm.get("feeder_id")
        lines = None
        how = "building_grid_map.csv as given"
    elif cable_path.exists():
        cables = _read_cables(cable_path)
        traced, lines, stats = trace(cables, tr, buildings, settings)
        bm = traced.merge(ids, on="building_feature_id")
        extra["trace"] = stats
        how = "traced along lv_cables.geojson"
    else:
        idx, dist = nearest_station(
            buildings[["x", "y"]].to_numpy(), tr[["x", "y"]].to_numpy()
        )
        bm = ids.assign(
            trafo_id=tr["trafo_id"].to_numpy()[idx],
            feeder_id=None,
            network_distance_m=None,
            connection_distance_m=None,
            method="euclidean",
        )
        lines = None
        how = "nearest station (no map, no cables provided)"
    return GridPackage(
        source="provided",
        transformers=tr.drop(columns=["x", "y"]),
        building_map=bm,
        lines=lines,
        inputs={"provided_dir": str(provided_dir), "assignment": how},
        licence=["User-provided network: terms as agreed with its owner."],
        assumptions=settings.describe()
        if cable_path.exists() and not map_path.exists()
        else [],
        extra=extra,
    )
