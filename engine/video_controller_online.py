from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class VideoControllerOnline(QObject):
    """
    Kontroler wideo online (fallback awaryjny dla braku wideo offline/yt-dlp).
    Zarządza drugim silnikiem QMediaPlayer z wyciszonym audio (tylko wideo).
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
