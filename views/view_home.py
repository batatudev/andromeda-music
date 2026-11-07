# views/view_home.py
import os
os.environ["QT_API"] = "pyside6"

import random
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont
import qtawesome as qta

from config import THEME
from utils import MediaItem
from core.enums import MediaType
from ui.components import SongItem, MediaCard, HeroSection
from core.i18n import tr
from views.library_base import LibraryScrollArea

class ResponsiveCardRow(QWidget):
    """
    Niełamliwy, jednoliniowy kontener kafelków.
    Zwraca minimumSizeHint = 0, aby nigdy nie blokować zwężania nadrzędnego okna,
    a jego szerokość jest sterowana dynamicznie z widoku HomeView.
    """
    def __init__(self, spacing=25, parent=None):
        super().__init__(parent)
        self.spacing = spacing
        self.cards = []
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(spacing)
        self.h_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def sizeHint(self):
        return QSize(0, self.height() if self.height() > 0 else 280)

    def add_card(self, card):
        card.setFixedSize(210, 280)
        self.cards.append(card)
        self.h_layout.addWidget(card)

    def update_width(self, avail_w):
        if not self.cards or avail_w <= 100:
            return

        spacing = self.spacing
        ideal_card_w = 210

        fit_count = max(1, (avail_w + spacing) // (ideal_card_w + spacing))
        visible_count = min(len(self.cards), fit_count)
        visible_count = max(1, visible_count)

        target_card_w = (avail_w - (visible_count - 1) * spacing) // visible_count
        target_card_w = max(150, min(300, target_card_w))
        target_card_h = target_card_w + 70

        for i, card in enumerate(self.cards):
            if i < visible_count:
                card.show()
                card.setFixedSize(target_card_w, target_card_h)
            else:
                card.hide()

        self.setFixedHeight(target_card_h)

class HomeView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.row_albs = None
        self.row_arts = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalculate_rows()

    def _recalculate_rows(self):
        avail_w = self.viewport().width() - 60
        if avail_w > 100:
            if self.row_albs:
                self.row_albs.update_width(avail_w)
            if self.row_arts:
                self.row_arts.update_width(avail_w)

    def load(self, force=False):
        if not force and self._is_loaded:
            return

        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        self.row_albs = None
        self.row_arts = None

        lbl = QLabel(tr("common.loading", "Wczytywanie..."))
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 16px; background: transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        self.content_layout.addStretch()
        self.content_layout.addWidget(lbl)
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)

        def fetch():
            repo = self.main_window.repo
            all_artists = self.main_window.all_artists_data

            with ThreadPoolExecutor(max_workers=4) as executor:
                f_stars = executor.submit(repo.get_starred, 40)
                f_albs = executor.submit(repo.get_random_albums, 16)
                f_songs = executor.submit(repo.get_random_songs, 10)
                f_arts = executor.submit(repo.get_artists) if not all_artists else None

                stars = f_stars.result()
                albs = f_albs.result()
                songs = f_songs.result()

                if f_arts:
                    all_artists = f_arts.result()
                    self.main_window.all_artists_data = all_artists

            r_arts = (
                random.sample(all_artists, min(16, len(all_artists)))
                if all_artists
                else []
            )
            return (stars, albs, songs, r_arts)

        def on_ready(data):
            if not data:
                return
            self.content_widget.setUpdatesEnabled(False)
            self._clear()
            stars, albs, songs, r_arts = data

            h = HeroSection()
            h.play_clicked.connect(lambda s: self.main_window.engine.play_list([s], 0))
            self.content_layout.addWidget(h)

            if stars:
                s = random.choice(stars)
                h.set_data(s.artist.upper(), s.title, s)
                if s.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), h)

            # SEKCJA ALBUMY
            self.content_layout.addWidget(
                QLabel(tr("menu.albums", "Albumy"), font=QFont("Sans", 20, QFont.Bold))
            )
            self.row_albs = ResponsiveCardRow(spacing=25, parent=self.content_widget)
            for i, a in enumerate(albs):
                card = MediaCard(a, MediaType.ALBUM)
                card.clicked.connect(self.main_window._show_details)
                card.play_clicked.connect(
                    lambda d, t: self.main_window.engine.play_list(
                        self.main_window.repo.get_album(d.item_id).get('song', []), 0
                    )
                )
                card.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                card.download_videos_clicked.connect(self.main_window._handle_download_videos)
                card.artist_clicked.connect(self.main_window._show_details)
                card.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                card.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                card.save_image_clicked.connect(self.main_window._save_image_to_file)
                self.row_albs.add_card(card)
                if a.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), card)
            self.content_layout.addWidget(self.row_albs)

            self.content_layout.addSpacing(20)
            self.content_layout.addWidget(
                QLabel(tr("menu.tracks", "Utwory"), font=QFont("Sans", 20, QFont.Bold))
            )

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

            # SEKCJA ARTYŚCI
            if r_arts:
                self.content_layout.addSpacing(20)
                self.content_layout.addWidget(
                    QLabel(tr("menu.artists", "Artyści"), font=QFont("Sans", 20, QFont.Bold))
                )
                self.row_arts = ResponsiveCardRow(spacing=25, parent=self.content_widget)
                for i, a in enumerate(r_arts):
                    card = MediaCard(a, MediaType.ARTIST)
                    card.clicked.connect(self.main_window._show_details)
                    card.play_clicked.connect(
                        lambda d, t: self.main_window.engine.play_list(
                            self.main_window.repo.get_top_songs_for_artist(d.title), 0
                        )
                    )
                    card.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                    card.download_videos_clicked.connect(self.main_window._handle_download_videos)
                    card.set_custom_image_clicked.connect(self.main_window._set_custom_artist_image)
                    card.reset_custom_image_clicked.connect(self.main_window._reset_custom_artist_image)
                    card.save_image_clicked.connect(self.main_window._save_image_to_file)
                    self.row_arts.add_card(card)
                    if a.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), card)
                self.content_layout.addWidget(self.row_arts)

            self.content_layout.addStretch()
            self._recalculate_rows()
            self.content_widget.setUpdatesEnabled(True)
            self._is_loaded = True

        self.main_window.run_async(fetch, on_ready, page_bound=True)