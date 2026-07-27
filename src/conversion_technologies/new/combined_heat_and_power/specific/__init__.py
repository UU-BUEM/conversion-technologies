"""Combined heat and power technologies, built directly from ``new/technologies.csv``.

One row per (variant, scale). Adding a fuel that already has a carrier
constant in ``core.carriers`` (e.g. hydrogen CHP) needs only a new CSV row.
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
from conversion_technologies.core.validation import require_scale_capacity
from conversion_technologies.new.combined_heat_and_power.generic.alpha_beta import (
    power_to_heat_ratio,
    validate_dispatch_factors,
)

# These columns feed the dispatch-factor carrier ratios instead of passing
# straight through as a Calliope key -- everything else in a CHP row does
# (including flow_ramping, which is just another passthrough parameter now).
_FORMULA_COLUMNS = ("alpha", "beta")

_ROWS = [
    row
    for row in load_technology_rows("conversion_technologies.new")
    if row["category"] == "combined_heat_and_power"
]


def _build(row: dict[str, Any]) -> TechnologySpec:
    tech_id = f"chp_{row['variant']}_{row['scale']}"

    alpha, beta = row["alpha"], row["beta"]
    validate_dispatch_factors(alpha, beta)
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=tech_id)

    return TechnologySpec(
        id=tech_id,
        name=f"{row['name']} ({row['scale']})",
        category="combined_heat_and_power",
        variant=row["variant"],
        scale=row["scale"],
        carriers_in={row["carrier_in"]: 1.0},
        carriers_out={ELECTRICITY: alpha, HEAT: beta},
        primary_carrier_in=row["carrier_in"],
        primary_carrier_out=ELECTRICITY,
        flow_cap_max=row["flow_cap_max"],
        lifetime=int(row["lifetime"]),
        cost_flow_cap=row["cost_flow_cap"],
        color=row["color"],
        notes=(
            f"Energy-hub dispatch factors alpha={alpha:.2f} (electrical), "
            f"beta={beta:.2f} (thermal); power:heat ratio "
            f"{power_to_heat_ratio(alpha, beta):.2f}."
        ),
        params=passthrough_params(row, formula_columns=_FORMULA_COLUMNS),
    )


for _row in _ROWS:
    register_technology(f"chp_{_row['variant']}_{_row['scale']}", partial(_build, _row))
