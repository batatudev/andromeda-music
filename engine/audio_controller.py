import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

class AudioController(QObject):
    """
    Kontroler odpowiedzialny za odtwarzanie strumienia audio oraz automatyczne
    przełączanie urządzeń wyjściowych (słuchawki, głośniki, Bluetooth).
    """
    device_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self.media_devices = QMediaDevices(self)
        default_out = self.media_devices.defaultAudioOutput()
        if not default_out.isNull():
            self.current_audio_device_id = default_out.id().data()
        else:
            self.current_audio_device_id = b''

        self.media_devices.audioOutputsChanged.connect(self._check_audio_device)

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

    def _check_audio_device(self):
        default_device = self.media_devices.defaultAudioOutput()
        if default_device.isNull():
            return
        new_id = default_device.id().data()
        if new_id != self.current_audio_device_id:
            self.current_audio_device_id = new_id
            self.apply_new_device(default_device)

    def apply_new_device(self, device, video_controller=None):
        was_playing = (self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        pos = self._player.position()

        if was_playing:
            self._player.pause()
            if video_controller:
                video_controller.player.pause()

        vol = self._audio_output.volume()
        self._player.setAudioOutput(None)
        if self._audio_output:
            self._audio_output.deleteLater()

        self._audio_output = QAudioOutput(self)
        self._audio_output.setDevice(device)
        self._audio_output.setVolume(vol)
        self._player.setAudioOutput(self._audio_output)

        if video_controller:
            video_controller.reassign_device(device)

        if was_playing:
            self._player.setPosition(pos)
            self._player.play()
            if video_controller:
                video_controller.player.setPosition(pos)
                video_controller.player.play()

        self.device_changed.emit(device.description())