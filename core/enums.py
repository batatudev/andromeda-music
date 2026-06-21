# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: core/enums.py
# OPIS ZMIAN: Rozszerzony zestaw stanów dla pełnej eliminacji magic strings.

from enum import Enum

class EngineState(str, Enum):
    STOPPED = "Zatrzymany"
    PLAYING_SMOOTH = "Odtwarzanie Płynne"
    PAUSED = "Wstrzymany (Pauza)"
    BUFFERING = "Buforowanie / Zacięcie"
    AUDIO_DOWNLOADING = "Pobieranie Audio..."
    WAITING_VIDEO_SYNC = "Oczekiwanie na wideo (Sync-Start)..."
    ARF_REDUCTION = "ARF Redukcja"
    VIDEO_DISABLED = "Wideo wyłączone (Brak łącza)"
    AUDIO_ERROR = "Błąd pobierania audio"
    RESOLVING_YTDLP = "Rozwiązywanie YT-DLP..."
    LOADING_ABORTED = "Przerwano ładowanie"

class MediaType(str, Enum):
    ARTIST = "artist"
    ALBUM = "album"
    PLAYLIST = "playlist"
    SONG = "song"
    VIDEO = "video"
    AUDIO = "audio"

class TelemetryEvent(str, Enum):
    HEARTBEAT = "HRT"
    MASK_ON = "MASK_ON"
    MASK_OFF = "MASK_OFF"
    SEEK_REQ = "SEEK_REQ"

class VideoResolution(str, Enum):
    RES_1080P = "1080p"
    RES_720P = "720p"
    RES_480P = "480p"
    RES_240P = "240p"
