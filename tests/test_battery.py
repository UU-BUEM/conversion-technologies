"""Stationary batteries (``new/battery``): storage export and bounds."""

from __future__ import annotations

import copy

import pytest

from conversion_technologies import (
    new,  # noqa: F401  (registers all built-in technologies)
)
from conversion_technologies.calliope_export.modern import export
from conversion_technologies.core.registry import get_technology
from conversion_technologies.new.battery.specific import _ROWS, _build


def _row(scale: str) -> dict:
    return copy.deepcopy(next(r for r in _ROWS if r["scale"] == scale))


@pytest.mark.parametrize("scale", ["household", "community"])
def test_battery_exports_as_electricity_storage(scale: str) -> None:
    body = export(get_technology(f"battery_lithium_ion_{scale}"))
    assert body["base_tech"] == "storage"
    assert body["carrier_in"] == body["carrier_out"] == "electricity"
    assert body["flow_in_eff"] == body["flow_out_eff"]
    assert 0 < body["flow_in_eff"] < 1
    assert body["cost_storage_cap"]["dims"] == "costs"
    assert body["flow_cap_per_storage_cap_max"] > 0
    assert body["storage_loss"] > 0


def test_home_battery_is_priced_per_kwh_only() -> None:
    """Home batteries are sold per usable kWh with inverter and installation,
    so all investment is on the energy capacity."""
    body = export(get_technology("battery_lithium_ion_household"))
    assert "cost_flow_cap" not in body
    assert body["cost_storage_cap"]["data"] > 0


def test_community_battery_splits_power_and_energy_costs() -> None:
    body = export(get_technology("battery_lithium_ion_community"))
    assert body["cost_flow_cap"]["data"] > 0
    assert body["cost_storage_cap"]["data"] > 0
    assert body["cost_om_annual"]["data"] > 0


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("efficiency", 1.2),
        ("flow_cap_per_storage_cap_max", 0),
        ("flow_cap_per_storage_cap_max", None),
        ("storage_cap_max", 0),
        ("storage_loss", 1.5),
        ("cost_storage_cap", None),
        ("carrier_in", "heat"),
    ],
)
def test_bad_battery_rows_are_rejected(column: str, value) -> None:
    row = _row("household")
    row[column] = value
    with pytest.raises((ValueError, TypeError)):
        _build(row)
