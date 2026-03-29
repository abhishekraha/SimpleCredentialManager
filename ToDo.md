# ToDo / Future development scope

This file lists planned improvements and features for future releases. Items are ordered and scoped as actionable work items.


3) Tamper-detection wipe on decryption failure
   - Implement a safeguard that reacts to metadata/config tampering or decryption errors.
   - Modes of operation:
     - Default: log the error, increment the incorrect-attempt counter, and warn the user.
     - Strict (configurable): if decryption fails in a way indicative of tampering, attempt a best-effort backup (timestamped) and then automatically wipe the password store and metadata to prevent further compromise.
   - Implementation notes: catch and distinguish cryptography-specific exceptions where possible, persist a tamper counter, and surface clear warnings to the user. Before any automatic wipe, attempt to create a local backup if the storage location is writable.

4) GUI
   - Provide a simple cross-platform GUI (desktop) as an alternative to the interactive CLI. Acceptable lightweight options: Tkinter (standard lib) or a minimal Electron/React wrapper if desired later.
   - Features: support master-password entry, the CLI menu operations (add/view/update/delete/list), import/export, backup, and settings for strict tamper mode.
   - Security: the GUI must require the master password at startup, mask password input, and clearly warn on export/import operations that produce plaintext output.
   - Packaging & distribution: package the GUI into standalone installers or executables for common platforms (Windows exe/installer, macOS app or dmg, Linux AppImage/.deb), e.g., using PyInstaller/briefcase or an Electron packager for web-based GUIs. Provide simple release artifacts so end users can install/run the GUI without a Python environment.

5) Encrypted backup command (`--backup`)
   - Implement a CLI command to create encrypted backups of the secret store.
   - Behavior: prompt for backup destination, encrypt backup using the current master password (or an optional backup passphrase), and keep a timestamped filename.
   - Restore flow: provide a corresponding restore command that validates backups before applying them.

6) Unit tests
   - Add unit tests covering CSV import/export, tamper-detection flows, authentication attempt counters, and utilities (SerDe, codec, input helpers).

7) Integration test / CI
   - Add a minimal integration script that runs the CLI in an ephemeral environment and validates the end-to-end flow (initialize, add, export, import, delete).
   - Wire basic CI (e.g., GitHub Actions) to run unit tests and the integration smoke test on push/PR.

8) UX & confirmation improvements
   - Ensure every destructive or plaintext-producing action (export, import overwrite, wipe) requires an explicit confirmation from the user.
   - Add a `--yes` override flag for scripted automation, but default to interactive confirmation.

Implementation & safety notes
- Any feature that produces plaintext output or can wipe user data must surface clear warnings and require confirmation.
- Provide a simple, visible backup/restore path before enabling strict automatic-wipe modes; prefer best-effort local backups to reduce accidental data loss.


Change Master Password: update the vault master password (requires current password).
Add check if one of the files exists but not the other 