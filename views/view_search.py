# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: views/view_search.py
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

class SearchView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(500)
        self.search_timer.timeout.connect(self._perform_search)
        self.last_query = ""
        
        self.input_lay = QVBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Czego chcesz posłuchać? (Artyści, Utwory, Albumy)")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 22px;
                padding: 10px 20px;
                font-size: 16px;
            }}
            QLineEdit:focus {{
                border: 1px solid {THEME['accent']};
            }}
        """)
        self.search_input.setFixedHeight(44)
        self.search_input.textChanged.connect(self._on_text_changed)
        
        self.input_lay.addWidget(self.search_input)
        
        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_layout.addLayout(self.input_lay)
        self.content_layout.addSpacing(20)
        self.content_layout.addWidget(self.results_widget)
        self.content_layout.addStretch()

    def load(self):
        self.search_input.setFocus()
        if not self.last_query:
            self._clear_layout(self.results_layout)
            lbl = QLabel("Wpisz tekst, aby rozpocząć wyszukiwanie...")
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 16px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.results_layout.addWidget(lbl)
            
    def _on_text_changed(self, text):
        self.last_query = text.strip()
        if not self.last_query:
            self.search_timer.stop()
            self._clear_layout(self.results_layout)
            lbl = QLabel("Wpisz tekst, aby rozpocząć wyszukiwanie...")
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 16px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.results_layout.addWidget(lbl)
            return
        self.search_timer.start()
        
    def _perform_search(self):
        query = self.last_query
        if not query:
            return
        
        self._clear_layout(self.results_layout)
        lbl = QLabel("Szukam w bibliotece...")
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 16px;")
        lbl.setAlignment(Qt.AlignCenter)
        self.results_layout.addWidget(lbl)

        def fetch():
            return self.main_window.client.search(query, limit=12)

        def on_ready(data):
            if query != self.last_query:
                return
            
            self.results_widget.setUpdatesEnabled(False)
            self._clear_layout(self.results_layout)
            
            if not data or (not data.get('artist') and not data.get('album') and not data.get('song')):
                err_lbl = QLabel(f"Brak wyników dla hasła '{query}'")
                err_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 16px;")
                err_lbl.setAlignment(Qt.AlignCenter)
                self.results_layout.addWidget(err_lbl)
                self.results_widget.setUpdatesEnabled(True)
                return
                
            artists = data.get('artist',[])
            albums = data.get('album',[])
            songs = data.get('song',[])
            
            if artists:
                self.results_layout.addWidget(QLabel("Artyści", font=QFont("Sans", 20, QFont.Bold)))
                flow_arts = FlowLayout(spacing=25)
                for a in artists:
                    card = MediaCard(a, MediaType.ARTIST)
                    card.clicked.connect(self.main_window._show_details)
                    card.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.client.get_top_songs_for_artist(d.title), 0))
                    card.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                    card.set_custom_image_clicked.connect(self.main_window._set_custom_artist_image)
                    card.reset_custom_image_clicked.connect(self.main_window._reset_custom_artist_image)
                    card.save_image_clicked.connect(self.main_window._save_image_to_file)
                    flow_arts.addWidget(card)
                    if a.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), card)
                self.results_layout.addLayout(flow_arts)
                self.results_layout.addSpacing(20)

            if albums:
                self.results_layout.addWidget(QLabel("Albumy", font=QFont("Sans", 20, QFont.Bold)))
                flow_albs = FlowLayout(spacing=25)
                for a in albums:
                    card = MediaCard(a, MediaType.ALBUM)
                    card.clicked.connect(self.main_window._show_details)
                    card.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.client.get_album(d.item_id).get('song',[]), 0))
                    card.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                    card.artist_clicked.connect(self.main_window._show_details)
                    card.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                    card.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                    card.save_image_clicked.connect(self.main_window._save_image_to_file)
                    flow_albs.addWidget(card)
                    if a.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), card)
                self.results_layout.addLayout(flow_albs)
                self.results_layout.addSpacing(20)
                
            if songs:
                self.results_layout.addWidget(QLabel("Utwory", font=QFont("Sans", 20, QFont.Bold)))
                sc = QWidget()
                vl = QVBoxLayout(sc)
                vl.setContentsMargins(0, 0, 0, 0)
                vl.setSpacing(5)
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
                    vl.addWidget(item)
                    if s.cover_id:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(s.cover_id), item)
                self.results_layout.addWidget(sc)

            self.results_widget.setUpdatesEnabled(True)

        self.main_window.run_async(fetch, on_ready, page_bound=True)


