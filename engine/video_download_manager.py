# WERSJA PROJEKTU: 14.18
# MODYFIKOWANY PLIK: engine/video_download_manager.py
# OPIS ZMIAN: Migracja bazy (cover_id, resolution, file_size), zaawansowane wstrzymywanie (-1, -2), zbieranie rozmiaru plików.

import os
import time
import sqlite3
import threading
import queue
from PySide6.QtCore import QObject, Signal, QTimer
from config import APP_CONFIG
from utils import logger

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

class DownloadStatus:
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    PAUSED = "PAUSED"

class VideoDownloadManager(QObject):
    # Sygnały dla UI
    download_progress = Signal(str, float)  # item_id, progress (0-100)
    download_status_changed = Signal(str, str) # item_id, now_status
    queue_updated = Signal()

    def __init__(self):
        super().__init__()
        self.db_path = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-v3", "offline_videos.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
        self.download_queue = queue.PriorityQueue()
        self.is_snoozed = False
        self.snooze_until = 0
        
        self.current_download_task = None
        self.cancel_current_event = threading.Event()
        
        # Wątek roboczy (Worker)
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Wczytaj QUEUED do kolejki
        self._reload_queued_to_memory()
        # Wczytaj ręczne override'y linków YT
        self.load_yt_link_overrides()
        
        # Timer odświeżający stan (Snooze)
        self.snooze_timer = QTimer(self)
        self.snooze_timer.timeout.connect(self._check_snooze)
        self.snooze_timer.start(10000)

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
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
        
        # Migracje dla starszych wersji bazy
        try:
            cursor.execute("ALTER TABLE downloads ADD COLUMN cover_id TEXT")
        except sqlite3.OperationalError:
            pass # Kolumna już istnieje
            
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
            
        # Reset unfinished downloads to QUEUED
        cursor.execute("UPDATE downloads SET status = ? WHERE status = ?", (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING))
        # Tabela nadpisanych linków YT (override dla plików bez linku w comment)
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
        """Wczytuje rekordy QUEUED z bazy do kolejki w pamięci."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, yt_link, title FROM downloads WHERE status = ? ORDER BY added_at ASC", (DownloadStatus.QUEUED,))
        for row in cursor.fetchall():
            self.download_queue.put((10, time.time(), row[0], row[1], row[2]))
        conn.close()

    def load_yt_link_overrides(self):
        """Ładuje wszystkie override'y do modułowego słownika w utils."""
        from utils import _set_yt_link_override
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, url FROM yt_link_overrides")
        for row in cursor.fetchall():
            _set_yt_link_override(row[0], row[1])
        conn.close()

    def save_yt_link_override(self, item_id, url, title=""):
        """Zapisuje ręczny override linku YT do bazy i odświeża cache."""
        from utils import _set_yt_link_override
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO yt_link_overrides (item_id, url, title, added_at) VALUES (?, ?, ?, ?)",
            (item_id, url, title, int(time.time()))
        )
        conn.commit()
        conn.close()
        _set_yt_link_override(item_id, url)

    def delete_yt_link_override(self, item_id):
        """Usuwa override linku YT z bazy i cache."""
        from utils import _set_yt_link_override
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM yt_link_overrides WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()
        _set_yt_link_override(item_id, None)


    def _update_db_status(self, item_id, status, file_path=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if file_path:
            cursor.execute("UPDATE downloads SET status = ?, file_path = ? WHERE item_id = ?", (status, file_path, item_id))
        else:
            cursor.execute("UPDATE downloads SET status = ? WHERE item_id = ?", (status, item_id))
        conn.commit()
        conn.close()
        self.download_status_changed.emit(item_id, status)

    def get_video_path(self, item_id):
        """Zwraca ścieżkę do pliku wideo jeśli istnieje i jest kompletny."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, status FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[1] == DownloadStatus.COMPLETED:
            if os.path.exists(row[0]):
                return row[0]
            else:
                # Plik usunięty ręcznie przez usera
                self._update_db_status(item_id, DownloadStatus.ERROR)
        return None

    def add_to_queue(self, item_id, yt_link, title, high_priority=False, cover_id=""):
        if not HAS_YTDLP or not yt_link:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        
        if row:
            if row[0] in [DownloadStatus.COMPLETED, DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED]:
                conn.close()
                return # Już jest lub pobiera
            else:
                cursor.execute("UPDATE downloads SET status = ?, yt_link = ?, title = ?, cover_id = ? WHERE item_id = ?", 
                               (DownloadStatus.QUEUED, yt_link, title, cover_id, item_id))
        else:
            cursor.execute("INSERT INTO downloads (item_id, title, yt_link, status, quality, added_at, cover_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (item_id, title, yt_link, DownloadStatus.QUEUED, APP_CONFIG.get("video_offline_quality", "1080p"), int(time.time()), cover_id))
        conn.commit()
        conn.close()
        
        priority = 1 if high_priority else 10
        # Dodajemy mikrosekundy do timestampa aby uniknąć kolizji i zapewnić FIFO
        self.download_queue.put((priority, time.time_ns(), item_id, yt_link, title))
        self.download_status_changed.emit(item_id, DownloadStatus.QUEUED)
        self.queue_updated.emit()

    def add_to_queue_bulk(self, items_list, high_priority=False):
        """Hurtowe dodawanie do kolejki. items_list = [(item_id, yt_link, title, cover_id), ...]"""
        if not HAS_YTDLP or not items_list:
            return
            
        # Deduplikacja (jeśli playlista ma ten sam utwór kilka razy)
        unique_items = []
        seen_ids = set()
        for it in items_list:
            if it[0] not in seen_ids:
                unique_items.append(it)
                seen_ids.add(it[0])
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Pobieramy obecne statusy
        cursor.execute("SELECT item_id, status, is_hidden FROM downloads")
        existing_status = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        
        inserts = []
        updates = []
        added_count = 0
        added_at = int(time.time())
        quality = APP_CONFIG.get("video_offline_quality", "1080p")
        
        for item in unique_items:
            item_id, yt_link, title, cover_id = item
            if not yt_link:
                continue
                
            status_info = existing_status.get(item_id)
            if status_info:
                status, is_hidden = status_info
                if status in [DownloadStatus.COMPLETED, DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED]:
                    if is_hidden:
                        updates.append((status, yt_link, title, cover_id, 0, item_id))
                        added_count += 1
                    continue # Już pobrane lub pobiera
                else:
                    updates.append((DownloadStatus.QUEUED, yt_link, title, cover_id, 0, item_id))
                    added_count += 1
            else:
                inserts.append((item_id, title, yt_link, DownloadStatus.QUEUED, quality, added_at, cover_id, 0))
                added_count += 1
                
        if inserts:
            cursor.executemany("INSERT OR IGNORE INTO downloads (item_id, title, yt_link, status, quality, added_at, cover_id, is_hidden) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", inserts)
        if updates:
            cursor.executemany("UPDATE downloads SET status = ?, yt_link = ?, title = ?, cover_id = ?, is_hidden = ? WHERE item_id = ?", updates)
            
        conn.commit()
        conn.close()
        
        if added_count > 0:
            priority = 1 if high_priority else 10
            for item in unique_items:
                item_id, yt_link, title, _ = item
                status_info = existing_status.get(item_id)
                if yt_link and (not status_info or status_info[0] not in [DownloadStatus.COMPLETED, DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED]):
                    self.download_queue.put((priority, time.time_ns(), item_id, yt_link, title))
                    self.download_status_changed.emit(item_id, DownloadStatus.QUEUED)
            self.queue_updated.emit()

    def remove_download(self, item_id):
        # Usuwa z bazy i kasuje plik
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, status FROM downloads WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            if row[1] == DownloadStatus.DOWNLOADING and self.current_download_task == item_id:
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
        cursor.execute("UPDATE downloads SET is_hidden = 1 WHERE status IN (?, ?)", (DownloadStatus.COMPLETED, DownloadStatus.ERROR))
        conn.commit()
        conn.close()
        self.queue_updated.emit()
        
    def cancel_all(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM downloads WHERE status = ?", (DownloadStatus.QUEUED,))
        if self.current_download_task:
            self.cancel_current_event.set()
        conn.commit()
        conn.close()
        
        # Czyścimy kolejkę z queue.PriorityQueue (po prostu wyciągamy wszystko)
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
        cursor.execute("SELECT file_path FROM downloads WHERE status = ?", (DownloadStatus.COMPLETED,))
        rows = cursor.fetchall()
        
        for row in rows:
            fp = row[0]
            if fp and os.path.exists(fp):
                try: os.remove(fp)
                except OSError: pass
                
        cursor.execute("DELETE FROM downloads WHERE status IN (?, ?)", (DownloadStatus.COMPLETED, DownloadStatus.ERROR))
        conn.commit()
        conn.close()
        self.queue_updated.emit()

    def set_snooze(self, hours):
        if hours == 0:
            self.is_snoozed = False
            self.snooze_until = 0
            logger.log("Menadżer pobierania: Wznowiono")
        else:
            self.is_snoozed = True
            if hours == -1: # Stałe wstrzymanie
                self.snooze_until = -1
                logger.log("Menadżer pobierania: Wstrzymano na stałe")
            elif hours == -2: # Do restartu
                self.snooze_until = -2
                logger.log("Menadżer pobierania: Wstrzymano do ponownego uruchomienia")
            else:
                self.snooze_until = time.time() + (hours * 3600)
                logger.log(f"Menadżer pobierania: Wstrzymano na {hours}h")
                
            if self.current_download_task:
                logger.log("Menadżer pobierania: Wstrzymywanie obecnego zadania...")
                self.cancel_current_event.set()
        self.queue_updated.emit()

    def _check_snooze(self):
        if self.is_snoozed:
            if self.snooze_until > 0 and time.time() > self.snooze_until:
                self.is_snoozed = False
                self.snooze_until = 0
                logger.log("Menadżer pobierania: Wybudzono z uśpienia (czas minął)")
                self.queue_updated.emit()

    def get_all_downloads(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Pobieraj tylko nieukryte utwory, w starszych bazach is_hidden może być null
        cursor.execute("SELECT item_id, title, status, cover_id, resolution, file_size FROM downloads WHERE is_hidden = 0 OR is_hidden IS NULL ORDER BY added_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_total_download_stats(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(file_size) FROM downloads WHERE status = ?", (DownloadStatus.COMPLETED,))
        row = cursor.fetchone()
        conn.close()
        count = row[0] if row and row[0] else 0
        total_size = row[1] if row and row[1] else 0
        return count, total_size

    def _worker_loop(self):
        while True:
            if self.is_snoozed:
                time.sleep(5)
                continue
                
            try:
                # Blokuje do momentu pojawienia się zadania
                priority, timestamp, item_id, yt_link, title = self.download_queue.get(timeout=2)
            except queue.Empty:
                continue
                
            # Sprawdź czy zadanie dalej widnieje jako QUEUED w bazie (mogło zostać usunięte)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM downloads WHERE item_id = ?", (item_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row or row[0] != DownloadStatus.QUEUED:
                self.download_queue.task_done()
                continue
                
            self.current_download_task = item_id
            self.cancel_current_event.clear()
            self._update_db_status(item_id, DownloadStatus.DOWNLOADING)
            
            try:
                self._download_video(item_id, yt_link)
            except Exception as e:
                logger.log(f"Video Download Error ({item_id}): {e}")
                if not self.cancel_current_event.is_set():
                    self._update_db_status(item_id, DownloadStatus.ERROR)
                else:
                    # Było anulowane/uśpione -> wraca do QUEUED
                    self._update_db_status(item_id, DownloadStatus.QUEUED)
                    # Wrzucamy z powrotem do kolejki z niskim priorytetem, żeby po wznownieniu kontynuował
                    self.download_queue.put((10, time.time(), item_id, yt_link, title))
            
            self.current_download_task = None
            self.download_queue.task_done()
            self.queue_updated.emit()

    def _download_video(self, item_id, yt_link):
        base_dir = os.path.expanduser(APP_CONFIG.get("video_offline_path", "~/.cache/navidrome-player-video-offline"))
        os.makedirs(base_dir, exist_ok=True)
        output_template = os.path.join(base_dir, f"{item_id}.%(ext)s")
        
        quality_str = APP_CONFIG.get("video_offline_quality", "1080p")
        h_limit = 1080
        if quality_str == "720p": h_limit = 720
        elif quality_str == "480p": h_limit = 480
        
        # Pobieramy SAM OBRAZ lub połączony format bez narzutu na postprocessing audio (wymuszamy H.264!)
        ydl_opts = {
            'format': f'bestvideo[height<={h_limit}][vcodec^=avc1][ext=mp4]/best[height<={h_limit}][vcodec^=avc1][ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': True,
            'nocheckcertificate': True,
            'noplaylist': True,
            'cookiesfrombrowser': ('firefox', )
        }

        def my_hook(d):
            if self.cancel_current_event.is_set():
                raise ValueError("Download Cancelled")
            if d['status'] == 'downloading':
                p = d.get('_percent_str', '0.0%').replace('%', '').strip()
                try:
                    pct = float(p)
                    self.download_progress.emit(item_id, pct)
                except ValueError:
                    pass

        ydl_opts['progress_hooks'] = [my_hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(yt_link, download=True)
            filename = ydl.prepare_filename(info)
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                resolution = info.get('resolution', quality_str)
                
                # Zaktualizuj bazę z rozmiarem i rozdzielczością
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE downloads SET status = ?, file_path = ?, resolution = ?, file_size = ? WHERE item_id = ?",
                               (DownloadStatus.COMPLETED, filename, resolution, file_size, item_id))
                conn.commit()
                conn.close()
                self.download_status_changed.emit(item_id, DownloadStatus.COMPLETED)
                
                logger.log(f"Pobrano wideo offline dla: {item_id} ({resolution}, {file_size} bajtów)")
            else:
                raise Exception("Plik nie został znaleziony po pobraniu")
