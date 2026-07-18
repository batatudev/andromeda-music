import config
from api_client import NavidromeClient
config.load_config()
c = NavidromeClient(config.APP_CONFIG.get("url"), config.APP_CONFIG.get("username"), config.APP_CONFIG.get("password"))
pls = c._make_request("getPlaylists", c._get_auth_params()).get('playlists', {}).get('playlist', [])
for pl in pls:
    print(f"Playlist: {pl['name']}")
    params = c._get_auth_params()
    params["id"] = pl['id']
    res = c._make_request("getPlaylist", params)
    entry = res.get('playlist', {}).get('entry', [])
    if entry:
        print("Keys in first entry:", list(entry[0].keys()))
        print("Comment in first entry:", entry[0].get('comment', 'MISSING'))
