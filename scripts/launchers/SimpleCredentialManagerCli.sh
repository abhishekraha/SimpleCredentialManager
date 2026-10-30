#!/bin/bash

# Move to project root (one directory up from scripts/launchers)
cd "$(dirname "$0")/../.."

# Find a working python executable
if command -v python3 &>/dev/null; then
    PYTHON_EXE="python3"
elif command -v python &>/dev/null; then
    PYTHON_EXE="python"
else
    echo "[ERROR] Python not found. Install Python first!"
    exit 1
fi

echo "Using Python: $PYTHON_EXE"
echo

# Create virtual environment if it doesn't exist
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment in .venv ..."
    "$PYTHON_EXE" -m venv .venv
    if [[ $? -ne 0 ]]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment
# shellcheck disable=SC1091
source .venv/bin/activate

# Install dependencies if requirements.txt exists (inside venv)
if [[ -f "requirements.txt" ]]; then
    echo "Installing dependencies into virtual environment..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "No requirements.txt found, skipping dependency installation."
fi

sleep 5
clear

python SimpleCredentialManagerCli.py
