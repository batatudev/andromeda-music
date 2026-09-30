import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: views/view_downloads.py
# OPIS ZMIAN: Naprawa gramatyki, oczyszczenie etykiet z krzyku i wdrożenie pełnego i18n przez tr()

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QToolButton, QMenu, QMessageBox
)
from PySide6.QtCore import Qt
from config import THEME, APP_CONFIG
from ui.widgets import CollapsibleSection
from ui.components import DownloadItemWidget
from core.i18n import tr

class DownloadsView(QWidget):
    """
    Główny widok Menadżera Pobrań (audio i wideo).
    """
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.v_mgr = main_window.engine.video_download_manager
        self.a_mgr = main_window.engine.audio_download_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        header_lay = QHBoxLayout()
        title_lay = QVBoxLayout()
        title_lbl = QLabel(tr("downloads.title", "Pobrane"))
        title_lbl.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {THEME['text_main']};")

        self.total_size_lbl = QLabel(f"{tr('downloads.storage', 'Zajęte miejsce:')} 0 MB")
        self.total_size_lbl.setStyleSheet(f"font-size: 13px; color: {THEME['text_muted']};")

        self.stats_lbl = QLabel(
            f"{tr('downloads.stats_audio', 'Audio:')} 0 | {tr('downloads.stats_video', 'Wideo:')} 0"
        )
        self.stats_lbl.setStyleSheet(f"font-size: 13px; color: {THEME['text_main']}; font-weight: bold;")

        title_lay.addWidget(title_lbl)
        info_lay = QHBoxLayout()
        info_lay.addWidget(self.total_size_lbl)
        info_lay.addSpacing(20)
        info_lay.addWidget(self.stats_lbl)
        title_lay.addLayout(info_lay)
        header_lay.addLayout(title_lay)
        header_lay.addStretch()

        btn_style = (
            f"QToolButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
            f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }} "
            f"QToolButton:hover {{ background-color: {THEME['hover_card']}; }} "
            f"QToolButton::menu-indicator {{ image: none; }}"
        )

        menu_style = (
            f"QMenu {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 6px; padding: 4px; }} "
            f"QMenu::item {{ padding: 8px 25px 8px 10px; border-radius: 4px; background: transparent; }} "
            f"QMenu::item:selected {{ background-color: {THEME['nav_bg']}; }} "
            f"QMenu::separator {{ height: 1px; background: {THEME['border']}; margin: 4px 10px; }}"
        )

        # MENU POBIERZ WIDEO
        self.btn_dl_video = QToolButton()
        self.btn_dl_video.setText(tr("downloads.btn_video", "Pobierz wideo..."))
        self.btn_dl_video.setPopupMode(QToolButton.InstantPopup)
        self.btn_dl_video.setCursor(Qt.PointingHandCursor)
        self.btn_dl_video.setStyleSheet(btn_style)

        v_menu = QMenu(self)
        v_menu.setStyleSheet(menu_style)
        v_menu.addAction(
            qta.icon('fa5s.heart', color='#e74c3c'),
            tr("downloads.favs", "Pobierz polubione"),
            lambda: self.main_window.start_bulk_download("favorites", media_type="video")
        )
        v_menu.addAction(
            qta.icon('fa5s.list', color='#e74c3c'),
            tr("downloads.playlist", "Pobierz z playlisty"),
            lambda: self._show_playlist_picker("video")
        )
        v_menu.addAction(
            qta.icon('fa5s.database', color='#e74c3c'),
            tr("downloads.library", "Pobierz całą bibliotekę"),
            lambda: self.main_window.start_bulk_download("all", media_type="video")
        )
        self.btn_dl_video.setMenu(v_menu)
        header_lay.addWidget(self.btn_dl_video)

        # MENU POBIERZ AUDIO
        self.btn_dl_audio = QToolButton()
        self.btn_dl_audio.setText(tr("downloads.btn_audio", "Pobierz audio..."))
        self.btn_dl_audio.setPopupMode(QToolButton.InstantPopup)
        self.btn_dl_audio.setCursor(Qt.PointingHandCursor)
        self.btn_dl_audio.setStyleSheet(btn_style)

        a_menu = QMenu(self)
        a_menu.setStyleSheet(menu_style)
        a_menu.addAction(
            qta.icon('fa5s.heart', color=THEME['accent']),
            tr("downloads.favs", "Pobierz polubione"),
            lambda: self.main_window.start_bulk_download("favorites", media_type="audio")
        )
        a_menu.addAction(
            qta.icon('fa5s.list', color=THEME['accent']),
            tr("downloads.playlist", "Pobierz z playlisty"),
            lambda: self._show_playlist_picker("audio")
        )
        a_menu.addAction(
            qta.icon('fa5s.database', color=THEME['accent']),
            tr("downloads.library", "Pobierz całą bibliotekę"),
            lambda: self.main_window.start_bulk_download("all", media_type="audio")
        )
        self.btn_dl_audio.setMenu(a_menu)
        header_lay.addWidget(self.btn_dl_audio)

        # MENU ZARZĄDZAJ
        self.btn_manage = QToolButton()
        self.btn_manage.setText(tr("downloads.btn_manage", "Zarządzaj"))
        self.btn_manage.setPopupMode(QToolButton.InstantPopup)
        self.btn_manage.setCursor(Qt.PointingHandCursor)
        self.btn_manage.setStyleSheet(btn_style)

        manage_menu = QMenu(self)
        manage_menu.setStyleSheet(menu_style)
        manage_menu.addAction(
            tr("downloads.clear_history", "Wyczyść historię"),
            lambda: (self.v_mgr.clear_history(), self.a_mgr.clear_history())
        )
        manage_menu.addAction(
            tr("downloads.cancel_pending", "Anuluj oczekujące pobierania"),
            lambda: (self.v_mgr.cancel_all(), self.a_mgr.cancel_all())
        )
        manage_menu.addAction(
            tr("downloads.delete_all", "Usuń wszystkie pobrane pliki"),
            lambda: (self.v_mgr.delete_all_files(), self.a_mgr.delete_all_files())
        )
        self.btn_manage.setMenu(manage_menu)
        header_lay.addWidget(self.btn_manage)

        # WSTRZYMANIE AUDIO
        self.btn_snooze_audio = QPushButton(tr("downloads.pause_audio", "Wstrzymaj audio"))
        self.btn_snooze_audio.setStyleSheet(
            f"QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
            f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }} "
            f"QPushButton:hover {{ background-color: {THEME['hover_card']}; }}"
        )
        self.btn_snooze_audio.setCursor(Qt.PointingHandCursor)
        self.btn_snooze_audio.clicked.connect(self._toggle_snooze_audio)
        header_lay.addWidget(self.btn_snooze_audio)

        # WSTRZYMANIE WIDEO
        self.btn_snooze = QPushButton(tr("downloads.pause_video", "Wstrzymaj wideo"))
        self.btn_snooze.setStyleSheet(
            f"QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
            f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }} "
            f"QPushButton:hover {{ background-color: {THEME['hover_card']}; }}"
        )
        self.btn_snooze.setCursor(Qt.PointingHandCursor)
        self.btn_snooze.clicked.connect(self._toggle_snooze)
        header_lay.addWidget(self.btn_snooze)

        layout.addLayout(header_lay)

        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(20)
        self.items_layout.setAlignment(Qt.AlignTop)

        self.audio_section = CollapsibleSection(tr("downloads.section_audio", "Muzyka (Audio)"))
        self.video_section = CollapsibleSection(tr("downloads.section_video", "Teledyski (Wideo)"))

        self.items_layout.addWidget(self.audio_section)
        self.items_layout.addWidget(self.video_section)

        layout.addLayout(self.items_layout)
        layout.addStretch()

        self.item_widgets = {}
        self._pending_reload = False

        self.v_mgr.queue_updated.connect(self.load)
        self.v_mgr.download_status_changed.connect(self._on_video_status_changed)
        self.v_mgr.download_progress.connect(self._on_video_progress)

        self.a_mgr.queue_updated.connect(self.load)
        self.a_mgr.download_status_changed.connect(self._on_audio_status_changed)
        self.a_mgr.download_progress.connect(self._on_audio_progress)

        self.load(force=True)

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, '_pending_reload', False):
            self.load(force=True)

    def _toggle_snooze_audio(self):
        if self.a_mgr.is_snoozed:
            self.a_mgr.set_snooze(0)
        else:
            self.a_mgr.set_snooze(-1)

    def _toggle_snooze(self):
        if self.v_mgr.is_snoozed:
            self.v_mgr.set_snooze(0)
        else:
            self.v_mgr.set_snooze(-1)

    def _show_playlist_picker(self, media_type):
        def fetch():
            params = self.main_window.client._get_auth_params()
            res = self.main_window.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QPushButton
            dlg = QDialog(self)
            typ_txt = tr("downloads.section_video", "Wideo") if media_type == "video" else tr("downloads.section_audio", "Audio")
            dlg.setWindowTitle(f"{tr('downloads.playlist', 'Pobierz z playlisty')} ({typ_txt})")
            dlg.setFixedSize(320, 450)
            from config import get_app_style
            dlg.setStyleSheet(get_app_style())
            layout = QVBoxLayout(dlg)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            content = QWidget()
            v = QVBoxLayout(content)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(5)

            for pl in playlists:
                btn = QPushButton(pl.get('name'))
                btn.setStyleSheet(
                    f"text-align: left; padding: 10px; border-radius: 5px; background: {THEME['bg_card']}; "
                    f"color: {THEME['text_main']}; border: none;"
                )
                btn.setCursor(Qt.PointingHandCursor)
                def make_cb(pid, pname):
                    return lambda: self._start_pl_bulk(dlg, pid, pname, media_type)
                btn.clicked.connect(make_cb(pl.get('id'), pl.get('name')))
                v.addWidget(btn)

            v.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll)

            dlg.exec()
        self.main_window.run_async(fetch, on_ready)

    def _start_pl_bulk(self, dlg, pid, pname, media_type):
        dlg.accept()
        self.main_window.start_bulk_download('playlist', pid, pname, media_type)

    def load(self, *args, force=False, **kwargs):
        if not force and not self.isVisible():
            self._pending_reload = True
            return
        self._pending_reload = False
        if self.a_mgr.is_snoozed:
            self.btn_snooze_audio.setText(tr("downloads.resume_audio", "Wznów audio"))
            self.btn_snooze_audio.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['accent']}; color: white; "
                f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: none; }}"
            )
        else:
            self.btn_snooze_audio.setText(tr("downloads.pause_audio", "Wstrzymaj audio"))
            self.btn_snooze_audio.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
                f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }} "
                f"QPushButton:hover {{ background-color: {THEME['hover_card']}; }}"
            )

        if self.v_mgr.is_snoozed:
            self.btn_snooze.setText(tr("downloads.resume_video", "Wznów wideo"))
            self.btn_snooze.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['accent']}; color: white; "
                f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: none; }}"
            )
        else:
            self.btn_snooze.setText(tr("downloads.pause_video", "Wstrzymaj wideo"))
            self.btn_snooze.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
                f"padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }} "
                f"QPushButton:hover {{ background-color: {THEME['hover_card']}; }}"
            )

        self.audio_section.clear()
        self.video_section.clear()
        self.item_widgets.clear()

        v_rows = self.v_mgr.get_all_downloads()
        a_rows = self.a_mgr.get_all_downloads()

        v_dls, v_sz = self.v_mgr.get_total_download_stats()
        a_dls, a_sz = self.a_mgr.get_total_download_stats()

        storage_lbl = tr("downloads.storage", "Zajęte miejsce:")
        total_sz = v_sz + a_sz
        if total_sz > 1024 * 1024 * 1024:
            self.total_size_lbl.setText(f"{storage_lbl} {total_sz / (1024**3):.2f} GB")
        elif total_sz > 0:
            self.total_size_lbl.setText(f"{storage_lbl} {total_sz / (1024**2):.1f} MB")
        else:
            self.total_size_lbl.setText(f"{storage_lbl} 0 MB")

        self.stats_lbl.setText(
            f"{tr('downloads.stats_audio', 'Audio:')} {a_dls} | {tr('downloads.stats_video', 'Wideo:')} {v_dls}"
        )

        def sort_rows(rows, is_video):
            return sorted(rows, key=lambda x: 0 if x[2] == "DOWNLOADING" else (1 if x[2] == "QUEUED" else 2))

        sorted_v = sort_rows(v_rows, True)
        if not sorted_v:
            lbl = QLabel(tr("downloads.no_videos", "Brak pobranych teledysków."))
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px;")
            self.video_section.addWidget(lbl)
        else:
            for r in sorted_v:
                i_id = r[0]
                t_str = r[1]
                st = r[2]
                cid = r[3] if len(r) > 3 else None
                res = r[4] if len(r) > 4 else None
                fsz = r[5] if len(r) > 5 else None

                w = DownloadItemWidget(i_id, t_str, st, 'video', lambda ch, x=i_id: self.v_mgr.remove_download(x), cid, res, fsz)
                if cid or i_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(cid or i_id), w.img)
                self.video_section.addWidget(w)
                self.item_widgets[f"video_{i_id}"] = w

        sorted_a = sort_rows(a_rows, False)
        if not sorted_a:
            lbl = QLabel(tr("downloads.no_audio", "Brak pobranej muzyki."))
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px;")
            self.audio_section.addWidget(lbl)
        else:
            for r in sorted_a:
                i_id = r[0]
                t_str = r[1]
                st = r[2]
                fsz = r[3] if len(r) > 3 else None

                w = DownloadItemWidget(i_id, t_str, st, 'audio', lambda ch, x=i_id: self.a_mgr.remove_download(x), i_id, None, fsz)
                self.main_window.loader.load(self.main_window.client.get_cover_art_url(i_id), w.img)
                self.audio_section.addWidget(w)
                self.item_widgets[f"audio_{i_id}"] = w

    def _on_video_status_changed(self, item_id, status):
        key = f"video_{item_id}"
        if key in self.item_widgets:
            if status == "":
                self.load()
            else:
                self.item_widgets[key].update_status(status)

    def _on_video_progress(self, item_id, pct):
        key = f"video_{item_id}"
        if key in self.item_widgets:
            self.item_widgets[key].update_progress(pct)

    def _on_audio_status_changed(self, item_id, status):
        key = f"audio_{item_id}"
        if key in self.item_widgets:
            if status == "":
                self.load()
            else:
                self.item_widgets[key].update_status(status)

    def _on_audio_progress(self, item_id, pct):
        key = f"audio_{item_id}"
        if key in self.item_widgets:
            self.item_widgets[key].update_progress(pct)