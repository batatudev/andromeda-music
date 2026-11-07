# views/library_base.py
import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import random
import qtawesome as qta

from config import THEME
from utils import MediaItem
from core.enums import MediaType
from ui.widgets import FlowLayout, DragDropContainer, SmoothScrollArea
from ui.components import SongItem, MediaCard, MediaHeader, HeroSection, QueueHeader

class LibraryScrollArea(SmoothScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._is_loaded = False
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("LibraryContentWidget")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(15)
        self.setWidget(self.content_widget)

    def invalidate_cache(self):
        self._is_loaded = False

    def _clear(self):
        self._clear_layout(self.content_layout)

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())