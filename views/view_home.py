
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

class HomeView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        
    def load(self):
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        lbl = QLabel("Wczytywanie...")
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 16px;")
        lbl.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(lbl)
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)

        def fetch():
            # Check offline status via repo
            is_offline = self.main_window.repo._is_offline()
            online = not is_offline
            
            # Use repo instead of client to benefit from caching and offline DB
            stars = self.main_window.repo.get_starred(40)
            albs = self.main_window.repo.get_random_albums(6)
            songs = self.main_window.repo.get_random_songs(10)

            if not self.main_window.all_artists_data:
                if online:
                    self.main_window.all_artists_data = self.main_window.client.get_artists()
                else:
                    self.main_window.all_artists_data = self.main_window.repo.library_sync.get_all_artists()

            r_arts = random.sample(self.main_window.all_artists_data, min(6, len(self.main_window.all_artists_data))) if self.main_window.all_artists_data else []
            return (True, stars, albs, songs, r_arts)

        def on_ready(data):
            if not data:
                return
            self.content_widget.setUpdatesEnabled(False)
            self._clear()
            online, stars, albs, songs, r_arts = data
            if not online:
                err_lbl = QLabel("Brak połączenia. Skonfiguruj serwer w Ustawieniach.")
                err_lbl.setStyleSheet(f"color: {THEME['text_main']}; font-size: 18px;")
                err_lbl.setAlignment(Qt.AlignCenter)
                self.content_layout.addWidget(err_lbl)
                self.content_layout.addStretch()
                self.content_widget.setUpdatesEnabled(True)
                return

            h = HeroSection()
            h.play_clicked.connect(lambda s: self.main_window.engine.play_list([s], 0))
            self.content_layout.addWidget(h)

            if stars:
                s = random.choice(stars)
                h.set_data(f"TWÓJ ULUBIONY UTWÓR: {s.artist.upper()}", s.title, s)
                if s.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), h)

            self.content_layout.addWidget(QLabel("Albumy", font=QFont("Sans", 20, QFont.Bold)))
            flow_albs = FlowLayout(spacing=25)
            for i, a in enumerate(albs):
                card = MediaCard(a, MediaType.ALBUM)
                card.clicked.connect(self.main_window._show_details)
                card.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.client.get_album(d.item_id).get('song',[]), 0))
                card.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                card.download_videos_clicked.connect(self.main_window._handle_download_videos)
                card.artist_clicked.connect(self.main_window._show_details)
                card.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                card.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                card.save_image_clicked.connect(self.main_window._save_image_to_file)
                flow_albs.addWidget(card)
                if a.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), card)
            self.content_layout.addLayout(flow_albs)

            self.content_layout.addSpacing(20)
            self.content_layout.addWidget(QLabel("Utwory", font=QFont("Sans", 20, QFont.Bold)))

            sc = QWidget()
            vl = QVBoxLayout(sc)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(5)

            for i, s in enumerate(songs):
                item = SongItem(s)
                item.clicked.connect(lambda song, idx=0, sl=[s]: self.main_window.engine.play_list(sl, idx))
                item.fav_clicked.connect(self.main_window._handle_song_fav)
                item.add_to_queue_clicked.connect(self.main_window.engine.add_to_queue)
                item.add_to_playlist_clicked.connect(self.main_window._show_playlist_dialog)
                item.artist_clicked.connect(self.main_window._show_details)
                item.album_clicked.connect(self.main_window._show_details)
                item.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                item.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                item.save_image_clicked.connect(self.main_window._save_image_to_file)
                vl.addWidget(item)
                if s.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), item)

            self.content_layout.addWidget(sc)

            if r_arts:
                self.content_layout.addSpacing(20)
                self.content_layout.addWidget(QLabel("Artyści", font=QFont("Sans", 20, QFont.Bold)))
                flow_arts = FlowLayout(spacing=25)
                for i, a in enumerate(r_arts):
                    card = MediaCard(a, MediaType.ARTIST)
                    card.clicked.connect(self.main_window._show_details)
                    card.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.client.get_top_songs_for_artist(d.title), 0))
                    card.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                    card.download_videos_clicked.connect(self.main_window._handle_download_videos)
                    card.set_custom_image_clicked.connect(self.main_window._set_custom_artist_image)
                    card.reset_custom_image_clicked.connect(self.main_window._reset_custom_artist_image)
                    card.save_image_clicked.connect(self.main_window._save_image_to_file)
                    flow_arts.addWidget(card)
                    if a.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), card)
                self.content_layout.addLayout(flow_arts)

            self.content_layout.addStretch()
            self.content_widget.setUpdatesEnabled(True)

        self.main_window.run_async(fetch, on_ready, page_bound=True)


