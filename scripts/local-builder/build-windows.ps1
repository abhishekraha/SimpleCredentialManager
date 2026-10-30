<#
.SYNOPSIS
    Builds standalone Windows executables (.exe) for Simple Credential Manager without requiring external Python.
#>

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $RepoRoot

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   Simple Credential Manager - Windows Binary Builder " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Verify Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Error "Python was not found in PATH. Please install Python to build the standalone executables."
    exit 1
}

Write-Host "[*] Upgrading build tools and installing dependencies..." -ForegroundColor Yellow
& python -m pip install --upgrade pip
& python -m pip install -r requirements.txt pyinstaller

# Check for abi3t-compat/python3t.dll
$compatDll = Join-Path $env:LOCALAPPDATA "Programs\Python\Python315\abi3t-compat\python3t.dll"
if (-not (Test-Path $compatDll)) {
    $compatDll = "C:\Python315\abi3t-compat\python3t.dll"
}
$addBinaryArg = @()
if (Test-Path $compatDll) {
    $addBinaryArg = @("--add-binary", "$compatDll;.")
}

Write-Host ""
Write-Host "[*] Building Standalone CLI (dist\scm.exe)..." -ForegroundColor Yellow
& python -m PyInstaller --clean --noconfirm --onefile `
    --name scm `
    --console `
    --collect-all cryptography `
    --collect-all pwinput `
    --collect-all pyotp `
    --collect-all rich `
    --collect-all typer `
    @addBinaryArg `
    --add-data "dev;dev" `
    SimpleCredentialManagerCli.py

Write-Host ""
Write-Host "[*] Building Standalone Desktop UI (dist\SimpleCredentialManagerUi.exe)..." -ForegroundColor Yellow
& python -m PyInstaller --clean --noconfirm --onefile `
    --name SimpleCredentialManagerUi `
    --noconsole `
    --collect-all cryptography `
    --collect-all pwinput `
    --collect-all pyotp `
    --collect-all rich `
    --collect-all typer `
    --collect-all PySide6 `
    @addBinaryArg `
    --add-data "dev;dev" `
    SimpleCredentialManagerUi.py

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "   Build Completed Successfully!                      " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "Standalone Executables Generated:"
Write-Host "  - CLI:  $RepoRoot\dist\scm.exe" -ForegroundColor White
Write-Host "  - GUI:  $RepoRoot\dist\SimpleCredentialManagerUi.exe" -ForegroundColor White
Write-Host ""
Write-Host "These executables run on any 64-bit Windows machine without Python!" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Green
