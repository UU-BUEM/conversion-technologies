"""Registry of available Calliope schema exporters, keyed by schema name.

Only ``modern`` (current Calliope) exists today -- the earlier ``legacy_v051``
exporter was removed once it became clear only current Calliope was actually
in use (see ``.claude/resolved.md``). The registry stays dict-based, not a
single hardcoded call, so adding a schema back (or a new one) is still just
one module + one line here, not a CLI/exporter-shape change.
"""

from __future__ import annotations

from conversion_technologies.calliope_export import modern

EXPORTERS = {
    modern.schema_name: modern,
}

SCHEMA_CHOICES = tuple(EXPORTERS)

__all__ = ["EXPORTERS", "SCHEMA_CHOICES"]
