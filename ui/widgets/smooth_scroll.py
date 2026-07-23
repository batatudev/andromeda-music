import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property


class SmoothScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_scroll = 0
        self._scroll_anim = QPropertyAnimation(self, b"scrollValue")
        self._scroll_anim.setDuration(350)
        self._scroll_anim.setEasingCurve(QEasingCurve.OutCubic)

    @Property(int)
    def scrollValue(self):
        return self.verticalScrollBar().value()

    @scrollValue.setter
    def scrollValue(self, val):
        self.verticalScrollBar().setValue(val)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        current_val = self.verticalScrollBar().value()
        if self._scroll_anim.state() != QPropertyAnimation.State.Running:
            self._target_scroll = current_val

        self._target_scroll -= int(delta * 1.5)

        max_scroll = self.verticalScrollBar().maximum()
        min_scroll = self.verticalScrollBar().minimum()
        self._target_scroll = max(min_scroll, min(max_scroll, self._target_scroll))

        self._scroll_anim.stop()
        self._scroll_anim.setStartValue(current_val)
        self._scroll_anim.setEndValue(self._target_scroll)
        self._scroll_anim.start()
