import os
os.environ["QT_API"] = "pyside6"

import time
import sqlite3
import queue
from config import APP_CONFIG
from utils import logger
from core.paths import PathsManager
from engine.base_download_manager import BaseDownloadManager, DownloadStatus

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

class VideoDownloadManager(BaseDownloadManager):
    """
    Menedżer pobierania teledysków z YouTube (yt-dlp) w tle.
    """
    def __init__(self):
        super().__init__(
            db_path=PathsManager.get_video_db_path(),
            download_dir=PathsManager.get_offline_videos_dir(),
            name="Menedżer pobierania wideo"
        )
        self._last_progress_emit = 0
        self.load_yt_link_overrides()

    def _init_db(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                item_id TEXT PRIMARY KEY,
                title TEXT,
                yt_link TEXT,
                file_path TEXT,
                status TEXT,
                quality TEXT,
                added_at INTEGER,
                cover_id TEXT,
                resolution TEXT,
                file_size INTEGER
            )
        ''')

        try:
            cursor.execute("ALTER TABLE downloads ADD COLUMN cover_id TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE downloads ADD COLUMN resolution TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE downloads ADD COLUMN file_size INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE downloads ADD COLUMN is_hidden INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        cursor.execute(
            "UPDATE downloads SET status = ? WHERE status = ?",
            (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)
        )
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yt_link_overrides (
                item_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                added_at INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    def _reload_queued_to_memory(self):
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT item_id, yt_link, title FROM downloads WHERE status = ? ORDER BY added_at ASC",
            (DownloadStatus.QUEUED,)
        )
        for row in cursor.fetchall():
            self.download_queue.put((10, time.time(), row[0], row[1], row[2]))
        conn.close()

    def load_yt_link_overrides(self):
        from utils import _set_yt_link_override
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, url FROM yt_link_overrides")
        for row in cursor.fetchall():
            _set_yt_link_override(row[0], row[1])
        conn.close()

    def save_yt_link_override(self, item_id: str, url: str, title: str = ""):
        from utils import _set_yt_link_override
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO yt_link_overrides (item_id, url, title, added_at) VALUES (?, ?, ?, ?)",
            (item_id, url, title, int(time.time()))
        )
        conn.commit()
        conn.close()
        _set_yt_link_override(item_id, url)

    def delete_yt_link_override(self, item_id: str):
        from utils import _set_yt_link_override
        conn = PathsManager.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM yt_link_overrides WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()
        _set_yt_link_override(item_id, None)

    def get_video_path(self, item_id: str) -> str | None:
        return self.get_file_path(item_id)

    def add_to_queue(self, item_id: str, yt_link: str, title: str, high_priority: bool = False, cover_id: str = ""):
        if not HAS_YTDLP or not yt_link:
            return

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
                # Plik zniknął z dysku — zezwalamy na ponowne pobranie
            elif status in [DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING]:
                conn.close()
                return
            cursor.execute(
                "UPDATE downloads SET status = ?, yt_link = ?, title = ?, cover_id = ?, is_hidden = 0, added_at = ? WHERE item_id = ?",
                (DownloadStatus.QUEUED, yt_link, title, cover_id, int(time.time()), item_id)
            )
        else:
            quality = APP_CONFIG.get("video_offline_quality", "1080p")
            cursor.execute(
                "INSERT INTO downloads (item_id, title, yt_link, status, quality, added_at, cover_id, is_hidden) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                (item_id, title, yt_link, DownloadStatus.QUEUED, quality, int(time.time()), cover_id)
            )
        conn.commit()
        conn.close()

        priority = 1 if high_priority else 10
        self.download_queue.put((priority, time.time_ns(), item_id, yt_link, title))
        self.download_status_changed.emit(item_id, DownloadStatus.QUEUED)
        self.queue_updated.emit()

    def add_to_queue_bulk(self, items_list: list, high_priority: bool = False):
        if not HAS_YTDLP or not items_list:
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
        quality = APP_CONFIG.get("video_offline_quality", "1080p")

        for item in unique_items:
            item_id, yt_link, title, cover_id = item
            if not yt_link:
                continue

            status_info = existing_status.get(item_id)
            if status_info:
                status, file_path, is_hidden = status_info
                if status == DownloadStatus.COMPLETED and file_path and os.path.exists(file_path):
                    continue
                elif status in [DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED]:
                    continue
                else:
                    updates.append((DownloadStatus.QUEUED, yt_link, title, cover_id, 0, added_at, item_id))
                    items_to_enqueue.append(item)
            else:
                inserts.append((item_id, title, yt_link, DownloadStatus.QUEUED, quality, added_at, cover_id, 0))
                items_to_enqueue.append(item)

        if inserts:
            cursor.executemany(
                "INSERT OR IGNORE INTO downloads (item_id, title, yt_link, status, quality, added_at, cover_id, is_hidden) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                inserts
            )
        if updates:
            cursor.executemany(
                "UPDATE downloads SET status = ?, yt_link = ?, title = ?, cover_id = ?, is_hidden = ?, added_at = ? WHERE item_id = ?",
                updates
            )

        conn.commit()
        conn.close()

        if items_to_enqueue:
            priority = 1 if high_priority else 10
            for item in items_to_enqueue:
                item_id, yt_link, title, _ = item
                self.download_queue.put((priority, time.time_ns(), item_id, yt_link, title))
            self.queue_updated.emit()

    def _worker_loop(self):
        while self._is_running:
            if self.is_snoozed:
                time.sleep(1)
                continue

            try:
                priority, timestamp, item_id, yt_link, title = self.download_queue.get(timeout=1.0)
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
                self._download_video(item_id, yt_link)
            except Exception as e:
                logger.log(f"Video Download Error ({item_id}): {e}")
                if self._is_running:
                    if not self.cancel_current_event.is_set():
                        self._update_status(item_id, DownloadStatus.ERROR)
                    else:
                        self._update_status(item_id, DownloadStatus.QUEUED)
                        self.download_queue.put((10, time.time(), item_id, yt_link, title))

            self.current_download_task = None
            self.download_queue.task_done()
            if self._is_running:
                self.queue_updated.emit()

    def _download_video(self, item_id: str, yt_link: str):
        base_dir = str(self.download_dir)
        os.makedirs(base_dir, exist_ok=True)
        output_template = os.path.join(base_dir, f"{item_id}.%(ext)s")

        quality_str = APP_CONFIG.get("video_offline_quality", "1080p")
        h_limit = 1080
        if quality_str == "720p":
            h_limit = 720
        elif quality_str == "480p":
            h_limit = 480

        ydl_opts = {
            'format': f'bestvideo[height<={h_limit}][vcodec^=avc1][ext=mp4]/best[height<={h_limit}][vcodec^=avc1][ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': True,
            'nocheckcertificate': True,
            'noplaylist': True,
        }

        cookies_file = PathsManager.get_cookies_file()
        if cookies_file.exists():
            ydl_opts['cookiefile'] = str(cookies_file)

        def my_hook(d):
            if not self._is_running or self.cancel_current_event.is_set():
                raise ValueError("Download Cancelled")
            if d.get('status') == 'downloading':
                current_time = time.time()
                if current_time - getattr(self, '_last_progress_emit', 0) > 0.2 and self._is_running:
                    downloaded = d.get('downloaded_bytes', 0) or 0
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    speed = d.get('speed') or 0

                    if total > 0:
                        pct = (downloaded / total) * 100.0
                    else:
                        pct = 0.0

                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                    elif speed > 1024:
                        speed_str = f"{speed / 1024:.0f} KB/s"
                    else:
                        speed_str = f"{speed:.0f} B/s"

                    dl_mb = downloaded / (1024 * 1024)
                    if total > 0:
                        tot_mb = total / (1024 * 1024)
                        stats_str = f"{dl_mb:.1f} MB / {tot_mb:.1f} MB • {speed_str}"
                    else:
                        stats_str = f"{dl_mb:.1f} MB • {speed_str}"

                    self.download_progress.emit(item_id, pct, stats_str)
                    self._last_progress_emit = current_time

        ydl_opts['progress_hooks'] = [my_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_link, download=True)
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    resolution = info.get('resolution', quality_str)
                    self._update_status(item_id, DownloadStatus.COMPLETED, file_path=filename, size=file_size, resolution=resolution)
                    logger.log(f"Pobrano wideo offline dla: {item_id} ({resolution}, {file_size} bajtów)")
                else:
                    raise Exception("Plik nie został znaleziony po pobraniu")
        except Exception as e:
            if not self._is_running or self.cancel_current_event.is_set():
                try:
                    for f in os.listdir(base_dir):
                        if f.startswith(item_id) and f.endswith(".part"):
                            try:
                                os.remove(os.path.join(base_dir, f))
                            except OSError:
                                pass
                except Exception:
                    pass
                raise e

            # Fallback na ciasteczka przeglądarki jeśli Fast-Path nie powiódł się
            if not cookies_file.exists():
                try:
                    ydl_opts_browser = dict(ydl_opts)
                    ydl_opts_browser['cookiesfrombrowser'] = ('firefox',)
                    with yt_dlp.YoutubeDL(ydl_opts_browser) as ydl_b:
                        info = ydl_b.extract_info(yt_link, download=True)
                        filename = ydl_b.prepare_filename(info)
                        if os.path.exists(filename):
                            file_size = os.path.getsize(filename)
                            resolution = info.get('resolution', quality_str)
                            self._update_status(item_id, DownloadStatus.COMPLETED, file_path=filename, size=file_size, resolution=resolution)
                            logger.log(f"Pobrano wideo offline dla: {item_id} ({resolution}, {file_size} bajtów) [Fallback Firefox]")
                            return
                except Exception:
                    pass

            raise e