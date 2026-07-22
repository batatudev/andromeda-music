# WERSJA PROJEKTU: 14.22
# MODYFIKOWANY PLIK: core/backup_manager.py
# OPIS ZMIAN: Dodanie systemu kopii zapasowych i przywracania ustawień fabrycznych.

import os
import shutil
import time
from pathlib import Path
from core.paths import PathsManager

class BackupManager:
    @staticmethod
    def create_backup():
        """Tworzy zrzut obecnej konfiguracji (config.ini)."""
        config_file = PathsManager.get_config_file()
        if not config_file.exists():
            return None
        
        backup_dir = PathsManager.get_data_dir() / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time())
        backup_file = backup_dir / f"config_backup_{timestamp}.ini"
        
        shutil.copy2(config_file, backup_file)
        return backup_file

    @staticmethod
    def restore_backup(backup_file: Path):
        """Przywraca konfigurację z podanego pliku kopii."""
        if not backup_file.exists():
            raise FileNotFoundError("Plik kopii zapasowej nie istnieje.")
        
        config_file = PathsManager.get_config_file()
        shutil.copy2(backup_file, config_file)

    @staticmethod
    def factory_reset():
        """Usuwa obecną konfigurację i cache (Reset do ustawień fabrycznych)."""
        config_file = PathsManager.get_config_file()
        if config_file.exists():
            config_file.unlink()
        
        # Czyszczenie cache
        cache_dir = PathsManager.get_cache_dir()
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
