from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from conversion_technologies import new  # noqa: F401
from conversion_technologies.calliope_export import legacy_v051, modern
from conversion_technologies.calliope_export.writer import (
    dump_technology_yaml,
    write_technology_yaml,
)
from conversion_technologies.core.registry import all_technologies, get_technology

_yaml = YAML(typ="safe")


def test_legacy_v051_export_uses_conversion_plus_and_carrier_tiers() -> None:
    tech = get_technology("heat_pump_electric_household")
    body = legacy_v051.export(tech)
    assert body["parent"] == "conversion_plus"
    assert body["primary_carrier_out"] == "heat"
    assert "carrier_in" in body and "carrier_in_2" in body
    assert body["constraints"]["e_cap.max"] == tech.flow_cap_max
    assert body["costs"]["monetary"]["e_cap"] == tech.cost_flow_cap


def test_legacy_v051_single_carrier_tech_has_no_second_tier() -> None:
    tech = get_technology("boiler_electric_household")
    body = legacy_v051.export(tech)
    assert "carrier_in_2" not in body
    assert "carrier_out_2" not in body


def test_modern_export_uses_conversion_and_flow_naming() -> None:
    tech = get_technology("chp_gas_building")
    body = modern.export(tech)
    assert body["base_tech"] == "conversion"
    assert body["carrier_in"] == "natural_gas"
    assert set(body["carrier_out"]) == {"electricity", "heat"}
    assert body["flow_out_eff"]["dims"] == "carriers"
    assert body["cost_flow_cap"]["index"] == "monetary"


def test_modern_export_single_carrier_uses_scalar_efficiency() -> None:
    tech = get_technology("boiler_gas_household")
    body = modern.export(tech)
    assert isinstance(body["carrier_in"], str)
    assert isinstance(body["flow_out_eff"], float)


def test_every_registered_technology_exports_under_both_schemas() -> None:
    for tech in all_technologies().values():
        legacy_body = legacy_v051.export(tech)
        modern_body = modern.export(tech)
        assert legacy_body["name"] == tech.name
        assert modern_body["name"] == tech.name


def test_dump_technology_yaml_round_trips_through_a_yaml_parser() -> None:
    tech = get_technology("heat_pump_geothermal_community")
    body = modern.export(tech)
    rendered = dump_technology_yaml(tech.id, body)
    parsed = _yaml.load(rendered)
    assert parsed["techs"][tech.id]["base_tech"] == "conversion"


def test_write_technology_yaml_creates_parent_dirs(tmp_path: Path) -> None:
    tech = get_technology("boiler_biomass_household")
    body = legacy_v051.export(tech)
    target = tmp_path / "nested" / f"{tech.id}.yaml"
    path = write_technology_yaml(tech.id, body, target)
    assert path.exists()
    parsed = _yaml.load(path.read_text(encoding="utf-8"))
    assert parsed["techs"][tech.id]["parent"] == "conversion_plus"
