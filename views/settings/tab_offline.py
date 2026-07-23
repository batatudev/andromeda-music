import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QPushButton, QDialog, QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt, QTimer

from config import APP_CONFIG, save_config, THEME

class TabOffline(QWidget):
    def __init__(self, settings_view):
        super().__init__()
        self.settings_view = settings_view
        self.main_window = settings_view.main_window
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        offline_group = QFrame()
        offline_group.setObjectName("SettingsCard")
        offline_group.setStyleSheet(f"#SettingsCard {{ background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px; }}")
        offline_layout = QVBoxLayout(offline_group)

        lbl_o_title = QLabel("Ustawienia pobierania")
        lbl_o_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        offline_layout.addWidget(lbl_o_title)

        input_style = f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 5px; padding: 8px; height: 18px;"

        self.combo_smart_auto = QComboBox()
        self.combo_smart_auto.addItems(["Wyłączone (Wymaga kliknięcia teledysku)", "Włączone (Automatycznie załaduj offline)"])
        self.combo_smart_auto.setCurrentIndex(1 if APP_CONFIG.get("video_smart_auto_play", False) else 0)
        self.combo_smart_auto.setStyleSheet(input_style)
        self.combo_smart_auto.setFixedWidth(350)

        self.combo_off_quality = QComboBox()
        self.combo_off_quality.addItems(["1080p", "720p", "480p", "240p"])
        self.combo_off_quality.setCurrentText(APP_CONFIG.get("video_offline_quality", "1080p"))
        self.combo_off_quality.setStyleSheet(input_style)
        self.combo_off_quality.setFixedWidth(350)

        self.combo_auto_favs = QComboBox()
        self.combo_auto_favs.addItems(["Wyłączone", "Włączone (pobieraj przy polubieniu)"])
        self.combo_auto_favs.setCurrentIndex(1 if APP_CONFIG.get("video_auto_dl_favs", False) else 0)
        self.combo_auto_favs.setStyleSheet(input_style)
        self.combo_auto_favs.setFixedWidth(350)

        self.btn_auto_pl = QPushButton("Wybierz playlisty...")
        self.btn_auto_pl.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px; border-radius: 5px;")
        self.btn_auto_pl.setCursor(Qt.PointingHandCursor)
        self.btn_auto_pl.setFixedWidth(350)
        self.btn_auto_pl.clicked.connect(self._show_playlists_sync_dialog)

        pl_cnt = len(APP_CONFIG.get("video_auto_dl_playlists", []))
        self.btn_auto_pl.setText(f"Wybierz playlisty... ({pl_cnt} wybrano)")

        self.combo_hide_offline = QComboBox()
        self.combo_hide_offline.addItems(["Pokaż wyszarzone (Domyślne)", "Ukryj całkowicie"])
        self.combo_hide_offline.setCurrentIndex(1 if str(APP_CONFIG.get("hide_undownloaded_offline", "False")).lower() == 'true' else 0)
        self.combo_hide_offline.setStyleSheet(input_style)
        self.combo_hide_offline.setFixedWidth(350)

        def add_row(parent_layout, text, widget):
            r = QHBoxLayout()
            lbl = QLabel(text)
            lbl.setFixedWidth(240)
            lbl.setFixedHeight(34)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            lbl.setStyleSheet(f"font-weight: bold; color: {THEME['text_main']}; margin-right: 10px; background: transparent;")
            r.addWidget(lbl)
            r.addWidget(widget)
            r.addStretch()
            parent_layout.addLayout(r)

        add_row(offline_layout, "Wideo Autoodtwarzanie:", self.combo_smart_auto)
        add_row(offline_layout, "Wideo Jakość:", self.combo_off_quality)
        add_row(offline_layout, "Wideo Auto-pobieranie (Ulubione):", self.combo_auto_favs)
        add_row(offline_layout, "Wideo Auto-pobieranie (Playlisty):", self.btn_auto_pl)
        add_row(offline_layout, "Muzyka - Niepobrane utwory:", self.combo_hide_offline)
        
        # Audio actions
        audio_actions_layout = QHBoxLayout()
        audio_actions_layout.addStretch()
        
        btn_sync = QPushButton("Synchronizuj Metadane")
        btn_sync.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_sync.setCursor(Qt.PointingHandCursor)
        btn_sync.clicked.connect(self._sync_library)
        
        btn_dl_all = QPushButton("Pobierz Całą Muzykę (Zalecane)")
        btn_dl_all.setStyleSheet(f"background-color: {THEME['accent']}; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_dl_all.setCursor(Qt.PointingHandCursor)
        btn_dl_all.clicked.connect(self._download_all_audio)
        
        audio_actions_layout.addWidget(btn_sync)
        audio_actions_layout.addWidget(btn_dl_all)
        offline_layout.addLayout(audio_actions_layout)

        btn_save_offline = QPushButton("Zapisz Ustawienia Offline")
        btn_save_offline.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; padding: 8px 15px; border-radius: 5px; margin-top: 20px;")
        btn_save_offline.setCursor(Qt.PointingHandCursor)
        btn_save_offline.clicked.connect(self._save_o_conf)

        self.lbl_o_status = QLabel("")
        self.lbl_o_status.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; background: transparent; margin-top: 20px;")

        save_o_lay = QHBoxLayout()
        save_o_lay.addStretch()
        save_o_lay.addWidget(self.lbl_o_status)
        save_o_lay.addWidget(btn_save_offline)
        offline_layout.addLayout(save_o_lay)

        self.layout.addWidget(offline_group)
        self.layout.addStretch()

    def _sync_library(self):
        win = self.main_window
        if hasattr(win, 'engine'):
            from core.library_sync import LibrarySyncManager
            sync_mgr = LibrarySyncManager(win.client)
            sync_mgr.sync_progress.connect(lambda current, total: self.lbl_o_status.setText(f"Synchronizacja... ({current} pobrano)"))
            sync_mgr.sync_completed.connect(lambda: self.lbl_o_status.setText("Zakończono synchronizację!"))
            sync_mgr.start_sync()
            self.lbl_o_status.setText("Rozpoczynanie synchronizacji...")
            
    def _download_all_audio(self):
        win = self.main_window
        if hasattr(win, 'engine') and hasattr(win.engine, 'audio_download_manager'):
            win.engine.audio_download_manager.download_all_from_library()
            self.lbl_o_status.setText("Dodano całą bibliotekę do kolejki pobierania")
            QTimer.singleShot(4000, lambda: self.lbl_o_status.setText(""))

    def _save_o_conf(self):
        APP_CONFIG["video_offline_quality"] = self.combo_off_quality.currentText()
        APP_CONFIG["video_smart_auto_play"] = (self.combo_smart_auto.currentIndex() == 1)
        APP_CONFIG["video_auto_dl_favs"] = (self.combo_auto_favs.currentIndex() == 1)
        APP_CONFIG["hide_undownloaded_offline"] = (self.combo_hide_offline.currentIndex() == 1)

        save_config()
        self.settings_view._initial_settings["video_offline_quality"] = APP_CONFIG["video_offline_quality"]
        self.settings_view._initial_settings["video_smart_auto_play"] = APP_CONFIG["video_smart_auto_play"]
        self.settings_view._initial_settings["video_auto_dl_favs"] = APP_CONFIG["video_auto_dl_favs"]
        self.settings_view._initial_settings["hide_undownloaded_offline"] = APP_CONFIG["hide_undownloaded_offline"]

        self.lbl_o_status.setText("Zapisano pomyślnie (Wymagany restart dla niektórych opcji)")
        QTimer.singleShot(3000, lambda: self.lbl_o_status.setText(""))

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
                self.settings_view._initial_settings["video_auto_dl_playlists"] = selected
                self.btn_auto_pl.setText(f"Wybierz playlisty... ({len(selected)} wybrano)")
                dlg.accept()

            btn_save.clicked.connect(save_selection)
            layout.addWidget(btn_save)

            dlg.exec()

        self.main_window.run_async(fetch, on_ready)
