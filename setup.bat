@echo off
setlocal enabledelayedexpansion

set "ENV_NAME=%~1"
if "%ENV_NAME%"=="" set "ENV_NAME=conversion_env"

where conda >nul 2>nul
if errorlevel 1 (
    echo conda was not found on PATH. Install Miniconda/Miniforge first.
    exit /b 1
)

set "REPO_ROOT=%~dp0"
set "ENV_FILE=%REPO_ROOT%infrastructure\env\conversion_env.yml"

echo Using conda env spec: %ENV_FILE%

conda env list | findstr /C:"%ENV_NAME%" >nul
if errorlevel 1 (
    echo Creating environment '%ENV_NAME%'...
    call conda env create -n %ENV_NAME% -f "%ENV_FILE%"
) else (
    echo Updating existing environment '%ENV_NAME%'...
    call conda env update -n %ENV_NAME% -f "%ENV_FILE%" --prune
)
if errorlevel 1 (
    echo conda env create/update failed.
    exit /b 1
)

if not exist "%REPO_ROOT%outputs" mkdir "%REPO_ROOT%outputs"

echo Setting CONVERSION_TECH_OUTPUT_DIR conda env var...
call conda env config vars set -n %ENV_NAME% CONVERSION_TECH_OUTPUT_DIR=%REPO_ROOT%outputs
if errorlevel 1 (
    echo conda env config vars set failed.
    exit /b 1
)

echo Installing package editable (pip install -e . --no-deps)...
call conda run -n %ENV_NAME% pip install -e "%REPO_ROOT%" --no-deps
if errorlevel 1 (
    echo pip install -e . failed.
    exit /b 1
)

echo Verifying installation...
call conda run -n %ENV_NAME% python -m conversion_technologies info
if errorlevel 1 (
    echo Verification failed: 'python -m conversion_technologies info' did not succeed.
    exit /b 1
)

echo.
echo Setup complete. Activate with:  conda activate %ENV_NAME%
