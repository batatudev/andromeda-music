import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import QWidget, QLabel, QApplication, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray, QPoint
from PySide6.QtGui import QDrag, QPainter, QPixmap, QPen, QColor

from config import THEME

class DragDropContainer(QWidget):
    drop_occurred = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._drag_active = False
        self._indicator_y = -1
        self._last_drag_pos_y = -100

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-queue-index"):
            self._drag_active = True
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._drag_active = False
        self._set_indicator(-1)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat("application/x-queue-index"):
            e.acceptProposedAction()
            pos_y = e.position().toPoint().y()
            if abs(pos_y - self._last_drag_pos_y) < 4:
                return
            self._last_drag_pos_y = pos_y

            layout = self.layout()
            indicator_y = -1

            if layout and layout.count() > 0:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget():
                        w = item.widget()
                        if pos_y < w.geometry().center().y():
                            indicator_y = w.geometry().top() - (layout.spacing() // 2)
                            break
                else:
                    last_w = layout.itemAt(layout.count() - 1).widget()
                    if last_w:
                        indicator_y = last_w.geometry().bottom() + (layout.spacing() // 2)

            self._set_indicator(indicator_y)

    def dropEvent(self, e):
        self._drag_active = False
        self._set_indicator(-1)
        self._last_drag_pos_y = -100
        data = e.mimeData().data("application/x-queue-index").data().decode()
        if data.isdigit():
            self.drop_occurred.emit(int(data), e.position().toPoint().y())
        e.acceptProposedAction()

    def _set_indicator(self, y):
        if self._indicator_y != y:
            if self._indicator_y >= 0:
                self.update(0, self._indicator_y - 5, self.width(), 10)

            self._indicator_y = y

            if self._indicator_y >= 0:
                self.update(0, self._indicator_y - 5, self.width(), 10)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._drag_active and self._indicator_y >= 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            pen = QPen(QColor(THEME["accent"]))
            pen.setWidth(2)
            painter.setPen(pen)

            painter.drawLine(20, self._indicator_y, self.width() - 20, self._indicator_y)

            painter.setBrush(QColor(THEME["accent"]))
            painter.drawEllipse(QPoint(20, self._indicator_y), 3, 3)
            painter.drawEllipse(QPoint(self.width() - 20, self._indicator_y), 3, 3)
            painter.end()

class DragHandle(QLabel):
    def __init__(self, index, parent_item=None):
        super().__init__()
        self.index = index
        self.parent_item = parent_item
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

        if self.parent_item:
            pixmap = self.parent_item.grab()
            transparent_pixmap = QPixmap(pixmap.size())
            transparent_pixmap.fill(Qt.transparent)

            painter = QPainter(transparent_pixmap)
            painter.setOpacity(0.7)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

            drag.setPixmap(transparent_pixmap)

            handle_pos_in_parent = self.mapTo(self.parent_item, e.pos())
            drag.setHotSpot(handle_pos_in_parent)

            effect = QGraphicsOpacityEffect(self.parent_item)
            effect.setOpacity(0.3)
            self.parent_item.setGraphicsEffect(effect)

        self.setCursor(Qt.ClosedHandCursor)
        drag.exec(Qt.MoveAction)

        self.setCursor(Qt.OpenHandCursor)
        self.drag_start_pos = None

        if self.parent_item:
            self.parent_item.setGraphicsEffect(None)