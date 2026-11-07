import os
os.environ["QT_API"] = "pyside6"

import time
from PySide6.QtCore import QObject, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from core.enums import EngineState, TelemetryEvent
from utils import logger

class WatchdogService(QObject):
    def __init__(self, main_window):
        super().__init__()
        self._win = main_window

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._win.engine.state_changed.connect(self.check_monitoring)
        self._win.engine.has_video_signal.connect(self.check_monitoring)
        self._win.player_bar.video_toggle_requested.connect(self.check_monitoring)

    def stop(self):
        self._timer.stop()

    def check_monitoring(self, *args):
        win = self._win
        engine = win.engine
        player_bar = win.player_bar

        playing = (engine.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        is_paused = (engine.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
        has_video = bool(player_bar.btn_video_toggle.isChecked() and engine.current_yt_link)

        if (playing or is_paused) and has_video:
            if not self._timer.isActive():
                self._timer.start(500)
        else:
            if self._timer.isActive():
                self._timer.stop()
            if getattr(win, '_current_mask_state', False):
                win._current_mask_state = False
                win.now_playing_view.set_buffering_state(False)

    def _tick(self):
        win = self._win
        engine = win.engine
        player_bar = win.player_bar
        now_playing = win.now_playing_view
        network_monitor = win.network_monitor

        if getattr(player_bar, '_slider_is_pressed', False):
            return

        if not player_bar.btn_video_toggle.isChecked() or not engine.current_yt_link:
            self.check_monitoring()
            return

        playing = (engine.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        is_paused = (engine.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)

        if not playing and not is_paused:
            self.check_monitoring()
            return

        state_str = engine.current_engine_state
        needs_mask = False
        buf_pct = engine.video_player.bufferProgress() * 100
        buf_sec = engine.get_buf_sec()

        v_status = engine.video_player.mediaStatus()
        is_video_stalled = (v_status == QMediaPlayer.MediaStatus.StalledMedia)
        is_video_buffering = (v_status in [
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.LoadingMedia
        ])
        is_video_buffered = (
            v_status == QMediaPlayer.MediaStatus.BufferedMedia
            or v_status == QMediaPlayer.MediaStatus.LoadedMedia
        )

        fps = getattr(now_playing.video_widget, 'current_fps', 0.0)
        if not playing or is_video_stalled or is_video_buffering:
            fps = 0.0

        is_in_grace_period = playing and (time.time() < getattr(win, '_seek_grace_until', 0))

        if fps > 5:
            win._frames_with_movement += 1
        else:
            win._frames_with_movement = 0

        if EngineState.AUDIO_DOWNLOADING in state_str or EngineState.RESOLVING_YTDLP in state_str:
            needs_mask = True

        if player_bar.btn_video_toggle.isChecked() and engine.current_yt_link:
            is_offline = not getattr(network_monitor, 'is_online', True)

            if is_offline and playing:
                needs_mask = True
            elif is_in_grace_period:
                if is_video_stalled:
                    needs_mask = True
                else:
                    needs_mask = True
            elif is_video_stalled:
                needs_mask = True
            elif buf_sec <= 0.1 and playing and fps == 0 and not is_video_buffered:
                needs_mask = True
            elif (
                EngineState.BUFFERING in state_str
                or EngineState.RESOLVING_YTDLP in state_str
                or EngineState.ARF_REDUCTION in state_str
                or EngineState.VIDEO_DISABLED in state_str
                or EngineState.WAITING_VIDEO_SYNC in state_str
            ):
                needs_mask = True
            elif fps == 0 and buf_pct < 100 and playing and not is_video_buffered:
                win._zero_fps_cycles = getattr(win, '_zero_fps_cycles', 0) + 1
                if win._zero_fps_cycles > 3:
                    needs_mask = True
            else:
                win._zero_fps_cycles = 0

            if playing and not is_in_grace_period:
                a_pos = engine.player.position()
                v_pos = engine.video_player.position()
                if abs(a_pos - v_pos) > 1500 and fps == 0 and not is_video_buffered:
                    needs_mask = True

        if playing and win._frames_with_movement > 3:
            needs_mask = False

        current_mask = getattr(win, '_current_mask_state', False)

        if needs_mask and not current_mask:
            win._current_mask_state = True
            if win._frames_with_movement > 0:
                win._current_mask_state = False
            else:
                win.force_telemetry_event = TelemetryEvent.MASK_ON
                now_playing.set_buffering_state(True)

        elif not needs_mask and current_mask:
            if player_bar.btn_video_toggle.isChecked() and engine.current_yt_link:
                if fps > 0 or is_video_buffered or (is_paused and buf_pct > 0):
                    win._current_mask_state = False
                    logger.decision("WATCHDOG", "System odzyskał wiarygodność", "Zdejmuję Mgłę Maskującą")
                    win.force_telemetry_event = TelemetryEvent.MASK_OFF
                    now_playing.set_buffering_state(False)
            else:
                win._current_mask_state = False
                win.force_telemetry_event = TelemetryEvent.MASK_OFF
                now_playing.set_buffering_state(False)