# Architecture & Design: Unified Multi-Surface Desktop Client (Local & Remote SCM)

**Document Version:** 1.0  
**Target Release:** v3.2.0  
**Status:** In Review  
**Date:** 2026-10-31  

---

## 1. Executive Summary & Intent

Simple Credential Manager (SCM) provides two operational paradigms: **Local Workstation Vault** (row-level SQLite WAL database on local disk) and **Remote Server Mode** (self-hosted REST API daemon with physical out-of-band device whitelisting and AES-256-GCM transport payload encryption).

Currently, desktop users interact with local vaults through the full `PySide6` or `Tkinter` application, while remote server access requires a web browser tab. 

This design unifies both paradigms under a single, cohesive desktop experience offering **three interchangeable presentation modes**:
1. **Floating Command Palette**: A lightweight, borderless search window summoned via a global system hotkey (`Ctrl+Shift+Space` / `Cmd+Shift+Space`), designed for sub-second fuzzy search, Enter-to-copy password with 30s auto-erase, and automatic blur-dismissal.
2. **System Tray Daemon**: A persistent icon in the Windows notification tray / macOS menu bar displaying connection status, live TOTP countdown arcs, quick-access favorites, and one-click vault locking.
3. **Full Management Window**: The comprehensive 3-pane desktop workspace for full secret CRUD, password health auditing, categories, tags, and theme switching.

The presentation layer is decoupled from storage via a unified **`VaultDataProvider`** interface. The exact same UI runs identically whether pointing to a local database (`LocalVaultProvider`) or an encrypted remote server (`RemoteVaultProvider`).

---

## 2. Goals, Non-Goals, and Anti-Goals

### 2.1 Goals
- **Unified Experience**: The same three presentation modes (Palette, Tray, Full Window) are available regardless of whether the backend is Local or Remote.
- **Provider Abstraction Seam**: Establish `VaultDataProvider` protocol so UI widgets never call SQLite or HTTP network sockets directly.
- **Sub-Second Credential Access**: Global hotkey invokes the Command Palette in <100ms with instant keyboard navigation (arrows to select, `Enter` to copy password, `Ctrl+T` to copy TOTP).
- **Physical Device Enrollment in Remote Mode**: First-time remote connection guides the user through device registration, presents the device fingerprint for host approval, and securely persists the device token.
- **Air-Gapped Parity & Strict Zero-Trace**: In Local Mode, zero network calls are made. In Remote Mode, all request bodies are encrypted via client-side AES-256-GCM keyed via HKDF from the approved device token. If the remote server is unreachable, the client displays an immediate "Server Unreachable" state with zero plaintext or cached credentials lingering on local disk.
- **Clean In-Place Backend Switch**: Clear separation between Local and Remote backends. Switching immediately locks the active vault, zeroes session keys, and switches the active data provider with zero automatic data migration between local and remote stores (users may manually export and re-import credentials if desired).
- **Seamless Presentation Switching**: Users can toggle between Command Palette, Tray Popover, and Full Window seamlessly via keyboard shortcuts or tray menu actions.

### 2.2 Non-Goals
- Multi-server synchronization or cloud mesh peering (SCM remains strictly 1:1 client-to-server or standalone local).
- Automatic data synchronization or silent migration between Local and Remote vaults.
- Automatic server discovery via mDNS / Zeroconf (explicit host/port or URL configuration preserves security and subtle 404 scanning defense).
- Web browser extension development (remains out of scope for this native desktop effort).

### 2.3 Anti-Goals
- No heavy Electron or bundled Chromium runtimes. The client builds directly upon Python and native `PySide6` (Qt 6) components.
- No plaintext credentials stored on disk or cached insecurely in unmanaged Python strings; all RAM hygiene invariants (`SecureBuffer`, 60-second inactivity lock) remain enforced.

---

## 3. Considered Approaches & Tradeoffs

### Approach A: PySide6 Multi-Window System (Selected)
- **Architecture**:
  - `QSystemTrayIcon` acts as the persistent application lifecycle owner (`QApplication.setQuitOnLastWindowClosed(False)`).
  - `CommandPaletteDialog`: A frameless, borderless `QDialog` styled with translucent backdrop blur, shadow effects, and global hotkey hooks via `QKeySequence` / OS hotkey listeners.
  - `ModernMainWindow`: The existing 3-pane desktop workspace refactored to consume `VaultDataProvider`.
  - `LocalVaultProvider`: Wraps `SecretManagerService`.
  - `RemoteVaultProvider`: Wraps `httpx` HTTP client with HKDF-derived AES-256-GCM transport crypto.
- **Pros**: 100% reuse of custom Qt widgets (animated TOTP countdown arc widget, dark/light theme engine, password health meters), zero secondary language runtime, identical cross-platform behavior on Windows, macOS, and Linux.
- **Cons**: Binary footprint includes PySide6 / Qt6 shared libraries (~40-60MB).
- **Decision**: **Selected**. Matches existing codebase conventions, delivers immediate reuse of all polished UI widgets, and guarantees consistent styling across all 3 presentation modes.

### Approach B: Native Webview Wrapper (`pywebview` + Web Dashboard)
- **Architecture**: Wrap the existing `dev/abhishekraha/secretmanager/server/static/` web application inside an OS native webview window (Edge WebView2 / WebKit) and drive tray/hotkeys through Python `pystray`.
- **Pros**: Tiny binary footprint (~10MB), reuses browser WebCrypto client code directly.
- **Cons**: Clunky floating palette transitions, poor OS-level global keyboard grab support, fragmented multi-window state management across WebView2 instances on Windows.
- **Decision**: Rejected. Does not satisfy the requirement for high-performance sub-second desktop command palette responsiveness.

### Approach C: Standalone Go / Rust Binary
- **Architecture**: Rewrite the client in Go/Fyne or Rust/Tauri.
- **Pros**: Minimal memory footprint (<15MB RAM).
- **Cons**: Introduces a second codebase and language toolchain, duplicating cryptography, TOTP algorithms, and UI components.
- **Decision**: Rejected for maintainability.

---

## 4. Architectural Design

```mermaid
flowchart TD
    subgraph Presentation_Layer ["Presentation Layer (PySide6)"]
        Tray["System Tray Controller\n(SystemTrayManager.py)"]
        Palette["Floating Command Palette\n(CommandPaletteDialog.py)"]
        Window["Full Management Window\n(ModernMainWindow.py)"]
        AuthDlg["Master Auth & Unlock Dialog\n(ModernAuthDialog.py)"]
    end

    subgraph Abstraction_Seam ["Provider Abstraction Seam"]
        Provider["<<interface>> VaultDataProvider\n(core/VaultDataProvider.py)"]
    end

    subgraph Data_Providers ["Concrete Providers"]
        LocalProv["LocalVaultProvider\n(providers/LocalVaultProvider.py)"]
        RemoteProv["RemoteVaultProvider\n(providers/RemoteVaultProvider.py)"]
    end

    subgraph Core_Services ["Core Engines"]
        Svc["SecretManagerService\n(core/SecretManagerService.py)"]
        HttpCli["TransportEncryptedClient\n(providers/RemoteHttpClient.py)"]
    end

    subgraph Storage_Network ["Storage & Network"]
        SQLite[("vault.scmdb\n(Local Disk)")]
        ServerDaemon["SCM FastAPI Server\n(Remote Port 8080)"]
    end

    Tray --> Provider
    Palette --> Provider
    Window --> Provider
    AuthDlg --> Provider

    Provider <|.. LocalProv
    Provider <|.. RemoteProv

    LocalProv --> Svc
    Svc --> SQLite

    RemoteProv --> HttpCli
    HttpCli -->|AES-256-GCM over HTTP(S)| ServerDaemon
```

---

## 5. Detailed Component Specifications

### 5.1 `VaultDataProvider` Interface
Located at `dev/abhishekraha/secretmanager/core/VaultDataProvider.py`:

```python
class VaultDataProvider(ABC):
    @abstractmethod
    def initialize(self) -> bool: ...

    @abstractmethod
    def is_initialized(self) -> bool: ...

    @abstractmethod
    def is_unlocked(self) -> bool: ...

    @abstractmethod
    def setup_master_password(self, master_password: str, confirmation_password: str) -> None: ...

    @abstractmethod
    def authenticate(self, master_password: str) -> tuple[bool, str]: ...

    @abstractmethod
    def lock_vault(self) -> None: ...

    @abstractmethod
    def get_lockout_status(self) -> dict: ...

    @abstractmethod
    def change_master_password(self, current_password: str, new_password: str, confirmation_password: str) -> None: ...

    @abstractmethod
    def get_secret_records(self, filter_text: str = "") -> list[Secret]: ...

    @abstractmethod
    def get_secret_names(self, filter_text: str = "") -> list[str]: ...

    @abstractmethod
    def get_secret(self, name: str) -> Optional[Secret]: ...

    @abstractmethod
    def add_secret(
        self,
        name: str,
        username: str,
        password: str,
        url: str = "",
        comments: str = "",
        category: str = "login",
        is_favorite: bool = False,
        totp_secret: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> None: ...

    @abstractmethod
    def update_secret(
        self,
        original_name: str,
        new_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        url: str = "",
        comments: str = "",
        category: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        totp_secret: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> None: ...

    @abstractmethod
    def delete_secret(self, name: str) -> None: ...

    @abstractmethod
    def generate_password(self, length: int = 20) -> str: ...

    @abstractmethod
    def audit_health(self) -> dict: ...
```

### 5.2 `LocalVaultProvider`
- Implements `VaultDataProvider` directly against `SecretManagerService`.
- Preserves all local disk optimizations: SQLite WAL mode, Argon2id KDF, and HMAC-SHA256 blind indexing.

### 5.3 `RemoteVaultProvider`
- Implements `VaultDataProvider` by dispatching authenticated, encrypted HTTP requests to the SCM Server (`/api/v1/*`).
- Strict Zero-Trace & Network Policy: Does not cache decrypted or snapshot data locally; network dropouts immediately show "Server Unreachable" error states.
- Client Device Enrollment & Configuration:
  - Stores `server_url`, `device_id`, and `device_token` under `~/.config/.simpleCredentialManager/remote_client.json` with strict user-only file mode `0600`.
  - Performs out-of-band enrollment if unregistered (`POST /api/v1/devices/enroll?secret=...`).
  - Encrypts master password and secret payloads using client-side `TransportCrypto` (AES-256-GCM with HKDF key derivation).

### 5.4 Cross-Platform Platform Integration & Global Hotkeys
- **Global Hotkey Daemon (`GlobalHotkeyService`)**:
  - Uses `pynput.keyboard` to capture `Ctrl+Shift+Space` (or macOS `Cmd+Shift+Space`) globally when the application is minimized or unfocused.
  - Emits a thread-safe Qt Signal to summon `CommandPaletteDialog` directly to the active screen where the user's cursor is currently located (`QGuiApplication.screenAt(QCursor.pos())`).
  - Graceful Fallback: If global shortcut registration fails (such as on Wayland or restricted environments), the UI provides a system tray activation with a warning tooltip.
- **System Tray Daemon (`SystemTrayManager`)**:
  - Manages application lifecycle via `QSystemTrayIcon` with `setQuitOnLastWindowClosed(False)`.
  - Clean In-Place Backend Switcher: Allows switching between Local Vault and Remote Server. Switching forcefully locks the active session, purges RAM keys, and connects to the alternate provider without cross-polluting or auto-migrating database records.

### 5.4 Presentation Surfaces

#### 1. Floating Command Palette (`CommandPaletteDialog`)
- **Appearance**: Frameless 600px wide dialog, dark slate styling, drop shadow, no window border. Centered in top third of screen.
- **Global Hotkey**: Registered system-wide (e.g. `Ctrl+Shift+Space` on Windows/Linux, `Cmd+Shift+Space` on macOS).
- **Behavior**:
  - Typing immediately filters secrets via real-time fuzzy matching.
  - Keyboard navigation: `Up`/`Down` arrows to navigate list.
  - `Enter`: Copies password to clipboard with 30-second auto-erase and dismisses palette.
  - `Ctrl+C` / `Cmd+C`: Copies username.
  - `Ctrl+T` / `Cmd+T`: Copies 2FA TOTP code.
  - `Escape` or focus loss: Instantly hides palette.
  - `Ctrl+O`: Opens the Full Management Window for the selected secret.

#### 2. System Tray Controller (`SystemTrayManager`)
- **Tray Menu Actions**:
  - `Open Command Palette` (`Ctrl+Shift+Space`)
  - `Open Vault Window`
  - `Connection Status`: Shows "Local Vault" or "Connected: https://remote.host"
  - `Lock Vault Now` (Clears memory and locks session)
  - `Preferences & Backend Switcher` (Toggle Local vs Remote)
  - `Quit SCM`
- **Tray Click**: Left-click opens Command Palette; double-click opens Full Window.

#### 3. Full Management Window (`ModernMainWindow`)
- Retrofitted to accept any `VaultDataProvider`.
- Adds a status bar indicator showing active connection type: `[Mode: Local DB]` or `[Mode: Remote Server (dev-xxx)]`.

---

## 6. Implementation Stages & Verification Plan

1. **Stage 1: Core Provider Seam**
   - Define `VaultDataProvider` interface and adapt `SecretManagerService` into `LocalVaultProvider`.
   - Implement `RemoteVaultProvider` with device enrollment, transport encryption, and HTTP client integration.
   - Comprehensive unit tests covering both providers.

2. **Stage 2: Command Palette & Global Shortcut Engine**
   - Create `CommandPaletteDialog` in `PySide6`.
   - Implement global hotkey registration with graceful platform fallbacks.

3. **Stage 3: System Tray Integration**
   - Build `SystemTrayManager` linking Tray icon, Command Palette, and `ModernMainWindow`.
   - Connect 60-second inactivity auto-lock and zeroization hooks.

4. **Stage 4: CLI & Configuration Integration**
   - Provide command launcher arguments:
     - `scm-gui` (Default: Local mode)
     - `scm-gui --remote https://server:8080` (Remote server mode)
     - `scm-gui --palette` (Launch directly into command palette)
     - `scm-gui --tray` (Launch minimized to system tray)
