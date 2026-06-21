# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: views/view_tracks.py
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

class TracksView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.track_list_layout = None
        self.offset = 0
        self.is_loading = False

    def _on_scroll(self, val):
        if not self.is_loading and val > self.verticalScrollBar().maximum() - 200:
            self._load_more()

    def load(self):
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        self.content_layout.addWidget(QLabel("Wszystkie Utwory", font=QFont("Sans", 24, QFont.Bold)))
        self.track_list_layout = QVBoxLayout()
        self.content_layout.addLayout(self.track_list_layout)
        self.offset = 0
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)
        self._load_more()

    def _load_more(self):
        if self.is_loading:
            return
        self.is_loading = True
        def fetch():
            return self.main_window.client.get_random_songs(50)
        def on_ready(songs):
            if songs:
                self.content_widget.setUpdatesEnabled(False)
                for s in songs:
                    i = SongItem(s)
                    i.clicked.connect(lambda song, idx=0, sl=[s]: self.main_window.engine.play_list(sl, idx))
                    i.fav_clicked.connect(self.main_window._handle_song_fav)
                    i.add_to_queue_clicked.connect(self.main_window.engine.add_to_queue)
                    i.add_to_playlist_clicked.connect(self.main_window._show_playlist_dialog)
                    i.artist_clicked.connect(self.main_window._show_details)
                    i.album_clicked.connect(self.main_window._show_details)
                    i.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                    i.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                    i.save_image_clicked.connect(self.main_window._save_image_to_file)
                    self.track_list_layout.addWidget(i)
                    if s.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), i)
                self.content_widget.setUpdatesEnabled(True)
            self.is_loading = False
        self.main_window.run_async(fetch, on_ready, page_bound=True)


