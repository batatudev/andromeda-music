import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import random

from config import THEME
from utils import MediaItem
from core.enums import MediaType
from ui.widgets import FlowLayout, DragDropContainer
from ui.components import SongItem, MediaCard, MediaHeader

from views.library_base import LibraryScrollArea

class DetailsView(LibraryScrollArea):
    def __init__(self, main_window):
        super().__init__(main_window)

        self.content_widget.deleteLater()
        self.content_widget = DragDropContainer()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_widget.drop_occurred.connect(self._handle_playlist_drop)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(15)
        self.setWidget(self.content_widget)

        self.current_playlist_id = None
        self.current_playlist_name = ""
        self.current_playlist_songs = []
        self.current_id = None
        self.current_type = None

    def load(self, d, t, force=False):
        if not d:
            return

        target_id = d.get('id') if isinstance(d, dict) else getattr(d, 'item_id', None)
        if not force and target_id and target_id == self.current_id and t == self.current_type:
            return

        self.current_id = target_id
        self.current_type = t

        self.content_widget.setUpdatesEnabled(False)
        self._clear()
        loading = QLabel("Wczytywanie...")
        loading.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(loading)
        self.content_layout.addStretch()
        self.content_widget.setUpdatesEnabled(True)

        def fetch():
            if t == MediaType.ALBUM:
                return (MediaType.ALBUM, self.main_window.repo.get_album(d.get('id')))
            elif t == MediaType.PLAYLIST:
                try:
                    params = self.main_window.client._get_auth_params()
                    params['id'] = d.get('id')
                    res = self.main_window.client._make_request("getPlaylist", params)
                    return (MediaType.PLAYLIST, res.get('playlist', {}))
                except Exception:
                    return (MediaType.PLAYLIST, {})
            else:
                art = self.main_window.repo.get_artist(d.get('id'))
                if not art: return None
                songs = self.main_window.repo.get_top_songs_for_artist(art.title)
                if len(songs) < 20:
                    ids = {s.item_id for s in songs}
                    for a in art.get('album',[]):
                        if len(songs) >= 100:
                            break
                        alb_data = self.main_window.repo.get_album(a.item_id)
                        if alb_data:
                            for ns in alb_data.get('song',[]):
                                if ns.item_id not in ids:
                                    songs.append(ns)
                                    ids.add(ns.item_id)
                random.shuffle(songs)
                return (MediaType.ARTIST, art, art.get('album',[]), songs)

        def on_ready(data):
            if not data:
                return

            self.content_widget.setUpdatesEnabled(False)
            self._clear()

            if data[0] == MediaType.PLAYLIST:
                pl = data[1]
                self.current_playlist_id = pl.get('id')
                self.current_playlist_name = pl.get('name', 'Unknown')

                songs = pl.get('entry',[])
                if not songs:
                    songs = pl.get('song',[])
                songs = [MediaItem(s) for s in songs]
                self.current_playlist_songs = list(songs)
                stats_text = f"{len(songs)} utworów"

                h = MediaHeader(pl.get('name', 'Unknown'), stats_text)
                h.play_clicked.connect(lambda: self.main_window.engine.play_list(songs, 0))

                cid = pl.get('coverArt')
                if not cid and songs:
                    cid = songs[0].cover_id

                if cid:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(cid), h)

                self.content_layout.addWidget(h)

                for i, s in enumerate(songs):
                    item = SongItem(s, is_playlist=True, playlist_index=i)
                    item.clicked.connect(lambda song, idx=i, sl=songs: self.main_window.engine.play_list(sl, idx))
                    item.fav_clicked.connect(self.main_window._handle_song_fav)
                    item.add_to_queue_clicked.connect(self.main_window.engine.add_to_queue)
                    item.remove_from_playlist_clicked.connect(lambda s_d, idx=i: self._remove_from_playlist(s_d, idx))
                    item.artist_clicked.connect(self.main_window._show_details)
                    item.album_clicked.connect(self.main_window._show_details)
                    item.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                    item.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                    item.save_image_clicked.connect(self.main_window._save_image_to_file)
                    self.content_layout.addWidget(item)
                    item_cid = s.cover_id or cid
                    if item_cid:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(item_cid), item)

            elif data[0] == MediaType.ALBUM:
                alb = data[1]
                songs = alb.get('song',[])
                art_name = alb.artist
                year = alb.get('year')
                yr_str = f"  •  {year}" if year else ""
                stats_text = f"{art_name}  •  {len(songs)} utworów{yr_str}"

                h = MediaHeader(alb.title, stats_text)
                h.play_clicked.connect(lambda: self.main_window.engine.play_list(songs, 0))

                cid = alb.cover_id
                if not cid and songs:
                    cid = songs[0].cover_id

                if cid:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(cid), h)

                self.content_layout.addWidget(h)

                for i, s in enumerate(songs):
                    track_num = s.get('track', i + 1)
                    item = SongItem(s, track_number=track_num)
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
                    item_cid = s.cover_id or cid
                    if item_cid:
                        self.main_window.loader.load(self.main_window.client.get_cover_art_url(item_cid), item)
            else:
                _, art, albs, songs = data
                h = MediaHeader(art.title, f"{len(albs)} albumów  •  {len(songs)} utworów")
                h.play_clicked.connect(lambda: self.main_window.engine.play_list(songs, 0))
                if art.cover_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(art.cover_id), h)
                self.content_layout.addWidget(h)

                if albs:
                    hl = QHBoxLayout()
                    hl.addWidget(QLabel("Albumy", font=QFont("Sans", 24, QFont.Bold)))
                    hl.addStretch()
                    btn_toggle_a = QPushButton("Więcej")
                    btn_toggle_a.setStyleSheet(f"background:transparent; color:{THEME['accent']}; font-weight:bold;")
                    btn_toggle_a.setCursor(Qt.PointingHandCursor)
                    if len(albs) > 6:
                        hl.addWidget(btn_toggle_a)
                    self.content_layout.addLayout(hl)

                    gc = QWidget()
                    ga = FlowLayout(gc, spacing=25)
                    ga.setContentsMargins(0, 0, 0, 0)

                    def build_a(show_all):
                        self.content_widget.setUpdatesEnabled(False)
                        self._clear_layout(ga)
                        limit = len(albs) if show_all else 6
                        for i, a in enumerate(albs[:limit]):
                            c = MediaCard(a, MediaType.ALBUM)
                            c.clicked.connect(self.main_window._show_details)
                            c.play_clicked.connect(lambda d, t: self.main_window.engine.play_list(self.main_window.repo.get_album(d.item_id).get('song',[]), 0))
                            c.add_to_queue_clicked.connect(self.main_window._handle_add_to_queue)
                            c.download_videos_clicked.connect(self.main_window._handle_download_videos)
                            c.artist_clicked.connect(self.main_window._show_details)
                            c.set_custom_cover_clicked.connect(self.main_window._set_custom_album_cover)
                            c.reset_custom_cover_clicked.connect(self.main_window._reset_custom_album_cover)
                            c.save_image_clicked.connect(self.main_window._save_image_to_file)
                            ga.addWidget(c)
                            if a.cover_id:
                                self.main_window.loader.load(self.main_window.client.get_cover_art_url(a.cover_id), c)
                        self.content_widget.setUpdatesEnabled(True)

                    btn_toggle_a.clicked.connect(lambda: (btn_toggle_a.setText("Mniej" if btn_toggle_a.text() == "Więcej" else "Więcej"), build_a(btn_toggle_a.text() == "Mniej")))
                    build_a(False)
                    self.content_layout.addWidget(gc)

                if songs:
                    hls = QHBoxLayout()
                    hls.addWidget(QLabel("Utwory", font=QFont("Sans", 24, QFont.Bold)))
                    hls.addStretch()
                    btn_more_s = QPushButton("Więcej")
                    btn_more_s.setStyleSheet(f"background:transparent; color:{THEME['accent']}; font-weight:bold; margin-top:40px;")
                    btn_more_s.setCursor(Qt.PointingHandCursor)
                    if len(songs) > 10:
                        hls.addWidget(btn_more_s)
                    self.content_layout.addLayout(hls)

                    sc = QWidget()
                    vl = QVBoxLayout(sc)
                    vl.setContentsMargins(0, 0, 0, 0)
                    vl.setSpacing(5)

                    def build_s(show_all):
                        self.content_widget.setUpdatesEnabled(False)
                        self._clear_layout(vl)
                        limit = len(songs) if show_all else 10
                        for i, s in enumerate(songs[:limit]):
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
                        self.content_widget.setUpdatesEnabled(True)

                    btn_more_s.clicked.connect(lambda: (btn_more_s.setText("Mniej" if btn_more_s.text() == "Więcej" else "Więcej"), build_s(btn_more_s.text() == "Mniej")))
                    build_s(False)
                    self.content_layout.addWidget(sc)
            self.content_layout.addStretch()
            self.content_widget.setUpdatesEnabled(True)

        self.main_window.run_async(fetch, on_ready, page_bound=True)

    def _remove_from_playlist(self, song, idx):
        if not self.current_playlist_id:
            return
        def on_ready(res):
            self.load({"id": self.current_playlist_id, "name": self.current_playlist_name}, MediaType.PLAYLIST)
        self.main_window.run_async(lambda: self.main_window.client.update_playlist(self.current_playlist_id, song_index_to_remove=idx), on_ready)

    def _handle_playlist_drop(self, old_idx, drop_y):
        if not self.current_playlist_id or not self.current_playlist_songs:
            return

        layout = self.content_layout
        song_widgets =[]
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), SongItem):
                song_widgets.append(item.widget())

        target_pl_idx = len(song_widgets)
        for i, w in enumerate(song_widgets):
            if drop_y < w.geometry().center().y():
                target_pl_idx = i
                break

        if old_idx == target_pl_idx or old_idx == target_pl_idx - 1:
            return

        song = self.current_playlist_songs.pop(old_idx)
        if old_idx < target_pl_idx:
            target_pl_idx -= 1
        self.current_playlist_songs.insert(target_pl_idx, song)

        song_ids =[s.item_id for s in self.current_playlist_songs]
        def on_ready(res):
            self.load({"id": self.current_playlist_id, "name": self.current_playlist_name}, MediaType.PLAYLIST)
        self.main_window.run_async(lambda: self.main_window.client.replace_playlist(self.current_playlist_id, song_ids), on_ready)