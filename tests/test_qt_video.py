import os
os.environ["QT_API"] = "pyside6"
import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import QUrl

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

url_str = "file:///home/mateusz/.cache/navidrome-player-video-offline/5ckcAuNLAmNYGLi4KTfgEL.mp4"
player.setSource(QUrl(url_str))

# quit after 5 seconds to not hang
from PySide6.QtCore import QTimer
QTimer.singleShot(5000, app.quit)

app.exec()
