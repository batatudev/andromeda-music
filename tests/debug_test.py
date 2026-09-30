import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: tests/debug_test.py
# OPIS ZMIAN: Zastąpienie legacy ścieżki navidrome-player-v3 wywołaniem PathsManager.get_video_db_path()

import sqlite3
from PySide6.QtCore import QUrl
from core.paths import PathsManager

db_path = PathsManager.get_video_db_path()

if not db_path.exists():
    print(f"Baza danych wideo nie istnieje: {db_path}")
    exit(0)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("SELECT item_id, file_path, status FROM downloads WHERE status = 'COMPLETED'")
rows = cursor.fetchall()
conn.close()

print(f"Pobrane wideo: {len(rows)}")
for r in rows:
    print(r)
    path = r[1]
    exists = os.path.exists(path) if path else False
    print(f"Exists: {exists}")
    if exists:
        url = QUrl.fromLocalFile(path).toString()
        print(f"QUrl.toString(): {url}")
        qurl2 = QUrl(url)
        print(f"QUrl(str).isValid(): {qurl2.isValid()}, isLocalFile: {qurl2.isLocalFile()}")