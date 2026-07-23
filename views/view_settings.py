import os
import sys

os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QPushButton
)
from PySide6.QtCore import Qt

from config import APP_CONFIG, THEME

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
            "theme_mode": APP_CONFIG.get("theme_mode", "system"),
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
            "video_auto_dl_playlists": APP_CONFIG.get("video_auto_dl_playlists", [])
        }

        self._clear(self.main_layout)

        center_widget = QWidget()
        center_widget.setMaximumWidth(800)
        center_widget.setMinimumWidth(600)
        center_lay = QVBoxLayout(center_widget)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(20)

        # Nagłówek i wersja
        header_lay = QHBoxLayout()
        lbl_title = QLabel("Ustawienia")
        lbl_title.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {THEME['text_main']}; background: transparent;")
        header_lay.addWidget(lbl_title)
        
        lbl_version = QLabel("Andromeda Music")
        lbl_version.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; background: transparent;")
        header_lay.addStretch()
        header_lay.addWidget(lbl_version)
        
        center_lay.addLayout(header_lay)

        # Tab Bar (Nawigacja)
        tab_bar_lay = QHBoxLayout()
        tab_bar_lay.setSpacing(10)
        
        self.buttons = []
        self.stacked_widget = QStackedWidget()

        tabs_info = [
            ("Serwer", TabServer),
            ("Wygląd", TabTheme),
            ("Wideo", TabVideo),
            ("Pobieranie", TabOffline),
            ("Deweloper", TabDev)
        ]

        for i, (name, WidgetClass) in enumerate(tabs_info):
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
            
            btn.clicked.connect(lambda checked, index=i: self._switch_tab(index))
            tab_bar_lay.addWidget(btn)
            self.buttons.append(btn)
            
            # Tworzenie widgetu dla danej zakładki
            tab_widget = WidgetClass(self)
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

    def _switch_tab(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.stacked_widget.setCurrentIndex(index)