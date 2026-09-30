import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize
from config import THEME


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def setText(self, text):
        self._full_text = text
        super().setText(self._elided_text())

    def text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().setText(self._elided_text())
        super().resizeEvent(event)

    def _elided_text(self):
        fm = self.fontMetrics()
        return fm.elidedText(self._full_text, Qt.ElideRight, self.width())

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self._full_text) + 5, fm.height() + 6)

    def minimumSizeHint(self):
        return QSize(30, self.fontMetrics().height() + 6)


class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, text="", default_color=None, hover_color=None, font_weight="normal", font_size="12px"):
        super().__init__(text)
        self.default_color = default_color if default_color is not None else THEME.get("text_muted", "#888888")
        self.hover_color = hover_color if hover_color is not None else THEME.get("text_main", "#ffffff")
        self.font_weight = font_weight
        self.font_size = font_size
        self.setCursor(Qt.PointingHandCursor)
        self.update_style(self.default_color, "none")

    def update_style(self, color, decoration):
        self.setStyleSheet(
            f"color: {color}; background: transparent; font-weight: {self.font_weight}; "
            f"font-size: {self.font_size}; text-decoration: {decoration}; border: none;"
        )

    def enterEvent(self, e):
        self.update_style(self.hover_color, "underline")
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update_style(self.default_color, "none")
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
        else:
            super().mousePressEvent(e)


class ClickableElidedLabel(ClickableLabel):
    def __init__(self, text="", default_color=None, hover_color=None, font_weight="normal", font_size="12px"):
        super().__init__(text, default_color, hover_color, font_weight, font_size)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def setText(self, text):
        self._full_text = text
        super().setText(self._elided_text())

    def text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().setText(self._elided_text())
        super().resizeEvent(event)

    def _elided_text(self):
        fm = self.fontMetrics()
        return fm.elidedText(self._full_text, Qt.ElideRight, self.width())

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self._full_text) + 5, fm.height() + 6)

    def minimumSizeHint(self):
        return QSize(30, self.fontMetrics().height() + 6)