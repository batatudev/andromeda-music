import os
os.environ["QT_API"] = "pyside6"

from config import APP_NAME

os.environ["PULSE_PROP_application.name"] = APP_NAME
os.environ["PULSE_PROP_application.icon_name"] = "multimedia-audio-player"
os.environ["PULSE_PROP_media.role"] = "music"

import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
import qtawesome as qta

from api_client import NavidromeClient
from config import APP_CONFIG, APP_NAME, APP_ICON_PATH
from ui.theme_manager import theme_manager
from ui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    theme_manager.reload_theme()

    _ = qta.icon("fa5s.music")

    if APP_CONFIG["url"]:
        c = NavidromeClient(APP_CONFIG["url"], APP_CONFIG["username"], APP_CONFIG["password"])
    else:
        c = NavidromeClient("http://localhost", "", "")
    w = MainWindow(c)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()