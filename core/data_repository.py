# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: core/data_repository.py
# OPIS ZMIAN: Logika awaryjnego odzyskiwania - Fallback przy błędach z serwera.
import time
from PySide6.QtCore import QObject, Signal
from api_client import NavidromeClient
from core.models import Song, Album, Artist
from utils import logger

class DataRepository(QObject):
    error_occurred = Signal(str)

    def __init__(self, client: NavidromeClient):
        super().__init__()
        self.client = client
        self._cache = {}
        self._cache_ttl = 300 
        from core.library_sync import LibrarySyncManager
        self.library_sync = LibrarySyncManager(self.client)

    def _get_cached(self, key):
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key, data):
        self._cache[key] = (data, time.time())

    def _is_offline(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if hasattr(w, 'network_monitor'):
                    return not getattr(w.network_monitor, 'is_online', True)
        return False

    def get_album(self, album_id: str) -> Album:
        key = f"album_{album_id}"
        cached = self._get_cached(key)
        if cached: return cached

        def offline_fallback():
            songs_data = self.library_sync.get_album_songs(album_id)
            if songs_data:
                album_name = songs_data[0].get('album') if songs_data else 'Unknown'
                return Album({'id': album_id, 'name': album_name, 'song': songs_data})
            return None

        if self._is_offline(): return offline_fallback()

        try:
            album = self.client.get_album(album_id)
            self._set_cache(key, album)
            return album
        except Exception as e:
            logger.log(f"Błąd get_album (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_artist(self, artist_id: str) -> Artist:
        key = f"artist_{artist_id}"
        cached = self._get_cached(key)
        if cached: return cached

        def offline_fallback():
            artists = self.library_sync.get_all_artists()
            art_data = next((a for a in artists if a.get('id') == artist_id), None)
            if art_data:
                albums_data = self.library_sync.get_artist_albums(artist_id)
                art_data['album'] = albums_data
                return Artist(art_data)
            return None

        if self._is_offline(): return offline_fallback()

        try:
            artist = self.client.get_artist(artist_id)
            self._set_cache(key, artist)
            return artist
        except Exception as e:
            logger.log(f"Błąd get_artist (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_artists(self) -> list[Artist]:
        key = "all_artists"
        cached = self._get_cached(key)
        if cached: return cached

        def offline_fallback():
            return [Artist(a) for a in self.library_sync.get_all_artists()]

        if self._is_offline(): return offline_fallback()

        try:
            arts = self.client.get_artists()
            self._set_cache(key, arts)
            return arts
        except Exception as e:
            logger.log(f"Błąd get_artists (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_albums(self, offset: int = 0, limit: int = 30) -> list[Album]:
        key = f"albums_{offset}_{limit}"
        cached = self._get_cached(key)
        if cached: return cached

        def offline_fallback():
            albs = self.library_sync.get_all_albums()
            return [Album(a) for a in albs[offset:offset+limit]]

        if self._is_offline(): return offline_fallback()

        try:
            albs = self.client.get_albums(offset, limit)
            self._set_cache(key, albs)
            return albs
        except Exception as e:
            logger.log(f"Błąd get_albums (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_random_songs(self, limit: int = 50) -> list[Song]:
        def offline_fallback():
            songs = self.library_sync.get_all_songs()
            import random
            if not songs: return []
            sampled = random.sample(songs, min(limit, len(songs)))
            return [Song(s) for s in sampled]

        if self._is_offline(): return offline_fallback()

        try:
            return self.client.get_random_songs(limit)
        except Exception as e:
            logger.log(f"Błąd get_random_songs (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_random_albums(self, limit: int = 10) -> list[Album]:
        def offline_fallback():
            albums = self.library_sync.get_all_albums()
            import random
            if not albums: return []
            sampled = random.sample(albums, min(limit, len(albums)))
            return [Album(a) for a in sampled]

        if self._is_offline(): return offline_fallback()

        try:
            return self.client.get_random_albums(limit)
        except Exception as e:
            logger.log(f"Błąd get_random_albums (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_top_songs_for_artist(self, artist_name: str, limit: int = 50) -> list[Song]:
        key = f"top_songs_{artist_name}_{limit}"
        cached = self._get_cached(key)
        if cached: return cached

        def offline_fallback():
            songs = self.library_sync.get_all_songs()
            matched = [Song(s) for s in songs if s.get('artist', '').lower() == artist_name.lower()]
            return matched[:limit]

        if self._is_offline(): return offline_fallback()

        try:
            songs = self.client.get_top_songs_for_artist(artist_name, limit)
            self._set_cache(key, songs)
            return songs
        except Exception as e:
            logger.log(f"Błąd get_top_songs (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def get_starred(self, limit: int = 50) -> list[Song]:
        def offline_fallback():
            songs = self.library_sync.get_all_songs()
            starred = [Song(s) for s in songs if s.get('starred')]
            return starred[:limit]

        if self._is_offline(): return offline_fallback()

        try:
            return self.client.get_starred(limit)
        except Exception as e:
            logger.log(f"Błąd get_starred (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()

    def search(self, query: str, limit: int = 10) -> dict:
        key = f"search_{query}_{limit}"
        cached = self._get_cached(key)
        if cached: return cached

        def offline_fallback():
            q = query.lower()
            songs = self.library_sync.get_all_songs()
            matched_songs = [Song(s) for s in songs if q in s.get('title', '').lower() or q in s.get('artist', '').lower()]
            return {'song': matched_songs[:limit]}

        if self._is_offline(): return offline_fallback()

        try:
            res = self.client.search(query, limit)
            self._set_cache(key, res)
            return res
        except Exception as e:
            logger.log(f"Błąd search (Zastosowano awaryjny Fallback): {e}")
            return offline_fallback()