import config
from api_client import NavidromeClient
from utils import MediaItem
config.load_config()
c = NavidromeClient(config.APP_CONFIG.get("url"), config.APP_CONFIG.get("username"), config.APP_CONFIG.get("password"))
pls = c._make_request("getPlaylists", c._get_auth_params()).get('playlists', {}).get('playlist', [])
for pl in pls:
    if pl['name'] == 'test 17':
        print(f"Playlist: {pl['name']}")
        params = c._get_auth_params()
        params["id"] = pl['id']
        res = c._make_request("getPlaylist", params)
        entry = res.get('playlist', {}).get('entry', [])
        songs = [MediaItem(s) for s in entry]
        valid_songs = []
        for s in songs:
            link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
            if link:
                valid_songs.append(s)
            print(f"Song: {s.title}, yt_link: {s.yt_link}, comment: {s.get('comment')}")
        print("Valid:", len(valid_songs))
