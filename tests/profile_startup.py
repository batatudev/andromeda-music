import os
os.environ["QT_API"] = "pyside6"

import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

t_prev = time.perf_counter()


def log_step(step_name):
    global t_prev
    now = time.perf_counter()
    elapsed = (now - t_prev) * 1000.0
    print(f"  [STARTUP STEP] {step_name:<45} : {elapsed:8.2f} ms")
    t_prev = now


print("================================================================")
print("     ANDROMEDA MUSIC — PROFILOWANIE STARTU APLIKACJI            ")
print("================================================================")

log_step("Start skryptu")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
log_step("Import modułów PySide6 (QtGui, QtWidgets)")

from config import APP_CONFIG, APP_NAME, APP_ICON_PATH
log_step("Import config (wczytanie config.ini)")

from ui.theme_manager import theme_manager
log_step("Import theme_manager")

t_start_theme = time.perf_counter()
theme_manager.reload_theme()
t_theme_elapsed = (time.perf_counter() - t_start_theme) * 1000.0
log_step(f"Wywołanie theme_manager.reload_theme() (darkdetect)")

import qtawesome as qta
log_step("Import qtawesome")

from api_client import NavidromeClient
log_step("Import api_client")

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)
log_step("Utworzenie instancji QApplication")

c = NavidromeClient(APP_CONFIG.get("url", "http://localhost"), "", "")
log_step("Inicjalizacja NavidromeClient")

t_import_win = time.perf_counter()
from ui.main_window import MainWindow
log_step("Import ui.main_window.MainWindow (wraz z silnikiem)")

t_init_win = time.perf_counter()
w = MainWindow(c)
log_step("Inicjalizacja MainWindow.__init__() (UI + Engine + MPRIS)")

t_show = time.perf_counter()
w.show()
log_step("Wywołanie w.show() (POKAZANIE OKNA NA EKRANIE)")

print("================================================================")
print(f" CAŁKOWITY CZAS DO POKAZANIA OKNA: {(time.perf_counter() - t_start_theme + t_theme_elapsed):.2f} ms")
print("================================================================")

QApplication.processEvents()
w.close()