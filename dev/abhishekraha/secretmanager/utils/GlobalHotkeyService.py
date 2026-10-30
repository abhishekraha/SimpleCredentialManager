import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal, QRect
from PySide6.QtGui import QGuiApplication, QCursor

logger = logging.getLogger(__name__)


def get_active_screen_geometry() -> QRect:
    """
    Returns the geometry of the screen/monitor where the cursor currently resides.
    Falls back to primary screen, or default 1920x1080 QRect if no screen is detected.
    """
    app = QGuiApplication.instance()
    if not app:
        # If QGuiApplication is not initialized yet
        return QRect(0, 0, 1920, 1080)

    cursor_pos = QCursor.pos()
    screen = QGuiApplication.screenAt(cursor_pos)
    if not screen:
        screen = QGuiApplication.primaryScreen()

    if screen:
        return screen.geometry()

    return QRect(0, 0, 1920, 1080)


class GlobalHotkeyService(QObject):
    """
    Global hotkey listener using pynput, emitting a Qt Signal hotkey_triggered.
    Gracefully degrades if pynput is unavailable or encounters OS permission/display errors.
    """
    hotkey_triggered = Signal()

    def __init__(self, parent: Optional[QObject] = None, hotkey: str = "<ctrl>+<shift>+<space>"):
        super().__init__(parent)
        self.hotkey = hotkey
        self._listener = None
        self._active = False

    def start(self) -> None:
        """
        Launches global hotkey listening in a daemon thread.
        Gracefully handles missing pynput or OS-level permission / display server errors.
        """
        if self._active:
            return

        try:
            import pynput.keyboard  # type: ignore

            def on_activate():
                self.hotkey_triggered.emit()

            self._listener = pynput.keyboard.GlobalHotKeys({
                self.hotkey: on_activate
            })
            self._listener.daemon = True
            self._listener.start()
            self._active = True
            logger.info("GlobalHotkeyService registered for %s", self.hotkey)
        except Exception as ex:
            logger.warning(
                "GlobalHotkeyService could not start listener for '%s': %s. Degraded gracefully.",
                self.hotkey,
                ex,
            )
            self._listener = None
            self._active = False

    def stop(self) -> None:
        """
        Stops the listener thread cleanly.
        """
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as ex:
                logger.debug("Error stopping GlobalHotkeyService listener: %s", ex)
            finally:
                self._listener = None
        self._active = False

    def is_active(self) -> bool:
        """
        Returns whether global hotkey listening is currently active.
        """
        return self._active
