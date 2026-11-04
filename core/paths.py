import os
os.environ["QT_API"] = "pyside6"

import sqlite3
import re
from pathlib import Path

raw_app_id = os.environ.get("ANDROMEDA_APP_ID", "andromeda-music")
APP_ID = re.sub(r'[^a-zA-Z0-9_\-]', '', str(raw_app_id).strip()) or "andromeda-music"

class PathsManager:
    _active_server_id = "default"

    @classmethod
    def set_active_server_id(cls, server_id: str):
        """Ustawia identyfikator aktywnego serwera dla ścieżek partycjonowanych."""
        clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(server_id).strip())
        cls._active_server_id = clean_id if clean_id else "default"

    @classmethod
    def get_active_server_id(cls) -> str:
        """Zwraca identyfikator aktywnego serwera."""
        return cls._active_server_id

    @classmethod
    def get_config_dir(cls) -> Path:
        """Katalog na pliki konfiguracyjne: ~/.config/<APP_ID>"""
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_data_dir(cls) -> Path:
        """Globalny katalog na trwałe dane użytkownika: ~/.local/share/<APP_ID>"""
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Globalny katalog na pamięć podręczną (cache): ~/.cache/<APP_ID>"""
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_server_data_dir(cls, server_id: str = None) -> Path:
        """Izolowany katalog na trwałe dane konkretnego serwera: ~/.local/share/<APP_ID>/servers/<server_id>"""
        sid = server_id or cls._active_server_id
        clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(sid).strip()) or "default"
        p = cls.get_data_dir() / "servers" / clean_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_server_cache_dir(cls, server_id: str = None) -> Path:
        """Izolowany katalog na pamięć podręczną konkretnego serwera: ~/.cache/<APP_ID>/servers/<server_id>"""
        sid = server_id or cls._active_server_id
        clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(sid).strip()) or "default"
        p = cls.get_cache_dir() / "servers" / clean_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_audio_cache_dir(cls) -> Path:
        """Katalog na tymczasowy bufor strumieniowania dla aktywnego serwera."""
        p = cls.get_server_cache_dir() / "audio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_images_cache_dir(cls) -> Path:
        """Katalog na cache okładek dla aktywnego serwera."""
        p = cls.get_server_cache_dir() / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_covers_cache_dir(cls) -> Path:
        """Katalog na zapisane miniaturki okładek dla aktywnego serwera."""
        p = cls.get_server_cache_dir() / "covers"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_offline_videos_dir(cls) -> Path:
        """Trwały katalog na pobrane teledyski dla aktywnego serwera."""
        p = cls.get_server_data_dir() / "video-offline"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_offline_audio_dir(cls) -> Path:
        """Trwały katalog na pobraną muzykę dla aktywnego serwera."""
        p = cls.get_server_data_dir() / "audio-offline"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_custom_covers_dir(cls) -> Path:
        """Katalog na własne okładki albumów dla aktywnego serwera."""
        p = cls.get_server_data_dir() / "custom_covers"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_custom_artists_dir(cls) -> Path:
        """Katalog na własne zdjęcia artystów dla aktywnego serwera."""
        p = cls.get_server_data_dir() / "custom_artists"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_video_db_path(cls) -> Path:
        """Baza SQLite pobrań wideo dla aktywnego serwera."""
        return cls.get_server_cache_dir() / "offline_videos.db"

    @classmethod
    def get_audio_db_path(cls) -> Path:
        """Baza SQLite pobrań audio dla aktywnego serwera."""
        return cls.get_server_cache_dir() / "offline_audio.db"

    @classmethod
    def get_library_cache_db_path(cls) -> Path:
        """Lokalna kopia biblioteki Navidrome dla aktywnego serwera."""
        return cls.get_server_cache_dir() / "library_cache.db"

    @classmethod
    def get_config_file(cls) -> Path:
        """Główny plik konfiguracyjny: ~/.config/<APP_ID>/config.ini"""
        return cls.get_config_dir() / "config.ini"

    @classmethod
    def get_cookies_file(cls) -> Path:
        """Plik na ciasteczka dla yt-dlp."""
        return cls.get_data_dir() / "cookies.txt"

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Katalog na logi zdarzeń i telemetrię."""
        p = cls.get_data_dir() / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def enable_wal_mode(cls, db_path: Path | str):
        """Włącza trwały tryb WAL w nagłówku bazy."""
        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.close()
        except Exception:
            pass

    @classmethod
    def get_db_connection(cls, db_path: Path | str, timeout: float = 10.0) -> sqlite3.Connection:
        """
        Zwraca szybkie połączenie do SQLite bez blokowania nagłówka bazy.
        - synchronous = NORMAL: bezpieczna redukcja fsync.
        - busy_timeout = 5000: automatyczny retry bez wyjątku 'database is locked'.
        - temp_store = MEMORY: tymczasowe indeksy i tabele alokowane w RAM zamiast dysku.
        """
        path_obj = Path(db_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path_obj), timeout=timeout)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        return conn