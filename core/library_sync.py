import os
os.environ["QT_API"] = "pyside6"

import json
import time
import threading
from PySide6.QtCore import QObject, Signal
from api_client import NavidromeClient
from utils import logger
from core.paths import PathsManager


class LibrarySyncManager(QObject):
    sync_progress = Signal(int, int)
    sync_completed = Signal()
    sync_error = Signal(str)

    def __init__(self, client: NavidromeClient):
        super().__init__()
        self.client = client
        self.db_path = PathsManager.get_library_cache_db_path()
        self._memory_cache = {}
        self._init_db()
        self._is_syncing = False

    def _init_db(self):
        conn = PathsManager.get_db_connection(self.db_path)
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

    def clear_memory_cache(self):
        self._memory_cache.clear()

    def start_sync(self):
        if self._is_syncing:
            return
        self._is_syncing = True
        threading.Thread(target=self._sync_worker, daemon=True).start()

    def _sync_worker(self):
        try:
            logger.log("Rozpoczynam synchronizację całej biblioteki (Offline-First)...")
            conn = PathsManager.get_db_connection(self.db_path)
            c = conn.cursor()

            artists = self.client.get_artists()
            artist_records = [
                ("artist", art.item_id, "", art.title, json.dumps(dict(art)))
                for art in artists
            ]
            if artist_records:
                c.executemany(
                    "INSERT OR REPLACE INTO library (type, id, parent_id, title, data) VALUES (?, ?, ?, ?, ?)",
                    artist_records
                )
            conn.commit()

            offset = 0
            limit = 500
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

                album_records = [
                    (
                        "album",
                        a.get('id', ''),
                        a.get('artistId', ''),
                        a.get('name', a.get('title', '')),
                        json.dumps(a)
                    )
                    for a in albums_data
                ]
                if album_records:
                    c.executemany(
                        "INSERT OR REPLACE INTO library (type, id, parent_id, title, data) VALUES (?, ?, ?, ?, ?)",
                        album_records
                    )

                song_records = [
                    (
                        "song",
                        s.get('id', ''),
                        s.get('albumId', ''),
                        s.get('title', ''),
                        json.dumps(s)
                    )
                    for s in songs_data
                ]
                if song_records:
                    c.executemany(
                        "INSERT OR REPLACE INTO library (type, id, parent_id, title, data) VALUES (?, ?, ?, ?, ?)",
                        song_records
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

            self.clear_memory_cache()
            logger.log(f"Zakończono synchronizację biblioteki. Zapisano {total_songs} utworów.")
            self._is_syncing = False
            self.sync_completed.emit()

        except Exception as e:
            self._is_syncing = False
            logger.log(f"Błąd synchronizacji: {e}")
            self.sync_error.emit(str(e))

    def get_all_songs(self):
        if "all_songs" in self._memory_cache:
            return self._memory_cache["all_songs"]
        conn = PathsManager.get_db_connection(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='song'")
        rows = c.fetchall()
        conn.close()
        res = [json.loads(r[0]) for r in rows]
        self._memory_cache["all_songs"] = res
        return res

    def get_all_albums(self):
        if "all_albums" in self._memory_cache:
            return self._memory_cache["all_albums"]
        conn = PathsManager.get_db_connection(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='album'")
        rows = c.fetchall()
        conn.close()
        res = [json.loads(r[0]) for r in rows]
        self._memory_cache["all_albums"] = res
        return res

    def get_album_songs(self, album_id):
        key = f"album_songs_{album_id}"
        if key in self._memory_cache:
            return self._memory_cache[key]
        conn = PathsManager.get_db_connection(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='song' AND parent_id=?", (album_id,))
        rows = c.fetchall()
        conn.close()
        res = [json.loads(r[0]) for r in rows]
        self._memory_cache[key] = res
        return res

    def get_all_artists(self):
        if "all_artists" in self._memory_cache:
            return self._memory_cache["all_artists"]
        conn = PathsManager.get_db_connection(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='artist'")
        rows = c.fetchall()
        conn.close()
        res = [json.loads(r[0]) for r in rows]
        self._memory_cache["all_artists"] = res
        return res

    def get_artist_albums(self, artist_id):
        key = f"artist_albums_{artist_id}"
        if key in self._memory_cache:
            return self._memory_cache[key]
        conn = PathsManager.get_db_connection(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM library WHERE type='album' AND parent_id=?", (artist_id,))
        rows = c.fetchall()
        conn.close()
        res = [json.loads(r[0]) for r in rows]
        self._memory_cache[key] = res
        return res