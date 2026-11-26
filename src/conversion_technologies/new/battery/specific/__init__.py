"""Stationary electricity storage (batteries), built from ``new/technologies.csv``.

A stationary battery is a Calliope ``storage`` technology on the
``electricity`` carrier, sized freely by the optimiser in two dimensions:

- ``storage_cap`` (kWh, usable energy), priced by ``cost_storage_cap``;
- ``flow_cap`` (kW, charge = discharge power), priced by ``cost_flow_cap``
  where the source splits the cost that way (community scale). A home
  battery is sold as one package per usable kWh (inverter and installation
  included), so its whole cost sits on ``cost_storage_cap`` and its power
  is tied to its energy by ``flow_cap_per_storage_cap_max`` (C-rate).

``efficiency`` is the *one-way* efficiency, used for both charging and
discharging (``flow_in_eff = flow_out_eff``), so the round trip is
``efficiency**2``. ``storage_loss`` is Calliope's self-discharge per hour.

Unlike the EV traction battery (``new/ev``), a stationary battery is an
energy-system investment, so it carries investment costs. It is dispatched
structurally (carrier ``electricity`` + storage columns), never by variant
name.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from conversion_technologies.core.carriers import ELECTRICITY
from conversion_technologies.core.csv_loader import (
    load_technology_rows,
    passthrough_params,
)
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.core.validation import (
    require_range,
    require_scale_capacity,
)

_FORMULA_COLUMNS = ("efficiency",)

_ROWS = [
    row
    for row in load_technology_rows("conversion_technologies.new")
    if row["category"] == "battery"
]


def _tech_id(row: dict[str, Any]) -> str:
    return f"battery_{row['variant']}_{row['scale']}"


def _validate(row: dict[str, Any], tech_id: str) -> float:
    """Technology-specific bounds; returns the one-way efficiency."""
    if row["carrier_in"] != ELECTRICITY:
        raise ValueError(
            f"Technology '{tech_id}': a stationary battery stores "
            f"{ELECTRICITY!r}, got carrier_in={row['carrier_in']!r}."
        )
    efficiency = require_range(
        row["efficiency"], 0, 1, name="efficiency", tech_id=tech_id, inclusive_lo=False
    )
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=tech_id)
    require_range(
        row["storage_cap_max"],
        0,
        float("inf"),
        name="storage_cap_max",
        tech_id=tech_id,
        inclusive_lo=False,
    )
    # A battery without a C-rate limit and without a power cost could
    # charge its whole capacity in one timestep for free.
    require_range(
        row["flow_cap_per_storage_cap_max"],
        0,
        10,
        name="flow_cap_per_storage_cap_max",
        tech_id=tech_id,
        inclusive_lo=False,
    )
    if row["storage_loss"] is not None:
        require_range(
            row["storage_loss"],
            0,
            1,
            name="storage_loss",
            tech_id=tech_id,
            inclusive_hi=False,
        )
    if row["storage_discharge_depth"] is not None:
        require_range(
            row["storage_discharge_depth"],
            0,
            1,
            name="storage_discharge_depth",
            tech_id=tech_id,
            inclusive_hi=False,
        )
    if row.get("cost_storage_cap") is None:
        raise ValueError(
            f"Technology '{tech_id}': a stationary battery is an investment, "
            "so it needs cost_storage_cap (costs.csv)."
        )
    return efficiency


def _build(row: dict[str, Any]) -> TechnologySpec:
    tech_id = _tech_id(row)
    efficiency = _validate(row, tech_id)
    return TechnologySpec(
        id=tech_id,
        name=f"{row['name']} ({row['scale']})",
        category="battery",
        variant=row["variant"],
        scale=row["scale"],
        flow_cap_max=row["flow_cap_max"],
        lifetime=int(row["lifetime"]),
        cost_flow_cap=row.get("cost_flow_cap"),
        color=row["color"],
        params=passthrough_params(row, formula_columns=_FORMULA_COLUMNS),
        carriers_in={ELECTRICITY: efficiency},
        carriers_out={ELECTRICITY: efficiency},
        primary_carrier_in=ELECTRICITY,
        primary_carrier_out=ELECTRICITY,
        base_tech="storage",
        notes=(
            f"Stationary battery: one-way efficiency {efficiency:.4f} "
            f"(round trip {efficiency**2:.3f}); up to "
            f"{row['storage_cap_max']:g} kWh and "
            f"{row['flow_cap_per_storage_cap_max']:g} kW per kWh."
        ),
    )


for _row in _ROWS:
    register_technology(_tech_id(_row), partial(_build, _row))
