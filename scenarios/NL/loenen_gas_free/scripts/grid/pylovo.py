"""Grid from enerplanet-pylovo (third tier: synthetic LV grid).

Talks to a running enerplanet-pylovo API (``make dev`` in a clone of
https://github.com/enerplanet/enerplanet-pylovo, default
``http://localhost:8086``) whose database already holds the region
(``make process COUNTRY=netherlands STATE=gelderland``).

``POST /generate-grid`` with ``{"geom": <GeoJSON Polygon, WGS84>}``
returns GeoJSON FeatureCollections (WGS84):

* ``buildings``: OSM footprints with ``osm_id``, ``grid_result_id``;
* ``transformers``: points with ``osm_id``, ``grid_result_id``,
  ``rated_power_kva`` (one transformer per ``grid_result_id``);
* ``lines``: LV cables with ``grid_result_id``, ``line_name``,
  ``cable_type`` (pandapower std type), ``length_km``.

pylovo's buildings are OpenStreetMap footprints, not BAG; each scenario
building is matched to the pylovo footprint that contains its centroid
(else the nearest pylovo footprint within ``match_m``).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from grid.common import GridPackage, nearest_station, to_rd, to_wgs


def available(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/health", timeout=5) as resp:
            return resp.status == 200
    except OSError:
        return False


def area_polygon(buildings: pd.DataFrame, buffer_m: float) -> dict[str, Any]:
    """Buffered convex hull of the buildings, as a WGS84 GeoJSON Polygon."""
    from shapely.geometry import MultiPoint

    hull = MultiPoint(buildings[["x", "y"]].to_numpy()).convex_hull.buffer(buffer_m)
    xs, ys = np.asarray(hull.exterior.xy)
    lat, lon = to_wgs(xs, ys)
    return {
        "type": "Polygon",
        "coordinates": [[[float(a), float(b)] for a, b in zip(lon, lat, strict=True)]],
    }


def fetch(url: str, polygon: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
    body = json.dumps({"geom": polygon, "include_private_buildings": False}).encode()
    key = hashlib.sha1(url.encode() + body).hexdigest()[:10]
    path = cache_dir / f"pylovo_generate_grid_{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        f"{url.rstrip('/')}/generate-grid",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=1800) as resp:
        result = json.loads(resp.read())
    if result.get("status") != "success":
        raise RuntimeError(f"pylovo /generate-grid: {str(result)[:300]}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def convert(
    response: dict[str, Any], buildings: pd.DataFrame, match_m: float = 30.0
) -> GridPackage:
    import shapely
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree

    trafos = []
    for f in response["transformers"]["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        trafos.append(
            {
                "trafo_id": f"PYLOVO{p['grid_result_id']}",
                "name": None if p.get("osm_id") is None else str(p["osm_id"]),
                "latitude": lat,
                "longitude": lon,
                "rated_kva": p.get("rated_power_kva"),
                "n_transformers": 1,
                "peak_kw": None,
                "nbl_limit_kw": None,
                "peak_date": None,
                "data": "rated"
                if p.get("rated_power_kva") is not None
                else "geometry_only",
                "source_id": f"pylovo:grid_result_id={p['grid_result_id']}",
            }
        )
    tr = pd.DataFrame(trafos).drop_duplicates("trafo_id")
    if tr.empty:
        raise RuntimeError("pylovo returned no transformers for this area")
    tr["x"], tr["y"] = to_rd(tr["longitude"], tr["latitude"])

    feats = [f for f in response["buildings"]["features"] if f.get("geometry")]
    # Footprints to RD, for distances in metres.
    geoms = [
        shapely.transform(
            shape(f["geometry"]), lambda c: np.column_stack(to_rd(c[:, 0], c[:, 1]))
        )
        for f in feats
    ]
    grid_of = [f["properties"].get("grid_result_id") for f in feats]
    tree = STRtree(geoms)

    rows = []
    for _, b in buildings.iterrows():
        pt = Point(b["x"], b["y"])
        hits = list(tree.query(pt, predicate="intersects"))
        method = "pylovo"
        if hits:
            gid = grid_of[hits[0]]
        else:
            i = tree.nearest(pt)
            gid = grid_of[i] if geoms[i].distance(pt) <= match_m else None
        trafo = f"PYLOVO{gid}" if gid is not None else None
        if trafo not in set(tr["trafo_id"]):
            idx, _ = nearest_station(
                np.array([[b["x"], b["y"]]]), tr[["x", "y"]].to_numpy()
            )
            trafo, method = tr["trafo_id"].iloc[int(idx[0])], "euclidean_fallback"
        rows.append(
            {
                "building_feature_id": b["building_feature_id"],
                "bag_pand_id": b["bag_pand_id"],
                "latitude": b["latitude"],
                "longitude": b["longitude"],
                "trafo_id": trafo,
                "feeder_id": None,
                "network_distance_m": None,
                "connection_distance_m": None,
                "method": method,
            }
        )

    lines = [
        {
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "line_id": f["properties"].get("line_id"),
                "trafo_id": f"PYLOVO{f['properties'].get('grid_result_id')}",
                "feeder_id": None,
                "cable_type": f["properties"].get("cable_type"),
                "length_km": f["properties"].get("length_km"),
            },
        }
        for f in response["lines"]["features"]
    ]
    return GridPackage(
        source="pylovo",
        transformers=tr.drop(columns=["x", "y"]),
        building_map=pd.DataFrame(rows),
        lines=lines,
        licence=[
            "pylovo output derived from OpenStreetMap (ODbL) and the enerplanet-pylovo "
            "datasets (see its ATTRIBUTIONS.md)."
        ],
        assumptions=[
            "Synthetic grid: transformer positions, sizes and cable routes are pylovo's "
            "planning heuristics, not the real network.",
            f"Scenario (BAG) buildings matched to pylovo (OSM) footprints by containment, "
            f"else the nearest footprint within {match_m} m, else the nearest transformer.",
            "pylovo's API returns no feeder ids; feeder_id is left empty.",
        ],
    )
