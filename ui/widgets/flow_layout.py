import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QLayout
from PySide6.QtCore import Qt, QSize, QRect, QPoint

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=25):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._item_list = []
        self._spacing = spacing

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def minimumSizeHint(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)

        if not self._item_list:
            return 0

        space_x = self._spacing
        space_y = self._spacing

        base_w = 210
        columns = max(1, (effective_rect.width() + space_x) // (base_w + space_x))
        item_w = (effective_rect.width() - (columns - 1) * space_x) // columns

        max_w = max([item.maximumSize().width() for item in self._item_list])
        if 0 < max_w < 16777215:
            item_w = min(item_w, max_w)

        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        col_idx = 0

        for item in self._item_list:
            w = item.widget()
            if w and hasattr(w, 'type_str'):
                item_h = item_w + 70
            else:
                item_h = item.sizeHint().height()

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_w, item_h)))

            x += item_w + space_x
            line_height = max(line_height, item_h)
            col_idx += 1

            if col_idx >= columns:
                x = effective_rect.x()
                y += line_height + space_y
                line_height = 0
                col_idx = 0

        return y + line_height - rect.y() + bottom