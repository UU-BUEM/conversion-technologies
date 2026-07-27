"""Natural gas CHP: natural gas -> electricity + heat."""

from __future__ import annotations

from functools import partial

from conversion_technologies.core.carriers import ELECTRICITY, HEAT, NATURAL_GAS
from conversion_technologies.core.data_loader import load_json_resource
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.new.combined_heat_and_power.generic.alpha_beta import (
    power_to_heat_ratio,
    validate_dispatch_factors,
)

_DEFAULTS = load_json_resource(
    "conversion_technologies.new.combined_heat_and_power", "data/defaults.json"
)


def _build(scale: str) -> TechnologySpec:
    params = _DEFAULTS["gas_chp"][scale]
    alpha, beta = params["alpha"], params["beta"]
    validate_dispatch_factors(alpha, beta)
    return TechnologySpec(
        id=f"chp_gas_{scale}",
        name=f"Natural gas combined heat and power ({scale})",
        category="combined_heat_and_power",
        scale=scale,
        carriers_in={NATURAL_GAS: 1.0},
        carriers_out={ELECTRICITY: alpha, HEAT: beta},
        primary_carrier_in=NATURAL_GAS,
        primary_carrier_out=ELECTRICITY,
        flow_cap_max=params["flow_cap_max"],
        lifetime=params["lifetime"],
        cost_flow_cap=params["cost_flow_cap"],
        color="#C1502E",
        notes=(
            f"Energy-hub dispatch factors alpha={alpha:.2f} (electrical), "
            f"beta={beta:.2f} (thermal); power:heat ratio "
            f"{power_to_heat_ratio(alpha, beta):.2f}."
        ),
    )


for _scale in ("household", "building", "community"):
    register_technology(f"chp_gas_{_scale}", partial(_build, _scale))
