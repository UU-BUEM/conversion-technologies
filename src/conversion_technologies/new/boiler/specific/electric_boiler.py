"""Electric resistance boiler: electricity -> heat, near 1:1."""

from __future__ import annotations

from functools import partial

from conversion_technologies.core.carriers import ELECTRICITY, HEAT
from conversion_technologies.core.data_loader import load_json_resource
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec

_DEFAULTS = load_json_resource(
    "conversion_technologies.new.boiler", "data/defaults.json"
)


def _build(scale: str) -> TechnologySpec:
    params = _DEFAULTS["electric_boiler"][scale]
    efficiency = params["efficiency"]
    return TechnologySpec(
        id=f"boiler_electric_{scale}",
        name=f"Electric resistance boiler ({scale})",
        category="boiler",
        scale=scale,
        carriers_in={ELECTRICITY: 1.0},
        carriers_out={HEAT: efficiency},
        primary_carrier_in=ELECTRICITY,
        primary_carrier_out=HEAT,
        flow_cap_max=params["flow_cap_max"],
        lifetime=params["lifetime"],
        cost_flow_cap=params["cost_flow_cap"],
        color="#F2C14E",
        notes=(
            f"Nameplate efficiency {efficiency:.0%}; "
            "near-1:1 electricity-to-heat conversion."
        ),
    )


for _scale in ("household", "building", "community"):
    register_technology(f"boiler_electric_{_scale}", partial(_build, _scale))
