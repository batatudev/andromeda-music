import os
os.environ["QT_API"] = "pyside6"
import sys
import time
from PySide6.QtWidgets import QApplication
from engine.player_engine import PlayerEngine
from core.models import MediaItem
from config import APP_CONFIG

APP_CONFIG["video_smart_auto_play"] = True

class DummyClient:
    pass

app = QApplication(sys.argv)
engine = PlayerEngine(DummyClient())

# create a fake song that has an offline video
# item_id: '5ckcAuNLAmNYGLi4KTfgEL'
song = MediaItem({"id": "5ckcAuNLAmNYGLi4KTfgEL", "title": "Test title", "artist": "Test Artist", "yt_link": "https://youtube.com/watch?v=dummy"})

def on_video_ready(url):
    print("Video ready:", url)

def on_state(state):
    print("Audio State:", state)
    
def on_video_status(s):
    print("Video Status:", s)

def on_ready_to_show():
    print("ready_to_show emitted!")

engine.video_ready.connect(on_video_ready)
engine.state_changed.connect(on_state)
engine.video_player.mediaStatusChanged.connect(on_video_status)
engine.video_ready_to_show.connect(on_ready_to_show)

engine.queue = [song]
engine.idx = 0

print("Calling play_current...")
engine.play_current()

from PySide6.QtCore import QTimer
def mock_audio_cached():
    print("Mocking audio cache completion...")
    # create a dummy empty file for audio
    with open("dummy_audio.mp3", "wb") as f:
        pass
    engine.audio_track_cached.emit(song.item_id, "dummy_audio.mp3")
    
QTimer.singleShot(1000, mock_audio_cached)
QTimer.singleShot(3000, app.quit)

app.exec()
