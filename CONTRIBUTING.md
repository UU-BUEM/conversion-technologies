# Contributing

## Prerequisites

- Miniconda or Miniforge
- Python 3.12+
- git

## Dev setup

```powershell
.\setup.ps1
```

This creates/updates the `conversion_env` conda environment from
`infrastructure/env/conversion_env.yml` (installed at
`C:\Users\<you>\.conda\envs\conversion_env`) and installs the package
editable: `pip install -e . --no-deps`.

Linux/HPC:

```bash
bash setup.sh
```

**Do not run `conda develop src`** — it does not install the
`conversion-technologies` console script. Use `pip install -e . --no-deps`.

## Config files

Numeric defaults (capacity, lifetime, efficiency/COP/dispatch-factor inputs
in `new/technologies.csv`; every `cost_*` value in `new/costs.csv`, joined
by category/variant/scale) — never hardcode them in Python. See
`CLAUDE.md` → "Extension points".

**Editing the CSVs in LibreOffice Calc**: it will prompt "Use CSV format!"
on save. Click it — that warning is about losing multiple
sheets/formulas/formatting on save, none of which these files use, so
nothing is lost for a flat single-table CSV.

**Validation lives in source, not in tests.** If you're adding a new
engineering bound (a min/max on a column), it belongs in
`core/validation.py` + `TechnologySpec.__post_init__` (common bounds) or
the relevant category's `specific/__init__.py` (technology-specific
bounds) — a test should only assert that an out-of-range value raises
`ValueError`, never be the sole place the bound is defined.

## Code quality

```powershell
ruff format .
ruff check src/ tests/
mypy src
pytest
python validate.py
```

## Commit style

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`,
`fix:`, `docs:`, `chore:`, optionally scoped, e.g. `feat(heat_pump): add
water-source variant`.

## Pull requests

- One concern per PR.
- Add/update tests for any behavior change.
- Update `CHANGELOG.md` under `[Unreleased]`.
- CI (lint, type check, tests, CLI smoke test) must be green.

## Releasing

Versioning is entirely tag-driven (`setuptools_scm`) -- there is nothing to
bump in `pyproject.toml`. To cut a release:

1. Move the `[Unreleased]` entries in `CHANGELOG.md` under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading (leave `[Unreleased]` empty above it).
2. Commit that, then tag: `git tag -a vX.Y.Z -m "vX.Y.Z: <one-line summary>"`.
3. `git push origin main --follow-tags` -- the tag push triggers
   `.github/workflows/release.yml`, which builds the sdist/wheel and
   publishes a GitHub Release with them attached.
4. Confirm both the `CI` and `Release` workflow runs are green:
   `gh run list --repo UU-BUEM/conversion-technologies --limit 2`.
