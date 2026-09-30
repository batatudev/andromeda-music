import os
os.environ["QT_API"] = "pyside6"

import shutil
import sqlite3
from pathlib import Path

APP_ID = "andromeda-music"
LEGACY_APP_ID = "navidrome-player-v3"


class PathsManager:
    _migration_checked = False

    @classmethod
    def get_config_dir(cls) -> Path:
        """Katalog na pliki konfiguracyjne: ~/.config/andromeda-music"""
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_data_dir(cls) -> Path:
        """Katalog na trwałe dane użytkownika: ~/.local/share/andromeda-music"""
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Katalog na pamięć podręczną (cache): ~/.cache/andromeda-music"""
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        cls._migrate_legacy_data_if_needed(p)
        return p

    @classmethod
    def _migrate_legacy_data_if_needed(cls, target_cache_dir: Path):
        """Automatycznie przenosi bazy z navidrome-player-v3, jeśli istnieją."""
        if cls._migration_checked:
            return
        cls._migration_checked = True

        legacy_base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        legacy_dir = Path(legacy_base) / LEGACY_APP_ID

        if not legacy_dir.exists():
            return

        db_files = ["library_cache.db", "offline_videos.db", "offline_audio.db"]
        for fname in db_files:
            src = legacy_dir / fname
            dst = target_cache_dir / fname
            if src.exists() and (not dst.exists() or dst.stat().st_size == 0):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

        legacy_music = legacy_dir / "offline_music"
        target_audio = cls.get_data_dir() / "audio-offline"
        if legacy_music.exists() and not target_audio.exists():
            try:
                shutil.copytree(legacy_music, target_audio, dirs_exist_ok=True)
            except Exception:
                pass

    @classmethod
    def get_audio_cache_dir(cls) -> Path:
        """Katalog na tymczasowy bufor strumieniowania: ~/.cache/andromeda-music/audio"""
        p = cls.get_cache_dir() / "audio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_images_cache_dir(cls) -> Path:
        """Katalog na cache okładek i miniatur: ~/.cache/andromeda-music/images"""
        p = cls.get_cache_dir() / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_offline_videos_dir(cls) -> Path:
        """Trwały katalog na pobrane teledyski offline: ~/.local/share/andromeda-music/video-offline"""
        p = cls.get_data_dir() / "video-offline"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_offline_audio_dir(cls) -> Path:
        """Trwały katalog na pobraną muzykę offline: ~/.local/share/andromeda-music/audio-offline"""
        p = cls.get_data_dir() / "audio-offline"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_video_db_path(cls) -> Path:
        """Baza SQLite pobrań wideo: ~/.cache/andromeda-music/offline_videos.db"""
        return cls.get_cache_dir() / "offline_videos.db"

    @classmethod
    def get_audio_db_path(cls) -> Path:
        """Baza SQLite pobrań audio: ~/.cache/andromeda-music/offline_audio.db"""
        return cls.get_cache_dir() / "offline_audio.db"

    @classmethod
    def get_library_cache_db_path(cls) -> Path:
        """Lokalna kopia biblioteki Navidrome: ~/.cache/andromeda-music/library_cache.db"""
        return cls.get_cache_dir() / "library_cache.db"

    @classmethod
    def get_config_file(cls) -> Path:
        """Główny plik konfiguracyjny: ~/.config/andromeda-music/config.ini"""
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
        """Włącza trwały tryb WAL w nagłówku bazy (wywoływane jednorazowo w _init_db)."""
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