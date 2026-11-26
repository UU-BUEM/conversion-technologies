"""Step 2: write an envelope-retrofit copy of buem's Loenen region data.

buem assigns each residential building one TABULA archetype row through
``lod2_building_feature.csv``'s ``tabula_variant_code_id``. The NL TABULA
table has three refurbishment variants per archetype (the last segment of
``Code_BuildingVariant``):

- ``001``: as built,
- ``002``: standard ("usual") refurbishment,
- ``003``: advanced (nZEB-level) refurbishment.

buem already picks 2 or 3 for buildings whose energy label shows they were
refurbished (``refurbishment_variant``). A retrofit scenario lifts every
residential building to *at least* the target variant and never lowers
one. Everything else in the region directory is copied unchanged, so the
retrofit run differs from the baseline only in the envelope.

The output is a buem ``CsvBuildingSource`` directory. Pass it to
``run_demand_with_cooling_setpoint.py --region-dir``. It lives under the
git-ignored ``data/`` folder; buem's own repository is never edited.

Usage (any environment with pandas; from the scenario root)::

    python scripts/build_retrofit_region.py --target-variant 2 \\
        --out data/buem_regions/retrofit_v2
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

DEFAULT_REGION = Path("D:/test/buem/src/buem/data/buildings/netherlands/Loenen")
BUILDINGS = "lod2_building_feature.csv"
TABULA = "tabula.csv"
VARIANT_NAMES = {2: "standard", 3: "advanced"}


def retrofit(
    buildings: pd.DataFrame, tabula: pd.DataFrame, target: int
) -> tuple[pd.DataFrame, dict]:
    """Return (buildings with lifted variants, statistics)."""
    if target not in VARIANT_NAMES:
        raise ValueError(f"target variant must be 2 or 3, got {target}")
    id_by_code = dict(zip(tabula["Code_BuildingVariant"], tabula["id"], strict=True))
    out = buildings.copy()
    residential = (
        out["is_residential"].astype(bool) & out["tabula_variant_code"].notna()
    )
    before = out.loc[residential, "tabula_variant_code"].astype(str)
    current = before.str.rsplit(".", n=1).str[1].astype(int)
    stem = before.str.rsplit(".", n=1).str[0]
    lifted = current.clip(lower=target)
    # TABULA NL defines no standard (002) package for the newest era (06,
    # 2015+): those buildings already meet it. Keep their current variant
    # rather than jumping them to 003.
    no_package = ~(stem + "." + lifted.map("{:03d}".format)).isin(id_by_code)
    lifted = lifted.where(~no_package, current)
    new_codes = stem + "." + lifted.map("{:03d}".format)
    missing = sorted(set(new_codes) - set(id_by_code))
    if missing:
        raise ValueError(
            f"TABULA has no row for {len(missing)} codes, e.g. {missing[:3]}"
        )
    out.loc[residential, "tabula_variant_code"] = new_codes
    out.loc[residential, "tabula_variant_code_id"] = new_codes.map(id_by_code)
    out.loc[residential, "refurbishment_variant"] = lifted
    stats = {
        "target_variant": target,
        "target_name": VARIANT_NAMES[target],
        "residential_buildings": int(residential.sum()),
        "changed": int((lifted != current).sum()),
        "kept_no_tabula_package": int(no_package.sum()),
        "variant_counts_before": {
            str(k): int(v) for k, v in current.value_counts().sort_index().items()
        },
        "variant_counts_after": {
            str(k): int(v) for k, v in lifted.value_counts().sort_index().items()
        },
    }
    return out, stats


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--region", type=Path, default=DEFAULT_REGION)
    parser.add_argument("--target-variant", type=int, required=True, choices=(2, 3))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    buildings = pd.read_csv(args.region / BUILDINGS, dtype={"bag_pand_id": str})
    tabula = pd.read_csv(args.region / TABULA)
    lifted, stats = retrofit(buildings, tabula, args.target_variant)

    args.out.mkdir(parents=True, exist_ok=True)
    for path in args.region.iterdir():
        if path.is_file() and path.name != BUILDINGS:
            shutil.copy2(path, args.out / path.name)
    lifted.to_csv(args.out / BUILDINGS, index=False)
    stats["source_region"] = str(args.region)
    (args.out / "retrofit_manifest.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
