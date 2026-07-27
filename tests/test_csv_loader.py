from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conversion_technologies.core import csv_loader as csv_loader_module
from conversion_technologies.core.csv_loader import load_technology_rows
from conversion_technologies.settings import EnvSettings

_TECH_COLUMNS = [
    "category",
    "variant",
    "scale",
    "name",
    "color",
    "carrier_in",
    "carrier_in_2",
    "flow_cap_min",
    "flow_cap_max",
    "lifetime",
    "efficiency",
    "part_load_factor",
    "design_source_temp_c",
    "design_sink_temp_c",
    "alpha",
    "beta",
    "flow_ramping",
]
_COST_COLUMNS = [
    "category",
    "variant",
    "scale",
    "name",
    "color",
    "cost_flow_cap",
    "cost_om_annual",
    "cost_flow_in",
    "cost_flow_out",
    "cost_interest_rate",
]


def _cell(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _write_split_csvs(rows: list[dict], directory: Path) -> None:
    """Write ``rows`` (already-merged, as returned by load_technology_rows)
    back out as a technologies.csv + costs.csv pair in ``directory``."""
    tech_lines = [",".join(_TECH_COLUMNS)]
    cost_lines = [",".join(_COST_COLUMNS)]
    for row in rows:
        tech_lines.append(",".join(_cell(row, key) for key in _TECH_COLUMNS))
        cost_lines.append(",".join(_cell(row, key) for key in _COST_COLUMNS))
    (directory / "technologies.csv").write_text("\n".join(tech_lines), encoding="utf-8")
    (directory / "costs.csv").write_text("\n".join(cost_lines), encoding="utf-8")


def test_load_technology_rows_coerces_blanks_and_numbers() -> None:
    rows = load_technology_rows("conversion_technologies.new")
    assert len(rows) == 21  # 3 boiler variants + 2 heat pump + 2 CHP, x3 scales

    row = next(
        r
        for r in rows
        if r["category"] == "boiler"
        and r["variant"] == "electric"
        and r["scale"] == "household"
    )
    assert row["flow_cap_max"] == 12.0
    assert isinstance(row["flow_cap_max"], float)
    assert row["design_source_temp_c"] is None  # blank, boiler-irrelevant column
    assert row["carrier_in"] == "electricity"  # non-numeric cells stay strings


def test_load_technology_rows_joins_costs_by_category_variant_scale() -> None:
    rows = load_technology_rows("conversion_technologies.new")
    row = next(
        r
        for r in rows
        if r["category"] == "boiler"
        and r["variant"] == "electric"
        and r["scale"] == "household"
    )
    assert row["cost_flow_cap"] == 150.0
    assert row["cost_interest_rate"] == pytest.approx(0.10)


def test_load_technology_rows_filters_by_category() -> None:
    rows = load_technology_rows("conversion_technologies.new")
    categories = {r["category"] for r in rows}
    assert categories == {"boiler", "heat_pump", "combined_heat_and_power"}


def test_load_technology_rows_rejects_an_orphaned_costs_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "technologies.csv").write_text(
        "category,variant,scale,flow_cap_max\nboiler,electric,household,10\n",
        encoding="utf-8",
    )
    (tmp_path / "costs.csv").write_text(
        "category,variant,scale,cost_flow_cap\n"
        "boiler,electric,household,100\n"
        "boiler,electric,builidng,100\n",  # typo'd scale -> orphaned row
        encoding="utf-8",
    )
    # SETTINGS.params_dir is resolved from os.environ once, at import time,
    # so setting os.environ here would have no effect -- rebind the module's
    # SETTINGS reference directly instead (frozen, so a new instance, not a
    # mutated attribute).
    monkeypatch.setattr(
        csv_loader_module,
        "SETTINGS",
        EnvSettings(output_dir="outputs", params_dir=str(tmp_path)),
    )
    with pytest.raises(ValueError, match="no matching technologies.csv"):
        load_technology_rows("conversion_technologies.new")


def test_conversion_tech_params_dir_overrides_the_bundled_defaults(
    tmp_path: Path,
) -> None:
    """End-to-end: a custom CSV pair pointed to via the env var changes CLI output.

    Registration happens at package-import time, so this can only be
    observed in a fresh interpreter (hence a subprocess) -- it can't be
    tested against the already-imported package in this test process.
    """
    rows = load_technology_rows("conversion_technologies.new")
    for row in rows:
        if (
            row["category"] == "boiler"
            and row["variant"] == "electric"
            and row["scale"] == "household"
        ):
            row["flow_cap_max"] = 42.0  # still under the household ceiling
    _write_split_csvs(rows, tmp_path)

    output = tmp_path / "boiler_electric_household.yaml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "conversion_technologies",
            "export",
            "boiler_electric_household",
            "-o",
            str(output),
        ],
        env={**os.environ, "CONVERSION_TECH_PARAMS_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "flow_cap_max: 42.0" in output.read_text(encoding="utf-8")


def test_conversion_tech_params_dir_handles_a_utf8_bom(tmp_path: Path) -> None:
    """A UTF-8 BOM (what Excel writes by default on Windows) must not break
    header parsing -- without utf-8-sig decoding, a BOM silently renames the
    first column to '﻿category' and every row lookup raises KeyError.
    """
    rows = load_technology_rows("conversion_technologies.new")
    tech_lines = [",".join(_TECH_COLUMNS)]
    cost_lines = [",".join(_COST_COLUMNS)]
    for row in rows:
        tech_lines.append(",".join(_cell(row, key) for key in _TECH_COLUMNS))
        cost_lines.append(",".join(_cell(row, key) for key in _COST_COLUMNS))
    (tmp_path / "technologies.csv").write_text(
        "\n".join(tech_lines), encoding="utf-8-sig"
    )
    (tmp_path / "costs.csv").write_text("\n".join(cost_lines), encoding="utf-8-sig")

    result = subprocess.run(
        [sys.executable, "-m", "conversion_technologies", "list"],
        env={**os.environ, "CONVERSION_TECH_PARAMS_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "boiler_electric_household" in result.stdout
