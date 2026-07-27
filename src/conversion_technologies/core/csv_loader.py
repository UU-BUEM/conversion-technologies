"""Load and join the ``technologies.csv`` + ``costs.csv`` parameter tables.

Every technology's fixed parameters live in two spreadsheet-friendly CSVs,
not in Python: ``technologies.csv`` (capacity, lifetime, efficiency/COP/
dispatch-factor inputs) and ``costs.csv`` (every ``cost_*`` column), joined
by ``(category, variant, scale)``. Kept as two files instead of one wide
table so each stays focused enough to review at a glance -- and instead of
one multi-sheet workbook (``.xlsx``/``.ods``) so both stay plain text (readable
git diffs, no new dependency to parse them). Blank cells become ``None`` --
each category's builder (``new/<category>/specific/__init__.py``) treats
that as "not applicable to this row."

To use your own values instead of the bundled defaults, copy both CSVs into
one folder, edit them (any spreadsheet program works -- LibreOffice will
prompt "Use CSV format!" on save; click it, this is expected and lossless
for a flat single-table CSV with no formulas), and set the
``CONVERSION_TECH_PARAMS_DIR`` environment variable to that folder's
absolute path *before* running the CLI. Technologies are registered once at
import time, so this cannot be changed via a CLI flag mid-run.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any

from conversion_technologies.settings import SETTINGS

# Columns every builder consumes itself (carrier topology, cosmetics, or
# already-named TechnologySpec fields) -- never copied into `params`.
# Category builders add their own formula-input columns (e.g. "efficiency",
# "alpha") on top of this before calling passthrough_params(); everything
# left over flows straight through to the `modern` exporter under its exact
# CSV column name.
STRUCTURAL_COLUMNS = frozenset(
    {
        "category",
        "variant",
        "scale",
        "name",
        "color",
        "carrier_in",
        "carrier_in_2",
        "flow_cap_max",
        "lifetime",
        "cost_flow_cap",
    }
)

# costs.csv repeats these identity columns (so it's readable/editable on its
# own); they're dropped on merge since technologies.csv's copy is authoritative.
_COST_IDENTITY_COLUMNS = frozenset({"category", "variant", "scale", "name", "color"})


def _coerce(value: str) -> str | float | None:
    """Blank cells become ``None``; numeric-looking cells become ``float``."""
    value = value.strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return value


def _load_csv(package: str, filename: str) -> list[dict[str, Any]]:
    # utf-8-sig strips a leading UTF-8 BOM if present (Excel commonly saves
    # CSV that way on Windows) and behaves exactly like utf-8 otherwise --
    # without this, a BOM silently renames the first column ("category"
    # becomes "﻿category") and every row lookup fails.
    if SETTINGS.params_dir:
        text = (Path(SETTINGS.params_dir) / filename).read_text(encoding="utf-8-sig")
    else:
        text = (
            resources.files(package).joinpath(filename).read_text(encoding="utf-8-sig")
        )
    reader = csv.DictReader(text.splitlines())
    return [{key: _coerce(value) for key, value in row.items()} for row in reader]


def _row_key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (row["category"], row["variant"], row["scale"])


def load_technology_rows(package: str) -> list[dict[str, Any]]:
    """Load ``technologies.csv`` and ``costs.csv`` from ``package``, joined.

    Reads ``SETTINGS.params_dir`` if set (both files must be in that one
    folder), otherwise the bundled files inside ``package``.

    Raises
    ------
    ValueError
        If a ``costs.csv`` row's (category, variant, scale) matches no
        ``technologies.csv`` row -- almost always a spelling mismatch
        between the two files.
    """
    tech_rows = _load_csv(package, "technologies.csv")
    cost_rows = _load_csv(package, "costs.csv")
    cost_by_key = {_row_key(row): row for row in cost_rows}

    matched_keys: set[tuple[Any, Any, Any]] = set()
    merged: list[dict[str, Any]] = []
    for row in tech_rows:
        key = _row_key(row)
        combined = dict(row)
        cost_row = cost_by_key.get(key)
        if cost_row is not None:
            matched_keys.add(key)
            for cost_key, cost_value in cost_row.items():
                if cost_key not in _COST_IDENTITY_COLUMNS:
                    combined[cost_key] = cost_value
        merged.append(combined)

    orphaned = set(cost_by_key) - matched_keys
    if orphaned:
        raise ValueError(
            f"costs.csv has {len(orphaned)} row(s) with no matching technologies.csv "
            f"row (category, variant, scale): {sorted(orphaned)}. Check both files "
            "use the same category/variant/scale spelling."
        )

    return merged


def passthrough_params(
    row: dict[str, Any], *, formula_columns: Iterable[str] = ()
) -> dict[str, float]:
    """Every non-blank column in ``row`` not consumed elsewhere, by name.

    ``formula_columns`` lists this category's own columns that feed a
    derivation instead of being passed straight through (e.g. heat pump's
    ``efficiency``/``design_source_temp_c``/``design_sink_temp_c``, which
    determine ``carriers_in``/``carriers_out`` but are not themselves a
    Calliope key). Everything else -- including any column a future version
    of this CSV adds that this function has never heard of -- ends up in
    the returned dict, keyed by its exact column name.
    """
    exclude = STRUCTURAL_COLUMNS | set(formula_columns)
    return {
        key: value
        for key, value in row.items()
        if key not in exclude and value is not None
    }
