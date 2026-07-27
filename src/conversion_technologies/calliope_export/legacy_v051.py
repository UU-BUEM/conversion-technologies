"""Export a TechnologySpec as Calliope v0.5.1 ``conversion_plus`` YAML.

Matches https://calliope.readthedocs.io/en/v0.5.1/user/configuration_reference.html
(abstract base technologies) exactly: ``parent: conversion_plus``, up to three
carrier_in/carrier_out tiers, nested ``constraints``/``costs.monetary``.
"""

from __future__ import annotations

from typing import Any

from conversion_technologies.core.technology import TechnologySpec

schema_name = "legacy_v051"

_IN_KEYS = ("carrier_in", "carrier_in_2", "carrier_in_3")
_OUT_KEYS = ("carrier_out", "carrier_out_2", "carrier_out_3")


def export(tech: TechnologySpec) -> dict[str, Any]:
    """Return a ``conversion_plus`` tech body for ``tech``."""
    carriers_in = list(tech.carriers_in.items())
    carriers_out = list(tech.carriers_out.items())
    if len(carriers_in) > len(_IN_KEYS) or len(carriers_out) > len(_OUT_KEYS):
        raise ValueError(
            f"Technology '{tech.id}' has more carriers than Calliope v0.5.1 "
            f"conversion_plus supports (max {len(_IN_KEYS)} in, {len(_OUT_KEYS)} out)."
        )

    body: dict[str, Any] = {"parent": "conversion_plus", "name": tech.name}
    if tech.color:
        body["color"] = tech.color

    body["primary_carrier_out"] = tech.primary_carrier_out or carriers_out[0][0]

    for key, (carrier, ratio) in zip(_IN_KEYS, carriers_in, strict=False):
        body[key] = {carrier: ratio}
    for key, (carrier, ratio) in zip(_OUT_KEYS, carriers_out, strict=False):
        body[key] = {carrier: ratio}

    constraints: dict[str, Any] = {
        "e_cap.max": tech.flow_cap_max,
        "lifetime": tech.lifetime,
    }
    if tech.flow_cap_min is not None:
        constraints["e_cap.min"] = tech.flow_cap_min
    body["constraints"] = constraints

    costs: dict[str, Any] = {"e_cap": tech.cost_flow_cap}
    if tech.cost_flow_om_annual is not None:
        costs["om_annual"] = tech.cost_flow_om_annual
    if tech.cost_flow_out is not None:
        costs["om_var"] = tech.cost_flow_out
    body["costs"] = {"monetary": costs}

    if tech.notes:
        body["_comment"] = tech.notes

    return body
