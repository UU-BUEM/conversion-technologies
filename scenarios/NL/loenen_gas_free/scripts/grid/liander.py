"""Grid from Liander's open data (DSO tier).

Two Liander sources, both cached under ``--cache-dir``:

* **Liggingsgegevens elektriciteitsnetten** (CC BY 4.0): ArcGIS
  FeatureServer ``Liander_Open_Data_Elektra``, EPSG:28992, geometry only.
  Layers used: 642 ``Middenspanningsstation`` (``FUNCTIE_HOOFDGROEP`` =
  ``Ruimte``: MV rooms with MV/LV transformers), 112 ``Laagspanningskabel``
  (LV cables), and for the record 643 ``Laagspanningsstation`` (LV
  cabinets), 424 ``Middenspanningskabel``, 641 ``Hoogspanningsstation``.
  No cable types, ratings or connectivity.
* **Netbewust publiek laden, dataset knelpunt** (CSV, ``;``-separated):
  one row per MV/LV transformer with MSR number, WGS84 position, rated
  capacity (``ACTIVEPOWERLIMIT_VALUE``, kW per the field description),
  peak load (``ANALOGVALUE_VALUE``, kW, "bepaald volgens de methodiek die
  gebruikt wordt voor netinpassing") and the Netbewust Laden limit.
  **Liander's terms: not to be shared with third parties without written
  permission.** It is used locally and only derived results are written,
  to the git-ignored ``data/`` folder; never commit it or its numbers.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from grid.common import GridPackage, bbox_rd, to_rd, to_wgs
from grid.lv_trace import TraceSettings, trace

SERVICE = (
    "https://services1.arcgis.com/v6W5HAVrpgSg3vts/arcgis/rest/services/"
    "Liander_Open_Data_Elektra/FeatureServer"
)
LAYERS = {
    "hs_station": 641,
    "ms_station": 642,
    "ls_station": 643,
    "ms_cable": 424,
    "ls_cable": 112,
}
KNELPUNT_URL = (
    "https://www.liander.nl/-/media/files/open-data/netbewust-publiek-laden/"
    "netbewust-publiek-laden-liander---dataset-knelpunt-2026-01.csv?v=1&d=20260422T144722Z"
)
KNELPUNT_EDITION = "2026-01"
LICENCE = [
    "Liander liggingsgegevens elektriciteitsnetten: CC BY 4.0 "
    "(https://data.overheid.nl/dataset/liander-liggingsgegevens-elektriciteitsnetten).",
    "Liander Netbewust publiek laden, dataset knelpunt 2026-01: may not be shared with "
    "third parties without Liander's written permission; indicative data quality, "
    "'niet bedoeld of geschikt voor inpassingsvraagstukken'. Keep this package local.",
]
_HEADERS = {"User-Agent": "Mozilla/5.0 (research grid model)"}


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_layer(
    name: str, bbox: tuple[float, float, float, float], cache_dir: Path
) -> list[dict[str, Any]]:
    """All features of one layer intersecting ``bbox`` (RD), Esri JSON,
    paged and cached."""
    key = hashlib.sha1(f"{name}{[round(v) for v in bbox]}".encode()).hexdigest()[:10]
    path = cache_dir / f"liander_{name}_{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "where": "1=1",
                "geometry": ",".join(f"{v:.0f}" for v in bbox),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 28992,
                "outSR": 28992,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "returnGeometry": "true",
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "json",
            }
        )
        page = json.loads(_get(f"{SERVICE}/{LAYERS[name]}/query?{query}"))
        if "error" in page:
            raise RuntimeError(f"Liander layer {name}: {page['error']}")
        features.extend(page.get("features", []))
        if not page.get("exceededTransferLimit"):
            break
        offset += len(page.get("features", []))
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(features), encoding="utf-8")
    return features


def fetch_knelpunt(cache_dir: Path) -> pd.DataFrame:
    path = cache_dir / f"liander_knelpunt_{KNELPUNT_EDITION}.csv"
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(KNELPUNT_URL))
    text = path.read_bytes().decode("utf-8-sig")
    df = pd.DataFrame(list(csv.DictReader(io.StringIO(text), delimiter=";")))

    def num(col: str) -> pd.Series:
        return pd.to_numeric(
            df[col].str.replace(",", ".", regex=False), errors="coerce"
        )

    out = pd.DataFrame(
        {
            "msr": df["SUBSTATION_NAME"].str.replace(" ", "", regex=False),
            "transformer": df["CONDUCTINGEQUIPMENT_NAME"],
            "lat": num("POSITIONPOINT_YPOSITION"),
            "lon": num("POSITIONPOINT_XPOSITION"),
            "rated_kw": num("ACTIVEPOWERLIMIT_VALUE"),
            "peak_kw": num("ANALOGVALUE_VALUE"),
            "nbl_limit_kw": num("ACTIVEPOWERLIMIT_VALUE_NBL"),
            "peak_date": df["ANALOGVALUE_TIMESTAMP"],
            "place": df["TOWNDETAIL_SECTION"],
            "lv_kv": df["BASEVOLTAGE_NOMINALVOLTAGE"],
        }
    )
    if (df["COORDINATESYSTEM_NAME"] != "EPSG:4326").any():
        raise ValueError("Liander knelpunt: expected EPSG:4326 positions throughout")
    return out


def _points(features: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "objectid": f["attributes"]["OBJECTID"],
                "function": f["attributes"].get("FUNCTIE_HOOFDGROEP"),
                "x": f["geometry"]["x"],
                "y": f["geometry"]["y"],
            }
            for f in features
            if f.get("geometry")
        ]
    )


def _paths(features: list[dict[str, Any]]) -> list[np.ndarray]:
    return [
        np.asarray(path, dtype=float)[:, :2]
        for f in features
        if f.get("geometry")
        for path in f["geometry"]["paths"]
    ]


def stations_from(
    ms_rooms: pd.DataFrame,
    knelpunt: pd.DataFrame,
    bbox: tuple[float, float, float, float],
    match_m: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """One station per MV room. Rated transformers from the knelpunt list
    are grouped per MSR and matched to the nearest MV room within
    ``match_m``; MV rooms without a match stay as ``geometry_only``."""
    from scipy.spatial import cKDTree

    kx, ky = to_rd(knelpunt["lon"], knelpunt["lat"])
    k = knelpunt.assign(x=kx, y=ky)
    k = k[(k.x >= bbox[0]) & (k.x <= bbox[2]) & (k.y >= bbox[1]) & (k.y <= bbox[3])]
    msr = (
        k.groupby("msr")
        .agg(
            x=("x", "mean"),
            y=("y", "mean"),
            rated_kva=("rated_kw", "sum"),
            n_transformers=("transformer", "size"),
            peak_kw=("peak_kw", "sum"),
            nbl_limit_kw=("nbl_limit_kw", "sum"),
            peak_date=("peak_date", "first"),
            transformers=("transformer", lambda s: ";".join(s)),
        )
        .reset_index()
    )
    rooms = ms_rooms.reset_index(drop=True)
    dist, idx = cKDTree(rooms[["x", "y"]].to_numpy()).query(msr[["x", "y"]].to_numpy())
    msr["room"] = np.where(dist <= match_m, idx, -1)
    msr["match_m"] = dist
    # A room can match only one MSR: keep the closest, others keep their own position.
    msr = msr.sort_values("match_m")
    msr.loc[msr.duplicated("room") & (msr.room >= 0), "room"] = -1

    rows = []
    matched_rooms = set()
    for _, m in msr.iterrows():
        room = int(m["room"])
        x, y = (
            (rooms.at[room, "x"], rooms.at[room, "y"])
            if room >= 0
            else (m["x"], m["y"])
        )
        if room >= 0:
            matched_rooms.add(room)
        rows.append(
            {
                "trafo_id": f"MSR{m['msr']}",
                "name": m["transformers"],
                "x": x,
                "y": y,
                "rated_kva": m["rated_kva"],
                "n_transformers": int(m["n_transformers"]),
                "peak_kw": m["peak_kw"],
                "nbl_limit_kw": m["nbl_limit_kw"],
                "peak_date": m["peak_date"],
                "data": "rated",
                "source_id": f"knelpunt:{m['msr']}"
                + (f"|ms_room:{rooms.at[room, 'objectid']}" if room >= 0 else ""),
            }
        )
    for room, r in rooms.iterrows():
        if room in matched_rooms:
            continue
        rows.append(
            {
                "trafo_id": f"MSRUIMTE{r['objectid']}",
                "name": None,
                "x": r["x"],
                "y": r["y"],
                "rated_kva": None,
                "n_transformers": None,
                "peak_kw": None,
                "nbl_limit_kw": None,
                "peak_date": None,
                "data": "geometry_only",
                "source_id": f"ms_room:{r['objectid']}",
            }
        )
    stations = pd.DataFrame(rows)
    stations["latitude"], stations["longitude"] = to_wgs(stations["x"], stations["y"])
    stats = {
        "knelpunt_msr_in_bbox": int(len(msr)),
        "knelpunt_msr_matched_to_ms_room": int((msr.room >= 0).sum()),
        "knelpunt_match_distance_m_max": round(
            float(msr.loc[msr.room >= 0, "match_m"].max()), 1
        )
        if (msr.room >= 0).any()
        else None,
        "ms_rooms_in_bbox": int(len(rooms)),
        "ms_rooms_without_rating": int(len(rooms) - len(matched_rooms)),
    }
    return stations, stats


def available(
    buildings: pd.DataFrame, cache_dir: Path, buffer_m: float = 1000.0
) -> bool:
    """True when Liander has MV rooms in the area (i.e. the area is Liander's)."""
    try:
        return bool(fetch_layer("ms_station", bbox_rd(buildings, buffer_m), cache_dir))
    except (OSError, RuntimeError, ValueError):
        return False


def build(
    buildings: pd.DataFrame,
    cache_dir: Path,
    settings: TraceSettings,
    buffer_m: float = 1000.0,
    match_m: float = 75.0,
    unrated_stations: str = "include",
) -> GridPackage:
    """``unrated_stations``: ``include`` (default) lets every Liander MV room
    feed buildings; ``exclude`` only those with a rated MV/LV transformer in
    the knelpunt list. Checked for Loenen 2026-11-25 (1,260 buildings):
    ``exclude`` gives 91 buildings a cable route over 1 km (max 2.4 km), all
    of which sit next to an unrated room in ``include`` mode; ``include``
    keeps every route under 1 km (max 964 m, P90 450 m) and halves the
    straight-line fallbacks (68 -> 31). So at least some unrated rooms do
    feed the LV network, and the knelpunt list is incomplete for them. The
    cost: some buildings sit on stations with no published rating."""
    if unrated_stations not in ("exclude", "include"):
        raise ValueError(
            f"unrated_stations must be exclude or include, got {unrated_stations!r}"
        )
    bbox = bbox_rd(buildings, buffer_m)
    ms_rooms = _points(fetch_layer("ms_station", bbox, cache_dir))
    ms_rooms = ms_rooms[ms_rooms["function"] == "Ruimte"]
    cables = _paths(fetch_layer("ls_cable", bbox, cache_dir))
    counts = {
        name: len(fetch_layer(name, bbox, cache_dir))
        for name in ("hs_station", "ls_station", "ms_cable")
    }
    stations, station_stats = stations_from(
        ms_rooms, fetch_knelpunt(cache_dir), bbox, match_m
    )

    feeding = (
        stations
        if unrated_stations == "include"
        else stations[stations.data == "rated"]
    )
    building_map, lines, trace_stats = trace(cables, feeding, buildings, settings)
    building_map = building_map.merge(
        buildings[["building_feature_id", "bag_pand_id", "latitude", "longitude"]],
        on="building_feature_id",
    )
    served = stations[stations.trafo_id.isin(building_map.trafo_id)]
    unrated_serving = served[served.data == "geometry_only"].trafo_id
    return GridPackage(
        source="dso:liander",
        transformers=stations.drop(columns=["x", "y"]),
        building_map=building_map,
        lines=lines,
        inputs={
            "feature_server": SERVICE,
            "layers": LAYERS,
            "knelpunt_csv": KNELPUNT_URL,
            "bbox_rd": [round(v) for v in bbox],
            "bbox_buffer_m": buffer_m,
            "unrated_stations": unrated_stations,
        },
        licence=LICENCE,
        assumptions=[
            *settings.describe(),
            f"A rated transformer (knelpunt list) is placed at the nearest Liander MV room "
            f"within {match_m} m; transformers of one MSR are summed into one station.",
            "rated_kva is Liander's ACTIVEPOWERLIMIT_VALUE (labelled kW, 'nominale "
            "capaciteit'); the values are standard transformer sizes, i.e. kVA ratings.",
            "MV rooms without a knelpunt row are kept as geometry_only stations (rating "
            "unknown; possibly customer-owned or without an MV/LV transformer); "
            f"unrated_stations={unrated_stations}: they "
            + (
                "may feed buildings."
                if unrated_stations == "include"
                else "feed no buildings."
            ),
        ],
        extra={
            "stations": station_stats,
            "trace": trace_stats,
            "other_layers_in_bbox": counts,
            "buildings_on_unrated_stations": int(
                building_map.trafo_id.isin(unrated_serving).sum()
            ),
        },
    )
