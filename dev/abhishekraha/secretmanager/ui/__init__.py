"""
PySide6 Modern UI Launcher and Module.
"""

import sys

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


def is_pyside6_available():
    return HAS_PYSIDE6


def run_modern_ui(provider=None, service=None, start_palette=False, start_tray=False):
    """
    Launches the PySide6 modern UI.
    Initializes GlobalHotkeyService, CommandPaletteDialog, ModernMainWindow, and SystemTrayManager.
    Supports starting directly in Command Palette mode (--palette) or minimized to System Tray (--tray).
    If PySide6 is unavailable, raises ImportError.
    """
    if not HAS_PYSIDE6:
        raise ImportError("PySide6 is not installed. Please install PySide6 or use the Tkinter UI.")

    from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
    from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
    from dev.abhishekraha.secretmanager.ui.CommandPaletteDialog import CommandPaletteDialog
    from dev.abhishekraha.secretmanager.ui.ModernAuthDialog import ModernAuthDialog
    from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
    from dev.abhishekraha.secretmanager.ui.SystemTrayManager import SystemTrayManager
    from dev.abhishekraha.secretmanager.utils.GlobalHotkeyService import GlobalHotkeyService

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if provider is not None:
        active_provider = provider
    elif service is not None:
        if isinstance(service, VaultDataProvider):
            active_provider = service
        else:
            active_provider = LocalVaultProvider(service=service)
    else:
        active_provider = LocalVaultProvider()

    # If provider is not unlocked, prompt authentication unless starting strictly into tray
    if not active_provider.is_unlocked() and not start_tray:
        auth_dialog = ModernAuthDialog(service=active_provider)
        if auth_dialog.exec() != QtWidgets.QDialog.Accepted or not auth_dialog.authenticated:
            # User closed dialog without authenticating
            return 0

    # Instantiate main window and command palette
    main_window = ModernMainWindow(provider=active_provider)
    palette_dialog = CommandPaletteDialog(provider=active_provider)

    # Wire palette Ctrl+O request to main window detail view
    palette_dialog.open_full_window_requested.connect(main_window.open_secret_detail)

    # Instantiate system tray manager
    tray_manager = SystemTrayManager(
        provider=active_provider,
        palette_dialog=palette_dialog,
        main_window=main_window,
    )

    # Instantiate global hotkey service and connect to command palette
    hotkey_service = GlobalHotkeyService()
    hotkey_service.hotkey_triggered.connect(palette_dialog.show_centered)
    hotkey_service.start()

    # Ensure hotkey service is stopped on app exit
    app.aboutToQuit.connect(hotkey_service.stop)

    # Handle launch surface states
    if start_palette:
        palette_dialog.show_centered()
    elif not start_tray:
        main_window.show()

    return app.exec()
