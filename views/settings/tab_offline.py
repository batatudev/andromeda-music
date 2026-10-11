import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QPushButton, QDialog, QScrollArea, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from config import APP_CONFIG, save_config, THEME
from core.i18n import tr

class TabOffline(QWidget):
    def __init__(self, settings_view):
        super().__init__()
        self.settings_view = settings_view
        self.main_window = settings_view.main_window

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        offline_group = QFrame()
        offline_group.setObjectName("SettingsCard")
        offline_group.setStyleSheet(
            f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 12px; padding: 26px 85px; border: 1px solid {THEME['border']}; }}"
        )
        offline_layout = QVBoxLayout(offline_group)
        offline_layout.setSpacing(14)

        lbl_o_title = QLabel(tr("settings.offline.header", "Ustawienia pobierania"))
        lbl_o_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 8px; background: transparent;"
        )
        offline_layout.addWidget(lbl_o_title)

        input_style = (
            f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 6px; padding: 8px 12px; height: 22px; font-size: 13px;"
        )

        self.combo_smart_auto = QComboBox()
        self.combo_smart_auto.addItems([
            tr("settings.disabled", "Wyłączona"),
            tr("settings.automatic", "Automatyczne")
        ])
        self.combo_smart_auto.setCurrentIndex(1 if APP_CONFIG.get("video_smart_auto_play", False) else 0)
        self.combo_smart_auto.setStyleSheet(input_style)

        self.combo_off_quality = QComboBox()
        self.combo_off_quality.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_off_quality.setCurrentText(APP_CONFIG.get("video_offline_quality", "1080p"))
        self.combo_off_quality.setStyleSheet(input_style)

        self.combo_auto_favs = QComboBox()
        self.combo_auto_favs.addItems([
            tr("settings.disabled", "Wyłączona"),
            tr("settings.enabled", "Włączona")
        ])
        self.combo_auto_favs.setCurrentIndex(1 if APP_CONFIG.get("video_auto_dl_favs", False) else 0)
        self.combo_auto_favs.setStyleSheet(input_style)

        self.btn_auto_pl = QPushButton(tr("settings.offline.select_playlists", "Wybierz playlisty..."))
        self.btn_auto_pl.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                padding: 8px 14px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                height: 22px;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """)
        self.btn_auto_pl.setCursor(Qt.PointingHandCursor)
        self.btn_auto_pl.clicked.connect(lambda: self._show_playlists_sync_dialog("video"))

        self.combo_audio_auto_favs = QComboBox()
        self.combo_audio_auto_favs.addItems([
            tr("settings.disabled", "Wyłączona"),
            tr("settings.enabled", "Włączona")
        ])
        self.combo_audio_auto_favs.setCurrentIndex(1 if APP_CONFIG.get("audio_auto_dl_favs", False) else 0)
        self.combo_audio_auto_favs.setStyleSheet(input_style)

        self.btn_audio_auto_pl = QPushButton(tr("settings.offline.select_playlists", "Wybierz playlisty..."))
        self.btn_audio_auto_pl.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                padding: 8px 14px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                height: 22px;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """)
        self.btn_audio_auto_pl.setCursor(Qt.PointingHandCursor)
        self.btn_audio_auto_pl.clicked.connect(lambda: self._show_playlists_sync_dialog("audio"))

        v_pl_cnt = len(APP_CONFIG.get("video_auto_dl_playlists", []))
        self.btn_auto_pl.setText(f"{tr('settings.offline.select_playlists', 'Wybierz playlisty...')} ({v_pl_cnt})")

        a_pl_cnt = len(APP_CONFIG.get("audio_auto_dl_playlists", []))
        self.btn_audio_auto_pl.setText(f"{tr('settings.offline.select_playlists', 'Wybierz playlisty...')} ({a_pl_cnt})")

        self.combo_hide_offline = QComboBox()
        self.combo_hide_offline.addItems([
            tr("settings.offline.undownloaded_dim", "Wyszarz"),
            tr("settings.offline.undownloaded_hide", "Ukryj")
        ])
        self.combo_hide_offline.setCurrentIndex(1 if str(APP_CONFIG.get("hide_undownloaded_offline", "False")).lower() == 'true' else 0)
        self.combo_hide_offline.setStyleSheet(input_style)

        def add_row(parent_layout, text, widget):
            r = QHBoxLayout()
            r.setSpacing(20)
            lbl = QLabel(text)
            lbl.setFixedWidth(230)
            lbl.setFixedHeight(36)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; background: transparent;")
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            r.addWidget(lbl)
            r.addWidget(widget)
            parent_layout.addLayout(r)

        add_row(offline_layout, tr("settings.offline.auto_play", "Autoodtwarzanie wideo:"), self.combo_smart_auto)
        add_row(offline_layout, tr("settings.offline.quality", "Jakość wideo:"), self.combo_off_quality)
        add_row(offline_layout, tr("settings.offline.video_favs", "Pobieranie wideo z polubionych:"), self.combo_auto_favs)
        add_row(offline_layout, tr("settings.offline.video_playlists", "Pobieranie wideo z playlist:"), self.btn_auto_pl)
        add_row(offline_layout, tr("settings.offline.audio_favs", "Pobieranie utworów z polubionych:"), self.combo_audio_auto_favs)
        add_row(offline_layout, tr("settings.offline.audio_playlists", "Pobieranie utworów z playlist:"), self.btn_audio_auto_pl)
        add_row(offline_layout, tr("settings.offline.undownloaded", "Niepobrane utwory:"), self.combo_hide_offline)

        audio_actions_layout = QHBoxLayout()
        audio_actions_layout.setContentsMargins(0, 5, 0, 0)
        audio_actions_layout.addSpacing(250)

        btn_sync = QPushButton(tr("settings.offline.sync_meta", "Synchronizuj metadane"))
        btn_sync.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """)
        btn_sync.setCursor(Qt.PointingHandCursor)
        btn_sync.clicked.connect(self._sync_library)
        audio_actions_layout.addWidget(btn_sync)
        audio_actions_layout.addStretch()
        offline_layout.addLayout(audio_actions_layout)

        btn_save_offline = QPushButton(tr("settings.save", "Zapisz"))
        btn_save_offline.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """)
        btn_save_offline.setCursor(Qt.PointingHandCursor)
        btn_save_offline.clicked.connect(self._save_o_conf)

        self.lbl_o_status = QLabel("")
        self.lbl_o_status.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; background: transparent;")

        save_o_lay = QHBoxLayout()
        save_o_lay.setContentsMargins(0, 15, 0, 0)
        save_o_lay.addStretch()
        save_o_lay.addWidget(self.lbl_o_status)
        save_o_lay.addWidget(btn_save_offline)
        offline_layout.addLayout(save_o_lay)

        self.layout.addWidget(offline_group)
        self.layout.addStretch()

        if hasattr(self.main_window, 'repo'):
            sync_mgr = self.main_window.repo.library_sync
            sync_mgr.sync_progress.connect(self._on_sync_progress)
            sync_mgr.sync_completed.connect(self._on_sync_completed)
            sync_mgr.sync_error.connect(self._on_sync_error)

    def _on_sync_progress(self, current, total):
        sync_txt = tr("settings.offline.syncing", "Synchronizacja...")
        self.lbl_o_status.setText(f"{sync_txt} ({current})")

    def _on_sync_completed(self):
        self.lbl_o_status.setText(tr("settings.offline.sync_done", "Synchronizacja zakończona pomyślnie."))

    def _on_sync_error(self, error_msg):
        err_prefix = tr("settings.offline.sync_error", "Błąd synchronizacji:")
        self.lbl_o_status.setText(f"{err_prefix} {error_msg}")
        self.lbl_o_status.setStyleSheet("color: #e74c3c; font-weight: bold; background: transparent;")

    def _sync_library(self):
        win = self.main_window
        if hasattr(win, 'repo'):
            sync_mgr = win.repo.library_sync
            self.lbl_o_status.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; background: transparent;")
            sync_mgr.start_sync()
            self.lbl_o_status.setText(tr("settings.offline.syncing", "Synchronizacja..."))

    def _clear_status_text(self):
        try:
            if hasattr(self, 'lbl_o_status') and self.lbl_o_status:
                self.lbl_o_status.setText("")
        except RuntimeError:
            pass

    def _save_o_conf(self):
        APP_CONFIG["video_offline_quality"] = self.combo_off_quality.currentText()
        APP_CONFIG["video_smart_auto_play"] = (self.combo_smart_auto.currentIndex() == 1)
        APP_CONFIG["video_auto_dl_favs"] = (self.combo_auto_favs.currentIndex() == 1)
        APP_CONFIG["audio_auto_dl_favs"] = (self.combo_audio_auto_favs.currentIndex() == 1)
        APP_CONFIG["hide_undownloaded_offline"] = (self.combo_hide_offline.currentIndex() == 1)

        save_config()
        self.settings_view._initial_settings["video_offline_quality"] = APP_CONFIG["video_offline_quality"]
        self.settings_view._initial_settings["video_smart_auto_play"] = APP_CONFIG["video_smart_auto_play"]
        self.settings_view._initial_settings["video_auto_dl_favs"] = APP_CONFIG["video_auto_dl_favs"]
        self.settings_view._initial_settings["audio_auto_dl_favs"] = APP_CONFIG["audio_auto_dl_favs"]
        self.settings_view._initial_settings["hide_undownloaded_offline"] = APP_CONFIG["hide_undownloaded_offline"]

        self.lbl_o_status.setText(tr("settings.saved", "Zapisano ustawienia"))
        QTimer.singleShot(3000, self, self._clear_status_text)

    def _show_playlists_sync_dialog(self, media_type):
        def fetch():
            params = self.main_window.client._get_auth_params()
            res = self.main_window.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("dialogs.playlist_add_title", "Dodaj do playlisty"))
            dlg.setFixedSize(400, 500)
            from config import get_app_style
            dlg.setStyleSheet(get_app_style())
            layout = QVBoxLayout(dlg)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            content = QWidget()
            v = QVBoxLayout(content)
            v.setSpacing(5)

            checkboxes = {}
            conf_key = "video_auto_dl_playlists" if media_type == "video" else "audio_auto_dl_playlists"
            current_selected = APP_CONFIG.get(conf_key, [])

            for pl in playlists:
                pl_id = pl.get('id')
                cb = QCheckBox(pl.get('name', ''))
                cb.setStyleSheet(f"color: {THEME['text_main']}; spacing: 10px; font-size: 14px;")
                if pl_id in current_selected:
                    cb.setChecked(True)
                v.addWidget(cb)
                checkboxes[pl_id] = cb

            v.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll)

            btn_save = QPushButton(tr("dialogs.save", "Zapisz"))
            btn_save.setStyleSheet(f"background-color: {THEME['accent']}; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
            btn_save.setCursor(Qt.PointingHandCursor)

            def save_selection():
                selected = [pid for pid, cb in checkboxes.items() if cb.isChecked()]
                APP_CONFIG[conf_key] = selected
                from config import save_config
                save_config()
                self.settings_view._initial_settings[conf_key] = selected

                btn_prefix = tr("settings.offline.select_playlists", "Wybierz playlisty...")
                if media_type == "video":
                    self.btn_auto_pl.setText(f"{btn_prefix} ({len(selected)})")
                else:
                    self.btn_audio_auto_pl.setText(f"{btn_prefix} ({len(selected)})")
                dlg.accept()

            btn_save.clicked.connect(save_selection)
            layout.addWidget(btn_save)
            dlg.exec()

        self.main_window.run_async(fetch, on_ready)