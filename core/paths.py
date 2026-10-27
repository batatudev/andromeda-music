import os
os.environ["QT_API"] = "pyside6"

import shutil
import sqlite3
import re
from pathlib import Path

raw_app_id = os.environ.get("ANDROMEDA_APP_ID", "andromeda-music")
APP_ID = re.sub(r'[^a-zA-Z0-9_\-]', '', str(raw_app_id).strip()) or "andromeda-music"
LEGACY_APP_ID = "navidrome-player-v3"

class PathsManager:
    _migration_checked = False
    _server_migration_checked = False
    _active_server_id = "default"

    @classmethod
    def set_active_server_id(cls, server_id: str):
        """Ustawia identyfikator aktywnego serwera dla ścieżek partycjonowanych."""
        clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(server_id).strip())
        cls._active_server_id = clean_id if clean_id else "default"
        cls._migrate_legacy_single_server_data_if_needed()

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
        cls._migrate_legacy_data_if_needed(p)
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
    def _migrate_legacy_data_if_needed(cls, target_cache_dir: Path):
        """Automatycznie przenosi bazy z navidrome-player-v3, jeśli istnieją."""
        if cls._migration_checked or APP_ID != "andromeda-music":
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
    def _migrate_legacy_single_server_data_if_needed(cls):
        """Przenosi stare dane pojedynczego serwera z katalogu głównego do profilu servers/default/."""
        if cls._server_migration_checked:
            return
        cls._server_migration_checked = True

        root_cache = cls.get_cache_dir()
        root_data = cls.get_data_dir()
        target_cache = cls.get_server_cache_dir("default")
        target_data = cls.get_server_data_dir("default")

        db_files = ["library_cache.db", "offline_videos.db", "offline_audio.db"]
        for db_name in db_files:
            src_db = root_cache / db_name
            dst_db = target_cache / db_name
            if src_db.exists() and not dst_db.exists():
                try:
                    shutil.move(str(src_db), str(dst_db))
                    for ext in ["-wal", "-shm"]:
                        src_extra = root_cache / f"{db_name}{ext}"
                        dst_extra = target_cache / f"{db_name}{ext}"
                        if src_extra.exists():
                            shutil.move(str(src_extra), str(dst_extra))
                except Exception:
                    pass

        dirs_to_move_cache = ["images", "covers", "audio"]
        for dname in dirs_to_move_cache:
            src_dir = root_cache / dname
            dst_dir = target_cache / dname
            if src_dir.exists() and not dst_dir.exists():
                try:
                    shutil.move(str(src_dir), str(dst_dir))
                except Exception:
                    pass

        dirs_to_move_data = ["audio-offline", "video-offline", "custom_covers", "custom_artists"]
        for dname in dirs_to_move_data:
            src_dir = root_data / dname
            dst_dir = target_data / dname
            if src_dir.exists() and not dst_dir.exists():
                try:
                    shutil.move(str(src_dir), str(dst_dir))
                except Exception:
                    pass

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