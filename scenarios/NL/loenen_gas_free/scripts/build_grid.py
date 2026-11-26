"""Step 1 of the energy-community workflow: the electricity grid.

Builds a grid package (``scripts/grid/common.py``) for every building in
the scenario, from the first source that is available:

1. ``provided`` -- a network the user supplies (``--provided-dir``);
2. ``dso`` -- the DSO's open data (Liander for Loenen);
3. ``pylovo`` -- a synthetic LV grid from a running enerplanet-pylovo API.

``--source auto`` (default) walks that order; naming a source forces it.
Output goes to ``data/grid/<source>/`` (git-ignored: the Liander transformer
list may not be redistributed). With ``--cross-check`` a pylovo or
provided grid is compared with the DSO stations (``cross_check.csv``).

Run from the scenario root, in scenario_env::

    python scripts/build_grid.py
    python scripts/build_grid.py --source pylovo --pylovo-url http://localhost:8086 --cross-check

See docs/phase7_grid.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

SCENARIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grid import cross_check, liander, provided, pylovo  # noqa: E402
from grid.common import GridPackage, load_buildings  # noqa: E402
from grid.lv_trace import TraceSettings  # noqa: E402

DEFAULT_BUILDINGS = (
    SCENARIO / "data" / "loenen_single_dwelling_summary_cool26_ev20.parquet"
)


def choose_source(args: argparse.Namespace, buildings) -> str:
    if args.source != "auto":
        return args.source
    if provided.available(args.provided_dir):
        return "provided"
    if args.dso == "liander" and liander.available(buildings, args.cache_dir):
        return "dso"
    if pylovo.available(args.pylovo_url):
        return "pylovo"
    raise SystemExit(
        "No grid source available: no --provided-dir with transformers.csv, no Liander "
        f"stations in the area, and no pylovo API at {args.pylovo_url} (start it with "
        "'make dev' in enerplanet-pylovo)."
    )


def build(
    source: str, args: argparse.Namespace, buildings, settings: TraceSettings
) -> GridPackage:
    if source == "provided":
        if not provided.available(args.provided_dir):
            raise SystemExit(f"--provided-dir {args.provided_dir}: no transformers.csv")
        return provided.build(buildings, args.provided_dir, settings)
    if source == "dso":
        return liander.build(
            buildings, args.cache_dir, settings, unrated_stations=args.unrated_stations
        )
    polygon = pylovo.area_polygon(buildings, buffer_m=200.0)
    return pylovo.convert(
        pylovo.fetch(args.pylovo_url, polygon, args.cache_dir), buildings
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--buildings",
        type=Path,
        nargs="+",
        default=[DEFAULT_BUILDINGS],
        help=(
            "buem summary Parquet(s) (or CSV) with bag_pand_id/latitude/longitude; "
            "several files are concatenated (e.g. single dwellings + background)"
        ),
    )
    p.add_argument(
        "--source", choices=["auto", "provided", "dso", "pylovo"], default="auto"
    )
    p.add_argument(
        "--provided-dir", type=Path, default=SCENARIO / "data" / "grid_provided"
    )
    p.add_argument(
        "--dso",
        choices=["liander"],
        default="liander",
        help="DSO open-data adapter (only Liander so far)",
    )
    p.add_argument(
        "--unrated-stations",
        choices=["include", "exclude"],
        default="include",
        help="DSO tier: may MV rooms without a rated transformer feed buildings?",
    )
    p.add_argument("--pylovo-url", default="http://localhost:8086")
    p.add_argument("--cache-dir", type=Path, default=SCENARIO / "data" / "grid_cache")
    p.add_argument("--out-root", type=Path, default=SCENARIO / "data" / "grid")
    p.add_argument(
        "--cross-check",
        action="store_true",
        help="compare a provided/pylovo grid's stations with the DSO's",
    )
    p.add_argument("--snap-m", type=float, default=1.0)
    p.add_argument("--station-radius-m", type=float, default=30.0)
    p.add_argument("--max-connection-m", type=float, default=75.0)
    args = p.parse_args(argv)

    buildings = pd.concat(
        [load_buildings(path) for path in args.buildings], ignore_index=True
    )
    if buildings["building_feature_id"].duplicated().any():
        raise ValueError("a building appears in more than one --buildings file")
    settings = TraceSettings(args.snap_m, args.station_radius_m, args.max_connection_m)
    source = choose_source(args, buildings)
    print(f"grid source: {source} ({len(buildings)} buildings)")
    package = build(source, args, buildings, settings)
    package.inputs["buildings"] = [str(path) for path in args.buildings]
    out_dir = args.out_root / package.source.replace(":", "_")

    if args.cross_check and source != "dso":
        reference = liander.build(
            buildings, args.cache_dir, settings, unrated_stations=args.unrated_stations
        )
        pairs, summary = cross_check.compare(
            reference.transformers, package.transformers
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        pairs.to_csv(out_dir / "cross_check.csv", index=False)
        package.extra["cross_check_vs_dso"] = summary

    package.write(out_dir)
    print(json.dumps(package.summary(), indent=2))
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
