import os
from pathlib import Path

APP_ID = "andromeda-music"

class PathsManager:
    @classmethod
    def get_config_dir(cls) -> Path:
        """Katalog na pliki konfiguracyjne np. ~/.config/navidrome-player"""
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_data_dir(cls) -> Path:
        """Katalog na dane aplikacji np. ~/.local/share/navidrome-player"""
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Katalog na cache np. ~/.cache/navidrome-player"""
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        p = Path(base) / APP_ID
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_audio_cache_dir(cls) -> Path:
        p = cls.get_cache_dir() / "audio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_config_file(cls) -> Path:
        return cls.get_config_dir() / "config.ini"

    @classmethod
    def get_cookies_file(cls) -> Path:
        """Plik na ciasteczka dla yt-dlp."""
        return cls.get_data_dir() / "cookies.txt"

    @classmethod
    def get_logs_dir(cls) -> Path:
        p = cls.get_data_dir() / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p
