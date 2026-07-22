# WERSJA PROJEKTU: 14.22
# MODYFIKOWANY PLIK: app.py
# OPIS ZMIAN: Inicjalizacja opóźnionego mechanizmu motywu systemowego (init_theme) tuż po utworzeniu instancji QApplication.

import os
os.environ["QT_API"] = "pyside6"

from config import APP_NAME

os.environ["PULSE_PROP_application.name"] = APP_NAME
os.environ["PULSE_PROP_application.icon_name"] = "multimedia-audio-player"
os.environ["PULSE_PROP_media.role"] = "music"

import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from api_client import NavidromeClient
from config import APP_CONFIG, APP_NAME, APP_ICON_PATH, init_theme
from ui.main_window import MainWindow

def run():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    init_theme()
    if APP_CONFIG["url"]:
        c = NavidromeClient(APP_CONFIG["url"], APP_CONFIG["username"], APP_CONFIG["password"])
    else:
        c = NavidromeClient("http://localhost", "", "")
    w = MainWindow(c)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run()