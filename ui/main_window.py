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
    offline_status_changed = Signal(str, str)

    def __init__(self, client):
        super().__init__()
        logger.start_session("14.6+")
        telemetry_recorder.start_session("14.6+")

        from core.data_repository import DataRepository
        self.client = client
        self.repo = DataRepository(self.client)
        self.loader = AsyncImageLoader(self)
        self.engine = PlayerEngine(self.client)

        self.network_monitor = NetworkMonitor(APP_CONFIG.get("url", "http://localhost"))
        self.network_monitor.start()

        if HAS_MPRIS_MODULE:
            try:
                self.mpris = MprisService(self.engine)
            except Exception as e:
                logger.log(f"Nie udało się załadować MPRIS: {e}")

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

        self.engine.video_download_manager.download_status_changed.connect(
            lambda item_id, status: self.offline_status_changed.emit(item_id, status)
        )
        self.engine.audio_download_manager.download_status_changed.connect(
            lambda item_id, status: self.offline_status_changed.emit(item_id, status)
        )

        self.engine.loop_mode_changed.connect(self._on_loop_mode_changed)
        self.engine.shuffle_mode_changed.connect(self._on_shuffle_mode_changed)

        self._is_fetching = False
        self.current_page_task_id = 0

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

    def show_toast(self, message: str, title: str = "Powiadomienie", icon_str: str = "fa5s.info-circle", icon_color: str = None, duration: int = 5000):
        if getattr(self, '_active_toast', None):
            try:
                self._active_toast.hide()
                self._active_toast.deleteLater()
            except Exception:
                pass
            self._active_toast = None

        from ui.widgets import ToastNotification
        toast = ToastNotification(self, message, title=title, icon_str=icon_str, icon_color=icon_color, duration=duration)
        self._active_toast = toast
        toast.show_toast()

    def resizeEvent(self, event):
        if hasattr(self, 'sidebar_ctrl'):
            self.sidebar_ctrl.handle_resize(self.width())
        if getattr(self, '_active_toast', None) and self._active_toast.isVisible():
            self._active_toast._reposition()
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
        self.sidebar_ctrl.load_playlists()
        self.router.navigate(Pages.HOME)

    def _sync_auto_downloads(self):
        def fetch():
            video_songs = []
            audio_songs = []

            if APP_CONFIG.get("video_auto_dl_favs", False):
                video_songs.extend(self.client.get_starred(1000))
            if APP_CONFIG.get("audio_auto_dl_favs", False):
                audio_songs.extend(self.client.get_starred(1000))

            v_pl_ids = APP_CONFIG.get("video_auto_dl_playlists", [])
            for pid in v_pl_ids:
                try:
                    params = self.client._get_auth_params()
                    params["id"] = pid
                    res = self.client._make_request("getPlaylist", params)
                    entry = res.get("playlist", {}).get("entry", [])
                    from core.models import MediaItem
                    video_songs.extend([MediaItem(s) for s in entry])
                except Exception as e:
                    logger.log(f"Auto-sync wideo playlist {pid} failed: {e}")

            a_pl_ids = APP_CONFIG.get("audio_auto_dl_playlists", [])
            for pid in a_pl_ids:
                try:
                    params = self.client._get_auth_params()
                    params["id"] = pid
                    res = self.client._make_request("getPlaylist", params)
                    entry = res.get("playlist", {}).get("entry", [])
                    from core.models import MediaItem
                    audio_songs.extend([MediaItem(s) for s in entry])
                except Exception as e:
                    logger.log(f"Auto-sync audio playlist {pid} failed: {e}")

            return video_songs, audio_songs

        def on_ready(result):
            if not result: return
            video_songs, audio_songs = result

            v_items_to_add = []
            for s in video_songs:
                link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
                if link:
                    v_items_to_add.append((s.item_id, link, s.title, s.cover_id))
            if v_items_to_add:
                self.engine.video_download_manager.add_to_queue_bulk(v_items_to_add, high_priority=False)

            a_items_to_add = [(s.item_id, s.title) for s in audio_songs]
            if a_items_to_add:
                self.engine.audio_download_manager.add_to_queue_bulk(a_items_to_add, high_priority=False)

        self.run_async(fetch, on_ready, page_bound=False)

    def _handle_song_fav(self, song, new_state):
        song_id = song.item_id
        if not song_id:
            return
        self.run_async(lambda: self.client.star_track(song_id, new_state))
        self.fav_updated.emit(song_id, new_state)

        if new_state:
            if APP_CONFIG.get("video_auto_dl_favs", False):
                def resolve_video_fav():
                    link = getattr(song, 'yt_link', None) or getattr(song, 'youtube_url', None)
                    if not link:
                        from engine.header_tag_extractor import check_and_cache_remote_header
                        link = check_and_cache_remote_header(self.client, song, self.engine.video_download_manager)
                    return link

                def on_video_resolved(link):
                    if link and APP_CONFIG.get("video_auto_dl_favs", False):
                        self.engine.video_download_manager.add_to_queue(song.item_id, link, song.title, high_priority=False, cover_id=song.cover_id)

                self.run_async(resolve_video_fav, on_video_resolved, page_bound=False)

            if APP_CONFIG.get("audio_auto_dl_favs", False):
                self.engine.audio_download_manager.add_to_queue(song.item_id, song.title, high_priority=False)

    def _on_fav_updated(self, song_id, is_fav):
        for q_song in self.engine.queue:
            if q_song.item_id == song_id:
                q_song.set_starred(is_fav)

        if 0 <= self.engine.idx < len(self.engine.queue):
            current_song = self.engine.queue[self.engine.idx]
            if current_song.item_id == song_id:
                self.player_bar.pb_fav_btn.set_default_color(THEME["accent"] if is_fav else THEME["heart_inactive"])
                self.player_bar.pb_fav_btn.update_icon('fa5s.heart' if is_fav else 'fa5.heart')

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

    def _show_details(self, data, type_str):
        self.router.show_details(data, type_str)

    def _go_back(self):
        self.router.go_back()

    def _switch_page(self, idx):
        self.router.switch_page(idx)

    def _navigate(self, page_idx, data=None, type_str=None, is_back=False):
        self.router.navigate(page_idx, data, type_str, is_back)

    def _manual_toggle_sidebar(self):
        self.sidebar_ctrl.toggle_sidebar(manual=True)

    def _update_sidebar_active_state(self):
        self.sidebar_ctrl.update_active_state(self.router)
        active_idx = self.router.current_route.get("page") if self.router.current_route else None
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

        from ui.router import AppRouter
        self.router = AppRouter(self)

        self.sidebar = SidebarWidget(dev_mode=APP_CONFIG.get("dev_mode", False))
        self.sidebar.page_requested.connect(self.router.switch_page)
        self.sidebar.back_requested.connect(self.router.go_back)
        self.sidebar.refresh_requested.connect(self._refresh_current)
        from ui.components.sidebar_controller import SidebarController
        self.sidebar_ctrl = SidebarController(self)
        self.sidebar.playlist_requested.connect(lambda pid, pname: self.router.show_details({"id": pid, "name": pname}, MediaType.PLAYLIST))
        self.sidebar.settings_requested.connect(self._toggle_settings)
        self.sidebar.dev_requested.connect(lambda: self.router.switch_page(Pages.DEV_MODE))

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
                dummy = QWidget()
                self.pages[page_id] = dummy
                self.stack.addWidget(dummy)

        self.router.setup(self.stack, self.pages)

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
        self.player_bar.volume_changed.connect(self._on_volume_changed)
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

    def _toggle_queue(self):
        self.now_playing_view.toggle_queue_visibility()

    def _toggle_settings(self):
        if self.stack.currentIndex() == Pages.SETTINGS:
            self.router.go_back()
        else:
            self.router.navigate(Pages.SETTINGS)

    def _toggle_now_playing(self):
        if self.stack.currentIndex() == Pages.NOW_PLAYING:
            self.router.go_back()
        else:
            self.router.navigate(Pages.NOW_PLAYING)

    def _refresh_current(self):
        if not self._is_fetching and getattr(self.router, 'current_route', None):
            self.current_page_task_id += 1
            idx = self.router.current_route["page"]
            if idx == Pages.DETAILS:
                self.pages[idx].load(self.router.current_route["data"], self.router.current_route["type"])
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
            self.start_bulk_download("album", data.item_id, data.title, media_type="video")
        elif type_str == MediaType.ARTIST:
            self.start_bulk_download("artist", data.title, data.title, media_type="video")

    def start_bulk_download(self, bulk_type, target_id=None, target_name=None, media_type="video"):
        if self._is_fetching:
            return

        def fetch():
            songs = []
            if bulk_type == "favorites":
                songs = self.client.get_starred(1000)
            elif bulk_type == "playlist":
                params = self.client._get_auth_params()
                params["id"] = target_id
                res = self.client._make_request("getPlaylist", params)
                entry = res.get("playlist", {}).get("entry", [])
                from core.models import MediaItem
                songs = [MediaItem(s) for s in entry]
            elif bulk_type == "album":
                songs = self.client.get_album(target_id).get('song', [])
            elif bulk_type == "artist":
                songs = self.client.get_top_songs_for_artist(target_id, limit=500)
            elif bulk_type == "all":
                if hasattr(self, 'repo'):
                    return self.repo.library_sync.get_all_songs()
                else:
                    songs = self.client.get_random_songs(1000)
            return songs

        def on_ready(songs):
            if not songs:
                QMessageBox.information(self, "Brak utworów", "Nie znaleziono utworów do pobrania.")
                return

            if media_type == "video":
                valid_songs = [s for s in songs if getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)]
                if not valid_songs:
                    QMessageBox.information(self, "Brak linków", "Znalezione utwory nie posiadają linków do wideo.")
                    return

                quality = APP_CONFIG.get("video_offline_quality", "1080p")
                avg_mb = 25
                if quality == "720p": avg_mb = 15
                elif quality == "480p": avg_mb = 10

                count = len(valid_songs)
                est_mb = count * avg_mb
                est_str = f"{est_mb / 1024:.2f} GB" if est_mb > 1024 else f"{est_mb} MB"

                msg = f"Znaleziono {count} utworów z teledyskami.\nSzacowany rozmiar do pobrania: ~{est_str} (Jakość: {quality}).\n\nCzy chcesz rozpocząć pobieranie wideo?"
                ans = QMessageBox.question(self, "Potwierdzenie pobierania", msg, QMessageBox.Yes | QMessageBox.No)

                if ans == QMessageBox.Yes:
                    items_to_add = []
                    for s in valid_songs:
                        link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
                        if link:
                            items_to_add.append((s.item_id, link, s.title, s.cover_id))
                    if items_to_add:
                        self.engine.video_download_manager.add_to_queue_bulk(items_to_add, high_priority=False)
                    self.show_toast(f"Dodano zadania ({len(items_to_add)}) do kolejki pobierania wideo.", title="Pobieranie Wideo", icon_str="fa5s.film", icon_color="#e74c3c")

            elif media_type == "audio":
                from core.models import MediaItem
                valid_songs = [s if isinstance(s, MediaItem) else MediaItem(s) for s in songs]

                avg_mb = 6
                count = len(valid_songs)
                est_mb = count * avg_mb
                est_str = f"{est_mb / 1024:.2f} GB" if est_mb > 1024 else f"{est_mb} MB"

                msg = f"Znaleziono {count} utworów audio.\nSzacowany rozmiar do pobrania: ~{est_str}.\n\nCzy chcesz rozpocząć pobieranie muzyki?"
                ans = QMessageBox.question(self, "Potwierdzenie pobierania", msg, QMessageBox.Yes | QMessageBox.No)

                if ans == QMessageBox.Yes:
                    items_to_add = [(s.item_id, s.title) for s in valid_songs]
                    if items_to_add:
                        self.engine.audio_download_manager.add_to_queue_bulk(items_to_add, high_priority=False)
                    self.show_toast(f"Dodano zadania ({len(items_to_add)}) do kolejki pobierania audio.", title="Pobieranie Audio", icon_str="fa5s.music", icon_color=THEME["accent"])

        self.run_async(fetch, on_ready, page_bound=False)

    def _pb_title_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('albumId'):
                self.router.show_details({"id": song.get('albumId'), "name": song.album}, MediaType.ALBUM)

    def _pb_artist_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('artistId'):
                self.router.show_details({"id": song.get('artistId'), "name": song.artist}, MediaType.ARTIST)

    def _pb_album_clicked(self):
        if 0 <= self.engine.idx < len(self.engine.queue):
            song = self.engine.queue[self.engine.idx]
            if song.get('albumId'):
                self.router.show_details({"id": song.get('albumId'), "name": song.album}, MediaType.ALBUM)

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
                self.router.go_back()
                self.router.show_details({"id": song.get('artistId'), "name": song.artist}, MediaType.ARTIST)

    def _show_video_layer(self):
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
        if self.engine.queue and self.engine.idx >= 0:
            song = self.engine.queue[self.engine.idx]
            offline_path = self.engine.video_download_manager.get_video_path(song.item_id)

            if offline_path:
                if not has_video:
                    self.player_bar.set_video_available(True)
                if APP_CONFIG.get("video_smart_auto_play", False):
                    self.engine.load_and_play_video()
                    return
                else:
                    if self.player_bar.btn_video_toggle.isChecked():
                        self.player_bar.set_video_active(True)
                        self.engine.load_and_play_video()
                        return
                    return

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
            if self.engine.queue and self.engine.idx >= 0:
                song = self.engine.queue[self.engine.idx]
                offline_path = self.engine.video_download_manager.get_video_path(song.item_id)
                if offline_path:
                    self.engine.load_and_play_video(force_mid_track=True)
                    return
            if self.engine.current_yt_link:
                self.engine.load_and_play_video(force_mid_track=True)
            else:
                self.now_playing_view.set_media_mode("audio")
        else:
            self._current_mask_state = False
            self.now_playing_view.set_buffering_state(False)
            self.now_playing_view.set_media_mode("audio")
            self.engine.video_player.stop()

    def _on_volume_changed(self, value):
        self.engine.set_volume(value)
        is_muted = self.engine.audio_output.isMuted()
        if value == 0:
            if not is_muted:
                self._toggle_mute(force_state=True)
        else:
            if is_muted:
                self._toggle_mute(force_state=False)

    def _toggle_mute(self, force_state=None):
        if force_state is not None:
            new_state = force_state
        else:
            new_state = not self.engine.audio_output.isMuted()
            if not new_state and self.player_bar.v_s.value() == 0:
                self.player_bar.v_s.setValue(30)
                return
        self.engine.audio_output.setMuted(new_state)
        self.player_bar.set_mute_state(new_state)

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

                self.loader.refresh_file_indexes()
                self.loader._ram_cache.clear()
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
            self.loader.refresh_file_indexes()
            self.loader._ram_cache.clear()
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

                self.loader.refresh_file_indexes()
                self.loader._ram_cache.clear()
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
            self.loader.refresh_file_indexes()
            self.loader._ram_cache.clear()
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

    def _clear(self, lay):
        while lay.count():
            i = lay.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
            elif i.layout():
                self._clear(i.layout())

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
        self._rebuild_now_playing_queue()

    def _rebuild_now_playing_queue(self):
        v_bar = self.now_playing_view.queue_scroll.verticalScrollBar()
        old_val = v_bar.value()

        self._clear(self.now_playing_view.queue_layout)
        active_idx = self.engine.idx
        for i, s in enumerate(self.engine.queue):
            item = SongItem(s, active=(i == active_idx), is_queue=True, queue_index=i, compact_mode=True)
            item.clicked.connect(lambda song, idx=i: self.engine.play_list(self.engine.queue, idx))
            item.fav_clicked.connect(self._handle_song_fav)
            item.play_next_clicked.connect(lambda s_d, idx=i: self.engine.queue_play_next(idx))
            item.add_to_playlist_clicked.connect(self._show_playlist_dialog)
            item.remove_clicked.connect(lambda s_d, idx=i: self.engine.queue_remove(idx))
            item.artist_clicked.connect(self.router.show_details)
            item.album_clicked.connect(self.router.show_details)
            item.set_custom_cover_clicked.connect(self._set_custom_album_cover)
            item.reset_custom_cover_clicked.connect(self._reset_custom_album_cover)
            item.save_image_clicked.connect(self._save_image_to_file)
            self.now_playing_view.queue_layout.addWidget(item)
            if s.cover_id:
                self.loader.load(self.client.get_cover_art_url(s.cover_id), item)

        QTimer.singleShot(0, lambda: self.now_playing_view.queue_scroll.verticalScrollBar().setValue(old_val))

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