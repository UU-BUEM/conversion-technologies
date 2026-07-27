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
from conversion_technologies.calliope_export.writer import write_technology_yaml
from conversion_technologies.core.registry import (
    all_technologies,
    get_technology,
    list_technology_ids,
)
from conversion_technologies.settings import SETTINGS


def _cmd_info(_args: argparse.Namespace) -> int:
    print(f"conversion_technologies {__version__}")
    print(f"Registered technologies: {len(list_technology_ids())}")
    print(f"Calliope schemas: {', '.join(SCHEMA_CHOICES)}")
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    for tech_id, tech in sorted(all_technologies().items()):
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
    output_dir = Path(args.output)
    exporter = EXPORTERS[args.schema]
    for tech_id, tech in sorted(all_technologies().items()):
        body = exporter.export(tech)
        path = write_technology_yaml(tech_id, body, output_dir / f"{tech_id}.yaml")
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
        "export-all", help="Export every registered technology."
    )
    export_all_parser.add_argument("--schema", choices=SCHEMA_CHOICES, default="modern")
    export_all_parser.add_argument(
        "-o",
        "--output",
        default=SETTINGS.output_dir,
        help="Output directory (default: %(default)s)",
    )
    export_all_parser.set_defaults(func=_cmd_export_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
