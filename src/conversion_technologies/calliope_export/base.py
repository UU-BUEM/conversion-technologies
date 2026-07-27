"""Shape every Calliope schema exporter must satisfy.

Exporters are plain modules (``legacy_v051``, ``modern``), not classes; this
Protocol exists purely to document and type-check that shape.
"""

from __future__ import annotations

from typing import Any, Protocol

from conversion_technologies.core.technology import TechnologySpec


class CalliopeExporter(Protocol):
    """A module that turns a TechnologySpec into a Calliope tech YAML body."""

    schema_name: str

    def export(self, tech: TechnologySpec) -> dict[str, Any]:
        """Return the tech's attribute mapping.

        Excludes the surrounding ``techs:`` key -- callers wrap it themselves.
        """
        ...
