import time
from PySide6.QtCore import QObject, Signal, QThread, QRunnable, QThreadPool
from api_client import NavidromeClient
from core.models import Song, Album, Artist

class DataRepository(QObject):
    """
    Centralna warstwa danych (Repository).
    Odpowiada za komunikację z NavidromeClient, 
    transformację i ujednolicanie danych oraz podstawowy cache.
    """
    error_occurred = Signal(str)

    def __init__(self, client: NavidromeClient):
        super().__init__()
        self.client = client
        self._cache = {}
        self._cache_ttl = 300 # 5 minut

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

    def get_album(self, album_id: str) -> Album:
        key = f"album_{album_id}"
        cached = self._get_cached(key)
        if cached: return cached
        try:
            album = self.client.get_album(album_id)
            self._set_cache(key, album)
            return album
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_album: {e}")
            return None

    def get_artist(self, artist_id: str) -> Artist:
        key = f"artist_{artist_id}"
        cached = self._get_cached(key)
        if cached: return cached
        try:
            artist = self.client.get_artist(artist_id)
            self._set_cache(key, artist)
            return artist
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_artist: {e}")
            return None
            
    def get_random_songs(self, limit: int = 50) -> list[Song]:
        try:
            return self.client.get_random_songs(limit)
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_random_songs: {e}")
            return []
            
    def get_random_albums(self, limit: int = 10) -> list[Album]:
        try:
            return self.client.get_random_albums(limit)
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_random_albums: {e}")
            return []
            
    def get_starred(self, limit: int = 50) -> list[Song]:
        # Starred zmienia się często, nie keszujemy
        try:
            return self.client.get_starred(limit)
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_starred: {e}")
            return []
            
    def search(self, query: str, limit: int = 10) -> dict:
        key = f"search_{query}_{limit}"
        cached = self._get_cached(key)
        if cached: return cached
        try:
            res = self.client.search(query, limit)
            self._set_cache(key, res)
            return res
        except Exception as e:
            self.error_occurred.emit(f"Błąd wyszukiwania: {e}")
            return {}
