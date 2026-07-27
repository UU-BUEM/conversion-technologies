"""Registry of available Calliope schema exporters, keyed by schema name."""

from __future__ import annotations

from conversion_technologies.calliope_export import legacy_v051, modern

EXPORTERS = {
    legacy_v051.schema_name: legacy_v051,
    modern.schema_name: modern,
}

SCHEMA_CHOICES = tuple(EXPORTERS)

__all__ = ["EXPORTERS", "SCHEMA_CHOICES"]
