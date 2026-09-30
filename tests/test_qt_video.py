import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: tests/test_qt_video.py
# OPIS ZMIAN: Usunięcie na sztywno zakodowanej ścieżki /home/mateusz/ na rzecz PathsManager

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import QUrl, QTimer

from core.paths import PathsManager

app = QApplication(sys.argv)
player = QMediaPlayer()

def on_status(s):
    print("Status changed:", s)
    if s == QMediaPlayer.MediaStatus.LoadedMedia:
        print("Loaded! Playing...")
        player.play()
    elif s == QMediaPlayer.MediaStatus.EndOfMedia:
        print("End of media")
        app.quit()
    elif s == QMediaPlayer.MediaStatus.InvalidMedia:
        print("Invalid Media Error:", player.errorString())
        app.quit()

def on_error(err, errstr):
    print("Error:", err, errstr)

def on_state(s):
    print("State:", s)

player.mediaStatusChanged.connect(on_status)
player.errorOccurred.connect(on_error)
player.playbackStateChanged.connect(on_state)

target_video = PathsManager.get_offline_videos_dir() / "5ckcAuNLAmNYGLi4KTfgEL.mp4"
if target_video.exists():
    player.setSource(QUrl.fromLocalFile(str(target_video)))
else:
    print(f"Plik testowy nie istnieje pod ścieżką XDG: {target_video}")

QTimer.singleShot(5000, app.quit)

app.exec()