"""Generation technologies: importing this package registers them.

Separate from ``conversion_technologies.new`` (conversion: carrier in ->
carrier out) because a generation technology has no input carrier and its
output depends on weather and site: it is a Calliope ``supply`` technology
whose available output per hour comes from a profile.

Today: rooftop photovoltaics (``pv``). The PV profile engine runs NREL's
PVWatts v8 through NREL-PySAM with the same parameter mapping and defaults
as EnerPlanET's PV service (``enerplanet/pysam-pv``), so both give the same
numbers; weather comes from the ``weather`` package's curated variables.
Costs follow THD-Spatial-AI/OpenTech-DB. See ``docs/generation_technologies.md``.

Parameters live in this subpackage's own ``technologies.csv`` and
``costs.csv`` (same loader and columns convention as ``new``).
"""

from __future__ import annotations

from conversion_technologies.generation_technologies import pv  # noqa: F401
from conversion_technologies.generation_technologies.pv import (
    specific as _pv_specific,  # noqa: F401
)
