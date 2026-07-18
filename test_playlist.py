import config
from api_client import NavidromeClient
config.load_config()
c = NavidromeClient(config.APP_CONFIG.get("url"), config.APP_CONFIG.get("username"), config.APP_CONFIG.get("password"))
res = c._make_request("getPlaylists", c._get_auth_params())
pls = res.get('playlists', {}).get('playlist', [])
if pls:
    first_pl = pls[-1] 
    print(first_pl['name'], first_pl['id'])
    params = c._get_auth_params()
    params["id"] = first_pl['id']
    res2 = c._make_request("getPlaylist", params)
    print(list(res2.keys()))
    if 'playlist' in res2:
        pl = res2['playlist']
        print(list(pl.keys()))
        if 'entry' in pl:
            print("Entries found:", len(pl['entry']))
        else:
            print("NO ENTRY FOUND")
