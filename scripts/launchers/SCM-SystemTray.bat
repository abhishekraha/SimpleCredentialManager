@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Move to project root (one directory up from scripts/launchers)
cd /d "%~dp0..\.."

set "DIST_EXE=dist\SimpleCredentialManager-UI.exe"
if exist "%DIST_EXE%" (
    start "" "%DIST_EXE%" --tray
    exit /b 0
)

set "PYTHON_EXE="
set "PYTHON_GUI_EXE="

where pythonw >nul 2>&1
if %errorlevel%==0 set "PYTHON_GUI_EXE=pythonw"

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_EXE=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    echo [ERROR] Neither standalone executable nor Python was found.
    pause
    exit /b 1
)

if defined PYTHON_GUI_EXE (
    start "" "%PYTHON_GUI_EXE%" "SimpleCredentialManagerUi.py" --tray
) else (
    start "" "%PYTHON_EXE%" "SimpleCredentialManagerUi.py" --tray
)

endlocal
exit /b 0
