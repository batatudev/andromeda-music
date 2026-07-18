import sqlite3
db_path = "/home/mateusz/.cache/navidrome-player-v3/offline_videos.db"
conn = sqlite3.connect(db_path, timeout=5.0)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode;")
print("Journal mode:", cursor.fetchone()[0])
conn.close()
