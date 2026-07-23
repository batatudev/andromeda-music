# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: utils.py
# OPIS ZMIAN: Stworzenie permanentnego cache'u okładek (odpornego na losowe tokeny URL).
import os
os.environ["QT_API"] = "pyside6"
import threading
import csv
import shutil
import time
import socket
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from PySide6.QtCore import QObject, QRunnable, QUrl, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QNetworkDiskCache
from core.paths import PathsManager

from core.models import MediaItem, Song, Album, Artist

_YT_LINK_OVERRIDES: dict = {}

def _set_yt_link_override(item_id: str, url):
    if url:
        _YT_LINK_OVERRIDES[item_id] = url
    else:
        _YT_LINK_OVERRIDES.pop(item_id, None)

class NetworkMonitor(threading.Thread):
    def __init__(self, local_url):
        super().__init__(daemon=True)
        self.local_host, self.local_port = self._extract_host_and_port(local_url)
        self.is_online = False 
        self.net_ping = 0
        self.loc_lat = 0
        self._running = True

    def _extract_host_and_port(self, url):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 4533
            return host, port
        except Exception:
            return "localhost", 4533

    def run(self):
        while self._running:
            start = time.time()
            try:
                socket.create_connection(("1.1.1.1", 53), timeout=2)
                self.net_ping = int((time.time() - start) * 1000)
                self.is_online = True
            except Exception:
                self.net_ping = -1
                self.is_online = False

            if self.local_host:
                start = time.time()
                try:
                    socket.create_connection((self.local_host, self.local_port), timeout=1)
                    self.loc_lat = int((time.time() - start) * 1000)
                except Exception:
                    self.loc_lat = -1

            time.sleep(2)

    def stop(self):
        self._running = False

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
        self.buffer =[]

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
            row =[
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
        try:
            with open(self.log_file, "a", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerows(self.buffer)
            self.buffer.clear()
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
        dest = os.path.join(desktop, f"navidrome_telemetry_v13.0_{timestamp}.csv")
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
        self.log_file = PathsManager.get_logs_dir() / "navidrome-player-errors.log"
        self.lock = threading.Lock()
        self.last_msg = None
        self.count = 0
        self.session_logs =[]

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
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_line + "\n")
            except Exception:
                pass
            self.last_msg = None
            self.count = 0

    def clear_logs(self):
        with self.lock:
            self.last_msg = None
            self.count = 0
            self.session_logs =[]
            try:
                with open(self.log_file, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass

logger = AppLogger()

class Worker(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.setAutoDelete(True)

    def run(self):
        self.fn()

class AsyncImageLoader(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.disk_cache = QNetworkDiskCache(self)
        cp = PathsManager.get_cache_dir() / "images"
        cp.mkdir(parents=True, exist_ok=True)
        self.disk_cache.setCacheDirectory(str(cp))
        self.manager.setCache(self.disk_cache)

        self.custom_artists_dir = PathsManager.get_data_dir() / "custom_artists"
        self.custom_artists_dir.mkdir(parents=True, exist_ok=True)

        self.custom_covers_dir = PathsManager.get_data_dir() / "custom_covers"
        self.custom_covers_dir.mkdir(parents=True, exist_ok=True)
        
        # PERMANENTNY CACHE OFFLINE
        self.covers_cache_dir = PathsManager.get_cache_dir() / "covers"
        self.covers_cache_dir.mkdir(parents=True, exist_ok=True)

        self.queue =[]
        self.active_reqs = 0
        self.MAX_ACTIVE = 10
        self._in_flight = {}

    def load(self, url, target):
        if not url:
            return
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if 'id' in qs:
                cover_id = qs['id'][0]
                # 1. Najpierw sprawdzamy nadpisane okładki
                for ext in ['.jpg', '.jpeg', '.png']:
                    artist_path = os.path.join(self.custom_artists_dir, f"{cover_id}{ext}")
                    if os.path.exists(artist_path):
                        pix = QPixmap(artist_path)
                        if target:
                            target.set_image(pix, animate=False)
                        return

                    cover_path = os.path.join(self.custom_covers_dir, f"{cover_id}{ext}")
                    if os.path.exists(cover_path):
                        pix = QPixmap(cover_path)
                        if target:
                            target.set_image(pix, animate=False)
                        return
                
                # 2. Sprawdzamy nasz permanentny cache okładek
                cached_path = os.path.join(self.covers_cache_dir, f"{cover_id}.jpg")
                if os.path.exists(cached_path):
                    pix = QPixmap(cached_path)
                    if target:
                        target.set_image(pix, animate=False)
                    return
        except Exception:
            pass

        if url in self._in_flight:
            if target not in self._in_flight[url]:
                self._in_flight[url].append(target)
            return

        self.queue.append((url, target))
        self._process()

    def _process(self):
        while self.queue and self.active_reqs < self.MAX_ACTIVE:
            url, target = self.queue.pop(0)
            try:
                if target is None:
                    continue
            except RuntimeError:
                continue
            self._in_flight[url] = [target]
            self.active_reqs += 1
            req = QNetworkRequest(QUrl(url))
            reply = self.manager.get(req)
            reply.setProperty("url", url)
            reply.setProperty("start_time", time.time())
            reply.finished.connect(self._done)

    def _done(self):
        self.active_reqs -= 1
        reply = self.sender()
        url = reply.property("url")
        start_time = reply.property("start_time")
        duration = time.time() - start_time
        is_fast_cache = (duration < 0.05)
        targets = self._in_flight.pop(url, [])

        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pix = QPixmap()
            pix.loadFromData(data)
            
            # Zapisz pobrany obrazek do permanentnego cache
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                if 'id' in qs:
                    cid = qs['id'][0]
                    cached_path = os.path.join(self.covers_cache_dir, f"{cid}.jpg")
                    with open(cached_path, "wb") as f:
                        f.write(data.data())
            except Exception:
                pass

            for target in targets:
                try:
                    if target:
                        target.set_image(pix, animate=(not is_fast_cache))
                except RuntimeError:
                    pass
        reply.deleteLater()
        self._process()

def get_blurred_pixmap(pixmap, radius):
    if not pixmap or pixmap.isNull():
        return pixmap
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
    from PySide6.QtCore import Qt

    scaled = pixmap.scaledToWidth(800, Qt.SmoothTransformation)
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(scaled)
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(radius)
    item.setGraphicsEffect(blur)
    scene.addItem(item)

    result = QPixmap(scaled.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    scene.render(painter)
    painter.end()
    return result