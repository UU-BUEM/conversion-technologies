"""Hourly air-source heat pump COP for Loenen, 2018, from the outdoor
temperature of the same weather cell as demand and PV.

Runs the package's ``conversion-technologies weather-cop`` CLI as a
subprocess in ``conversion_env`` (this scenario never imports the package),
for every air-source heat pump the nodes can build
(``heat_pump_electric_household``, ``heat_pump_electric_building``). The
CLI takes the 2 m air temperature from the UU-BUEM ``weather`` module
(``get_point_weather``, MERRA-2) and applies each technology's own Carnot
quality factor and 45 degC design sink temperature (``technologies.csv``),
so the COP falls in cold hours and rises in mild ones.

It writes two series per technology into ``heat_pump_cop_2018/``
(tracked, small, like ``grid_price_nl_2018.csv``), one value per hour for
every node:

- ``<tech>_flow_out_eff.csv``: COP, heat out per kWh of electricity;
- ``<tech>_carrier_flow_ratio_in.csv``: COP - 1, the free ambient heat
  drawn per kWh of electricity (the ratio math reads this, not the ambient
  carrier's ``flow_in_eff``).

``build_nodes.py --cop hourly`` (the default) wires them in. Ground-source
heat pumps keep their design-point COP: the weather module has no ground
temperature, and the ground is close to its design 10 degC all year.

Usage (any env with Python, scenario root)::

    python scripts/build_hp_cop.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pandas as pd

SCENARIO_ROOT = Path(__file__).resolve().parent.parent
CT_PYTHON = "C:/Users/sahoo002/.conda/envs/conversion_env/python.exe"
WEATHER_DIR = "D:/test/weather/data/merra2/output"
OUT_DIR = SCENARIO_ROOT / "heat_pump_cop_2018"

# Same weather point as buem's demand run and build_pv_potential.py.
LATITUDE, LONGITUDE, YEAR = 52.12, 6.03, 2018
TECHS = ("heat_pump_electric_household", "heat_pump_electric_building")


def run(out_dir: Path = OUT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "year": YEAR,
        "provider": "merra-2",
        "weather_module": "UU-BUEM/weather get_point_weather (column T)",
        "techs": {},
    }
    for tech in TECHS:
        cmd = [
            CT_PYTHON,
            "-m",
            "conversion_technologies",
            "weather-cop",
            tech,
            "--latitude",
            str(LATITUDE),
            "--longitude",
            str(LONGITUDE),
            "--year",
            str(YEAR),
            "--provider",
            "merra-2",
            "--data-dir",
            WEATHER_DIR,
            "-o",
            str(out_dir),
        ]
        print(" ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)
        cop = pd.read_csv(out_dir / f"{tech}_flow_out_eff.csv", index_col=0)[
            "flow_out_eff"
        ]
        summary["techs"][tech] = {
            "hours": int(len(cop)),
            "cop_min": round(float(cop.min()), 3),
            "cop_mean": round(float(cop.mean()), 3),
            "cop_max": round(float(cop.max()), 3),
            "first_timestep": str(cop.index[0]),
        }
        # The CLI's own data_tables YAML has no node mapping; build_nodes.py
        # writes the scenario's entries, so drop it to avoid two sources.
        (out_dir / f"{tech}_data_tables.yaml").unlink(missing_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.out), indent=2))


if __name__ == "__main__":
    main()
