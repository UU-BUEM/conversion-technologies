"""Air-source electric heat pump: electricity + ambient (outdoor air) heat -> heat."""

from __future__ import annotations

from functools import partial

from conversion_technologies.core.carriers import AMBIENT_HEAT, ELECTRICITY, HEAT
from conversion_technologies.core.data_loader import load_json_resource
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.new.heat_pump.generic.cop_calculation import carnot_cop

_DEFAULTS = load_json_resource(
    "conversion_technologies.new.heat_pump", "data/defaults.json"
)


def _build(scale: str) -> TechnologySpec:
    tech_defaults = _DEFAULTS["electric_heat_pump"]
    params = tech_defaults[scale]
    cop = carnot_cop(
        t_source_c=tech_defaults["design_source_temp_c"],
        t_sink_c=tech_defaults["design_sink_temp_c"],
        carnot_efficiency=params["carnot_efficiency"],
    )
    assert isinstance(cop, float)  # scalar in, scalar out
    return TechnologySpec(
        id=f"heat_pump_electric_{scale}",
        name=f"Air-source electric heat pump ({scale})",
        category="heat_pump",
        scale=scale,
        carriers_in={ELECTRICITY: 1.0, AMBIENT_HEAT: cop - 1.0},
        carriers_out={HEAT: cop},
        primary_carrier_in=ELECTRICITY,
        primary_carrier_out=HEAT,
        flow_cap_max=params["flow_cap_max"],
        lifetime=params["lifetime"],
        cost_flow_cap=params["cost_flow_cap"],
        color="#4C9F70",
        notes=(
            f"COP={cop:.2f} at design conditions "
            f"(source={tech_defaults['design_source_temp_c']}C, "
            f"sink={tech_defaults['design_sink_temp_c']}C, "
            f"carnot_efficiency={params['carnot_efficiency']})."
        ),
    )


for _scale in ("household", "building", "community"):
    register_technology(f"heat_pump_electric_{_scale}", partial(_build, _scale))
