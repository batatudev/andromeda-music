# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: engine/audio_download_manager.py
# OPIS ZMIAN: Dodano metody zarządzania bazą (remove_download, cancel_all, clear_history), by zrównać możliwości z menadżerem wideo.
import os
import time
import sqlite3
import threading
import queue
import requests
from PySide6.QtCore import QObject, Signal, QTimer
from config import APP_CONFIG
from utils import logger
from api_client import NavidromeClient

class AudioDownloadStatus:
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

class AudioDownloadManager(QObject):
    download_progress = Signal(str, float)
    download_status_changed = Signal(str, str)
    queue_updated = Signal()

    def __init__(self, api_client: NavidromeClient):
        super().__init__()
        self.api_client = api_client
        self.db_path = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-v3", "offline_audio.db")
        self.music_dir = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-v3", "offline_music")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.music_dir, exist_ok=True)

        self._init_db()

        self.download_queue = queue.PriorityQueue()
        self.current_download_task = None
        self.cancel_current_event = threading.Event()

        self._reload_queued_to_memory()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                item_id TEXT PRIMARY KEY,
                title TEXT,
                file_path TEXT,
                status TEXT,
                added_at INTEGER,
                file_size INTEGER
            )
        ''')
        try:
            cursor.execute("ALTER TABLE downloads ADD COLUMN is_hidden INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        cursor.execute("UPDATE downloads SET status = ? WHERE status = ?", (AudioDownloadStatus.QUEUED, AudioDownloadStatus.DOWNLOADING))
        conn.commit()
        conn.close()

    def _reload_queued_to_memory(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, title FROM downloads WHERE status = ? ORDER BY added_at ASC", (AudioDownloadStatus.QUEUED,))
        for row in cursor.fetchall():
            self.download_queue.put((10, time.time(), row[0], row[1]))
        conn.close()

    def get_all_downloads(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, title, status, file_size FROM downloads WHERE is_hidden = 0 OR is_hidden IS NULL ORDER BY added_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_total_download_stats(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(file_size) FROM downloads WHERE status = ?", (AudioDownloadStatus.COMPLETED,))
        row = cursor.fetchone()
        conn.close()
        count = row[0] if row and row[0] else 0
        total_size = row[1] if row and row[1] else 0
        return count, total_size

    def remove_download(self, item_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, status FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            if row[1] == AudioDownloadStatus.DOWNLOADING and self.current_download_task == item_id:
                self.cancel_current_event.set()
            file_path = row[0]
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except OSError: pass
            cursor.execute("DELETE FROM downloads WHERE item_id = ?", (item_id,))
            conn.commit()
        conn.close()
        self.download_status_changed.emit(item_id, "")
        self.queue_updated.emit()

    def clear_history(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE downloads SET is_hidden = 1 WHERE status IN (?, ?)", (AudioDownloadStatus.COMPLETED, AudioDownloadStatus.ERROR))
        conn.commit()
        conn.close()
        self.queue_updated.emit()

    def cancel_all(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM downloads WHERE status = ?", (AudioDownloadStatus.QUEUED,))
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM downloads WHERE status = ?", (AudioDownloadStatus.COMPLETED,))
        rows = cursor.fetchall()
        for row in rows:
            fp = row[0]
            if fp and os.path.exists(fp):
                try: os.remove(fp)
                except OSError: pass
        cursor.execute("DELETE FROM downloads WHERE status IN (?, ?)", (AudioDownloadStatus.COMPLETED, AudioDownloadStatus.ERROR))
        conn.commit()
        conn.close()
        self.queue_updated.emit()

    def is_downloaded(self, item_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, file_path FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == AudioDownloadStatus.COMPLETED:
            if os.path.exists(row[1]):
                return True
        return False

    def get_file_path(self, item_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, file_path FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == AudioDownloadStatus.COMPLETED and os.path.exists(row[1]):
            return row[1]
        return None

    def add_to_queue(self, item_id, title, high_priority=False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()

        if row:
            if row[0] in [AudioDownloadStatus.COMPLETED, AudioDownloadStatus.QUEUED, AudioDownloadStatus.DOWNLOADING]:
                conn.close()
                return

        priority = 1 if high_priority else 10
        cursor.execute(
            "INSERT OR REPLACE INTO downloads (item_id, title, status, added_at) VALUES (?, ?, ?, ?)",
            (item_id, title, AudioDownloadStatus.QUEUED, int(time.time()))
        )
        conn.commit()
        conn.close()

        self.download_queue.put((priority, time.time(), item_id, title))
        self.download_status_changed.emit(item_id, AudioDownloadStatus.QUEUED)
        self.queue_updated.emit()

    def _update_status(self, item_id, status, file_path=None, size=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if file_path and size:
            cursor.execute("UPDATE downloads SET status = ?, file_path = ?, file_size = ? WHERE item_id = ?", (status, file_path, size, item_id))
        elif file_path:
            cursor.execute("UPDATE downloads SET status = ?, file_path = ? WHERE item_id = ?", (status, file_path, item_id))
        else:
            cursor.execute("UPDATE downloads SET status = ? WHERE item_id = ?", (status, item_id))
        conn.commit()
        conn.close()
        self.download_status_changed.emit(item_id, status)
        self.queue_updated.emit()

    def _worker_loop(self):
        while True:
            try:
                priority, added_ts, item_id, title = self.download_queue.get()
                
                # Upewnijmy się, że wpis nadal istnieje i ma odpowiedni status
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM downloads WHERE item_id = ?", (item_id,))
                row = cursor.fetchone()
                conn.close()
                if not row or row[0] != AudioDownloadStatus.QUEUED:
                    self.download_queue.task_done()
                    continue

                self.current_download_task = item_id
                self.cancel_current_event.clear()
                self._update_status(item_id, AudioDownloadStatus.DOWNLOADING)

                try:
                    self._download_audio(item_id)
                except Exception as e:
                    logger.log(f"Błąd pobierania audio {item_id}: {e}")
                    if not self.cancel_current_event.is_set():
                        self._update_status(item_id, AudioDownloadStatus.ERROR)

                self.current_download_task = None
                self.download_queue.task_done()
            except Exception as e:
                logger.log(f"AudioDownloadWorker Error: {e}")
                time.sleep(2)

    def _download_audio(self, item_id):
        stream_url = self.api_client.get_stream_url(item_id)
        if not stream_url:
            raise Exception("Nie można uzyskać URL strumienia.")

        temp_file = os.path.join(self.music_dir, f"{item_id}.tmp")
        final_file = os.path.join(self.music_dir, f"{item_id}.mp3")

        response = requests.get(stream_url, stream=True, timeout=10)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if self.cancel_current_event.is_set():
                    raise Exception("Anulowano przez użytkownika")
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        self.download_progress.emit(item_id, progress)

        os.rename(temp_file, final_file)
        self._update_status(item_id, AudioDownloadStatus.COMPLETED, final_file, downloaded)
        logger.log(f"Pobrano audio: {item_id}")

    def download_all_from_library(self):
        from core.library_sync import LibrarySyncManager
        sync = LibrarySyncManager(self.api_client)
        songs = sync.get_all_songs()
        for s in songs:
            sid = s.get('id')
            if not self.is_downloaded(sid):
                self.add_to_queue(sid, s.get('title', ''), high_priority=False)