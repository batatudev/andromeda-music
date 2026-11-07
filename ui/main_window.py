# ui/main_window.py
import os
os.environ["QT_API"] = "pyside6"

import sys
import time

import qtawesome as qta

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer, QThreadPool
from PySide6.QtMultimedia import QMediaPlayer

from api_client import NavidromeClient
from config import APP_CONFIG, APP_NAME, save_config, THEME, get_app_style, Pages
from utils import Worker, AsyncImageLoader, logger, telemetry_recorder, NetworkMonitor
from core.enums import EngineState, TelemetryEvent, MediaType
from core.i18n import tr
from core.system_health import SystemHealthChecker

from ui.widgets import HoverIconButton, SmoothScrollArea, ToastNotification
from ui.dialogs import PlaylistDialog
from ui.components import SongItem
from ui.components.custom_media_manager import CustomMediaManager
from ui.components.bulk_download_handler import BulkDownloadHandler

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

        self.mpris = None
        if HAS_MPRIS_MODULE:
            QTimer.singleShot(300, self._init_mpris)

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
        self.engine.video_error_occurred.connect(self._on_video_error_occurred)

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
        QTimer.singleShot(1500, self._ensure_video_output)

    def _init_mpris(self):
        try:
            self.mpris = MprisService(self.engine)
        except Exception as e:
            logger.log(f"Nie udało się załadować MPRIS: {e}")

    def _ensure_video_output(self):
        if not getattr(self, '_video_output_initialized', False):
            self._video_output_initialized = True
            if hasattr(self, 'now_playing_view') and hasattr(self.now_playing_view, 'video_widget'):
                self.engine.video_player.setVideoOutput(self.now_playing_view.video_widget.video_item)

    @property
    def settings_view(self):
        p = self.get_or_create_page(Pages.SETTINGS)
        if isinstance(p, QScrollArea):
            return p.widget()
        return p

    def get_or_create_page(self, page_idx):
        if self.pages[page_idx] is not None:
            return self.pages[page_idx]
        factory = self.page_factories.get(page_idx)
        if not factory:
            return self.stack.widget(page_idx)
        w = factory()
        old_dummy = self.stack.widget(page_idx)
        self.stack.removeWidget(old_dummy)
        old_dummy.deleteLater()
        self.stack.insertWidget(page_idx, w)
        self.pages[page_idx] = w
        return w

    def show_toast(self, message: str, title: str = "Powiadomienie", icon_str: str = "fa5s.info-circle", icon_color: str = None, duration: int = 5000):
        old_toast = getattr(self, '_active_toast', None)
        if old_toast is not None:
            try:
                old_toast.hide()
                old_toast.deleteLater()
            except (RuntimeError, Exception):
                pass
            self._active_toast = None

        toast = ToastNotification(self, message, title=title, icon_str=icon_str, icon_color=icon_color, duration=duration)
        self._active_toast = toast
        toast.destroyed.connect(lambda: self._on_toast_destroyed(toast))
        toast.show_toast()

    def _on_toast_destroyed(self, toast_ref=None):
        if getattr(self, '_active_toast', None) is toast_ref:
            self._active_toast = None

    def _on_video_error_occurred(self, error_type, custom_msg=""):
        if error_type == "INVALID_LINK":
            title = tr("toast.yt_title_invalid_link", "Błędny link YouTube")
            msg = custom_msg or tr("toast.yt_msg_invalid_link", "Podany link YouTube ma nieprawidłowy format. Sprawdź poprawność adresu lub przypisz nowy.")
            icon_str = "fa5s.unlink"
            icon_color = "#e67e22"
            duration = 6000
        elif error_type == "BLOCKED_OR_REMOVED":
            title = tr("toast.yt_title_blocked_or_removed", "Teledysk zablokowany")
            msg = custom_msg or tr("toast.yt_msg_blocked_or_removed", "Film został usunięty, zablokowany terytorialnie lub oznaczony jako prywatny.")
            icon_str = "fa5s.ban"
            icon_color = "#e74c3c"
            duration = 6000
        elif error_type in ("RATE_LIMIT", "BOT_CHECK"):
            title = tr("toast.yt_title_rate_limit_ip", "Blokada IP (HTTP 429)")
            msg = custom_msg or tr("toast.yt_msg_rate_limit_ip", "YouTube nałożył limit zapytań na Twój adres IP lub wymaga weryfikacji bota. Dodaj cookies.txt.")
            icon_str = "fa5s.shield-alt"
            icon_color = "#c0392b"
            duration = 8000
        elif error_type == "RATE_LIMIT_DL":
            title = tr("toast.yt_title_rate_limit_dl", "Limit pobierania wideo")
            msg = custom_msg or tr("toast.yt_msg_rate_limit_dl", "YouTube nałożył limit zapytań (HTTP 429). Kolejka pobierania wideo została wstrzymana na 1 godzinę.")
            icon_str = "fa5s.shield-alt"
            icon_color = "#c0392b"
            duration = 8000
        elif error_type == "AGE_RESTRICTED":
            title = tr("toast.yt_title_age_restricted", "Ograniczenie wiekowe")
            msg = custom_msg or tr("toast.yt_msg_age_restricted", "Teledysk wymaga konta 18+. Dodaj plik cookies.txt z zalogowanego konta.")
            icon_str = "fa5s.user-shield"
            icon_color = "#f39c12"
            duration = 7000
        elif error_type == "NETWORK_TIMEOUT":
            title = tr("toast.yt_title_network_error", "Błąd sieci")
            msg = custom_msg or tr("toast.yt_msg_network_error", "Przekroczono limit czasu połączenia z YouTube. Sprawdź stabilność łącza internetowego.")
            icon_str = "fa5s.wifi"
            icon_color = "#7f8c8d"
            duration = 6000
        else:
            title = tr("health.warning", "Ostrzeżenie")
            msg = custom_msg or tr("toast.yt_video_unavailable", "Teledysk jest niedostępny lub zablokowany. Odtwarzam wyłącznie utwór audio.")
            icon_str = "fa5s.exclamation-triangle"
            icon_color = "#e67e22"
            duration = 6000

        self.show_toast(
            msg,
            title=title,
            icon_str=icon_str,
            icon_color=icon_color,
            duration=duration
        )

    def resizeEvent(self, event):
        if hasattr(self, 'sidebar_ctrl'):
            self.sidebar_ctrl.handle_resize(self.width())
        toast = getattr(self, '_active_toast', None)
        if toast is not None:
            try:
                import shiboken6
                is_valid = shiboken6.isValid(toast)
            except Exception:
                is_valid = True

            if is_valid:
                try:
                    if toast.isVisible():
                        toast._reposition()
                except RuntimeError:
                    self._active_toast = None
            else:
                self._active_toast = None
        super().resizeEvent(event)

    def closeEvent(self, event):
        save_config()

        if hasattr(self, 'engine'):
            if hasattr(self.engine, 'audio_download_manager'):
                self.engine.audio_download_manager.stop()
            if hasattr(self.engine, 'video_download_manager'):
                self.engine.video_download_manager.stop()
            if hasattr(self.engine, 'sync_timeout_timer') and self.engine.sync_timeout_timer.isActive():
                self.engine.sync_timeout_timer.stop()
            if hasattr(self.engine, 'sync_timer') and self.engine.sync_timer.isActive():
                self.engine.sync_timer.stop()
            if hasattr(self.engine, 'player'):
                self.engine.player.stop()
            if hasattr(self.engine, 'video_player'):
                self.engine.video_player.stop()

        if hasattr(self, 'repo') and hasattr(self.repo, 'library_sync'):
            self.repo.library_sync.stop()

        if hasattr(self, 'watchdog'):
            self.watchdog.stop()

        if hasattr(self, 'telemetry'):
            self.telemetry.stop()

        if hasattr(self, 'network_monitor'):
            self.network_monitor.stop()
            self.network_monitor.join(timeout=0.5)

        if hasattr(self, 'threadpool'):
            self.threadpool.waitForDone(600)

        logger.flush()
        telemetry_recorder.flush()
        super().closeEvent(event)

    def _start_app(self):
        SystemHealthChecker.perform_startup_check(self)
        self.sidebar_ctrl.load_playlists()
        self.router.navigate(Pages.HOME)

    def _sync_auto_downloads(self):
        BulkDownloadHandler.sync_auto_downloads(self)

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
                        self.engine.video_download_manager.add_to_queue(
                            song.item_id, link, song.title, high_priority=False, cover_id=song.cover_id
                        )

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
        self.sidebar.playlist_requested.connect(
            lambda pid, pname: self.router.show_details({"id": pid, "name": pname}, MediaType.PLAYLIST)
        )
        self.sidebar.settings_requested.connect(self._toggle_settings)
        self.sidebar.dev_requested.connect(lambda: self.router.switch_page(Pages.DEV_MODE))

        self.stack = QStackedWidget()
        self.pages = [None] * len(Pages)

        self.now_playing_view = NowPlayingWidget()
        self.now_playing_view.queue_content.drop_occurred.connect(self._handle_now_playing_queue_drop)
        self._video_output_initialized = False

        def make_scrollable(view_widget):
            s = SmoothScrollArea()
            s.setWidgetResizable(True)
            s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            s.setStyleSheet("background: transparent; border: none;")
            s.setWidget(view_widget)
            return s

        self.page_factories = {
            Pages.HOME: lambda: HomeView(self),
            Pages.FAVS: lambda: FavsView(self),
            Pages.QUEUE: lambda: QWidget(),
            Pages.ALBUMS: lambda: AlbumsView(self),
            Pages.DETAILS: lambda: DetailsView(self),
            Pages.TRACKS: lambda: TracksView(self),
            Pages.ARTISTS: lambda: ArtistsView(self),
            Pages.SETTINGS: lambda: make_scrollable(SettingsView(self)),
            Pages.NOW_PLAYING: lambda: self.now_playing_view,
            Pages.DEV_MODE: lambda: make_scrollable(DevModeView(self)),
            Pages.SEARCH: lambda: SearchView(self),
            Pages.DOWNLOADS: lambda: make_scrollable(DownloadsView(self))
        }

        for pid in Pages:
            if pid == Pages.HOME:
                w = self.page_factories[pid]()
                self.pages[pid] = w
                self.stack.addWidget(w)
            elif pid == Pages.NOW_PLAYING:
                w = self.now_playing_view
                self.pages[pid] = w
                self.stack.addWidget(w)
            else:
                dummy = QWidget()
                self.stack.addWidget(dummy)

        self.router.setup(self.stack, self.pages)

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
            target = self.get_or_create_page(idx)

            if hasattr(target, 'load'):
                actual = target
            elif isinstance(target, QScrollArea) and hasattr(target.widget(), 'load'):
                actual = target.widget()
            else:
                actual = target

            if hasattr(actual, 'invalidate_cache'):
                actual.invalidate_cache()

            if idx == Pages.DETAILS:
                actual.load(self.router.current_route["data"], self.router.current_route["type"], force=True)
            elif idx in [Pages.HOME, Pages.FAVS, Pages.ALBUMS, Pages.TRACKS, Pages.ARTISTS, Pages.SEARCH, Pages.DOWNLOADS]:
                if hasattr(actual, 'load'):
                    actual.load(force=True)

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
        BulkDownloadHandler.start_bulk_download(self, bulk_type, target_id, target_name, media_type)

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
        self._ensure_video_output()
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
            self._ensure_video_output()
            if self.engine.queue and self.engine.idx >= 0:
                song = self.engine.queue[self.engine.idx]
                fresh_link = song.yt_link
                if not fresh_link and hasattr(self.engine, 'client') and self.engine.client:
                    from engine.header_tag_extractor import check_and_cache_remote_header
                    fresh_link = check_and_cache_remote_header(
                        self.engine.client, song, getattr(self.engine, 'video_download_manager', None)
                    )
                self.engine.current_yt_link = fresh_link
                self.engine.video_killed_for_track = False

                offline_path = self.engine.video_download_manager.get_video_path(song.item_id)
                if offline_path:
                    self.engine.load_and_play_video(force_mid_track=True)
                    return
                if fresh_link:
                    self.engine.load_and_play_video(force_mid_track=True)
                    return
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
        CustomMediaManager.set_custom_artist_image(self, data, type_str, self.loader, self._refresh_current)

    def _reset_custom_artist_image(self, data, type_str):
        CustomMediaManager.reset_custom_artist_image(self, data, type_str, self.loader, self._refresh_current)

    def _set_custom_album_cover(self, data, type_str):
        CustomMediaManager.set_custom_album_cover(
            self, data, type_str, self.loader, self._refresh_current, self._refresh_player_bar_if_needed
        )

    def _reset_custom_album_cover(self, data, type_str):
        CustomMediaManager.reset_custom_album_cover(
            self, data, type_str, self.loader, self._refresh_current, self._refresh_player_bar_if_needed
        )

    def _save_image_to_file(self, data, type_str):
        CustomMediaManager.save_image_to_file(self, self.client, data, type_str, self.run_async)

    def _show_playlist_dialog(self, song):
        dlg = PlaylistDialog(
            self, self.client, song,
            self.engine.video_download_manager,
            on_playlists_changed=self.sidebar_ctrl.load_playlists
        )
        dlg.exec()

    def _handle_now_playing_queue_drop(self, old_idx, drop_y):
        if not self.engine.queue:
            return
        layout = self.now_playing_view.queue_layout
        song_widgets = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), SongItem):
                song_widgets.append(item.widget())

        if not song_widgets:
            return

        target_idx = len(song_widgets) - 1
        for i, w in enumerate(song_widgets):
            if drop_y <= w.geometry().bottom():
                target_idx = i
                break

        self.engine.handle_queue_drop(old_idx, target_idx)

    def _shuffle_queue(self):
        if self._is_fetching:
            return

        def fetch_songs():
            return self.client.get_random_songs(50)

        def process_songs(songs):
            self.engine.shuffle_queue(songs)

        self.run_async(fetch_songs, process_songs, page_bound=True)

    def _sync_queue_ui(self):
        self.now_playing_view.sync_active_index(self.engine.idx)

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
        handlers = {
            'play': lambda idx: self.engine.play_list(self.engine.queue, idx),
            'fav': self._handle_song_fav,
            'play_next': lambda idx: self.engine.queue_play_next(idx),
            'add_to_playlist': self._show_playlist_dialog,
            'remove': lambda idx: self.engine.queue_remove(idx),
            'artist': self.router.show_details,
            'album': self.router.show_details,
            'set_custom_cover': self._set_custom_album_cover,
            'reset_custom_cover': self._reset_custom_album_cover,
            'save_image': self._save_image_to_file
        }
        self.now_playing_view.update_queue(
            self.engine.queue,
            self.engine.idx,
            handlers,
            self.loader,
            self.client
        )

    def _scroll_now_playing_to_active(self):
        self.now_playing_view.scroll_to_active(self.engine.idx)

    def _on_queue_cleared(self):
        self.player_bar.reset()
        self.now_playing_view.title_lbl.setText(tr("player.not_playing", "Nic nie gra"))
        self.now_playing_view.artist_lbl.setText("-")
        self.now_playing_view.set_image(None, animate=False)
        self._on_queue_updated()

    def _on_loop_mode_changed(self, is_looping):
        self.player_bar.set_loop_state(is_looping)

    def _on_shuffle_mode_changed(self, is_shuffled):
        self.player_bar.set_shuffle_state(is_shuffled)