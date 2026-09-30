import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: views/view_settings.py
# OPIS ZMIAN: Wdrożenie i18n przez tr() w głównym nagłówku oraz nazwach zakładek

import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QPushButton
)
from PySide6.QtCore import Qt

from config import APP_CONFIG, THEME
from core.i18n import tr

from views.settings.tab_server import TabServer
from views.settings.tab_theme import TabTheme
from views.settings.tab_video import TabVideo
from views.settings.tab_offline import TabOffline
from views.settings.tab_dev import TabDev

class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._initial_settings = {}
        self.buttons = []

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(15)

        self._init_layout()
        self.sync_values()

    def _init_layout(self):
        center_widget = QWidget()
        center_widget.setMaximumWidth(800)
        center_widget.setMinimumWidth(600)
        center_lay = QVBoxLayout(center_widget)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(20)

        header_lay = QHBoxLayout()
        lbl_title = QLabel(tr("settings.title", "Ustawienia"))
        lbl_title.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {THEME['text_main']}; background: transparent;"
        )
        header_lay.addWidget(lbl_title)

        lbl_version = QLabel("Andromeda Music")
        lbl_version.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; background: transparent;")
        header_lay.addStretch()
        header_lay.addWidget(lbl_version)

        center_lay.addLayout(header_lay)

        tab_bar_lay = QHBoxLayout()
        tab_bar_lay.setSpacing(10)

        self.stacked_widget = QStackedWidget()

        self.tab_server = TabServer(self)
        self.tab_theme = TabTheme(self)
        self.tab_video = TabVideo(self)
        self.tab_offline = TabOffline(self)
        self.tab_dev = TabDev(self)

        tabs_info = [
            (tr("settings.tab_server", "Serwer"), self.tab_server),
            (tr("settings.tab_theme", "Wygląd"), self.tab_theme),
            (tr("settings.tab_video", "Wideo"), self.tab_video),
            (tr("settings.tab_offline", "Pobieranie"), self.tab_offline),
            (tr("settings.tab_dev", "Deweloper"), self.tab_dev)
        ]

        for i, (name, tab_widget) in enumerate(tabs_info):
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME['bg_card']};
                    color: {THEME['text_main']};
                    padding: 8px 16px;
                    border-radius: 15px;
                    font-weight: bold;
                    border: 1px solid transparent;
                }}
                QPushButton:hover {{
                    background-color: {THEME['nav_bg']};
                }}
                QPushButton:checked {{
                    background-color: {THEME['accent']};
                    color: white;
                }}
            """)

            btn.clicked.connect(lambda checked=False, index=i: self._switch_tab(index))
            tab_bar_lay.addWidget(btn)
            self.buttons.append(btn)
            self.stacked_widget.addWidget(tab_widget)

        tab_bar_lay.addStretch()
        center_lay.addLayout(tab_bar_lay)
        center_lay.addWidget(self.stacked_widget)

        wrap_lay = QHBoxLayout()
        wrap_lay.addStretch()
        wrap_lay.addWidget(center_widget)
        wrap_lay.addStretch()

        self.main_layout.addLayout(wrap_lay)
        self.main_layout.addStretch()

    def _save_initial_state(self):
        self._initial_settings = {
            "url": APP_CONFIG.get("url", ""),
            "username": APP_CONFIG.get("username", ""),
            "password": APP_CONFIG.get("password", ""),
            "theme_mode": APP_CONFIG.get("theme_mode", "system"),
            "language": APP_CONFIG.get("language", "pl"),
            "accent": APP_CONFIG.get("accent", "#1db954"),
            "video_resolution": APP_CONFIG.get("video_resolution", "1080p"),
            "video_min_res": APP_CONFIG.get("video_min_res", "480p"),
            "video_auto_res": APP_CONFIG.get("video_auto_res", True),
            "video_dynamic_opacity": APP_CONFIG.get("video_dynamic_opacity", 30),
            "video_dynamic_blur": APP_CONFIG.get("video_dynamic_blur", 0),
            "video_static_opacity": APP_CONFIG.get("video_static_opacity", 80),
            "video_static_blur": APP_CONFIG.get("video_static_blur", 60),
            "dev_mode": APP_CONFIG.get("dev_mode", False),
            "video_offline_quality": APP_CONFIG.get("video_offline_quality", "1080p"),
            "video_smart_auto_play": APP_CONFIG.get("video_smart_auto_play", False),
            "video_auto_dl_favs": APP_CONFIG.get("video_auto_dl_favs", False),
            "video_auto_dl_playlists": list(APP_CONFIG.get("video_auto_dl_playlists", [])),
            "audio_auto_dl_favs": APP_CONFIG.get("audio_auto_dl_favs", False),
            "audio_auto_dl_playlists": list(APP_CONFIG.get("audio_auto_dl_playlists", [])),
            "hide_undownloaded_offline": APP_CONFIG.get("hide_undownloaded_offline", False)
        }

    def sync_values(self):
        self._save_initial_state()

        if hasattr(self, 'tab_server'):
            self.tab_server.inp_url.setText(APP_CONFIG.get("url", ""))
            self.tab_server.inp_user.setText(APP_CONFIG.get("username", ""))
            self.tab_server.inp_pwd.setText(APP_CONFIG.get("password", ""))

        if hasattr(self, 'tab_theme'):
            mode = APP_CONFIG.get("theme_mode", "system")
            if mode == "system":
                idx = 0
            elif mode == "light":
                idx = 2
            elif mode == "custom":
                idx = 3
            else:
                idx = 1
            self.tab_theme.combo_theme.setCurrentIndex(idx)
            lang = APP_CONFIG.get("language", "pl")
            self.tab_theme.combo_lang.setCurrentIndex(0 if lang == "pl" else 1)
            self.tab_theme.current_accent = APP_CONFIG.get("accent", "#1db954")
            self.tab_theme.btn_color.setStyleSheet(
                f"background-color: {self.tab_theme.current_accent}; color: white; padding: 8px; border-radius: 5px;"
            )

        if hasattr(self, 'tab_video'):
            self.tab_video.combo_res.setCurrentText(APP_CONFIG.get("video_resolution", "1080p"))
            self.tab_video.combo_auto_res.setCurrentIndex(1 if APP_CONFIG.get("video_auto_res", True) else 0)
            self.tab_video.combo_min_res.setCurrentText(APP_CONFIG.get("video_min_res", "480p"))
            for key, slider in self.tab_video.video_sliders.items():
                slider.blockSignals(True)
                slider.setValue(APP_CONFIG.get(key, 0))
                slider.blockSignals(False)

        if hasattr(self, 'tab_offline'):
            self.tab_offline.combo_smart_auto.setCurrentIndex(1 if APP_CONFIG.get("video_smart_auto_play", False) else 0)
            self.tab_offline.combo_off_quality.setCurrentText(APP_CONFIG.get("video_offline_quality", "1080p"))
            self.tab_offline.combo_auto_favs.setCurrentIndex(1 if APP_CONFIG.get("video_auto_dl_favs", False) else 0)
            self.tab_offline.combo_audio_auto_favs.setCurrentIndex(1 if APP_CONFIG.get("audio_auto_dl_favs", False) else 0)
            hide_val = str(APP_CONFIG.get("hide_undownloaded_offline", "False")).lower() == 'true'
            self.tab_offline.combo_hide_offline.setCurrentIndex(1 if hide_val else 0)

            v_cnt = len(APP_CONFIG.get("video_auto_dl_playlists", []))
            a_cnt = len(APP_CONFIG.get("audio_auto_dl_playlists", []))
            prefix = tr("settings.offline.select_playlists", "Wybierz playlisty...")
            self.tab_offline.btn_auto_pl.setText(f"{prefix} ({v_cnt})")
            self.tab_offline.btn_audio_auto_pl.setText(f"{prefix} ({a_cnt})")

        if hasattr(self, 'tab_dev'):
            self.tab_dev.combo_dev.setCurrentIndex(1 if APP_CONFIG.get("dev_mode", False) else 0)

    def revert_changes(self):
        if self._initial_settings:
            for k, v in self._initial_settings.items():
                APP_CONFIG[k] = v
            self.main_window.now_playing_view.update_video_settings()
            self.sync_values()

    def _switch_tab(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.stacked_widget.setCurrentIndex(index)