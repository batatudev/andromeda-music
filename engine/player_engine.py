import os
os.environ["QT_API"] = "pyside6"

import random
import threading
import time
import requests
from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from config import APP_CONFIG
from utils import logger, telemetry_recorder
from core.enums import EngineState, VideoResolution

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False
    logger.log("Brak biblioteki yt-dlp! Funkcja wideo będzie wyłączona.")
    print("Brak biblioteki yt-dlp! Funkcja wideo będzie wyłączona. Uruchom: pip install yt-dlp")



from engine.cache_manager import CacheManager
from engine.arf_manager import ARFManager
from engine.yt_resolver import YTResolver
from engine.video_download_manager import VideoDownloadManager

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
        from engine.audio_controller import AudioController
        from engine.video_controller_online import VideoControllerOnline

        self.audio_ctrl = AudioController(self)
        self.player = self.audio_ctrl.player
        self.audio_output = self.audio_ctrl.audio_output

        self.video_ctrl = VideoControllerOnline(self)
        self.video_player = self.video_ctrl.player
        self.video_audio = self.video_ctrl._audio_output

        self.queue =[]
        self.idx = -1
        
        # Managers
        self.cache_manager = CacheManager(self)
        self.arf_manager = ARFManager(self)
        self.yt_resolver = YTResolver(self)
        self.video_download_manager = VideoDownloadManager()
        
        from engine.audio_download_manager import AudioDownloadManager
        self.audio_download_manager = AudioDownloadManager(self.client)

        self.is_looping = False
        self.is_shuffled = False
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

        from core.paths import PathsManager
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
        # Timer startowany dopiero gdy wideo jest aktywne (_activate_sync_timer)
        # Zatrzymywany gdy wideo jest wyczyszczone (_deactivate_sync_timer)

        self.media_devices = QMediaDevices(self)

        default_out = self.media_devices.defaultAudioOutput()
        if not default_out.isNull():
            self.current_audio_device_id = default_out.id().data()
        else:
            self.current_audio_device_id = b''

        self.media_devices.audioOutputsChanged.connect(self._check_audio_device)
        self.audio_check_timer = QTimer(self)
        self.audio_check_timer.timeout.connect(self._check_audio_device)
        self.audio_check_timer.start(2000)

        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.mediaStatusChanged.connect(self._status_upd)
        self.video_player.mediaStatusChanged.connect(self._video_status_upd)
        self.player.playbackStateChanged.connect(self._playback_state_changed)

        self.video_ready.connect(self._on_video_resolved)
        self.video_player.playingChanged.connect(self._on_video_playing_changed)

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
        buffering_states =[
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
        if self.queue and self.idx != -1 and self.queue[self.idx].item_id == song_id:
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
        from PySide6.QtMultimedia import QMediaPlayer
        if getattr(self, 'video_killed_for_track', False):
            return
        if getattr(self, '_sync_start_active', False):
            return
        if not self.video_player.source().isValid():
            return

        v_status = self.video_player.mediaStatus()
        if v_status in [QMediaPlayer.MediaStatus.BufferingMedia,
                        QMediaPlayer.MediaStatus.LoadingMedia,
                        QMediaPlayer.MediaStatus.StalledMedia]:
            return

        if time.time() < getattr(self, '_seek_grace_until', 0):
            return
            
        a_state = self.player.playbackState()
        
        if a_state != QMediaPlayer.PlaybackState.PlayingState:
            if self.video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.video_player.pause()
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
            from utils import logger
            logger.decision("Hard-Sync", f"Delta: {delta}ms", "Twardy reset klatki")
        elif delta > 250:
            self.video_player.setPlaybackRate(1.1)
        elif delta < -250:
            self.video_player.setPlaybackRate(0.9)
        else:
            self.video_player.setPlaybackRate(1.0)

    def _activate_sync_timer(self):
        """Uruchamia sync_timer gdy wideo jest aktywne."""
        if not self.sync_timer.isActive():
            self.sync_timer.start()

    def _deactivate_sync_timer(self):
        """Wstrzymuje sync_timer gdy nie ma aktywnego wideo."""
        if self.sync_timer.isActive():
            self.sync_timer.stop()

    def load_and_play_video(self, force_mid_track=False):
        # Najpierw sprawdzamy offline
        if self.queue and self.idx >= 0:
            song = self.queue[self.idx]
            offline_path = self.video_download_manager.get_video_path(song.item_id)
            if offline_path:
                from utils import logger
                from PySide6.QtCore import QUrl
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
        if self.idx >= 0:
            if self.idx + 1 < len(self.queue):
                next_song = self.queue[self.idx + 1]
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
                    from utils import logger
                    logger.decision("SYNC-START", "Audio i Wideo gotowe", "Jednoczesny start potoków A/V")
                    self.player.play()
                    self.video_player.play()

    def _map_status(self, s):
        from PySide6.QtMultimedia import QMediaPlayer
        if s == QMediaPlayer.MediaStatus.NoMedia: return "Brak mediów"
        if s == QMediaPlayer.MediaStatus.LoadingMedia: return "Ładowanie..."
        if s == QMediaPlayer.MediaStatus.LoadedMedia: return "Gotowe"
        if s == QMediaPlayer.MediaStatus.StalledMedia: return "Zacięcie (Brak danych!)"
        if s == QMediaPlayer.MediaStatus.BufferingMedia: return "Buforowanie..."
        if s == QMediaPlayer.MediaStatus.BufferedMedia: return "Odtwarzanie (Zbuforowano)"
        if s == QMediaPlayer.MediaStatus.EndOfMedia: return "Koniec"
        if s == QMediaPlayer.MediaStatus.InvalidMedia: return "Błąd strumienia"
        return "Nieznany"

    def _video_status_upd(self, s):
        from PySide6.QtMultimedia import QMediaPlayer
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

    def _check_audio_device(self):
        default_device = self.media_devices.defaultAudioOutput()
        if default_device.isNull():
            return
        new_id = default_device.id().data()
        if new_id != self.current_audio_device_id:
            self.current_audio_device_id = new_id
            self._apply_new_audio_device(default_device)

    def _apply_new_audio_device(self, device):
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        pos = self.player.position()
        if was_playing:
            self.player.pause()
            self.video_player.pause()
        vol = self.audio_output.volume()
        self.player.setAudioOutput(None)
        self.video_player.setAudioOutput(None)
        if self.audio_output:
            self.audio_output.deleteLater()
        if self.video_audio:
            self.video_audio.deleteLater()
        self.audio_output = QAudioOutput(self)
        self.audio_output.setDevice(device)
        self.audio_output.setVolume(vol)
        self.player.setAudioOutput(self.audio_output)
        self.video_audio = QAudioOutput(self)
        self.video_audio.setDevice(device)
        self.video_audio.setMuted(True)
        self.video_player.setAudioOutput(self.video_audio)
        if was_playing:
            self.player.setPosition(pos)
            self.video_player.setPosition(pos)
            self.player.play()
            self.video_player.play()

    def _playback_state_changed(self, state):
        from PySide6.QtMultimedia import QMediaPlayer
        is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
        self.state_changed.emit(is_playing)
        self._evaluate_buffering()
        if is_playing:
            if self.video_player.source().isValid():
                self.video_player.play()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.video_player.pause()

    def _status_upd(self, s):
        from PySide6.QtMultimedia import QMediaPlayer
        if s != QMediaPlayer.MediaStatus.NoMedia:
            self.audio_status_str = self._map_status(s)
        self._evaluate_buffering()
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_looping:
                self.play_current()
            else:
                self.next_song()

    def set_volume(self, v):
        self.audio_output.setVolume(v / 100)
        APP_CONFIG["volume"] = v

    def play_list(self, songs, start_idx):
        self.queue = list(songs)
        self.idx = start_idx
        self.play_current()
        self.queue_updated.emit()

    def add_to_queue(self, song):
        self.queue.append(song)
        self.queue_updated.emit()

    def clear_queue(self):
        from PySide6.QtCore import QUrl
        if getattr(self, 'sync_timeout_timer', None):
            self.sync_timeout_timer.stop()
        if getattr(self, 'yt_cancel_event', None):
            self.yt_cancel_event.set()
        if getattr(self, 'prefetch_cancel_event', None):
            self.prefetch_cancel_event.set()
            
        self.queue = []
        self.idx = -1
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
        self.queue_cleared.emit()

    def shuffle_queue(self, new_songs):
        if new_songs:
            self.play_list(new_songs, 0)

    def handle_queue_drop(self, old_idx, target_q_idx):
        if old_idx == target_q_idx or old_idx == target_q_idx - 1:
            return
        song = self.queue.pop(old_idx)
        if old_idx < target_q_idx:
            target_q_idx -= 1
        self.queue.insert(target_q_idx, song)
        if self.idx == old_idx:
            self.idx = target_q_idx
        elif old_idx < self.idx <= target_q_idx:
            self.idx -= 1
        elif target_q_idx <= self.idx < old_idx:
            self.idx += 1
        self.queue_updated.emit()

    def queue_play_next(self, index):
        if self.idx < 0:
            target_idx = 0
        else:
            target_idx = self.idx + 1
        if index == target_idx or index == self.idx:
            return
        song = self.queue.pop(index)
        if index < target_idx:
            target_idx -= 1
        self.queue.insert(target_idx, song)
        if self.idx == index:
            self.idx = target_idx
        elif index < self.idx <= target_idx:
            self.idx -= 1
        elif target_idx <= self.idx < index:
            self.idx += 1
        self.queue_updated.emit()

    def queue_remove(self, index):
        if 0 <= index < len(self.queue):
            if index < self.idx:
                self.queue.pop(index)
                self.idx -= 1
            elif index == self.idx:
                self.queue.pop(index)
                if len(self.queue) == 0:
                    self.clear_queue()
                    return
                else:
                    if self.idx >= len(self.queue):
                        self.clear_queue()
                        return
                    else:
                        self.play_current()
            else:
                self.queue.pop(index)
            self.queue_updated.emit()

    def play_current(self):
        import time
        from PySide6.QtCore import QUrl
        from utils import logger
        
        if 0 <= self.idx < len(self.queue):
            song = self.queue[self.idx]
            self._sync_start_active = False
            self._audio_loaded_for_sync = False
            self._video_loaded_for_sync = False
            self._is_new_track_starting = True
            
            if getattr(self, 'player', None):
                if self.player.position() > 30000:
                    if self.arf_drop_ticks == 0:
                        if getattr(self, 'arf_pending_downgrade', False) == False:
                            self.arf_success_streak += 1
                    else:
                        self.arf_success_streak = 0
                        
            current_base_res = APP_CONFIG.get("video_resolution", VideoResolution.RES_1080P)
            current_min_res = APP_CONFIG.get("video_min_res", VideoResolution.RES_480P)
            
            if getattr(self, '_last_base_res', None) != current_base_res or getattr(self, '_last_min_res', None) != current_min_res:
                self.arf_active_res = current_base_res
                self.arf_success_streak = 0
                self.arf_pending_downgrade = False
                self._last_base_res = current_base_res
                self._last_min_res = current_min_res
                logger.decision("ARF 3.1", "Wykryto zmianę ustawień wideo", f"Reset ARF do {current_base_res}")

            res_order = [VideoResolution.RES_1080P, VideoResolution.RES_720P, VideoResolution.RES_480P, VideoResolution.RES_240P]
            try:
                base_idx = res_order.index(current_base_res)
                min_idx = res_order.index(current_min_res)
                if min_idx < base_idx:
                    min_idx = base_idx
                    
                active_idx = res_order.index(self.arf_active_res)
                
                if active_idx < base_idx:
                    active_idx = base_idx
                    self.arf_active_res = res_order[active_idx]
                elif active_idx > min_idx:
                    active_idx = min_idx
                    self.arf_active_res = res_order[active_idx]
                    
                if getattr(self, 'arf_pending_downgrade', False):
                    if active_idx < min_idx:
                        self.arf_active_res = res_order[active_idx + 1]
                        logger.decision("ARF 3.1", "Aplikowanie zaplanowanej redukcji jakości", f"Nowa rozdzielczość: {self.arf_active_res}")
                    self.arf_pending_downgrade = False
                    self.arf_success_streak = 0
                elif getattr(self, 'arf_success_streak', 0) >= 2:
                    if active_idx > base_idx:
                        self.arf_active_res = res_order[active_idx - 1]
                        logger.decision("ARF 3.1", "Sieć stabilna przez 2 utwory", f"Zwiększam jakość: {self.arf_active_res}")
                    self.arf_success_streak = 0
            except ValueError:
                self.arf_active_res = current_base_res

            self.arf_drop_ticks = 0
            self.current_video_resolution = self.arf_active_res
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
            if yt_link:
                self.current_yt_link = yt_link
                self.has_video_signal.emit(True)
            else:
                self.current_yt_link = None
                self._deactivate_sync_timer()
                # Sprawdz czy mamy plik offline - jeśli tak, wideo nadal jest dostępne
                offline_path = self.video_download_manager.get_video_path(song.item_id)
                if offline_path:
                    self.has_video_signal.emit(True)
                else:
                    self.has_video_signal.emit(False)
                
            self.audio_status_str = "Pobieranie do cache..."
            self._evaluate_buffering()
            self.track_changed.emit(song)
            
            # Najpierw sprawdzamy, czy plik jest zapisany przez AudioDownloadManager (Offline)
            audio_offline_path = self.audio_download_manager.get_file_path(song.item_id)
            if audio_offline_path:
                self.audio_status_str = "Lokalny plik (Offline)"
                self.audio_track_cached.emit(song.item_id, audio_offline_path)
            else:
                self.cache_manager.start_audio_download(song, is_prefetch=False)
            
            # Smart Video Mode obsługiwany jest teraz w głównym widoku (UI), co eliminuje podwójne zlecenia odtwarzania.

    def play_pause(self):
        from PySide6.QtMultimedia import QMediaPlayer
        from utils import logger
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
            return

        if self.idx == -1:
            if self.queue:
                self.idx = 0
                self.play_current()
                return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.video_player.pause()
        else:
            self.player.play()
            self.video_player.play()

    def next_song(self):
        if self.idx < len(self.queue) - 1:
            self.idx += 1
            self.play_current()

    def prev_song(self):
        if self.player.position() > 3000:
            self.player.setPosition(0)
            self.video_player.setPosition(0)
            self.video_player.setPlaybackRate(1.0)
        elif self.idx > 0:
            self.idx -= 1
            self.play_current()

    def skip_backward(self):
        from PySide6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]:
            new_pos = max(0, self.player.position() - 10000)
            self.player.setPosition(new_pos)
            self.video_player.setPosition(new_pos)
            self.video_player.setPlaybackRate(1.0)

    def skip_forward(self):
        from PySide6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() in [QMediaPlayer.PlaybackState.PlayingState, QMediaPlayer.PlaybackState.PausedState]:
            new_pos = self.player.position() + 10000
            if self.player.duration() > 0:
                new_pos = min(self.player.duration(), new_pos)
            self.player.setPosition(new_pos)
            self.video_player.setPosition(new_pos)
            self.video_player.setPlaybackRate(1.0)

    def set_loop(self, state):
        if self.is_looping != state:
            self.is_looping = state
            self.loop_mode_changed.emit(self.is_looping)

    def toggle_loop(self):
        self.set_loop(not self.is_looping)
        return self.is_looping

    def set_shuffle(self, state):
        if self.is_shuffled != state:
            self.is_shuffled = state
            if self.is_shuffled:
                if self.queue:
                    if len(self.queue) > 1:
                        if 0 <= self.idx < len(self.queue):
                            current_song = self.queue[self.idx]
                            q_copy = self.queue[:]
                            q_copy.pop(self.idx)
                            import random
                            random.shuffle(q_copy)
                            self.queue = [current_song] + q_copy
                            self.idx = 0
                            self.queue_updated.emit()
            self.shuffle_mode_changed.emit(self.is_shuffled)

    def toggle_shuffle(self):
        self.set_shuffle(not self.is_shuffled)
        return self.is_shuffled

    def set_position(self, pos):
        self.player.setPosition(pos)
        self.video_player.setPosition(pos)
        self.video_player.setPlaybackRate(1.0)
