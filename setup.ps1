param(
    [string]$EnvName = "conversion_env",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-CondaExe {
    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if (-not $conda) {
        throw "conda was not found on PATH. Install Miniconda/Miniforge first."
    }
    return $conda.Source
}

$condaExe = Get-CondaExe
$repoRoot = $PSScriptRoot
$envFile = Join-Path $repoRoot "infrastructure\env\conversion_env.yml"

Write-Host "Using conda env spec: $envFile"

$envExists = (& conda env list) -match [regex]::Escape($EnvName)

if ($envExists -and $Force) {
    Write-Host "Removing existing environment '$EnvName' (-Force)..."
    & conda env remove -n $EnvName -y
    $envExists = $false
}

if ($envExists) {
    Write-Host "Updating existing environment '$EnvName'..."
    & conda env update -n $EnvName -f $envFile --prune
} else {
    Write-Host "Creating environment '$EnvName'..."
    & conda env create -n $EnvName -f $envFile
}
if ($LASTEXITCODE -ne 0) { throw "conda env create/update failed." }

$outputsDir = Join-Path $repoRoot "outputs"
New-Item -ItemType Directory -Force -Path $outputsDir | Out-Null

Write-Host "Setting CONVERSION_TECH_OUTPUT_DIR conda env var..."
& conda env config vars set -n $EnvName CONVERSION_TECH_OUTPUT_DIR=$outputsDir
if ($LASTEXITCODE -ne 0) { throw "conda env config vars set failed." }

Write-Host "Installing package editable (pip install -e . --no-deps)..."
& conda run -n $EnvName pip install -e $repoRoot --no-deps
if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed." }

Write-Host "Verifying installation..."
& conda run -n $EnvName python -m conversion_technologies info
if ($LASTEXITCODE -ne 0) { throw "Verification failed: 'python -m conversion_technologies info' did not succeed." }

Write-Host ""
Write-Host "Setup complete. Activate with:  conda activate $EnvName"
