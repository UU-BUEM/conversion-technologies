"""A small, explicit config for batch YAML export runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExportConfig:
    """Which technologies to export, in which Calliope schema, and where to.

    An empty ``technology_ids`` means "export every registered technology".
    """

    technology_ids: list[str] = field(default_factory=list)
    schema: str = "modern"
    output_dir: str = "outputs"


def load_export_config(path: str | Path) -> ExportConfig:
    """Load an :class:`ExportConfig` from a JSON file.

    See ``config/data/default_scenario.json`` for the expected shape.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ExportConfig(
        technology_ids=data.get("technology_ids", []),
        schema=data.get("schema", "modern"),
        output_dir=data.get("output_dir", "outputs"),
    )
