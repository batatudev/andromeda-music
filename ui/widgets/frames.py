import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Qt, Signal

class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
