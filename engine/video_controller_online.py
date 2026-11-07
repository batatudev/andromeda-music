import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class VideoControllerOnline(QObject):
    """
    Kontroler wideo online (wyciszone wyjście audio, synchronizacja obrazu).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._audio_output.setMuted(True)
        self._player.setAudioOutput(self._audio_output)

    @property
    def player(self):
        return self._player

    @property
    def audio_output(self):
        return self._audio_output

    def reassign_device(self, device):
        self._player.setAudioOutput(None)
        if self._audio_output:
            self._audio_output.deleteLater()
        self._audio_output = QAudioOutput(self)
        self._audio_output.setDevice(device)
        self._audio_output.setMuted(True)
        self._player.setAudioOutput(self._audio_output)

    def set_source(self, url: QUrl):
        self._player.setSource(url)

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def stop(self):
        self._player.stop()

    def set_position(self, pos: int):
        self._player.setPosition(pos)