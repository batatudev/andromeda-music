# core/logger.py
import os
os.environ["QT_API"] = "pyside6"

import threading
import csv
import shutil
import time
from datetime import datetime
from core.paths import PathsManager

class TelemetryRecorder:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryRecorder, cls).__new__(cls)
            cls._instance._init_recorder()
        return cls._instance

    def _init_recorder(self):
        self.log_file = PathsManager.get_logs_dir() / "navidrome-telemetry.csv"
        self.lock = threading.Lock()
        self.buffer = []

    def start_session(self, version):
        with self.lock:
            try:
                with open(self.log_file, "w", encoding="utf-8", newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Time", "Event", "State", "A_Pos", "V_Pos", "AV_Delta",
                        "Buf_Sec", "FPS", "Motion", "Vis_State", "ARF_Res",
                        "Z_FPS_Cyc", "Rate", "H_Sync_Count", "Grace", "Net_Link", "Loc_Lat", "Sync_Locked"
                    ])
            except Exception:
                pass

    def log_event(self, event_name, state, a_pos, v_pos, av_delta, buf_sec, fps, motion, vis_state, arf_res, z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked):
        self._write_row(event_name, state, a_pos, v_pos, av_delta, buf_sec, fps, motion, vis_state, arf_res, z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked)

    def log_heartbeat(self, state, a_pos, v_pos, av_delta, buf_sec, fps, motion, vis_state, arf_res, z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked):
        self._write_row("HRT", state, a_pos, v_pos, av_delta, buf_sec, fps, motion, vis_state, arf_res, z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked)

    def _write_row(self, event, state, a_pos, v_pos, av_delta, buf_sec, fps, motion, vis_state, arf_res, z_fps, rate, h_sync, grace, net_link, loc_lat, sync_locked):
        with self.lock:
            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            a_pos_str = f"{a_pos:.1f}" if isinstance(a_pos, (int, float)) else str(a_pos)
            v_pos_str = f"{v_pos:.1f}" if isinstance(v_pos, (int, float)) else str(v_pos)
            buf_sec_str = f"{buf_sec:.1f}" if isinstance(buf_sec, (int, float)) else str(buf_sec)
            motion_str = f"{motion:.2f}" if isinstance(motion, (int, float)) else str(motion)
            rate_str = f"{rate:.2f}" if isinstance(rate, (int, float)) else str(rate)
            row = [
                now, event, state, a_pos_str, v_pos_str, av_delta,
                buf_sec_str, fps, motion_str, vis_state, arf_res,
                z_fps, rate_str, h_sync, str(grace),
                "ONLINE" if net_link else "OFFLINE", loc_lat, str(sync_locked)
            ]
            self.buffer.append(row)
            if len(self.buffer) >= 5 or event != "HRT":
                self._flush_unlocked()

    def _flush_unlocked(self):
        if not self.buffer:
            return
        rows_to_write = list(self.buffer)
        self.buffer.clear()

        try:
            with open(self.log_file, "a", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows_to_write)
        except Exception:
            pass

    def flush(self):
        with self.lock:
            self._flush_unlocked()

    def export_to_desktop(self):
        self.flush()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            desktop = os.path.join(os.path.expanduser("~"), "Pulpit")
        if not os.path.exists(desktop):
            return "Błąd: Nie znaleziono folderu Pulpit / Desktop."
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(desktop, f"andromeda_telemetry_{timestamp}.csv")
        try:
            shutil.copy(self.log_file, dest)
            return f"Sukces! Plik zapisano:\n{os.path.basename(dest)}"
        except Exception as e:
            return f"Błąd eksportu: {e}"

telemetry_recorder = TelemetryRecorder()

class AppLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        self.log_file = PathsManager.get_logs_dir() / "andromeda-player-errors.log"
        self.lock = threading.Lock()
        self.last_msg = None
        self.count = 0
        self.session_logs = []

    def start_session(self, version):
        with self.lock:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header = f"========== START SESJI | Wersja: {version} | Data: {now} =========="
            self.session_logs.append(header)
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write("\n" + header + "\n")
            except Exception:
                pass

    def log(self, msg):
        with self.lock:
            if self.last_msg == msg:
                self.count += 1
            else:
                self._flush_unlocked()
                self.last_msg = msg
                self.count = 1

    def decision(self, tag, condition, action):
        msg = f"[{tag}] {condition} -> DECYZJA: {action}"
        self.log(msg)

    def flush(self):
        with self.lock:
            self._flush_unlocked()

    def _flush_unlocked(self):
        if self.last_msg is not None:
            now = datetime.now().strftime("%H:%M:%S")
            count_str = f" (Wystąpiło {self.count} razy)" if self.count > 1 else ""
            log_line = f"[{now}] {self.last_msg}{count_str}"
            self.session_logs.append(log_line)
            self.last_msg = None
            self.count = 0

            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_line + "\n")
            except Exception:
                pass

    def clear_logs(self):
        with self.lock:
            self.last_msg = None
            self.count = 0
            self.session_logs = []
            try:
                with open(self.log_file, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass

logger = AppLogger()