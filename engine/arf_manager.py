import os
os.environ["QT_API"] = "pyside6"


import time
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import QUrl
from config import APP_CONFIG
from utils import logger
from core.enums import EngineState, VideoResolution

class ARFManager:
    def __init__(self, engine):
        self.engine = engine

    def evaluate_arf(self):
        if getattr(self.engine, 'video_killed_for_track', False):
            return
        if not APP_CONFIG.get("video_auto_res", True):
            return
        if not self.engine.current_yt_link:
            return
        if not self.engine.video_player.source().isValid():
            return
        current_time = time.time()
        if (current_time - getattr(self.engine, 'video_stream_start_time', current_time)) < 10.0:
            return
        buf_sec = self.engine.get_buf_sec()
        buf_pct = self.engine.video_player.bufferProgress() * 100
        if buf_pct >= 99:
            self.engine.arf_drop_ticks = 0
            self.engine.arf_last_buffer_sec = buf_sec
            return
        if buf_sec < self.engine.arf_last_buffer_sec:
            if buf_sec < 10.0:
                self.engine.arf_drop_ticks += 1
        else:
            self.engine.arf_drop_ticks = 0
        self.engine.arf_last_buffer_sec = buf_sec
        if self.engine.arf_drop_ticks >= 8:
            if buf_sec < 5.0:
                logger.decision("ARF 3.1", f"Wykryto drastyczny spadek bufora ({buf_sec:.1f}s)", "Planuję degradację jakości.")
                self.engine.arf_pending_downgrade = True
                self.engine.arf_drop_ticks = 0
        v_status = self.engine.video_player.mediaStatus()
        if v_status in [QMediaPlayer.MediaStatus.BufferingMedia, QMediaPlayer.MediaStatus.StalledMedia, QMediaPlayer.MediaStatus.LoadingMedia]:
            self.engine.arf_drop_ticks += 2
            if self.engine.arf_drop_ticks >= 15:
                self.trigger_hard_arf()

    def trigger_hard_arf(self):
        res_order = [VideoResolution.RES_1080P, VideoResolution.RES_720P, VideoResolution.RES_480P, VideoResolution.RES_240P]
        try:
            idx = res_order.index(self.engine.arf_active_res)
            min_res = APP_CONFIG.get("video_min_res", VideoResolution.RES_480P)
            min_idx = res_order.index(min_res)
        except ValueError:
            idx = 0
            min_idx = 3
        if idx < min_idx:
            self.engine.arf_active_res = res_order[idx + 1]
            self.engine.current_engine_state = f"{EngineState.ARF_REDUCTION}: {self.engine.arf_active_res}"
            logger.decision("ARF 3.1", "Twarde zacięcie strumienia", f"Natychmiastowa redukcja do {self.engine.arf_active_res}")
            self.engine.arf_success_streak = 0
            self.engine.arf_pending_downgrade = False
            self.engine.arf_drop_ticks = 0
            self.engine.current_video_resolution = self.engine.arf_active_res
            self.engine.resolve_id += 1
            self.engine.video_player.stop()
            self.engine.video_player.setSource(QUrl(""))
            self.engine.yt_resolver.load_and_play_video(force_mid_track=True)
        else:
            logger.decision("ARF 3.1", "Osiągnięto limit minimalnej jakości wideo", "Wideo wyłączone (Video Kill-Switch)")
            self.kill_video_stream()

    def kill_video_stream(self):
        self.engine.video_killed_for_track = True
        self.engine.current_engine_state = EngineState.VIDEO_DISABLED
        self.engine.video_player.stop()
        self.engine.video_player.setSource(QUrl(""))
        self.engine.has_video_signal.emit(False)
