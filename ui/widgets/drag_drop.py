# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: ui/widgets/drag_drop.py
# OPIS ZMIAN: Wyodrębnienie DragDropContainer i DragHandle z ui_core.py.

import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import QWidget, QLabel, QApplication
from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray
from PySide6.QtGui import QDrag

from config import THEME

class DragDropContainer(QWidget):
    drop_occurred = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-queue-index"):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        data = e.mimeData().data("application/x-queue-index").data().decode()
        if data.isdigit():
            self.drop_occurred.emit(int(data), e.position().toPoint().y())
        e.acceptProposedAction()

class DragHandle(QLabel):
    def __init__(self, index):
        super().__init__()
        self.index = index
        self.setPixmap(qta.icon('fa5s.grip-vertical', color=THEME["text_muted"]).pixmap(16, 16))
        self.setFixedSize(20, 40)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.OpenHandCursor)
        self.drag_start_pos = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_start_pos = e.pos()

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton):
            return
        if self.drag_start_pos is None:
            return
        if (e.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-queue-index", QByteArray(str(self.index).encode()))
        drag.setMimeData(mime)
        self.setCursor(Qt.ClosedHandCursor)
        drag.exec(Qt.MoveAction)
        self.setCursor(Qt.OpenHandCursor)
        self.drag_start_pos = None
