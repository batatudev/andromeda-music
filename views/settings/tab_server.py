import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: views/settings/tab_server.py
# OPIS ZMIAN: Oczyszczenie etykiet i pełne wdrożenie i18n przez tr()

import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton
)
from PySide6.QtCore import Qt, QCoreApplication, QTimer

from config import APP_CONFIG, save_config, THEME
from api_client import NavidromeClient
from core.i18n import tr

class TabServer(QWidget):
    def __init__(self, settings_view):
        super().__init__()
        self.settings_view = settings_view
        self.main_window = settings_view.main_window

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        server_group = QFrame()
        server_group.setObjectName("SettingsCard")
        server_group.setStyleSheet(
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}"
        )
        server_layout = QVBoxLayout(server_group)

        lbl_s_title = QLabel(tr("settings.server.header", "Serwer Navidrome"))
        lbl_s_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;"
        )
        server_layout.addWidget(lbl_s_title)

        input_style = (
            f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 5px; padding: 8px; height: 18px;"
        )

        self.inp_url = QLineEdit(APP_CONFIG["url"])
        self.inp_url.setStyleSheet(input_style)
        self.inp_url.setFixedWidth(350)
        self.inp_user = QLineEdit(APP_CONFIG["username"])
        self.inp_user.setStyleSheet(input_style)
        self.inp_user.setFixedWidth(350)
        self.inp_pwd = QLineEdit(APP_CONFIG["password"])
        self.inp_pwd.setEchoMode(QLineEdit.Password)
        self.inp_pwd.setStyleSheet(input_style)
        self.inp_pwd.setFixedWidth(350)

        def add_row(parent_layout, text, widget):
            r = QHBoxLayout()
            lbl = QLabel(text)
            lbl.setFixedWidth(190)
            lbl.setFixedHeight(34)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; margin-right: 10px; background: transparent;")
            r.addWidget(lbl)
            r.addWidget(widget)
            r.addStretch()
            parent_layout.addLayout(r)

        add_row(server_layout, tr("settings.server.url", "Adres URL:"), self.inp_url)
        add_row(server_layout, tr("settings.server.user", "Użytkownik:"), self.inp_user)
        add_row(server_layout, tr("settings.server.pass", "Hasło:"), self.inp_pwd)

        btn_test = QPushButton(tr("settings.server.test", "Testuj połączenie"))
        btn_test.setStyleSheet(
            f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px; border-radius: 5px;"
        )
        btn_test.setCursor(Qt.PointingHandCursor)
        btn_test.setFixedWidth(150)
        btn_test.clicked.connect(self._test_connection)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")

        btn_save_server = QPushButton(tr("settings.save_restart", "Zapisz i restartuj"))
        btn_save_server.setStyleSheet(
            f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;"
        )
        btn_save_server.setCursor(Qt.PointingHandCursor)
        btn_save_server.clicked.connect(self._save_and_restart)

        status_lay = QHBoxLayout()
        status_lay.addSpacing(200)
        status_lay.addWidget(btn_test)
        status_lay.addWidget(self.lbl_status)
        status_lay.addStretch()
        status_lay.addWidget(btn_save_server)
        server_layout.addLayout(status_lay)

        self.layout.addWidget(server_group)
        self.layout.addStretch()

    def _test_connection(self):
        self.lbl_status.setText(tr("settings.server.testing", "Łączenie..."))
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        QCoreApplication.processEvents()

        temp_client = NavidromeClient(self.inp_url.text(), self.inp_user.text(), self.inp_pwd.text())
        ok = temp_client.ping()

        if ok:
            self.lbl_status.setText(tr("settings.server.success", "Połączono pomyślnie!"))
            self.lbl_status.setStyleSheet("color: #1db954; background: transparent;")
        else:
            self.lbl_status.setText(tr("settings.server.error", "Błąd połączenia."))
            self.lbl_status.setStyleSheet("color: #e74c3c; background: transparent;")

    def _save_and_restart(self):
        APP_CONFIG["url"] = self.inp_url.text()
        APP_CONFIG["username"] = self.inp_user.text()
        APP_CONFIG["password"] = self.inp_pwd.text()

        self.settings_view._initial_settings["url"] = APP_CONFIG["url"]
        self.settings_view._initial_settings["username"] = APP_CONFIG["username"]
        self.settings_view._initial_settings["password"] = APP_CONFIG["password"]

        save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)