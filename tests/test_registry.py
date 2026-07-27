from __future__ import annotations

import pytest

from conversion_technologies import (
    new,  # noqa: F401  (registers all built-in technologies)
)
from conversion_technologies.core.registry import (
    all_technologies,
    get_technology,
    list_technology_ids,
)
from conversion_technologies.core.technology import TechnologySpec


def test_all_expected_categories_are_registered() -> None:
    ids = list_technology_ids()
    assert any(tech_id.startswith("boiler_") for tech_id in ids)
    assert any(tech_id.startswith("heat_pump_") for tech_id in ids)
    assert any(tech_id.startswith("chp_") for tech_id in ids)


def test_every_scale_is_registered_per_technology() -> None:
    ids = set(list_technology_ids())
    for base in (
        "boiler_electric",
        "boiler_gas",
        "boiler_biomass",
        "heat_pump_electric",
        "heat_pump_geothermal",
        "chp_gas",
        "chp_biomass",
    ):
        for scale in ("household", "building", "community"):
            assert f"{base}_{scale}" in ids


def test_get_technology_builds_a_technology_spec() -> None:
    tech = get_technology("boiler_electric_household")
    assert isinstance(tech, TechnologySpec)
    assert tech.scale == "household"
    assert tech.category == "boiler"


def test_get_technology_unknown_id_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_technology("not_a_real_technology")


def test_all_technologies_returns_one_spec_per_registered_id() -> None:
    techs = all_technologies()
    assert set(techs) == set(list_technology_ids())
    assert all(isinstance(tech, TechnologySpec) for tech in techs.values())
