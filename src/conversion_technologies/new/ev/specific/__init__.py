"""Electric-vehicle technologies, built directly from ``new/technologies.csv``.

An electric vehicle is not one Calliope technology but three roles around
a separate ``ev_electricity`` carrier, which stands for the energy on the
car's side of the charger:

- **Charger** (``charger_ac``, ``charger_dc``): ``conversion``,
  electricity -> ev_electricity, with the charging efficiency. It can only
  run while the car is connected, so it carries
  ``time_varying_availability`` (see ``calliope_export.availability_math``).
- **Vehicle-to-grid discharger** (``v2g``): ``conversion``,
  ev_electricity -> electricity, also availability-bound. Its
  ``cost_flow_cap`` is the extra cost of a bidirectional charger over a
  unidirectional one, and its ``cost_flow_out`` the battery wear caused by
  each kWh sent back to the grid.
- **Battery** (``battery``): ``storage`` on ev_electricity, with a fixed
  size (``storage_cap_min == storage_cap_max``) and a reserve
  (``storage_discharge_depth``). It has no investment cost: the car is
  bought for mobility, not as an energy-system asset. The wear that
  flexibility adds is priced on the ``v2g`` discharger instead, because
  smart charging without discharging does not change the battery's total
  throughput.

The driving demand on ev_electricity (from the occupancy package's
``ev_drive_kwh``) and charging away from home are scenario data, not
catalogue technologies -- see ``docs/calliope_schema_mapping.md``
"Electric vehicles".

Each row's role is dispatched structurally from its carriers and whether it
populates the storage columns -- never from its variant name.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from conversion_technologies.core.carriers import ELECTRICITY, EV_ELECTRICITY
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
    if row["category"] == "ev"
]


def _tech_id(row: dict[str, Any]) -> str:
    return f"ev_{row['variant']}_{row['scale']}"


def _validate_storage(row: dict[str, Any], tech_id: str) -> None:
    cap_max = require_range(
        row["storage_cap_max"],
        0,
        float("inf"),
        name="storage_cap_max",
        tech_id=tech_id,
        inclusive_lo=False,
    )
    if row["storage_cap_min"] is not None:
        require_range(
            row["storage_cap_min"], 0, cap_max, name="storage_cap_min", tech_id=tech_id
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


def _build(row: dict[str, Any]) -> TechnologySpec:
    tech_id = _tech_id(row)
    efficiency = require_range(
        row["efficiency"], 0, 1, name="efficiency", tech_id=tech_id, inclusive_lo=False
    )
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=tech_id)
    carrier_in = row["carrier_in"]
    common: dict[str, Any] = {
        "id": tech_id,
        "name": f"{row['name']} ({row['scale']})",
        "category": "ev",
        "variant": row["variant"],
        "scale": row["scale"],
        "flow_cap_max": row["flow_cap_max"],
        "lifetime": int(row["lifetime"]),
        # The battery has no costs.csv row at all (no investment cost).
        "cost_flow_cap": row.get("cost_flow_cap"),
        "color": row["color"],
        "params": passthrough_params(row, formula_columns=_FORMULA_COLUMNS),
    }

    if carrier_in == EV_ELECTRICITY and row["storage_cap_max"] is not None:
        _validate_storage(row, tech_id)
        return TechnologySpec(
            **common,
            carriers_in={EV_ELECTRICITY: efficiency},
            carriers_out={EV_ELECTRICITY: efficiency},
            primary_carrier_in=EV_ELECTRICITY,
            primary_carrier_out=EV_ELECTRICITY,
            base_tech="storage",
            notes=(
                f"Vehicle battery, {row['storage_cap_max']:g} kWh; no "
                "investment cost (bought for mobility)."
            ),
        )

    if carrier_in == ELECTRICITY:
        carrier_out = EV_ELECTRICITY
        role = "Charger"
    elif carrier_in == EV_ELECTRICITY:
        carrier_out = ELECTRICITY
        role = "Vehicle-to-grid discharger"
    else:
        raise ValueError(
            f"Technology '{tech_id}': carrier_in must be {ELECTRICITY!r} "
            f"(charger) or {EV_ELECTRICITY!r} (battery or vehicle-to-grid), "
            f"got {carrier_in!r}."
        )
    return TechnologySpec(
        **common,
        carriers_in={carrier_in: 1.0},
        carriers_out={carrier_out: efficiency},
        primary_carrier_in=carrier_in,
        primary_carrier_out=carrier_out,
        time_varying_availability=True,
        notes=(
            f"{role}, efficiency={efficiency:.2f}. Only operates while the car "
            "is connected: bound by flow_out_max_relative (scenario data)."
        ),
    )


for _row in _ROWS:
    register_technology(_tech_id(_row), partial(_build, _row))
