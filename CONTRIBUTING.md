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

Numeric defaults (capacity, cost, efficiency per deployment scale) live in
each category's `data/defaults.json` under `src/conversion_technologies/new/`
— never hardcode them in Python. See `CLAUDE.md` → "Extension points".

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
