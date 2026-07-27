"""Serialise an exported tech body to a standalone Calliope-importable YAML file."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 100


def dump_technology_yaml(tech_id: str, body: dict[str, Any]) -> str:
    """Render ``body`` as a ``techs:`` document Calliope can import as-is."""
    stream = StringIO()
    _yaml.dump({"techs": {tech_id: body}}, stream)
    return stream.getvalue()


def write_technology_yaml(tech_id: str, body: dict[str, Any], path: Path) -> Path:
    """Write the rendered YAML for ``tech_id`` to ``path``.

    Creates parent directories as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_technology_yaml(tech_id, body), encoding="utf-8")
    return path
