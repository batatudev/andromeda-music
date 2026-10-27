import os
os.environ["QT_API"] = "pyside6"

import json
from PySide6.QtCore import QObject, Signal
import config
from core.paths import PathsManager

class ThemeManager(QObject):
    theme_changed = Signal(dict)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ThemeManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        super().__init__()
        self._initialized = True
        self.current_theme = {}
        self.reload_theme()

    def reload_theme(self):
        mode = config.APP_CONFIG.get("theme_mode", "system")
        if mode == "system":
            try:
                import darkdetect
                mode = "dark" if darkdetect.isDark() else "light"
            except ImportError:
                mode = "dark"

        if mode == "custom":
            self.current_theme = self._load_custom_theme()
        else:
            self.current_theme = self._get_builtin_theme(mode == "dark")

        config.THEME.update(self.current_theme)
        self.theme_changed.emit(self.current_theme)
        return self.current_theme

    def _get_builtin_theme(self, is_dark: bool) -> dict:
        acc = config.APP_CONFIG.get("accent", "#aa00ff")
        return {
            "bg_main": "#050505" if is_dark else "#f5f5f5",
            "bg_main_rgb": "5,5,5" if is_dark else "245,245,245",
            "text_main": "#ffffff" if is_dark else "#000000",
            "text_muted": "#888888" if is_dark else "#666666",
            "bg_card": "#111111" if is_dark else "#ffffff",
            "hover_card": "#181818" if is_dark else "#eeeeee",
            "bg_sidebar": "#000000" if is_dark else "#ebebeb",
            "border": "#121212" if is_dark else "#dddddd",
            "nav_bg": "#222222" if is_dark else "#dddddd",
            "nav_hover": "#333333" if is_dark else "#cccccc",
            "play_bg": "white" if is_dark else "#111111",
            "play_color": "black" if is_dark else "white",
            "accent": acc,
            "accent_rgba": self.hex_to_rgba(acc, 0.1),
            "heart_inactive": "#444444" if is_dark else "#cccccc",
            "btn_hover_bg": "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.1)",
            "btn_remove_hover": "rgba(231,76,60,0.2)",
            "btn_play_next_hover": "rgba(52,152,219,0.2)",
            "btn_add_pl_hover": "rgba(46,204,113,0.2)",
            "btn_add_hover": "rgba(230,126,34,0.2)"
        }

    def _load_custom_theme(self) -> dict:
        base = self._get_builtin_theme(True)
        custom_path = PathsManager.get_data_dir() / "custom_theme.json"
        if custom_path.exists():
            try:
                with open(custom_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    base.update(data)
                    return base
            except Exception:
                pass
        return base

    @staticmethod
    def hex_to_rgba(hex_color, alpha):
        hex_color = hex_color.lstrip('#')
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha})"
        except ValueError:
            return f"rgba(170, 0, 255, {alpha})"

theme_manager = ThemeManager()