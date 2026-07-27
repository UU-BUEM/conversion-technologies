"""Load JSON default-parameter files bundled as package data.

Keeps numeric defaults (capacities, costs, efficiencies) out of Python source,
matching the convention used by the sibling ``occupancy`` package.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_json_resource(package: str, resource: str) -> dict[str, Any]:
    """Load and parse a JSON file bundled inside ``package`` at path ``resource``."""
    traversable = resources.files(package).joinpath(resource)
    with traversable.open("r", encoding="utf-8") as fh:
        return json.load(fh)
