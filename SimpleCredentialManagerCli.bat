@echo off
setlocal ENABLEDELAYEDEXPANSION

REM 1) Go to the folder where this .bat file lives
cd /d "%~dp0"

REM 2) Find a working Python interpreter
set "PYTHON_EXE="

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_EXE=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=py"
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python and make sure "python" or "py" works from Command Prompt.
    pause
    exit /b 1
)

echo Using Python executable: %PYTHON_EXE%
echo.

REM 3) Install requirements if requirements.txt exists
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

REM 4) Small delay
timeout /t 5 /nobreak >nul

REM 5) Launch the password manager CLI in a NEW window and KEEP IT OPEN
REM    Trick: cmd /k ""command" args" to get quoting right
start "Simple Credential Manager" cmd /k ""%PYTHON_EXE%" "%~dp0SimpleCredentialManagerCli.py""

echo.
echo Launched Simple Credential Manager in a new window.
echo You can close this window now if you want.
pause

endlocal
exit /b 0
