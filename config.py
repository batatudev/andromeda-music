import os
os.environ["QT_API"] = "pyside6"

import configparser
from enum import IntEnum
from PySide6.QtGui import QGuiApplication, QPixmap, QPainter, QColor, QPen
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
    "video_auto_dl_playlists": [],
    "audio_auto_dl_favs": False,
    "audio_auto_dl_playlists": [],
    "hide_undownloaded_offline": False
}

def get_combo_arrow_path(is_hover=False) -> str:
    cache_dir = PathsManager.get_cache_dir()
    fname = "combo_arrow_hover.png" if is_hover else "combo_arrow.png"
    arrow_file = cache_dir / fname
    if not arrow_file.exists():
        pix = QPixmap(12, 8)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#ffffff" if is_hover else "#888888"))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(1, 1, 6, 6)
        painter.drawLine(6, 6, 11, 1)
        painter.end()
        pix.save(str(arrow_file), "PNG")
    return str(arrow_file).replace("\\", "/")

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
        APP_CONFIG["language"] = cfg["Theme"].get("language", fallback="pl")
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
    if "VideoOffline" in cfg:
        APP_CONFIG["video_offline_path"] = cfg["VideoOffline"].get("path", fallback=str(PathsManager.get_data_dir() / "video-offline"))
        APP_CONFIG["video_offline_quality"] = cfg["VideoOffline"].get("quality", fallback="1080p")
        APP_CONFIG["video_smart_auto_play"] = cfg["VideoOffline"].getboolean("smart_auto_play", fallback=False)
        APP_CONFIG["video_auto_dl_favs"] = cfg["VideoOffline"].getboolean("auto_dl_favs", fallback=False)
        dl_pl = cfg["VideoOffline"].get("auto_dl_playlists", fallback="")
        APP_CONFIG["video_auto_dl_playlists"] = [p.strip() for p in dl_pl.split(",") if p.strip()]
    if "AudioOffline" in cfg:
        APP_CONFIG["audio_auto_dl_favs"] = cfg["AudioOffline"].getboolean("auto_dl_favs", fallback=False)
        a_dl_pl = cfg["AudioOffline"].get("auto_dl_playlists", fallback="")
        APP_CONFIG["audio_auto_dl_playlists"] = [p.strip() for p in a_dl_pl.split(",") if p.strip()]
        APP_CONFIG["hide_undownloaded_offline"] = cfg["AudioOffline"].getboolean("hide_undownloaded_offline", fallback=False)

def save_config():
    cfg = configparser.ConfigParser()
    cfg["Navidrome"] = {
        "url": APP_CONFIG["url"],
        "username": APP_CONFIG["username"],
        "password": APP_CONFIG["password"]
    }
    cfg["Theme"] = {
        "theme_mode": APP_CONFIG.get("theme_mode", "system"),
        "language": APP_CONFIG.get("language", "pl"),
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
    cfg["AudioOffline"] = {
        "auto_dl_favs": str(APP_CONFIG.get("audio_auto_dl_favs", False)),
        "auto_dl_playlists": ",".join(APP_CONFIG.get("audio_auto_dl_playlists", [])),
        "hide_undownloaded_offline": str(APP_CONFIG.get("hide_undownloaded_offline", False))
    }

    config_path = PathsManager.get_config_file()
    with open(config_path, "w") as f:
        cfg.write(f)

THEME = {}
load_config()

def get_app_style():
    arrow_normal = get_combo_arrow_path(False)
    arrow_hover = get_combo_arrow_path(True)

    return f"""
    QMainWindow, QWidget {{
        background-color: {THEME.get('bg_main', '#050505')};
        color: {THEME.get('text_main', '#ffffff')};
        font-family: "Noto Sans", sans-serif;
    }}
    QScrollArea {{ border: none; background-color: transparent; }}
    QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0px; }}
    QScrollBar::handle:vertical {{ background: {THEME.get('nav_bg', '#222222')}; min-height: 30px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: {THEME.get('nav_hover', '#333333')}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    #Sidebar {{ background-color: {THEME.get('bg_sidebar', '#000000')}; border-right: 1px solid {THEME.get('border', '#121212')}; }}
    #Sidebar QPushButton[isMenu="true"] {{
        background-color: transparent; border: none; text-align: left;
        padding: 12px 15px; font-size: 13px; border-radius: 6px;
        color: {THEME.get('text_muted', '#888888')}; margin: 2px 10px;
    }}
    #Sidebar QPushButton[isMenu="true"]:hover {{ color: {THEME.get('text_main', '#ffffff')}; background-color: {THEME.get('bg_card', '#111111')}; }}
    #Sidebar QPushButton[active="true"] {{ background-color: {THEME.get('nav_bg', '#222222')}; color: {THEME.get('text_main', '#ffffff')}; font-weight: bold; }}

    #NavBtn {{ background-color: {THEME.get('nav_bg', '#222222')}; border-radius: 18px; border: none; padding: 0px !important; margin: 0px; }}
    #NavBtn:hover {{ background-color: {THEME.get('nav_hover', '#333333')}; }}

    #PlayerBar {{ background-color: {THEME.get('bg_sidebar', '#000000')}; border-top: 1px solid {THEME.get('border', '#121212')}; padding: 5px; }}

    #PlayPauseBtn {{
        background-color: {THEME.get('play_bg', 'white')};
        border-radius: 23px;
        border: none;
    }}
    #PlayPauseBtn:hover {{
        background-color: {THEME.get('accent', '#1db954')};
    }}

    #ControlBtn {{ background: transparent; border: none; border-radius: 18px; }}
    #ControlBtn:hover {{ background: {THEME.get('btn_hover_bg', 'rgba(255,255,255,0.1)')}; }}

    #HeroSection {{ margin-bottom: 25px; border-radius: 0px; }}
    #QueueHeader {{ border-radius: 15px; margin-bottom: 25px; }}
    #HeroTitle {{ font-size: 42px; font-weight: bold; background: transparent; border: none; }}
    #HeroSubtitle {{ font-size: 12px; color: {THEME.get('accent', '#1db954')}; font-weight: bold; letter-spacing: 2px; background: transparent; }}

    #Card {{ background-color: {THEME.get('bg_card', '#111111')}; border-radius: 12px; border: none; }}
    #Card:hover {{ background-color: {THEME.get('hover_card', '#181818')}; }}

    #ArtistCard {{ background-color: transparent; border: none; }}
    #ArtistCard:hover {{ background-color: transparent; border: none; }}

    #CardTitle {{ font-weight: bold; font-size: 15px; margin-top: 8px; background: transparent; color: {THEME.get('text_main', '#ffffff')}; }}
    #ArtistCard #CardTitle {{ text-align: center; }}
    #CardArtist {{ font-size: 13px; color: {THEME.get('text_muted', '#888888')}; background: transparent; }}

    #CardOverlay {{ background-color: rgba(0,0,0,0.55); border: none; border-radius: 12px; }}
    #CardOverlayArtist {{ background-color: rgba(0,0,0,0.55); border: none; border-radius: 500px; }}

    #CardImgContainer, #SongImgContainer, #LibraryContentWidget, #DetailsContentWidget {{ background: transparent; border: none; }}

    #NowPlayingQueueFrame {{
        background-color: rgba({THEME.get('bg_main_rgb', '5,5,5')}, 100);
        border-radius: 12px;
        border: 1px solid {THEME.get('border', '#121212')};
    }}
    #NowPlayingUiContainer, #NowPlayingMediaContainer, #NowPlayingArtWrapper, #NowPlayingQueueContent, #NowPlayingRightSpacer {{
        background: transparent;
        border: none;
    }}

    #CardPlayBtn, QPushButton#CardPlayBtn, #Card QPushButton#CardPlayBtn, #ArtistCard QPushButton#CardPlayBtn {{
        background-color: {THEME.get('play_bg', 'white')};
        border-radius: 23px;
        border: none;
        padding: 0px;
        margin: 0px;
    }}
    #CardPlayBtn:hover, QPushButton#CardPlayBtn:hover, #Card QPushButton#CardPlayBtn:hover, #ArtistCard QPushButton#CardPlayBtn:hover {{
        background-color: {THEME.get('accent', '#1db954')};
    }}

    #SongItem {{ background-color: transparent; border-radius: 8px; padding: 0px 8px; }}
    #SongItem:hover {{ background-color: {THEME.get('bg_card', '#111111')}; }}
    #SongItem QLabel {{ background: transparent; border: none; }}
    #SongItem[active="true"] {{ background-color: {THEME.get('accent_rgba', 'rgba(29, 185, 84, 0.1)')}; }}
    #SongTitle {{ font-weight: 600; font-size: 14px; color: {THEME.get('text_main', '#ffffff')}; background: transparent; margin: 0px; padding: 0px; }}
    #SongArtist, #SongAlbum {{ font-size: 12px; color: {THEME.get('text_muted', '#888888')}; background: transparent; }}
    #SongArtist:hover, #SongAlbum:hover {{ color: {THEME.get('text_main', '#ffffff')}; text-decoration: underline; }}
    #SongDot {{ color: {THEME.get('text_muted', '#888888')}; font-size: 12px; background: transparent; }}
    #SongDuration {{ color: {THEME.get('text_muted', '#888888')}; font-size: 13px; background: transparent; margin-right: 15px; }}
    #SongTrackNum {{ color: {THEME.get('text_muted', '#888888')}; font-size: 13px; font-weight: bold; background: transparent; }}
    #SongCoverOverlay {{ border-radius: 6px; background-color: rgba(0,0,0,0.55); border: none; }}

    #SongItem QPushButton {{ background: transparent; border: none; border-radius: 16px; }}
    #SongItem QPushButton:hover {{ background: {THEME.get('btn_hover_bg', 'rgba(255,255,255,0.1)')}; }}

    #SongPlayBtn,
    QPushButton#SongPlayBtn,
    #SongItem #SongPlayBtn,
    #SongItem QPushButton#SongPlayBtn,
    #SongImgContainer #SongPlayBtn,
    #SongImgContainer QPushButton#SongPlayBtn,
    #NowPlayingQueueFrame #SongPlayBtn,
    #NowPlayingQueueFrame QPushButton#SongPlayBtn {{
        background-color: {THEME.get('play_bg', 'white')};
        border-radius: 14px;
        border: none;
        padding: 0px;
        margin: 0px;
    }}
    #SongPlayBtn:hover,
    QPushButton#SongPlayBtn:hover,
    #SongItem #SongPlayBtn:hover,
    #SongItem QPushButton#SongPlayBtn:hover,
    #SongImgContainer #SongPlayBtn:hover,
    #SongImgContainer QPushButton#SongPlayBtn:hover,
    #NowPlayingQueueFrame #SongPlayBtn:hover,
    #NowPlayingQueueFrame QPushButton#SongPlayBtn:hover {{
        background-color: {THEME.get('accent', '#1db954')};
    }}

    #SongPlayNextBtn:hover {{ background: {THEME.get('btn_play_next_hover', 'rgba(52,152,219,0.2)')}; }}
    #SongAddPlBtn:hover {{ background: {THEME.get('btn_add_pl_hover', 'rgba(46,204,113,0.2)')}; }}
    #SongAddBtn:hover {{ background: {THEME.get('btn_add_hover', 'rgba(230,126,34,0.2)')}; }}
    #SongRemoveBtn:hover {{ background: {THEME.get('btn_remove_hover', 'rgba(231,76,60,0.2)')}; }}

    #StorageCard {{
        background-color: {THEME.get('bg_card', '#111111')};
        border-radius: 12px;
        border: 1px solid {THEME.get('border', '#121212')};
    }}
    QProgressBar#StorageBar {{
        background-color: {THEME.get('nav_bg', '#222222')};
        border-radius: 4px;
        border: none;
        height: 6px;
    }}
    QProgressBar#StorageBar::chunk {{
        background-color: {THEME.get('accent', '#1db954')};
        border-radius: 4px;
    }}

    QPushButton#FilterPill {{
        background-color: {THEME.get('bg_card', '#111111')};
        color: {THEME.get('text_muted', '#888888')};
        border: 1px solid {THEME.get('border', '#121212')};
        border-radius: 16px;
        padding: 6px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#FilterPill:hover {{
        background-color: {THEME.get('nav_bg', '#222222')};
        color: {THEME.get('text_main', '#ffffff')};
    }}
    QPushButton#FilterPill[active="true"] {{
        background-color: {THEME.get('accent', '#1db954')};
        color: white;
        border-color: {THEME.get('accent', '#1db954')};
    }}
    QPushButton#FilterPill[has_error="true"] {{
        color: #e74c3c;
        border-color: #e74c3c;
    }}
    QPushButton#FilterPill[has_error="true"][active="true"] {{
        background-color: #e74c3c;
        color: white;
    }}

    QPushButton#LoadMoreBtn {{
        background-color: {THEME.get('bg_card', '#111111')};
        color: {THEME.get('text_muted', '#888888')};
        border: 1px dashed {THEME.get('border', '#121212')};
        border-radius: 8px;
        padding: 12px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton#LoadMoreBtn:hover {{
        background-color: {THEME.get('nav_bg', '#222222')};
        color: {THEME.get('text_main', '#ffffff')};
        border-style: solid;
    }}

    ClickableLabel, ClickableElidedLabel {{
        color: {THEME.get('text_muted', '#888888')};
        background: transparent;
        border: none;
    }}
    ClickableLabel:hover, ClickableElidedLabel:hover {{
        color: {THEME.get('text_main', '#ffffff')};
        text-decoration: underline;
    }}

    QSlider::groove:horizontal {{ height: 4px; background: {THEME.get('nav_bg', '#222222')}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {THEME.get('accent', '#1db954')}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {THEME.get('text_main', '#ffffff')}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}

    QComboBox {{
        background-color: {THEME.get('bg_main', '#050505')};
        color: {THEME.get('text_main', '#ffffff')};
        border: 1px solid {THEME.get('border', '#121212')};
        border-radius: 6px;
        padding: 6px 36px 6px 12px;
        font-size: 13px;
    }}
    QComboBox:hover {{
        border-color: {THEME.get('nav_hover', '#333333')};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border: none;
        margin-right: 12px;
    }}
    QComboBox::down-arrow {{
        image: url("{arrow_normal}");
        width: 12px;
        height: 8px;
    }}
    QComboBox::down-arrow:hover {{
        image: url("{arrow_hover}");
    }}
    QComboBox QAbstractItemView {{
        background-color: {THEME.get('bg_card', '#111111')};
        color: {THEME.get('text_main', '#ffffff')};
        border: 1px solid {THEME.get('border', '#121212')};
        selection-background-color: {THEME.get('nav_bg', '#222222')};
        selection-color: {THEME.get('text_main', '#ffffff')};
        border-radius: 6px;
        padding: 4px;
        outline: none;
    }}
    """