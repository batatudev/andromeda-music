import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.enums import MediaType
from ui.widgets import FlowLayout
from ui.components import MediaCard

from views.library_base import LibraryScrollArea

class ArtistsView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.artist_flow = None
        self.offset = 0
        self.is_loading = False

    def _on_scroll(self, val):
        if not self.is_loading and val > self.verticalScrollBar().maximum() - 200:
            self._load_more()

    def load(self):
        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        self.content_layout.addWidget(QLabel("Wszyscy Artyści", font=QFont("Sans", 24, QFont.Bold)))
        self.artist_flow = FlowLayout(spacing=25)
        self.content_layout.addLayout(self.artist_flow)
        self.offset = 0
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)
        self._load_more()

    def _load_more(self):
        if self.is_loading:
            return
        self.is_loading = True
        def fetch():
            if not self.main_window.all_artists_data:
                self.main_window.all_artists_data = self.main_window.repo.get_artists()
            return self.main_window.all_artists_data[self.offset : self.offset + 30]
        def on_ready(paczka):
            if paczka:
                self.content_widget.setUpdatesEnabled(False)
                for a in paczka:
                    c = MediaCard(a, MediaType.ARTIST)
                    c.clicked.connect(self.main_window._show_details)
                    c.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.repo.get_top_songs_for_artist(d.title), 0))
                    c.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                    c.download_videos_clicked.connect(self.main_window._handle_download_videos)
                    c.set_custom_image_clicked.connect(self.main_window._set_custom_artist_image)
                    c.reset_custom_image_clicked.connect(self.main_window._reset_custom_artist_image)
                    c.save_image_clicked.connect(self.main_window._save_image_to_file)
                    self.artist_flow.addWidget(c)
                    if a.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), c)
                    self.offset += 1
                self.content_widget.setUpdatesEnabled(True)
            self.is_loading = False
        self.main_window.run_async(fetch, on_ready, page_bound=True)