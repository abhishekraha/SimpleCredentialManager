#!/bin/bash

cd "$(dirname "$0")"

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

if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment in .venv ..."
    "$PYTHON_EXE" -m venv .venv
    if [[ $? -ne 0 ]]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ -f "requirements.txt" ]]; then
    echo "Installing dependencies into virtual environment..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "No requirements.txt found, skipping dependency installation."
fi

python SimpleCredentialManagerUi.py
