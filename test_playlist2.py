import config
import config
config.load_config()
from ui.main_window import MainWindow

config.load_config()

class DummyLoader:
    def __init__(self):
        self.session = None

class DummyEngine:
    class DummyVideoManager:
        def __init__(self):
            pass
    def __init__(self):
        self.video_download_manager = self.DummyVideoManager()

class MockMainWindow:
    def __init__(self):
        self.client = __import__('api_client').NavidromeClient(config.APP_CONFIG.get("url"), config.APP_CONFIG.get("username"), config.APP_CONFIG.get("password"))
        self._is_fetching = False
        self.engine = DummyEngine()
    def start_bulk_download(self, bulk_type, target_id=None, target_name=None):
        params = self.client._get_auth_params()
        params["id"] = target_id
        res = self.client._make_request("getPlaylist", params)
        entry = res.get("playlist", {}).get("entry", [])
        from core.media_item import MediaItem
        songs = [MediaItem(s) for s in entry]
        print(f"FETCHED {len(songs)} songs")
        
        valid_songs = [s for s in songs if getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)]
        print(f"VALID SONGS {len(valid_songs)}")
        if not songs:
            print("Brak utworów")
        elif not valid_songs:
            print("Znalezione utwory nie posiadają linków do wideo.")

mw = MockMainWindow()
res = mw.client._make_request("getPlaylists", mw.client._get_auth_params())
pls = res.get('playlists', {}).get('playlist', [])
if pls:
    print(pls[-1]['id'])
    mw.start_bulk_download('playlist', target_id=pls[-1]['id'])
