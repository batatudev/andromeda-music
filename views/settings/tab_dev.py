import os
os.environ["QT_API"] = "pyside6"

import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt

from config import APP_CONFIG, save_config, THEME

class TabDev(QWidget):
    def __init__(self, settings_view):
        super().__init__()
        self.settings_view = settings_view

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        dev_group = QFrame()
        dev_group.setObjectName("SettingsCard")
        dev_group.setStyleSheet(
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 24px; }}"
        )
        dev_layout = QVBoxLayout(dev_group)
        dev_layout.setSpacing(14)

        lbl_d_title = QLabel("Opcje dla programistów")
        lbl_d_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;"
        )
        dev_layout.addWidget(lbl_d_title)

        input_style = (
            f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 6px; padding: 8px 12px; height: 20px; font-size: 13px;"
        )

        self.combo_dev = QComboBox()
        self.combo_dev.addItems(["Wyłączony", "Włączony"])
        self.combo_dev.setCurrentIndex(1 if APP_CONFIG.get("dev_mode", False) else 0)
        self.combo_dev.setStyleSheet(input_style)

        def add_row(parent_layout, text, widget):
            r = QHBoxLayout()
            r.setSpacing(15)
            lbl = QLabel(text)
            lbl.setMinimumWidth(140)
            lbl.setMaximumWidth(200)
            lbl.setFixedHeight(36)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; background: transparent;")
            widget.setMinimumWidth(240)
            widget.setMaximumWidth(460)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            r.addWidget(lbl)
            r.addWidget(widget)
            r.addStretch()
            parent_layout.addLayout(r)

        add_row(dev_layout, "Dev mode:", self.combo_dev)

        btn_save_dev = QPushButton("Zapisz i Restartuj")
        btn_save_dev.setStyleSheet(
            f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 20px; border-radius: 6px;"
        )
        btn_save_dev.setCursor(Qt.PointingHandCursor)
        btn_save_dev.clicked.connect(self._save_and_restart)

        save_d_lay = QHBoxLayout()
        save_d_lay.setContentsMargins(0, 10, 0, 0)
        save_d_lay.addStretch()
        save_d_lay.addWidget(btn_save_dev)
        dev_layout.addLayout(save_d_lay)

        self.layout.addWidget(dev_group)
        self.layout.addStretch()

    def _save_and_restart(self):
        APP_CONFIG["dev_mode"] = (self.combo_dev.currentIndex() == 1)
        self.settings_view._initial_settings["dev_mode"] = APP_CONFIG["dev_mode"]

        save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)