"""Tests for the step-1 grid builder (scripts/grid/), on synthetic networks.

Run in scenario_env from the repository root:

    python -m pytest scenarios/NL/loenen_gas_free/tests -q

No network access and no Liander data needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from grid import cross_check, provided, pylovo  # noqa: E402
from grid.common import GridPackage, to_wgs  # noqa: E402
from grid.liander import stations_from  # noqa: E402
from grid.lv_trace import TraceSettings, trace  # noqa: E402

X0, Y0 = 195_000.0, 460_000.0  # somewhere near Loenen, RD New


def _xy(points):
    return [np.array([[X0 + x, Y0 + y] for x, y in line]) for line in points]


# Station A at (0,0), B at (1000,0). Street cable A->B in two pieces joined
# at x=500; a branch whose end sits 0.5 m from cable 1's interior vertex
# (250,0), so it joins; and a cable crossing cable 1 at x=350 with a
# vertex 0.2 m from it but no *end* near anything, so it stays separate.
CABLES = _xy(
    [
        [(0, 0), (250, 0), (500, 0)],
        [(500, 0), (1000, 0)],
        [(250, 0.5), (250, 200)],
        [(340, -50), (350, 0.2), (360, 50)],
    ]
)
STATIONS = pd.DataFrame({"trafo_id": ["A", "B"], "x": [X0, X0 + 1000], "y": [Y0, Y0]})
BUILDING_XY = {
    1: (100, 10),  # near A
    2: (900, 10),  # near B
    3: (255, 190),  # on the branch: A by cable (~440 m) vs B (~940 m)
    4: (600, -10),  # A 600 m vs B 400 m along the street cable
    5: (342, -45),  # next to the isolated crossing cable
    6: (5000, 5000),  # no cable within reach
}


def _buildings() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "building_feature_id": k,
                "bag_pand_id": f"NL.IMBAG.Pand.{k:016d}",
                "x": X0 + x,
                "y": Y0 + y,
            }
            for k, (x, y) in BUILDING_XY.items()
        ]
    )
    df["latitude"], df["longitude"] = to_wgs(df["x"], df["y"])
    return df


def _trace():
    bm, lines, stats = trace(CABLES, STATIONS, _buildings(), TraceSettings())
    return bm.set_index("building_feature_id"), lines, stats


def test_buildings_follow_the_cables_to_the_nearest_station_by_route():
    bm, _, _ = _trace()
    assert bm.loc[1, "trafo_id"] == "A" and bm.loc[1, "method"] == "lv_network"
    assert bm.loc[2, "trafo_id"] == "B"
    assert bm.loc[3, "trafo_id"] == "A"
    assert bm.loc[3, "network_distance_m"] == pytest.approx(250 + 190, abs=2)
    assert bm.loc[4, "trafo_id"] == "B"
    assert bm.loc[4, "network_distance_m"] == pytest.approx(400, abs=1)
    assert bm.loc[1, "connection_distance_m"] == pytest.approx(10, abs=0.1)


def test_crossing_cables_are_not_joined_and_unreachable_buildings_fall_back():
    bm, _, stats = _trace()
    assert bm.loc[5, "method"] == "euclidean_fallback"  # its cable reaches no station
    assert bm.loc[5, "connection_distance_m"] == pytest.approx(1, abs=1)
    assert bm.loc[6, "method"] == "euclidean_fallback"
    assert pd.isna(bm.loc[6, "connection_distance_m"])
    assert bm.loc[6, "trafo_id"] in {"A", "B"}
    # pieces: A-B street with branch, and the isolated crossing cable
    assert stats["cable_graph"]["n_connected_pieces"] == 2


def test_feeders_are_the_first_cable_leaving_the_station():
    bm, lines, _ = _trace()
    assert bm.loc[1, "feeder_id"] == bm.loc[3, "feeder_id"]  # same cable out of A
    assert bm.loc[1, "feeder_id"].startswith("A-F")
    assert bm.loc[2, "feeder_id"].startswith("B-F")
    assert {f["properties"]["trafo_id"] for f in lines} >= {"A", "B"}
    lon, lat = lines[0]["geometry"]["coordinates"][0]
    assert 5 < lon < 7 and 51 < lat < 53  # written in WGS84


def test_package_validation_rejects_inconsistent_output():
    bm, lines, _ = _trace()
    bm = bm.reset_index().merge(
        _buildings()[["building_feature_id"]], on="building_feature_id"
    )
    bm["bag_pand_id"] = "x"
    bm["latitude"] = bm["longitude"] = 0.0
    tr = STATIONS.assign(
        name=None,
        latitude=52.0,
        longitude=6.0,
        rated_kva=250.0,
        n_transformers=1,
        peak_kw=None,
        nbl_limit_kw=None,
        peak_date=None,
        data="rated",
        source_id="t",
    )
    GridPackage("test", tr, bm, lines).validate()
    with pytest.raises(ValueError, match="duplicate trafo_id"):
        GridPackage("test", pd.concat([tr, tr]), bm).validate()
    with pytest.raises(ValueError, match="unknown trafo_id"):
        GridPackage("test", tr[tr.trafo_id == "A"], bm).validate()
    with pytest.raises(ValueError, match="assigned twice"):
        GridPackage("test", tr, pd.concat([bm, bm])).validate()


def test_knelpunt_transformers_are_grouped_per_msr_and_placed_at_the_mv_room():
    lat, lon = to_wgs([X0 + 2, X0 + 2, X0 + 3000], [Y0, Y0, Y0])
    knelpunt = pd.DataFrame(
        {
            "msr": ["111", "111", "222"],
            "transformer": ["111-T01", "111-T02", "222-T01"],
            "lat": lat,
            "lon": lon,
            "rated_kw": [400.0, 250.0, 100.0],
            "peak_kw": [200.0, 100.0, 50.0],
            "nbl_limit_kw": [380.0, 240.0, 96.0],
            "peak_date": ["1-1-2025"] * 3,
        }
    )
    rooms = pd.DataFrame(
        {
            "objectid": [10, 11],
            "function": ["Ruimte"] * 2,
            "x": [X0, X0 + 500],
            "y": [Y0, Y0],
        }
    )
    bbox = (X0 - 100, Y0 - 100, X0 + 3100, Y0 + 100)
    st, stats = stations_from(rooms, knelpunt, bbox, match_m=75)
    st = st.set_index("trafo_id")
    assert (
        st.loc["MSR111", "rated_kva"] == 650 and st.loc["MSR111", "n_transformers"] == 2
    )
    assert st.loc["MSR111", "x"] == X0  # moved onto Liander's MV room
    assert st.loc["MSR222", "x"] == pytest.approx(
        X0 + 3000
    )  # no room nearby: own position
    assert st.loc["MSRUIMTE11", "data"] == "geometry_only"
    assert stats["ms_rooms_without_rating"] == 1


def _write_transformers(d: Path) -> None:
    lat, lon = to_wgs(STATIONS["x"], STATIONS["y"])
    pd.DataFrame(
        {
            "trafo_id": ["A", "B"],
            "latitude": lat,
            "longitude": lon,
            "rated_kva": [400, None],
        }
    ).to_csv(d / "transformers.csv", index=False)


def test_provided_network_three_ways(tmp_path):
    b = _buildings()
    assert not provided.available(tmp_path)
    _write_transformers(tmp_path)
    assert provided.available(tmp_path)

    plain = provided.build(b, tmp_path, TraceSettings())
    assert set(plain.building_map["method"]) == {"euclidean"}
    assert list(plain.transformers["data"]) == ["rated", "geometry_only"]
    plain.validate()

    features = []
    for line in CABLES:
        lat, lon = to_wgs(line[:, 0], line[:, 1])
        features.append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": np.column_stack([lon, lat]).tolist(),
                },
            }
        )
    (tmp_path / "lv_cables.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features})
    )
    traced = provided.build(b, tmp_path, TraceSettings()).building_map.set_index(
        "building_feature_id"
    )
    assert traced.loc[4, "trafo_id"] == "B" and traced.loc[4, "method"] == "lv_network"

    pd.DataFrame(
        {"bag_pand_id": b["bag_pand_id"][:5], "trafo_id": ["A", "B", "A", "A", "B"]}
    ).to_csv(tmp_path / "building_grid_map.csv", index=False)
    given = provided.build(b, tmp_path, TraceSettings())
    given.validate()
    gm = given.building_map.set_index("building_feature_id")
    assert (
        gm.loc[4, "trafo_id"] == "A" and gm.loc[4, "method"] == "provided"
    )  # as given
    assert gm.loc[6, "method"] == "euclidean_fallback"  # missing from the user's map


def _square(cx: float, cy: float, half: float = 8.0) -> dict:
    xs = [cx - half, cx + half, cx + half, cx - half, cx - half]
    ys = [cy - half, cy - half, cy + half, cy + half, cy - half]
    lat, lon = to_wgs(xs, ys)
    return {"type": "Polygon", "coordinates": [np.column_stack([lon, lat]).tolist()]}


def test_pylovo_response_is_converted_to_the_common_package():
    lat, lon = to_wgs(STATIONS["x"], STATIONS["y"])
    response = {
        "status": "success",
        "transformers": {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [lon[i], lat[i]]},
                    "properties": {
                        "osm_id": 9 + i,
                        "grid_result_id": 7 + i,
                        "rated_power_kva": 400,
                    },
                }
                for i in range(2)
            ]
        },
        "buildings": {
            "features": [
                {
                    "geometry": _square(X0 + 100, Y0 + 10),
                    "properties": {"osm_id": 1, "grid_result_id": 7},
                },
                {
                    "geometry": _square(X0 + 900, Y0 + 30),
                    "properties": {"osm_id": 2, "grid_result_id": 8},
                },
            ]
        },
        "lines": {
            "features": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[lon[0], lat[0]], [lon[1], lat[1]]],
                    },
                    "properties": {
                        "line_id": 1,
                        "grid_result_id": 7,
                        "cable_type": "NAYY 4x150 SE",
                        "length_km": 1.0,
                    },
                }
            ]
        },
    }
    pkg = pylovo.convert(response, _buildings(), match_m=30)
    pkg.validate()
    bm = pkg.building_map.set_index("building_feature_id")
    assert bm.loc[1, "trafo_id"] == "PYLOVO7" and bm.loc[1, "method"] == "pylovo"
    assert (
        bm.loc[2, "trafo_id"] == "PYLOVO8"
    )  # 20 m from the footprint: nearest within 30 m
    assert bm.loc[6, "method"] == "euclidean_fallback"
    assert pkg.lines[0]["properties"]["cable_type"] == "NAYY 4x150 SE"
    assert pylovo.area_polygon(_buildings(), 200)["type"] == "Polygon"


def test_cross_check_reports_distances_to_reference_stations():
    lat, lon = to_wgs(STATIONS["x"], STATIONS["y"])
    ref = pd.DataFrame(
        {
            "trafo_id": ["A", "B"],
            "latitude": lat,
            "longitude": lon,
            "rated_kva": [400, 250],
            "data": ["rated", "rated"],
        }
    )
    tlat, tlon = to_wgs(STATIONS["x"] + 30, STATIONS["y"])
    test = pd.DataFrame(
        {
            "trafo_id": ["P1", "P2"],
            "latitude": tlat,
            "longitude": tlon,
            "rated_kva": [630, 630],
        }
    )
    pairs, summary = cross_check.compare(ref, test)
    assert list(pairs["nearest_reference"]) == ["A", "B"]
    assert summary["distance_m"]["median"] == pytest.approx(30, abs=0.5)
    assert summary["share_within_50_m"] == 1.0
    assert summary["total_rated_kva"] == {"reference": 650.0, "test": 1260.0}
