
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

class FavsView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        
    def load(self):
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        lbl = QLabel("Wczytywanie...")
        lbl.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(lbl)
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)

        def on_ready(songs):
            self.content_widget.setUpdatesEnabled(False)
            self._clear()
            self.content_layout.addWidget(QLabel("Twoje ulubione utwory", font=QFont("Sans", 24, QFont.Bold)))
            if not songs:
                self.content_layout.addStretch()
                iv = QVBoxLayout()
                iv.setAlignment(Qt.AlignCenter)
                ie = QLabel()
                ie.setPixmap(qta.icon('fa5s.heart-broken', color=THEME["text_muted"]).pixmap(100, 100))
                te = QLabel("Brak polubionych")
                te.setStyleSheet(f"color:{THEME['text_muted']}; font-size:18px;")
                iv.addWidget(ie)
                iv.addWidget(te)
                self.content_layout.addLayout(iv)
                self.content_layout.addStretch()
                self.content_widget.setUpdatesEnabled(True)
                return

            for i, s in enumerate(songs):
                item = SongItem(s)
                item.clicked.connect(lambda song, idx=i, sl=songs: self.main_window.engine.play_list(sl, idx))
                item.fav_clicked.connect(self.main_window._handle_song_fav)
                item.add_to_queue_clicked.connect(self.main_window.engine.add_to_queue)
                item.add_to_playlist_clicked.connect(self.main_window._show_playlist_dialog)
                item.artist_clicked.connect(self.main_window._show_details)
                item.album_clicked.connect(self.main_window._show_details)
                item.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                item.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                item.save_image_clicked.connect(self.main_window._save_image_to_file)
                self.content_layout.addWidget(item)
                if s.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), item)
            self.content_layout.addStretch()
            self.content_widget.setUpdatesEnabled(True)
            
        self.main_window.run_async(lambda: self.main_window.client.get_starred(100), on_ready, page_bound=True)


