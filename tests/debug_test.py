import os
os.environ["QT_API"] = "pyside6"
import sqlite3
from PySide6.QtCore import QUrl
from engine.video_download_manager import DownloadStatus

db_path = os.path.expanduser("~/.cache/navidrome-player-v3/offline_videos.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT item_id, file_path, status FROM downloads WHERE status = 'COMPLETED'")
rows = cursor.fetchall()
conn.close()

print(f"Pobrane wideo: {len(rows)}")
for r in rows:
    print(r)
    path = r[1]
    exists = os.path.exists(path)
    print(f"Exists: {exists}")
    if exists:
        url = QUrl.fromLocalFile(path).toString()
        print(f"QUrl.toString(): {url}")
        qurl2 = QUrl(url)
        print(f"QUrl(str).isValid(): {qurl2.isValid()}, isLocalFile: {qurl2.isLocalFile()}")
