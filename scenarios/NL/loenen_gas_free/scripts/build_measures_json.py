"""Validate the Loenen measures catalogue and write it as one JSON file.

The four CSVs under ``measures/`` are the source of truth (see
``measures/README.md``); this script never edits them. It checks:

* every enum column holds an allowed value;
* every measure, subsidy scheme and community asset has a ``source_url``;
* every numeric column parses (blank = unknown);
* every ``subsidy_scheme_ids`` entry and every ``community_asset:`` /
  ``subsidy_scheme:`` model hook points at an existing row;
* ids are unique within each table.

It then writes ``measures/loenen_measures.json``: the tables as lists, plus
each measure with its subsidy schemes and community asset nested in.

Stdlib only (``csv``/``json``), so it runs in any environment::

    python scripts/build_measures_json.py            # from the scenario root
    python scripts/build_measures_json.py --check    # validate, write nothing
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

MEASURES_DIR = Path(__file__).resolve().parents[1] / "measures"

CATEGORIES = {
    "insulation",
    "heating",
    "hot_water",
    "pv",
    "storage",
    "ev_mobility",
    "collective_generation",
    "heat_network",
    "grid_flexibility",
    "behaviour_saving",
    "financing_subsidy",
    "advice_service",
    "other",
}
LEVELS = {"household", "building", "community"}
MEASURE_STATUS = {"offered", "operating", "planned", "idea", "past"}
MODEL_STATUS = {"exists", "needs_tech", "out_of_scope"}
SCHEME_STATUS = {"offered", "awarded", "intended", "closed", "past"}
ASSET_STATUS = {"operating", "planned", "idea", "past"}
# Hooks with a target after the colon; bare hooks have none.
HOOK_PREFIXES = {
    "conversion_tech",
    "generation_tech",
    "storage",
    "community_asset",
    "subsidy_scheme",
}
BARE_HOOKS = {"buem_envelope", "tariff", "not_modelled"}

NUMERIC = {
    "measures.csv": ["cost_value"],
    "subsidy_schemes.csv": ["rate_pct", "cap_eur", "amount_eur"],
    "community_assets.csv": [
        "capacity_kw",
        "energy_kwh",
        "annual_yield_kwh",
        "investment_eur",
    ],
}


def read_table(name: str) -> list[dict[str, str | float | None]]:
    """Read one CSV; blank cells become ``None``, numeric columns floats."""
    path = MEASURES_DIR / name
    with path.open(encoding="utf-8", newline="") as fh:
        rows: list[dict[str, str | float | None]] = []
        for raw in csv.DictReader(fh):
            row: dict[str, str | float | None] = {
                k: (v.strip() or None) for k, v in raw.items()
            }
            for col in NUMERIC.get(name, []):
                value = row[col]
                if value is not None:
                    try:
                        row[col] = float(str(value))
                    except ValueError as exc:
                        raise ValueError(
                            f"{name} {row.get('id')}: {col}={value!r} is not a number"
                        ) from exc
            rows.append(row)
    return rows


def check_enum(
    errors: list[str], table: str, row: dict, col: str, allowed: set[str]
) -> None:
    if row[col] not in allowed:
        errors.append(
            f"{table} {row['id']}: {col}={row[col]!r} not in {sorted(allowed)}"
        )


def check_ids(errors: list[str], table: str, rows: list[dict]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for row in rows:
        if not row.get("id"):
            errors.append(f"{table}: row without id")
        elif row["id"] in by_id:
            errors.append(f"{table}: duplicate id {row['id']!r}")
        else:
            by_id[str(row["id"])] = row
    return by_id


def validate(
    measures: list[dict], schemes: list[dict], assets: list[dict], context: list[dict]
) -> list[str]:
    errors: list[str] = []
    scheme_ids = check_ids(errors, "subsidy_schemes.csv", schemes)
    asset_ids = check_ids(errors, "community_assets.csv", assets)
    check_ids(errors, "measures.csv", measures)

    for table, rows in (
        ("measures.csv", measures),
        ("subsidy_schemes.csv", schemes),
        ("community_assets.csv", assets),
    ):
        for row in rows:
            if not row.get("source_url"):
                errors.append(f"{table} {row['id']}: missing source_url")

    for row in measures:
        check_enum(errors, "measures.csv", row, "category", CATEGORIES)
        check_enum(errors, "measures.csv", row, "level", LEVELS)
        check_enum(errors, "measures.csv", row, "status", MEASURE_STATUS)
        check_enum(errors, "measures.csv", row, "model_status", MODEL_STATUS)
        for sid in (row["subsidy_scheme_ids"] or "").split(";"):
            if sid and sid not in scheme_ids:
                errors.append(
                    f"measures.csv {row['id']}: unknown subsidy scheme {sid!r}"
                )
        hook = row["model_hook"] or ""
        prefix, _, target = hook.partition(":")
        if hook in BARE_HOOKS:
            pass
        elif prefix in HOOK_PREFIXES and target:
            if prefix == "community_asset" and target not in asset_ids:
                errors.append(
                    f"measures.csv {row['id']}: unknown community asset {target!r}"
                )
            if prefix == "subsidy_scheme" and target not in scheme_ids:
                errors.append(
                    f"measures.csv {row['id']}: unknown subsidy scheme {target!r}"
                )
        else:
            errors.append(f"measures.csv {row['id']}: bad model_hook {hook!r}")

    for row in schemes:
        check_enum(errors, "subsidy_schemes.csv", row, "status", SCHEME_STATUS)
    for row in assets:
        check_enum(errors, "community_assets.csv", row, "status", ASSET_STATUS)
    for row in context:
        if not row.get("key"):
            errors.append("context.csv: row without key")
        elif not (row.get("value") or row.get("notes")):
            errors.append(f"context.csv {row['key']}: needs a value or a note")
    return errors


def build(
    measures: list[dict], schemes: list[dict], assets: list[dict], context: list[dict]
) -> dict:
    scheme_by_id = {s["id"]: s for s in schemes}
    asset_by_id = {a["id"]: a for a in assets}
    nested = []
    for m in measures:
        item = dict(m)
        ids = [s for s in (m["subsidy_scheme_ids"] or "").split(";") if s]
        item["subsidy_scheme_ids"] = ids
        item["subsidy_schemes"] = [scheme_by_id[s] for s in ids]
        prefix, _, target = (m["model_hook"] or "").partition(":")
        item["community_asset"] = (
            asset_by_id.get(target) if prefix == "community_asset" else None
        )
        nested.append(item)
    return {
        "description": (
            "Loenen sustainable-measures catalogue, generated from measures/*.csv by "
            "scripts/build_measures_json.py. Values are as quoted by the sources "
            "(consumer prices, often incl. VAT); see measures/README.md."
        ),
        "measures": nested,
        "subsidy_schemes": schemes,
        "community_assets": assets,
        "context": {
            c["key"]: {k: v for k, v in c.items() if k != "key"} for c in context
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate only")
    parser.add_argument(
        "--out",
        type=Path,
        default=MEASURES_DIR / "loenen_measures.json",
        help="JSON output path",
    )
    args = parser.parse_args(argv)

    try:
        measures = read_table("measures.csv")
        schemes = read_table("subsidy_schemes.csv")
        assets = read_table("community_assets.csv")
        context = read_table("context.csv")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = validate(measures, schemes, assets, context)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(
        f"OK: {len(measures)} measures, {len(schemes)} subsidy schemes, "
        f"{len(assets)} community assets, {len(context)} context entries"
    )
    if not args.check:
        payload = build(measures, schemes, assets, context)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
