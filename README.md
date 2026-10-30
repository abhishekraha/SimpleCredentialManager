# Simple Credential Manager (SCM)

[![GitHub Pages](https://img.shields.io/badge/Live_Site-GitHub_Pages-10b981?style=for-the-badge&logo=github)](https://abhishekraha.github.io/SimpleCredentialManager/)
[![License: MIT](https://img.shields.io/badge/License-MIT-06b6d4?style=for-the-badge)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-38bdf8?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Zero Cloud](https://img.shields.io/badge/Storage-100%25_Local_Zero_Cloud-34d399?style=for-the-badge)](https://abhishekraha.github.io/SimpleCredentialManager/)

> **Live Interactive Site & Documentation:** [https://abhishekraha.github.io/SimpleCredentialManager/](https://abhishekraha.github.io/SimpleCredentialManager/)  
> **Author & Developer Contact:** [https://abhishekraha.github.io/AbhishekRaha](https://abhishekraha.github.io/AbhishekRaha)

---

Simple Credential Manager is a high-assurance, sovereign, local-first credential vault and RFC 6238 2FA authenticator designed for developers, privacy advocates, and security-minded power users. It eliminates cloud storage risks by keeping your encrypted credentials on your local machine using state-of-the-art cryptography.

```
       ┌────────────────────────────────────────────────────────┐
       │   Simple Credential Manager — Dual Interface (v3.0)   │
       └────────────────────────────────────────────────────────┘
                 │                                    │
                 ▼                                    ▼
       [ Modern PySide6 Desktop UI ]       [ Modern Rich/Typer CLI ]
       (Dark/Light, TOTP Arc, 3-Pane)      (Interactive & Headless)
                 │                                    │
                 └─────────────────┬──────────────────┘
                                   ▼
                   [ SecretManagerService Core ]
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   [ Envelope KEK / DEK ]                    [ SecureBuffer RAM ]
    Argon2id (64MB / 3-iter)                  Explicit C-style memset
              │                                         │
              ▼                                         ▼
   [ SQLite WAL Row-Level AEAD ]             [ Zero-Trace Clipboard ]
    AES-256-GCM + Blind Index                 30s auto-erase + OS flags
```

---

## The 4 Security Pillars

1. **Argon2id & Two-Tier Envelope Encryption (KEK / DEK)**:
   - Derives a 256-bit Key Encryption Key (KEK) using memory-hard Argon2id ($m=64\text{MB}, t=3$).
   - The KEK unwraps an internal Data Encryption Key (DEK). Changing master passwords rotates only the DEK envelope in under a millisecond with zero re-encryption of stored secrets.

2. **SecureBuffer Explicit Memory Zeroing**:
   - Python strings are immutable and linger in garbage-collected memory. SCM utilizes mutable `bytearray` memory buffers cleared via explicit `memset` upon session locking.
   - Sessions automatically lock after 60 seconds of inactivity.

3. **Zero-Trace OS Clipboard Protection**:
   - Applies Windows `ExcludeClipboardContentFromMonitorProcessing` / `ClipboardViewerIgnore` and macOS `org.nspasteboard.ConcealedType` to shield copied passwords from cloud syncs, clipboard histories, and spyware.
   - Cleans up secrets with a guaranteed 30-second background eraser.

4. **Row-Level SQLite WAL & HMAC Blind Indexing**:
   - Stored in `~/.simpleCredentialManager/vault.scmdb` with Write-Ahead Logging (WAL) for atomic transactions.
   - Each secret is encrypted with distinct 96-bit AES-GCM nonces.
   - HMAC-SHA256 blind indexing allows instant $O(1)$ querying without exposing credential names in plaintext.

---

## User Interfaces

### 1. Modern Desktop UI (Default)
Built with PySide6:
- **Master Password Prompt On Open**: Prompts for master password entry before revealing any vault data.
- **3-Pane Layout**: Collapsible sidebar (All, Favorites, Categories, Security Health), live searchable credential list, and comprehensive details panel.
- **Integrated TOTP Arc**: Live countdown animation and one-click TOTP token copying.
- **Password Generator & Health Audit**: Live entropy scores, duplicate detection, and optional HaveIBeenPwned k-anonymity leak audits.
- **Theme Switcher**: Button in the sidebar to toggle between Modern UI and Classic Tkinter UI with immediate or restart prompts.

### 2. Modern Rich CLI
Interactive and headless commands powered by Typer and Rich:
```bash
# List all credentials in a styled table
python SimpleCredentialManagerCli.py list

# Retrieve and copy a secret (with 30-second auto-erase)
python SimpleCredentialManagerCli.py get github-token --clip

# Generate real-time 2FA / TOTP code
python SimpleCredentialManagerCli.py totp aws-root --clip

# Audit vault password health
python SimpleCredentialManagerCli.py health --breaches

# Interactive full terminal menu
python SimpleCredentialManagerCli.py interactive
```

---

## Persistent Lockout & Fresh Wipe Option

- Failed master password attempts are tracked persistently across restarts.
- Backoff escalates exponentially ($30\text{s} \to 60\text{s} \to 120\text{s} \to \dots \to 15\text{min}$) to thwart brute-force attempts.
- **After 3 failed attempts**, users are presented with a **Reset Vault & Wipe** option. Requiring typing `"WIPE"` for confirmation, this securely deletes vault databases, metadata, and backups to allow starting fresh.

---

## Quickstart

### Prerequisites
- Python 3.10+
- `pip`

### Installation
```bash
git clone https://github.com/abhishekraha/SimpleCredentialManager.git
cd SimpleCredentialManager
pip install -r requirements.txt
```

### Launch
```bash
# Launch Modern Desktop UI (PySide6)
python SimpleCredentialManagerUi.py

# Launch Interactive CLI
python SimpleCredentialManagerCli.py
```

*Or use the dedicated platform launcher scripts located in `scripts/launchers/`:*
- **Windows**: `scripts/launchers/SimpleCredentialManagerUi.bat` or `scripts/launchers/SimpleCredentialManagerCli.bat`
- **Linux / macOS**: `scripts/launchers/SimpleCredentialManagerUi.sh` or `scripts/launchers/SimpleCredentialManagerCli.sh`

*To explicitly run the legacy interface, launch with `--classic` or `--tkinter`:*
```bash
python SimpleCredentialManagerUi.py --classic
python SimpleCredentialManagerCli.py --legacy
```

---

## Standalone Binary Packaging

To compile standalone binaries without requiring Python on the target host:
- **Windows**: `scripts/local-builder/build-windows.bat` or `scripts/local-builder/build-windows.ps1`
- **Linux / macOS**: `scripts/local-builder/build-unix.sh`

---

## Documentation

- [**Live GitHub Pages Site**](https://abhishekraha.github.io/SimpleCredentialManager/)
- [**Migration Guide (v2.0.8 to v3.0.0)**](docs/MIGRATION_V2_TO_V3.md)
- [**Architecture & Cryptography Deep Dive**](docs/ARCHITECTURE_DEEP_DIVE.md)
- [**Security & Threat Model**](docs/ARCHITECTURE_DEEP_DIVE.md#threat-model--mitigations)
- [**Change Log**](CHANGELOG.md)

---

## License & Attribution

- Distributed under the [MIT License](LICENSE).
- Created and maintained by [**Abhishek Raha**](https://abhishekraha.github.io/AbhishekRaha).
