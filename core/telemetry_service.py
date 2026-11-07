import os
os.environ["QT_API"] = "pyside6"

import time
import threading
from PySide6.QtCore import QObject, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QMediaMetaData
from config import APP_CONFIG
from core.enums import TelemetryEvent
from utils import telemetry_recorder

def get_telemetry(win=None) -> dict:
    if win is None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if hasattr(w, 'engine') and hasattr(w, 'now_playing_view'):
                    win = w
                    break

    if win is None:
        return {}

    engine = getattr(win, 'engine', None)
    now_playing = getattr(win, 'now_playing_view', None)
    network_monitor = getattr(win, 'network_monitor', None)
    loader = getattr(win, 'loader', None)
    v_mgr = getattr(engine, 'video_download_manager', None) if engine else None
    vw = getattr(now_playing, 'video_widget', None) if now_playing else None

    is_online = getattr(network_monitor, 'is_online', True)
    net_ping = getattr(network_monitor, 'net_ping', 0)
    loc_lat = getattr(network_monitor, 'loc_lat', 0)

    net_link_str = "ONLINE" if is_online else "OFFLINE"
    net_ping_str = f"{net_ping} ms" if net_ping > 0 else "Brak"
    loc_lat_str = f"{loc_lat} ms" if loc_lat > 0 else "Brak"

    state_str = getattr(engine, 'current_engine_state', "STOPPED")
    sync_lock_str = "ZABLOKOWANY" if getattr(engine, 'sync_locked', False) else "Stabilny"

    a_pos_ms = engine.player.position() if engine else 0
    v_pos_ms = engine.video_player.position() if engine else 0
    is_v_playing = (engine.video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState) if engine else False
    is_v_paused = (engine.video_player.playbackState() == QMediaPlayer.PlaybackState.PausedState) if engine else False
    av_sync_str = f"{abs(a_pos_ms - v_pos_ms)} ms" if is_v_playing else "0 ms"

    rate_val = engine.video_player.playbackRate() if engine else 1.0
    rate_str = f"{rate_val:.2f}x"
    h_sync_str = str(getattr(engine, 'h_sync_count', 0))

    is_grace = time.time() < getattr(win, '_seek_grace_until', 0)
    grace_str = "AKTYWNY" if is_grace else "NIEAKTYWNY"

    buf_sec = engine.get_buf_sec() if engine else 0.0
    v_health_str = f"{buf_sec:.1f} s"

    meta = engine.video_player.metaData() if engine else None
    if meta is not None and vw is not None:
        if not vw.actual_resolution:
            v_res = meta.value(QMediaMetaData.Key.Resolution)
            if v_res and hasattr(v_res, 'width') and v_res.width() > 0:
                vw.actual_video_width = v_res.width()
                vw.actual_video_height = v_res.height()
                vw.actual_resolution = f"{v_res.width()}x{v_res.height()}"

        v_fps = meta.value(QMediaMetaData.Key.VideoFrameRate)
        if v_fps is not None:
            try:
                v_fps_float = float(v_fps)
                if v_fps_float > 0:
                    vw.current_fps = v_fps_float
            except Exception:
                pass

    actual_res = getattr(vw, 'actual_resolution', '')
    if actual_res:
        res_act_str = actual_res
    else:
        if engine and is_v_playing:
            res_act_str = f"Wykrywanie ({engine.current_video_resolution})"
        else:
            res_act_str = "Brak"

    v_status = engine.video_player.mediaStatus() if engine else QMediaPlayer.MediaStatus.NoMedia
    is_buffering_or_stalled = v_status in [
        QMediaPlayer.MediaStatus.BufferingMedia,
        QMediaPlayer.MediaStatus.LoadingMedia,
        QMediaPlayer.MediaStatus.StalledMedia
    ]

    if is_v_playing and not is_buffering_or_stalled:
        fps_val = getattr(vw, 'current_fps', 0.0)
        fps_str = f"{fps_val:.1f} FPS" if fps_val > 0 else "25.0 FPS"
        motion_str = "1.00"
    else:
        fps_str = "0.0 FPS"
        motion_str = "0.00"

    z_fps_str = str(getattr(win, '_zero_fps_cycles', 0))

    target_res = APP_CONFIG.get("video_resolution", "1080p")
    target_fps = APP_CONFIG.get("video_fps", "60")
    res_conf_str = f"{target_res} ({target_fps} FPS)"

    if engine and (is_v_playing or is_v_paused):
        source_url = engine.video_player.source()
        is_local = source_url.isLocalFile() if hasattr(source_url, 'isLocalFile') else False
        suffix = " (Wstrzymany)" if is_v_paused else ""

        if is_local:
            v_source_str = f"OFFLINE (Dysk){suffix}"
        elif getattr(engine, 'last_resolve_time', 0) == 0:
            v_source_str = f"ONLINE (Prefetch RAM){suffix}"
        else:
            v_source_str = f"ONLINE (W locie){suffix}"
    elif engine and getattr(engine, 'current_yt_link', None):
        v_source_str = "Ładowanie..."
    else:
        v_source_str = "Brak / Wyłączone"

    is_masked = getattr(win, '_current_mask_state', False)
    filter_str = "MASKA (Aktywna)" if is_masked else "CZYSTY (Widoczny)"

    resolve_ms = getattr(engine, 'last_resolve_time', 0)
    resolve_str = f"{resolve_ms} ms"

    v_buf_str = getattr(engine, 'video_status_str', "Brak")
    a_buf_str = getattr(engine, 'audio_status_str', "Brak")

    q_len = len(getattr(loader, 'queue', [])) if loader else 0
    ram_len = len(getattr(loader, '_ram_cache', {})) if loader else 0
    img_q_str = f"{q_len} w kolejce / {ram_len} w RAM"

    threads_str = f"{threading.active_count()} aktywnych"
    arf_auto = APP_CONFIG.get("video_auto_res", True)
    arf_profile_str = f"ARF 3.1 ({'Auto' if arf_auto else 'Manual'})"

    drop_rate_str = f"{getattr(engine, 'arf_drop_ticks', 0)} ticks"
    recoveries_str = f"{getattr(engine, 'arf_success_streak', 0)} stabilnych"

    cur_task = getattr(v_mgr, 'current_download_task', None) if v_mgr else None
    dl_active_str = str(cur_task) if cur_task else "Brak"
    dl_queue_str = str(v_mgr.download_queue.qsize()) if v_mgr else "0"
    dl_speed_str = "Aktywne pobieranie" if cur_task else "Bezczynny"
    dl_health_str = ("Wstrzymany (Snooze)" if v_mgr.is_snoozed else "Sprawny (Gotowy)") if v_mgr else "Niedostępny"

    return {
        "net_link": net_link_str,
        "net_ping": net_ping_str,
        "loc_lat": loc_lat_str,
        "state": state_str,
        "sync_lock": sync_lock_str,
        "av_sync": av_sync_str,
        "rate": rate_str,
        "h_sync": h_sync_str,
        "grace": grace_str,
        "v_health": v_health_str,
        "v_source": v_source_str,
        "fps": fps_str,
        "z_fps": z_fps_str,
        "res_conf": res_conf_str,
        "res_act": res_act_str,
        "motion": motion_str,
        "filter": filter_str,
        "resolve": resolve_str,
        "v_buf": v_buf_str,
        "a_buf": a_buf_str,
        "img_q": img_q_str,
        "threads": threads_str,
        "arf_profile": arf_profile_str,
        "drop_rate": drop_rate_str,
        "recoveries": recoveries_str,
        "dl_active": dl_active_str,
        "dl_queue": dl_queue_str,
        "dl_speed": dl_speed_str,
        "dl_health": dl_health_str
    }

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
            fps = getattr(now_playing.video_widget, 'current_fps', 0.0)
            motion = round(getattr(now_playing.video_widget, 'last_motion_score', 0.0), 2)
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