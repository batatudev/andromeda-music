# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: app.py
# OPIS ZMIAN: Nowy korzeń uruchomieniowy aplikacji (zgodnie z Etapem 4 roadmapy).
# Izoluje inicjalizację QApplication, klienta API i głównego okna od logiki UI.

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
from config import APP_CONFIG, APP_NAME, APP_ICON_PATH
from ui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    if APP_CONFIG["url"]:
        c = NavidromeClient(APP_CONFIG["url"], APP_CONFIG["username"], APP_CONFIG["password"])
    else:
        c = NavidromeClient("http://localhost", "", "")
    w = MainWindow(c)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
