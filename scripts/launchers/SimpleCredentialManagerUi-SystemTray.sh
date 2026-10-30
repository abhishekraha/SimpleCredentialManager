#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if [ -f "dist/SimpleCredentialManager-UI" ]; then
    nohup ./dist/SimpleCredentialManager-UI --tray >/dev/null 2>&1 &
    exit 0
fi

if command -v python3 &>/dev/null; then
    nohup python3 SimpleCredentialManagerUi.py --tray >/dev/null 2>&1 &
else
    echo "[ERROR] Neither standalone binary nor python3 found."
    exit 1
fi
