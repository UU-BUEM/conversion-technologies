"""conversion_technologies.

Calliope-compatible technology definitions for heat-producing energy
conversion options (heat pumps, boilers, combined heat and power) from
household to community scale. See ``conversion_technologies.new`` for the
registry of candidate technologies and ``conversion_technologies.calliope_export``
for the YAML exporters.
"""

from __future__ import annotations

try:
    from conversion_technologies._version import __version__
except ImportError:  # pragma: no cover - only hit in an unbuilt source checkout
    __version__ = "0.0.0.dev0"

from conversion_technologies import (
    new,  # noqa: F401,E402  (registers all built-in technologies)
)

__all__ = ["__version__"]
