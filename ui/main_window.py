# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: ui/main_window.py
# OPIS ZMIAN: Dodanie logiki pobierania masowego teledysków (szacowanie rozmiaru, okna dialogowe).

import os
os.environ["QT_API"] = "pyside6"

import sys
import time
import shutil
import requests
import random

import qtawesome as qta

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QScrollArea, QDialog, QLineEdit, QFrame, QPushButton,
    QGraphicsOpacityEffect, QMenu, QFileDialog, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QThreadPool, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint
from PySide6.QtGui import QAction
from PySide6.QtMultimedia import QMediaPlayer

from api_client import NavidromeClient
from config import APP_CONFIG, APP_NAME, save_config, THEME, get_app_style, Pages
from utils import Worker, AsyncImageLoader, logger, telemetry_recorder, NetworkMonitor
from core.enums import EngineState, TelemetryEvent, MediaType

from ui.widgets import DragDropContainer, HoverIconButton, SmoothScrollArea
from ui.components import SongItem, QueueHeader
from views.view_now_playing import NowPlayingWidget
from views.view_sidebar import SidebarWidget
from views.view_player_bar import PlayerBarWidget

from engine.player_engine import PlayerEngine
from engine.watchdog import WatchdogService
from core.telemetry_service import TelemetryService

from views.view_settings import SettingsView
from views.view_dev import DevModeView
from views.view_home import HomeView
from views.view_search import SearchView
from views.view_albums import AlbumsView
from views.view_tracks import TracksView
from views.view_artists import ArtistsView
from views.view_favs import FavsView
from views.view_details import DetailsView
from views.view_downloads import DownloadsView

try:
    from mpris_adapter import MprisService
    HAS_MPRIS_MODULE = True
except ImportError:
    HAS_MPRIS_MODULE = False


class MainWindow(QMainWindow):
    async_signal = Signal(object, object, object)
    fav_updated = Signal(str, bool)
    offline_status_changed = Signal(str, str)  # item_id, status - broadcast do SongItem

    def __init__(self, client):
        super().__init__()
        logger.start_session("14.6+")
        telemetry_recorder.start_session("14.6+")

        self.client = client
        self.loader = AsyncImageLoader(self)
        self.engine = PlayerEngine(self.client)

        self.network_monitor = NetworkMonitor(APP_CONFIG.get("url", "http://localhost"))
        self.network_monitor.start()

        if HAS_MPRIS_MODULE:
            self.mpris = MprisService(self.engine)

        self.threadpool = QThreadPool()
        self.async_signal.connect(self._handle_async)
        self.fav_updated.connect(self._on_fav_updated)

        self._queue_update_timer = QTimer(self)
        self._queue_update_timer.setSingleShot(True)
        self._queue_update_timer.setInterval(50)
        self._queue_update_timer.timeout.connect(self._actual_queue_updated)

        self.engine.track_changed.connect(self._on_track_changed)
        self.engine.state_changed.connect(self._on_state_changed)
        self.engine.position_changed.connect(self._on_position_changed)
        self.engine.duration_changed.connect(self._on_duration_changed)
        self.engine.queue_updated.connect(self._on_queue_updated)
        self.engine.queue_cleared.connect(self._on_queue_cleared)
        self.engine.video_ready_to_show.connect(self._show_video_layer)
        self.engine.loading_changed.connect(self._on_loading_changed)

        # Broadcast statusu pobierania do wszystkich aktywnych SongItem
        self.engine.video_download_manager.download_status_changed.connect(
            lambda item_id, status: self.offline_status_changed.emit(item_id, status)
        )

        self.engine.loop_mode_changed.connect(self._on_loop_mode_changed)
        self.engine.shuffle_mode_changed.connect(self._on_shuffle_mode_changed)

        self._is_fetching = False
        self.current_page_task_id = 0

        # Odpalenie w tle synchronizacji pobrań po starcie (z opóźnieniem)
        QTimer.singleShot(5000, self._sync_auto_downloads)
        self.sidebar_collapsed = False
        self.manual_sidebar_override = False
        self._seek_grace_until = 0
        self._frames_with_movement = 0
        self._zero_fps_cycles = 0
        self._current_mask_state = False

        self.force_telemetry_event = None

        self.all_artists_data = []
        self.history = []
        self.current_route = None

        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)
        self.setMinimumSize(1024, 720)
        self.setStyleSheet(get_app_style())
        self._init_ui()

        self.engine.has_video_signal.connect(self._on_has_video)

        self.now_playing_view.btn_q_shuffle.clicked.connect(self._shuffle_queue)
        self.now_playing_view.btn_q_clear.clicked.connect(self.engine.clear_queue)
        self.now_playing_view.artist_lbl.clicked.connect(self._now_playing_artist_clicked)

        self.watchdog = WatchdogService(self)
        self.telemetry = TelemetryService(self)

        QTimer.singleShot(200, self._start_app)

    def resizeEvent(self, event):
        if not getattr(self, 'manual_sidebar_override', False):
            if self.width() < 1050 and not self.sidebar_collapsed:
                self._toggle_sidebar(manual=False)
            elif self.width() >= 1050 and self.sidebar_collapsed:
                self._toggle_sidebar(manual=False)
        super().resizeEvent(event)

    def closeEvent(self, event):
        save_config()
        logger.flush()
        telemetry_recorder.flush()
        self.watchdog.stop()
        self.telemetry.stop()
        if hasattr(self, 'network_monitor'):
            self.network_monitor.stop()
            self.network_monitor.join(timeout=1.0)
        super().closeEvent(event)

    def _start_app(self):
        self.history = []
        self.current_route = None
        self._load_playlists()
        self._navigate(Pages.HOME)

    def _sync_auto_downloads(self):
        """Uruchamia się w tle, pobiera z Navidrome ulubione/playlisty i dodaje brakujące do kolejki."""
        def fetch():
            songs_to_dl = []
            if APP_CONFIG.get("video_auto_dl_favs", False):
                songs_to_dl.extend(self.client.get_starred(1000))
                
            pl_ids = APP_CONFIG.get("video_auto_dl_playlists", [])
            for pid in pl_ids:
                try:
                    params = self.client._get_auth_params()
                    params["id"] = pid
                    res = self.client._make_request("getPlaylist", params)
                    pl_data = res.get("playlist", {})
                    entry = pl_data.get("entry", [])
                    from utils import MediaItem
                    songs_to_dl.extend([MediaItem(s) for s in entry])
                except Exception as e:
                    logger.error(f"Auto-sync playlist {pid} failed: {e}")
                    
            return songs_to_dl
            
        def on_ready(songs):
            if not songs: return
            valid_songs = [s for s in songs if getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)]
            items_to_add = []
            for s in valid_songs:
                link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
                if link:
                    items_to_add.append((s.item_id, link, s.title, s.cover_id))
            
            if items_to_add:
                self.engine.video_download_manager.add_to_queue_bulk(items_to_add, high_priority=False)
                    
        self.run_async(fetch, on_ready, page_bound=False)

    def _handle_song_fav(self, song, new_state):
        song_id = song.item_id
        if not song_id:
            return
        self.run_async(lambda: self.client.star_track(song_id, new_state))
        self.fav_updated.emit(song_id, new_state)

        if new_state and APP_CONFIG.get("video_auto_dl_favs", False):
            link = getattr(song, 'yt_link', None) or getattr(song, 'youtube_url', None)
            if link:
                self.engine.video_download_manager.add_to_queue(song.item_id, link, song.title, high_priority=False, cover_id=song.cover_id)

    def _on_fav_updated(self, song_id, is_fav):
        for q_song in self.engine.queue:
            if q_song.item_id == song_id:
                q_song.set_starred(is_fav)

        if 0 <= self.engine.idx < len(self.engine.queue):
            current_song = self.engine.queue[self.engine.idx]
            if current_song.item_id == song_id:
                self.player_bar.pb_fav_btn.set_default_color(THEME["accent"] if is_fav else THEME["heart_inactive"])
                self.player_bar.pb_fav_btn.update_icon('fa5s.heart' if is_fav else 'fa5.heart')

        for page in self.pages:
            if page is None:
                continue
            if isinstance(page, QScrollArea) and page.widget():
                layout = page.widget().layout()
                if layout:
                    self._update_song_items_fav(layout, song_id, is_fav)
            elif isinstance(page, NowPlayingWidget):
                if hasattr(page, 'ui_container') and page.ui_container.layout():
                    self._update_song_items_fav(page.ui_container.layout(), song_id, is_fav)
            elif hasattr(page, 'layout') and page.layout():
                self._update_song_items_fav(page.layout(), song_id, is_fav)

    def _update_song_items_fav(self, layout, song_id, is_fav):
        if not layout:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                w = item.widget()
                if isinstance(w, SongItem):
                    if w.song.item_id == song_id:
                        w.update_fav_state(is_fav)
                else:
                    if isinstance(w, QScrollArea) and w.widget() and w.widget().layout():
                        self._update_song_items_fav(w.widget().layout(), song_id, is_fav)
                    elif w.layout():
                        self._update_song_items_fav(w.layout(), song_id, is_fav)
            elif item.layout():
                self._update_song_items_fav(item.layout(), song_id, is_fav)

    def _handle_async(self, callback, result, task_id):
        if task_id is not None and task_id != self.current_page_task_id:
            return
        if callback:
            try:
                callback(result)
            except Exception as e:
                logger.log(f"Async UI Callback Error: {e}")
        self._is_fetching = False
        self.sidebar.setCursor(Qt.ArrowCursor)

    def run_async(self, task_func, callback_func=None, page_bound=False):
        if page_bound:
            self._is_fetching = True
            self.sidebar.setCursor(Qt.WaitCursor)
        task_id = self.current_page_task_id if page_bound else None
        def worker_logic():
            try:
                res = task_func()
                self.async_signal.emit(callback_func, res, task_id)
            except Exception as e:
                logger.log(f"Async Worker Error: {e}")
                self.async_signal.emit(callback_func, None, task_id)
        self.threadpool.start(Worker(worker_logic))

    def _manual_toggle_sidebar(self):
        self._toggle_sidebar(manual=True)

    def _toggle_sidebar(self, manual=False):
        if manual:
            self.manual_sidebar_override = True
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.sidebar.set_collapsed(self.sidebar_collapsed)

    def _update_sidebar_active_state(self):
        active_idx = None
        active_type = None
        active_data = None
        if self.current_route:
            active_idx = self.current_route.get("page")
            active_type = self.current_route.get("type")
            active_data = self.current_route.get("data")

        active_playlist_id = None
        if active_idx == Pages.DETAILS and active_type == MediaType.PLAYLIST and active_data:
            active_playlist_id = active_data.get('id')

        self.sidebar.update_active_state(active_idx, active_playlist_id)

        if active_idx == Pages.QUEUE:
            self.player_bar.btn_q.set_default_color(THEME["accent"])
        else:
            self.player_bar.btn_q.set_default_color(THEME["text_muted"])

    def _init_ui(self):
        main = QWidget()
        self.setCentralWidget(main)
        root = QVBoxLayout(main)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QHBoxLayout()
        content.setSpacing(0)

        self.sidebar = SidebarWidget(dev_mode=APP_CONFIG.get("dev_mode", False))
        self.sidebar.page_requested.connect(self._switch_page)
        self.sidebar.back_requested.connect(self._go_back)
        self.sidebar.refresh_requested.connect(self._refresh_current)
        self.sidebar.toggle_sidebar_requested.connect(self._manual_toggle_sidebar)
        self.sidebar.playlist_requested.connect(lambda pid, pname: self._show_details({"id": pid, "name": pname}, MediaType.PLAYLIST))
        self.sidebar.settings_requested.connect(self._toggle_settings)
        self.sidebar.dev_requested.connect(lambda: self._switch_page(Pages.DEV_MODE))

        self.stack = QStackedWidget()
        self.pages = [None] * len(Pages)

        for page_id in Pages:
            if page_id == Pages.NOW_PLAYING:
                self.now_playing_view = NowPlayingWidget()
                self.now_playing_view.queue_content.drop_occurred.connect(self._handle_now_playing_queue_drop)
                self.pages[page_id] = self.now_playing_view
                self.stack.addWidget(self.now_playing_view)
            elif page_id == Pages.SETTINGS:
                self.settings_view = SettingsView(self)
                s = SmoothScrollArea()
                s.setWidgetResizable(True)
                s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                s.setStyleSheet("background: transparent; border: none;")
                s.setWidget(self.settings_view)
                self.pages[page_id] = s
                self.stack.addWidget(s)
            elif page_id == Pages.DEV_MODE:
                self.dev_view = DevModeView(self)
                s = SmoothScrollArea()
                s.setWidgetResizable(True)
                s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                s.setStyleSheet("background: transparent; border: none;")
                s.setWidget(self.dev_view)
                self.pages[page_id] = s
                self.stack.addWidget(s)
            elif page_id == Pages.DOWNLOADS:
                self.downloads_view = DownloadsView(self)
                s = SmoothScrollArea()
                s.setWidgetResizable(True)
                s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                s.setStyleSheet("background: transparent; border: none;")
                s.setWidget(self.downloads_view)
                self.pages[page_id] = s
                self.stack.addWidget(s)
            elif page_id == Pages.HOME:
                self.pages[page_id] = HomeView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.SEARCH:
                self.pages[page_id] = SearchView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.ALBUMS:
                self.pages[page_id] = AlbumsView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.TRACKS:
                self.pages[page_id] = TracksView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.ARTISTS:
                self.pages[page_id] = ArtistsView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.FAVS:
                self.pages[page_id] = FavsView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.DETAILS:
                self.pages[page_id] = DetailsView(self)
                self.stack.addWidget(self.pages[page_id])
            elif page_id == Pages.QUEUE:
                s = SmoothScrollArea()
                s.setWidgetResizable(True)
                s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                w = DragDropContainer()
                w.drop_occurred.connect(self._handle_queue_drop)
                l = QVBoxLayout(w)
                l.setContentsMargins(30, 30, 30, 30)
                l.setSpacing(15)
                s.setWidget(w)
                self.pages[page_id] = s
                self.stack.addWidget(s)

        self.engine.video_player.setVideoOutput(self.now_playing_view.video_widget.video_item)
        content.addWidget(self.sidebar)
        content.addWidget(self.stack)
        root.addLayout(content)

        self.player_bar = PlayerBarWidget(initial_volume=APP_CONFIG["volume"])
        self.player_bar.clicked.connect(self._toggle_now_playing)
        self.player_bar.play_pause_requested.connect(self.engine.play_pause)
        self.player_bar.next_requested.connect(self.engine.next_song)
        self.player_bar.prev_requested.connect(self.engine.prev_song)
        self.player_bar.skip_f_requested.connect(self.engine.skip_forward)
        self.player_bar.skip_b_requested.connect(self.engine.skip_backward)
        self.player_bar.loop_requested.connect(self.engine.toggle_loop)
        self.player_bar.shuffle_requested.connect(self.engine.toggle_shuffle)
        self.player_bar.video_toggle_requested.connect(self._toggle_video_mode)
        self.player_bar.mute_requested.connect(self._toggle_mute)
        self.player_bar.queue_requested.connect(self._toggle_queue)
        self.player_bar.volume_changed.connect(self.engine.set_volume)
        self.player_bar.seek_requested.connect(self._handle_seek)
        self.player_bar.seek_started.connect(self._on_seek_started)
        self.player_bar.fav_toggled.connect(self._toggle_pb_fav)
        self.player_bar.title_clicked.connect(self._pb_title_clicked)
        self.player_bar.artist_clicked.connect(self._pb_artist_clicked)
        self.player_bar.album_clicked.connect(self._pb_album_clicked)

        root.addWidget(self.player_bar)

    def _handle_seek(self, pos):
        ping = getattr(self.network_monitor, 'net_ping', 50)
        if ping < 0:
            ping = 500
        grace_add = min(ping / 100.0, 5.0)
        self._seek_grace_until = time.time() + 3.0 + grace_add
        self.engine.set_position(pos)

    def _on_seek_started(self):
        self.force_telemetry_event = TelemetryEvent.SEEK_REQ
        if self.player_bar.btn_video_toggle.isChecked() and self.engine.current_yt_link:
            self._current_mask_state = True
            self.now_playing_view.set_seek_blur(True)

    def _navigate(self, page_idx, data=None, type_str=None, is_back=False):
        if self._is_fetching:
            return

        if self.stack.currentIndex() == Pages.SETTINGS and page_idx != Pages.SETTINGS:
            self.settings_view.revert_changes()

        if page_idx == Pages.SETTINGS and self.stack.currentIndex() != Pages.SETTINGS:
            self.settings_view.build_ui()

        if not is_back and self.current_route:
            if self.current_route.get("page") != page_idx or self.current_route.get("data") != data:
                self.history.append(self.current_route)
                if len(self.history) > 50:
                    self.history.pop(0)

        self.current_page_task_id += 1
        self.current_route = {"page": page_idx, "data": data, "type": type_str}

        if hasattr(self, 'anim_group') and self.anim_group.state() == QParallelAnimationGroup.State.Running:
            self.anim_group.stop()
            if hasattr(self, 'current_anim_page') and self.current_anim_page:
                self.current_anim_page.setGraphicsEffect(None)
                self.current_anim_page.move(0, 0)

        self.stack.setCurrentIndex(page_idx)
        self.current_anim_page = self.stack.currentWidget()

        self.page_effect = QGraphicsOpacityEffect(self.current_anim_page)
        self.current_anim_page.setGraphicsEffect(self.page_effect)

        self.fade_anim = QPropertyAnimation(self.page_effect, b"opacity")
        self.fade_anim.setDuration(400)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.pos_anim = QPropertyAnimation(self.current_anim_page, b"pos")
        self.pos_anim.setDuration(400)
        self.pos_anim.setStartValue(QPoint(0, 30))
        self.pos_anim.setEndValue(QPoint(0, 0))
        self.pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.fade_anim)
        self.anim_group.addAnimation(self.pos_anim)

        def on_fade_finished():
            if hasattr(self, 'current_anim_page') and self.current_anim_page:
                self.current_anim_page.setGraphicsEffect(None)

        self.anim_group.finished.connect(on_fade_finished)
        self.page_effect.setOpacity(0.0)
        self.anim_group.start()

        self._update_sidebar_active_state()

        if page_idx == Pages.DETAILS:
            self.pages[Pages.DETAILS].load(data, type_str)
        elif page_idx == Pages.QUEUE:
            self._nav_queue()
        elif page_idx in [Pages.HOME, Pages.FAVS, Pages.ALBUMS, Pages.TRACKS, Pages.ARTISTS, Pages.SEARCH, Pages.DOWNLOADS]:
            if not is_back:
                self.pages[page_idx].load()

    def _go_back(self):
        if self._is_fetching:
            return
        if not getattr(self, 'history', []):
            return
        prev = self.history.pop()
        self._navigate(prev["page"], prev.get("data"), prev.get("type"), is_back=True)

    def _switch_page(self, idx):
        self._navigate(idx)

    def _show_details(self, d, t):
        self._navigate(Pages.DETAILS, data=d, type_str=t)

    def _toggle_queue(self):
        if self.stack.currentIndex() == Pages.QUEUE:
            self._go_back()
        else:
            self._navigate(Pages.QUEUE)

    def _toggle_settings(self):
        if self.stack.currentIndex() == Pages.SETTINGS:
            self._go_back()
        else:
            self._navigate(Pages.SETTINGS)

    def _toggle_now_playing(self):
        if self.stack.currentIndex() == Pages.NOW_PLAYING:
            self._go_back()
        else:
            self._navigate(Pages.NOW_PLAYING)

    def _refresh_current(self):
        if not self._is_fetching and getattr(self, 'current_route', None):
            self.current_page_task_id += 1
            idx = self.current_route["page"]
            if idx == Pages.DETAILS:
                self.pages[idx].load(self.current_route["data"], self.current_route["type"])
            elif idx == Pages.QUEUE:
                self._nav_queue()
            elif idx in [Pages.HOME, Pages.FAVS, Pages.ALBUMS, Pages.TRACKS, Pages.ARTISTS, Pages.SEARCH, Pages.DOWNLOADS]:
                self.pages[idx].load()

    def _handle_add_to_queue(self, data, type_str):
        if self._is_fetching:
            return
        def fetch():
            if type_str == MediaType.ALBUM:
                return self.client.get_album(data.item_id).get('song', [])
            elif type_str == MediaType.ARTIST:
                return self.client.get_top_songs_for_artist(data.title)
            return []
        def on_ready(songs):
            if songs:
                for s in songs:
                    self.engine.add_to_queue(s)
        self.run_async(fetch, on_ready, page_bound=False)

    def _handle_download_videos(self, data, type_str):
        if type_str == MediaType.ALBUM:
            self.start_bulk_download("album", data.item_id, data.title)
        elif type_str == MediaType.ARTIST:
            self.start_bulk_download("artist", data.title, data.title)

    def start_bulk_download(self, bulk_type, target_id=None, target_name=None):
        if self._is_fetching:
            return

        def fetch():
            songs = []
            if bulk_type == "favorites":
                songs = self.client.get_starred(1000) # Pobierz max 1000 ulubionych
            elif bulk_type == "playlist":
                params = self.client._get_auth_params()
                params["id"] = target_id
                res = self.client._make_request("getPlaylist", params)
                entry = res.get("playlist", {}).get("entry", [])
                from utils import MediaItem
                songs = [MediaItem(s) for s in entry]
                print("PLAYLIST FETCH:", target_id, res)
            elif bulk_type == "album":
                songs = self.client.get_album(target_id).get('song', [])
            elif bulk_type == "artist":
                songs = self.client.get_top_songs_for_artist(target_id, limit=500)
            elif bulk_type == "all":
                # Dla całej bazy - losowe 1000 utworów (lub search).
                # UWAGA: Prawdziwe "wszystko" może zabić serwer. Pobieramy 1000 ostatnich/najczęstszych.
                songs = self.client.get_random_songs(1000)
            return songs

        def on_ready(songs):
            if not songs:
                QMessageBox.information(self, "Brak utworów", "Nie znaleziono utworów do pobrania.")
                return
            
            # Filtrowanie utworów z yt_link
            valid_songs = [s for s in songs if getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)]
            
            if not valid_songs:
                QMessageBox.information(self, "Brak linków", "Znalezione utwory nie posiadają linków do wideo.")
                return

            quality = APP_CONFIG.get("video_offline_quality", "1080p")
            # Szacowanie wg jakości
            avg_mb = 25 # 1080p
            if quality == "720p": avg_mb = 15
            elif quality == "480p": avg_mb = 10
            
            count = len(valid_songs)
            est_mb = count * avg_mb
            est_str = f"{est_mb / 1024:.2f} GB" if est_mb > 1024 else f"{est_mb} MB"
            
            msg = f"Znaleziono {count} utworów z teledyskami.\nSzacowany rozmiar do pobrania: ~{est_str} (Jakość: {quality}).\n\nCzy chcesz rozpocząć pobieranie?"
            ans = QMessageBox.question(self, "Potwierdzenie pobierania", msg, QMessageBox.Yes | QMessageBox.No)
            
            if ans == QMessageBox.Yes:
                items_to_add = []
                for s in valid_songs:
                    link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
                    if link:
                        items_to_add.append((s.item_id, link, s.title, s.cover_id))
                
                if items_to_add:
                    self.engine.video_download_manager.add_to_queue_bulk(items_to_add, high_priority=False)
                QMessageBox.information(self, "Rozpoczęto", f"Zadania ({len(items_to_add)}) zostały dodane do kolejki pobierania.")

        self.run_async(fetch, on_ready, page_bound=False)

    def _pb_title_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('albumId'):
                self._show_details({"id": song.get('albumId'), "name": song.album}, MediaType.ALBUM)

    def _pb_artist_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('artistId'):
                self._show_details({"id": song.get('artistId'), "name": song.artist}, MediaType.ARTIST)

    def _pb_album_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('albumId'):
                self._show_details({"id": song.get('albumId'), "name": song.album}, MediaType.ALBUM)

    def _toggle_pb_fav(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            new_state = not song.is_starred
            song_id = song.item_id
            self.run_async(lambda: self.client.star_track(song_id, new_state))
            self.fav_updated.emit(song_id, new_state)

    def _now_playing_artist_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('artistId'):
                self._go_back()
                self._show_details({"id": song.get('artistId'), "name": song.artist}, MediaType.ARTIST)

    def _show_video_layer(self):
        # Pokaż wideo jeśli: (1) tryb teledysku aktywny przez użytkownika,
        # LUB (2) auto-play włączony i istnieje plik offline dla aktualnego utworu
        should_show = self.player_bar.btn_video_toggle.isChecked()
        if not should_show and APP_CONFIG.get("video_smart_auto_play", False):
            if self.engine.queue and self.engine.idx >= 0:
                song = self.engine.queue[self.engine.idx]
                if self.engine.video_download_manager.get_video_path(song.item_id):
                    should_show = True
        if should_show:
            self.now_playing_view.transition_to_video()

    def _on_loading_changed(self, is_loading):
        self.player_bar.set_loading_state(is_loading)

    def _on_has_video(self, has_video):
        self.player_bar.set_video_available(has_video)

        # Sprawdz czy jest plik offline (nawet gdy has_video=False bo brak yt_link)
        if self.engine.queue and self.engine.idx >= 0:
            song = self.engine.queue[self.engine.idx]
            offline_path = self.engine.video_download_manager.get_video_path(song.item_id)

            if offline_path:
                if not has_video:
                    # Informuj pasek że wideo jest lokalnie dostępne
                    self.player_bar.set_video_available(True)

                if APP_CONFIG.get("video_smart_auto_play", False):
                    # Auto-play WŁĄCZONE: graj wideo NIEZALEŻNIE od stanu przycisku.
                    # Nie zmieniamy stanu przycisku - to narzędzie użytkownika.
                    self.engine.load_and_play_video()
                    return
                else:
                    # Auto-play WYŁĄCZONE: graj tylko gdy przycisk użytkownika jest aktywny
                    if self.player_bar.btn_video_toggle.isChecked():
                        self.player_bar.set_video_active(True)
                        self.engine.load_and_play_video()
                        return
                    # Przycisk nieaktywny - nic nie robimy, czekamy na akcję użytkownika
                    return

        # Standardowa ścieżka streamingu (brak pliku offline)
        is_video = self.player_bar.btn_video_toggle.isChecked()
        if is_video:
            if has_video:
                def on_fade_done():
                    self.player_bar.set_video_active(True)
                    self.engine.load_and_play_video()
                self.now_playing_view.transition_to_audio(on_fade_done)
            else:
                self.player_bar.set_video_active(False)
                self.now_playing_view.set_media_mode("audio")
                self.engine.video_player.stop()
        else:
            self.player_bar.set_video_active(False)
            self.now_playing_view.set_media_mode("audio")
            self.engine.video_player.stop()


    def _toggle_video_mode(self):
        is_video = self.player_bar.btn_video_toggle.isChecked()
        self.player_bar.set_video_active(is_video)
        if is_video:
            # Najpierw sprawdz czy jest plik offline
            if self.engine.queue and self.engine.idx >= 0:
                song = self.engine.queue[self.engine.idx]
                offline_path = self.engine.video_download_manager.get_video_path(song.item_id)
                if offline_path:
                    self.engine.load_and_play_video(force_mid_track=True)
                    return
            # Brak pliku offline - użyj streamingu na żywo
            if self.engine.current_yt_link:
                self.engine.load_and_play_video(force_mid_track=True)
            else:
                self.now_playing_view.set_media_mode("audio")
        else:
            self._current_mask_state = False
            self.now_playing_view.set_buffering_state(False)
            self.now_playing_view.set_media_mode("audio")
            self.engine.video_player.stop()

    def _toggle_mute(self):
        is_muted = self.engine.audio_output.isMuted()
        self.engine.audio_output.setMuted(not is_muted)
        self.player_bar.set_mute_state(not is_muted)

    def _refresh_player_bar_if_needed(self, target_album_id, target_cover_id):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            s_album_id = song.get('albumId')
            s_cover_id = song.cover_id

            if (target_album_id and s_album_id == target_album_id) or (target_cover_id and s_cover_id == target_cover_id):
                cid = s_cover_id
                if cid:
                    self.loader.load(self.client.get_cover_art_url(cid), self.player_bar.pb_img)
                    self.loader.load(self.client.get_cover_art_url(cid), self.now_playing_view)

    def _set_custom_artist_image(self, data, type_str):
        if type_str != MediaType.ARTIST:
            return

        artist_id = data.item_id
        cover_id = data.cover_id

        if not artist_id and not cover_id:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz zdjęcie artysty", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            target_dir = self.loader.custom_artists_dir

            for cid in [artist_id, cover_id]:
                if not cid:
                    continue
                for old_ext in ['.jpg', '.jpeg', '.png']:
                    old_file = os.path.join(target_dir, f"{cid}{old_ext}")
                    if os.path.exists(old_file):
                        try:
                            os.remove(old_file)
                        except Exception:
                            pass

            try:
                if cover_id:
                    shutil.copy2(file_path, os.path.join(target_dir, f"{cover_id}{ext}"))
                if artist_id and artist_id != cover_id:
                    shutil.copy2(file_path, os.path.join(target_dir, f"{artist_id}{ext}"))

                self._refresh_current()
                logger.log(f"Ustawiono własne zdjęcie dla artysty {artist_id or cover_id}")
            except Exception as e:
                logger.log(f"Błąd kopiowania zdjęcia artysty: {e}")

    def _reset_custom_artist_image(self, data, type_str):
        if type_str != MediaType.ARTIST:
            return

        artist_id = data.item_id
        cover_id = data.cover_id

        target_dir = self.loader.custom_artists_dir
        deleted = False

        for cid in [artist_id, cover_id]:
            if not cid:
                continue
            for ext in ['.jpg', '.jpeg', '.png']:
                file_path = os.path.join(target_dir, f"{cid}{ext}")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted = True
                    except Exception:
                        pass

        if deleted:
            self._refresh_current()
            logger.log(f"Przywrócono domyślne zdjęcie dla artysty {artist_id or cover_id}")

    def _set_custom_album_cover(self, data, type_str):
        if type_str not in [MediaType.ALBUM, MediaType.SONG]:
            return

        album_id = data.get('albumId') if type_str == MediaType.SONG else data.item_id
        cover_id = data.cover_id

        if not album_id and not cover_id:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz okładkę", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            target_dir = self.loader.custom_covers_dir

            for cid in [album_id, cover_id]:
                if not cid:
                    continue
                for old_ext in ['.jpg', '.jpeg', '.png']:
                    old_file = os.path.join(target_dir, f"{cid}{old_ext}")
                    if os.path.exists(old_file):
                        try:
                            os.remove(old_file)
                        except Exception:
                            pass

            try:
                if cover_id:
                    shutil.copy2(file_path, os.path.join(target_dir, f"{cover_id}{ext}"))
                if album_id and album_id != cover_id:
                    shutil.copy2(file_path, os.path.join(target_dir, f"{album_id}{ext}"))

                self._refresh_current()
                self._refresh_player_bar_if_needed(album_id, cover_id)
                logger.log(f"Ustawiono własną okładkę dla {album_id or cover_id}")
            except Exception as e:
                logger.log(f"Błąd kopiowania okładki: {e}")

    def _reset_custom_album_cover(self, data, type_str):
        if type_str not in [MediaType.ALBUM, MediaType.SONG]:
            return

        album_id = data.get('albumId') if type_str == MediaType.SONG else data.item_id
        cover_id = data.cover_id

        target_dir = self.loader.custom_covers_dir
        deleted = False
        for cid in [album_id, cover_id]:
            if not cid:
                continue
            for ext in ['.jpg', '.jpeg', '.png']:
                file_path = os.path.join(target_dir, f"{cid}{ext}")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted = True
                    except Exception:
                        pass

        if deleted:
            self._refresh_current()
            self._refresh_player_bar_if_needed(album_id, cover_id)
            logger.log(f"Przywrócono domyślną okładkę dla {album_id or cover_id}")

    def _save_image_to_file(self, data, type_str):
        cover_id = data.cover_id
        if not cover_id:
            return

        default_name = f"{data.artist} - {data.title}.jpg"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz obrazek jako...", default_name, "Images (*.jpg)"
        )

        if file_path:
            size = 600 if type_str != MediaType.ARTIST else 1000
            url = self.client.get_cover_art_url(cover_id, size=size)

            def task():
                try:
                    res = requests.get(url, timeout=15)
                    res.raise_for_status()
                    with open(file_path, "wb") as f:
                        f.write(res.content)
                    return True
                except Exception as e:
                    logger.log(f"Błąd zapisu obrazka do pliku: {e}")
                    return False

            self.run_async(task, lambda success: logger.log("Zapisano grafikę do pliku.") if success else None)

    def _show_playlist_dialog(self, song):
        def fetch():
            params = self.client._get_auth_params()
            res = self.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            dlg = QDialog(self)
            dlg.setWindowTitle("Dodaj do playlisty")
            dlg.setFixedSize(320, 450)
            dlg.setStyleSheet(get_app_style())
            layout = QVBoxLayout(dlg)

            lbl_title = QLabel("Dodaj lub utwórz playlistę:")
            lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME['text_main']}; margin-bottom: 10px;")
            layout.addWidget(lbl_title)

            new_pl_layout = QHBoxLayout()
            inp_new_pl = QLineEdit()
            inp_new_pl.setPlaceholderText("Nowa playlista...")
            inp_new_pl.setStyleSheet(f"background: {THEME['bg_main']}; color: {THEME['text_main']}; padding: 8px; border: 1px solid {THEME['border']}; border-radius: 5px;")

            btn_new_pl = QPushButton("Utwórz")
            btn_new_pl.setCursor(Qt.PointingHandCursor)
            btn_new_pl.setStyleSheet(f"background: {THEME['accent']}; color: white; padding: 8px; border-radius: 5px; font-weight: bold;")

            def create_pl():
                name = inp_new_pl.text().strip()
                if name:
                    dlg.accept()
                    def task():
                        p = self.client._get_auth_params()
                        p['name'] = name
                        p['songId'] = [song.item_id]
                        self.client._make_request("createPlaylist", p)
                        
                        if APP_CONFIG.get("video_auto_dl_playlists", False):
                            link = getattr(song, 'yt_link', None) or getattr(song, 'youtube_url', None)
                            if link:
                                self.engine.video_download_manager.add_to_queue(song.item_id, link, song.title, high_priority=False, cover_id=song.cover_id)
                                
                    self.run_async(task, lambda r: self._load_playlists())

            btn_new_pl.clicked.connect(create_pl)
            new_pl_layout.addWidget(inp_new_pl)
            new_pl_layout.addWidget(btn_new_pl)
            layout.addLayout(new_pl_layout)

            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"background-color: {THEME['border']}; margin: 10px 0px;")
            layout.addWidget(line)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            content = QWidget()
            content.setStyleSheet("background: transparent;")
            v = QVBoxLayout(content)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(5)

            for pl in playlists:
                btn = QPushButton(pl.get('name'))
                btn.setStyleSheet(f"text-align: left; padding: 10px; border-radius: 5px; background: {THEME['bg_card']}; color: {THEME['text_main']}; border: none;")
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda ch, pid=pl.get('id'): select_pl(pid))
                v.addWidget(btn)

            v.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll)

            def select_pl(pid):
                dlg.accept()
                def task():
                    self.client.update_playlist(pid, song_id_to_add=song.item_id)
                    if APP_CONFIG.get("video_auto_dl_playlists", False):
                        link = getattr(song, 'yt_link', None) or getattr(song, 'youtube_url', None)
                        if link:
                            self.engine.video_download_manager.add_to_queue(song.item_id, link, song.title, high_priority=False, cover_id=song.cover_id)
                self.run_async(task)

            dlg.exec()
        self.run_async(fetch, on_ready)

    def _show_playlist_context_menu(self, widget, pos):
        pl_id = widget.property("pl_id")
        if not pl_id:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 6px; padding: 4px; }} QMenu::item {{ padding: 8px 25px 8px 10px; border-radius: 4px; background: transparent; }} QMenu::item:selected {{ background-color: {THEME['btn_remove_hover']}; }}")
        act_del = QAction("Usuń playlistę", self)
        act_del.triggered.connect(lambda: self._delete_playlist(pl_id))
        menu.addAction(act_del)
        menu.exec(widget.mapToGlobal(pos))

    def _delete_playlist(self, pl_id):
        def on_ready(res):
            if self.current_route and self.current_route.get("data", {}).get("id") == pl_id:
                self._go_back()
            self._load_playlists()
        self.run_async(lambda: self.client.delete_playlist(pl_id), on_ready, page_bound=False)

    def _load_playlists(self):
        def fetch():
            try:
                params = self.client._get_auth_params()
                res = self.client._make_request("getPlaylists", params)
                return res.get('playlists', {}).get('playlist', [])
            except Exception:
                return []
        def on_ready(data):
            self.sidebar.set_playlists(data)
            for i in range(self.sidebar.playlist_layout.count()):
                w = self.sidebar.playlist_layout.itemAt(i).widget()
                if w:
                    w.setContextMenuPolicy(Qt.CustomContextMenu)
                    w.customContextMenuRequested.connect(lambda pos, widget=w: self._show_playlist_context_menu(widget, pos))
        self.run_async(fetch, on_ready, page_bound=False)

    def _clear(self, lay):
        while lay.count():
            i = lay.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
            elif i.layout():
                self._clear(i.layout())

    def _handle_queue_drop(self, old_idx, drop_y):
        if not self.engine.queue:
            return
        layout = self.pages[Pages.QUEUE].widget().layout()
        song_widgets = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), SongItem):
                song_widgets.append(item.widget())
        target_q_idx = len(song_widgets)
        for i, w in enumerate(song_widgets):
            if drop_y < w.geometry().center().y():
                target_q_idx = i
                break
        self.engine.handle_queue_drop(old_idx, target_q_idx)

    def _handle_now_playing_queue_drop(self, old_idx, drop_y):
        if not self.engine.queue:
            return
        layout = self.now_playing_view.queue_layout
        song_widgets = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), SongItem):
                song_widgets.append(item.widget())
        target_q_idx = len(song_widgets)
        for i, w in enumerate(song_widgets):
            if drop_y < w.geometry().center().y():
                target_q_idx = i
                break
        self.engine.handle_queue_drop(old_idx, target_q_idx)

    def _shuffle_queue(self):
        if self._is_fetching:
            return
        def fetch_songs():
            return self.client.get_random_songs(50)
        def process_songs(songs):
            self.engine.shuffle_queue(songs)
        self.run_async(fetch_songs, process_songs, page_bound=True)

    def _sync_queue_ui(self):
        lay = self.now_playing_view.queue_layout
        if lay:
            for i in range(lay.count()):
                item = lay.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), SongItem):
                    w = item.widget()
                    w.queue_index = i
                    w.set_active(w.queue_index == self.engine.idx)
        if self.stack.currentIndex() == Pages.QUEUE:
            q_lay = self.pages[Pages.QUEUE].widget().layout()
            if q_lay:
                q_idx = 0
                for i in range(q_lay.count()):
                    item = q_lay.itemAt(i)
                    if item and item.widget():
                        w = item.widget()
                        if isinstance(w, QueueHeader):
                            if 0 <= self.engine.idx < len(self.engine.queue):
                                s = self.engine.queue[self.engine.idx]
                                w.sub_lbl.setText(f"ZACZNIJ SŁUCHAĆ: {s.title.upper()}")
                        elif isinstance(w, SongItem):
                            w.queue_index = q_idx
                            w.set_active(w.queue_index == self.engine.idx)
                            q_idx += 1
        QTimer.singleShot(100, self._scroll_now_playing_to_active)

    def _on_track_changed(self, song):
        self.force_telemetry_event = "TRACK_CHANGE"
        self.player_bar.set_track_info(song.title, song.artist, song.album, song.is_starred)
        self.now_playing_view.title_lbl.setText(song.title)
        self.now_playing_view.artist_lbl.setText(song.artist)
        if song.cover_id:
            self.loader.load(self.client.get_cover_art_url(song.cover_id), self.player_bar.pb_img)
            self.loader.load(self.client.get_cover_art_url(song.cover_id), self.now_playing_view)
        self._sync_queue_ui()

    def _on_state_changed(self, is_playing):
        self.player_bar.set_playing_state(is_playing)

    def _on_position_changed(self, p):
        self.player_bar.update_position(p)

    def _on_duration_changed(self, d):
        self.player_bar.update_duration(d)

    def _on_queue_updated(self):
        self._queue_update_timer.start()

    def _actual_queue_updated(self):
        if self.stack.currentIndex() == Pages.QUEUE:
            self._nav_queue()
        self._rebuild_now_playing_queue()

    def _rebuild_now_playing_queue(self):
        self._clear(self.now_playing_view.queue_layout)
        active_idx = self.engine.idx
        for i, s in enumerate(self.engine.queue):
            item = SongItem(s, active=(i == active_idx), is_queue=True, queue_index=i, compact_mode=True)
            item.clicked.connect(lambda song, idx=i: self.engine.play_list(self.engine.queue, idx))
            item.fav_clicked.connect(self._handle_song_fav)
            item.play_next_clicked.connect(lambda s_d, idx=i: self.engine.queue_play_next(idx))
            item.add_to_playlist_clicked.connect(self._show_playlist_dialog)
            item.remove_clicked.connect(lambda s_d, idx=i: self.engine.queue_remove(idx))
            item.artist_clicked.connect(self._show_details)
            item.album_clicked.connect(self._show_details)
            item.set_custom_cover_clicked.connect(self._set_custom_album_cover)
            item.reset_custom_cover_clicked.connect(self._reset_custom_album_cover)
            item.save_image_clicked.connect(self._save_image_to_file)
            self.now_playing_view.queue_layout.addWidget(item)
            if s.cover_id:
                self.loader.load(self.client.get_cover_art_url(s.cover_id), item)
        if 0 <= active_idx < self.now_playing_view.queue_layout.count():
            QTimer.singleShot(100, self._scroll_now_playing_to_active)

    def _scroll_now_playing_to_active(self):
        active_idx = self.engine.idx
        if 0 <= active_idx < self.now_playing_view.queue_layout.count():
            item = self.now_playing_view.queue_layout.itemAt(active_idx).widget()
            if item:
                self.now_playing_view.queue_scroll.ensureWidgetVisible(item)

    def _on_queue_cleared(self):
        self.player_bar.reset()
        self.now_playing_view.title_lbl.setText("Nic nie gra")
        self.now_playing_view.artist_lbl.setText("-")
        self.now_playing_view.set_image(None, animate=False)
        self._on_queue_updated()

    def _on_loop_mode_changed(self, is_looping):
        self.player_bar.set_loop_state(is_looping)

    def _on_shuffle_mode_changed(self, is_shuffled):
        self.player_bar.set_shuffle_state(is_shuffled)

    def _nav_queue(self):
        l = self.pages[Pages.QUEUE].widget().layout()
        self._clear(l)

        if not self.engine.queue:
            h = QueueHeader("Twoja kolejka jest pusta", "KOLEJKA ODTWARZANIA")
            h.set_empty_state(True)
            l.addWidget(h)
            l.addStretch()
            return

        active_idx = max(0, self.engine.idx)
        if active_idx < len(self.engine.queue):
            active_song = self.engine.queue[active_idx]
        else:
            active_song = self.engine.queue[0]

        h = QueueHeader("Twoja Kolejka", f"ZACZNIJ SŁUCHAĆ: {active_song.title.upper()}")
        h.set_empty_state(False)
        h.play_clicked.connect(self.engine.play_pause)
        h.shuffle_clicked.connect(self._shuffle_queue)
        h.clear_clicked.connect(self.engine.clear_queue)
        if active_song.cover_id:
            self.loader.load(self.client.get_cover_art_url(active_song.cover_id), h)
        l.addWidget(h)

        for i, s in enumerate(self.engine.queue):
            item = SongItem(s, active=(i == self.engine.idx), is_queue=True, queue_index=i)
            item.clicked.connect(lambda song, idx=i: self.engine.play_list(self.engine.queue, idx))
            item.fav_clicked.connect(self._handle_song_fav)
            item.play_next_clicked.connect(lambda s_d, idx=i: self.engine.queue_play_next(idx))
            item.add_to_playlist_clicked.connect(self._show_playlist_dialog)
            item.remove_clicked.connect(lambda s_d, idx=i: self.engine.queue_remove(idx))
            item.artist_clicked.connect(self._show_details)
            item.album_clicked.connect(self._show_details)
            item.set_custom_cover_clicked.connect(self._set_custom_album_cover)
            item.reset_custom_cover_clicked.connect(self._reset_custom_album_cover)
            item.save_image_clicked.connect(self._save_image_to_file)
            l.addWidget(item)
            if s.cover_id:
                self.loader.load(self.client.get_cover_art_url(s.cover_id), item)
        l.addStretch()
