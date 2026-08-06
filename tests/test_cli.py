from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

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


def test_list_command_filters_by_type_within_a_category(capsys) -> None:
    exit_code = main(["list", "--category", "hp", "--variant", "electric"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "heat_pump_electric_household" in out
    assert "heat_pump_electric_building" in out
    assert "heat_pump_electric_community" in out
    assert "heat_pump_geothermal" not in out


def test_list_command_type_filter_is_case_insensitive(capsys) -> None:
    exit_code = main(["list", "--category", "hp", "--variant", "ELECTRIC"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "heat_pump_electric_household" in out


def test_list_command_filters_by_scale(capsys) -> None:
    exit_code = main(["list", "--scale", "household"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "heat_pump_electric_household" in out
    assert "heat_pump_electric_building" not in out


def test_list_command_type_and_scale_combine_to_one_technology(capsys) -> None:
    exit_code = main(
        ["list", "--category", "hp", "--variant", "electric", "--scale", "household"]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "heat_pump_electric_household" in lines[0]


def test_list_command_no_match_reports_available_types(capsys) -> None:
    exit_code = main(["list", "--category", "boiler", "--variant", "geothermal"])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "electric" in out and "gas" in out and "biomass" in out


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


def test_export_all_category_and_type_isolate_one_variant_all_scales(
    tmp_path: Path,
) -> None:
    output = tmp_path / "heat_pump_electric.yaml"
    exit_code = main(
        [
            "export-all",
            "--category",
            "hp",
            "--variant",
            "electric",
            "-o",
            str(output),
        ]
    )
    assert exit_code == 0
    text = output.read_text(encoding="utf-8")
    assert "heat_pump_electric_household" in text
    assert "heat_pump_electric_building" in text
    assert "heat_pump_electric_community" in text
    assert "heat_pump_geothermal" not in text


def test_export_all_category_type_and_scale_isolate_exactly_one_technology(
    tmp_path: Path,
) -> None:
    output = tmp_path / "one.yaml"
    exit_code = main(
        [
            "export-all",
            "--category",
            "hp",
            "--variant",
            "electric",
            "--scale",
            "household",
            "-o",
            str(output),
        ]
    )
    assert exit_code == 0
    text = output.read_text(encoding="utf-8")
    assert "heat_pump_electric_household" in text
    assert "heat_pump_electric_building" not in text


def test_export_all_config_file_selects_exact_technology_ids(tmp_path: Path) -> None:
    config_path = tmp_path / "scenario.json"
    config_path.write_text(
        json.dumps(
            {
                "technology_ids": [
                    "heat_pump_electric_household",
                    "boiler_gas_household",
                ],
                "schema": "modern",
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    exit_code = main(
        ["export-all", "--config", str(config_path), "-o", str(output_dir)]
    )
    assert exit_code == 0
    # additional_math.yaml (the multi-carrier-ratio fix, triggered here since
    # heat_pump_electric_household has two input carriers) is a real file but
    # not a per-technology export -- excluded from this "which technologies
    # got written" check.
    written = {p.stem for p in output_dir.glob("*.yaml") if p.stem != "additional_math"}
    assert written == {"heat_pump_electric_household", "boiler_gas_household"}
    body = (output_dir / "heat_pump_electric_household.yaml").read_text(
        encoding="utf-8"
    )
    assert "base_tech: conversion" in body  # modern schema, per the config file


def test_export_writes_additional_math_for_a_multi_carrier_technology(
    tmp_path: Path,
) -> None:
    output = tmp_path / "hp.yaml"
    exit_code = main(["export", "heat_pump_electric_household", "-o", str(output)])
    assert exit_code == 0
    math_path = tmp_path / "hp.additional_math.yaml"
    assert math_path.exists()
    text = math_path.read_text(encoding="utf-8")
    assert "carrier_flow_ratio_in" in text
    assert "balance_conversion" in text


def test_export_no_custom_math_flag_skips_the_math_file(tmp_path: Path) -> None:
    output = tmp_path / "hp.yaml"
    exit_code = main(
        [
            "export",
            "heat_pump_electric_household",
            "-o",
            str(output),
            "--no-custom-math",
        ]
    )
    assert exit_code == 0
    assert not (tmp_path / "hp.additional_math.yaml").exists()


def test_export_all_boiler_only_writes_no_math_file(tmp_path: Path, capsys) -> None:
    output = tmp_path / "boilers.yaml"
    exit_code = main(["export-all", "--category", "boiler", "-o", str(output)])
    assert exit_code == 0
    assert not (tmp_path / "boilers.additional_math.yaml").exists()
    assert "No custom math needed" in capsys.readouterr().out


def test_export_all_directory_mode_writes_one_shared_math_file(tmp_path: Path) -> None:
    exit_code = main(["export-all", "--category", "hp", "-o", str(tmp_path)])
    assert exit_code == 0
    math_path = tmp_path / "additional_math.yaml"
    assert math_path.exists()
    text = math_path.read_text(encoding="utf-8")
    assert "heat_pump_electric_household" in text
    assert "heat_pump_geothermal_household" in text


def test_weather_cop_command_writes_three_files(tmp_path: Path, monkeypatch) -> None:
    index = pd.date_range("2018-01-01 00:00:00", "2018-12-31 23:00:00", freq="h")
    weather_df = pd.DataFrame({"T": [8.0] * len(index)}, index=index)
    monkeypatch.setattr(
        "conversion_technologies.new.heat_pump.weather_cop.get_point_weather",
        lambda *args, **kwargs: weather_df,
    )
    output_dir = tmp_path / "out"
    exit_code = main(
        [
            "weather-cop",
            "heat_pump_electric_household",
            "--latitude",
            "52.09",
            "--longitude",
            "5.12",
            "--year",
            "2018",
            "-o",
            str(output_dir),
        ]
    )
    assert exit_code == 0
    assert (output_dir / "heat_pump_electric_household_flow_out_eff.csv").exists()
    assert (output_dir / "heat_pump_electric_household_flow_in_eff.csv").exists()
    assert (output_dir / "heat_pump_electric_household_data_tables.yaml").exists()
