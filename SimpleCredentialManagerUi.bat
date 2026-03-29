@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_GUI_EXE="

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_EXE=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=py"
    )
)

where pythonw >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_GUI_EXE=pythonw"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python and make sure "python" or "py" works from Command Prompt.
    pause
    exit /b 1
)

echo Using Python executable: %PYTHON_EXE%
echo.

if exist requirements.txt (
    echo Installing/Updating dependencies from requirements.txt ...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to upgrade pip.
        pause
        exit /b 1
    )

    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies from requirements.txt.
        pause
        exit /b 1
    )
) else (
    echo No requirements.txt found, skipping dependency installation.
)

if defined PYTHON_GUI_EXE (
    start "Simple Credential Manager" "%PYTHON_GUI_EXE%" "%~dp0SimpleCredentialManagerUi.py"
) else (
    start "Simple Credential Manager" "%PYTHON_EXE%" "%~dp0SimpleCredentialManagerUi.py"
)

endlocal
exit /b 0
