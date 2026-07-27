"""Biomass (wood pellet) boiler: biomass -> heat."""

from __future__ import annotations

from functools import partial

from conversion_technologies.core.carriers import BIOMASS, HEAT
from conversion_technologies.core.data_loader import load_json_resource
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec

_DEFAULTS = load_json_resource(
    "conversion_technologies.new.boiler", "data/defaults.json"
)


def _build(scale: str) -> TechnologySpec:
    params = _DEFAULTS["biomass_boiler"][scale]
    efficiency = params["efficiency"]
    return TechnologySpec(
        id=f"boiler_biomass_{scale}",
        name=f"Biomass (wood pellet) boiler ({scale})",
        category="boiler",
        scale=scale,
        carriers_in={BIOMASS: 1.0},
        carriers_out={HEAT: efficiency},
        primary_carrier_in=BIOMASS,
        primary_carrier_out=HEAT,
        flow_cap_max=params["flow_cap_max"],
        lifetime=params["lifetime"],
        cost_flow_cap=params["cost_flow_cap"],
        color="#7A5230",
        notes=f"Nameplate efficiency {efficiency:.0%}.",
    )


for _scale in ("household", "building", "community"):
    register_technology(f"boiler_biomass_{_scale}", partial(_build, _scale))
