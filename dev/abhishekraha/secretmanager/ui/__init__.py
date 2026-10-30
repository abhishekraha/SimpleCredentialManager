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


def run_modern_ui(service=None):
    """
    Launches the PySide6 modern UI.
    Prompts for master password authentication or initial setup before showing the main window.
    If PySide6 is unavailable, raises ImportError.
    """
    if not HAS_PYSIDE6:
        raise ImportError("PySide6 is not installed. Please install PySide6 or use the Tkinter UI.")

    from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
    from dev.abhishekraha.secretmanager.ui.ModernAuthDialog import ModernAuthDialog
    from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    active_service = service or SecretManagerService(client_name="Modern-UI")

    # If the service is not currently unlocked, require master password entry first
    if not active_service.is_unlocked():
        auth_dialog = ModernAuthDialog(service=active_service)
        if auth_dialog.exec() != QtWidgets.QDialog.Accepted or not auth_dialog.authenticated:
            # User closed dialog without authenticating
            return 0

    window = ModernMainWindow(service=active_service)
    window.show()
    return app.exec()
