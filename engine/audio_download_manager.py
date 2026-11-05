import os
os.environ["QT_API"] = "pyside6"

import time
import sqlite3
import queue
import requests
from config import APP_CONFIG
from utils import logger
from api_client import NavidromeClient
from core.paths import PathsManager
from engine.base_download_manager import BaseDownloadManager, DownloadStatus

AudioDownloadStatus = DownloadStatus

class AudioDownloadManager(BaseDownloadManager):
    """
    Menedżer pobierania plików audio (MP3) w tle.
    """
    def __init__(self, api_client: NavidromeClient):
        self.api_client = api_client
        super().__init__(
            db_path=PathsManager.get_audio_db_path(),
            download_dir=PathsManager.get_offline_audio_dir(),
            name="Menedżer pobierania audio"
        )
        self.music_dir = str(self.download_dir)

    def _init_db(self):
        conn = PathsManager.get_db_connection(self.db_path)
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

        cursor.execute(
            "UPDATE downloads SET status = ? WHERE status = ?",
            (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)
        )
        conn.commit()
        conn.close()

    def _reload_queued_to_memory(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT item_id, title FROM downloads WHERE status = ? ORDER BY added_at ASC",
            (DownloadStatus.QUEUED,)
        )
        for row in cursor.fetchall():
            self.download_queue.put((10, time.time(), row[0], row[1]))
        conn.close()

    def add_to_queue(self, item_id: str, title: str, high_priority: bool = False):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, file_path, is_hidden FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()

        if row:
            status, file_path, is_hidden = row[0], row[1], row[2]
            if status == DownloadStatus.COMPLETED:
                if file_path and os.path.exists(file_path):
                    if is_hidden == 1:
                        cursor.execute("UPDATE downloads SET is_hidden = 0 WHERE item_id = ?", (item_id,))
                        conn.commit()
                        self.queue_updated.emit()
                    conn.close()
                    return
            elif status in [DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING]:
                conn.close()
                return

        priority = 1 if high_priority else 10
        cursor.execute(
            "INSERT OR REPLACE INTO downloads (item_id, title, status, added_at, is_hidden) VALUES (?, ?, ?, ?, 0)",
            (item_id, title, DownloadStatus.QUEUED, int(time.time()))
        )
        conn.commit()
        conn.close()

        self.download_queue.put((priority, time.time(), item_id, title))
        self.download_status_changed.emit(item_id, DownloadStatus.QUEUED)
        self.queue_updated.emit()

    def add_to_queue_bulk(self, items_list: list, high_priority: bool = False):
        if not items_list:
            return

        unique_items = []
        seen_ids = set()
        for it in items_list:
            if it[0] not in seen_ids:
                unique_items.append(it)
                seen_ids.add(it[0])

        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, status, file_path, is_hidden FROM downloads")
        existing_status = {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}

        inserts = []
        updates = []
        items_to_enqueue = []
        added_at = int(time.time())

        for item in unique_items:
            item_id, title = item
            status_info = existing_status.get(item_id)
            if status_info:
                status, file_path, is_hidden = status_info
                if status == DownloadStatus.COMPLETED and file_path and os.path.exists(file_path):
                    continue
                elif status in [DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED]:
                    continue
                else:
                    updates.append((DownloadStatus.QUEUED, 0, added_at, item_id))
                    items_to_enqueue.append(item)
            else:
                inserts.append((item_id, title, DownloadStatus.QUEUED, added_at, 0))
                items_to_enqueue.append(item)

        if inserts:
            cursor.executemany(
                "INSERT OR IGNORE INTO downloads (item_id, title, status, added_at, is_hidden) VALUES (?, ?, ?, ?, ?)",
                inserts
            )
        if updates:
            cursor.executemany(
                "UPDATE downloads SET status = ?, is_hidden = ?, added_at = ? WHERE item_id = ?",
                updates
            )

        conn.commit()
        conn.close()

        if items_to_enqueue:
            priority = 1 if high_priority else 10
            for item in items_to_enqueue:
                item_id, title = item
                self.download_queue.put((priority, time.time(), item_id, title))
            self.queue_updated.emit()

    def _worker_loop(self):
        while self._is_running:
            if self.is_snoozed:
                time.sleep(1)
                continue

            try:
                priority, added_ts, item_id, title = self.download_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if not self._is_running:
                self.download_queue.task_done()
                break

            conn = PathsManager.get_db_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM downloads WHERE item_id = ?", (item_id,))
            row = cursor.fetchone()
            conn.close()

            if not row or row[0] != DownloadStatus.QUEUED:
                self.download_queue.task_done()
                continue

            self.current_download_task = item_id
            self.cancel_current_event.clear()
            self._update_status(item_id, DownloadStatus.DOWNLOADING)

            try:
                self._download_audio(item_id)
            except Exception as e:
                logger.log(f"Błąd pobierania audio {item_id}: {e}")
                if self._is_running:
                    if not self.cancel_current_event.is_set():
                        self._update_status(item_id, DownloadStatus.ERROR)
                    else:
                        self._update_status(item_id, DownloadStatus.QUEUED)
                        self.download_queue.put((10, time.time(), item_id, title))

            self.current_download_task = None
            self.download_queue.task_done()
            if self._is_running:
                self.queue_updated.emit()

    def _download_audio(self, item_id: str):
        stream_url = self.api_client.get_stream_url(item_id)
        if not stream_url:
            raise Exception("Nie można uzyskać URL strumienia.")

        temp_file = os.path.join(self.music_dir, f"{item_id}.tmp")
        final_file = os.path.join(self.music_dir, f"{item_id}.mp3")

        try:
            session = getattr(self.api_client, 'session', requests)
            response = session.get(stream_url, stream=True, timeout=10)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_emit_time = time.time()
            last_downloaded = 0

            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=16384):
                    if not self._is_running or self.cancel_current_event.is_set():
                        raise Exception("Przerwano pobieranie (anulowanie lub zamknięcie aplikacji)")
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        current_time = time.time()
                        time_diff = current_time - last_emit_time
                        if time_diff > 0.2 and self._is_running:
                            bytes_diff = downloaded - last_downloaded
                            speed = bytes_diff / time_diff if time_diff > 0 else 0

                            if speed > 1024 * 1024:
                                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                            elif speed > 1024:
                                speed_str = f"{speed / 1024:.0f} KB/s"
                            else:
                                speed_str = f"{speed:.0f} B/s"

                            dl_mb = downloaded / (1024 * 1024)
                            if total_size > 0:
                                pct = (downloaded / total_size) * 100.0
                                tot_mb = total_size / (1024 * 1024)
                                stats_str = f"{dl_mb:.1f} MB / {tot_mb:.1f} MB • {speed_str}"
                            else:
                                pct = 0.0
                                stats_str = f"{dl_mb:.1f} MB • {speed_str}"

                            self.download_progress.emit(item_id, pct, stats_str)
                            last_emit_time = current_time
                            last_downloaded = downloaded

            if not self._is_running or self.cancel_current_event.is_set():
                raise Exception("Pobieranie przerwane przed zakończeniem")

            os.rename(temp_file, final_file)
            self._update_status(item_id, DownloadStatus.COMPLETED, final_file, downloaded)
            logger.log(f"Pobrano audio: {item_id}")

        except Exception as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            raise e

    def download_all_from_library(self):
        from core.library_sync import LibrarySyncManager
        sync = LibrarySyncManager(self.api_client)
        songs = sync.get_all_songs()

        items_to_add = []
        for s in songs:
            sid = s.get('id')
            if not self.is_downloaded(sid):
                items_to_add.append((sid, s.get('title', '')))

        if items_to_add:
            self.add_to_queue_bulk(items_to_add, high_priority=False)