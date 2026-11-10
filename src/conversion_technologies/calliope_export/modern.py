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

``TechnologySpec.params`` is passed straight through here under its own
keys (unknown here, uninvented) -- e.g. a ``technologies.csv`` column named
``cost_flow_in`` becomes ``body["cost_flow_in"]`` with no code in this file
naming it. This is deliberate: this exporter's naming already tracks
current Calliope, so a future rename is a CSV-column edit, not a code
change.
"""

from __future__ import annotations

from typing import Any

from conversion_technologies.calliope_export.ratio_math import carrier_flow_ratios
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


# Calliope 0.7 creates one ``flow_cap`` per carrier -- inputs included -- and
# its base math applies these parameters to every one of them
# (calliope/math/base.yaml: ``flow_cap_max``/``flow_cap_min`` bound each
# carrier's flow_cap; ``cost_investment_flow_cap`` is ``foreach carriers``;
# ``cost_operation_fixed`` is ``sum(cost_om_annual * flow_cap, over=carriers)``).
# A scalar value therefore caps the *input* capacity too and charges
# investment/O&M on input *and* output capacity. This package's values are
# all per kW of the technology's primary output, so -- exactly as Calliope's
# own example models do (``index: heat, dims: carriers``) -- they are indexed
# on that carrier only. This is a shape translation dictated by Calliope's
# math, not a parameter value (CLAUDE.md "Hard conventions" #7).
_PER_CAPACITY_PARAMS = ("flow_cap_max", "flow_cap_min", "cost_om_annual")


def _primary_out(tech: TechnologySpec) -> str:
    if tech.primary_carrier_out:
        return tech.primary_carrier_out
    if len(tech.carriers_out) == 1:
        return next(iter(tech.carriers_out))
    raise ValueError(
        f"Technology '{tech.id}' has several output carriers but no "
        "primary_carrier_out -- its capacity has no unambiguous carrier."
    )


def _capacity_field(value: float, carrier: str) -> dict[str, Any]:
    return {"data": value, "index": carrier, "dims": "carriers"}


def _capacity_cost_field(value: float, carrier: str) -> dict[str, Any]:
    return {
        "data": value,
        "index": [["monetary", carrier]],
        "dims": ["costs", "carriers"],
    }


def export(tech: TechnologySpec) -> dict[str, Any]:
    """Return a ``conversion`` tech body for ``tech``."""
    body: dict[str, Any] = {"base_tech": "conversion", "name": tech.name}
    if tech.color:
        body["color"] = tech.color

    body["carrier_in"] = _carrier_field(tech.carriers_in)
    body["carrier_out"] = _carrier_field(tech.carriers_out)
    body["flow_in_eff"] = _efficiency_field(tech.carriers_in)
    body["flow_out_eff"] = _efficiency_field(tech.carriers_out)
    # carrier_flow_ratio_in/out's value lives here, on the tech itself --
    # see ratio_math.carrier_flow_ratios()'s docstring for why it cannot
    # live inside additional_math.yaml's parameters block under real
    # Calliope 0.7.0.
    body.update(carrier_flow_ratios(tech))

    out = _primary_out(tech)
    body["flow_cap_max"] = _capacity_field(tech.flow_cap_max, out)
    body["lifetime"] = tech.lifetime
    body["cost_flow_cap"] = _capacity_cost_field(tech.cost_flow_cap, out)

    for key, value in tech.params.items():
        if key in _PER_CAPACITY_PARAMS:
            body[key] = (
                _capacity_cost_field(value, out)
                if key.startswith("cost_")
                else _capacity_field(value, out)
            )
        elif key.startswith("cost_"):
            body[key] = _cost_field(value)
        else:
            body[key] = value

    comment_parts = [tech.notes] if tech.notes else []
    if len(tech.carriers_in) > 1 or len(tech.carriers_out) > 1:
        comment_parts.append(_MULTI_CARRIER_NOTE)
    if comment_parts:
        # Calliope 0.7.0's real schema rejects any tech key starting with
        # an underscore (`^[^_^\d][\w]*$`) -- confirmed by validating a
        # real export against an installed calliope==0.7.0, not assumed.
        # `comment` (no leading underscore) is accepted as an arbitrary
        # extra tech parameter.
        body["comment"] = " ".join(comment_parts)

    return body
