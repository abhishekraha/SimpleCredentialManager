# ToDo / Future development scope

This file lists planned improvements and features for future releases. Items are ordered and scoped as actionable work items.


1) Tamper-detection wipe on decryption failure
   - Implement a safeguard that reacts to metadata/config tampering or decryption errors.
   - Modes of operation:
     - Default: log the error, increment the incorrect-attempt counter, and warn the user.
     - Strict (configurable): if decryption fails in a way indicative of tampering, attempt a best-effort backup (timestamped) and then automatically wipe the password store and metadata to prevent further compromise.
   - Implementation notes: catch and distinguish cryptography-specific exceptions where possible, persist a tamper counter, and surface clear warnings to the user. Before any automatic wipe, attempt to create a local backup if the storage location is writable.

2) Encrypted backup command (`--backup`)
   - Implement a CLI command to create encrypted backups of the secret store.
   - Behavior: prompt for backup destination, encrypt backup using the current master password (or an optional backup passphrase), and keep a timestamped filename.
   - Restore flow: provide a corresponding restore command that validates backups before applying them.

3) Extend unit tests
   - Add unit tests covering CSV import/export and tamper-detection flows.
   - Keep expanding utility and CLI coverage as new features land.

4) Integration test
   - Add a minimal integration script that runs the CLI in an ephemeral environment and validates the end-to-end flow (initialize, add, export, import, delete).
   - Extend CI to run the integration smoke test in addition to the unit tests already configured.

5) UX & confirmation improvements
   - Add an explicit confirmation before deleting a stored secret.
   - Add a `--yes` override flag for scripted automation, but default to interactive confirmation.

Implementation & safety notes
- Any feature that produces plaintext output or can wipe user data must surface clear warnings and require confirmation.
- Provide a simple, visible backup/restore path before enabling strict automatic-wipe modes; prefer best-effort local backups to reduce accidental data loss.


6) Change Master Password
   - Update the vault master password after verifying the current password.

7) Missing-file consistency checks
   - Add handling for cases where metadata exists but the vault file does not, or vice versa.

8) Package release detection
   - Add a mechanism to identify when a newer package release is available.
   - Surface a link to the package or release page so users can upgrade from the app or docs.
