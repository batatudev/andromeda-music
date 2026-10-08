import os
os.environ["QT_API"] = "pyside6"

import shutil
from utils import logger
from core.i18n import tr

class SystemHealthChecker:
    @staticmethod
    def check_ffmpeg() -> bool:
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def check_mpris() -> bool:
        try:
            import pydbus
            import gi
            return True
        except ImportError:
            return False

    @classmethod
    def perform_startup_check(cls, main_window):
        if not cls.check_ffmpeg():
            logger.log("OSTRZEŻENIE: Brak narzędzia 'ffmpeg' w systemie!")
            if hasattr(main_window, 'show_toast'):
                msg = tr(
                    "health.ffmpeg_missing",
                    "Brak pakietu ffmpeg w systemie. Scalanie wideo i pobieranie 1080p może nie działać poprawnie."
                )
                main_window.show_toast(
                    msg,
                    title=tr("health.warning", "Ostrzeżenie systemowe"),
                    icon_str="fa5s.exclamation-triangle",
                    icon_color="#e67e22",
                    duration=7000
                )