# Local Binary Builder Scripts

This directory contains standalone build scripts to package **Simple Credential Manager** into portable, native executables for Windows, macOS, and Linux using PyInstaller.

The resulting binaries **embed the Python interpreter and all compiled cryptographic dependencies**. End users can run them directly on their machines without installing Python, Git, or any packages.

---

## Available Scripts

| Script | Platform | Output Files |
| :--- | :--- | :--- |
| **`build-windows.bat`** | Windows Command Prompt | `dist/SimpleCredentialManager-CLI.exe` (CLI)<br>`dist/SimpleCredentialManager-UI.exe` (GUI) |
| **`build-windows.ps1`** | Windows PowerShell | `dist/SimpleCredentialManager-CLI.exe` (CLI)<br>`dist/SimpleCredentialManager-UI.exe` (GUI) |
| **`build-unix.sh`** | macOS / Linux Bash | `dist/SimpleCredentialManager-CLI` (CLI)<br>`dist/SimpleCredentialManager-UI` (GUI / macOS `.app`) |

---

## How to Build

### On Windows
Run from PowerShell:
```powershell
.\scripts\local-builder\build-windows.ps1
```
Or double-click `scripts\local-builder\build-windows.bat`.

### On macOS / Linux
Run from terminal:
```bash
chmod +x scripts/local-builder/build-unix.sh
./scripts/local-builder/build-unix.sh
```

---

## Output Location
The compiled single-file executables are placed in the root **`dist/`** directory:
* **`dist/SimpleCredentialManager-CLI.exe` / `dist/SimpleCredentialManager-CLI`**: The interactive terminal & scriptable CLI tool.
* **`dist/SimpleCredentialManager-UI.exe` / `dist/SimpleCredentialManager-UI`**: The native desktop graphical application.
