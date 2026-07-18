# WERSJA PROJEKTU: 14.13
# MODYFIKOWANY PLIK: view_settings.py
# OPIS ZMIAN: Dodano nową zakładkę w ustawieniach ("Ustawienia Pobrań Offline") obsługującą opcje video_smart_auto_play i video_offline_quality.

import os
import sys

os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QComboBox, QPushButton, QSlider, QColorDialog, QDialog, QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QCoreApplication
from PySide6.QtGui import QColor

from config import APP_CONFIG, save_config, THEME
from api_client import NavidromeClient


class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._initial_settings = {}
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(15)

    def _clear(self, lay):
        while lay.count():
            i = lay.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
            elif i.layout():
                self._clear(i.layout())

    def revert_changes(self):
        if self._initial_settings:
            for k, v in self._initial_settings.items():
                APP_CONFIG[k] = v
            self.main_window.now_playing_view.update_video_settings()

    def build_ui(self):
        self._initial_settings = {
            "url": APP_CONFIG["url"],
            "username": APP_CONFIG["username"],
            "password": APP_CONFIG["password"],
            "dark_mode": APP_CONFIG["dark_mode"],
            "accent": APP_CONFIG["accent"],
            "video_resolution": APP_CONFIG.get("video_resolution", "1080p"),
            "video_min_res": APP_CONFIG.get("video_min_res", "480p"),
            "video_auto_res": APP_CONFIG.get("video_auto_res", True),
            "video_dynamic_opacity": APP_CONFIG["video_dynamic_opacity"],
            "video_dynamic_blur": APP_CONFIG["video_dynamic_blur"],
            "video_static_opacity": APP_CONFIG["video_static_opacity"],
            "video_static_blur": APP_CONFIG["video_static_blur"],
            "dev_mode": APP_CONFIG.get("dev_mode", False),
            "video_offline_quality": APP_CONFIG.get("video_offline_quality", "1080p"),
            "video_smart_auto_play": APP_CONFIG.get("video_smart_auto_play", False),
            "video_auto_dl_favs": APP_CONFIG.get("video_auto_dl_favs", False),
            "video_auto_dl_playlists": APP_CONFIG.get("video_auto_dl_playlists", False)
        }

        self._clear(self.main_layout)

        center_widget = QWidget()
        center_widget.setMaximumWidth(800)
        center_widget.setMinimumWidth(600)
        center_lay = QVBoxLayout(center_widget)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(20)

        lbl_title = QLabel("Ustawienia")
        lbl_title.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {THEME['text_main']}; margin-bottom: 20px; background: transparent;")
        center_lay.addWidget(lbl_title)

        server_group = QFrame()
        server_group.setObjectName("SettingsCard")
        server_group.setStyleSheet(f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}")
        server_layout = QVBoxLayout(server_group)

        lbl_s_title = QLabel("Serwer Navidrome")
        lbl_s_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        server_layout.addWidget(lbl_s_title)

        input_style = f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 5px; padding: 8px; height: 18px;"

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

        add_row(server_layout, "Adres URL:", self.inp_url)
        add_row(server_layout, "Nazwa usera:", self.inp_user)
        add_row(server_layout, "Hasło:", self.inp_pwd)

        btn_test = QPushButton("Testuj połączenie")
        btn_test.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px; border-radius: 5px;")
        btn_test.setCursor(Qt.PointingHandCursor)
        btn_test.setFixedWidth(150)
        btn_test.clicked.connect(self._test_connection)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")

        btn_save_server = QPushButton("Zapisz i Restartuj")
        btn_save_server.setStyleSheet(f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_save_server.setCursor(Qt.PointingHandCursor)
        btn_save_server.clicked.connect(self._save_and_restart)

        status_lay = QHBoxLayout()
        status_lay.addSpacing(200)
        status_lay.addWidget(btn_test)
        status_lay.addWidget(self.lbl_status)
        status_lay.addStretch()
        status_lay.addWidget(btn_save_server)
        server_layout.addLayout(status_lay)

        center_lay.addWidget(server_group)

        theme_group = QFrame()
        theme_group.setObjectName("SettingsCard")
        theme_group.setStyleSheet(f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}")
        theme_layout = QVBoxLayout(theme_group)

        lbl_t_title = QLabel("Wygląd aplikacji")
        lbl_t_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        theme_layout.addWidget(lbl_t_title)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Ciemny", "Jasny"])
        self.combo_theme.setCurrentIndex(0 if APP_CONFIG["dark_mode"] else 1)
        self.combo_theme.setStyleSheet(input_style)
        self.combo_theme.setFixedWidth(350)

        self.current_accent = APP_CONFIG["accent"]
        self.btn_color = QPushButton("Wybierz kolor")
        self.btn_color.setStyleSheet(f"background-color: {self.current_accent}; color: white; padding: 8px; border-radius: 5px;")
        self.btn_color.setCursor(Qt.PointingHandCursor)
        self.btn_color.clicked.connect(self._pick_color)

        color_lay = QHBoxLayout()
        color_lay.setContentsMargins(0, 0, 0, 0)
        color_lay.addWidget(self.btn_color)
        color_lay.addStretch()
        color_widget = QWidget()
        color_widget.setFixedWidth(350)
        color_widget.setStyleSheet("background: transparent;")
        color_widget.setLayout(color_lay)

        add_row(theme_layout, "Motyw:", self.combo_theme)
        add_row(theme_layout, "Kolor akcentu:", color_widget)

        btn_save_theme = QPushButton("Zapisz i Restartuj")
        btn_save_theme.setStyleSheet(f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_save_theme.setCursor(Qt.PointingHandCursor)
        btn_save_theme.clicked.connect(self._save_and_restart)

        save_t_lay = QHBoxLayout()
        save_t_lay.addStretch()
        save_t_lay.addWidget(btn_save_theme)
        theme_layout.addLayout(save_t_lay)

        center_lay.addWidget(theme_group)

        video_group = QFrame()
        video_group.setObjectName("SettingsCard")
        video_group.setStyleSheet(f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}")
        video_layout = QVBoxLayout(video_group)

        lbl_v_title = QLabel("Ustawienia Wideo (Inteligentne Filtry)")
        lbl_v_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 5px; background: transparent;")
        video_layout.addWidget(lbl_v_title)

        lbl_v_hint = QLabel("Zapisz ustawienia, aby zastosować filtry wizualne natychmiast. Ustawienia rozdzielczości będą aktywne od następnego utworu.")
        lbl_v_hint.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; margin-bottom: 15px; background: transparent;")
        video_layout.addWidget(lbl_v_hint)

        self.combo_res = QComboBox()
        self.combo_res.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_res.setCurrentText(APP_CONFIG.get("video_resolution", "1080p"))
        self.combo_res.setStyleSheet(input_style)
        self.combo_res.setFixedWidth(350)
        add_row(video_layout, "Rozdzielczość bazy:", self.combo_res)

        self.combo_auto_res = QComboBox()
        self.combo_auto_res.addItems(["Wyłączona", "Włączona (Zalecane)"])
        self.combo_auto_res.setCurrentIndex(1 if APP_CONFIG.get("video_auto_res", True) else 0)
        self.combo_auto_res.setStyleSheet(input_style)
        self.combo_auto_res.setFixedWidth(350)
        add_row(video_layout, "Automatyczna (ARF):", self.combo_auto_res)

        self.combo_min_res = QComboBox()
        self.combo_min_res.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_min_res.setCurrentText(APP_CONFIG.get("video_min_res", "480p"))
        self.combo_min_res.setStyleSheet(input_style)
        self.combo_min_res.setFixedWidth(350)
        add_row(video_layout, "Minimalna jakość (ARF):", self.combo_min_res)

        slider_style = f"""
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{ height: 4px; background: {THEME['bg_main']}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {THEME['accent']}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {THEME['text_main']}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
        """

        self.video_sliders = {}

        def add_slider(parent_layout, label_text, config_key, is_percent=False):
            lay = QHBoxLayout()
            lay.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(label_text)
            lbl.setFixedWidth(190)
            lbl.setFixedHeight(34)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; margin-right: 10px; background: transparent;")

            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setFixedWidth(300)
            slider.setValue(APP_CONFIG.get(config_key, 0))
            slider.setStyleSheet(slider_style)

            val_lbl = QLabel(f"{slider.value()}%" if is_percent else f"{slider.value()}")
            val_lbl.setFixedWidth(50)
            val_lbl.setStyleSheet(f"color: {THEME['text_main']}; font-weight: bold; margin-left: 10px; background: transparent;")

            def on_change(v, l=val_lbl, k=config_key, perc=is_percent):
                l.setText(f"{v}%" if perc else f"{v}")
                APP_CONFIG[k] = v
                self.main_window.now_playing_view.update_video_settings()

            slider.valueChanged.connect(on_change)
            self.video_sliders[config_key] = slider

            lay.addWidget(lbl)
            lay.addWidget(slider)
            lay.addWidget(val_lbl)
            lay.addStretch()

            parent_layout.addLayout(lay)

        lbl_v_dyn = QLabel("Profil: Teledysk (wykryto ruch w kadrze)")
        lbl_v_dyn.setStyleSheet(f"font-weight: bold; color: {THEME['accent']}; margin-top: 10px; margin-bottom: 5px; background: transparent;")
        video_layout.addWidget(lbl_v_dyn)

        add_slider(video_layout, "Przyciemnienie:", "video_dynamic_opacity", True)
        add_slider(video_layout, "Rozmycie wideo:", "video_dynamic_blur", False)

        lbl_v_stat = QLabel("Profil: Statyczna Okładka (brak ruchu)")
        lbl_v_stat.setStyleSheet(f"font-weight: bold; color: {THEME['accent']}; margin-top: 15px; margin-bottom: 5px; background: transparent;")
        video_layout.addWidget(lbl_v_stat)

        add_slider(video_layout, "Przyciemnienie:", "video_static_opacity", True)
        add_slider(video_layout, "Rozmycie wideo:", "video_static_blur", False)

        self.lbl_v_status = QLabel("")
        self.lbl_v_status.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; background: transparent;")

        btn_save_video = QPushButton("Zapisz Ustawienia Wideo")
        btn_save_video.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_save_video.setCursor(Qt.PointingHandCursor)

        def _save_v_conf():
            APP_CONFIG["video_resolution"] = self.combo_res.currentText()
            APP_CONFIG["video_min_res"] = self.combo_min_res.currentText()
            APP_CONFIG["video_auto_res"] = (self.combo_auto_res.currentIndex() == 1)
            for k, s in self.video_sliders.items():
                APP_CONFIG[k] = s.value()
            
            save_config()
            self.main_window.now_playing_view.update_video_settings()
            
            self._initial_settings["video_resolution"] = APP_CONFIG["video_resolution"]
            self._initial_settings["video_min_res"] = APP_CONFIG["video_min_res"]
            self._initial_settings["video_auto_res"] = APP_CONFIG["video_auto_res"]
            self._initial_settings["video_dynamic_opacity"] = APP_CONFIG["video_dynamic_opacity"]
            self._initial_settings["video_dynamic_blur"] = APP_CONFIG["video_dynamic_blur"]
            self._initial_settings["video_static_opacity"] = APP_CONFIG["video_static_opacity"]
            self._initial_settings["video_static_blur"] = APP_CONFIG["video_static_blur"]

            self.lbl_v_status.setText("Zapisano pomyślnie")
            QTimer.singleShot(3000, lambda: self.lbl_v_status.setText(""))

        btn_save_video.clicked.connect(_save_v_conf)

        save_v_lay = QHBoxLayout()
        save_v_lay.addStretch()
        save_v_lay.addWidget(self.lbl_v_status)
        save_v_lay.addWidget(btn_save_video)
        video_layout.addLayout(save_v_lay)

        center_lay.addWidget(video_group)

        offline_group = QFrame()
        offline_group.setObjectName("SettingsCard")
        offline_group.setStyleSheet(f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}")
        offline_layout = QVBoxLayout(offline_group)

        lbl_o_title = QLabel("Ustawienia Pobrań Offline")
        lbl_o_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        offline_layout.addWidget(lbl_o_title)

        self.combo_smart_auto = QComboBox()
        self.combo_smart_auto.addItems(["Wyłączone (Wymaga kliknięcia teledysku)", "Włączone (Automatycznie załaduj offline)"])
        self.combo_smart_auto.setCurrentIndex(1 if APP_CONFIG.get("video_smart_auto_play", False) else 0)
        self.combo_smart_auto.setStyleSheet(input_style)
        self.combo_smart_auto.setFixedWidth(350)
        add_row(offline_layout, "Autoodtwarzanie:", self.combo_smart_auto)

        self.combo_off_quality = QComboBox()
        self.combo_off_quality.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_off_quality.setCurrentText(APP_CONFIG.get("video_offline_quality", "1080p"))
        self.combo_off_quality.setStyleSheet(input_style)
        self.combo_off_quality.setFixedWidth(350)
        add_row(offline_layout, "Jakość wideo (offline):", self.combo_off_quality)

        self.combo_auto_favs = QComboBox()
        self.combo_auto_favs.addItems(["Wyłączone", "Włączone (pobieraj przy polubieniu)"])
        self.combo_auto_favs.setCurrentIndex(1 if APP_CONFIG.get("video_auto_dl_favs", False) else 0)
        self.combo_auto_favs.setStyleSheet(input_style)
        self.combo_auto_favs.setFixedWidth(350)
        add_row(offline_layout, "Auto-pobieranie (Ulubione):", self.combo_auto_favs)

        self.btn_auto_pl = QPushButton("Wybierz playlisty...")
        self.btn_auto_pl.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px; border-radius: 5px;")
        self.btn_auto_pl.setCursor(Qt.PointingHandCursor)
        self.btn_auto_pl.setFixedWidth(350)
        self.btn_auto_pl.clicked.connect(self._show_playlists_sync_dialog)
        
        pl_cnt = len(APP_CONFIG.get("video_auto_dl_playlists", []))
        self.btn_auto_pl.setText(f"Wybierz playlisty... ({pl_cnt} wybrano)")
        add_row(offline_layout, "Auto-pobieranie (Playlisty):", self.btn_auto_pl)

        btn_save_offline = QPushButton("Zapisz Ustawienia Offline")
        btn_save_offline.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_save_offline.setCursor(Qt.PointingHandCursor)
        
        self.lbl_o_status = QLabel("")
        self.lbl_o_status.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; background: transparent;")

        def _save_o_conf():
            APP_CONFIG["video_offline_quality"] = self.combo_off_quality.currentText()
            APP_CONFIG["video_smart_auto_play"] = (self.combo_smart_auto.currentIndex() == 1)
            APP_CONFIG["video_auto_dl_favs"] = (self.combo_auto_favs.currentIndex() == 1)
            
            save_config()
            self._initial_settings["video_offline_quality"] = APP_CONFIG["video_offline_quality"]
            self._initial_settings["video_smart_auto_play"] = APP_CONFIG["video_smart_auto_play"]
            self._initial_settings["video_auto_dl_favs"] = APP_CONFIG["video_auto_dl_favs"]
            
            self.lbl_o_status.setText("Zapisano pomyślnie")
            QTimer.singleShot(3000, lambda: self.lbl_o_status.setText(""))

        btn_save_offline.clicked.connect(_save_o_conf)

        save_o_lay = QHBoxLayout()
        save_o_lay.addStretch()
        save_o_lay.addWidget(self.lbl_o_status)
        save_o_lay.addWidget(btn_save_offline)
        offline_layout.addLayout(save_o_lay)

        center_lay.addWidget(offline_group)

        dev_group = QFrame()
        dev_group.setObjectName("SettingsCard")
        dev_group.setStyleSheet(f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}")
        dev_layout = QVBoxLayout(dev_group)

        lbl_d_title = QLabel("Opcje dla programistów")
        lbl_d_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        dev_layout.addWidget(lbl_d_title)

        self.combo_dev = QComboBox()
        self.combo_dev.addItems(["Wyłączony", "Włączony"])
        self.combo_dev.setCurrentIndex(1 if APP_CONFIG.get("dev_mode", False) else 0)
        self.combo_dev.setStyleSheet(input_style)
        self.combo_dev.setFixedWidth(350)

        add_row(dev_layout, "Tryb dewelopera:", self.combo_dev)

        btn_save_dev = QPushButton("Zapisz i Restartuj")
        btn_save_dev.setStyleSheet(f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_save_dev.setCursor(Qt.PointingHandCursor)
        btn_save_dev.clicked.connect(self._save_and_restart)

        save_d_lay = QHBoxLayout()
        save_d_lay.addStretch()
        save_d_lay.addWidget(btn_save_dev)
        dev_layout.addLayout(save_d_lay)

        center_lay.addWidget(dev_group)

        lbl_version = QLabel("Wersja programu: 11.4 (Odroczona rozdzielczość ARF, poprawki UI)")
        lbl_version.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; margin-top: 20px; background: transparent;")
        lbl_version.setAlignment(Qt.AlignCenter)
        center_lay.addWidget(lbl_version)

        wrap_lay = QHBoxLayout()
        wrap_lay.addStretch()
        wrap_lay.addWidget(center_widget)
        wrap_lay.addStretch()

        self.main_layout.addLayout(wrap_lay)
        self.main_layout.addStretch()

    def _show_playlists_sync_dialog(self):
        def fetch():
            params = self.main_window.client._get_auth_params()
            res = self.main_window.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            dlg = QDialog(self)
            dlg.setWindowTitle("Wybierz playlisty do auto-pobierania")
            dlg.setFixedSize(400, 500)
            from config import get_app_style
            dlg.setStyleSheet(get_app_style())
            layout = QVBoxLayout(dlg)
            
            lbl = QLabel("Zaznacz playlisty, które mają być automatycznie synchronizowane:")
            lbl.setStyleSheet(f"color: {THEME['text_main']}; margin-bottom: 10px;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            content = QWidget()
            v = QVBoxLayout(content)
            v.setSpacing(5)
            
            checkboxes = {}
            current_selected = APP_CONFIG.get("video_auto_dl_playlists", [])
            
            for pl in playlists:
                pl_id = pl.get('id')
                cb = QCheckBox(pl.get('name', 'Nieznana'))
                cb.setStyleSheet(f"color: {THEME['text_main']}; spacing: 10px; font-size: 14px;")
                if pl_id in current_selected:
                    cb.setChecked(True)
                v.addWidget(cb)
                checkboxes[pl_id] = cb
                
            v.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll)
            
            btn_save = QPushButton("Zapisz wybór")
            btn_save.setStyleSheet(f"background-color: {THEME['accent']}; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
            btn_save.setCursor(Qt.PointingHandCursor)
            
            def save_selection():
                selected = [pid for pid, cb in checkboxes.items() if cb.isChecked()]
                APP_CONFIG["video_auto_dl_playlists"] = selected
                from config import save_config
                save_config()
                self._initial_settings["video_auto_dl_playlists"] = selected
                self.btn_auto_pl.setText(f"Wybierz playlisty... ({len(selected)} wybrano)")
                dlg.accept()
                
            btn_save.clicked.connect(save_selection)
            layout.addWidget(btn_save)
            
            dlg.exec()
            
        self.main_window.run_async(fetch, on_ready)

    def _test_connection(self):
        self.lbl_status.setText("Łączenie...")
        self.lbl_status.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        QCoreApplication.processEvents()

        temp_client = NavidromeClient(self.inp_url.text(), self.inp_user.text(), self.inp_pwd.text())
        ok = temp_client.ping()

        if ok:
            self.lbl_status.setText("Połączono pomyślnie!")
            self.lbl_status.setStyleSheet("color: #1db954; background: transparent;")
        else:
            self.lbl_status.setText("Błąd połączenia.")
            self.lbl_status.setStyleSheet("color: #e74c3c; background: transparent;")

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.current_accent), self)
        if color.isValid():
            self.current_accent = color.name()
            self.btn_color.setStyleSheet(f"background-color: {self.current_accent}; color: white; padding: 8px; border-radius: 5px;")

    def _save_and_restart(self):
        APP_CONFIG["url"] = self.inp_url.text()
        APP_CONFIG["username"] = self.inp_user.text()
        APP_CONFIG["password"] = self.inp_pwd.text()
        APP_CONFIG["dark_mode"] = (self.combo_theme.currentIndex() == 0)
        APP_CONFIG["accent"] = self.current_accent
        APP_CONFIG["dev_mode"] = (self.combo_dev.currentIndex() == 1)

        self._initial_settings["url"] = APP_CONFIG["url"]
        self._initial_settings["username"] = APP_CONFIG["username"]
        self._initial_settings["password"] = APP_CONFIG["password"]
        self._initial_settings["dark_mode"] = APP_CONFIG["dark_mode"]
        self._initial_settings["accent"] = APP_CONFIG["accent"]
        self._initial_settings["dev_mode"] = APP_CONFIG["dev_mode"]

        save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)