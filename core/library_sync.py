# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: core/library_sync.py
# OPIS ZMIAN: Dodano metody wyciągające artystów i albumy artystów z bazy offline.
import os
import json
import time
import sqlite3
import threading
from PySide6.QtCore import QObject, Signal
from api_client import NavidromeClient
from utils import logger

class LibrarySyncManager(QObject):
    sync_progress = Signal(int, int) # current, total
    sync_completed = Signal()
    sync_error = Signal(str)

    def __init__(self, client: NavidromeClient):
        super().__init__()
        self.client = client
        self.db_path = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-v3", "library_cache.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._is_syncing = False

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS library (
                type TEXT,
                id TEXT,
                parent_id TEXT,
                title TEXT,
                data TEXT,
                PRIMARY KEY (type, id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def start_sync(self):
        if self._is_syncing:
            return
        self._is_syncing = True
        threading.Thread(target=self._sync_worker, daemon=True).start()

    def _sync_worker(self):
        try:
            logger.log("Rozpoczynam synchronizację całej biblioteki (Offline-First)...")
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # 1. Pobieranie Artystów
            artists = self.client.get_artists()
            for art in artists:
                c.execute(
                    "INSERT OR REPLACE INTO library (type, id, parent_id, title, data) VALUES (?, ?, ?, ?, ?)",
                    ("artist", art.item_id, "", art.name, json.dumps(art._data))
                )

            # 2. Pobieranie pełnej bazy (Utwory + Albumy) przez search3 (z pustym zapytaniem)
            offset = 0
            limit = 5000
            total_songs = 0

            while True:
                params = self.client._get_auth_params()
                params['query'] = ''
                params['songCount'] = limit
                params['songOffset'] = offset
                params['albumCount'] = limit
                params['albumOffset'] = offset

                res = self.client._make_request("search3", params).get('searchResult3', {})

                songs_data = res.get('song', [])
                albums_data = res.get('album', [])

                for a in albums_data:
                    c.execute(
                        "INSERT OR REPLACE INTO library (type, id, parent_id, title, data) VALUES (?, ?, ?, ?, ?)",
                        ("album", a.get('id'), a.get('artistId', ''), a.get('name', ''), json.dumps(a))
                    )

                for s in songs_data:
                    c.execute(
                        "INSERT OR REPLACE INTO library (type, id, parent_id, title, data) VALUES (?, ?, ?, ?, ?)",
                        ("song", s.get('id'), s.get('albumId', ''), s.get('title', ''), json.dumps(s))
                    )

                conn.commit()

                count = len(songs_data)
                total_songs += count
                self.sync_progress.emit(total_songs, 0)

                if count < limit:
                    break
                offset += limit

            c.execute("INSERT OR REPLACE INTO sync_meta (key, value) VALUES (?, ?)", ("last_sync", str(time.time())))
            conn.commit()
            conn.close()

            logger.log(f"Zakończono synchronizację biblioteki. Zapisano {total_songs} utworów.")
            self._is_syncing = False
            self.sync_completed.emit()

        except Exception as e:
            self._is_syncing = False
            logger.log(f"Błąd synchronizacji: {e}")
            self.sync_error.emit(str(e))

    def get_all_songs(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='song'")
        rows = c.fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def get_all_albums(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='album'")
        rows = c.fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def get_album_songs(self, album_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='song' AND parent_id=?", (album_id,))
        rows = c.fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def get_all_artists(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='artist'")
        rows = c.fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def get_artist_albums(self, artist_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='album' AND parent_id=?", (artist_id,))
        rows = c.fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]