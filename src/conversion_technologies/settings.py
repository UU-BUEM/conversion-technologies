"""Single centralised place for environment-variable defaults.

Mirrors the ``EnvSettings`` convention used by the sibling ``weather`` package:
no other module reads ``os.environ`` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvSettings:
    output_dir: str = os.environ.get("CONVERSION_TECH_OUTPUT_DIR", "outputs")
    # Absolute path to a folder containing your own technologies.csv +
    # costs.csv (same columns as the bundled defaults) -- see
    # core.csv_loader.load_technology_rows. Must be set before the process
    # starts (e.g. in .env); technologies are registered once, at import time.
    params_dir: str | None = os.environ.get("CONVERSION_TECH_PARAMS_DIR")


SETTINGS = EnvSettings()
