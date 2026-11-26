from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from conversion_technologies import new  # noqa: F401
from conversion_technologies.calliope_export import modern
from conversion_technologies.calliope_export.availability_math import (
    PARAMETER,
    build_availability_math,
    merge_math,
)
from conversion_technologies.calliope_export.ratio_math import build_ratio_math
from conversion_technologies.cli import main
from conversion_technologies.core.carriers import ELECTRICITY, EV_ELECTRICITY
from conversion_technologies.core.registry import all_technologies, get_technology
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.new.ev.specific import _build


def _row(**overrides: object) -> dict:
    row = {
        "category": "ev",
        "variant": "charger_ac",
        "scale": "household",
        "name": "Test charger",
        "color": "#000000",
        "carrier_in": "electricity",
        "carrier_in_2": None,
        "flow_cap_min": None,
        "flow_cap_max": 11.0,
        "lifetime": 15.0,
        "efficiency": 0.92,
        "storage_cap_max": None,
        "storage_cap_min": None,
        "storage_discharge_depth": None,
        "cost_flow_cap": 150.0,
        "cost_interest_rate": 0.0225,
    }
    row.update(overrides)
    return row


def test_charger_converts_grid_electricity_into_the_car():
    tech = get_technology("ev_charger_ac_household")
    assert tech.base_tech == "conversion"
    assert tech.carriers_in == {ELECTRICITY: 1.0}
    assert tech.carriers_out == {EV_ELECTRICITY: pytest.approx(0.92)}
    assert tech.time_varying_availability


def test_v2g_discharges_the_car_into_the_grid():
    tech = get_technology("ev_v2g_household")
    assert tech.carriers_in == {EV_ELECTRICITY: 1.0}
    assert set(tech.carriers_out) == {ELECTRICITY}
    assert tech.time_varying_availability
    assert tech.params["cost_flow_out"] > 0  # battery wear per kWh sent back


def test_battery_is_fixed_size_storage_without_investment_cost():
    tech = get_technology("ev_battery_household")
    assert tech.base_tech == "storage"
    assert tech.cost_flow_cap is None
    assert tech.params["storage_cap_min"] == tech.params["storage_cap_max"]
    assert not tech.time_varying_availability

    body = modern.export(tech)
    assert body["base_tech"] == "storage"
    assert body["carrier_in"] == body["carrier_out"] == EV_ELECTRICITY
    assert body["storage_cap_max"] == pytest.approx(60)
    assert body["storage_discharge_depth"] == pytest.approx(0.1)
    assert "cost_flow_cap" not in body


def test_charger_capacity_and_cost_sit_on_the_car_side_carrier():
    body = modern.export(get_technology("ev_charger_ac_household"))
    assert body["flow_cap_max"]["index"] == EV_ELECTRICITY
    assert body["cost_flow_cap"]["index"] == [["monetary", EV_ELECTRICITY]]


def test_availability_math_covers_exactly_the_availability_bound_techs():
    math = build_availability_math(all_technologies().values())
    assert math is not None
    constraint = next(iter(math["constraints"].values()))
    bound = {t.id for t in all_technologies().values() if t.time_varying_availability}
    assert bound == {
        "ev_charger_ac_household",
        "ev_charger_ac_building",
        "ev_charger_dc_community",
        "ev_v2g_household",
    }
    for tech_id in bound:
        assert tech_id in constraint["where"]
    assert "ev_battery_household" not in constraint["where"]
    assert math["parameters"][PARAMETER]["default"] == 1
    assert build_availability_math([get_technology("boiler_gas_household")]) is None


def test_merge_math_combines_ratio_and_availability_and_rejects_duplicates():
    techs = [
        get_technology("heat_pump_electric_household"),
        get_technology("ev_charger_ac_household"),
    ]
    merged = merge_math(build_ratio_math(techs), build_availability_math(techs))
    assert merged is not None
    assert "balance_conversion" in merged["constraints"]
    assert "flow_out_max_availability" in merged["constraints"]
    with pytest.raises(ValueError, match="twice"):
        merge_math(build_availability_math(techs), build_availability_math(techs))
    assert merge_math(None, None) is None


def test_builder_rejects_bad_rows():
    with pytest.raises(ValueError, match="efficiency"):
        _build(_row(efficiency=1.2))
    with pytest.raises(ValueError, match="carrier_in"):
        _build(_row(carrier_in="natural_gas"))
    with pytest.raises(ValueError, match="storage_cap_min"):
        _build(
            _row(
                variant="battery",
                carrier_in="ev_electricity",
                storage_cap_max=60.0,
                storage_cap_min=80.0,
                cost_flow_cap=None,
            )
        )


def test_conversion_technology_still_requires_an_investment_cost():
    with pytest.raises(ValueError, match="cost_flow_cap"):
        TechnologySpec(
            id="x",
            name="x",
            category="ev",
            variant="charger_ac",
            scale="household",
            carriers_in={ELECTRICITY: 1.0},
            carriers_out={EV_ELECTRICITY: 0.9},
            flow_cap_max=11,
            lifetime=15,
            cost_flow_cap=None,
        )
    with pytest.raises(ValueError, match="same single carrier"):
        TechnologySpec(
            id="y",
            name="y",
            category="ev",
            variant="battery",
            scale="household",
            carriers_in={EV_ELECTRICITY: 1.0},
            carriers_out={ELECTRICITY: 1.0},
            flow_cap_max=50,
            lifetime=15,
            cost_flow_cap=None,
            base_tech="storage",
        )


def test_cli_exports_ev_category_with_availability_math(tmp_path: Path):
    output = tmp_path / "ev.yaml"
    assert main(["export-all", "--category", "ev", "-o", str(output)]) == 0
    yaml = YAML(typ="safe")
    techs = yaml.load(output.read_text(encoding="utf-8"))["techs"]
    assert set(techs) == {
        "ev_charger_ac_household",
        "ev_charger_ac_building",
        "ev_charger_dc_community",
        "ev_v2g_household",
        "ev_battery_household",
    }
    math = yaml.load((tmp_path / "ev.additional_math.yaml").read_text(encoding="utf-8"))
    assert "flow_out_max_availability" in math["constraints"]


def test_storage_final_math_covers_storage_techs_only():
    from conversion_technologies.calliope_export.storage_math import (
        PARAMETER,
        build_storage_final_math,
    )

    math = build_storage_final_math(all_technologies().values())
    assert math is not None
    assert math["parameters"][PARAMETER]["default"] == 0
    where = math["constraints"]["storage_final_level_min"]["where"]
    storage_ids = {
        t.id for t in all_technologies().values() if t.base_tech == "storage"
    }
    assert storage_ids
    for tech_id in storage_ids:
        assert tech_id in where
    assert build_storage_final_math([get_technology("boiler_gas_household")]) is None
    # Combines with the other custom math without name clashes.
    merged = merge_math(build_availability_math(all_technologies().values()), math)
    assert PARAMETER in merged["parameters"]
