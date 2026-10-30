"""Chiller technologies, built directly from ``new/technologies.csv``.

One row per (variant, scale). Three variants share this builder, structurally
dispatched off which carrier/ratio columns a row populates -- same pattern
``heat_pump/specific/__init__.py`` uses for its ``carrier_in_2``:

- ``electric`` (compression chiller / AC): electricity in, cooling out.
- ``heat_pump_reversible``: same shape as ``electric`` -- same physical unit
  in cooling mode, kept as its own row so it gets its own (lower) COP and
  (higher) cost rather than being conflated with a dedicated AC. It is a
  separate catalog entry, not a literal shared-capacity dual-mode
  technology -- see ``.claude/chiller/resolved.md``.
- ``absorption``: heat in (plus a small parasitic electricity draw via
  ``carrier_in_2``), cooling out -- a second input carrier, same structural
  shape as ``heat_pump``'s electricity+ambient_heat, so
  ``calliope_export.ratio_math.build_ratio_math``'s existing
  ``len(carriers) > 1`` check already covers it with no new code.

``cop`` is read directly from the CSV, not derived by a formula (unlike
``heat_pump``'s Carnot-cycle COP) -- cooling-mode delta-T isn't modeled here,
so there is nothing to derive from; see ``docs/calliope_schema_mapping.md``
"Cooling technologies".
"""

from __future__ import annotations

from functools import partial
from typing import Any

from conversion_technologies.core.carriers import COOLING
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

# These columns feed carriers_in/carriers_out directly instead of passing
# straight through as a Calliope key -- everything else in a chiller row does.
_FORMULA_COLUMNS = ("cop", "aux_electricity_ratio")

# Per-variant sanity bounds on COP -- generous, not tight engineering limits
# (same spirit as DEFAULT_CAPACITY_CEILINGS_KW): electric compression
# chillers and reversible heat pumps are both electricity-driven vapor-
# compression cycles (COP > 1 by definition); absorption chillers are
# heat-driven and have COP < 1 by definition.
_COP_BOUNDS: dict[str, tuple[float, float]] = {
    "electric": (2.0, 8.0),
    "heat_pump_reversible": (1.5, 5.0),
    "absorption": (0.4, 1.3),
}

_ROWS = [
    row
    for row in load_technology_rows("conversion_technologies.new")
    if row["category"] == "chiller"
]


def _build(row: dict[str, Any]) -> TechnologySpec:
    tech_id = f"chiller_{row['variant']}_{row['scale']}"

    cop_lo, cop_hi = _COP_BOUNDS[row["variant"]]
    cop = require_range(row["cop"], cop_lo, cop_hi, name="cop", tech_id=tech_id)
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=tech_id)

    carriers_in: dict[str, float] = {row["carrier_in"]: 1.0}
    if row["carrier_in_2"] is not None:
        aux_ratio = require_range(
            row["aux_electricity_ratio"],
            0,
            1,
            name="aux_electricity_ratio",
            tech_id=tech_id,
            inclusive_lo=False,
        )
        carriers_in[row["carrier_in_2"]] = aux_ratio

    return TechnologySpec(
        id=tech_id,
        name=f"{row['name']} ({row['scale']})",
        category="chiller",
        variant=row["variant"],
        scale=row["scale"],
        carriers_in=carriers_in,
        carriers_out={COOLING: cop},
        primary_carrier_in=row["carrier_in"],
        primary_carrier_out=COOLING,
        flow_cap_max=row["flow_cap_max"],
        lifetime=int(row["lifetime"]),
        cost_flow_cap=row["cost_flow_cap"],
        color=row["color"],
        notes=f"COP={cop:.2f}.",
        params=passthrough_params(row, formula_columns=_FORMULA_COLUMNS),
    )


for _row in _ROWS:
    register_technology(
        f"chiller_{_row['variant']}_{_row['scale']}", partial(_build, _row)
    )
