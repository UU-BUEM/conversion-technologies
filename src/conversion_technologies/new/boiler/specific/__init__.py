"""Boiler technologies, built directly from ``new/technologies.csv``.

One row per (variant, scale). No per-variant Python file is needed to add a
boiler burning a carrier that already has a constant in ``core.carriers``
(e.g. a hydrogen boiler) -- just add rows to the CSV.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from conversion_technologies.core.carriers import HEAT
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
from conversion_technologies.new.boiler.generic.thermal_efficiency import (
    derated_efficiency,
)

# These columns feed derated_efficiency() instead of passing straight
# through as a Calliope key -- everything else in a boiler row does.
_FORMULA_COLUMNS = ("efficiency", "part_load_factor")

_ROWS = [
    row
    for row in load_technology_rows("conversion_technologies.new")
    if row["category"] == "boiler"
]


def _build(row: dict[str, Any]) -> TechnologySpec:
    tech_id = f"boiler_{row['variant']}_{row['scale']}"

    nameplate_efficiency = require_range(
        row["efficiency"], 0.8, 0.99, name="efficiency", tech_id=tech_id
    )
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=tech_id)

    efficiency = nameplate_efficiency
    if row["part_load_factor"] is not None:
        efficiency = derated_efficiency(nameplate_efficiency, row["part_load_factor"])
        notes = (
            f"Part-load-derated efficiency {efficiency:.0%} "
            f"(nameplate {nameplate_efficiency:.0%})."
        )
    else:
        notes = f"Nameplate efficiency {efficiency:.0%}."

    return TechnologySpec(
        id=tech_id,
        name=f"{row['name']} ({row['scale']})",
        category="boiler",
        variant=row["variant"],
        scale=row["scale"],
        carriers_in={row["carrier_in"]: 1.0},
        carriers_out={HEAT: efficiency},
        primary_carrier_in=row["carrier_in"],
        primary_carrier_out=HEAT,
        flow_cap_max=row["flow_cap_max"],
        lifetime=int(row["lifetime"]),
        cost_flow_cap=row["cost_flow_cap"],
        color=row["color"],
        notes=notes,
        params=passthrough_params(row, formula_columns=_FORMULA_COLUMNS),
    )


for _row in _ROWS:
    register_technology(
        f"boiler_{_row['variant']}_{_row['scale']}", partial(_build, _row)
    )
