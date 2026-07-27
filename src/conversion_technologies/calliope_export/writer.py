"""Serialise exported tech bodies to standalone Calliope-importable YAML files."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 100


def dump_techs_yaml(bodies: dict[str, dict[str, Any]]) -> str:
    """Render one or more tech bodies under a single shared ``techs:`` document."""
    stream = StringIO()
    _yaml.dump({"techs": bodies}, stream)
    return stream.getvalue()


def write_techs_yaml(bodies: dict[str, dict[str, Any]], path: Path) -> Path:
    """Write the rendered YAML for ``bodies`` to ``path``.

    Creates parent directories as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_techs_yaml(bodies), encoding="utf-8")
    return path


def dump_technology_yaml(tech_id: str, body: dict[str, Any]) -> str:
    """Render a single tech body as a ``techs:`` document Calliope can import as-is."""
    return dump_techs_yaml({tech_id: body})


def write_technology_yaml(tech_id: str, body: dict[str, Any], path: Path) -> Path:
    """Write the rendered YAML for a single ``tech_id`` to ``path``."""
    return write_techs_yaml({tech_id: body}, path)
