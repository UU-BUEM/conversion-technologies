"""Step 2: rooftop PV potential for every building, plus the Thomassen roof.

Two parts, both through the package's ``conversion-technologies pv-profile``
CLI (run as a subprocess in ``conversion_env``; this scenario never imports
the package):

1. **Buildings.** Every building's ``roof_faces`` from buem's summary
   parquets -> ``pv_rooftop_household`` profile per kWp (PVWatts v8, the
   package's roof rules) and the roof's maximum kWp. Node names follow
   ``build_nodes.py`` (``bldg_<building_feature_id>``).
2. **Thomassen distribution centre** (``measures/community_assets.csv``
   ``thomassen_rooftop_pv``). The site publishes its yield (about 800 MWh/yr)
   but not its kWp or roof layout, and the address point (PDOK, Kanaal Zuid
   496) falls on a small office, not on one identifiable hall. So the array
   is one flat roof under the package's ``pv_rooftop_building`` flat-roof
   rule, at the address, and its capacity is **calibrated** so the 2018
   profile yields the published annual energy. The layout is an
   assumption; the calibration fixes the energy, the layout only the shape.

Outputs (git-ignored ``data/step2/pv/``):

- ``roof_faces.json``, ``thomassen_faces.json``: the CLI inputs;
- ``pv_rooftop_household_source_use_max.csv`` etc.: the CLI's own outputs
  (per-kWp profiles, data tables, nodes YAML);
- ``pv_building_potential.csv``: per building, max kWp, kWh/kWp, max kWh/yr;
- ``thomassen_pv.csv``: hourly kW of the calibrated site; ``thomassen_pv.json``
  its kWp and assumptions.

Usage (scenario_env, from the scenario root)::

    python scripts/build_pv_potential.py \\
        --summary data/loenen_single_dwelling_summary_cool26_ev20.parquet \\
        --summary data/loenen_background_cool26_ev20_summary.parquet
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

# Region weather point: buem's _batch_weather mean building centroid, so PV
# and demand see the same MERRA-2 cell (docs/phase1_demand.md).
LATITUDE, LONGITUDE = 52.12, 6.03

# Thomassen: PDOK locatieserver, "Kanaal Zuid 496, 7371GL Loenen"
# (adresseerbaarobject 0200010000108350), accessed 2026-11-25.
THOMASSEN = {
    "node": "thomassen",
    "address": "Kanaal Zuid 496, 7371GL Loenen",
    "latitude": 52.1294107,
    "longitude": 6.04419252,
    "rd_x": 199986.036,
    "rd_y": 460337.505,
    "annual_yield_kwh": 800000.0,  # community_assets.csv, cooperative page
    "panels": 2404,  # community_assets.csv
    # Assumption: one flat roof, big enough not to bind (the capacity is
    # calibrated afterwards, not taken from the area).
    "assumed_flat_roof_area_m2": 10000.0,
}


def _run_cli(technology: str, faces: Path, lat: float, lon: float, out: Path) -> None:
    cmd = [
        CT_PYTHON,
        "-m",
        "conversion_technologies",
        "pv-profile",
        technology,
        "--roof-faces",
        str(faces),
        "--latitude",
        str(lat),
        "--longitude",
        str(lon),
        "--year",
        "2018",
        "--provider",
        "merra-2",
        "--data-dir",
        WEATHER_DIR,
        "-o",
        str(out),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def _nodes_kwp(nodes_yaml: Path) -> dict[str, float]:
    """``flow_cap_max`` per node from the CLI's nodes YAML (no YAML parser
    needed: the file is the package's fixed layout)."""
    kwp: dict[str, float] = {}
    node = None
    for line in nodes_yaml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if (
            line.startswith("  ")
            and not line.startswith("   ")
            and stripped.endswith(":")
        ):
            node = stripped[:-1].strip("'\"")
        elif stripped.startswith("data:") and node is not None:
            kwp[node] = float(stripped.split(":", 1)[1])
    return kwp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, default=SCENARIO_ROOT / "data/step2/pv")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    faces: dict[str, list] = {}
    for path in args.summary:
        summary = pd.read_parquet(path, columns=["building_feature_id", "roof_faces"])
        for bid, raw in zip(
            summary["building_feature_id"], summary["roof_faces"], strict=True
        ):
            faces[f"bldg_{bid}"] = json.loads(raw) if isinstance(raw, str) else []
    faces_path = args.out / "roof_faces.json"
    faces_path.write_text(json.dumps(faces), encoding="utf-8")
    _run_cli("pv_rooftop_household", faces_path, LATITUDE, LONGITUDE, args.out)

    profile = pd.read_csv(
        args.out / "pv_rooftop_household_source_use_max.csv", index_col=0
    )
    kwp = _nodes_kwp(args.out / "pv_rooftop_household_nodes.yaml")
    potential = pd.DataFrame({"node": list(faces)})
    potential["building_feature_id"] = potential["node"].str[5:].astype(int)
    potential["max_kwp"] = potential["node"].map(kwp).fillna(0.0)
    potential["kwh_per_kwp"] = potential["node"].map(profile.sum()).fillna(0.0)
    potential["max_kwh"] = potential["max_kwp"] * potential["kwh_per_kwp"]
    potential.to_csv(args.out / "pv_building_potential.csv", index=False)

    site_dir = args.out / "thomassen"
    site_faces = site_dir / "thomassen_faces.json"
    site_dir.mkdir(exist_ok=True)
    flat = {
        "id": "flat",
        "tilt": 0.0,
        "azimuth": 180.0,
        "area_m2": THOMASSEN["assumed_flat_roof_area_m2"],
    }
    site_faces.write_text(json.dumps({THOMASSEN["node"]: [flat]}), encoding="utf-8")
    _run_cli(
        "pv_rooftop_building",
        site_faces,
        THOMASSEN["latitude"],
        THOMASSEN["longitude"],
        site_dir,
    )
    per_kwp = pd.read_csv(
        site_dir / "pv_rooftop_building_source_use_max.csv", index_col=0
    )[THOMASSEN["node"]]
    kwh_per_kwp = float(per_kwp.sum())
    site_kwp = THOMASSEN["annual_yield_kwh"] / kwh_per_kwp
    (per_kwp * site_kwp).rename("pv_kW").rename_axis("time").to_csv(
        args.out / "thomassen_pv.csv"
    )
    meta = {
        **THOMASSEN,
        "technology": "pv_rooftop_building (flat-roof rule)",
        "kwh_per_kwp_2018_merra2": round(kwh_per_kwp, 1),
        "calibrated_kwp": round(site_kwp, 1),
        "wp_per_panel_implied": round(site_kwp * 1000 / THOMASSEN["panels"], 1),
    }
    (args.out / "thomassen_pv.json").write_text(json.dumps(meta, indent=2))

    usable = potential[potential["max_kwp"] > 0]
    print(
        f"{len(usable)} of {len(potential)} buildings can carry PV; "
        f"{usable['max_kwp'].sum():.0f} kWp, {usable['max_kwh'].sum() / 1e6:.2f} GWh/yr "
        f"max; median {usable['kwh_per_kwp'].median():.0f} kWh/kWp"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
