# Changelog

All notable changes to this project are documented in this file.

## v2.0.5 - 2026-03-30

### Added
- Added ability to change the master password

## v2.0.4 - 2026-03-30

### Added
- Added GitHub release update awareness across the app, including startup checks, UI footer status indicators, update prompts, and a 10-second CLI warning when a newer or stale release is detected.

## v2.0.3 - 2026-03-30

### Added
- Added automatic locking after 1 minute of inactivity.

## v2.0.2 - 2026-03-30

### Changed
- Updated the desktop UI so clicking the username field copies the username to the clipboard.
- Updated the desktop UI so clicking the URL field opens the stored link in the default browser.

## v2.0.1 - 2026-03-30

### Added
- Added bulk insert support in the desktop UI and CLI with comma-separated input.

## v2.0.0

### Added
- Added the first cross-platform desktop UI release.
- Introduced a shared backend path for UI and CLI workflows.
- Added UI launchers for Windows and POSIX environments.
- Added audit logger test coverage.

### Changed
- Enhanced centralized action auditing across setup, auth, vault actions, CRUD, import/export, listing, viewing, and clipboard copy.


## v1.1.1

### Changed
- Removed legacy `v2` and `v3` vault logic.
- Restricted support to `v4` vault metadata and key derivation.

## v1.1.0

### Added
- Added stronger fail-safe protections around authentication and vault access.
- Added lockout and backoff handling after repeated failed authentication attempts.
- Added audit logging for security-sensitive authentication events.
- Added key-derivation versioning to support safer cryptographic evolution over time.

### Changed
- Refined key management, serialization, and encryption/decryption flows for file-based secret storage.
- Improved project guidance and security notes in the documentation.

## v1.0.1

### Added
- Added CSV import and export support for stored secrets.

### Fixed
- Fixed a critical issue where newly added passwords could be written to the underlying pickle file in plaintext.

## v1.0.0

### Added
- Initial release of Simple Credential Manager.
- Added first-run setup with master password protection for the local vault.
- Added the core credential store with create, read, update, delete, and listing operations.
- Added basic authentication attempt limits and foundational project documentation.
