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


SETTINGS = EnvSettings()
