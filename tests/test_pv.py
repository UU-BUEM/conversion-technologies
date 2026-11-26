"""Rooftop PV (generation_technologies.pv): the Calliope supply technology,
the PVWatts v8 profile engine (checked against EnerPlanET's pysam-pv), the
roof layout and the Calliope data writer."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conversion_technologies import generation_technologies  # noqa: F401
from conversion_technologies.calliope_export.modern import export
from conversion_technologies.core.registry import get_technology, list_technology_ids
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.generation_technologies.pv.specific import PROFILE_COLUMNS

PYSAM_PV = Path(__file__).parent / "data" / "pysam_pv"
LOCATION = (48.8295, 12.9554)  # pysam-pv's test location (Deggendorf)

pysam = pytest.importorskip(
    "PySAM.Pvwattsv8", reason="NREL-PySAM (extra 'pv') not installed"
)

from conversion_technologies.generation_technologies.pv import pvwatts  # noqa: E402
from conversion_technologies.generation_technologies.pv.profiles import (  # noqa: E402
    write_pv_profiles,
)
from conversion_technologies.generation_technologies.pv.roof import (  # noqa: E402
    building_capacity_factor,
    roof_pv,
)

# -- fixtures -------------------------------------------------------------------


@pytest.fixture(scope="module")
def reference():
    """pysam-pv's own simulate.py, pinned (tests/data/pysam_pv/COMMIT)."""
    spec = importlib.util.spec_from_file_location(
        "pysam_pv_simulate", PYSAM_PV / "simulate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def weather_json() -> dict:
    return json.loads(
        (PYSAM_PV / "merra2_2018_deggendorf.json").read_text(encoding="utf-8")
    )


def _frame(body: dict) -> pd.DataFrame:
    index = pd.to_datetime(body["index"], format="%Y-%m-%dT%H:%M:%SZ")
    return pd.DataFrame(
        {
            name: pd.array(values, dtype="Float64").astype(float)
            for name, values in body["variables"].items()
        },
        index=index,
    )


@pytest.fixture(scope="module")
def weather(weather_json) -> pd.DataFrame:
    return _frame(weather_json)


def _reference_ac(reference, body: dict, **array) -> list[float]:
    parsed = reference.parse_weather(body)
    item = {"id": "a", **array}
    return reference.simulate(*LOCATION, 0.0, parsed, reference.parse_arrays([item])[0])


# -- the technology ---------------------------------------------------------------


def test_pv_technologies_are_registered_as_supply():
    assert {"pv_rooftop_household", "pv_rooftop_building"} <= set(list_technology_ids())
    tech = get_technology("pv_rooftop_household")
    assert tech.base_tech == "supply"
    assert tech.carriers_in == {}
    assert tech.carriers_out == {"electricity": 1.0}
    assert tech.source_unit == "per_cap"
    assert tech.lifetime == 25
    # OpenTech-DB solar_pv_dist_res_6kw_de: USD2024 2350/kW, 22/kW/yr.
    assert tech.cost_flow_cap == pytest.approx(2350 / 1.08238 * 1.0213, abs=0.01)
    assert tech.params["cost_om_annual"] == pytest.approx(
        22 / 1.08238 * 1.0213, abs=0.01
    )


def test_export_is_a_calliope_supply_body_without_profile_settings():
    body = export(get_technology("pv_rooftop_household"))
    assert body["base_tech"] == "supply"
    assert body["carrier_out"] == "electricity"
    assert "carrier_in" not in body
    assert body["source_unit"] == "per_cap"
    assert body["flow_out_eff"] == 1.0
    assert body["flow_cap_max"] == {
        "data": 20.0,
        "index": "electricity",
        "dims": "carriers",
    }
    assert body["cost_flow_cap"]["index"] == [["monetary", "electricity"]]
    assert not (set(PROFILE_COLUMNS) - {"carrier_out"}) & set(body)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"carriers_in": {"electricity": 1.0}}, "no input carrier"),
        (
            {"carriers_out": {"electricity": 1.0, "heat": 1.0}},
            "exactly one output carrier",
        ),
        ({"source_unit": None}, "source_unit"),
    ],
)
def test_supply_spec_is_checked(change, message):
    fields = {
        "id": "x",
        "name": "x",
        "category": "pv",
        "variant": "v",
        "scale": "household",
        "carriers_in": {},
        "carriers_out": {"electricity": 1.0},
        "flow_cap_max": 10.0,
        "lifetime": 25,
        "cost_flow_cap": 1000.0,
        "base_tech": "supply",
        "source_unit": "per_cap",
    }
    with pytest.raises(ValueError, match=message):
        TechnologySpec(**{**fields, **change})


# -- the profile engine = pysam-pv ------------------------------------------------


@pytest.mark.parametrize(
    "array",
    [
        {"tilt": 35, "azimuth": 180},
        {"tilt": 20, "azimuth": 90, "capacity_kw": 6.0},
        {
            "tilt": 45,
            "azimuth": 250,
            "losses": 0.1,
            "dc_ac_ratio": 1.3,
            "module_type": "premium",
        },
        {
            "tilt": 10,
            "azimuth": 180,
            "mounting": "open_rack",
            "module_type": "thin_film",
        },
    ],
)
def test_profile_equals_pysam_pv(reference, weather_json, weather, array):
    expected = _reference_ac(reference, weather_json, **array)
    ours = pvwatts.simulate_ac_kw(weather, *LOCATION, pvwatts.PVArray(id="a", **array))
    assert len(ours) == len(expected) == 8760
    np.testing.assert_allclose(ours.to_numpy(), expected, rtol=0, atol=1e-12)


def test_null_filling_equals_pysam_pv(reference, weather_json, weather):
    body = json.loads(json.dumps(weather_json))
    noon = 180 * 24 + 11
    body["variables"]["DNI"][noon] = None
    body["variables"]["T"][0] = None
    body["variables"]["WS_10M"][noon] = None
    expected = _reference_ac(reference, body, tilt=35, azimuth=180)
    frame = weather.copy()
    frame.iloc[noon, frame.columns.get_loc("DNI")] = np.nan
    frame.iloc[0, frame.columns.get_loc("T")] = np.nan
    frame.iloc[noon, frame.columns.get_loc("WS_10M")] = np.nan
    ours = pvwatts.simulate_ac_kw(
        frame, *LOCATION, pvwatts.PVArray(id="a", tilt=35, azimuth=180)
    )
    np.testing.assert_allclose(ours.to_numpy(), expected, rtol=0, atol=1e-12)


def test_leap_year_keeps_every_hour_in_place(weather_json):
    feb29 = 59 * 24
    start = datetime(2020, 1, 1, 0, 30)
    variables = {}
    for name, values in weather_json["variables"].items():
        day = values[feb29 - 24 : feb29]
        if name in ("GHI", "DHI", "DNI"):
            day = [0.0] * 24
        variables[name] = values[:feb29] + day + values[feb29:]
    index = [
        (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(8784)
    ]
    ac = pvwatts.simulate_ac_kw(
        _frame({"index": index, "variables": variables}),
        *LOCATION,
        pvwatts.PVArray(id="a", tilt=35, azimuth=180),
    )
    assert len(ac) == 8784
    assert ac.iloc[feb29 : feb29 + 24].sum() == 0
    assert (
        ac.iloc[feb29 - 24 : feb29].sum() > 0
        and ac.iloc[feb29 + 24 : feb29 + 48].sum() > 0
    )


def test_capacity_factors_by_orientation(weather):
    arrays = [
        pvwatts.PVArray(id=name, tilt=35, azimuth=az)
        for name, az in (("south", 180), ("east", 90), ("west", 270), ("north", 0))
    ]
    factors = pvwatts.pv_capacity_factors(weather, *LOCATION, arrays)
    energy = factors.sum()
    # pysam-pv's own bound: MERRA-2 irradiance runs high in central Europe.
    assert 1000 < energy["south"] < 1500
    assert energy["south"] > energy["east"] > energy["north"]
    assert energy["south"] > energy["west"] > energy["north"]
    assert ((factors >= 0) & (factors <= 1)).all().all()
    assert (factors.loc[weather["GHI"] == 0] == 0).all().all()


def test_wind_is_required(weather):
    with pytest.raises(ValueError, match="WS_10M"):
        pvwatts.simulate_ac_kw(
            weather.drop(columns="WS_10M"),
            *LOCATION,
            pvwatts.PVArray(id="a", tilt=35, azimuth=180),
        )


def test_old_weather_package_gives_a_clear_error(monkeypatch):
    import weather as weather_package

    def old_signature(
        latitude, longitude, year, *, provider="era5-land", data_dir=None
    ):
        raise AssertionError("not reached")

    monkeypatch.setattr(weather_package, "get_point_weather", old_signature)
    with pytest.raises(ImportError, match="weather >= 2.0"):
        pvwatts.fetch_weather(52.1, 5.2, 2018)


def test_array_settings_are_checked():
    with pytest.raises(ValueError, match="tilt"):
        pvwatts.PVArray(id="a", tilt=95, azimuth=180)
    with pytest.raises(ValueError, match="module_type"):
        pvwatts.PVArray(id="a", tilt=30, azimuth=180, module_type="mono")


# -- roof layout ------------------------------------------------------------------


def _face(eid, tilt, azimuth, area):
    return {"id": eid, "tilt": tilt, "azimuth": azimuth, "area_m2": area}


def test_roof_rules():
    roof = roof_pv(
        [
            _face("south", 40, 180, 30.0),
            _face("north", 40, 0, 30.0),  # faces north: skipped
            _face("east", 40, 90, 20.0),  # exactly 90 deg from south: kept
            _face("dormer", 45, 180, 4.0),  # too small: skipped
            _face("flat", 2, None, 50.0),  # flat: 15 deg rack facing south
            {"id": "broken", "tilt": None, "area_m2": 30.0},
        ]
    )
    by_id = {array.id: array for array in roof.arrays}
    assert set(by_id) == {"south", "east", "flat"}
    assert (by_id["flat"].tilt, by_id["flat"].azimuth) == (15.0, 180.0)
    # 0.6 of the area usable at 0.2 kWp/m2.
    assert by_id["south"].capacity_kw == pytest.approx(30 * 0.6 * 0.2)
    assert roof.max_capacity_kwp == pytest.approx((30 + 20 + 50) * 0.12)
    assert by_id["south"].losses == 0.14 and by_id["south"].dc_ac_ratio == 1.1


def test_building_profile_is_the_capacity_weighted_mean(weather):
    roof = roof_pv([_face("south", 35, 180, 30.0), _face("east", 35, 90, 10.0)])
    combined = building_capacity_factor(weather, *LOCATION, roof)
    parts = pvwatts.pv_capacity_factors(weather, *LOCATION, roof.arrays)
    expected = (parts["south"] * 3 + parts["east"]) / 4
    np.testing.assert_allclose(combined.to_numpy(), expected.to_numpy(), atol=1e-12)
    empty = building_capacity_factor(
        weather, *LOCATION, roof_pv([_face("north", 40, 0, 50.0)])
    )
    assert (empty == 0).all()


# -- Calliope data ------------------------------------------------------------------


def test_write_pv_profiles(tmp_path, weather):
    factors = pd.DataFrame(
        {"bldg_1": np.full(len(weather), 0.1), "bldg_2": np.zeros(len(weather))},
        index=weather.index,
    )
    paths = write_pv_profiles(
        "pv_rooftop_household", factors, {"bldg_1": 4.5, "bldg_2": 0.0}, tmp_path
    )
    csv = pd.read_csv(paths["profile_csv"], index_col=0)
    assert list(csv.columns) == ["bldg_1"] and csv.index.name == "timesteps"
    tables = paths["data_tables_yaml"].read_text(encoding="utf-8")
    assert (
        "source_use_max" in tables
        and "pv_rooftop_household" in tables
        and "columns: nodes" in tables
    )
    nodes = paths["nodes_yaml"].read_text(encoding="utf-8")
    assert "bldg_1" in nodes and "bldg_2" not in nodes and "4.5" in nodes


def test_write_pv_profiles_rejects_bad_values(tmp_path, weather):
    factors = pd.DataFrame({"bldg_1": np.full(len(weather), 1.5)}, index=weather.index)
    with pytest.raises(ValueError, match="source_use_max"):
        write_pv_profiles("pv_rooftop_household", factors, {"bldg_1": 4.5}, tmp_path)


def test_cli_pv_profile(tmp_path, monkeypatch, weather):
    from conversion_technologies import cli

    monkeypatch.setattr(pvwatts, "fetch_weather", lambda *args, **kwargs: weather)
    faces = tmp_path / "faces.json"
    faces.write_text(
        json.dumps(
            {
                "bldg_1": [_face("r1", 35, 180, 40.0)],
                "bldg_2": [_face("r1", 35, 0, 40.0)],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert (
        cli.main(
            [
                "pv-profile",
                "pv_rooftop_household",
                "--roof-faces",
                str(faces),
                "--latitude",
                str(LOCATION[0]),
                "--longitude",
                str(LOCATION[1]),
                "--year",
                "2018",
                "-o",
                str(out),
            ]
        )
        == 0
    )
    csv = pd.read_csv(out / "pv_rooftop_household_source_use_max.csv", index_col=0)
    assert list(csv.columns) == ["bldg_1"]
    assert 1000 < csv["bldg_1"].sum() < 1500
