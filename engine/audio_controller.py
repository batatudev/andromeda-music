from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class AudioController(QObject):
    """
    Kontroler odpowiedzialny stricte za odtwarzanie strumienia audio.
    Zajmuje się inicjalizacją instancji QMediaPlayer i wyjściem audio.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

    @property
    def player(self):
        return self._player

    @property
    def audio_output(self):
        return self._audio_output

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

    def set_volume(self, vol: float):
        self._audio_output.setVolume(vol)
