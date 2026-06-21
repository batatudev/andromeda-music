# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: views/library_base.py
# OPIS ZMIAN: Ekstrakcja z view_library.py (SRP)


import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import random
import qtawesome as qta

from config import THEME
from utils import MediaItem
from core.enums import MediaType
from ui.widgets import FlowLayout, DragDropContainer
from ui.components import SongItem, MediaCard, MediaHeader, HeroSection, QueueHeader

class LibraryScrollArea(QScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("background: transparent; border: none;")
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(15)
        self.setWidget(self.content_widget)
        
    def _clear(self):
        while self.content_layout.count():
            i = self.content_layout.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
            elif i.layout():
                self._clear_layout(i.layout())

    def _clear_layout(self, lay):
        while lay.count():
            i = lay.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
            elif i.layout():
                self._clear_layout(i.layout())

