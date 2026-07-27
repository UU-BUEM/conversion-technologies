"""Standalone validation suite for the conversion-technologies package.

Usage: python validate.py [--env NAME] [--full] [--skip-docker]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

EXPECTED_FILES = [
    "pyproject.toml",
    "meta.yaml",
    "CHANGELOG.md",
    "infrastructure/env/conversion_env.yml",
    "infrastructure/container/Dockerfile",
    "src/conversion_technologies/__init__.py",
    "src/conversion_technologies/__main__.py",
    "src/conversion_technologies/cli.py",
    "src/conversion_technologies/core/technology.py",
    "src/conversion_technologies/core/registry.py",
    "src/conversion_technologies/calliope_export/legacy_v051.py",
    "src/conversion_technologies/calliope_export/modern.py",
    "src/conversion_technologies/new/boiler/data/defaults.json",
    "src/conversion_technologies/new/heat_pump/data/defaults.json",
    "src/conversion_technologies/new/combined_heat_and_power/data/defaults.json",
]


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, **kwargs)  # type: ignore[arg-type]


def check_conda_env(env_name: str) -> bool:
    print(f"[1/5] Conda environment '{env_name}' + core imports...")
    result = _run(["conda", "run", "-n", env_name, "python", "-c", "import numpy, ruamel.yaml, conversion_technologies"])
    ok = result.returncode == 0
    print("  OK" if ok else f"  FAILED\n{result.stderr}")
    return ok


def check_cli(env_name: str) -> bool:
    print("[2/5] CLI (info / list)...")
    info = _run(["conda", "run", "-n", env_name, "python", "-m", "conversion_technologies", "info"])
    listing = _run(["conda", "run", "-n", env_name, "python", "-m", "conversion_technologies", "list"])
    ok = info.returncode == 0 and listing.returncode == 0
    print("  OK" if ok else f"  FAILED\n{info.stderr}\n{listing.stderr}")
    return ok


def check_pytest(env_name: str) -> bool:
    print("[3/5] pytest suite...")
    result = _run(["conda", "run", "-n", env_name, "python", "-m", "pytest", "-q", "--tb=short"])
    ok = result.returncode == 0
    print("  OK" if ok else f"  FAILED (non-fatal)\n{result.stdout}\n{result.stderr}")
    return ok


def check_docker(env_name: str, full: bool) -> bool:
    print("[4/5] Docker...")
    if not full:
        print("  SKIPPED (pass --full to build/run the container)")
        return True
    if not shutil.which("docker"):
        print("  SKIPPED (docker not on PATH)")
        return True
    build = _run(
        [
            "docker",
            "compose",
            "-f",
            "infrastructure/container/docker-compose.yml",
            "build",
        ]
    )
    if build.returncode != 0:
        print(f"  FAILED (build)\n{build.stderr}")
        return False
    run = _run(
        [
            "docker",
            "compose",
            "-f",
            "infrastructure/container/docker-compose.yml",
            "run",
            "--rm",
            "conversion-technologies",
            "python",
            "-m",
            "conversion_technologies",
            "info",
        ]
    )
    ok = run.returncode == 0
    print("  OK" if ok else f"  FAILED (run)\n{run.stderr}")
    return ok


def check_structure() -> bool:
    print("[5/5] Package structure...")
    missing = [f for f in EXPECTED_FILES if not (REPO_ROOT / f).exists()]
    if missing:
        print("  FAILED, missing:")
        for f in missing:
            print(f"    - {f}")
        return False
    print("  OK")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="conversion_env")
    parser.add_argument("--full", action="store_true", help="Also build/run the Docker container.")
    parser.add_argument("--skip-docker", action="store_true")
    args = parser.parse_args()

    results = {
        "conda env + imports": check_conda_env(args.env),
        "CLI": check_cli(args.env),
        "pytest": check_pytest(args.env),
        "Docker": True if args.skip_docker else check_docker(args.env, args.full),
        "package structure": check_structure(),
    }

    print("\nSummary:")
    all_ok = True
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {name}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
