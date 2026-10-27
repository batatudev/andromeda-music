import os
os.environ["QT_API"] = "pyside6"

import re
import threading
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtMultimedia import QMediaPlayer

from config import APP_NAME
from core.paths import PathsManager, APP_ID
from utils import logger

try:
    from pydbus import SessionBus
    from pydbus.generic import signal
    from gi.repository import GLib
    HAS_MPRIS = True
except ImportError as e:
    HAS_MPRIS = False
    print(f"\n[MPRIS BŁĄD] Brak wymaganych modułów D-Bus (pydbus / PyGObject): {e}")
    print("[MPRIS INFO] Zainstaluj pakiety: pip install pydbus PyGObject\n")
    logger.log(f"Brak bibliotek pydbus/gi. Integracja MPRIS wyłączona: {e}")

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
            <signal name="Seeked">
                <arg type="x" name="Position"/>
            </signal>
        </interface>
    </node>
    """

    PropertiesChanged = signal()
    Seeked = signal()

    def __init__(self, signals):
        self.signals = signals
        self._playback_status = "Stopped"
        self._loop_status = "None"
        self._shuffle = False
        self._volume = 1.0
        self._position_us = 0
        self._can_go_next = True
        self._can_go_previous = True
        self._metadata = {
            "mpris:trackid": GLib.Variant('o', "/org/mpris/MediaPlayer2/TrackList/NoTrack")
        }

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
        desktop_filename = f"{APP_ID}.desktop"
        standard_dirs = [
            Path.home() / ".local" / "share" / "applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications")
        ]
        for d in standard_dirs:
            if (d / desktop_filename).exists():
                return APP_ID
        return ""

    @property
    def SupportedUriSchemes(self):
        return ["file", "http", "https"]

    @property
    def SupportedMimeTypes(self):
        return ["audio/mpeg", "audio/mp4", "audio/x-wav", "video/mp4", "video/webm"]

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
        return self._playback_status

    @property
    def LoopStatus(self):
        return self._loop_status

    @LoopStatus.setter
    def LoopStatus(self, val):
        self.signals.loop_status_changed.emit(val)

    @property
    def Shuffle(self):
        return self._shuffle

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
        return self._metadata

    @property
    def Volume(self):
        return self._volume

    @Volume.setter
    def Volume(self, val):
        self.signals.volume_changed.emit(val)

    @property
    def Position(self):
        return self._position_us

    @property
    def MinimumRate(self):
        return 1.0

    @property
    def MaximumRate(self):
        return 1.0

    @property
    def CanGoNext(self):
        return self._can_go_next

    @property
    def CanGoPrevious(self):
        return self._can_go_previous

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
        self.player = MprisPlayer(self.signals)

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

        self.loop = GLib.MainLoop()
        self._loop_thread = threading.Thread(target=self.loop.run, daemon=True)
        self._loop_thread.start()

        self.bus = SessionBus()
        self._publication = None

        bus_name = "org.mpris.MediaPlayer2.AndromedaMusic"

        try:
            self._publication = self.bus.publish(bus_name, ("/org/mpris/MediaPlayer2", self.player))
            print(f"[MPRIS OK] Zarejestrowano w D-Bus: '{bus_name}'")
            logger.log(f"MPRIS: Opublikowano serwis '{bus_name}'")
        except Exception as e:
            fallback_name = f"{bus_name}.instance{os.getpid()}"
            print(f"[MPRIS OSTRZEŻENIE] Nazwa '{bus_name}' zajęta ({e}). Rejestracja instancji: '{fallback_name}'")
            try:
                self._publication = self.bus.publish(fallback_name, ("/org/mpris/MediaPlayer2", self.player))
                print(f"[MPRIS OK] Zarejestrowano instancję: '{fallback_name}'")
                logger.log(f"MPRIS: Opublikowano instancję '{fallback_name}'")
            except Exception as e2:
                print(f"[MPRIS BŁĄD] Krytyczny błąd rejestracji D-Bus: {e2}")
                logger.log(f"MPRIS: Krytyczny błąd publikacji D-Bus: {e2}")

        self.engine.track_changed.connect(self._on_track_changed)
        self.engine.state_changed.connect(self._on_state_changed)
        self.engine.position_changed.connect(self._on_position_changed)
        self.engine.loop_mode_changed.connect(self._on_loop_changed)
        self.engine.shuffle_mode_changed.connect(self._on_shuffle_changed)
        self.engine.queue_cleared.connect(self._on_queue_cleared)

        self._emit_current_state()

    def _resolve_cover_uri(self, song):
        if not song:
            return None

        cid = getattr(song, 'cover_id', None)
        if not cid:
            return None

        covers_dir = PathsManager.get_covers_cache_dir()
        for ext in [".jpg", ".png", ".jpeg"]:
            cf = covers_dir / f"{cid}{ext}"
            if cf.exists():
                return cf.as_uri()

        custom_covers = PathsManager.get_custom_covers_dir()
        for ext in [".jpg", ".png", ".jpeg"]:
            cf = custom_covers / f"{cid}{ext}"
            if cf.exists():
                return cf.as_uri()

        img_cache = PathsManager.get_images_cache_dir()
        for ext in [".jpg", ".png"]:
            cf = img_cache / f"{cid}{ext}"
            if cf.exists():
                return cf.as_uri()

        if hasattr(self.engine, 'client') and self.engine.client:
            url = self.engine.client.get_cover_art_url(cid)
            if url and (url.startswith("http://") or url.startswith("https://")):
                return url

        return None

    def _build_metadata(self, song):
        meta = {}
        if song:
            raw_id = getattr(song, 'item_id', '0')
            clean_id = re.sub(r'[^a-zA-Z0-9_]', '_', str(raw_id)) or "0"

            meta["mpris:trackid"] = GLib.Variant('o', f"/org/mpris/MediaPlayer2/Track/{clean_id}")

            dur_sec = getattr(song, 'duration_sec', 0)
            dur_us = int(dur_sec * 1000000)
            if dur_us > 0:
                meta["mpris:length"] = GLib.Variant('x', dur_us)

            title = getattr(song, 'title', '')
            if title:
                meta["xesam:title"] = GLib.Variant('s', str(title))

            artist = getattr(song, 'artist', '')
            if artist:
                meta["xesam:artist"] = GLib.Variant('as', [str(artist)])

            album = getattr(song, 'album', '')
            if album:
                meta["xesam:album"] = GLib.Variant('s', str(album))

            art_uri = self._resolve_cover_uri(song)
            if art_uri:
                meta["mpris:artUrl"] = GLib.Variant('s', str(art_uri))
        else:
            meta["mpris:trackid"] = GLib.Variant('o', "/org/mpris/MediaPlayer2/TrackList/NoTrack")

        return meta

    def _emit_current_state(self):
        try:
            changed = {
                "PlaybackStatus": self.player._playback_status,
                "Metadata": self.player._metadata,
                "CanControl": True,
                "CanPlay": True,
                "CanPause": True,
                "CanGoNext": self.player._can_go_next,
                "CanGoPrevious": self.player._can_go_previous,
                "LoopStatus": self.player._loop_status,
                "Shuffle": self.player._shuffle
            }
            GLib.idle_add(self._notify_properties_changed, changed)
        except Exception as e:
            logger.log(f"MPRIS emit state error: {e}")

    def _notify_properties_changed(self, changed_dict):
        try:
            self.player.PropertiesChanged("org.mpris.MediaPlayer2.Player", changed_dict, [])
        except Exception as e:
            logger.log(f"MPRIS PropertiesChanged error: {e}")

    def _on_track_changed(self, song):
        self.player._metadata = self._build_metadata(song)
        self.player._can_go_next = bool(len(self.engine.queue) > 1)
        self.player._can_go_previous = bool(len(self.engine.queue) > 1)

        title = getattr(song, 'title', 'Nieznany') if song else 'Brak'
        artist = getattr(song, 'artist', '') if song else ''
        print(f"[MPRIS] Zmiana utworu: '{title}' - '{artist}' | Status: {self.player._playback_status}")

        changed = {
            "Metadata": self.player._metadata,
            "PlaybackStatus": self.player._playback_status,
            "CanGoNext": self.player._can_go_next,
            "CanGoPrevious": self.player._can_go_previous
        }
        GLib.idle_add(self._notify_properties_changed, changed)

    def _on_state_changed(self, is_playing):
        if is_playing:
            self.player._playback_status = "Playing"
        else:
            state = self.engine.player.playbackState()
            if state == QMediaPlayer.PlaybackState.PausedState:
                self.player._playback_status = "Paused"
            else:
                self.player._playback_status = "Stopped"

        if not self.player._metadata or "xesam:title" not in self.player._metadata:
            current_song = self.engine.queue_mgr.current_song() if hasattr(self.engine, 'queue_mgr') else None
            if current_song:
                self.player._metadata = self._build_metadata(current_song)

        print(f"[MPRIS] Zmiana stanu odtwarzania -> {self.player._playback_status}")

        changed = {
            "PlaybackStatus": self.player._playback_status,
            "Metadata": self.player._metadata
        }
        GLib.idle_add(self._notify_properties_changed, changed)

    def _on_position_changed(self, pos_ms):
        self.player._position_us = int(pos_ms * 1000)

    def _on_loop_changed(self, is_looping):
        self.player._loop_status = "Track" if is_looping else "None"
        changed = {"LoopStatus": self.player._loop_status}
        GLib.idle_add(self._notify_properties_changed, changed)

    def _on_shuffle_changed(self, is_shuffled):
        self.player._shuffle = bool(is_shuffled)
        changed = {"Shuffle": self.player._shuffle}
        GLib.idle_add(self._notify_properties_changed, changed)

    def _on_queue_cleared(self):
        self.player._playback_status = "Stopped"
        self.player._metadata = {
            "mpris:trackid": GLib.Variant('o', "/org/mpris/MediaPlayer2/TrackList/NoTrack")
        }
        print("[MPRIS] Kolejka wyczyszczona -> Stopped")
        changed = {
            "PlaybackStatus": "Stopped",
            "Metadata": self.player._metadata
        }
        GLib.idle_add(self._notify_properties_changed, changed)

    def _handle_seek(self, offset):
        try:
            new_pos_ms = self.engine.player.position() + int(offset / 1000)
            if new_pos_ms < 0:
                new_pos_ms = 0
            self.engine.set_position(new_pos_ms)
            new_pos_us = int(new_pos_ms * 1000)
            self.player._position_us = new_pos_us
            GLib.idle_add(self.player.Seeked, new_pos_us)
        except Exception:
            pass

    def _handle_set_position(self, position):
        try:
            new_pos_ms = int(position / 1000)
            if new_pos_ms < 0:
                new_pos_ms = 0
            self.engine.set_position(new_pos_ms)
            self.player._position_us = int(position)
            GLib.idle_add(self.player.Seeked, int(position))
        except Exception:
            pass

    def _handle_loop(self, val):
        if val in ["Track", "Playlist"]:
            self.engine.set_loop(True)
        else:
            self.engine.set_loop(False)

    def _handle_shuffle(self, val):
        self.engine.set_shuffle(val)

    def _handle_volume(self, val):
        vol_pct = max(0, min(100, int(val * 100)))
        self.engine.set_volume(vol_pct)
        self.player._volume = float(val)