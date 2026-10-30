"""
Custom circular arc countdown widget for TOTP 30-second window in PySide6.
"""

import math

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import QWidget
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QWidget = object


class TotpCountdownWidget(QWidget):
    """
    A circular countdown ring widget displaying the seconds remaining (e.g. 28s)
    and an animated sweep arc reflecting progress within the 30s TOTP period.
    """

    def __init__(self, parent=None, size=44):
        if not HAS_QT:
            return
        super().__init__(parent)
        self._remaining_seconds = 30
        self._total_seconds = 30
        self._progress = 0.0  # 0.0 to 1.0
        self._size = size
        self.setFixedSize(size, size)

    def set_remaining(self, remaining_seconds, total_seconds=30):
        if not HAS_QT:
            return
        self._remaining_seconds = max(0, int(remaining_seconds))
        self._total_seconds = max(1, int(total_seconds))
        self._progress = (self._total_seconds - self._remaining_seconds) / float(self._total_seconds)
        self.update()

    def paintEvent(self, event):
        if not HAS_QT:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        margin = 4
        arc_rect = QRectF(
            rect.x() + margin,
            rect.y() + margin,
            rect.width() - (margin * 2),
            rect.height() - (margin * 2),
        )

        # Background track pen
        bg_pen = QPen(QColor(60, 65, 75), 3)
        painter.setPen(bg_pen)
        painter.drawEllipse(arc_rect)

        # Arc color transitions: Green -> Yellow (< 10s) -> Red (< 5s)
        if self._remaining_seconds <= 5:
            arc_color = QColor(239, 68, 68)  # Red
        elif self._remaining_seconds <= 10:
            arc_color = QColor(245, 158, 11)  # Amber
        else:
            arc_color = QColor(16, 185, 129)  # Emerald green

        # Active progress arc
        active_pen = QPen(arc_color, 3)
        active_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(active_pen)

        # 16ths of a degree in Qt: 360 * 16 = 5760
        # Start at top (90 degrees = 90 * 16)
        start_angle = 90 * 16
        # Remaining proportion spans backwards
        remaining_ratio = self._remaining_seconds / float(self._total_seconds)
        span_angle = int(-remaining_ratio * 360 * 16)

        painter.drawArc(arc_rect, start_angle, span_angle)

        # Text in center
        painter.setPen(QColor(220, 225, 235))
        font = QFont()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, f"{self._remaining_seconds}s")
