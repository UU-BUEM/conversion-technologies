"""Standalone validation suite for the conversion-technologies package.

Usage: python validate.py [--env NAME] [--full] [--skip-docker]
"""

from __future__ import annotations

import argparse
import os
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
    "src/conversion_technologies/core/validation.py",
    "src/conversion_technologies/calliope_export/modern.py",
    "src/conversion_technologies/new/technologies.csv",
    "src/conversion_technologies/new/costs.csv",
    "src/conversion_technologies/core/csv_loader.py",
]


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, **kwargs)  # type: ignore[arg-type]


def _env_prefix(env_name: str) -> Path | None:
    """Directory of conda env ``env_name`` in the usual locations, if present."""
    roots = [Path.home() / ".conda" / "envs"]
    for var in ("CONDA_PREFIX", "CONDA_EXE"):
        value = os.environ.get(var)
        if value:
            # CONDA_PREFIX=<base or env>, CONDA_EXE=<base>/Scripts|bin/conda
            base = Path(value).parent.parent if var == "CONDA_EXE" else Path(value)
            roots += [base / "envs", base.parent]
    for root in roots:
        if (root / env_name / "conda-meta").is_dir():
            return root / env_name
    return None


_ENV_PATH: dict[str, str] = {}


def _python(env_name: str) -> list[str]:
    """Command prefix that runs ``python`` inside conda env ``env_name``.

    Prefers ``conda run`` (``conda`` on PATH, or ``CONDA_EXE`` -- set by
    ``conda init`` even when ``conda`` itself is not on PATH, e.g. in Git
    Bash). Otherwise runs the env's own interpreter directly, with the env's
    DLL folders prepended to PATH (an unactivated conda env on Windows
    cannot load numpy's DLLs without them).
    """
    conda = shutil.which("conda") or os.environ.get("CONDA_EXE")
    if conda:
        return [conda, "run", "-n", env_name, "python"]
    prefix = _env_prefix(env_name)
    if prefix is None:
        raise SystemExit(
            f"conda env '{env_name}' not found and `conda` is not on PATH; create it "
            "with: conda env create -f infrastructure/env/conversion_env.yml"
        )
    dirs = [prefix, prefix / "Library" / "bin", prefix / "Scripts", prefix / "bin"]
    _ENV_PATH["PATH"] = os.pathsep.join(
        [str(d) for d in dirs if d.is_dir()] + [os.environ.get("PATH", "")]
    )
    exe = prefix / ("python.exe" if os.name == "nt" else "bin/python")
    return [str(exe)]


def _run_in_env(env_name: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = _python(env_name) + args
    env = {**os.environ, **_ENV_PATH} if _ENV_PATH else None
    return _run(cmd, env=env)


def check_conda_env(env_name: str) -> bool:
    print(f"[1/5] Conda environment '{env_name}' + core imports...")
    result = _run_in_env(
        env_name, ["-c", "import numpy, ruamel.yaml, conversion_technologies"]
    )
    ok = result.returncode == 0
    print("  OK" if ok else f"  FAILED\n{result.stderr}")
    return ok


def check_cli(env_name: str) -> bool:
    print("[2/5] CLI (info / list)...")
    info = _run_in_env(env_name, ["-m", "conversion_technologies", "info"])
    listing = _run_in_env(env_name, ["-m", "conversion_technologies", "list"])
    ok = info.returncode == 0 and listing.returncode == 0
    print("  OK" if ok else f"  FAILED\n{info.stderr}\n{listing.stderr}")
    return ok


def check_pytest(env_name: str) -> bool:
    print("[3/5] pytest suite...")
    result = _run_in_env(env_name, ["-m", "pytest", "-q", "--tb=short"])
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
    parser.add_argument(
        "--full", action="store_true", help="Also build/run the Docker container."
    )
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
