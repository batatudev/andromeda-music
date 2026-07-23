import os
os.environ["QT_API"] = "pyside6"

import time
from PySide6.QtCore import QObject, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from core.enums import TelemetryEvent
from utils import telemetry_recorder


class TelemetryService(QObject):
    def __init__(self, main_window):
        super().__init__()
        self._win = main_window
        self._tick_count = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        try:
            win = self._win
            engine = win.engine
            now_playing = win.now_playing_view
            network_monitor = win.network_monitor

            self._tick_count += 1
            state = engine.current_engine_state

            a_pos_ms = engine.player.position()
            v_pos_ms = engine.video_player.position()
            a_pos = a_pos_ms / 1000.0
            v_pos = v_pos_ms / 1000.0

            av_delta = 0
            if engine.video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                av_delta = abs(a_pos_ms - v_pos_ms)

            buf_sec = engine.get_buf_sec()
            fps = getattr(now_playing.video_widget, 'current_fps', 0)
            motion = round(getattr(now_playing.video_widget, 'last_motion_score', 0), 2)
            vis_state = "MASK" if getattr(win, '_current_mask_state', False) else "CLEAR"

            arf_res = getattr(engine, 'current_video_resolution', "1080p")
            z_fps = getattr(win, '_zero_fps_cycles', 0)
            rate = engine.video_player.playbackRate()
            h_sync = getattr(engine, 'h_sync_count', 0)
            grace = (time.time() < getattr(win, '_seek_grace_until', 0))
            net_link = getattr(network_monitor, 'is_online', True)
            loc_lat = getattr(network_monitor, 'loc_lat', 0)
            sync_locked = getattr(engine, 'sync_locked', False)

            event_name = TelemetryEvent.HEARTBEAT
            if win.force_telemetry_event:
                event_name = win.force_telemetry_event
                win.force_telemetry_event = None

            if event_name != TelemetryEvent.HEARTBEAT:
                telemetry_recorder.log_event(
                    event_name, state, a_pos, v_pos, av_delta,
                    buf_sec, fps, motion, vis_state, arf_res,
                    z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked
                )
                self._tick_count = 0
            elif self._tick_count >= 5:
                telemetry_recorder.log_heartbeat(
                    state, a_pos, v_pos, av_delta,
                    buf_sec, fps, motion, vis_state, arf_res,
                    z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked
                )
                self._tick_count = 0

        except Exception:
            pass
