from __future__ import annotations

import json
from pathlib import Path

from conversion_technologies.cli import main


def test_info_command_runs(capsys) -> None:
    exit_code = main(["info"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "conversion_technologies" in out


def test_list_command_runs(capsys) -> None:
    exit_code = main(["list"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "boiler_electric_household" in out


def test_list_command_filters_by_category_alias(capsys) -> None:
    exit_code = main(["list", "--category", "hp"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "heat_pump_electric_household" in out
    assert "boiler_electric_household" not in out


def test_export_command_writes_a_file(tmp_path: Path) -> None:
    output = tmp_path / "hp.yaml"
    exit_code = main(["export", "heat_pump_electric_household", "-o", str(output)])
    assert exit_code == 0
    assert output.exists()


def test_export_all_command_writes_one_file_per_technology(tmp_path: Path) -> None:
    exit_code = main(["export-all", "-o", str(tmp_path)])
    assert exit_code == 0
    assert len(list(tmp_path.glob("*.yaml"))) > 0


def test_export_all_category_alias_writes_a_single_combined_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "heat_pump.yaml"
    exit_code = main(["export-all", "--category", "hp", "-o", str(output)])
    assert exit_code == 0
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "heat_pump_electric_household" in text
    assert "heat_pump_geothermal_household" in text
    assert "boiler_electric_household" not in text


def test_export_all_category_to_directory_only_writes_that_category(
    tmp_path: Path,
) -> None:
    exit_code = main(["export-all", "--category", "boiler", "-o", str(tmp_path)])
    assert exit_code == 0
    written = {p.stem for p in tmp_path.glob("*.yaml")}
    assert written == {
        "boiler_electric_household",
        "boiler_electric_building",
        "boiler_electric_community",
        "boiler_gas_household",
        "boiler_gas_building",
        "boiler_gas_community",
        "boiler_biomass_household",
        "boiler_biomass_building",
        "boiler_biomass_community",
    }


def test_export_all_config_file_selects_exact_technology_ids(tmp_path: Path) -> None:
    config_path = tmp_path / "scenario.json"
    config_path.write_text(
        json.dumps(
            {
                "technology_ids": [
                    "heat_pump_electric_household",
                    "boiler_gas_household",
                ],
                "schema": "legacy_v051",
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    exit_code = main(
        ["export-all", "--config", str(config_path), "-o", str(output_dir)]
    )
    assert exit_code == 0
    written = {p.stem for p in output_dir.glob("*.yaml")}
    assert written == {"heat_pump_electric_household", "boiler_gas_household"}
    body = (output_dir / "heat_pump_electric_household.yaml").read_text(
        encoding="utf-8"
    )
    assert "conversion_plus" in body  # legacy_v051 schema, per the config file
