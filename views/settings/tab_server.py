import os
os.environ["QT_API"] = "pyside6"

import sys
import uuid
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QSizePolicy, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, QCoreApplication

from config import (
    APP_CONFIG, save_config, THEME, DEFAULT_DEMO_SERVER,
    get_combo_arrow_path, get_server_by_id, add_or_update_server,
    remove_server, set_active_server
)
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
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 12px; padding: 26px 85px; border: 1px solid {THEME['border']}; }}"
        )
        self.server_layout = QVBoxLayout(server_group)
        self.server_layout.setSpacing(16)

        lbl_s_title = QLabel(tr("settings.server.header", "Serwer Navidrome"))
        lbl_s_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        self.server_layout.addWidget(lbl_s_title)

        arrow_normal = get_combo_arrow_path(False)
        arrow_hover = get_combo_arrow_path(True)

        input_style = f"""
            QLineEdit {{
                background-color: {THEME['bg_main']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 8px 12px;
                height: 22px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {THEME['accent']};
            }}
            QComboBox {{
                background-color: {THEME['bg_main']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 6px 36px 6px 12px;
                height: 22px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {THEME['nav_hover']};
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
                background-color: {THEME['bg_card']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                selection-background-color: {THEME['nav_bg']};
                selection-color: {THEME['text_main']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
        """

        btn_action_style = f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                padding: 7px 14px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """

        btn_del_style = f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: #e74c3c;
                padding: 7px 14px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: rgba(231, 76, 60, 0.25);
            }}
        """

        # Dwukolumnowa siatka formularza gwarantująca identyczny punkt startu X
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(20)
        form_grid.setVerticalSpacing(12)
        form_grid.setContentsMargins(0, 0, 0, 0)
        form_grid.setColumnMinimumWidth(0, 200)
        form_grid.setColumnStretch(0, 0)
        form_grid.setColumnStretch(1, 1)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setFixedWidth(200)
            lbl.setFixedHeight(36)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; background: transparent;")
            return lbl

        # Rząd 0: Aktywny profil
        lbl_profile = make_label(tr("settings.server.active_profile", "Aktywny profil:"))
        self.combo_servers = QComboBox()
        self.combo_servers.setStyleSheet(input_style)
        self.combo_servers.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_servers.currentIndexChanged.connect(self._on_server_selected)
        form_grid.addWidget(lbl_profile, 0, 0)
        form_grid.addWidget(self.combo_servers, 0, 1)

        # Rząd 1: Przyciski akcji profilu (idealnie wewnątrz Kolumny 1)
        actions_widget = QWidget()
        actions_widget.setStyleSheet("background: transparent;")
        actions_lay = QHBoxLayout(actions_widget)
        actions_lay.setContentsMargins(0, 0, 0, 0)
        actions_lay.setSpacing(10)

        self.btn_new_server = QPushButton(tr("settings.server.new_profile", "+ Nowy profil"))
        self.btn_new_server.setStyleSheet(btn_action_style)
        self.btn_new_server.setCursor(Qt.PointingHandCursor)
        self.btn_new_server.clicked.connect(self._create_new_server)
        actions_lay.addWidget(self.btn_new_server)

        self.btn_load_demo = QPushButton(tr("settings.server.load_demo", "Wstaw publiczne Demo"))
        self.btn_load_demo.setStyleSheet(btn_action_style)
        self.btn_load_demo.setCursor(Qt.PointingHandCursor)
        self.btn_load_demo.setToolTip("Wstawia publiczny serwer testowy demo.navidrome.org")
        self.btn_load_demo.clicked.connect(self._load_public_demo)
        actions_lay.addWidget(self.btn_load_demo)

        self.btn_del_server = QPushButton(tr("settings.server.delete_profile", "Usuń profil"))
        self.btn_del_server.setStyleSheet(btn_del_style)
        self.btn_del_server.setCursor(Qt.PointingHandCursor)
        self.btn_del_server.clicked.connect(self._delete_current_server)
        actions_lay.addWidget(self.btn_del_server)

        actions_lay.addStretch()
        form_grid.addWidget(actions_widget, 1, 1)

        # Rząd 2: Subtelna linia podziału
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {THEME['border']}; max-height: 1px; margin: 6px 0px 8px 0px;")
        form_grid.addWidget(line, 2, 0, 1, 2)

        # Rząd 3: Nazwa profilu
        lbl_name = make_label(tr("settings.server.profile_name", "Nazwa profilu:"))
        self.inp_name = QLineEdit()
        self.inp_name.setStyleSheet(input_style)
        self.inp_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_grid.addWidget(lbl_name, 3, 0)
        form_grid.addWidget(self.inp_name, 3, 1)

        # Rząd 4: Adres URL
        lbl_url = make_label(tr("settings.server.url", "Adres URL:"))
        self.inp_url = QLineEdit()
        self.inp_url.setStyleSheet(input_style)
        self.inp_url.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_grid.addWidget(lbl_url, 4, 0)
        form_grid.addWidget(self.inp_url, 4, 1)

        # Rząd 5: Użytkownik
        lbl_user = make_label(tr("settings.server.user", "Użytkownik:"))
        self.inp_user = QLineEdit()
        self.inp_user.setStyleSheet(input_style)
        self.inp_user.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_grid.addWidget(lbl_user, 5, 0)
        form_grid.addWidget(self.inp_user, 5, 1)

        # Rząd 6: Hasło
        lbl_pwd = make_label(tr("settings.server.pass", "Hasło:"))
        self.inp_pwd = QLineEdit()
        self.inp_pwd.setEchoMode(QLineEdit.Password)
        self.inp_pwd.setStyleSheet(input_style)
        self.inp_pwd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_grid.addWidget(lbl_pwd, 6, 0)
        form_grid.addWidget(self.inp_pwd, 6, 1)

        self.server_layout.addLayout(form_grid)

        # Dolny pasek akcji (Testowanie i Zapis)
        btn_test = QPushButton(tr("settings.server.test", "Testuj połączenie"))
        btn_test.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                padding: 9px 18px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """)
        btn_test.setCursor(Qt.PointingHandCursor)
        btn_test.clicked.connect(self._test_connection)
        btn_test.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent; font-weight: bold;")
        self.lbl_status.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        btn_save_server = QPushButton(tr("settings.save_restart", "Zapisz i restartuj"))
        btn_save_server.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent']};
                color: white;
                font-weight: bold;
                padding: 9px 24px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_save_server.setCursor(Qt.PointingHandCursor)
        btn_save_server.clicked.connect(self._save_and_restart)
        btn_save_server.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        status_lay = QHBoxLayout()
        status_lay.setContentsMargins(0, 10, 0, 0)
        status_lay.setSpacing(15)
        status_lay.addWidget(self.lbl_status)
        status_lay.addStretch()
        status_lay.addWidget(btn_test)
        status_lay.addWidget(btn_save_server)
        self.server_layout.addLayout(status_lay)

        self.layout.addWidget(server_group)
        self.layout.addStretch()

        self._populate_server_profiles()

    def _populate_server_profiles(self):
        self.combo_servers.blockSignals(True)
        self.combo_servers.clear()

        servers = APP_CONFIG.get("servers", [])
        active_id = APP_CONFIG.get("active_server_id", "demo")

        selected_idx = 0
        for i, s in enumerate(servers):
            sid = s.get("id", f"srv_{i}")
            name = s.get("name", sid)
            self.combo_servers.addItem(name, sid)
            if sid == active_id:
                selected_idx = i

        self.combo_servers.setCurrentIndex(selected_idx)
        self.combo_servers.blockSignals(False)

        self._load_selected_server_to_inputs()
        self._update_delete_button_state()

    def _update_delete_button_state(self):
        can_delete = len(APP_CONFIG.get("servers", [])) > 1
        self.btn_del_server.setEnabled(can_delete)
        self.btn_del_server.setVisible(can_delete)

    def _on_server_selected(self, index):
        if index < 0:
            return
        self._load_selected_server_to_inputs()

    def _load_selected_server_to_inputs(self):
        sid = self.combo_servers.currentData()
        if not sid:
            return
        server = get_server_by_id(sid)
        if server:
            self.inp_name.setText(server.get("name", ""))
            self.inp_url.setText(server.get("url", ""))
            self.inp_user.setText(server.get("username", ""))
            self.inp_pwd.setText(server.get("password", ""))

    def _create_new_server(self):
        new_id = f"server_{str(uuid.uuid4())[:6]}"
        new_server = {
            "id": new_id,
            "name": f"Nowy Serwer ({self.combo_servers.count() + 1})",
            "url": "http://",
            "username": "",
            "password": ""
        }
        add_or_update_server(new_server)
        self._populate_server_profiles()
        idx = self.combo_servers.findData(new_id)
        if idx >= 0:
            self.combo_servers.setCurrentIndex(idx)
        self.inp_name.setFocus()
        self.lbl_status.setText(tr("settings.server.created", "Utworzono nowy profil serwera."))
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")

    def _load_public_demo(self):
        demo_id = "demo_public"
        existing = get_server_by_id(demo_id)
        if not existing:
            demo_server = DEFAULT_DEMO_SERVER.copy()
            demo_server["id"] = demo_id
            add_or_update_server(demo_server)
            self._populate_server_profiles()

        idx = self.combo_servers.findData(demo_id)
        if idx >= 0:
            self.combo_servers.setCurrentIndex(idx)
        else:
            self.inp_name.setText(DEFAULT_DEMO_SERVER["name"])
            self.inp_url.setText(DEFAULT_DEMO_SERVER["url"])
            self.inp_user.setText(DEFAULT_DEMO_SERVER["username"])
            self.inp_pwd.setText(DEFAULT_DEMO_SERVER["password"])

        self.lbl_status.setText(tr("settings.server.demo_loaded", "Załadowano dane serwera demonstracyjnego."))
        self.lbl_status.setStyleSheet(f"color: {THEME['accent']}; background: transparent; font-weight: bold;")

    def _delete_current_server(self):
        sid = self.combo_servers.currentData()
        if not sid:
            return
        server = get_server_by_id(sid)
        sname = server.get("name", sid) if server else sid

        prompt_txt = tr(
            "settings.server.delete_confirm",
            "Czy na pewno chcesz usunąć profil '{name}'?\n(Pobrane pliki tego serwera pozostaną na dysku)."
        ).replace("{name}", sname)

        ans = QMessageBox.question(
            self,
            tr("settings.server.delete_title", "Usuwanie profilu serwera"),
            prompt_txt,
            QMessageBox.Yes | QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            remove_server(sid)
            self._populate_server_profiles()

    def _test_connection(self):
        self.lbl_status.setText(tr("settings.server.testing", "Łączenie..."))
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        QCoreApplication.processEvents()

        test_url = self.inp_url.text().strip()
        test_user = self.inp_user.text().strip()
        test_pwd = self.inp_pwd.text()

        temp_client = NavidromeClient(test_url, test_user, test_pwd)
        ok = temp_client.ping()

        if ok:
            self.lbl_status.setText(tr("settings.server.success", "Połączono pomyślnie!"))
            self.lbl_status.setStyleSheet("color: #1db954; background: transparent; font-weight: bold;")
        else:
            self.lbl_status.setText(tr("settings.server.error", "Błąd połączenia."))
            self.lbl_status.setStyleSheet("color: #e74c3c; background: transparent; font-weight: bold;")

    def _save_and_restart(self):
        sid = self.combo_servers.currentData()
        if not sid:
            sid = "default"

        updated_server = {
            "id": sid,
            "name": self.inp_name.text().strip() or sid,
            "url": self.inp_url.text().strip(),
            "username": self.inp_user.text().strip(),
            "password": self.inp_pwd.text()
        }

        add_or_update_server(updated_server)
        set_active_server(sid)

        self.settings_view._initial_settings["url"] = updated_server["url"]
        self.settings_view._initial_settings["username"] = updated_server["username"]
        self.settings_view._initial_settings["password"] = updated_server["password"]

        save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)