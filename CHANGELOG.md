# Changelog

All notable changes to this project are documented in this file.

## v3.1.0 - 2026-10-30
### Added
- **SCM Server Mode & Web Dashboard**: Zero-dependency, modern dark-themed web dashboard and REST API (`FastAPI` + `Uvicorn`) supporting standalone hosting and Nginx subpath reverse proxy integration (e.g. `/password/`).
- **Out-of-Band Physical Device Whitelisting**: Cryptographically secure device enrollment (`/enroll?secret=...`) requiring explicit local approval on the server host machine via `scm server devices approve <fingerprint>`.
- **Subtle Unauthorized Defense**: Returns nondescript `HTTP 404 Not Found` with `{"detail": "Service unavailable"}` for unauthorized devices, preventing network probes from detecting service presence.
- **Device-Bound Transport Payload Encryption**: Automatic client-side and server-side AES-256-GCM encryption of sensitive request payloads (including master password and secret CRUD) keyed via HKDF-SHA256 derived from the approved device token.
- **Docker Containerization**: Production-ready `Dockerfile` and `docker-compose.yml` with non-root security UID 10001, healthchecks, persistent volumes for vault data/config, and an `/usr/local/bin/scm` CLI alias.
- **Server CLI Commands**: Integrated `scm server start`, `scm server devices list`, `scm server devices approve`, `scm server devices revoke`, and `scm server devices token` subcommands into the modern CLI.

### Fixed
- Fixed session key derivation during authentication in `SecretManagerService` ensuring SQLite row decryption succeeds reliably on unlocked vaults.
- Fixed web dashboard session preservation across browser refreshes by normalizing session token keys and endpoints.
- Prevented premature device re-registration when a device is already approved.
- Prevented device enrollment requests on uninitialized server vaults.

## v3.0.0 - 2026-10-30
### Added
- **Modern PySide6 Desktop GUI**: Full-featured 3-pane responsive desktop interface with dark/light themes, reactive live search, category grouping, tags, and favorites.
- **Modern Typer & Rich CLI**: Interactive, colored tabular CLI (`scm interactive`, `scm list`, `scm get`, `scm add`, `scm totp`, `scm health`, `scm bulk`).
- **HaveIBeenPwned Dark Web Breach Checking**: Privacy-preserving k-anonymity breach detection integrated directly into the password health audit, secret detail panel, and add/edit dialog with live status logs and deduplicated queries.
- **Two-Factor Authentication (TOTP 2FA)**: RFC 6238 TOTP computation with animated circular countdown arc in UI and instant code generation in CLI.
- **Two-Tier Envelope Cryptography**: Master Key (KM) derivation via Argon2id (64MB RAM, $t=3$, $p=4$, with Scrypt fallback), KEK/DEK hierarchy, AES-256-GCM envelope wrapping, and HMAC-SHA256 blind indexing for leak-free $O(1)$ secret lookups.
- **SQLite WAL Storage Engine**: High-performance embedded SQLite database (`vault.scmdb`) with Write-Ahead Logging and automatic migration from legacy file SerDe.
- **Memory Hygiene & Zero-Trace Clipboard**: `SecureBuffer` mutable `bytearray` zeroization (memset on exit/lock) and `SecureClipboardManager` with OS-level privacy exclusion flags and 30-second background auto-clear.
- **Progress Animation & Live Activity Logs**: Real-time multi-step progress logging and indeterminate progress animation for vault health audits.
- **Click-to-Copy Everywhere**: Quick click-to-copy on username, password (even while masked), and TOTP code in the modern UI.
- **Server Mode & Docker Roadmap**: Architectural blueprint for containerized web server mode with Nginx `/password/` reverse proxy integration.

### Changed
- Reorganized repository root: moved launcher scripts into `scripts/launchers/` and builder tools into `scripts/local-builder/`.
- Removed obsolete screenshots from `images/` to streamline repository footprint.
- Updated `SecretManagerService.update_secret` and `add_secret` to atomically handle renaming, categories, tags, favorites, and TOTP secrets with audit logging.
- Upgraded package version to `3.0.0` across all metadata and configuration files.

## v2.0.8 - 2026-04-19
### Changed
- Replaced the desktop upgrade prompt redirect with an in-place update flow that downloads and installs the latest tagged release into the current app directory.
- Added a GitHub source archive fallback URL for updates and improved automatic upgrade error handling in the desktop UI.

## v2.0.7 - 2026-04-06
### Added
- Added a password generator to the desktop add/edit secret dialog and the CLI secret entry flow.
- Added encrypted backup export with a dedicated backup password, plus import support for those encrypted backup files.

## v2.0.6 - 2026-03-30
### Changed
- Fixed a bug in the version check logic where cached release data was being used for the first 6 hours to save network cost

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
