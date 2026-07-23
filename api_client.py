import os
os.environ["QT_API"] = "pyside6"

import hashlib
import random
import string
import requests
import time
from config import APP_NAME
from utils import logger
from core.models import Song, Album, Artist


class NavidromeClient:
    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip('/')
        self.user = user
        self.password = password
        self.api_version = "1.16.1"
        self.client_name = APP_NAME.replace(" ", "")
        self.failures = 0
        self.circuit_breaker_until = 0
        self.session = requests.Session()

    def _get_auth_params(self) -> dict:
        salt = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        token = hashlib.md5((self.password + salt).encode('utf-8')).hexdigest()
        return {'u': self.user, 't': token, 's': salt, 'v': self.api_version, 'c': self.client_name, 'f': 'json'}

    def ping(self) -> bool:
        try:
            res = self._make_request("ping", self._get_auth_params())
            return res.get('status') == 'ok'
        except Exception:
            return False

    def _make_request(self, endpoint: str, params: dict) -> dict:
        if time.time() < self.circuit_breaker_until:
            return {}
        try:
            response = self.session.get(f"{self.url}/rest/{endpoint}", params=params, timeout=(3.0, 10.0))
            response.raise_for_status()
            self.failures = 0
            return response.json().get('subsonic-response', {})
        except Exception as e:
            self.failures += 1
            if self.failures >= 3:
                self.circuit_breaker_until = time.time() + 60
                logger.log(f"API Error[{endpoint}]: {e} -> CIRCUIT BREAKER ACTIVATED FOR 60s")
            else:
                logger.log(f"API Error [{endpoint}]: {e}")
            return {}

    def get_cover_art_url(self, cover_id: str, size: int = 400) -> str:
        if not cover_id:
            return ""
        params = self._get_auth_params()
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.url}/rest/getCoverArt?id={cover_id}&size={size}&{query}"

    def get_stream_url(self, song_id: str) -> str:
        if not song_id:
            return ""
        params = self._get_auth_params()
        params['format'] = 'mp3'
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.url}/rest/stream?id={song_id}&{query}"

    def star_track(self, song_id: str, star: bool = True):
        endpoint = "star" if star else "unstar"
        params = self._get_auth_params()
        params['id'] = song_id
        return self._make_request(endpoint, params)

    def get_starred(self, limit: int = 50) -> list:
        data = self._make_request("getStarred", self._get_auth_params())
        starred_data = data.get('starred', {})
        if not starred_data:
            return[]
        return [Song(s) for s in starred_data.get('song', [])[:limit]]

    def get_albums(self, offset: int = 0, limit: int = 30) -> list:
        params = self._get_auth_params()
        params['type'] = 'alphabeticalByName'
        params['size'] = limit
        params['offset'] = offset
        res = self._make_request("getAlbumList", params).get('albumList', {}).get('album',[])
        return [Album(a) for a in res]

    def get_random_albums(self, limit: int = 10) -> list:
        params = self._get_auth_params()
        params['type'] = 'random'
        params['size'] = limit
        res = self._make_request("getAlbumList", params).get('albumList', {}).get('album',[])
        return [Album(a) for a in res]

    def get_random_songs(self, limit: int = 50) -> list:
        params = self._get_auth_params()
        params['size'] = limit
        res = self._make_request("getRandomSongs", params).get('randomSongs', {}).get('song', [])
        return [Song(s) for s in res]

    def get_artists(self) -> list:
        data = self._make_request("getArtists", self._get_auth_params())
        indices = data.get('artists', {}).get('index',[])
        all_artists = []
        for i in indices:
            for a in i.get('artist',[]):
                all_artists.append(Artist(a))
        return all_artists

    def get_album(self, album_id: str) -> Album:
        params = self._get_auth_params()
        params['id'] = album_id
        album_data = self._make_request("getAlbum", params).get('album', {})
        if 'song' in album_data:
            album_data['song'] = [Song(s) for s in album_data['song']]
        return Album(album_data)

    def get_artist(self, artist_id: str) -> Artist:
        params = self._get_auth_params()
        params['id'] = artist_id
        artist_data = self._make_request("getArtist", params).get('artist', {})
        if 'album' in artist_data:
            artist_data['album'] =[Album(a) for a in artist_data['album']]
        return Artist(artist_data)

    def get_top_songs_for_artist(self, artist_name: str, limit: int = 50) -> list:
        params = self._get_auth_params()
        params['artist'] = artist_name
        params['count'] = limit
        res = self._make_request("getTopSongs", params).get('topSongs', {}).get('song', [])
        return [Song(s) for s in res]

    def update_playlist(self, playlist_id: str, song_id_to_add: str = None, song_index_to_remove: int = None):
        params = self._get_auth_params()
        params['playlistId'] = playlist_id
        if song_id_to_add:
            params['songIdToAdd'] = song_id_to_add
        if song_index_to_remove is not None:
            params['songIndexToRemove'] = song_index_to_remove
        return self._make_request("updatePlaylist", params)

    def replace_playlist(self, playlist_id: str, song_ids: list):
        params = self._get_auth_params()
        params['playlistId'] = playlist_id
        params['songId'] = song_ids
        return self._make_request("createPlaylist", params)
        
    def delete_playlist(self, playlist_id: str):
        params = self._get_auth_params()
        params['id'] = playlist_id
        return self._make_request("deletePlaylist", params)

    def search(self, query: str, limit: int = 10) -> dict:
        if not query:
            return {}
        params = self._get_auth_params()
        params['query'] = query
        params['songCount'] = limit
        params['albumCount'] = limit
        params['artistCount'] = limit
        res = self._make_request("search3", params).get('searchResult3', {})
        
        if 'artist' in res: res['artist'] = [Artist(i) for i in res['artist']]
        if 'album' in res: res['album'] = [Album(i) for i in res['album']]
        if 'song' in res: res['song'] = [Song(i) for i in res['song']]
        return res