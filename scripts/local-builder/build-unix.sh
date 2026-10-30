#!/usr/bin/env bash
set -e

# Resolve repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

echo "======================================================"
echo "   Simple Credential Manager - Unix Binary Builder"
echo "======================================================"
echo ""

# Detect OS
OS_NAME="$(uname -s)"
echo "[*] Detected Operating System: $OS_NAME"

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is required to build binaries."
    exit 1
fi

echo "[*] Installing build requirements..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller

echo ""
echo "[*] Building Standalone CLI Binary (dist/scm)..."
python3 -m PyInstaller --clean --noconfirm --onefile \
    --name scm \
    --collect-all cryptography \
    --collect-all pwinput \
    --collect-all pyotp \
    --collect-all rich \
    --collect-all typer \
    --add-data "dev:dev" \
    SimpleCredentialManagerCli.py

echo ""
echo "[*] Building Standalone Desktop UI Binary (dist/SimpleCredentialManagerUi)..."
if [ "$OS_NAME" = "Darwin" ]; then
    # macOS windowed build
    python3 -m PyInstaller --clean --noconfirm --onefile --windowed \
        --name SimpleCredentialManagerUi \
        --collect-all cryptography \
        --collect-all pwinput \
        --collect-all pyotp \
        --collect-all rich \
        --collect-all typer \
        --collect-all PySide6 \
        --add-data "dev:dev" \
        SimpleCredentialManagerUi.py
else
    # Linux build
    python3 -m PyInstaller --clean --noconfirm --onefile \
        --name SimpleCredentialManagerUi \
        --collect-all cryptography \
        --collect-all pwinput \
        --collect-all pyotp \
        --collect-all rich \
        --collect-all typer \
        --collect-all PySide6 \
        --add-data "dev:dev" \
        SimpleCredentialManagerUi.py
fi

echo ""
echo "======================================================"
echo "   Build Completed Successfully!"
echo "======================================================"
echo "Binaries created:"
echo "  - CLI:  $REPO_ROOT/dist/scm"
echo "  - GUI:  $REPO_ROOT/dist/SimpleCredentialManagerUi"
echo ""
echo "These are standalone executables that run without needing"
echo "Python installed on the target machine."
echo "======================================================"
