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
        from utils import network_monitor
        return not network_monitor.is_connected

    def get_album(self, album_id: str) -> Album:
        key = f"album_{album_id}"
        cached = self._get_cached(key)
        if cached: return cached
        
        if self._is_offline():
            songs_data = self.library_sync.get_album_songs(album_id)
            if songs_data:
                # Mock album wrapper
                album = Album({'id': album_id, 'name': songs_data[0].get('album'), 'song': songs_data})
                return album
            return None
            
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
        
        if self._is_offline():
            # In offline mode, get all albums for artist, but library_sync doesn't have get_artist_albums yet.
            # For simplicity, returning empty for now or implementing it in library_sync
            # Wait, let's just use try/except on online and return cached if available
            pass
            
        try:
            artist = self.client.get_artist(artist_id)
            self._set_cache(key, artist)
            return artist
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_artist: {e}")
            return None
            
    def get_random_songs(self, limit: int = 50) -> list[Song]:
        if self._is_offline():
            songs = self.library_sync.get_all_songs()
            import random
            if not songs: return []
            sampled = random.sample(songs, min(limit, len(songs)))
            return [Song(s) for s in sampled]
            
        try:
            return self.client.get_random_songs(limit)
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_random_songs: {e}")
            return []
            
    def get_random_albums(self, limit: int = 10) -> list[Album]:
        if self._is_offline():
            albums = self.library_sync.get_all_albums()
            import random
            if not albums: return []
            sampled = random.sample(albums, min(limit, len(albums)))
            return [Album(a) for a in sampled]
            
        try:
            return self.client.get_random_albums(limit)
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_random_albums: {e}")
            return []
            
    def get_starred(self, limit: int = 50) -> list[Song]:
        if self._is_offline():
            songs = self.library_sync.get_all_songs()
            starred = [Song(s) for s in songs if s.get('starred')]
            return starred[:limit]
            
        try:
            return self.client.get_starred(limit)
        except Exception as e:
            self.error_occurred.emit(f"Błąd get_starred: {e}")
            return []
            
    def search(self, query: str, limit: int = 10) -> dict:
        key = f"search_{query}_{limit}"
        cached = self._get_cached(key)
        if cached: return cached
        
        if self._is_offline():
            q = query.lower()
            songs = self.library_sync.get_all_songs()
            matched_songs = [Song(s) for s in songs if q in s.get('title', '').lower() or q in s.get('artist', '').lower()]
            return {'song': matched_songs[:limit]}
            
        try:
            res = self.client.search(query, limit)
            self._set_cache(key, res)
            return res
        except Exception as e:
            self.error_occurred.emit(f"Błąd wyszukiwania: {e}")
            return {}
