"""Condensing natural gas boiler: natural gas -> heat."""

from __future__ import annotations

from functools import partial

from conversion_technologies.core.carriers import HEAT, NATURAL_GAS
from conversion_technologies.core.data_loader import load_json_resource
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.new.boiler.generic.thermal_efficiency import (
    derated_efficiency,
)

_DEFAULTS = load_json_resource(
    "conversion_technologies.new.boiler", "data/defaults.json"
)


def _build(scale: str) -> TechnologySpec:
    params = _DEFAULTS["gas_boiler"][scale]
    efficiency = derated_efficiency(params["efficiency"], params["part_load_factor"])
    return TechnologySpec(
        id=f"boiler_gas_{scale}",
        name=f"Condensing natural gas boiler ({scale})",
        category="boiler",
        scale=scale,
        carriers_in={NATURAL_GAS: 1.0},
        carriers_out={HEAT: efficiency},
        primary_carrier_in=NATURAL_GAS,
        primary_carrier_out=HEAT,
        flow_cap_max=params["flow_cap_max"],
        lifetime=params["lifetime"],
        cost_flow_cap=params["cost_flow_cap"],
        color="#8D8D8D",
        notes=(
            f"Part-load-derated efficiency {efficiency:.0%} "
            f"(nameplate {params['efficiency']:.0%})."
        ),
    )


for _scale in ("household", "building", "community"):
    register_technology(f"boiler_gas_{_scale}", partial(_build, _scale))
