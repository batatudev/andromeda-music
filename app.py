import os
os.environ["QT_API"] = "pyside6"

from config import APP_NAME

os.environ["PULSE_PROP_application.name"] = APP_NAME
os.environ["PULSE_PROP_application.icon_name"] = "multimedia-audio-player"
os.environ["PULSE_PROP_media.role"] = "music"

import sys
from PySide6.QtGui import QIcon, QSurfaceFormat
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import qtawesome as qta

from api_client import NavidromeClient
from config import APP_CONFIG, APP_NAME, APP_ICON_PATH
from ui.theme_manager import theme_manager
from ui.main_window import MainWindow
from core.models import MediaItem
from utils import logger

def _auto_play_playlist(main_window, pl_name: str):
    """
    Automatycznie odnajduje playlistę o zadanej nazwie i rozpoczyna odtwarzanie.
    """
    def fetch():
        try:
            params = main_window.client._get_auth_params()
            res = main_window.client._make_request("getPlaylists", params)
            playlists = res.get('playlists', {}).get('playlist', [])
            target_id = None
            for pl in playlists:
                if pl.get('name', '').lower() == pl_name.lower():
                    target_id = pl.get('id')
                    break
            if target_id:
                p_params = main_window.client._get_auth_params()
                p_params['id'] = target_id
                p_res = main_window.client._make_request("getPlaylist", p_params)
                pl_data = p_res.get('playlist', {})
                songs = pl_data.get('entry', []) or pl_data.get('song', [])
                return [MediaItem(s) for s in songs]
        except Exception as e:
            logger.log(f"Błąd auto-play playlisty {pl_name}: {e}")
        return []

    def on_ready(songs):
        if songs:
            main_window.engine.play_list(songs, 0)

    main_window.run_async(fetch, on_ready, page_bound=False)

def _force_video_mode(main_window):
    if not main_window.player_bar.btn_video_toggle.isChecked():
        main_window.player_bar.btn_video_toggle.setChecked(True)
        main_window._toggle_video_mode()

def run():
    surface_format = QSurfaceFormat()
    surface_format.setAlphaBufferSize(8)
    surface_format.setDepthBufferSize(24)
    surface_format.setRenderableType(QSurfaceFormat.OpenGL)
    QSurfaceFormat.setDefaultFormat(surface_format)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    theme_manager.reload_theme()

    _ = qta.icon("fa5s.music")

    ignore_ssl = APP_CONFIG.get("ignore_ssl", False)

    if APP_CONFIG["url"]:
        c = NavidromeClient(
            APP_CONFIG["url"],
            APP_CONFIG["username"],
            APP_CONFIG["password"],
            ignore_ssl=ignore_ssl
        )
    else:
        c = NavidromeClient("http://localhost", "", "", ignore_ssl=False)

    w = MainWindow(c)
    w.showMaximized()

    if "--play-playlist" in sys.argv:
        try:
            idx = sys.argv.index("--play-playlist")
            if idx + 1 < len(sys.argv):
                playlist_name = sys.argv[idx + 1]
                QTimer.singleShot(600, lambda: _auto_play_playlist(w, playlist_name))
        except Exception as e:
            logger.log(f"Błąd parsowania argumentu --play-playlist: {e}")

    if "--video" in sys.argv:
        QTimer.singleShot(1500, lambda: _force_video_mode(w))

    sys.exit(app.exec())

if __name__ == "__main__":
    run()