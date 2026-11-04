import os
os.environ["QT_API"] = "pyside6"

import time
import sqlite3
import threading
import queue
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
from utils import logger
from core.paths import PathsManager

class DownloadStatus:
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    PAUSED = "PAUSED"

class BaseDownloadManager(QObject):
    """
    Abstrakcyjna klasa bazowa dla menedżerów pobierania offline (audio/wideo).
    Obsługuje kolejkę wielowątkową, uśpienie oraz operacje dyskowe i bazodanowe.
    """
    download_progress = Signal(str, float, str)
    download_status_changed = Signal(str, str)
    queue_updated = Signal()

    def __init__(self, db_path: Path | str, download_dir: Path | str, name: str = "Pobieranie"):
        super().__init__()
        self.manager_name = name
        self.db_path = Path(db_path)
        self.download_dir = Path(download_dir)

        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._path_cache = {}
        self.download_queue = queue.PriorityQueue()
        self.is_snoozed = False
        self.snooze_until = 0
        self.current_download_task = None
        self.cancel_current_event = threading.Event()
        self._is_running = True

        PathsManager.enable_wal_mode(self.db_path)
        self._init_db()
        self._reload_path_cache()
        self._reload_queued_to_memory()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self.snooze_timer = QTimer(self)
        self.snooze_timer.timeout.connect(self._check_snooze)
        self.snooze_timer.start(10000)

    def stop(self):
        """Bezpiecznie zatrzymuje wątek roboczy i anuluje bieżące transfery."""
        self._is_running = False
        self.cancel_current_event.set()
        if hasattr(self, 'snooze_timer') and self.snooze_timer.isActive():
            self.snooze_timer.stop()

    def _init_db(self):
        raise NotImplementedError

    def _reload_queued_to_memory(self):
        raise NotImplementedError

    def _worker_loop(self):
        raise NotImplementedError

    def _reload_path_cache(self):
        try:
            conn = PathsManager.get_db_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT item_id, file_path FROM downloads WHERE status = ?",
                (DownloadStatus.COMPLETED,)
            )
            self._path_cache = {
                row[0]: row[1] for row in cursor.fetchall()
                if row[1] and os.path.exists(row[1])
            }
            conn.close()
        except Exception as e:
            logger.log(f"Błąd ładowania path cache ({self.manager_name}): {e}")
            self._path_cache = {}

    def is_downloaded(self, item_id: str) -> bool:
        """Sprawdza obecność pliku w cache i weryfikuje fizyczne istnienie na dysku (self-healing)."""
        path = self._path_cache.get(item_id)
        if path and os.path.exists(path):
            return True
        if item_id in self._path_cache:
            self._path_cache.pop(item_id, None)
        return False

    def get_file_path(self, item_id: str) -> str | None:
        path = self._path_cache.get(item_id)
        if path and os.path.exists(path):
            return path
        if item_id in self._path_cache:
            self._path_cache.pop(item_id, None)
        return None

    def set_snooze(self, hours: int):
        if hours == 0:
            self.is_snoozed = False
            self.snooze_until = 0
            logger.log(f"{self.manager_name}: Wznowiono")
        else:
            self.is_snoozed = True
            if hours == -1:
                self.snooze_until = -1
                logger.log(f"{self.manager_name}: Wstrzymano na stałe")
            elif hours == -2:
                self.snooze_until = -2
                logger.log(f"{self.manager_name}: Wstrzymano do ponownego uruchomienia")
            else:
                self.snooze_until = time.time() + (hours * 3600)
                logger.log(f"{self.manager_name}: Wstrzymano na {hours}h")

            if self.current_download_task:
                logger.log(f"{self.manager_name}: Wstrzymywanie obecnego zadania...")
                self.cancel_current_event.set()
        self.queue_updated.emit()

    def _check_snooze(self):
        if not self._is_running:
            return
        if self.is_snoozed and self.snooze_until > 0 and time.time() > self.snooze_until:
            self.is_snoozed = False
            self.snooze_until = 0
            logger.log(f"{self.manager_name}: Wybudzono z uśpienia (czas minął)")
            self.queue_updated.emit()

    def _update_status(self, item_id: str, status: str, file_path: str = None, size: int = None, resolution: str = None):
        try:
            conn = PathsManager.get_db_connection(self.db_path)
            cursor = conn.cursor()

            query_parts = ["status = ?"]
            params = [status]

            if file_path is not None:
                query_parts.append("file_path = ?")
                params.append(file_path)
            if size is not None:
                query_parts.append("file_size = ?")
                params.append(size)
            if resolution is not None:
                query_parts.append("resolution = ?")
                params.append(resolution)

            params.append(item_id)
            sql = f"UPDATE downloads SET {', '.join(query_parts)} WHERE item_id = ?"
            cursor.execute(sql, tuple(params))

            if status == DownloadStatus.COMPLETED and file_path and os.path.exists(file_path):
                self._path_cache[item_id] = file_path
            elif status != DownloadStatus.COMPLETED:
                self._path_cache.pop(item_id, None)

            conn.commit()
            conn.close()
            if self._is_running:
                self.download_status_changed.emit(item_id, status)
                self.queue_updated.emit()
        except Exception as e:
            logger.log(f"Błąd aktualizacji statusu ({self.manager_name}): {e}")

    def get_all_downloads(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(downloads)")
        columns = [col[1] for col in cursor.fetchall()]

        if "cover_id" in columns and "resolution" in columns:
            cursor.execute(
                "SELECT item_id, title, status, cover_id, resolution, file_size, added_at FROM downloads WHERE is_hidden = 0 OR is_hidden IS NULL ORDER BY added_at DESC"
            )
        else:
            cursor.execute(
                "SELECT item_id, title, status, file_size, added_at FROM downloads WHERE is_hidden = 0 OR is_hidden IS NULL ORDER BY added_at DESC"
            )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_total_download_stats(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), SUM(file_size) FROM downloads WHERE status = ?",
            (DownloadStatus.COMPLETED,)
        )
        row = cursor.fetchone()
        conn.close()
        count = row[0] if row and row[0] else 0
        total_size = row[1] if row and row[1] else 0
        return count, total_size

    def remove_download(self, item_id: str):
        self._path_cache.pop(item_id, None)
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, status FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            if row[1] == DownloadStatus.DOWNLOADING and self.current_download_task == item_id:
                self.cancel_current_event.set()

            file_path = row[0]
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

            cursor.execute("DELETE FROM downloads WHERE item_id = ?", (item_id,))
            conn.commit()

        conn.close()
        self.download_status_changed.emit(item_id, "")
        self.queue_updated.emit()

    def clear_history(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE downloads SET is_hidden = 1 WHERE status IN (?, ?)",
            (DownloadStatus.COMPLETED, DownloadStatus.ERROR)
        )
        conn.commit()
        conn.close()
        self.queue_updated.emit()

    def cancel_all(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM downloads WHERE status = ?", (DownloadStatus.QUEUED,))
        if self.current_download_task:
            self.cancel_current_event.set()
        conn.commit()
        conn.close()

        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
                self.download_queue.task_done()
            except queue.Empty:
                break

        self.queue_updated.emit()

    def delete_all_files(self):
        self._path_cache.clear()
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM downloads WHERE status = ?", (DownloadStatus.COMPLETED,))
        rows = cursor.fetchall()

        for row in rows:
            fp = row[0]
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass

        cursor.execute(
            "DELETE FROM downloads WHERE status IN (?, ?)",
            (DownloadStatus.COMPLETED, DownloadStatus.ERROR)
        )
        conn.commit()
        conn.close()
        self.queue_updated.emit()