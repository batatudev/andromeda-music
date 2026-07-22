# WERSJA PROJEKTU: 14.22
# MODYFIKOWANY PLIK: config.py
# OPIS ZMIAN: Wdrożenie dynamicznego wykrywania motywu systemowego (theme_mode) i opóźnionej inicjalizacji palety kolorów po utworzeniu QApplication.

import os
os.environ["QT_API"] = "pyside6"

import configparser
from enum import IntEnum
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt

from core.paths import PathsManager

APP_NAME = "Andromeda Music"
APP_ICON_PATH = "assets/logo.png"

class Pages(IntEnum):
    HOME = 0
    FAVS = 1
    QUEUE = 2
    ALBUMS = 3
    DETAILS = 4
    TRACKS = 5
    ARTISTS = 6
    SETTINGS = 7
    NOW_PLAYING = 8
    DEV_MODE = 9
    SEARCH = 10
    DOWNLOADS = 11

APP_CONFIG = {
    "url": "",
    "username": "",
    "password": "",
    "theme_mode": "system",
    "dark_mode": True,
    "accent": "#1db954",
    "volume": 80,
    "video_resolution": "1080p",
    "video_min_res": "480p",
    "video_auto_res": True,
    "video_dynamic_opacity": 30,
    "video_dynamic_blur": 0,
    "video_static_opacity": 80,
    "video_static_blur": 60,
    "video_offline_path": str(PathsManager.get_data_dir() / "video-offline"),
    "video_offline_quality": "1080p",
    "video_smart_auto_play": False,
    "video_auto_dl_favs": False,
    "video_auto_dl_playlists": []
}

def load_config():
    cfg = configparser.ConfigParser()
    config_path = PathsManager.get_config_file()
    
    if config_path.exists():
        cfg.read(config_path)
        
    if "Navidrome" in cfg:
        APP_CONFIG["url"] = cfg["Navidrome"].get("url", "")
        APP_CONFIG["username"] = cfg["Navidrome"].get("username", "")
        APP_CONFIG["password"] = cfg["Navidrome"].get("password", "")
    if "Theme" in cfg:
        if "theme_mode" in cfg["Theme"]:
            APP_CONFIG["theme_mode"] = cfg["Theme"].get("theme_mode", "system")
        else:
            legacy_dark = cfg["Theme"].getboolean("dark_mode", fallback=True)
            APP_CONFIG["theme_mode"] = "dark" if legacy_dark else "light"
        APP_CONFIG["accent"] = cfg["Theme"].get("accent", fallback="#1db954")
        APP_CONFIG["volume"] = cfg["Theme"].getint("volume", fallback=80)
        APP_CONFIG["dev_mode"] = cfg["Theme"].getboolean("dev_mode", fallback=False)
    if "Video" in cfg:
        APP_CONFIG["video_resolution"] = cfg["Video"].get("resolution", fallback="1080p")
        APP_CONFIG["video_min_res"] = cfg["Video"].get("min_resolution", fallback="480p")
        APP_CONFIG["video_auto_res"] = cfg["Video"].getboolean("auto_res", fallback=True)
        APP_CONFIG["video_dynamic_opacity"] = cfg["Video"].getint("dynamic_opacity", fallback=30)
        APP_CONFIG["video_dynamic_blur"] = cfg["Video"].getint("dynamic_blur", fallback=0)
        APP_CONFIG["video_static_opacity"] = cfg["Video"].getint("static_opacity", fallback=80)
        APP_CONFIG["video_static_blur"] = cfg["Video"].getint("static_blur", fallback=60)
        APP_CONFIG["video_offline_path"] = cfg["VideoOffline"].get("path", fallback=str(PathsManager.get_data_dir() / "video-offline"))
        APP_CONFIG["video_offline_quality"] = cfg["VideoOffline"].get("quality", fallback="1080p")
        APP_CONFIG["video_smart_auto_play"] = cfg["VideoOffline"].getboolean("smart_auto_play", fallback=False)
        APP_CONFIG["video_auto_dl_favs"] = cfg["VideoOffline"].getboolean("auto_dl_favs", fallback=False)
        dl_pl = cfg["VideoOffline"].get("auto_dl_playlists", fallback="")
        APP_CONFIG["video_auto_dl_playlists"] = [p.strip() for p in dl_pl.split(",") if p.strip()]

def save_config():
    cfg = configparser.ConfigParser()
    cfg["Navidrome"] = {
        "url": APP_CONFIG["url"],
        "username": APP_CONFIG["username"],
        "password": APP_CONFIG["password"]
    }
    cfg["Theme"] = {
        "theme_mode": APP_CONFIG.get("theme_mode", "system"),
        "accent": APP_CONFIG["accent"],
        "volume": str(APP_CONFIG["volume"]),
        "dev_mode": str(APP_CONFIG.get("dev_mode", False))
    }
    cfg["Video"] = {
        "resolution": APP_CONFIG["video_resolution"],
        "min_resolution": APP_CONFIG["video_min_res"],
        "auto_res": str(APP_CONFIG["video_auto_res"]),
        "dynamic_opacity": str(APP_CONFIG["video_dynamic_opacity"]),
        "dynamic_blur": str(APP_CONFIG["video_dynamic_blur"]),
        "static_opacity": str(APP_CONFIG["video_static_opacity"]),
        "static_blur": str(APP_CONFIG["video_static_blur"])
    }
    cfg["VideoOffline"] = {
        "path": APP_CONFIG.get("video_offline_path", str(PathsManager.get_data_dir() / "video-offline")),
        "quality": APP_CONFIG.get("video_offline_quality", "1080p"),
        "smart_auto_play": str(APP_CONFIG.get("video_smart_auto_play", False)),
        "auto_dl_favs": str(APP_CONFIG.get("video_auto_dl_favs", False)),
        "auto_dl_playlists": ",".join(APP_CONFIG.get("video_auto_dl_playlists", []))
    }
    
    config_path = PathsManager.get_config_file()
    with open(config_path, "w") as f:
        cfg.write(f)

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

def get_theme_colors():
    dark = APP_CONFIG["dark_mode"]
    acc = APP_CONFIG["accent"]

    return {
        "bg_main": "#050505" if dark else "#f5f5f5",
        "bg_main_rgb": "5,5,5" if dark else "245,245,245",
        "text_main": "#ffffff" if dark else "#000000",
        "text_muted": "#888888" if dark else "#666666",
        "bg_card": "#111111" if dark else "#ffffff",
        "hover_card": "#181818" if dark else "#eeeeee",
        "bg_sidebar": "#000000" if dark else "#ebebeb",
        "border": "#121212" if dark else "#dddddd",
        "nav_bg": "#222222" if dark else "#dddddd",
        "nav_hover": "#333333" if dark else "#cccccc",
        "play_bg": "white" if dark else "#111111",
        "play_color": "black" if dark else "white",
        "accent": acc,
        "accent_rgba": hex_to_rgba(acc, 0.1),
        "heart_inactive": "#444444" if dark else "#cccccc",
        "btn_hover_bg": "rgba(255,255,255,0.1)" if dark else "rgba(0,0,0,0.1)",
        "btn_remove_hover": "rgba(231,76,60,0.2)",
        "btn_play_next_hover": "rgba(52,152,219,0.2)",
        "btn_add_pl_hover": "rgba(46,204,113,0.2)",
        "btn_add_hover": "rgba(230,126,34,0.2)"
    }

def init_theme():
    mode = APP_CONFIG.get("theme_mode", "system")
    if mode == "system":
        hints = QGuiApplication.styleHints()
        is_dark = (hints.colorScheme() == Qt.ColorScheme.Dark)
        APP_CONFIG["dark_mode"] = is_dark
    elif mode == "light":
        APP_CONFIG["dark_mode"] = False
    else:
        APP_CONFIG["dark_mode"] = True
    THEME.update(get_theme_colors())

load_config()
THEME = get_theme_colors()

def get_app_style():
    return f"""
    QMainWindow, QWidget {{
        background-color: {THEME['bg_main']};
        color: {THEME['text_main']};
        font-family: "Noto Sans", sans-serif;
    }}
    QScrollArea {{ border: none; background-color: transparent; }}
    QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0px; }}
    QScrollBar::handle:vertical {{ background: {THEME['nav_bg']}; min-height: 30px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: {THEME['nav_hover']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    #Sidebar {{ background-color: {THEME['bg_sidebar']}; border-right: 1px solid {THEME['border']}; }}
    #Sidebar QPushButton[isMenu="true"] {{
        background-color: transparent; border: none; text-align: left;
        padding: 12px 15px; font-size: 13px; border-radius: 6px;
        color: {THEME['text_muted']}; margin: 2px 10px;
    }}
    #Sidebar QPushButton[isMenu="true"]:hover {{ color: {THEME['text_main']}; background-color: {THEME['bg_card']}; }}
    #Sidebar QPushButton[active="true"] {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; }}

    #NavBtn {{ background-color: {THEME['nav_bg']}; border-radius: 18px; border: none; padding: 0px !important; margin: 0px; }}
    #NavBtn:hover {{ background-color: {THEME['nav_hover']}; }}

    #PlayerBar {{ background-color: {THEME['bg_sidebar']}; border-top: 1px solid {THEME['border']}; padding: 5px; }}

    #PlayPauseBtn, #CardPlayBtn {{ background-color: {THEME['play_bg']}; border-radius: 23px; border: none; }}
    #PlayPauseBtn:hover, #CardPlayBtn:hover {{ background-color: {THEME['accent']}; }}

    #ControlBtn {{ background: transparent; border: none; border-radius: 18px; }}
    #ControlBtn:hover {{ background: {THEME['btn_hover_bg']}; }}

    #HeroSection, #QueueHeader {{ border-radius: 15px; margin-bottom: 25px; }}
    #HeroTitle {{ font-size: 42px; font-weight: bold; background: transparent; border: none; }}
    #HeroSubtitle {{ font-size: 12px; color: {THEME['accent']}; font-weight: bold; letter-spacing: 2px; background: transparent; }}

    #Card {{ background-color: {THEME['bg_card']}; border-radius: 12px; border: none; }}
    #Card:hover {{ background-color: {THEME['hover_card']}; }}
    #CardTitle {{ font-weight: bold; font-size: 15px; margin-top: 8px; background: transparent; color: {THEME['text_main']}; }}
    #CardArtist {{ font-size: 13px; color: {THEME['text_muted']}; background: transparent; }}

    #SongItem {{ background-color: transparent; border-radius: 8px; padding: 8px 12px; }}
    #SongItem:hover {{ background-color: {THEME['bg_card']}; }}
    #SongItem QLabel {{ background: transparent; border: none; }}
    #SongItem[active="true"] {{ background-color: {THEME['accent_rgba']}; }}

    QSlider::groove:horizontal {{ height: 4px; background: {THEME['nav_bg']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {THEME['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {THEME['text_main']}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
    """