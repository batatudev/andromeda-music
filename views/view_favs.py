# views/view_favs.py
import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import qtawesome as qta

from config import THEME
from ui.components import SongItem
from core.i18n import tr
from views.library_base import LibraryScrollArea

class FavsView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self._current_songs = []

    def _on_song_clicked(self, idx):
        if 0 <= idx < len(self._current_songs):
            self.main_window.engine.play_list(self._current_songs, idx)

    def load(self, force=False):
        if not force and self._is_loaded:
            return

        self.show_loading()
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        self._current_songs.clear()
        self.content_widget.setUpdatesEnabled(True)

        def on_ready(songs):
            self.content_widget.setUpdatesEnabled(False)
            self._clear()
            self._current_songs = list(songs) if songs else []
            title_txt = tr("favs.title", "Twoje ulubione utwory")
            self.content_layout.addWidget(QLabel(title_txt, font=QFont("Sans", 24, QFont.Bold)))

            if not songs:
                self.content_layout.addStretch()
                iv = QVBoxLayout()
                iv.setAlignment(Qt.AlignCenter)
                ie = QLabel()
                ie.setPixmap(qta.icon('fa5s.heart-broken', color=THEME["text_muted"]).pixmap(100, 100))
                empty_txt = tr("favs.empty", "Brak polubionych utworów")
                te = QLabel(empty_txt)
                te.setStyleSheet(f"color:{THEME['text_muted']}; font-size:18px;")
                iv.addWidget(ie)
                iv.addWidget(te)
                self.content_layout.addLayout(iv)
                self.content_layout.addStretch()
                self.content_widget.setUpdatesEnabled(True)
                self._is_loaded = True
                self.hide_loading(0)
                return

            for i, s in enumerate(songs):
                item = SongItem(s, parent=self.content_widget)
                item.clicked.connect(lambda song, idx=i: self._on_song_clicked(idx))
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
            self._is_loaded = True
            self.hide_loading(delay_ms=60)

        self.main_window.run_async(lambda: self.main_window.repo.get_starred(100), on_ready, page_bound=True)