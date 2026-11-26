"""Calliope "additional math" fixing where a storage technology may end the
model period.

Calliope 0.7.0 offers two ways to treat a storage's first and last
timestep (``calliope/math/base.yaml``): ``cyclic_storage`` (the last level
feeds the first) and ``storage_initial`` (a fixed starting level). With
both set, ``set_storage_initial`` forces the *last* level to equal the
starting level too. For an electric-vehicle battery that is often
infeasible: on the last evening of the year the car may be away or nearly
empty. Without cyclic storage, the base math leaves the final level free,
so the optimiser would end the year empty to save cost.

This module adds the missing lower bound on the final level::

    storage[last timestep] >= storage_final_min * storage_cap

``storage_final_min`` is a fraction of the storage capacity, like
``storage_initial``. Its default is 0, which the ``where`` treats as "not
set", so a storage technology without the parameter behaves exactly as in
the base math. Used with ``cyclic_storage: false`` and ``storage_initial``
taken from a simulated trajectory (occupancy's EV battery), the model
starts at the simulated level and ends at least at the simulated level:
the simulated year itself is then always a feasible solution.

The constraint lists the storage technologies explicitly, for the same
reason as ``ratio_math``: Calliope can prune every other technology.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from conversion_technologies.core.technology import TechnologySpec

PARAMETER = "storage_final_min"
_CONSTRAINT = "storage_final_level_min"


def build_storage_final_math(
    techs: Iterable[TechnologySpec],
) -> dict[str, Any] | None:
    """The final-level bound for every storage technology in ``techs``;
    ``None`` if there is none."""
    ids = sorted(t.id for t in techs if t.base_tech == "storage")
    if not ids:
        return None
    return {
        "parameters": {
            PARAMETER: {
                "description": (
                    "Minimum stored level in the last timestep, as a fraction "
                    "of storage capacity (0-1); 0 = not set. For use with "
                    "cyclic_storage false, e.g. so an EV battery ends the year "
                    "at least where a simulated year ends."
                ),
                "default": 0,
            }
        },
        "constraints": {
            _CONSTRAINT: {
                "description": (
                    "A storage technology must end the model period with at "
                    "least storage_final_min x storage_cap stored."
                ),
                "foreach": ["nodes", "techs"],
                "where": f"storage AND {PARAMETER} AND [{', '.join(ids)}] in techs",
                "equations": [
                    {
                        "expression": (
                            "storage[timesteps=$final_step] >= "
                            f"{PARAMETER} * storage_cap"
                        )
                    }
                ],
                "slices": {
                    "final_step": [{"expression": "get_val_at_index(timesteps=-1)"}]
                },
            }
        },
    }
