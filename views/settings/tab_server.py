import os
os.environ["QT_API"] = "pyside6"

import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QCoreApplication

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
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 12px; padding: 24px; border: 1px solid {THEME['border']}; }}"
        )
        server_layout = QVBoxLayout(server_group)
        server_layout.setSpacing(14)

        lbl_s_title = QLabel(tr("settings.server.header", "Serwer Navidrome"))
        lbl_s_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;"
        )
        server_layout.addWidget(lbl_s_title)

        input_style = (
            f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 6px; padding: 8px 12px; height: 22px; font-size: 13px;"
        )

        self.inp_url = QLineEdit(APP_CONFIG["url"])
        self.inp_url.setStyleSheet(input_style)
        self.inp_user = QLineEdit(APP_CONFIG["username"])
        self.inp_user.setStyleSheet(input_style)
        self.inp_pwd = QLineEdit(APP_CONFIG["password"])
        self.inp_pwd.setEchoMode(QLineEdit.Password)
        self.inp_pwd.setStyleSheet(input_style)

        def add_row(parent_layout, text, widget):
            r = QHBoxLayout()
            r.setSpacing(15)
            lbl = QLabel(text)
            lbl.setFixedWidth(160)
            lbl.setFixedHeight(36)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; background: transparent;")
            widget.setMinimumWidth(260)
            widget.setMaximumWidth(520)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            r.addWidget(lbl)
            r.addWidget(widget)
            r.addStretch()
            parent_layout.addLayout(r)

        add_row(server_layout, tr("settings.server.url", "Adres URL:"), self.inp_url)
        add_row(server_layout, tr("settings.server.user", "Użytkownik:"), self.inp_user)
        add_row(server_layout, tr("settings.server.pass", "Hasło:"), self.inp_pwd)

        btn_test = QPushButton(tr("settings.server.test", "Testuj połączenie"))
        btn_test.setStyleSheet(
            f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px 18px; border-radius: 6px; font-weight: bold; border: none;"
        )
        btn_test.setCursor(Qt.PointingHandCursor)
        btn_test.clicked.connect(self._test_connection)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent; font-weight: bold;")

        btn_save_server = QPushButton(tr("settings.save_restart", "Zapisz i restartuj"))
        btn_save_server.setStyleSheet(
            f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 20px; border-radius: 6px; border: none;"
        )
        btn_save_server.setCursor(Qt.PointingHandCursor)
        btn_save_server.clicked.connect(self._save_and_restart)

        status_lay = QHBoxLayout()
        status_lay.setContentsMargins(0, 10, 0, 0)
        status_lay.setSpacing(15)
        status_lay.addSpacing(175)
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
            self.lbl_status.setStyleSheet("color: #1db954; background: transparent; font-weight: bold;")
        else:
            self.lbl_status.setText(tr("settings.server.error", "Błąd połączenia."))
            self.lbl_status.setStyleSheet("color: #e74c3c; background: transparent; font-weight: bold;")

    def _save_and_restart(self):
        APP_CONFIG["url"] = self.inp_url.text()
        APP_CONFIG["username"] = self.inp_user.text()
        APP_CONFIG["password"] = self.inp_pwd.text()

        self.settings_view._initial_settings["url"] = APP_CONFIG["url"]
        self.settings_view._initial_settings["username"] = APP_CONFIG["username"]
        self.settings_view._initial_settings["password"] = APP_CONFIG["password"]

        save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)