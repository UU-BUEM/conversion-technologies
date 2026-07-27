from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from conversion_technologies import new  # noqa: F401
from conversion_technologies.calliope_export import modern
from conversion_technologies.calliope_export.writer import (
    dump_technology_yaml,
    write_technology_yaml,
)
from conversion_technologies.core.registry import all_technologies, get_technology

_yaml = YAML(typ="safe")


def test_modern_export_uses_conversion_and_flow_naming() -> None:
    tech = get_technology("chp_gas_building")
    body = modern.export(tech)
    assert body["base_tech"] == "conversion"
    assert body["carrier_in"] == "natural_gas"
    assert set(body["carrier_out"]) == {"electricity", "heat"}
    assert body["flow_out_eff"]["dims"] == "carriers"
    assert body["cost_flow_cap"]["index"] == "monetary"
    assert body["cost_flow_in"]["data"] == pytest.approx(tech.params["cost_flow_in"])
    assert body["cost_interest_rate"]["data"] == pytest.approx(0.10)
    assert body["flow_ramping"] == pytest.approx(tech.params["flow_ramping"])


def test_modern_export_passes_through_an_unknown_params_key_unchanged() -> None:
    """The whole point of the redesign: modern.py needs zero code for a new column."""
    tech = get_technology("boiler_gas_household")
    tech.params["flow_out_min_relative"] = 0.2  # a hypothetical future Calliope key
    body = modern.export(tech)
    assert body["flow_out_min_relative"] == pytest.approx(0.2)


def test_modern_export_single_carrier_uses_scalar_efficiency() -> None:
    tech = get_technology("boiler_gas_household")
    body = modern.export(tech)
    assert isinstance(body["carrier_in"], str)
    assert isinstance(body["flow_out_eff"], float)


def test_every_registered_technology_exports() -> None:
    for tech in all_technologies().values():
        body = modern.export(tech)
        assert body["name"] == tech.name


def test_dump_technology_yaml_round_trips_through_a_yaml_parser() -> None:
    tech = get_technology("heat_pump_geothermal_community")
    body = modern.export(tech)
    rendered = dump_technology_yaml(tech.id, body)
    parsed = _yaml.load(rendered)
    assert parsed["techs"][tech.id]["base_tech"] == "conversion"


def test_write_technology_yaml_creates_parent_dirs(tmp_path: Path) -> None:
    tech = get_technology("boiler_biomass_household")
    body = modern.export(tech)
    target = tmp_path / "nested" / f"{tech.id}.yaml"
    path = write_technology_yaml(tech.id, body, target)
    assert path.exists()
    parsed = _yaml.load(path.read_text(encoding="utf-8"))
    assert parsed["techs"][tech.id]["base_tech"] == "conversion"
