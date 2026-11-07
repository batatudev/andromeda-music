import os
os.environ["QT_API"] = "pyside6"

import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication
from api_client import NavidromeClient
from config import APP_CONFIG
from ui.theme_manager import theme_manager

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)
theme_manager.reload_theme()

c = NavidromeClient(APP_CONFIG.get("url", "http://localhost"), "", "")

print("\n================================================================")
print("     ROZBICIE CZASU WNĘTRZA MainWindow.__init__()               ")
print("================================================================")

t_mark = time.perf_counter()


def mark(step_name):
    global t_mark
    now = time.perf_counter()
    elapsed = (now - t_mark) * 1000.0
    print(f"  --> {step_name:<50} : {elapsed:8.2f} ms")
    t_mark = now


mark("Start testu")

from core.data_repository import DataRepository
from utils import AsyncImageLoader
repo = DataRepository(c)
loader = AsyncImageLoader()
mark("1. Inicjalizacja DataRepository + AsyncImageLoader")

from engine.player_engine import PlayerEngine
engine = PlayerEngine(c)
mark("2. Inicjalizacja PlayerEngine (Audio + Wideo + SQLite)")

try:
    from mpris_adapter import MprisService
    mpris = MprisService(engine)
    mark("3. Inicjalizacja MPRIS (D-Bus SessionBus)")
except Exception as e:
    mark(f"3. Błąd MPRIS: {e}")

from views.view_sidebar import SidebarWidget
from views.view_player_bar import PlayerBarWidget
sidebar = SidebarWidget()
player_bar = PlayerBarWidget()
mark("4. Inicjalizacja pasków bazowych (Sidebar + PlayerBar)")

from views.view_home import HomeView
home = HomeView(None)
mark("5. Inicjalizacja HomeView")

from views.view_now_playing import NowPlayingWidget
now_playing = NowPlayingWidget()
mark("6. Inicjalizacja NowPlayingWidget (Wideo widget + FFmpeg)")

from views.view_downloads import DownloadsView
from views.view_settings import SettingsView
from views.view_dev import DevModeView

try:
    class DummyWin:
        def __init__(self, eng, rep, ldr, cli):
            self.engine = eng
            self.repo = rep
            self.loader = ldr
            self.client = cli
            self.router = None
            self.sidebar_ctrl = None
            self.now_playing_view = now_playing
    d_win = DummyWin(engine, repo, loader, c)

    dl_view = DownloadsView(d_win)
    mark("7. Inicjalizacja DownloadsView (odczyt SQLite pobrań)")

    st_view = SettingsView(d_win)
    mark("8. Inicjalizacja SettingsView (5 zakładek)")

    dev_view = DevModeView(d_win)
    mark("9. Inicjalizacja DevModeView (logi + telemetria)")
except Exception as e:
    mark(f"Błąd tworzenia widoków: {e}")

print("================================================================\n")