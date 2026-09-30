import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: views/settings/tab_theme.py
# OPIS ZMIAN: Oczyszczenie etykiet i pełne wdrożenie i18n przez tr()

import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QPushButton, QColorDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from config import APP_CONFIG, save_config, THEME
from core.i18n import tr

class TabTheme(QWidget):
    def __init__(self, settings_view):
        super().__init__()
        self.settings_view = settings_view

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        theme_group = QFrame()
        theme_group.setObjectName("SettingsCard")
        theme_group.setStyleSheet(
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}"
        )
        theme_layout = QVBoxLayout(theme_group)

        lbl_t_title = QLabel(tr("settings.theme.header", "Wygląd aplikacji"))
        lbl_t_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;"
        )
        theme_layout.addWidget(lbl_t_title)

        input_style = (
            f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 5px; padding: 8px; height: 18px;"
        )

        self.combo_theme = QComboBox()
        self.combo_theme.addItems([
            tr("settings.theme.system", "Systemowy"),
            tr("settings.theme.dark", "Ciemny"),
            tr("settings.theme.light", "Jasny"),
            tr("settings.theme.custom", "Własny motyw")
        ])

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Polski", "English"])
        current_lang = APP_CONFIG.get("language", "pl")
        self.combo_lang.setCurrentIndex(0 if current_lang == "pl" else 1)
        self.combo_lang.setStyleSheet(input_style)
        self.combo_lang.setFixedWidth(350)

        current_mode = APP_CONFIG.get("theme_mode", "system")
        if current_mode == "system":
            self.combo_theme.setCurrentIndex(0)
        elif current_mode == "light":
            self.combo_theme.setCurrentIndex(2)
        elif current_mode == "custom":
            self.combo_theme.setCurrentIndex(3)
        else:
            self.combo_theme.setCurrentIndex(1)
        self.combo_theme.setStyleSheet(input_style)
        self.combo_theme.setFixedWidth(350)

        self.current_accent = APP_CONFIG["accent"]
        self.btn_color = QPushButton(tr("settings.theme.pick_color", "Wybierz kolor"))
        self.btn_color.setStyleSheet(
            f"background-color: {self.current_accent}; color: white; padding: 8px; border-radius: 5px;"
        )
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

        add_row(theme_layout, tr("settings.theme.mode", "Motyw:"), self.combo_theme)
        add_row(theme_layout, tr("settings.theme.lang", "Język:"), self.combo_lang)
        add_row(theme_layout, tr("settings.theme.accent", "Kolor akcentu:"), color_widget)

        btn_save_theme = QPushButton(tr("settings.save_restart", "Zapisz i restartuj"))
        btn_save_theme.setStyleSheet(
            f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;"
        )
        btn_save_theme.setCursor(Qt.PointingHandCursor)
        btn_save_theme.clicked.connect(self._save_and_restart)

        save_t_lay = QHBoxLayout()
        save_t_lay.addStretch()
        save_t_lay.addWidget(btn_save_theme)
        theme_layout.addLayout(save_t_lay)

        self.layout.addWidget(theme_group)
        self.layout.addStretch()

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.current_accent), self)
        if color.isValid():
            self.current_accent = color.name()
            self.btn_color.setStyleSheet(
                f"background-color: {self.current_accent}; color: white; padding: 8px; border-radius: 5px;"
            )

    def _save_and_restart(self):
        idx = self.combo_theme.currentIndex()
        if idx == 0:
            APP_CONFIG["theme_mode"] = "system"
        elif idx == 2:
            APP_CONFIG["theme_mode"] = "light"
        elif idx == 3:
            APP_CONFIG["theme_mode"] = "custom"
        else:
            APP_CONFIG["theme_mode"] = "dark"

        APP_CONFIG["language"] = "pl" if self.combo_lang.currentIndex() == 0 else "en"
        APP_CONFIG["accent"] = self.current_accent

        self.settings_view._initial_settings["theme_mode"] = APP_CONFIG["theme_mode"]
        self.settings_view._initial_settings["accent"] = APP_CONFIG["accent"]

        save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)