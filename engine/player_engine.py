import os
os.environ["QT_API"] = "pyside6"

import threading
import time
from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from config import APP_CONFIG
from utils import logger
from core.enums import EngineState, VideoResolution

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False
    logger.log("Brak biblioteki yt-dlp! Funkcja wideo będzie wyłączona.")

from engine.cache_manager import CacheManager
from engine.arf_manager import ARFManager
from engine.yt_resolver import YTResolver
from engine.video_download_manager import VideoDownloadManager
from engine.audio_download_manager import AudioDownloadManager
from engine.queue_manager import QueueManager
from engine.audio_controller import AudioController
from engine.video_controller_online import VideoControllerOnline
from core.paths import PathsManager


class PlayerEngine(QObject):
    track_changed = Signal(object)
    state_changed = Signal(bool)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    queue_updated = Signal()
    queue_cleared = Signal()
    loading_changed = Signal(bool)

    video_ready = Signal(str)
    has_video_signal = Signal(bool)
    video_ready_to_show = Signal()
    audio_track_cached = Signal(str, str)

    loop_mode_changed = Signal(bool)
    shuffle_mode_changed = Signal(bool)
    buffering_changed = Signal(bool)

    def __init__(self, client):
        super().__init__()
        self.client = client

        self.audio_ctrl = AudioController(self)
        self.player = self.audio_ctrl.player
        self.audio_output = self.audio_ctrl.audio_output

        self.video_ctrl = VideoControllerOnline(self)
        self.video_player = self.video_ctrl.player
        self.video_audio = self.video_ctrl.audio_output

        self.queue_mgr = QueueManager(self)
        self.cache_manager = CacheManager(self)
        self.arf_manager = ARFManager(self)
        self.yt_resolver = YTResolver(self)
        self.video_download_manager = VideoDownloadManager()
        self.audio_download_manager = AudioDownloadManager(self.client)

        self.queue_mgr.queue_updated.connect(self.queue_updated.emit)
        self.queue_mgr.queue_cleared.connect(self.queue_cleared.emit)
        self.queue_mgr.loop_mode_changed.connect(self.loop_mode_changed.emit)
        self.queue_mgr.shuffle_mode_changed.connect(self.shuffle_mode_changed.emit)

        self.current_yt_link = None
        self.video_needs_sync_on_load = False
        self.resolve_id = 0

        self.prefetched_song_id = None
        self.prefetched_yt_url = None
        self.prefetched_yt_info_dict = None
        self._current_yt_info_dict = None

        self._sync_start_active = False
        self._audio_loaded_for_sync = False
        self._video_loaded_for_sync = False
        self._is_new_track_starting = False
        self._seek_grace_until = 0

        self.audio_status_str = "Brak"
        self.video_status_str = "Brak"
        self.current_engine_state = EngineState.STOPPED
        self.last_resolve_time = 0

        self._last_buffering_state = False
        self._pending_buffering_state = False

        self.yt_cancel_event = threading.Event()
        self.prefetch_cancel_event = threading.Event()

        self.sync_timeout_timer = QTimer(self)
        self.sync_timeout_timer.setSingleShot(True)
        self.sync_timeout_timer.timeout.connect(self._on_sync_timeout)

        self.buffering_hysteresis_timer = QTimer(self)
        self.buffering_hysteresis_timer.setSingleShot(True)
        self.buffering_hysteresis_timer.timeout.connect(self._commit_buffering_state)

        self.cache_dir = str(PathsManager.get_audio_cache_dir())
        self.cancel_event = None
        self.audio_track_cached.connect(self._on_audio_track_cached)

        self.cache_cleanup_timer = QTimer(self)
        self.cache_cleanup_timer.timeout.connect(self.cache_manager.cleanup_cache)
        self.cache_cleanup_timer.start(3600000)
        QTimer.singleShot(5000, self.cache_manager.cleanup_cache)

        self.current_video_resolution = APP_CONFIG.get("video_resolution", VideoResolution.RES_1080P)
        self.arf_active_res = APP_CONFIG.get("video_resolution", VideoResolution.RES_1080P)
        self.arf_success_streak = 0
        self.arf_pending_downgrade = False
        self.arf_last_buffer_sec = 0.0
        self.arf_drop_ticks = 0
        self.video_stream_start_time = 0
        self.video_killed_for_track = False

        self.h_sync_count = 0
        self.sync_locked = False

        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(500)
        self.sync_timer.timeout.connect(self._sync_video)

        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.mediaStatusChanged.connect(self._status_upd)
        self.video_player.mediaStatusChanged.connect(self._video_status_upd)
        self.player.playbackStateChanged.connect(self._playback_state_changed)

        self.video_ready.connect(self._on_video_resolved)
        self.video_player.playingChanged.connect(self._on_video_playing_changed)

    @property
    def queue(self):
        return self.queue_mgr.queue

    @queue.setter
    def queue(self, val):
        self.queue_mgr.queue = val

    @property
    def idx(self):
        return self.queue_mgr.idx

    @idx.setter
    def idx(self, val):
        self.queue_mgr.idx = val

    @property
    def is_looping(self):
        return self.queue_mgr.is_looping

    @is_looping.setter
    def is_looping(self, val):
        self.queue_mgr.is_looping = val

    @property
    def is_shuffled(self):
        return self.queue_mgr.is_shuffled

    @is_shuffled.setter
    def is_shuffled(self, val):
        self.queue_mgr.is_shuffled = val

    def _on_sync_timeout(self):
        if getattr(self, '_sync_start_active', False):
            logger.decision("SYNC-START", "Przekroczono czas oczekiwania na wideo", "Wymuszenie startu audio (Fallback)")
            self._sync_start_active = False
            self.loading_changed.emit(False)
            if getattr(self, '_audio_loaded_for_sync', False):
                self.player.play()

    def get_buf_sec(self):
        dur_ms = self.player.duration()
        pos_ms = self.player.position()
        if dur_ms <= 0:
            return 0.0
        dur_sec = dur_ms / 1000.0
        pos_sec = pos_ms / 1000.0
        buf_pct = self.video_player.bufferProgress()
        buffered_total_sec = dur_sec * buf_pct
        buf_sec = buffered_total_sec - pos_sec
        v_stat = self.video_player.mediaStatus()
        if v_stat == QMediaPlayer.MediaStatus.BufferedMedia:
            return max(2.0, buf_sec)
        return max(0.0, buf_sec)

    def _evaluate_buffering(self):
        if getattr(self, '_sync_start_active', False):
            return
        a_stat = self.player.mediaStatus()
        v_stat = self.video_player.mediaStatus()
        buffering_states = [
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.StalledMedia
        ]
        is_buffering = (a_stat in buffering_states)
        if self.current_yt_link is not None:
            if self.video_player.source().isValid():
                if v_stat in buffering_states:
                    is_buffering = True
        if not is_buffering:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.current_engine_state = EngineState.PLAYING_SMOOTH
            elif self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
                self.current_engine_state = EngineState.PAUSED
        if is_buffering != self._pending_buffering_state:
            self._pending_buffering_state = is_buffering
            if is_buffering:
                self.buffering_hysteresis_timer.start(500)
            else:
                self.buffering_hysteresis_timer.stop()
                self._commit_buffering_state()

    def _commit_buffering_state(self):
        if getattr(self, '_sync_start_active', False):
            return
        if self._pending_buffering_state:
            self.current_engine_state = EngineState.BUFFERING
        if self._last_buffering_state != self._pending_buffering_state:
            self._last_buffering_state = self._pending_buffering_state
            self.buffering_changed.emit(self._pending_buffering_state)

    def _on_audio_track_cached(self, song_id, path):
        current_song = self.queue_mgr.current_song()
        if current_song and current_song.item_id == song_id:
            self.player.setSource(QUrl.fromLocalFile(path))
            self.loading_changed.emit(False)
            if getattr(self, '_sync_start_active', False):
                self._audio_loaded_for_sync = True
                self._check_sync_start()
            else:
                self.player.play()

    def _on_video_resolved(self, direct_url):
        self.yt_resolver.on_video_resolved(direct_url)

    def _sync_video(self):
        if getattr(self, 'video_killed_for_track', False):
            self._deactivate_sync_timer()
            return
        if getattr(self, '_sync_start_active', False):
            return
        if not self.video_player.source().isValid():
            self._deactivate_sync_timer()
            return

        v_status = self.video_player.mediaStatus()
        if v_status in [
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.StalledMedia
        ]:
            return

        if time.time() < getattr(self, '_seek_grace_until', 0):
            return

        a_state = self.player.playbackState()
        if a_state != QMediaPlayer.PlaybackState.PlayingState:
            if self.video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.video_player.pause()
            self._deactivate_sync_timer()
            return

        if self.video_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.video_player.play()

        a_pos = self.player.position()
        v_pos = self.video_player.position()
        delta = a_pos - v_pos

        buf_sec = self.get_buf_sec()
        hard_limit = 1200 if buf_sec < 10.0 else 800

        if buf_sec < 2.0:
            if not getattr(self, 'sync_locked', False):
                self.sync_locked = True
                self.video_player.setPlaybackRate(1.0)
            return
        else:
            self.sync_locked = False

        if abs(delta) > hard_limit:
            self._seek_grace_until = time.time() + 1.5
            self.video_player.setPosition(a_pos)
            self.video_player.setPlaybackRate(1.0)
            logger.decision("Hard-Sync", f"Delta: {delta}ms", "Twardy reset klatki")
        elif delta > 250:
            self.video_player.setPlaybackRate(1.1)
        elif delta < -250:
            self.video_player.setPlaybackRate(0.9)
        else:
            self.video_player.setPlaybackRate(1.0)

    def _activate_sync_timer(self):
        if not self.sync_timer.isActive():
            self.sync_timer.start()

    def _deactivate_sync_timer(self):
        if self.sync_timer.isActive():
            self.sync_timer.stop()

    def load_and_play_video(self, force_mid_track=False):
        song = self.queue_mgr.current_song()
        if song:
            offline_path = self.video_download_manager.get_video_path(song.item_id)
            if offline_path:
                logger.decision("SMART VIDEO", "Znaleziono plik wideo offline", "Natychmiastowe ładowanie z dysku")
                self._activate_sync_timer()

                if force_mid_track:
                    self._sync_start_active = False
                    self.video_needs_sync_on_load = True
                elif getattr(self, '_is_new_track_starting', False):
                    self._sync_start_active = True
                    self._is_new_track_starting = False
                    self.video_needs_sync_on_load = False
                    self.sync_timeout_timer.start(6000)
                else:
                    self.video_needs_sync_on_load = True

                self._on_video_resolved(QUrl.fromLocalFile(offline_path).toString())
                return

        self._activate_sync_timer()
        self.yt_resolver.load_and_play_video(force_mid_track)

    def _prefetch_next(self):
        next_song = self.queue_mgr.next_song_item()
        if next_song:
            self.cache_manager.start_audio_download(next_song, is_prefetch=True)

    def _check_sync_start(self):
        if self._sync_start_active:
            if self._audio_loaded_for_sync:
                if self._video_loaded_for_sync:
                    self.sync_timeout_timer.stop()
                    self._sync_start_active = False
                    self._audio_loaded_for_sync = False
                    self._video_loaded_for_sync = False
                    self.current_engine_state = EngineState.PLAYING_SMOOTH
                    self.loading_changed.emit(False)
                    logger.decision("SYNC-START", "Audio i Wideo gotowe", "Jednoczesny start potoków A/V")
                    self.player.play()
                    self.video_player.play()

    def _map_status(self, s):
        if s == QMediaPlayer.MediaStatus.NoMedia:
            return "Brak mediów"
        if s == QMediaPlayer.MediaStatus.LoadingMedia:
            return "Ładowanie..."
        if s == QMediaPlayer.MediaStatus.LoadedMedia:
            return "Gotowe"
        if s == QMediaPlayer.MediaStatus.StalledMedia:
            return "Zacięcie (Brak danych!)"
        if s == QMediaPlayer.MediaStatus.BufferingMedia:
            return "Buforowanie..."
        if s == QMediaPlayer.MediaStatus.BufferedMedia:
            return "Odtwarzanie (Zbuforowano)"
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            return "Koniec"
        if s == QMediaPlayer.MediaStatus.InvalidMedia:
            return "Błąd strumienia"
        return "Nieznany"

    def _video_status_upd(self, s):
        self.video_status_str = self._map_status(s)
        self._evaluate_buffering()
        if s == QMediaPlayer.MediaStatus.LoadedMedia:
            if getattr(self, '_sync_start_active', False):
                self._video_loaded_for_sync = True
                self._check_sync_start()
            else:
                self.video_player.setPosition(self.player.position())
                self.video_player.setPlaybackRate(1.0)
                if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.video_player.play()
        elif s == QMediaPlayer.MediaStatus.InvalidMedia:
            if getattr(self, '_sync_start_active', False):
                self.sync_timeout_timer.stop()
                self._sync_start_active = False
                self.loading_changed.emit(False)
                if getattr(self, '_audio_loaded_for_sync', False):
                    self.player.play()

    def _on_video_playing_changed(self, is_playing):
        if is_playing:
            self.video_ready_to_show.emit()

    def _playback_state_changed(self, state):
        is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
        self.state_changed.emit(is_playing)
        self._evaluate_buffering()
        if is_playing:
            if self.video_player.source().isValid():
                self.video_player.play()
                self._activate_sync_timer()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.video_player.pause()
            self._deactivate_sync_timer()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.video_player.stop()
            self._deactivate_sync_timer()

    def _status_upd(self, s):
        if s != QMediaPlayer.MediaStatus.NoMedia:
            self.audio_status_str = self._map_status(s)
        self._evaluate_buffering()
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_looping:
                self.play_current()
            else:
                self.next_song()

    def set_volume(self, v):
        vol_float = (v / 100.0) ** 2
        self.audio_ctrl.set_volume(vol_float)
        APP_CONFIG["volume"] = v

    def play_list(self, songs, start_idx):
        self.queue_mgr.set_queue(songs, start_idx)
        self.play_current()

    def add_to_queue(self, song):
        self.queue_mgr.add(song)

    def clear_queue(self):
        if getattr(self, 'sync_timeout_timer', None):
            self.sync_timeout_timer.stop()
        if getattr(self, 'yt_cancel_event', None):
            self.yt_cancel_event.set()
        if getattr(self, 'prefetch_cancel_event', None):
            self.prefetch_cancel_event.set()

        self.queue_mgr.clear()
        self._sync_start_active = False
        self._audio_loaded_for_sync = False
        self._video_loaded_for_sync = False
        self._is_new_track_starting = False
        self.current_engine_state = EngineState.STOPPED
        self.loading_changed.emit(False)
        self.player.stop()
        self.player.setSource(QUrl(""))
        self.video_player.stop()
        self.video_player.setSource(QUrl(""))
        self.video_player.setPlaybackRate(1.0)
        self.has_video_signal.emit(False)
        self.current_yt_link = None
        self.video_killed_for_track = False
        self.prefetched_song_id = None
        self.prefetched_yt_url = None
        self.prefetched_yt_info_dict = None
        self._current_yt_info_dict = None
        self._deactivate_sync_timer()

    def shuffle_queue(self, new_songs):
        self.queue_mgr.shuffle(new_songs)
        if new_songs:
            self.play_current()

    def handle_queue_drop(self, old_idx, target_q_idx):
        self.queue_mgr.handle_drop(old_idx, target_q_idx)

    def queue_play_next(self, index):
        self.queue_mgr.play_next(index)

    def queue_remove(self, index):
        should_play, should_clear = self.queue_mgr.remove(index)
        if should_clear:
            self.clear_queue()
        elif should_play:
            self.play_current()

    def play_current(self):
        song = self.queue_mgr.current_song()
        if not song:
            return

        self._sync_start_active = False
        self._audio_loaded_for_sync = False
        self._video_loaded_for_sync = False
        self._is_new_track_starting = True

        self.current_video_resolution = self.arf_manager.prepare_track_resolution(
            self.player.position()
        )
        self.video_killed_for_track = False
        self.video_stream_start_time = time.time()
        self.h_sync_count = 0
        self.current_engine_state = EngineState.AUDIO_DOWNLOADING
        self.video_needs_sync_on_load = False

        self.resolve_id += 1
        self.loading_changed.emit(True)
        self.player.stop()
        self.player.setSource(QUrl(""))
        self.video_player.stop()
        self.video_player.setSource(QUrl(""))
        self.video_player.setPlaybackRate(1.0)
        self.last_resolve_time = 0

        if getattr(self, 'prefetched_song_id', None) == song.item_id:
            self._current_yt_info_dict = getattr(self, 'prefetched_yt_info_dict', None)
        else:
            self._current_yt_info_dict = None
            self.prefetched_song_id = None
            self.prefetched_yt_url = None
            self.prefetched_yt_info_dict = None

        yt_link = song.yt_link
        if not yt_link and hasattr(self, 'client') and self.client:
            from engine.header_tag_extractor import check_and_cache_remote_header
            yt_link = check_and_cache_remote_header(
                self.client, song, getattr(self, 'video_download_manager', None)
            )

        if yt_link:
            self.current_yt_link = yt_link
            self.has_video_signal.emit(True)
        else:
            self.current_yt_link = None
            self._deactivate_sync_timer()
            offline_path = self.video_download_manager.get_video_path(song.item_id)
            self.has_video_signal.emit(bool(offline_path))

        self.audio_status_str = "Pobieranie do cache..."
        self._evaluate_buffering()
        self.track_changed.emit(song)

        audio_offline_path = self.audio_download_manager.get_file_path(song.item_id)
        if audio_offline_path:
            self.audio_status_str = "Lokalny plik (Offline)"
            self.audio_track_cached.emit(song.item_id, audio_offline_path)
        else:
            self.cache_manager.start_audio_download(song, is_prefetch=False)

    def play_pause(self):
        if not self.queue:
            return
        if getattr(self, '_sync_start_active', False) or self.audio_status_str == "Ładowanie...":
            logger.decision("USER", "Manualna pauza", "Przerwanie synchronizacji i powrót do spoczynku")
            if getattr(self, 'sync_timeout_timer', None):
                self.sync_timeout_timer.stop()
            if getattr(self, 'yt_cancel_event', None):
                self.yt_cancel_event.set()
            if getattr(self, 'cancel_event', None):
                self.cancel_event.set()
            if getattr(self, 'prefetch_cancel_event', None):
                self.prefetch_cancel_event.set()
            self._sync_start_active = False
            self.loading_changed.emit(False)
            self.current_engine_state = EngineState.LOADING_ABORTED
            self.player.stop()
            self.video_player.stop()
            self._deactivate_sync_timer()
            return

        if self.idx == -1:
            if self.queue:
                self.idx = 0
                self.play_current()
                return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.video_player.pause()
            self._deactivate_sync_timer()
        else:
            self.player.play()
            self.video_player.play()
            if self.current_yt_link or self.video_download_manager.is_downloaded(getattr(self.queue_mgr.current_song(), 'item_id', '')):
                self._activate_sync_timer()

    def next_song(self):
        if self.queue_mgr.advance():
            self.play_current()

    def prev_song(self):
        if self.player.position() > 3000:
            self.player.setPosition(0)
            self.video_player.setPosition(0)
            self.video_player.setPlaybackRate(1.0)
        elif self.queue_mgr.previous():
            self.play_current()

    def skip_backward(self):
        if self.player.playbackState() in [
            QMediaPlayer.PlaybackState.PlayingState,
            QMediaPlayer.PlaybackState.PausedState
        ]:
            new_pos = max(0, self.player.position() - 10000)
            self.player.setPosition(new_pos)
            self.video_player.setPosition(new_pos)
            self.video_player.setPlaybackRate(1.0)

    def skip_forward(self):
        if self.player.playbackState() in [
            QMediaPlayer.PlaybackState.PlayingState,
            QMediaPlayer.PlaybackState.PausedState
        ]:
            new_pos = self.player.position() + 10000
            if self.player.duration() > 0:
                new_pos = min(self.player.duration(), new_pos)
            self.player.setPosition(new_pos)
            self.video_player.setPosition(new_pos)
            self.video_player.setPlaybackRate(1.0)

    def set_loop(self, state):
        self.queue_mgr.set_loop(state)

    def toggle_loop(self):
        return self.queue_mgr.toggle_loop()

    def set_shuffle(self, state):
        self.queue_mgr.set_shuffle(state)

    def toggle_shuffle(self):
        return self.queue_mgr.toggle_shuffle()

    def set_position(self, pos):
        self.player.setPosition(pos)
        self.video_player.setPosition(pos)
        self.video_player.setPlaybackRate(1.0)