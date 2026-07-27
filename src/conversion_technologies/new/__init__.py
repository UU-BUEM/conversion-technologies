"""Candidate conversion technologies: importing this package registers all of them.

Out of scope here: ``conversion_technologies.existing`` (bottom-up, occupancy
and weather driven simulation of already-installed stock, e.g. ``fireplace.py``)
is a separate modeling paradigm and is not imported from this package.
"""

from __future__ import annotations

from conversion_technologies.new import (  # noqa: F401
    boiler,
    combined_heat_and_power,
    heat_pump,
)
from conversion_technologies.new.boiler import (
    specific as _boiler_specific,  # noqa: F401
)
from conversion_technologies.new.combined_heat_and_power import (  # noqa: F401
    specific as _chp_specific,
)
from conversion_technologies.new.heat_pump import (
    specific as _heat_pump_specific,  # noqa: F401
)
