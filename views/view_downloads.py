import os
os.environ["QT_API"] = "pyside6"

import shutil
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QToolButton, QMenu, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from config import THEME, APP_CONFIG
from ui.components import DownloadItemWidget
from core.paths import PathsManager
from core.i18n import tr

class DownloadsView(QWidget):
    """
    Nowoczesne Centrum Transferów i Magazynu Pobrań w stylu Zenith Video Player.
    Zawiera graficzną kartę dysku, filtry stanów (pigułki z licznikami),
    priorytet dla aktywnych transferów oraz paginację ukończonych pozycji.
    """
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.v_mgr = main_window.engine.video_download_manager
        self.a_mgr = main_window.engine.audio_download_manager

        self.current_status_filter = "all"
        self.current_source_filter = "all"
        self.completed_limit = 15

        self.filter_buttons = {}
        self.item_widgets = {}
        self.raw_tasks = []
        self._pending_reload = False

        self._init_ui()
        self._connect_signals()
        self.load(force=True)

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # 1. KARTA MAGAZYNU I PAMIĘCI MASOWEJ (STYL ZENITH)
        self.storage_card = QFrame()
        self.storage_card.setObjectName("StorageCard")
        storage_vbox = QVBoxLayout(self.storage_card)
        storage_vbox.setContentsMargins(20, 16, 20, 18)
        storage_vbox.setSpacing(12)

        storage_head = QHBoxLayout()
        storage_head.setSpacing(10)

        icon_disk = QLabel()
        icon_disk.setPixmap(qta.icon('fa5s.hdd', color=THEME.get('accent', '#1db954')).pixmap(18, 18))
        storage_title = QLabel("Zarządzanie pamięcią masową i magazynem offline")
        storage_title.setStyleSheet(f"font-weight: bold; font-size: 16px; color: {THEME['text_main']};")

        storage_head.addWidget(icon_disk)
        storage_head.addWidget(storage_title)
        storage_head.addStretch()

        self.btn_open_folder = QPushButton("Otwórz folder offline")
        self.btn_open_folder.setIcon(qta.icon('fa5s.folder-open', color=THEME['text_main']))
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.setStyleSheet(
            f"QPushButton {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; "
            f"padding: 6px 14px; border-radius: 6px; font-weight: bold; border: none; }} "
            f"QPushButton:hover {{ background-color: {THEME['nav_hover']}; }}"
        )
        self.btn_open_folder.clicked.connect(self._open_downloads_dir)
        storage_head.addWidget(self.btn_open_folder)

        storage_vbox.addLayout(storage_head)

        # PASEK POSTĘPU DYSKU I STATYSTYKI
        self.storage_bar = QProgressBar()
        self.storage_bar.setObjectName("StorageBar")
        self.storage_bar.setFixedHeight(8)
        self.storage_bar.setTextVisible(False)
        self.storage_bar.setRange(0, 100)
        storage_vbox.addWidget(self.storage_bar)

        self.storage_stats_lbl = QLabel("Obliczanie rozmiaru pamięci...")
        self.storage_stats_lbl.setStyleSheet(f"font-size: 13px; color: {THEME['text_muted']};")
        storage_vbox.addWidget(self.storage_stats_lbl)

        # PRZYCISKI AKCJI ZARZĄDZANIA W KARTACH
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(10)

        tool_style = (
            f"QToolButton {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; "
            f"padding: 7px 14px; border-radius: 6px; font-weight: bold; border: none; }} "
            f"QToolButton:hover {{ background-color: {THEME['nav_hover']}; }} "
            f"QToolButton::menu-indicator {{ image: none; }}"
        )
        menu_style = (
            f"QMenu {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 6px; padding: 4px; }} "
            f"QMenu::item {{ padding: 8px 25px 8px 10px; border-radius: 4px; background: transparent; }} "
            f"QMenu::item:selected {{ background-color: {THEME['nav_bg']}; }} "
            f"QMenu::separator {{ height: 1px; background: {THEME['border']}; margin: 4px 10px; }}"
        )

        self.btn_dl_audio = QToolButton()
        self.btn_dl_audio.setText(tr("downloads.btn_audio", "Pobierz audio..."))
        self.btn_dl_audio.setPopupMode(QToolButton.InstantPopup)
        self.btn_dl_audio.setCursor(Qt.PointingHandCursor)
        self.btn_dl_audio.setStyleSheet(tool_style)
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

        self.btn_dl_video = QToolButton()
        self.btn_dl_video.setText(tr("downloads.btn_video", "Pobierz wideo..."))
        self.btn_dl_video.setPopupMode(QToolButton.InstantPopup)
        self.btn_dl_video.setCursor(Qt.PointingHandCursor)
        self.btn_dl_video.setStyleSheet(tool_style)
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

        self.btn_manage = QToolButton()
        self.btn_manage.setText(tr("downloads.btn_manage", "Zarządzaj"))
        self.btn_manage.setPopupMode(QToolButton.InstantPopup)
        self.btn_manage.setCursor(Qt.PointingHandCursor)
        self.btn_manage.setStyleSheet(tool_style)
        manage_menu = QMenu(self)
        manage_menu.setStyleSheet(menu_style)
        manage_menu.addAction(
            tr("downloads.clear_history", "Wyczyść historię"),
            self._clear_completed_history
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

        btn_action_style = (
            f"QPushButton {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; "
            f"padding: 7px 14px; border-radius: 6px; font-weight: bold; border: none; }} "
            f"QPushButton:hover {{ background-color: {THEME['nav_hover']}; }}"
        )

        self.btn_snooze_audio = QPushButton(tr("downloads.pause_audio", "Wstrzymaj audio"))
        self.btn_snooze_audio.setStyleSheet(btn_action_style)
        self.btn_snooze_audio.setCursor(Qt.PointingHandCursor)
        self.btn_snooze_audio.clicked.connect(self._toggle_snooze_audio)

        self.btn_snooze = QPushButton(tr("downloads.pause_video", "Wstrzymaj wideo"))
        self.btn_snooze.setStyleSheet(btn_action_style)
        self.btn_snooze.setCursor(Qt.PointingHandCursor)
        self.btn_snooze.clicked.connect(self._toggle_snooze)

        actions_bar.addWidget(self.btn_dl_audio)
        actions_bar.addWidget(self.btn_dl_video)
        actions_bar.addWidget(self.btn_manage)
        actions_bar.addSpacing(10)
        actions_bar.addWidget(self.btn_snooze_audio)
        actions_bar.addWidget(self.btn_snooze)
        actions_bar.addStretch()

        storage_vbox.addLayout(actions_bar)
        self.main_layout.addWidget(self.storage_card)

        # 2. SEKCJA KOLEJKI I STATUSÓW (PIGUŁKI W STYLU ZENITH)
        queue_header_lay = QHBoxLayout()
        queue_header_lay.setContentsMargins(0, 10, 0, 0)
        queue_title = QLabel("Kolejka i status transferów")
        queue_title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {THEME['text_main']};")
        queue_header_lay.addWidget(queue_title)
        queue_header_lay.addStretch()

        self.btn_clear_completed = QPushButton("Wyczyść ukończone")
        self.btn_clear_completed.setIcon(qta.icon('fa5s.trash-alt', color=THEME['text_muted']))
        self.btn_clear_completed.setCursor(Qt.PointingHandCursor)
        self.btn_clear_completed.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {THEME['text_muted']}; border: none; font-size: 13px; font-weight: bold; }} "
            f"QPushButton:hover {{ color: {THEME['text_main']}; }}"
        )
        self.btn_clear_completed.clicked.connect(self._clear_completed_history)
        queue_header_lay.addWidget(self.btn_clear_completed)

        self.main_layout.addLayout(queue_header_lay)

        # BELKA PIGUŁEK FILTRÓW
        pills_bar = QHBoxLayout()
        pills_bar.setSpacing(8)

        self.pills_data = [
            ("all", "Wszystkie"),
            ("downloading", "W trakcie"),
            ("queued", "W kolejce"),
            ("completed", "Ukończone"),
            ("error", "Błędy")
        ]

        for key, label in self.pills_data:
            btn = QPushButton(f"{label} (0)")
            btn.setObjectName("FilterPill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", "true" if key == "all" else "false")
            btn.clicked.connect(lambda ch=False, k=key: self._set_status_filter(k))
            pills_bar.addWidget(btn)
            self.filter_buttons[key] = btn

        pills_bar.addStretch()

        # PRZEŁĄCZNIK ŹRÓDŁA (AUDIO / WIDEO / WSZYSTKO)
        self.btn_source_all = QPushButton("Wszystko")
        self.btn_source_all.setObjectName("FilterPill")
        self.btn_source_all.setProperty("active", "true")
        self.btn_source_all.setCursor(Qt.PointingHandCursor)
        self.btn_source_all.clicked.connect(lambda: self._set_source_filter("all"))

        self.btn_source_audio = QPushButton("Tylko Audio")
        self.btn_source_audio.setObjectName("FilterPill")
        self.btn_source_audio.setProperty("active", "false")
        self.btn_source_audio.setCursor(Qt.PointingHandCursor)
        self.btn_source_audio.clicked.connect(lambda: self._set_source_filter("audio"))

        self.btn_source_video = QPushButton("Tylko Wideo")
        self.btn_source_video.setObjectName("FilterPill")
        self.btn_source_video.setProperty("active", "false")
        self.btn_source_video.setCursor(Qt.PointingHandCursor)
        self.btn_source_video.clicked.connect(lambda: self._set_source_filter("video"))

        pills_bar.addWidget(self.btn_source_all)
        pills_bar.addWidget(self.btn_source_audio)
        pills_bar.addWidget(self.btn_source_video)

        self.main_layout.addLayout(pills_bar)

        # 3. KONTENER LISTY ELEMENTÓW
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.main_layout.addWidget(self.list_container)

        # PRZYCISK ZAŁADUJ WIĘCEJ (PAGINACJA UKOŃCZONYCH)
        self.btn_load_more = QPushButton("Załaduj więcej")
        self.btn_load_more.setObjectName("LoadMoreBtn")
        self.btn_load_more.setCursor(Qt.PointingHandCursor)
        self.btn_load_more.clicked.connect(self._load_more_completed)
        self.btn_load_more.hide()
        self.main_layout.addWidget(self.btn_load_more)

        self.main_layout.addStretch()

    def _connect_signals(self):
        self.v_mgr.queue_updated.connect(self.load)
        self.v_mgr.download_status_changed.connect(self._on_video_status_changed)
        self.v_mgr.download_progress.connect(self._on_video_progress)

        self.a_mgr.queue_updated.connect(self.load)
        self.a_mgr.download_status_changed.connect(self._on_audio_status_changed)
        self.a_mgr.download_progress.connect(self._on_audio_progress)

    def _open_downloads_dir(self):
        dest_dir = PathsManager.get_data_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(dest_dir)))

    def _set_status_filter(self, status_key):
        self.current_status_filter = status_key
        for k, btn in self.filter_buttons.items():
            is_act = (k == status_key)
            btn.setProperty("active", "true" if is_act else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._rebuild_list()

    def _set_source_filter(self, source_key):
        self.current_source_filter = source_key
        self.btn_source_all.setProperty("active", "true" if source_key == "all" else "false")
        self.btn_source_audio.setProperty("active", "true" if source_key == "audio" else "false")
        self.btn_source_video.setProperty("active", "true" if source_key == "video" else "false")
        for b in [self.btn_source_all, self.btn_source_audio, self.btn_source_video]:
            b.style().unpolish(b)
            b.style().polish(b)
        self._rebuild_list()

    def _load_more_completed(self):
        self.completed_limit += 20
        self._rebuild_list()

    def _clear_completed_history(self):
        self.v_mgr.clear_history()
        self.a_mgr.clear_history()
        self.load(force=True)

    def _toggle_snooze_audio(self):
        if self.a_mgr.is_snoozed:
            self.a_mgr.set_snooze(0)
        else:
            self.a_mgr.set_snooze(-1)
        self.load(force=True)

    def _toggle_snooze(self):
        if self.v_mgr.is_snoozed:
            self.v_mgr.set_snooze(0)
        else:
            self.v_mgr.set_snooze(-1)
        self.load(force=True)

    def _show_playlist_picker(self, media_type):
        def fetch():
            params = self.main_window.client._get_auth_params()
            res = self.main_window.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea
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
                f"padding: 7px 14px; border-radius: 6px; font-weight: bold; border: none; }}"
            )
        else:
            self.btn_snooze_audio.setText(tr("downloads.pause_audio", "Wstrzymaj audio"))
            self.btn_snooze_audio.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; "
                f"padding: 7px 14px; border-radius: 6px; font-weight: bold; border: none; }} "
                f"QPushButton:hover {{ background-color: {THEME['nav_hover']}; }}"
            )

        if self.v_mgr.is_snoozed:
            self.btn_snooze.setText(tr("downloads.resume_video", "Wznów wideo"))
            self.btn_snooze.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['accent']}; color: white; "
                f"padding: 7px 14px; border-radius: 6px; font-weight: bold; border: none; }}"
            )
        else:
            self.btn_snooze.setText(tr("downloads.pause_video", "Wstrzymaj wideo"))
            self.btn_snooze.setStyleSheet(
                f"QPushButton {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; "
                f"padding: 7px 14px; border-radius: 6px; font-weight: bold; border: none; }} "
                f"QPushButton:hover {{ background-color: {THEME['nav_hover']}; }}"
            )

        v_rows = self.v_mgr.get_all_downloads()
        a_rows = self.a_mgr.get_all_downloads()
        v_dls, v_sz = self.v_mgr.get_total_download_stats()
        a_dls, a_sz = self.a_mgr.get_total_download_stats()

        # OBLICZANIE FIZYCZNEGO DYSKU (NVMe OFFLINE)
        try:
            total_b, used_b, free_b = shutil.disk_usage(str(PathsManager.get_data_dir()))
            total_gb = total_b / (1024 ** 3)
            used_gb = used_b / (1024 ** 3)
            free_gb = free_b / (1024 ** 3)
            pct = int((used_b / total_b) * 100) if total_b > 0 else 0
            self.storage_bar.setValue(pct)
        except Exception:
            used_gb = 0
            total_gb = 1
            free_gb = 0
            pct = 0

        a_mb = a_sz / (1024 * 1024)
        v_mb = v_sz / (1024 * 1024)

        stats_txt = (
            f"<b>Muzyka Audio:</b> {a_dls} utworów ({a_mb:.1f} MB) &nbsp;&bull;&nbsp; "
            f"<b>Teledyski Wideo:</b> {v_dls} filmów ({v_mb:.1f} MB) &nbsp;&bull;&nbsp; "
            f"<b>Dysk urządzenia:</b> {used_gb:.1f} GB / {total_gb:.1f} GB ({pct}%) &bull; <b>{free_gb:.1f} GB wolne</b>"
        )
        self.storage_stats_lbl.setText(stats_txt)

        # PARSOWANIE ZADAŃ WRAZ ZE ZNACZNIKIEM added_at
        tasks = []
        for r in a_rows:
            i_id = r[0]
            t_str = r[1]
            st = r[2]
            fsz = r[3] if len(r) > 3 else None
            added_ts = r[4] if len(r) > 4 and r[4] else 0
            tasks.append({
                'id': i_id,
                'title': t_str,
                'status': st,
                'media_type': 'audio',
                'cover_id': i_id,
                'resolution': None,
                'file_size': fsz,
                'added_at': int(added_ts)
            })

        for r in v_rows:
            i_id = r[0]
            t_str = r[1]
            st = r[2]
            cid = r[3] if len(r) > 3 else None
            res = r[4] if len(r) > 4 else None
            fsz = r[5] if len(r) > 5 else None
            added_ts = r[6] if len(r) > 6 and r[6] else 0
            tasks.append({
                'id': i_id,
                'title': t_str,
                'status': st,
                'media_type': 'video',
                'cover_id': cid,
                'resolution': res,
                'file_size': fsz,
                'added_at': int(added_ts)
            })

        self.raw_tasks = tasks
        self._update_pill_counts()
        self._rebuild_list()

    def _update_pill_counts(self):
        counts = {
            'all': len(self.raw_tasks),
            'downloading': 0,
            'queued': 0,
            'completed': 0,
            'error': 0
        }

        for t in self.raw_tasks:
            st = t['status']
            if st == "DOWNLOADING":
                counts['downloading'] += 1
            elif st == "QUEUED":
                counts['queued'] += 1
            elif st == "COMPLETED":
                counts['completed'] += 1
            elif st == "ERROR":
                counts['error'] += 1

        for key, btn in self.filter_buttons.items():
            base_label = dict(self.pills_data).get(key, key)
            c = counts.get(key, 0)
            btn.setText(f"{base_label} ({c})")
            if key == "error":
                btn.setProperty("has_error", "true" if c > 0 else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def _rebuild_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        self.item_widgets.clear()

        # 1. FILTROWANIE PO ŹRÓDLE
        filtered = self.raw_tasks
        if self.current_source_filter != "all":
            filtered = [t for t in filtered if t['media_type'] == self.current_source_filter]

        # 2. FILTROWANIE PO STATUSIE
        if self.current_status_filter == "downloading":
            filtered = [t for t in filtered if t['status'] == "DOWNLOADING"]
        elif self.current_status_filter == "queued":
            filtered = [t for t in filtered if t['status'] == "QUEUED"]
        elif self.current_status_filter == "completed":
            filtered = [t for t in filtered if t['status'] == "COMPLETED"]
        elif self.current_status_filter == "error":
            filtered = [t for t in filtered if t['status'] == "ERROR"]

        if not filtered:
            empty_lbl = QLabel("Brak zadań w wybranej kategorii.")
            empty_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px; margin: 30px 0;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty_lbl)
            self.btn_load_more.hide()
            return

        # 3. SORTOWANIE CHRONOLOGICZNE AUDIO I WIDEO (NAJNOWSZE NA GÓRZE)
        def sort_key(t):
            st = t['status']
            if st == "DOWNLOADING":
                prio = 0
            elif st == "QUEUED":
                prio = 1
            elif st == "ERROR":
                prio = 2
            else:
                prio = 3
            return (prio, -t['added_at'])

        sorted_tasks = sorted(filtered, key=sort_key)

        # 4. PAGINACJA UKOŃCZONYCH (ZAPOBIEGANIE TASIEMCOWI)
        active_tasks = [t for t in sorted_tasks if t['status'] != "COMPLETED"]
        completed_tasks = [t for t in sorted_tasks if t['status'] == "COMPLETED"]

        visible_completed = completed_tasks[:self.completed_limit]
        final_tasks = active_tasks + visible_completed

        for t in final_tasks:
            i_id = t['id']
            t_str = t['title']
            st = t['status']
            m_type = t['media_type']
            cid = t['cover_id']
            res = t['resolution']
            fsz = t['file_size']

            def make_remove_cb(target_id=i_id, target_type=m_type):
                if target_type == 'video':
                    return lambda ch: self.v_mgr.remove_download(target_id)
                return lambda ch: self.a_mgr.remove_download(target_id)

            w = DownloadItemWidget(i_id, t_str, st, m_type, make_remove_cb(), cid, res, fsz)
            if cid or i_id:
                self.main_window.loader.load(self.main_window.client.get_cover_art_url(cid or i_id), w.img)

            self.list_layout.addWidget(w)
            self.item_widgets[f"{m_type}_{i_id}"] = w

        # CZYSTY NAPIS PRZYCISKU ZAŁADUJ WIĘCEJ
        total_completed = len(completed_tasks)
        if total_completed > self.completed_limit:
            self.btn_load_more.setText(
                f"Załaduj więcej • Wyświetlono {len(visible_completed)} z {total_completed} ukończonych"
            )
            self.btn_load_more.show()
        else:
            self.btn_load_more.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, '_pending_reload', False):
            self.load(force=True)

    def _on_video_status_changed(self, item_id, status):
        key = f"video_{item_id}"
        if key in self.item_widgets:
            if status == "":
                self.load()
            else:
                self.item_widgets[key].update_status(status)
                self._update_pill_counts()
        else:
            self.load()

    def _on_video_progress(self, item_id, pct, stats_str=""):
        key = f"video_{item_id}"
        if key in self.item_widgets:
            self.item_widgets[key].update_progress(pct, stats_str)

    def _on_audio_status_changed(self, item_id, status):
        key = f"audio_{item_id}"
        if key in self.item_widgets:
            if status == "":
                self.load()
            else:
                self.item_widgets[key].update_status(status)
                self._update_pill_counts()
        else:
            self.load()

    def _on_audio_progress(self, item_id, pct, stats_str=""):
        key = f"audio_{item_id}"
        if key in self.item_widgets:
            self.item_widgets[key].update_progress(pct, stats_str)