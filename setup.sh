#!/usr/bin/env bash
# Linux/macOS/HPC setup for conversion-technologies.
set -euo pipefail

ENV_NAME="${1:-conversion_env}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REPO_ROOT}/infrastructure/env/conversion_env.yml"

if [ -f "${REPO_ROOT}/.env" ]; then
    # shellcheck disable=SC1090
    source "${REPO_ROOT}/.env"
fi

if ! command -v conda >/dev/null 2>&1; then
    if [ -n "${CONDA_MODULE:-}" ]; then
        echo "conda not on PATH; loading module ${CONDA_MODULE}"
        module load "${CONDA_MODULE}"
    else
        echo "conda was not found on PATH and no CONDA_MODULE is set. Install Miniconda/Miniforge or set CONDA_MODULE in .env." >&2
        exit 1
    fi
fi

# Resolve where the environment should live: explicit override, then the
# location the user asked for, then conda's own default envs_dirs.
if [ -n "${CONDA_ENV_PREFIX:-}" ]; then
    ENV_PREFIX="${CONDA_ENV_PREFIX}/${ENV_NAME}"
elif [ -d "${HOME}/.conda/envs" ]; then
    ENV_PREFIX="${HOME}/.conda/envs/${ENV_NAME}"
else
    ENV_PREFIX="$(conda info --base)/envs/${ENV_NAME}"
fi

echo "Using conda env spec: ${ENV_FILE}"
echo "Target environment prefix: ${ENV_PREFIX}"

if [ -d "${ENV_PREFIX}" ]; then
    echo "Updating existing environment at ${ENV_PREFIX}..."
    conda env update -p "${ENV_PREFIX}" -f "${ENV_FILE}" --prune
else
    echo "Creating environment at ${ENV_PREFIX}..."
    conda env create -p "${ENV_PREFIX}" -f "${ENV_FILE}"
fi

mkdir -p "${REPO_ROOT}/outputs"
conda env config vars set -p "${ENV_PREFIX}" CONVERSION_TECH_OUTPUT_DIR="${REPO_ROOT}/outputs"

echo "Installing package editable (pip install -e . --no-deps)..."
conda run -p "${ENV_PREFIX}" pip install -e "${REPO_ROOT}" --no-deps

echo "Verifying installation..."
conda run -p "${ENV_PREFIX}" python -m conversion_technologies info

echo
echo "Setup complete. This shell cannot activate a conda env in a subshell --"
echo "run:  conda activate ${ENV_PREFIX}"
