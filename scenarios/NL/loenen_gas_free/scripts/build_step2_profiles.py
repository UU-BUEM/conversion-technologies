"""Step 2: demand and supply per building, per station, per scenario.

Joins the buem Phase 1 runs (demand), the PV potential
(``build_pv_potential.py``) and the grid map (``build_grid.py``, all
buildings) into the tables step 3 (power flow, headroom) and step 5
(community filter) read. Nothing is optimised here.

Building roles:

- ``single_dwelling``: the 1,260 buildings the per-building Calliope models
  cover. Their demand comes from the scenario's own Phase 1 run.
- ``background``: buildings that load the grid but have no Calliope model
  (yet): the residential buildings outside that list (multi-unit and a
  few large ones) and the 63 service buildings. Their baseline demand is
  added to every scenario unchanged (no retrofit, EV share as the
  baseline), so scenarios differ only where they say they do.

Scenarios (``SCENARIOS``) name a Phase 1 run for the single dwellings. Every
scenario gets the same PV potential and the same Thomassen profile: those
are supply *options*, not dispatch. The present-day electric load is
``elec_kW + ev_kW`` (appliances and uncontrolled home charging); heat, hot
water and cooling are reported as thermal demand. Turning them into
electricity needs a technology choice (heat pump COP), which is step 3's
"electrified" variant.

Outputs (git-ignored ``data/step2/``):

- ``building_annual.csv``: one row per building and scenario;
- ``<scenario>/station_hourly.parquet``: per station and hour, the summed
  demand components and the PV potential (kW if every usable roof carried
  its maximum);
- ``station_summary.csv``: per station and scenario, annual energy, the
  coincident peak of the present-day electric load next to Liander's rated
  kVA and measured peak, and PV potential;
- ``region_summary.csv``: one row per scenario;
- ``manifest.json``: every input path, so step 3 can find the full
  hourly data.

Usage (scenario_env, from the scenario root)::

    python scripts/build_step2_profiles.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCENARIO_ROOT = Path(__file__).resolve().parent.parent
DATA = SCENARIO_ROOT / "data"

SCENARIOS: dict[str, dict[str, str]] = {
    "baseline": {
        "run": "loenen_single_dwelling_{part}_cool26_ev20.parquet",
        "description": "as Phase 1: buem envelope (label-based variant), EV 20%",
    },
    "retrofit_standard": {
        "run": "loenen_single_dwelling_retrofit_v2_cool26_ev20_{part}.parquet",
        "description": "every dwelling at least TABULA variant 2 (standard)",
    },
    "retrofit_advanced": {
        "run": "loenen_single_dwelling_retrofit_v3_cool26_ev20_{part}.parquet",
        "description": "every dwelling at TABULA variant 3 (advanced / nZEB)",
    },
    "ev50": {
        "run": "loenen_single_dwelling_cool26_ev50_{part}.parquet",
        "description": "baseline envelope, EV ownership probability 0.5",
    },
}
BACKGROUND = "loenen_background_cool26_ev20_{part}.parquet"

HOURLY_COLUMNS = {
    "elec_kW": "elec_kW",
    "ev_kW": "ev_kW",
    "Q_heat_kW": "heat_kW",
    "dhw_kW": "dhw_kW",
    "Q_cool_kW": "cool_kW",
    "cooking_gas_kW": "cooking_kW",
}
ANNUAL_COLUMNS = list(HOURLY_COLUMNS.values())


def _read_hourly(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(
        path, columns=["building_feature_id", "time", *HOURLY_COLUMNS]
    ).rename(columns=HOURLY_COLUMNS)
    # buem signs cooling negative (heat removed); report it as a positive
    # thermal demand like heat.
    df["cool_kW"] = -df["cool_kW"]
    if (df["cool_kW"] < -1e-6).any():
        raise ValueError(f"{path}: cooling with the wrong sign")
    return df


def _read_summary(path: Path, role: str) -> pd.DataFrame:
    keep = [
        "building_feature_id",
        "bag_pand_id",
        "building_type",
        "construction_period",
        "refurbishment_variant",
        "residential_units",
        "A_ref",
        "has_ev",
        "status",
    ]
    df = pd.read_parquet(path, columns=keep)
    df["role"] = role
    return df


def _pv_station_hourly(
    pv_dir: Path, grid_map: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-station PV potential (kW) per hour, and the per-building table."""
    potential = pd.read_csv(pv_dir / "pv_building_potential.csv")
    profile = pd.read_csv(
        pv_dir / "pv_rooftop_household_source_use_max.csv", index_col=0
    )
    profile.index = pd.to_datetime(profile.index)
    usable = potential[potential["max_kwp"] > 0].merge(
        grid_map[["building_feature_id", "trafo_id"]], on="building_feature_id"
    )
    station = {}
    for trafo, group in usable.groupby("trafo_id"):
        kw = profile[group["node"]].to_numpy() @ group["max_kwp"].to_numpy()
        station[trafo] = kw
    pv = pd.DataFrame(station, index=profile.index).rename_axis("time")
    return pv, potential


def _station_hourly(
    hourly: pd.DataFrame, grid_map: pd.DataFrame, pv: pd.DataFrame
) -> pd.DataFrame:
    trafo = hourly["building_feature_id"].map(
        grid_map.set_index("building_feature_id")["trafo_id"]
    )
    if trafo.isna().any():
        missing = hourly.loc[trafo.isna(), "building_feature_id"].unique()
        raise ValueError(
            f"{len(missing)} buildings have no station, e.g. {missing[:5]}"
        )
    grouped = (
        hourly.assign(trafo_id=trafo.to_numpy())
        .groupby(["trafo_id", "time"], sort=True)[ANNUAL_COLUMNS]
        .sum()
    )
    pv_long = pv.stack().rename("pv_potential_kW")
    pv_long.index = pv_long.index.set_names(["time", "trafo_id"])
    pv_long = pv_long.reorder_levels(["trafo_id", "time"])
    out = grouped.join(pv_long, how="left").fillna({"pv_potential_kW": 0.0})
    out["electric_kW"] = out["elec_kW"] + out["ev_kW"]
    return out.astype("float32")


def _station_summary(
    station: pd.DataFrame,
    counts: pd.DataFrame,
    transformers: pd.DataFrame,
    pv_kwp: pd.Series,
) -> pd.DataFrame:
    grouped = station.groupby(level="trafo_id")
    annual = grouped[[*ANNUAL_COLUMNS, "pv_potential_kW"]].sum() / 1000.0
    annual.columns = [c.replace("_kW", "_MWh") for c in annual.columns]
    summary = annual.join(grouped["electric_kW"].max().rename("electric_peak_kW")).join(
        grouped["heat_kW"].max().rename("heat_peak_kW")
    )
    peak_time = grouped["electric_kW"].idxmax().map(lambda key: key[1])
    summary["electric_peak_time"] = peak_time
    summary = summary.join(counts).join(pv_kwp.rename("pv_potential_kWp"))
    summary = summary.join(
        transformers.set_index("trafo_id")[["rated_kva", "peak_kw", "data"]].rename(
            columns={"peak_kw": "liander_peak_kW", "data": "liander_data"}
        )
    )
    summary["electric_peak_over_liander_peak"] = (
        summary["electric_peak_kW"] / summary["liander_peak_kW"]
    )
    summary["pv_kWp_over_rated_kVA"] = (
        summary["pv_potential_kWp"] / summary["rated_kva"]
    )
    return summary.reset_index()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--grid-dir", type=Path, default=DATA / "step2/grid/dso_liander"
    )
    parser.add_argument("--pv-dir", type=Path, default=DATA / "step2/pv")
    parser.add_argument("--out", type=Path, default=DATA / "step2")
    parser.add_argument(
        "--scenarios", nargs="+", default=list(SCENARIOS), choices=list(SCENARIOS)
    )
    args = parser.parse_args(argv)

    grid_map = pd.read_csv(args.grid_dir / "building_grid_map.csv")
    transformers = pd.read_csv(args.grid_dir / "transformers.csv")
    pv, potential = _pv_station_hourly(args.pv_dir, grid_map)
    pv_kwp = (
        potential.merge(grid_map[["building_feature_id", "trafo_id"]])
        .groupby("trafo_id")["max_kwp"]
        .sum()
    )

    thomassen = json.loads((args.pv_dir / "thomassen_pv.json").read_text())
    rated = transformers.dropna(subset=["latitude"])
    dist = np.hypot(
        (rated["latitude"] - thomassen["latitude"]) * 111_320,
        (rated["longitude"] - thomassen["longitude"])
        * 111_320
        * np.cos(np.radians(thomassen["latitude"])),
    )
    nearest = rated.iloc[int(np.argmin(dist.to_numpy()))]
    thomassen_station = {
        "nearest_station": nearest["trafo_id"],
        "distance_m": round(float(dist.min()), 1),
        "station_rated_kva": nearest["rated_kva"],
    }

    background_hourly = _read_hourly(DATA / BACKGROUND.format(part="hourly"))
    background_summary = _read_summary(
        DATA / BACKGROUND.format(part="summary"), "background"
    )

    building_rows, station_rows, region_rows = [], [], []
    manifest: dict = {
        "grid_dir": str(args.grid_dir),
        "pv_dir": str(args.pv_dir),
        "background": {
            "hourly": str(DATA / BACKGROUND.format(part="hourly")),
            "summary": str(DATA / BACKGROUND.format(part="summary")),
        },
        "thomassen": {**thomassen, **thomassen_station},
        "scenarios": {},
    }
    for name in args.scenarios:
        spec = SCENARIOS[name]
        hourly_path = DATA / spec["run"].format(part="hourly")
        summary_path = DATA / spec["run"].format(part="summary")
        print(f"[{name}] {hourly_path.name}")
        hourly = pd.concat(
            [_read_hourly(hourly_path), background_hourly], ignore_index=True
        )
        summary = pd.concat(
            [_read_summary(summary_path, "single_dwelling"), background_summary],
            ignore_index=True,
        )
        if (summary["status"] != "ok").any():
            raise ValueError(f"{name}: buem reported failed buildings")

        annual = hourly.groupby("building_feature_id")[ANNUAL_COLUMNS].sum() / 1000.0
        annual.columns = [c.replace("_kW", "_MWh") for c in annual.columns]
        peaks = hourly.groupby("building_feature_id")[["elec_kW", "ev_kW"]].max()
        peaks.columns = ["elec_peak_kW", "ev_peak_kW"]
        building = (
            summary.drop(columns="status")
            .merge(annual.reset_index(), on="building_feature_id")
            .merge(peaks.reset_index(), on="building_feature_id")
            .merge(
                grid_map[["building_feature_id", "trafo_id", "feeder_id", "method"]],
                on="building_feature_id",
                how="left",
            )
            .merge(
                potential[["building_feature_id", "max_kwp", "kwh_per_kwp", "max_kwh"]],
                on="building_feature_id",
                how="left",
            )
            .rename(
                columns={
                    "max_kwp": "pv_max_kWp",
                    "kwh_per_kwp": "pv_kWh_per_kWp",
                    "max_kwh": "pv_max_MWh",
                    "method": "grid_method",
                }
            )
        )
        building["pv_max_MWh"] = building["pv_max_MWh"] / 1000.0
        building.insert(0, "scenario", name)
        building_rows.append(building)

        station = _station_hourly(hourly, grid_map, pv)
        out_dir = args.out / name
        out_dir.mkdir(parents=True, exist_ok=True)
        station.reset_index().to_parquet(out_dir / "station_hourly.parquet")

        counts = building.groupby(["trafo_id", "role"]).size().unstack(fill_value=0)
        counts.columns = [f"n_{c}" for c in counts.columns]
        st = _station_summary(station, counts, transformers, pv_kwp)
        st.insert(0, "scenario", name)
        station_rows.append(st)

        region = station.groupby(level="time").sum()
        region_rows.append(
            {
                "scenario": name,
                "description": spec["description"],
                "n_buildings": len(building),
                **{
                    f"{c.replace('_kW', '_GWh')}": round(region[c].sum() / 1e6, 3)
                    for c in [*ANNUAL_COLUMNS, "electric_kW"]
                },
                "electric_peak_MW": round(region["electric_kW"].max() / 1000, 3),
                "heat_peak_MW": round(region["heat_kW"].max() / 1000, 3),
                "cool_peak_MW": round(region["cool_kW"].max() / 1000, 3),
                "pv_potential_GWh": round(region["pv_potential_kW"].sum() / 1e6, 3),
                "thomassen_pv_GWh": thomassen["annual_yield_kwh"] / 1e6,
            }
        )
        manifest["scenarios"][name] = {
            **spec,
            "hourly": str(hourly_path),
            "summary": str(summary_path),
            "station_hourly": str(out_dir / "station_hourly.parquet"),
        }

    pd.concat(building_rows).to_csv(args.out / "building_annual.csv", index=False)
    pd.concat(station_rows).to_csv(args.out / "station_summary.csv", index=False)
    region = pd.DataFrame(region_rows)
    region.to_csv(args.out / "region_summary.csv", index=False)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(region.T.to_string())
    print(json.dumps(manifest["thomassen"], indent=2))


if __name__ == "__main__":
    main()
