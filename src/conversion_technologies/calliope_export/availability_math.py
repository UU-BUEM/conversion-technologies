"""Calliope "additional math" for technologies that can only run while an
external condition allows it.

An EV charger can only charge a car that is parked and plugged in, and a
vehicle-to-grid discharger can only return energy from a connected car.
Calliope 0.7.0's base math has a lower bound ``flow_out_min_relative`` but
no time-varying *upper* bound on a technology's output relative to its
capacity (checked against ``calliope/math/base.yaml`` of 0.7.0), so this
module adds one::

    flow_out <= flow_cap * timestep_resolution * flow_out_max_relative

``flow_out_max_relative`` is a per-node, per-timestep fraction in [0, 1]
that the scenario supplies as data (for an EV: the share of each hour the
car is connected at home, which the occupancy package outputs as
``ev_plugged_in``). Its declared default is 1, so a technology without
data is unconstrained -- identical to the base model.

Which technologies get the constraint is structural
(``TechnologySpec.time_varying_availability``), never decided by name, and
the constraint's ``where`` lists them explicitly, for the same reason as
``ratio_math``: it lets Calliope prune every other technology before
building a dense nodes x techs x timesteps array.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from conversion_technologies.core.technology import TechnologySpec

PARAMETER = "flow_out_max_relative"
_CONSTRAINT = "flow_out_max_availability"


def build_availability_math(
    techs: Iterable[TechnologySpec],
) -> dict[str, Any] | None:
    """The availability constraint for every technology in ``techs`` with
    ``time_varying_availability``; ``None`` if there is none."""
    ids = sorted(t.id for t in techs if t.time_varying_availability)
    if not ids:
        return None
    return {
        "parameters": {
            PARAMETER: {
                "description": (
                    "Upper bound on a technology's output as a fraction of "
                    "its capacity in each timestep (0-1), e.g. the share of "
                    "an hour an electric vehicle is connected to its charger."
                ),
                "default": 1,
            }
        },
        "constraints": {
            _CONSTRAINT: {
                "description": (
                    "A technology with time-varying availability may only "
                    "use the available share of its capacity: "
                    "flow_out <= flow_cap x timestep_resolution x "
                    "flow_out_max_relative."
                ),
                "foreach": ["nodes", "techs", "carriers", "timesteps"],
                "where": f"carrier_out AND [{', '.join(ids)}] in techs",
                "equations": [
                    {
                        "expression": (
                            f"flow_out <= flow_cap * timestep_resolution * {PARAMETER}"
                        )
                    }
                ],
            }
        },
    }


def merge_math(*documents: dict[str, Any] | None) -> dict[str, Any] | None:
    """Merge several additional-math documents (``parameters``,
    ``constraints``, ...) into one; ``None`` if all are ``None``. A name
    defined twice raises rather than silently overwriting."""
    merged: dict[str, dict[str, Any]] = {}
    for document in documents:
        if not document:
            continue
        for section, entries in document.items():
            target = merged.setdefault(section, {})
            for name, body in entries.items():
                if name in target:
                    raise ValueError(f"additional math defines {section}.{name} twice.")
                target[name] = body
    return merged or None
