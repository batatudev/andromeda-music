# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: ui/widgets/frames.py
# OPIS ZMIAN: Wyodrębnienie ClickableFrame z ui_core.py.

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
