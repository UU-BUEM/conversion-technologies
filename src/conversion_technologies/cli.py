"""Command-line interface for ``conversion-technologies``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from conversion_technologies import (  # noqa: F401  (new registers technologies)
    __version__,
    new,
)
from conversion_technologies.calliope_export import EXPORTERS, SCHEMA_CHOICES
from conversion_technologies.calliope_export.writer import (
    write_technology_yaml,
    write_techs_yaml,
)
from conversion_technologies.config import load_export_config
from conversion_technologies.core.registry import (
    all_technologies,
    get_technology,
    list_technology_ids,
)
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.settings import SETTINGS

# Short, memorable aliases alongside the full category names used internally
# (TechnologySpec.category). "hp" is what most people actually type.
_CATEGORY_ALIASES = {
    "hp": "heat_pump",
    "heat_pump": "heat_pump",
    "boiler": "boiler",
    "chp": "combined_heat_and_power",
    "combined_heat_and_power": "combined_heat_and_power",
}


def _cmd_info(_args: argparse.Namespace) -> int:
    print(f"conversion_technologies {__version__}")
    print(f"Registered technologies: {len(list_technology_ids())}")
    print(f"Calliope schemas: {', '.join(SCHEMA_CHOICES)}")
    return 0


def _filter_by_category(
    techs: list[tuple[str, TechnologySpec]], category: str | None
) -> list[tuple[str, TechnologySpec]]:
    if category is None:
        return techs
    canonical = _CATEGORY_ALIASES[category]
    return [(tid, t) for tid, t in techs if t.category == canonical]


def _cmd_list(args: argparse.Namespace) -> int:
    techs = _filter_by_category(sorted(all_technologies().items()), args.category)
    for tech_id, tech in techs:
        print(
            f"{tech_id:32s} {tech.category:24s} "
            f"{tech.scale:10s} {tech.flow_cap_max:>8.1f} kW"
        )
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    tech = get_technology(args.technology_id)
    exporter = EXPORTERS[args.schema]
    body = exporter.export(tech)
    output = (
        Path(args.output)
        if args.output
        else Path(SETTINGS.output_dir) / f"{tech.id}.yaml"
    )
    path = write_technology_yaml(tech.id, body, output)
    print(f"Wrote {path}")
    return 0


def _cmd_export_all(args: argparse.Namespace) -> int:
    schema = args.schema
    output = args.output
    technology_ids: list[str] | None = None

    if args.config:
        cfg = load_export_config(args.config)
        technology_ids = cfg.technology_ids or None
        schema = schema or cfg.schema
        output = output or cfg.output_dir

    schema = schema or "modern"
    output = output or SETTINGS.output_dir
    exporter = EXPORTERS[schema]

    techs = sorted(all_technologies().items())
    if technology_ids:
        wanted = set(technology_ids)
        techs = [(tid, t) for tid, t in techs if tid in wanted]
    else:
        techs = _filter_by_category(techs, args.category)

    if not techs:
        print("No technologies matched the given filters.")
        return 1

    output_path = Path(output)
    if output_path.suffix in (".yaml", ".yml"):
        bodies = {tid: exporter.export(t) for tid, t in techs}
        path = write_techs_yaml(bodies, output_path)
        print(f"Wrote {path} ({len(bodies)} technologies)")
        return 0

    for tid, tech in techs:
        body = exporter.export(tech)
        path = write_technology_yaml(tid, body, output_path / f"{tid}.yaml")
        print(f"Wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conversion-technologies",
        description=(
            "Generate Calliope technology YAML configs for heat-producing energy "
            "conversion technologies (heat pumps, boilers, combined heat and power)."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser(
        "info", help="Show package and environment info."
    )
    info_parser.set_defaults(func=_cmd_info)

    list_parser = subparsers.add_parser("list", help="List registered technologies.")
    list_parser.add_argument(
        "--category",
        choices=sorted(_CATEGORY_ALIASES),
        default=None,
        help="Filter by category (aliases: hp, boiler, chp).",
    )
    list_parser.set_defaults(func=_cmd_list)

    export_parser = subparsers.add_parser(
        "export", help="Export a single technology to a Calliope YAML file."
    )
    export_parser.add_argument("technology_id")
    export_parser.add_argument("--schema", choices=SCHEMA_CHOICES, default="modern")
    export_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output YAML path (default: <output_dir>/<technology_id>.yaml)",
    )
    export_parser.set_defaults(func=_cmd_export)

    export_all_parser = subparsers.add_parser(
        "export-all",
        help="Export every registered technology, optionally filtered by category.",
    )
    export_all_parser.add_argument("--schema", choices=SCHEMA_CHOICES, default=None)
    export_all_parser.add_argument(
        "--category",
        choices=sorted(_CATEGORY_ALIASES),
        default=None,
        help="Only export this category (aliases: hp, boiler, chp).",
    )
    export_all_parser.add_argument(
        "--config",
        default=None,
        help=(
            "Load an ExportConfig JSON file (technology_ids/schema/output_dir); "
            "see config/data/default_scenario.json. Its technology_ids list "
            "overrides --category if both are given."
        ),
    )
    export_all_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output directory (one file per technology) or a single "
            "<name>.yaml/.yml path (all matched technologies combined "
            "into one file). Default: <output_dir>/ or the --config value."
        ),
    )
    export_all_parser.set_defaults(func=_cmd_export_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
