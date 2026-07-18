import config
from engine.video_download_manager import VideoDownloadManager
from api_client import NavidromeClient
from utils import MediaItem

config.load_config()
c = NavidromeClient(config.APP_CONFIG.get("url"), config.APP_CONFIG.get("username"), config.APP_CONFIG.get("password"))

res = c._make_request("getPlaylist", {"id": "pdMBioFmMTlGumeFAr4qTF", **c._get_auth_params()})
entry = res.get('playlist', {}).get('entry', [])
songs = [MediaItem(s) for s in entry]
items_to_add = []
for s in songs:
    link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
    if link:
        items_to_add.append((s.item_id, link, s.title, s.cover_id))

print(f"Items to add: {len(items_to_add)}")
if items_to_add:
    import sqlite3
    db_path = "/home/mateusz/.cache/navidrome-player-v3/offline_videos.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, status, is_hidden FROM downloads")
    existing_status = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    added_count = 0
    inserts = []
    updates = []
    for item in items_to_add:
        item_id, yt_link, title, cover_id = item
        status_info = existing_status.get(item_id)
        if status_info:
            status, is_hidden = status_info
            if status in ["COMPLETED", "DOWNLOADING", "QUEUED"]:
                print(f"Item {title} is {status}, hidden: {is_hidden}")
                if is_hidden:
                    added_count += 1
                    updates.append(item_id)
            else:
                print(f"Item {title} is {status}, adding to queue")
                added_count += 1
                updates.append(item_id)
        else:
            print(f"Item {title} not in DB, inserting")
            added_count += 1
            inserts.append(item_id)
            
    print(f"Added count: {added_count}, updates: {len(updates)}, inserts: {len(inserts)}")
