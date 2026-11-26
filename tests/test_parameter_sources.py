"""Every bundled parameter value must be traceable to a documented source.

``docs/sources/parameter_sources.csv`` records, for each value cell of
``new/`` and ``generation_technologies/`` ``technologies.csv`` and
``costs.csv``, where the value comes from
(``source_id`` -> ``docs/sources/references.csv``), the raw source value and
unit, and the conversion applied. These tests fail if a value is changed in
one file but not the other, or if a new value is added without provenance.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "conversion_technologies"
PARAMS_DIRS = (PACKAGE_DIR / "new", PACKAGE_DIR / "generation_technologies")
SOURCES_DIR = ROOT / "docs" / "sources"

# Identity/structure columns: not parameters, so they need no provenance.
_STRUCTURAL = {
    "category",
    "variant",
    "scale",
    "name",
    "color",
    "carrier_in",
    "carrier_in_2",
    "carrier_out",
}
_BASES = {"direct", "derived", "proxy", "assumption"}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _value(text: str) -> float | str:
    """Numbers compare as numbers; a text setting (e.g. a PV module type)
    as text."""
    try:
        return float(text)
    except ValueError:
        return text.strip()


def _catalogue_cells() -> dict[tuple[str, str, str, str], float | str]:
    cells = {}
    for params_dir in PARAMS_DIRS:
        for name in ("technologies.csv", "costs.csv"):
            for row in _read(params_dir / name):
                key = (row["category"], row["variant"], row["scale"])
                for col, val in row.items():
                    if col in _STRUCTURAL or val.strip() == "":
                        continue
                    cells[(*key, col)] = _value(val)
    return cells


def _provenance() -> dict[tuple[str, str, str, str], dict[str, str]]:
    rows = _read(SOURCES_DIR / "parameter_sources.csv")
    out = {}
    for r in rows:
        key = (r["category"], r["variant"], r["scale"], r["parameter"])
        assert key not in out, f"duplicate provenance row for {key}"
        out[key] = r
    return out


def test_every_catalogue_value_has_a_provenance_row() -> None:
    missing = sorted(set(_catalogue_cells()) - set(_provenance()))
    assert not missing, f"values without a parameter_sources.csv row: {missing}"


def test_every_provenance_row_matches_the_catalogue_value() -> None:
    cells = _catalogue_cells()
    for key, row in _provenance().items():
        assert key in cells, f"parameter_sources.csv row {key} has no catalogue value"
        expected = _value(row["value"])
        if isinstance(cells[key], str) or isinstance(expected, str):
            assert cells[key] == expected, key
        else:
            assert cells[key] == pytest.approx(expected, rel=1e-9), key


def test_every_provenance_row_names_a_known_source_and_basis() -> None:
    known = {r["source_id"] for r in _read(SOURCES_DIR / "references.csv")}
    for key, row in _provenance().items():
        assert row["basis"] in _BASES, key
        if row["basis"] == "assumption":
            continue  # modelling assumptions are labelled as such, not sourced
        assert row["source_id"] in known, (
            f"{key}: unknown source_id {row['source_id']!r}"
        )
        assert row["source_item"].strip(), (
            f"{key}: source_item must say where in the source"
        )


def test_proxy_values_explain_why_they_are_proxies() -> None:
    for key, row in _provenance().items():
        if row["basis"] == "proxy":
            assert row["note"].strip(), f"{key}: a proxy value needs a note"
