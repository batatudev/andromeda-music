import os
os.environ["QT_API"] = "pyside6"

import threading
import random
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtMultimedia import QMediaPlayer
from config import APP_NAME
from utils import logger

try:
    from pydbus import SessionBus
    from pydbus.generic import signal
    from gi.repository import GLib
    HAS_MPRIS = True
except ImportError as e:
    HAS_MPRIS = False
    logger.log(f"Brak pydbus/gi. Integracja MPRIS wyłączona. {e}")

class MprisSignals(QObject):
    next_requested = Signal()
    prev_requested = Signal()
    pause_requested = Signal()
    play_pause_requested = Signal()
    stop_requested = Signal()
    play_requested = Signal()
    seek_requested = Signal(int)
    set_position_requested = Signal(int)
    loop_status_changed = Signal(str)
    shuffle_changed = Signal(bool)
    volume_changed = Signal(float)

class MprisPlayer:
    dbus = """
    <node>
        <interface name="org.mpris.MediaPlayer2">
            <property name="CanQuit" type="b" access="read"/>
            <property name="CanRaise" type="b" access="read"/>
            <property name="HasTrackList" type="b" access="read"/>
            <property name="Identity" type="s" access="read"/>
            <property name="DesktopEntry" type="s" access="read"/>
            <property name="SupportedUriSchemes" type="as" access="read"/>
            <property name="SupportedMimeTypes" type="as" access="read"/>
            <method name="Quit"/>
            <method name="Raise"/>
        </interface>
        <interface name="org.mpris.MediaPlayer2.Player">
            <method name="Next"/>
            <method name="Previous"/>
            <method name="Pause"/>
            <method name="PlayPause"/>
            <method name="Stop"/>
            <method name="Play"/>
            <method name="Seek">
                <arg direction="in" name="Offset" type="x"/>
            </method>
            <method name="SetPosition">
                <arg direction="in" name="TrackId" type="o"/>
                <arg direction="in" name="Position" type="x"/>
            </method>
            <property name="PlaybackStatus" type="s" access="read"/>
            <property name="LoopStatus" type="s" access="readwrite"/>
            <property name="Rate" type="d" access="readwrite"/>
            <property name="Shuffle" type="b" access="readwrite"/>
            <property name="Metadata" type="a{sv}" access="read"/>
            <property name="Volume" type="d" access="readwrite"/>
            <property name="Position" type="x" access="read"/>
            <property name="MinimumRate" type="d" access="read"/>
            <property name="MaximumRate" type="d" access="read"/>
            <property name="CanGoNext" type="b" access="read"/>
            <property name="CanGoPrevious" type="b" access="read"/>
            <property name="CanPlay" type="b" access="read"/>
            <property name="CanPause" type="b" access="read"/>
            <property name="CanSeek" type="b" access="read"/>
            <property name="CanControl" type="b" access="read"/>
        </interface>
    </node>
    """

    PropertiesChanged = signal()

    def __init__(self, engine, signals):
        self.engine = engine
        self.signals = signals

    @property
    def CanQuit(self):
        return True

    @property
    def CanRaise(self):
        return True

    @property
    def HasTrackList(self):
        return False

    @property
    def Identity(self):
        return APP_NAME

    @property
    def DesktopEntry(self):
        return "andromeda-music"

    @property
    def SupportedUriSchemes(self):
        return []

    @property
    def SupportedMimeTypes(self):
        return []

    def Quit(self):
        pass

    def Raise(self):
        pass

    def Next(self):
        self.signals.next_requested.emit()

    def Previous(self):
        self.signals.prev_requested.emit()

    def Pause(self):
        self.signals.pause_requested.emit()

    def PlayPause(self):
        self.signals.play_pause_requested.emit()

    def Stop(self):
        self.signals.stop_requested.emit()

    def Play(self):
        self.signals.play_requested.emit()

    def Seek(self, offset):
        self.signals.seek_requested.emit(offset)

    def SetPosition(self, track_id, position):
        self.signals.set_position_requested.emit(position)

    @property
    def PlaybackStatus(self):
        try:
            state = self.engine.player.playbackState()
            if state == QMediaPlayer.PlaybackState.PlayingState:
                return "Playing"
            if state == QMediaPlayer.PlaybackState.PausedState:
                return "Paused"
            return "Stopped"
        except RuntimeError:
            return "Stopped"

    @property
    def LoopStatus(self):
        try:
            if self.engine.is_looping:
                return "Track"
            return "None"
        except RuntimeError:
            return "None"

    @LoopStatus.setter
    def LoopStatus(self, val):
        self.signals.loop_status_changed.emit(val)

    @property
    def Shuffle(self):
        try:
            return self.engine.is_shuffled
        except RuntimeError:
            return False

    @Shuffle.setter
    def Shuffle(self, val):
        self.signals.shuffle_changed.emit(val)

    @property
    def Rate(self):
        return 1.0

    @Rate.setter
    def Rate(self, val):
        pass

    @property
    def Metadata(self):
        try:
            if 0 <= self.engine.idx < len(self.engine.queue):
                song = self.engine.queue[self.engine.idx]
                cid = song.cover_id

                if cid:
                    url = self.engine.client.get_cover_art_url(cid)
                else:
                    url = ""

                dur = song.duration_sec * 1000000

                return {
                    "mpris:trackid": GLib.Variant('o', "/org/mpris/MediaPlayer2/Track/0"),
                    "mpris:length": GLib.Variant('x', dur),
                    "mpris:artUrl": GLib.Variant('s', url),
                    "xesam:title": GLib.Variant('s', song.title),
                    "xesam:artist": GLib.Variant('as', [song.artist]),
                    "xesam:album": GLib.Variant('s', song.album)
                }
            return {"mpris:trackid": GLib.Variant('o', "/org/mpris/MediaPlayer2/Track/0")}
        except RuntimeError:
            return {"mpris:trackid": GLib.Variant('o', "/org/mpris/MediaPlayer2/Track/0")}

    @property
    def Volume(self):
        try:
            return self.engine.audio_output.volume()
        except RuntimeError:
            return 1.0

    @Volume.setter
    def Volume(self, val):
        self.signals.volume_changed.emit(val)

    @property
    def Position(self):
        try:
            return self.engine.player.position() * 1000
        except RuntimeError:
            return 0

    @property
    def MinimumRate(self):
        return 1.0

    @property
    def MaximumRate(self):
        return 1.0

    @property
    def CanGoNext(self):
        return True

    @property
    def CanGoPrevious(self):
        return True

    @property
    def CanPlay(self):
        return True

    @property
    def CanPause(self):
        return True

    @property
    def CanSeek(self):
        return True

    @property
    def CanControl(self):
        return True

class MprisService:
    def __init__(self, engine):
        if not HAS_MPRIS:
            return

        self.engine = engine
        self.signals = MprisSignals()
        self.player = MprisPlayer(engine, self.signals)

        self.signals.next_requested.connect(self.engine.next_song, Qt.QueuedConnection)
        self.signals.prev_requested.connect(self.engine.prev_song, Qt.QueuedConnection)
        self.signals.pause_requested.connect(self.engine.player.pause, Qt.QueuedConnection)
        self.signals.play_pause_requested.connect(self.engine.play_pause, Qt.QueuedConnection)
        self.signals.stop_requested.connect(self.engine.clear_queue, Qt.QueuedConnection)
        self.signals.play_requested.connect(self.engine.player.play, Qt.QueuedConnection)

        self.signals.seek_requested.connect(self._handle_seek, Qt.QueuedConnection)
        self.signals.set_position_requested.connect(self._handle_set_position, Qt.QueuedConnection)
        self.signals.loop_status_changed.connect(self._handle_loop, Qt.QueuedConnection)
        self.signals.shuffle_changed.connect(self._handle_shuffle, Qt.QueuedConnection)
        self.signals.volume_changed.connect(self._handle_volume, Qt.QueuedConnection)

        self.bus = SessionBus()
        try:
            self.bus.request_name(f"org.mpris.MediaPlayer2.{APP_NAME.replace(' ', '')}")
            self.bus.register_object("/org/mpris/MediaPlayer2", self.player, None)
        except RuntimeError as e:
            logger.log(f"Nie można zarejestrować MPRIS (prawdopodobnie inna instancja działa): {e}")
            try:
                import os
                self.bus.request_name(f"org.mpris.MediaPlayer2.{APP_NAME.replace(' ', '')}.instance{os.getpid()}")
                self.bus.register_object("/org/mpris/MediaPlayer2", self.player, None)
            except Exception:
                pass
        self.engine.track_changed.connect(self._upd_meta)
        self.engine.state_changed.connect(self._upd_state)
        self.engine.loop_mode_changed.connect(self._upd_loop)
        self.engine.shuffle_mode_changed.connect(self._upd_shuffle)

        self.loop = GLib.MainLoop()
        threading.Thread(target=self.loop.run, daemon=True).start()

    def _handle_seek(self, offset):
        try:
            new_pos = self.engine.player.position() + int(offset / 1000)
            if new_pos < 0:
                new_pos = 0
            self.engine.set_position(new_pos)
        except RuntimeError:
            pass

    def _handle_set_position(self, position):
        try:
            self.engine.set_position(int(position / 1000))
        except RuntimeError:
            pass

    def _handle_loop(self, val):
        if val in ["Track", "Playlist"]:
            self.engine.set_loop(True)
        else:
            self.engine.set_loop(False)
        GLib.idle_add(self.player.PropertiesChanged, "org.mpris.MediaPlayer2.Player", {"LoopStatus": self.player.LoopStatus}, [])

    def _handle_shuffle(self, val):
        self.engine.set_shuffle(val)
        GLib.idle_add(self.player.PropertiesChanged, "org.mpris.MediaPlayer2.Player", {"Shuffle": self.player.Shuffle}, [])

    def _handle_volume(self, val):
        self.engine.set_volume(int(val * 100))

    def _upd_meta(self, _):
        GLib.idle_add(self.player.PropertiesChanged, "org.mpris.MediaPlayer2.Player", {
            "Metadata": self.player.Metadata,
            "PlaybackStatus": self.player.PlaybackStatus
        }, [])

    def _upd_state(self, _):
        GLib.idle_add(self.player.PropertiesChanged, "org.mpris.MediaPlayer2.Player", {"PlaybackStatus": self.player.PlaybackStatus}, [])

    def _upd_loop(self, is_looping):
        GLib.idle_add(self.player.PropertiesChanged, "org.mpris.MediaPlayer2.Player", {"LoopStatus": self.player.LoopStatus}, [])

    def _upd_shuffle(self, is_shuffled):
        GLib.idle_add(self.player.PropertiesChanged, "org.mpris.MediaPlayer2.Player", {"Shuffle": self.player.Shuffle}, [])