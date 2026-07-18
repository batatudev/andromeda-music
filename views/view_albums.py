# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: views/view_albums.py
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

from views.library_base import LibraryScrollArea

class AlbumsView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.album_flow = None
        self.offset = 0
        self.is_loading = False

    def _on_scroll(self, val):
        if not self.is_loading and val > self.verticalScrollBar().maximum() - 200:
            self._load_more()

    def load(self):
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        self.content_layout.addWidget(QLabel("Wszystkie Albumy", font=QFont("Sans", 24, QFont.Bold)))
        self.album_flow = FlowLayout(spacing=25)
        self.content_layout.addLayout(self.album_flow)
        self.offset = 0
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)
        self._load_more()

    def _load_more(self):
        if self.is_loading:
            return
        self.is_loading = True
        def fetch():
            return self.main_window.client.get_albums(self.offset, 30)
        def on_ready(albs):
            if albs:
                self.content_widget.setUpdatesEnabled(False)
                for a in albs:
                    c = MediaCard(a, MediaType.ALBUM)
                    c.clicked.connect(self.main_window._show_details)
                    c.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.client.get_album(d.item_id).get('song',[]), 0))
                    c.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                    c.download_videos_clicked.connect(self.main_window._handle_download_videos)
                    c.artist_clicked.connect(self.main_window._show_details)
                    c.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                    c.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                    c.save_image_clicked.connect(self.main_window._save_image_to_file)
                    self.album_flow.addWidget(c)
                    if a.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), c)
                    self.offset += 1
                self.content_widget.setUpdatesEnabled(True)
            self.is_loading = False
        self.main_window.run_async(fetch, on_ready, page_bound=True)


