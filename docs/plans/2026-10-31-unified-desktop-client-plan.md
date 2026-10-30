# Unified Multi-Surface Desktop Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight, unified multi-surface desktop client offering a floating Command Palette, System Tray controller, and full Management Window running identically over local SQLite vaults or encrypted remote SCM server daemons.

**Architecture:** Introduce an abstract `VaultDataProvider` seam that completely decouples presentation widgets from persistence. Implement `LocalVaultProvider` (wrapping `SecretManagerService`) and `RemoteVaultProvider` (AES-256-GCM transport-encrypted HTTP client with out-of-band device pairing). Build a frameless `CommandPaletteDialog` summonable via a global hotkey with cursor-screen awareness, alongside `SystemTrayManager` providing live TOTP countdowns and clean in-place backend switching with zero local credential caching.

**Tech Stack:** Python 3.9+, PySide6 (Qt 6), `httpx`, `cryptography` (AES-256-GCM, HKDF-SHA256), `pynput` (with native QShortcut / QKeySequence fallback).

**Spec:** [`docs/specs/2026-10-31-unified-desktop-client-design.md`](file:///C:/Workspace/git/SimpleCredentialManager/docs/specs/2026-10-31-unified-desktop-client-design.md)

## Global Constraints

- **Python & PySide6 Versions**: Minimum Python 3.9+, `PySide6 >= 6.5.0`, `httpx >= 0.27.0`.
- **Memory Hygiene**: Decrypted credentials must never persist in unmanaged memory. Use `SecureBuffer` where applicable, enforce 60-second inactivity auto-lock (`SESSION_IDLE_LOCK_SECONDS = 60`), and 30-second clipboard wipe (`SecureClipboardManager`).
- **Strict Zero-Trace Offline Policy**: In Remote Mode, if the server is unreachable or offline, the client must never write unencrypted credentials, partial responses, or cached secrets to local disk; it must immediately reflect "Server Unreachable".
- **Clean In-Place Backend Switch**: When switching between Local and Remote backends, the active session must be locked, memory keys zeroed, and active provider swapped without automatic data migration between stores.
- **Config & Token Permissions**: Client remote config and device tokens must be saved to `~/.config/.simpleCredentialManager/remote_client.json` with strict `0600` (user-only read/write) permissions.
- **Dependencies**: Add `pynput>=1.7.6` to `pyproject.toml` dependencies with graceful fallback if the global keyboard hook is blocked in restricted or Wayland environments.

## Review Focus

1. **Remote server drops mid-session**: On network failure or HTTP 5xx/404 during secret retrieval or update, `RemoteVaultProvider` raises a clean `ConnectionError` without crashing or corrupting memory, triggering an inline reconnect banner in the UI.
2. **Device unapproved / token revoked mid-session**: Server returns 401/403/404 due to revoked device token; client clears session token, presents enrollment/re-approval status, and zeroes in-memory credentials.
3. **Global hotkey collision or unsupported environment**: In environments where `pynput` cannot hook global hotkeys (Wayland, sandboxed containers, or key conflict), initialization catches the exception, logs a warning, and falls back to window-level `QKeySequence` plus System Tray activation without crashing the app.
4. **Rapid double-invocation of Command Palette**: Summoning the command palette while it is already visible centers it on the current cursor screen without duplicating dialog instances or leaking Qt timers.
5. **Switching backends with unsaved changes or active search**: Backend switcher forcefully clears search queries, aborts in-flight requests, purges credential buffers, and resets navigation state to prevent cross-contamination of secret names between backends.

---

### Task 1: Provider Abstraction Seam & `LocalVaultProvider`

**Files:**
- Create: `dev/abhishekraha/secretmanager/core/VaultDataProvider.py`
- Create: `dev/abhishekraha/secretmanager/providers/__init__.py`
- Create: `dev/abhishekraha/secretmanager/providers/LocalVaultProvider.py`
- Test: `tests/test_local_vault_provider.py`

**Interfaces:**
- Consumes: `dev/abhishekraha/secretmanager/core/SecretManagerService.py`, `dev/abhishekraha/secretmanager/model/Secret.py`
- Produces: `VaultDataProvider` (abstract interface), `LocalVaultProvider` conforming to `VaultDataProvider`

- [ ] **Step 1: Write the failing tests for `VaultDataProvider` and `LocalVaultProvider`**

```python
# tests/test_local_vault_provider.py
import unittest
from unittest.mock import MagicMock
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret

class TestLocalVaultProvider(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.provider = LocalVaultProvider(service=self.mock_service)

    def test_implements_interface(self):
        self.assertIsInstance(self.provider, VaultDataProvider)

    def test_delegates_lifecycle_and_auth(self):
        self.mock_service.is_initialized.return_value = True
        self.mock_service.is_unlocked.return_value = False
        self.mock_service.authenticate.return_value = (True, "Unlocked successfully")
        
        self.assertTrue(self.provider.is_initialized())
        self.assertFalse(self.provider.is_unlocked())
        ok, msg = self.provider.authenticate("MasterPass123!")
        self.assertTrue(ok)
        self.mock_service.authenticate.assert_called_once_with("MasterPass123!")

    def test_delegates_secret_crud(self):
        dummy_secret = Secret(name="github", username="user", password="pwd")
        self.mock_service.get_secret_records.return_value = [dummy_secret]
        records = self.provider.get_secret_records(filter_text="git")
        self.assertEqual(records, [dummy_secret])
        self.mock_service.get_secret_records.assert_called_once_with("git")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_local_vault_provider.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'dev.abhishekraha.secretmanager.core.VaultDataProvider'`

- [ ] **Step 3: Implement `VaultDataProvider` and `LocalVaultProvider`**

Create `VaultDataProvider` ABC matching the 16 exact methods defined in Section 5.1 of the spec.
Create `LocalVaultProvider(VaultDataProvider)` taking an optional `SecretManagerService` instance (instantiating one by default), delegating each method to the underlying service and wrapping `audit_vault` for `audit_health()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_local_vault_provider.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dev/abhishekraha/secretmanager/core/VaultDataProvider.py dev/abhishekraha/secretmanager/providers tests/test_local_vault_provider.py
git commit -m "feat: add VaultDataProvider protocol and LocalVaultProvider adapter"
```

---

### Task 2: `RemoteVaultProvider` & Device-Bound Transport Client

**Files:**
- Create: `dev/abhishekraha/secretmanager/providers/RemoteHttpClient.py`
- Create: `dev/abhishekraha/secretmanager/providers/RemoteVaultProvider.py`
- Test: `tests/test_remote_vault_provider.py`

**Interfaces:**
- Consumes: `VaultDataProvider`, `TransportCrypto` (`dev/abhishekraha/secretmanager/server/TransportCrypto.py`), `Secret`
- Produces: `RemoteHttpClient` (handles enrollment, token persistence, and encrypted HTTP dispatch), `RemoteVaultProvider` implementing `VaultDataProvider`

- [ ] **Step 1: Write failing tests for `RemoteHttpClient` and `RemoteVaultProvider`**

```python
# tests/test_remote_vault_provider.py
import unittest
from unittest.mock import patch, MagicMock
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.providers.RemoteVaultProvider import RemoteVaultProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret

class TestRemoteVaultProvider(unittest.TestCase):
    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_implements_interface(self, mock_client_cls):
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        self.assertIsInstance(provider, VaultDataProvider)

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_authenticate_and_fetch_secrets(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.post_encrypted.side_effect = [
            {"success": True, "token": "session-xyz", "message": "Unlocked"},
            {"items": [{"name": "gmail", "username": "me@example.com", "category": "login", "is_favorite": False}]}
        ]
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        ok, msg = provider.authenticate("MasterPass123!")
        self.assertTrue(ok)
        secrets = provider.get_secret_records("gm")
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0].name, "gmail")

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_server_unreachable_zero_trace(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        import httpx
        mock_client.post_encrypted.side_effect = httpx.ConnectError("Connection refused")
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        with self.assertRaises(ConnectionError):
            provider.get_secret_records()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_remote_vault_provider.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `RemoteHttpClient` and `RemoteVaultProvider`**

1. In `RemoteHttpClient`:
   - Config file: `~/.config/.simpleCredentialManager/remote_client.json` with `os.chmod(0o600)`.
   - Stores `server_url`, `device_id`, `device_token`.
   - `enroll_device(enrollment_token, device_name)`: calls `POST /api/v1/devices/enroll`.
   - `post_encrypted(endpoint, json_payload, session_token=None)`: uses `TransportCrypto.encrypt_payload(payload, device_token)` and decrypts response with `TransportCrypto.decrypt_payload(resp_data, device_token)`.
2. In `RemoteVaultProvider`:
   - Maintains ephemeral `session_token` in memory, clears to `None` on `lock_vault()`.
   - Converts remote JSON payloads into `Secret` model instances.
   - Converts HTTP failures into clean `ConnectionError` with zero local disk logging.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_remote_vault_provider.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dev/abhishekraha/secretmanager/providers/RemoteHttpClient.py dev/abhishekraha/secretmanager/providers/RemoteVaultProvider.py tests/test_remote_vault_provider.py
git commit -m "feat: implement RemoteVaultProvider and RemoteHttpClient with transport crypto"
```

---

### Task 3: Floating Command Palette Dialog (`CommandPaletteDialog`)

**Files:**
- Create: `dev/abhishekraha/secretmanager/ui/CommandPaletteDialog.py`
- Test: `tests/test_command_palette_dialog.py`

**Interfaces:**
- Consumes: `VaultDataProvider`, `SecureClipboardManager`, `TotpService`
- Produces: `CommandPaletteDialog(QDialog)`

- [ ] **Step 1: Write failing tests for `CommandPaletteDialog` logic**

```python
# tests/test_command_palette_dialog.py
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from dev.abhishekraha.secretmanager.model.Secret import Secret

app = QApplication.instance() or QApplication([])

class TestCommandPaletteDialog(unittest.TestCase):
    def setUp(self):
        from dev.abhishekraha.secretmanager.ui.CommandPaletteDialog import CommandPaletteDialog
        self.mock_provider = MagicMock()
        self.mock_provider.is_unlocked.return_value = True
        self.mock_provider.get_secret_records.return_value = [
            Secret(name="AWS Console", username="admin", password="aws_password_123", totp_secret="JBSWY3DPEHPK3PXP"),
            Secret(name="GitHub", username="octocat", password="gh_password_456")
        ]
        self.dialog = CommandPaletteDialog(provider=self.mock_provider)

    def test_search_filters_results(self):
        self.dialog.search_input.setText("git")
        self.assertEqual(self.dialog.results_list.count(), 1)
        self.assertEqual(self.dialog.results_list.item(0).text(), "GitHub (octocat)")

    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.SecureClipboardManager.copy")
    def test_enter_copies_password_and_hides(self, mock_copy):
        self.dialog.search_input.setText("aws")
        self.dialog.handle_primary_action() # Simulates Enter
        mock_copy.assert_called_once_with("aws_password_123", clear_timeout_seconds=30)
        self.assertFalse(self.dialog.isVisible())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_command_palette_dialog.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'dev.abhishekraha.secretmanager.ui.CommandPaletteDialog'`

- [ ] **Step 3: Implement `CommandPaletteDialog`**

- Frameless `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`.
- Dark slate theme (#0f172a / #1e293b / #38bdf8), 600px width, rounded corners with drop shadow.
- Real-time search `QLineEdit` connected to `textChanged`.
- `results_list` (`QListWidget`) displaying title, username, category icon, and TOTP badge indicator.
- Key bindings:
  - `Enter`: Copy password via `SecureClipboardManager.copy(..., clear_timeout_seconds=30)` and dismiss.
  - `Ctrl+C`: Copy username.
  - `Ctrl+T`: Generate and copy current TOTP code.
  - `Ctrl+O`: Emit signal `open_full_window_requested(secret_name)`.
  - `Escape` or `changeEvent(QEvent.ActivationChange)`: Auto-dismiss on loss of focus.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_command_palette_dialog.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dev/abhishekraha/secretmanager/ui/CommandPaletteDialog.py tests/test_command_palette_dialog.py
git commit -m "feat: implement frameless CommandPaletteDialog with quick keyboard copy"
```

---

### Task 4: Global Hotkey Service & Active Screen Placement

**Files:**
- Modify: `pyproject.toml:41-55` (add `pynput>=1.7.6`)
- Create: `dev/abhishekraha/secretmanager/utils/GlobalHotkeyService.py`
- Test: `tests/test_global_hotkey_service.py`

**Interfaces:**
- Consumes: `pynput.keyboard` (with graceful `ImportError` / permission catch), `PySide6.QtCore.QObject`
- Produces: `GlobalHotkeyService` emitting Qt signal `hotkey_triggered`

- [ ] **Step 1: Write failing tests for `GlobalHotkeyService`**

```python
# tests/test_global_hotkey_service.py
import unittest
from unittest.mock import patch, MagicMock
from dev.abhishekraha.secretmanager.utils.GlobalHotkeyService import GlobalHotkeyService

class TestGlobalHotkeyService(unittest.TestCase):
    def test_hotkey_service_initialization_and_fallback(self):
        # Test initialization without throwing even if pynput is missing
        with patch.dict("sys.modules", {"pynput": None, "pynput.keyboard": None}):
            service = GlobalHotkeyService()
            self.assertFalse(service.is_active())
            # Should not crash on start or stop
            service.start()
            service.stop()

    def test_screen_placement_utility(self):
        from dev.abhishekraha.secretmanager.utils.GlobalHotkeyService import get_active_screen_geometry
        # Geometry should return a valid QRect
        rect = get_active_screen_geometry()
        self.assertGreater(rect.width(), 0)
        self.assertGreater(rect.height(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_global_hotkey_service.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Update `pyproject.toml` and implement `GlobalHotkeyService`**

1. Add `"pynput>=1.7.6"` to `pyproject.toml`.
2. Implement `GlobalHotkeyService(QObject)`:
   - Defines Qt signal `hotkey_triggered = Signal()`.
   - Listens for `<ctrl>+<shift>+<space>` using `pynput.keyboard.GlobalHotKeys` running in a daemon thread.
   - On trigger, invokes `hotkey_triggered.emit()`.
   - If `pynput` is unavailable or fails with permission/platform errors, logs a warning and marks `is_active() == False`.
   - Helper `get_active_screen_geometry()`: uses `QGuiApplication.screenAt(QCursor.pos())` to find the monitor hosting the user's cursor, returning its geometry to center the palette in the top third of the active monitor.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_global_hotkey_service.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml dev/abhishekraha/secretmanager/utils/GlobalHotkeyService.py tests/test_global_hotkey_service.py
git commit -m "feat: add GlobalHotkeyService with multi-monitor cursor screen placement"
```

---

### Task 5: System Tray Manager & Live TOTP Controller (`SystemTrayManager`)

**Files:**
- Create: `dev/abhishekraha/secretmanager/ui/SystemTrayManager.py`
- Test: `tests/test_system_tray_manager.py`

**Interfaces:**
- Consumes: `VaultDataProvider`, `CommandPaletteDialog`, `TotpService`
- Produces: `SystemTrayManager` managing `QSystemTrayIcon`, tray menus, backend switching, and auto-lock

- [ ] **Step 1: Write failing tests for `SystemTrayManager`**

```python
# tests/test_system_tray_manager.py
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from dev.abhishekraha.secretmanager.ui.SystemTrayManager import SystemTrayManager

app = QApplication.instance() or QApplication([])

class TestSystemTrayManager(unittest.TestCase):
    def setUp(self):
        self.mock_provider = MagicMock()
        self.mock_palette = MagicMock()
        self.mock_main_window = MagicMock()
        self.tray = SystemTrayManager(
            provider=self.mock_provider,
            palette_dialog=self.mock_palette,
            main_window=self.mock_main_window
        )

    def test_tray_initialization(self):
        self.assertIsNotNone(self.tray.tray_icon)
        self.assertTrue(QApplication.quitOnLastWindowClosed() is False)

    def test_switch_backend_locks_and_swaps_provider(self):
        new_provider = MagicMock()
        self.tray.switch_backend(new_provider)
        self.mock_provider.lock_vault.assert_called_once()
        self.assertEqual(self.tray.provider, new_provider)

    def test_lock_action_clears_palette_and_locks(self):
        self.tray.lock_vault_now()
        self.mock_provider.lock_vault.assert_called_once()
        self.mock_palette.hide.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_system_tray_manager.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `SystemTrayManager`**

- Initializes `QSystemTrayIcon` with SCM padlock icon.
- Sets `QApplication.setQuitOnLastWindowClosed(False)`.
- Builds context menu:
  - `Quick Search (Command Palette)` -> `palette_dialog.show_centered()`
  - `Open Vault Manager` -> `main_window.show()`, `main_window.activateWindow()`
  - `Mode: [Local Database | Remote Server: <url>]` (informative header)
  - Separator
  - `Lock Vault Now` -> calls `provider.lock_vault()` and hides open windows
  - `Switch Backend...` -> opens prompt/dialog to toggle between Local and Remote
  - Separator
  - `Quit SCM` -> cleans up hotkey service and exits `QApplication.quit()`
- Connects left click on tray icon to open command palette; double click to open main window.
- Live TOTP preview: If unlocked, periodically updates tray tooltip with active countdown or favorite TOTP code.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_system_tray_manager.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dev/abhishekraha/secretmanager/ui/SystemTrayManager.py tests/test_system_tray_manager.py
git commit -m "feat: implement SystemTrayManager with backend switcher and persistent tray daemon"
```

---

### Task 6: Wire `ModernMainWindow` & Application Entry Points

**Files:**
- Modify: `dev/abhishekraha/secretmanager/ui/ModernMainWindow.py:25-95` (accept `VaultDataProvider`)
- Modify: `dev/abhishekraha/secretmanager/SimpleCredentialManagerUi.py:1-120` (add `--remote`, `--palette`, `--tray` CLI flags)
- Test: `tests/test_modern_ui_provider_wiring.py`

**Interfaces:**
- Consumes: `VaultDataProvider`, `LocalVaultProvider`, `RemoteVaultProvider`, `SystemTrayManager`, `CommandPaletteDialog`, `GlobalHotkeyService`
- Produces: Integrated desktop application entry point supporting both local and remote backends across all 3 presentation surfaces

- [ ] **Step 1: Write failing tests for `ModernMainWindow` provider parameter and CLI launchers**

```python
# tests/test_modern_ui_provider_wiring.py
import unittest
from unittest.mock import MagicMock
from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider

class TestModernMainWindowProviderWiring(unittest.TestCase):
    def test_window_accepts_vault_data_provider(self):
        mock_provider = MagicMock(spec=LocalVaultProvider)
        mock_provider.is_unlocked.return_value = False
        window = ModernMainWindow(provider=mock_provider)
        self.assertEqual(window.provider, mock_provider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_modern_ui_provider_wiring.py`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'provider'`

- [ ] **Step 3: Refactor `ModernMainWindow` and `SimpleCredentialManagerUi.py`**

1. In `ModernMainWindow.__init__`:
   - Accept optional `provider: Optional[VaultDataProvider] = None`.
   - If omitted, default to `LocalVaultProvider()`.
   - Update all service calls to use `self.provider`.
   - Update status bar to display current provider mode (`[Mode: Local DB]` or `[Mode: Remote Server: <url>]`).
2. In `SimpleCredentialManagerUi.py`:
   - Parse CLI arguments:
     - `--remote <url>`: Initializes `RemoteVaultProvider(url)`.
     - `--palette`: Shows command palette directly on launch.
     - `--tray`: Starts minimized to system tray without opening main window.
     - (Default without flags: launches full window in Local mode).
   - Instantiate `GlobalHotkeyService`, `CommandPaletteDialog`, `ModernMainWindow`, and `SystemTrayManager`.
   - Wire `palette_dialog.open_full_window_requested` -> `main_window.open_secret_detail(name)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_modern_ui_provider_wiring.py`
Expected: PASS

- [ ] **Step 5: Run full project test suite**

Run: `python -m unittest discover tests`
Expected: All tests PASS (>= 172 tests).

- [ ] **Step 6: Commit**

```bash
git add dev/abhishekraha/secretmanager/ui/ModernMainWindow.py dev/abhishekraha/secretmanager/SimpleCredentialManagerUi.py tests/test_modern_ui_provider_wiring.py
git commit -m "feat: wire ModernMainWindow to VaultDataProvider and add CLI flags for remote, palette, and tray"
```

---

### Task 7: End-to-End Verification & Documentation Update

**Files:**
- Modify: `AGENTS.md` (document `VaultDataProvider`, `LocalVaultProvider`, `RemoteVaultProvider`, presentation surfaces)
- Modify: `README.md` (document Command Palette hotkey `Ctrl+Shift+Space`, tray mode, `--remote`, `--palette`, `--tray`)
- Test: `tests/test_unified_desktop_client_e2e.py`

**Interfaces:**
- Consumes: All components from Tasks 1-6
- Produces: Complete regression test suite and updated documentation

- [ ] **Step 1: Write end-to-end integration test verifying complete client lifecycle**

```python
# tests/test_unified_desktop_client_e2e.py
import unittest
from unittest.mock import MagicMock, patch
from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
from dev.abhishekraha.secretmanager.providers.RemoteVaultProvider import RemoteVaultProvider
from dev.abhishekraha.secretmanager.ui.SystemTrayManager import SystemTrayManager
from dev.abhishekraha.secretmanager.ui.CommandPaletteDialog import CommandPaletteDialog
from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

class TestUnifiedDesktopClientE2E(unittest.TestCase):
    def test_full_lifecycle_and_backend_switching(self):
        local_provider = MagicMock(spec=LocalVaultProvider)
        remote_provider = MagicMock(spec=RemoteVaultProvider)
        
        palette = CommandPaletteDialog(provider=local_provider)
        window = ModernMainWindow(provider=local_provider)
        tray = SystemTrayManager(provider=local_provider, palette_dialog=palette, main_window=window)
        
        # Verify initial local state
        self.assertEqual(tray.provider, local_provider)
        
        # Switch to remote backend
        tray.switch_backend(remote_provider)
        local_provider.lock_vault.assert_called_once()
        self.assertEqual(tray.provider, remote_provider)
        self.assertEqual(palette.provider, remote_provider)
        self.assertEqual(window.provider, remote_provider)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m unittest tests/test_unified_desktop_client_e2e.py`
Expected: PASS

- [ ] **Step 3: Update `AGENTS.md` and `README.md`**

Update `AGENTS.md` with:
- The new `VaultDataProvider` interface and provider architecture diagram.
- Presentation surfaces documentation (Command Palette, System Tray, Management Window).
Update `README.md` with:
- Desktop client launcher options (`--remote`, `--palette`, `--tray`).
- Global shortcut guide (`Ctrl+Shift+Space` for instant floating search).

- [ ] **Step 4: Run full test suite**

Run: `python -m unittest discover tests`
Expected: 100% PASS with 0 failures or errors.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md README.md tests/test_unified_desktop_client_e2e.py
git commit -m "docs: update AGENTS.md and README.md with unified multi-surface client documentation"
```
