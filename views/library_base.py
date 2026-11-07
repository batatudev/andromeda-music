# views/library_base.py
import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor
import random
import qtawesome as qta

from config import THEME
from utils import MediaItem
from core.enums import MediaType
from ui.widgets import FlowLayout, DragDropContainer, SmoothScrollArea
from ui.components import SongItem, MediaCard, MediaHeader, HeroSection, QueueHeader
from core.i18n import tr

class LoadingOverlay(QWidget):
    """
    Czysta, w 100% nieprzezroczysta kurtyna ładowania na litym tle #050505.
    Pozostaje całkowicie kryjąca do momentu jednoczesnego odsłonięcia zawartości.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoadingOverlay")
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(THEME.get("bg_main", "#050505")))
        self.setPalette(pal)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)

        self.spinner_lbl = QLabel()
        self.spinner_lbl.setFixedSize(40, 40)
        self.spinner_lbl.setAlignment(Qt.AlignCenter)
        self.spinner_lbl.setStyleSheet("background: transparent; border: none;")
        self._spin_anim = qta.Spin(self.spinner_lbl, interval=16, step=10)
        self.spinner_lbl.setPixmap(
            qta.icon('fa5s.circle-notch', color=THEME.get('accent', '#aa00ff'), animation=self._spin_anim).pixmap(32, 32)
        )

        self.text_lbl = QLabel(tr("common.loading", "Wczytywanie..."))
        self.text_lbl.setStyleSheet(
            f"color: {THEME.get('text_muted', '#888888')}; font-size: 14px; font-weight: 500; background: transparent; border: none;"
        )
        self.text_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.spinner_lbl, 0, Qt.AlignCenter)
        layout.addWidget(self.text_lbl, 0, Qt.AlignCenter)
        self.hide()

class LibraryScrollArea(SmoothScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._is_loaded = False
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.viewport().setAutoFillBackground(True)
        v_pal = self.viewport().palette()
        v_pal.setColor(QPalette.Window, QColor(THEME.get("bg_main", "#050505")))
        self.viewport().setPalette(v_pal)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("LibraryContentWidget")
        self.content_widget.setAutoFillBackground(True)
        c_pal = self.content_widget.palette()
        c_pal.setColor(QPalette.Window, QColor(THEME.get("bg_main", "#050505")))
        self.content_widget.setPalette(c_pal)

        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(15)
        self.setWidget(self.content_widget)

        self.loading_overlay = LoadingOverlay(self.viewport())
        self.show_loading()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.setGeometry(0, 0, self.viewport().width(), self.viewport().height())

    def show_loading(self, text=None):
        if hasattr(self, 'content_widget') and self.content_widget:
            self.content_widget.setVisible(False)
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            if text:
                self.loading_overlay.text_lbl.setText(text)
            else:
                self.loading_overlay.text_lbl.setText(tr("common.loading", "Wczytywanie..."))
            self.loading_overlay.setGeometry(0, 0, self.viewport().width(), self.viewport().height())
            self.loading_overlay.show()
            self.loading_overlay.raise_()

    def hide_loading(self, delay_ms=100):
        def _apply_hide():
            if hasattr(self, 'loading_overlay') and self.loading_overlay:
                self.loading_overlay.hide()
            if hasattr(self, 'content_widget') and self.content_widget:
                self.content_widget.setVisible(True)

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _apply_hide)
        else:
            _apply_hide()

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