@echo off
setlocal enabledelayedexpansion

echo ======================================================
echo    Simple Credential Manager - Local Binary Builder
echo ======================================================
echo.

cd /d "%~dp0\..\.."

echo [*] Checking Python installation...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo [*] Ensuring PyInstaller and dependencies are installed...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo.
echo [*] Building Standalone CLI Executable (dist/scm.exe)...
python -m PyInstaller --clean --noconfirm --onefile ^
    --name scm ^
    --console ^
    --collect-all cryptography ^
    --collect-all pwinput ^
    --collect-all pyotp ^
    --collect-all rich ^
    --collect-all typer ^
    --add-binary "C:\Python315\abi3t-compat\python3t.dll;." ^
    --add-data "dev;dev" ^
    SimpleCredentialManagerCli.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to build CLI executable.
    pause
    exit /b 1
)

echo.
echo [*] Building Standalone Desktop UI Executable (dist/SimpleCredentialManagerUi.exe)...
python -m PyInstaller --clean --noconfirm --onefile ^
    --name SimpleCredentialManagerUi ^
    --noconsole ^
    --collect-all cryptography ^
    --collect-all pwinput ^
    --collect-all pyotp ^
    --collect-all rich ^
    --collect-all typer ^
    --collect-all PySide6 ^
    --add-binary "C:\Python315\abi3t-compat\python3t.dll;." ^
    --add-data "dev;dev" ^
    SimpleCredentialManagerUi.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to build Desktop UI executable.
    pause
    exit /b 1
)

echo.
echo ======================================================
echo    Build Completed Successfully!
echo ======================================================
echo Executables created:
echo   - CLI:  %CD%\dist\scm.exe
echo   - GUI:  %CD%\dist\SimpleCredentialManagerUi.exe
echo.
echo These are standalone executables. You can move them to any
echo Windows computer without installing Python!
echo ======================================================
pause
