import os
os.environ["QT_API"] = "pyside6"

import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QPushButton, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from config import APP_CONFIG, save_config, THEME
from core.i18n import tr

class TabVideo(QWidget):
    def __init__(self, settings_view):
        super().__init__()
        self.settings_view = settings_view
        self.main_window = settings_view.main_window

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        video_group = QFrame()
        video_group.setObjectName("SettingsCard")
        video_group.setStyleSheet(
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 12px; padding: 24px; border: 1px solid {THEME['border']}; }}"
        )
        video_layout = QVBoxLayout(video_group)
        video_layout.setSpacing(14)

        lbl_v_title = QLabel(tr("settings.video.header", "Teledyski"))
        lbl_v_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 2px; background: transparent;"
        )
        video_layout.addWidget(lbl_v_title)

        lbl_v_hint = QLabel(tr("settings.video.hint", "Ustawienia rozdzielczości będą aktywne od następnego utworu."))
        lbl_v_hint.setStyleSheet(
            f"color: {THEME['text_muted']}; font-size: 12px; margin-bottom: 10px; background: transparent;"
        )
        video_layout.addWidget(lbl_v_hint)

        input_style = (
            f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 6px; padding: 8px 12px; height: 20px; font-size: 13px;"
        )

        self.combo_res = QComboBox()
        self.combo_res.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_res.setCurrentText(APP_CONFIG.get("video_resolution", "1080p"))
        self.combo_res.setStyleSheet(input_style)

        self.combo_auto_res = QComboBox()
        self.combo_auto_res.addItems([
            tr("settings.disabled", "Wyłączona"),
            tr("settings.enabled", "Włączona")
        ])
        self.combo_auto_res.setCurrentIndex(1 if APP_CONFIG.get("video_auto_res", True) else 0)
        self.combo_auto_res.setStyleSheet(input_style)

        self.combo_min_res = QComboBox()
        self.combo_min_res.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_min_res.setCurrentText(APP_CONFIG.get("video_min_res", "480p"))
        self.combo_min_res.setStyleSheet(input_style)

        def add_row(parent_layout, text, widget):
            r = QHBoxLayout()
            r.setSpacing(15)
            lbl = QLabel(text)
            lbl.setFixedWidth(200)
            lbl.setFixedHeight(36)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; background: transparent;")
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            r.addWidget(lbl)
            r.addWidget(widget)
            parent_layout.addLayout(r)

        add_row(video_layout, tr("settings.video.res", "Domyślna rozdzielczość:"), self.combo_res)
        add_row(video_layout, tr("settings.video.arf", "Adaptacyjna jakość (ARF):"), self.combo_auto_res)
        add_row(video_layout, tr("settings.video.min_res", "Minimalna rozdzielczość:"), self.combo_min_res)

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
            lay.setSpacing(15)

            lbl = QLabel(label_text)
            lbl.setFixedWidth(200)
            lbl.setFixedHeight(36)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; background: transparent;")

            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            slider.setValue(APP_CONFIG.get(config_key, 0))
            slider.setStyleSheet(slider_style)

            val_lbl = QLabel(f"{slider.value()}%" if is_percent else f"{slider.value()}")
            val_lbl.setFixedWidth(45)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setStyleSheet(f"color: {THEME['text_main']}; font-weight: bold; background: transparent;")

            def on_change(v, l=val_lbl, k=config_key, perc=is_percent):
                l.setText(f"{v}%" if perc else f"{v}")
                APP_CONFIG[k] = v
                self.main_window.now_playing_view.update_video_settings()

            slider.valueChanged.connect(on_change)
            self.video_sliders[config_key] = slider

            lay.addWidget(lbl)
            lay.addWidget(slider)
            lay.addWidget(val_lbl)

            parent_layout.addLayout(lay)

        lbl_v_dyn = QLabel(tr("settings.video.profile_dynamic", "Teledysk (Wideo)"))
        lbl_v_dyn.setStyleSheet(
            f"font-weight: bold; font-size: 15px; color: {THEME['accent']}; margin-top: 10px; margin-bottom: 2px; background: transparent;"
        )
        video_layout.addWidget(lbl_v_dyn)

        add_slider(video_layout, tr("settings.video.opacity", "Przyciemnienie:"), "video_dynamic_opacity", True)
        add_slider(video_layout, tr("settings.video.blur", "Rozmycie:"), "video_dynamic_blur", False)

        lbl_v_stat = QLabel(tr("settings.video.profile_static", "Tło statyczne (Okładka)"))
        lbl_v_stat.setStyleSheet(
            f"font-weight: bold; font-size: 15px; color: {THEME['accent']}; margin-top: 15px; margin-bottom: 2px; background: transparent;"
        )
        video_layout.addWidget(lbl_v_stat)

        add_slider(video_layout, tr("settings.video.opacity", "Przyciemnienie:"), "video_static_opacity", True)
        add_slider(video_layout, tr("settings.video.blur", "Rozmycie:"), "video_static_blur", False)

        self.lbl_v_status = QLabel("")
        self.lbl_v_status.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; background: transparent;")

        btn_save_video = QPushButton(tr("settings.save", "Zapisz"))
        btn_save_video.setStyleSheet(
            f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; padding: 8px 24px; border-radius: 6px; border: none;"
        )
        btn_save_video.setCursor(Qt.PointingHandCursor)
        btn_save_video.clicked.connect(self._save_v_conf)

        save_v_lay = QHBoxLayout()
        save_v_lay.setContentsMargins(0, 15, 0, 0)
        save_v_lay.addStretch()
        save_v_lay.addWidget(self.lbl_v_status)
        save_v_lay.addWidget(btn_save_video)
        video_layout.addLayout(save_v_lay)

        self.layout.addWidget(video_group)
        self.layout.addStretch()

    def _clear_status_text(self):
        try:
            if hasattr(self, 'lbl_v_status') and self.lbl_v_status:
                self.lbl_v_status.setText("")
        except RuntimeError:
            pass

    def _save_v_conf(self):
        APP_CONFIG["video_resolution"] = self.combo_res.currentText()
        APP_CONFIG["video_min_res"] = self.combo_min_res.currentText()
        APP_CONFIG["video_auto_res"] = (self.combo_auto_res.currentIndex() == 1)
        for k, s in self.video_sliders.items():
            APP_CONFIG[k] = s.value()

        save_config()
        self.main_window.now_playing_view.update_video_settings()

        self.settings_view._initial_settings["video_resolution"] = APP_CONFIG["video_resolution"]
        self.settings_view._initial_settings["video_min_res"] = APP_CONFIG["video_min_res"]
        self.settings_view._initial_settings["video_auto_res"] = APP_CONFIG["video_auto_res"]
        self.settings_view._initial_settings["video_dynamic_opacity"] = APP_CONFIG["video_dynamic_opacity"]
        self.settings_view._initial_settings["video_dynamic_blur"] = APP_CONFIG["video_dynamic_blur"]
        self.settings_view._initial_settings["video_static_opacity"] = APP_CONFIG["video_static_opacity"]
        self.settings_view._initial_settings["video_static_blur"] = APP_CONFIG["video_static_blur"]

        self.lbl_v_status.setText(tr("settings.saved", "Zapisano ustawienia"))
        QTimer.singleShot(3000, self, self._clear_status_text)