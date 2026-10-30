"""
SystemTrayManager: System tray controller for Simple Credential Manager.
Manages QSystemTrayIcon lifecycle, slim TrayPopoverWindow flyout,
backend switching, and zero-trace application locking/exit.
"""

from typing import Optional
from PySide6.QtCore import QObject, Qt, QRect
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.ui.CommandPaletteDialog import CommandPaletteDialog
from dev.abhishekraha.secretmanager.ui.TrayPopoverWindow import TrayPopoverWindow


def _create_fallback_padlock_icon() -> QIcon:
    """Creates a high-contrast fallback padlock icon as a QPixmap."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Shackle (top loop)
    painter.setPen(Qt.GlobalColor.white)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(8, 4, 16, 16, 0, 180 * 16)

    # Body (bottom block)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0284c7"))  # Sky blue padlock body
    painter.drawRoundedRect(6, 14, 20, 15, 3, 3)

    # Keyhole
    painter.setBrush(Qt.GlobalColor.white)
    painter.drawEllipse(14, 18, 4, 4)
    painter.drawRect(15, 21, 2, 4)

    painter.end()
    return QIcon(pixmap)


class SystemTrayManager(QObject):
    """
    Manages the system tray icon, persistent background execution,
    compact TrayPopoverWindow flyout, context menu interactions, and backend switching.
    """

    def __init__(
        self,
        provider: VaultDataProvider,
        palette_dialog: CommandPaletteDialog,
        main_window: Optional[QWidget] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.provider = provider
        self.palette_dialog = palette_dialog
        self.main_window = main_window

        # Dedicated slim tray popover (320px)
        self.popover = TrayPopoverWindow(provider=self.provider)
        self.popover.open_full_window_requested.connect(self._open_main_window)
        self.popover.open_palette_requested.connect(self.palette_dialog.show_centered)
        self.popover.lock_vault_requested.connect(self.lock_vault_now)

        # Ensure application remains alive in background when windows are closed
        QApplication.setQuitOnLastWindowClosed(False)

        # Initialize Tray Icon
        self.tray_icon = QSystemTrayIcon(self)
        icon = _create_fallback_padlock_icon()
        self.tray_icon.setIcon(icon)

        # Build Context Menu
        self.context_menu = QMenu()
        self._build_menu()
        self.tray_icon.setContextMenu(self.context_menu)

        # Connect activations
        self.tray_icon.activated.connect(self.on_tray_activated)

        # Initial status update
        self._update_status_display()
        self.tray_icon.show()

    def _build_menu(self) -> None:
        """Constructs the system tray context menu."""
        # 1. Quick Tray Flyout
        self.action_quick_flyout = QAction("Quick Flyout...", self)
        self.action_quick_flyout.triggered.connect(self.show_popover)
        self.context_menu.addAction(self.action_quick_flyout)

        # 2. Quick Search / Command Palette
        self.action_quick_search = QAction("Command Palette (Ctrl+Shift+Space)", self)
        self.action_quick_search.triggered.connect(self.palette_dialog.show_centered)
        self.context_menu.addAction(self.action_quick_search)

        # 3. Open Full Management Window
        self.action_open_manager = QAction("Open Workstation Window", self)
        self.action_open_manager.triggered.connect(self._open_main_window)
        self.context_menu.addAction(self.action_open_manager)

        self.context_menu.addSeparator()

        # 4. Status Header (Informative, Disabled)
        self.action_status = QAction("Status: [Local Database]", self)
        self.action_status.setEnabled(False)
        self.context_menu.addAction(self.action_status)

        # 5. Lock Vault Now
        self.action_lock = QAction("Lock Vault Now", self)
        self.action_lock.triggered.connect(self.lock_vault_now)
        self.context_menu.addAction(self.action_lock)

        # 6. Switch Backend
        self.action_switch_backend = QAction("Switch Backend...", self)
        self.action_switch_backend.triggered.connect(self.prompt_switch_backend)
        self.context_menu.addAction(self.action_switch_backend)

        self.context_menu.addSeparator()

        # 7. Quit SCM
        self.action_quit = QAction("Quit SCM", self)
        self.action_quit.triggered.connect(self.quit_application)
        self.context_menu.addAction(self.action_quit)

    def _get_provider_description(self) -> str:
        """Returns human-readable backend description."""
        provider_name = type(self.provider).__name__
        if "Remote" in provider_name:
            client = getattr(self.provider, "client", None)
            server_url = getattr(client, "server_url", "remote") if client else "remote"
            return f"Remote Server: {server_url}"
        return "Local Database"

    def _update_status_display(self) -> None:
        """Updates tray menu status action text and tray tooltip."""
        desc = self._get_provider_description()
        self.action_status.setText(f"Status: [{desc}]")
        self.tray_icon.setToolTip(f"Simple Credential Manager\n{desc}")
        if hasattr(self, "popover"):
            self.popover.reload_data()

    def show_popover(self) -> None:
        """Displays the slim 320px popover anchored to the tray geometry."""
        tray_geo = self.tray_icon.geometry()
        self.popover.show_anchored(tray_geo)

    def _open_main_window(self) -> None:
        """Shows and activates the main management window if available."""
        if self.main_window:
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.raise_()

    def switch_backend(self, new_provider: VaultDataProvider) -> None:
        """
        Safely swaps backend provider:
        - Locks active vault to zero memory and active keys.
        - Updates provider references on tray, popover, palette, and main window.
        - Updates UI status headers and tooltips.
        """
        if self.provider:
            self.provider.lock_vault()

        self.provider = new_provider
        self.palette_dialog.set_provider(new_provider)
        self.popover.set_provider(new_provider)

        if self.main_window and hasattr(self.main_window, "set_provider"):
            self.main_window.set_provider(new_provider)

        self._update_status_display()

    def prompt_switch_backend(self) -> None:
        """
        Displays a dialog allowing the user to switch between Local and Remote backends.
        """
        options = ["Local Workstation Database", "Remote Encrypted SCM Server"]
        current_idx = 1 if "Remote" in type(self.provider).__name__ else 0

        choice, ok = QInputDialog.getItem(
            None,
            "Switch Vault Backend",
            "Select active credential store:",
            options,
            current_idx,
            False,
        )
        if not ok or not choice:
            return

        if choice == "Local Workstation Database":
            from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
            new_provider = LocalVaultProvider()
            self.switch_backend(new_provider)
        else:
            server_url, ok_url = QInputDialog.getText(
                None,
                "Remote SCM Server",
                "Enter server endpoint URL:",
                text="http://127.0.0.1:8080",
            )
            if ok_url and server_url.strip():
                from dev.abhishekraha.secretmanager.providers.RemoteVaultProvider import RemoteVaultProvider
                new_provider = RemoteVaultProvider(server_url=server_url.strip())
                self.switch_backend(new_provider)

    def lock_vault_now(self) -> None:
        """
        Locks the provider, hides command palette and popover,
        locks/hides main window, and updates tray tooltip.
        """
        if self.provider:
            self.provider.lock_vault()

        if self.palette_dialog:
            self.palette_dialog.hide()

        if hasattr(self, "popover") and self.popover:
            self.popover.hide()

        if self.main_window:
            if hasattr(self.main_window, "lock_vault"):
                self.main_window.lock_vault()
            elif hasattr(self.main_window, "_lock_vault"):
                self.main_window._lock_vault()
            else:
                self.main_window.hide()

        self._update_status_display()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """
        Handles system tray clicks:
        - Single left click (Trigger): shows the slim 320px popover flyout.
        - Double click: opens full management workstation window.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_popover()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_main_window()

    def quit_application(self) -> None:
        """
        Securely terminates application:
        - Locks active provider and clears memory.
        - Hides tray icon and popover.
        - Quits QApplication.
        """
        if self.provider:
            self.provider.lock_vault()

        if hasattr(self, "popover") and self.popover:
            self.popover.hide()

        if self.tray_icon:
            self.tray_icon.hide()

        QApplication.quit()
