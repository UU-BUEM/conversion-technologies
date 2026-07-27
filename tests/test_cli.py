from __future__ import annotations

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


def test_export_command_writes_a_file(tmp_path: Path) -> None:
    output = tmp_path / "hp.yaml"
    exit_code = main(["export", "heat_pump_electric_household", "-o", str(output)])
    assert exit_code == 0
    assert output.exists()


def test_export_all_command_writes_one_file_per_technology(tmp_path: Path) -> None:
    exit_code = main(["export-all", "-o", str(tmp_path)])
    assert exit_code == 0
    assert len(list(tmp_path.glob("*.yaml"))) > 0
