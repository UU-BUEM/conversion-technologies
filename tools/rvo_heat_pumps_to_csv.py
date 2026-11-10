"""Convert RVO's monthly ISDE heat pump list (Excel) into a tidy CSV + summary.

RVO publishes the "Meldcodelijst Warmtepompen" every month at
https://www.rvo.nl/subsidies-financiering/isde/meldcodelijsten/warmtepompen
(Excel download). It lists every heat pump eligible for the Dutch ISDE
subsidy: meldcode, manufacturer, model, heat output (kW), subsidy amount,
refrigerant and its GWP, and category. It contains no purchase prices.

This is a maintenance tool, not package code -- it needs ``openpyxl``,
which is deliberately not a dependency of ``conversion_technologies``.

Usage::

    python tools/rvo_heat_pumps_to_csv.py "Meldcodelijst Warmtepompen - November 2026.xlsx" 2026-11

writes ``docs/sources/rvo_isde_heat_pumps_<release>.csv`` and
``docs/sources/rvo_isde_heat_pumps_<release>_summary.csv``.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
from pathlib import Path

import openpyxl

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "sources"

CATEGORY_EN = {
    "Lucht-Water": "air_to_water",
    "Grond-Water": "ground_to_water",
    "Water-Water": "water_to_water",
    "Warmtepompboiler": "heat_pump_water_heater",
}
FIELDS = [
    "meldcode",
    "manufacturer",
    "model",
    "heat_output_kw",
    "subsidy_eur",
    "subsidy_second_heat_pump_eur",
    "refrigerant",
    "refrigerant_gwp",
    "category_nl",
    "category",
]


def _eur(cell: object) -> float | None:
    """'  €4.425' (Dutch thousands separator) -> 4425.0."""
    if cell is None or str(cell).strip() == "":
        return None
    digits = re.sub(r"[^0-9,]", "", str(cell)).replace(",", ".")
    return float(digits) if digits else None


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (numpy's default), without numpy."""
    xs = sorted(values)
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def convert(xlsx: Path, release: str) -> tuple[Path, Path]:
    sheet = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)["Meldcodes"]
    rows = []
    for r in sheet.iter_rows(min_row=2, values_only=True):
        if not r or not r[0]:
            continue
        rows.append(
            {
                "meldcode": r[0],
                "manufacturer": r[1],
                "model": r[2],
                "heat_output_kw": r[3],
                "subsidy_eur": _eur(r[4]),
                "subsidy_second_heat_pump_eur": _eur(r[5]),
                "refrigerant": r[6],
                "refrigerant_gwp": r[7],
                "category_nl": r[8],
                "category": CATEGORY_EN.get(str(r[8]), str(r[8])),
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_path = OUT_DIR / f"rvo_isde_heat_pumps_{release}.csv"
    with data_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summary_path = OUT_DIR / f"rvo_isde_heat_pumps_{release}_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(
            [
                "category",
                "n_models",
                "kw_p10",
                "kw_p50",
                "kw_p90",
                "kw_p95",
                "kw_max",
                "subsidy_eur_median",
                "subsidy_eur_min",
                "subsidy_eur_max",
            ]
        )
        for cat in sorted({row["category"] for row in rows}):
            sub = [row for row in rows if row["category"] == cat]
            kw = [float(row["heat_output_kw"]) for row in sub if row["heat_output_kw"]]
            eur = [row["subsidy_eur"] for row in sub if row["subsidy_eur"]]
            writer.writerow(
                [cat, len(sub)]
                + (
                    [round(_percentile(kw, p), 1) for p in (10, 50, 90, 95)] + [max(kw)]
                    if kw
                    else ["", "", "", "", ""]
                )
                + (
                    [statistics.median(eur), min(eur), max(eur)]
                    if eur
                    else ["", "", ""]
                )
            )
    return data_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "xlsx", type=Path, help="RVO 'Meldcodelijst Warmtepompen' Excel file"
    )
    parser.add_argument(
        "release", help="release tag for the output names, e.g. 2026-11"
    )
    args = parser.parse_args()
    for path in convert(args.xlsx, args.release):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
