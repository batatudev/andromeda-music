import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.enums import MediaType
from ui.components import SongItem
from core.i18n import tr
from views.library_base import LibraryScrollArea


class TracksView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.track_list_layout = None
        self.offset = 0
        self.is_loading = False
        self._current_songs = []

    def _on_scroll(self, val):
        if not self.is_loading and val > self.verticalScrollBar().maximum() - 200:
            self._load_more()

    def _on_song_clicked(self, idx):
        if 0 <= idx < len(self._current_songs):
            self.main_window.engine.play_list(self._current_songs, idx)

    def load(self):
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        self._current_songs.clear()
        title_txt = tr("tracks.title", "Wszystkie Utwory")
        self.content_layout.addWidget(QLabel(title_txt, font=QFont("Sans", 24, QFont.Bold)))
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
            return self.main_window.repo.get_random_songs(50)

        def on_ready(songs):
            if songs:
                self.content_widget.setUpdatesEnabled(False)
                start_idx = len(self._current_songs)
                self._current_songs.extend(songs)

                for i, s in enumerate(songs):
                    real_idx = start_idx + i
                    item = SongItem(s, parent=self.content_widget)
                    item.clicked.connect(lambda song, idx=real_idx: self._on_song_clicked(idx))
                    item.fav_clicked.connect(self.main_window._handle_song_fav)
                    item.add_to_queue_clicked.connect(self.main_window.engine.add_to_queue)
                    item.add_to_playlist_clicked.connect(self.main_window._show_playlist_dialog)
                    item.artist_clicked.connect(self.main_window._show_details)
                    item.album_clicked.connect(self.main_window._show_details)
                    item.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                    item.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                    item.save_image_clicked.connect(self.main_window._save_image_to_file)
                    self.track_list_layout.addWidget(item)
                    if s.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), item)
                self.content_widget.setUpdatesEnabled(True)
            self.is_loading = False

        self.main_window.run_async(fetch, on_ready, page_bound=True)