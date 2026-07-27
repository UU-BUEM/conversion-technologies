"""Export a TechnologySpec as current Calliope (0.7.x, ``flow_*``) YAML.

Current Calliope removed the separate ``conversion_plus`` base tech: a plain
``conversion`` tech now takes carrier_in/carrier_out as lists, and per-carrier
efficiency (``flow_in_eff``/``flow_out_eff`` with ``dims: carriers``) is used
to fix the ratio between each carrier and the technology's single shared
internal flow. That is sufficient for every technology in this package
(fixed heat-pump COP, fixed CHP power-to-heat ratio, etc.).

It is NOT sufficient for genuinely alternative/either-or carrier choices
(what v0.5.1 called ``carrier_tiers``) — Calliope removed that from the base
schema entirely; expressing it now requires hand-written "user-defined math".
No technology in this package currently needs that, so exporters here raise
nothing for it, but see docs/calliope_schema_mapping.md and .claude/open.md.
"""

from __future__ import annotations

from typing import Any

from conversion_technologies.core.technology import TechnologySpec

schema_name = "modern"

_MULTI_CARRIER_NOTE = (
    "Multi-carrier flows share one internal capacity variable; per-carrier "
    "flow_in_eff/flow_out_eff fixes their ratios for this linear-efficiency "
    "use case. Genuinely alternative/either-or carriers would need "
    "hand-written user-defined math (carrier_tiers/carrier_ratios were "
    "removed from the base schema in this Calliope version)."
)


def _carrier_field(carriers: dict[str, float]) -> Any:
    keys = list(carriers.keys())
    return keys[0] if len(keys) == 1 else keys


def _efficiency_field(carriers: dict[str, float]) -> Any:
    if len(carriers) == 1:
        return next(iter(carriers.values()))
    return {
        "data": list(carriers.values()),
        "index": list(carriers.keys()),
        "dims": "carriers",
    }


def _cost_field(value: float) -> dict[str, Any]:
    return {"data": value, "index": "monetary", "dims": "costs"}


def export(tech: TechnologySpec) -> dict[str, Any]:
    """Return a ``conversion`` tech body for ``tech``."""
    body: dict[str, Any] = {"base_tech": "conversion", "name": tech.name}
    if tech.color:
        body["color"] = tech.color

    body["carrier_in"] = _carrier_field(tech.carriers_in)
    body["carrier_out"] = _carrier_field(tech.carriers_out)
    body["flow_in_eff"] = _efficiency_field(tech.carriers_in)
    body["flow_out_eff"] = _efficiency_field(tech.carriers_out)

    body["flow_cap_max"] = tech.flow_cap_max
    if tech.flow_cap_min is not None:
        body["flow_cap_min"] = tech.flow_cap_min
    body["lifetime"] = tech.lifetime

    body["cost_flow_cap"] = _cost_field(tech.cost_flow_cap)
    if tech.cost_flow_om_annual is not None:
        body["cost_flow_cap_annual"] = _cost_field(tech.cost_flow_om_annual)
    if tech.cost_flow_out is not None:
        body["cost_flow_out"] = _cost_field(tech.cost_flow_out)

    comment_parts = [tech.notes] if tech.notes else []
    if len(tech.carriers_in) > 1 or len(tech.carriers_out) > 1:
        comment_parts.append(_MULTI_CARRIER_NOTE)
    if comment_parts:
        body["_comment"] = " ".join(comment_parts)

    return body
