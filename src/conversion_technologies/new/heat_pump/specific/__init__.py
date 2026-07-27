"""Heat pump technologies, built directly from ``new/technologies.csv``.

One row per (variant, scale). Adding a new free heat source (e.g. a
surface-water heat pump) that already has a carrier constant in
``core.carriers`` needs only a new CSV row, no Python.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from conversion_technologies.core.carriers import ELECTRICITY, HEAT
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
from conversion_technologies.new.heat_pump.generic.cop_calculation import carnot_cop

# These columns feed carnot_cop() instead of passing straight through as a
# Calliope key -- everything else in a heat pump row does. "efficiency"
# here is the Carnot quality/2nd-law factor (0-1), not the COP itself --
# shares its column name with boiler's plain thermal efficiency by design
# (see docs/calliope_schema_mapping.md "Heat pump efficiency").
_FORMULA_COLUMNS = ("efficiency", "design_source_temp_c", "design_sink_temp_c")

_ROWS = [
    row
    for row in load_technology_rows("conversion_technologies.new")
    if row["category"] == "heat_pump"
]


def _build(row: dict[str, Any]) -> TechnologySpec:
    tech_id = f"heat_pump_{row['variant']}_{row['scale']}"

    quality_factor = require_range(
        row["efficiency"],
        0,
        1,
        name="efficiency",
        tech_id=tech_id,
        inclusive_lo=False,
        inclusive_hi=True,
    )
    cop = carnot_cop(
        t_source_c=row["design_source_temp_c"],
        t_sink_c=row["design_sink_temp_c"],
        carnot_efficiency=quality_factor,
    )
    assert isinstance(cop, float)  # scalar in (one CSV row), scalar out
    require_range(cop, 1, 20, name="cop", tech_id=tech_id)
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=tech_id)

    source_carrier = row["carrier_in_2"]

    return TechnologySpec(
        id=tech_id,
        name=f"{row['name']} ({row['scale']})",
        category="heat_pump",
        variant=row["variant"],
        scale=row["scale"],
        carriers_in={ELECTRICITY: 1.0, source_carrier: cop - 1.0},
        carriers_out={HEAT: cop},
        primary_carrier_in=ELECTRICITY,
        primary_carrier_out=HEAT,
        flow_cap_max=row["flow_cap_max"],
        lifetime=int(row["lifetime"]),
        cost_flow_cap=row["cost_flow_cap"],
        color=row["color"],
        notes=(
            f"COP={cop:.2f} at design conditions "
            f"(source={row['design_source_temp_c']}C, "
            f"sink={row['design_sink_temp_c']}C, "
            f"quality/Carnot efficiency={quality_factor})."
        ),
        params=passthrough_params(row, formula_columns=_FORMULA_COLUMNS),
    )


for _row in _ROWS:
    register_technology(
        f"heat_pump_{_row['variant']}_{_row['scale']}", partial(_build, _row)
    )
