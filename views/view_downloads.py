# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: views/view_downloads.py
# OPIS ZMIAN: Podział na zakładki Muzyka i Wideo. Obsługa AudioDownloadManager.
import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QFrame, QToolButton, QMenu, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt
from config import THEME, APP_CONFIG
from ui.widgets import HoverIconButton, RoundedImage

class CollapsibleSection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        self.btn_toggle = QPushButton(title)
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                font-size: 16px;
                font-weight: bold;
                text-align: left;
                padding: 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover_card']};
            }}
        """)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle)
        self.layout.addWidget(self.btn_toggle)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 5, 10, 15)
        self.content_layout.setSpacing(10)
        self.layout.addWidget(self.content_widget)

    def toggle(self):
        self.content_widget.setVisible(not self.content_widget.isVisible())

    def addWidget(self, w):
        self.content_layout.addWidget(w)

    def clear(self):
        while self.content_layout.count():
            i = self.content_layout.takeAt(0)
            if i.widget():
                i.widget().deleteLater()

class DownloadItemWidget(QFrame):
    def __init__(self, item_id, title, status, media_type, remove_cb, cover_id=None, resolution=None, file_size=None, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("Card")
        self.setStyleSheet(f"#Card {{ background-color: {THEME['bg_card']}; border-radius: 8px; }}")
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        # Okładka
        self.img = RoundedImage(size=50, radius=6)
        self.img.setFixedSize(50, 50)
        layout.addWidget(self.img)

        # Info
        info_lay = QVBoxLayout()
        info_lay.setSpacing(3)
        info_lay.setContentsMargins(0, 0, 0, 0)
        
        # Ikona typu i tytuł
        icon_str = 'fa5s.music' if media_type == 'audio' else 'fa5s.film'
        icon_color = THEME['accent'] if media_type == 'audio' else '#e74c3c'
        
        title_lay = QHBoxLayout()
        title_lay.setContentsMargins(0,0,0,0)
        title_lay.setSpacing(5)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_str, color=icon_color).pixmap(12, 12))
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {THEME['text_main']}; background: transparent;")
        title_lay.addWidget(icon_lbl)
        title_lay.addWidget(self.title_lbl)
        title_lay.addStretch()
        
        # Generowanie tekstu statusu
        self.base_status = status
        self.resolution = resolution
        self.file_size = file_size
        
        status_text = self._build_status_text()
        self.status_lbl = QLabel(status_text)
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {THEME['text_muted']}; background: transparent;")

        info_lay.addLayout(title_lay)
        info_lay.addWidget(self.status_lbl)

        layout.addLayout(info_lay)
        layout.addStretch()

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setFixedWidth(150)
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background-color: {THEME['nav_bg']}; border-radius: 5px; }}
            QProgressBar::chunk {{ background-color: {THEME['accent']}; border-radius: 5px; }}
        """)
        self.progress.setVisible(status == "DOWNLOADING")
        layout.addWidget(self.progress)

        # Usuń przycisk
        self.btn_remove = HoverIconButton('fa5s.times', icon_size=14)
        self.btn_remove.setFixedSize(32, 32)
        self.btn_remove.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: 16px; }} QPushButton:hover {{ background: {THEME['btn_remove_hover']}; }}")
        self.btn_remove.setToolTip("Usuń pobieranie / plik")
        self.btn_remove.clicked.connect(remove_cb)
        layout.addWidget(self.btn_remove)

    def _translate_status(self, st):
        trans = {
            "QUEUED": "Oczekuje w kolejce",
            "DOWNLOADING": "Pobieranie...",
            "COMPLETED": "Pobrano",
            "ERROR": "Błąd",
            "PAUSED": "Wstrzymano"
        }
        return trans.get(st, st)

    def _parse_resolution(self, res_str):
        if not res_str:
            return "1080p"
        if 'x' in res_str:
            try:
                return f"{int(res_str.split('x')[1])}p"
            except (ValueError, IndexError):
                pass
        return res_str

    def _build_status_text(self):
        status_text = self._translate_status(self.base_status)
        if self.base_status == "COMPLETED" and self.file_size:
            sz_mb = self.file_size / (1024 * 1024)
            if self.resolution:
                res_str = self._parse_resolution(self.resolution)
                status_text += f" • {res_str} • {sz_mb:.1f} MB"
            else:
                status_text += f" • {sz_mb:.1f} MB"
        return status_text

    def update_status(self, new_status, file_size=None, resolution=None):
        self.base_status = new_status
        if file_size is not None: self.file_size = file_size
        if resolution is not None: self.resolution = resolution
        self.status_lbl.setText(self._build_status_text())
        self.progress.setVisible(new_status == "DOWNLOADING")

    def update_progress(self, pct):
        self.progress.setValue(int(pct))


class DownloadsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.v_mgr = main_window.engine.video_download_manager
        self.a_mgr = main_window.engine.audio_download_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header_lay = QHBoxLayout()
        title_lay = QVBoxLayout()
        title_lbl = QLabel("Menadżer Pobrania")
        title_lbl.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {THEME['text_main']};")

        self.total_size_lbl = QLabel("Zajęte miejsce: 0 MB")
        self.total_size_lbl.setStyleSheet(f"font-size: 13px; color: {THEME['text_muted']};")

        self.stats_lbl = QLabel("Wideo: 0 | Audio: 0")
        self.stats_lbl.setStyleSheet(f"font-size: 13px; color: {THEME['text_main']}; font-weight: bold;")

        title_lay.addWidget(title_lbl)
        info_lay = QHBoxLayout()
        info_lay.addWidget(self.total_size_lbl)
        info_lay.addSpacing(20)
        info_lay.addWidget(self.stats_lbl)
        title_lay.addLayout(info_lay)
        header_lay.addLayout(title_lay)
        header_lay.addStretch()

        button_style = f"""
            QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }}
            QPushButton:hover {{ background-color: {THEME['hover_card']}; }}
        """

        self.btn_dl_fav = QPushButton("Pobierz Ulubione (Wideo)")
        self.btn_dl_fav.setStyleSheet(button_style)
        self.btn_dl_fav.setCursor(Qt.PointingHandCursor)
        self.btn_dl_fav.clicked.connect(lambda: self.main_window.start_bulk_download("favorites"))
        header_lay.addWidget(self.btn_dl_fav)

        self.btn_manage = QToolButton()
        self.btn_manage.setText("Zarządzaj Wszystkim")
        self.btn_manage.setPopupMode(QToolButton.InstantPopup)
        self.btn_manage.setCursor(Qt.PointingHandCursor)
        self.btn_manage.setStyleSheet(f"""
            QToolButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }}
            QToolButton:hover {{ background-color: {THEME['hover_card']}; }}
            QToolButton::menu-indicator {{ image: none; }}
        """)
        manage_menu = QMenu(self)
        manage_menu.setStyleSheet(f"""
            QMenu {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 6px; padding: 4px; }}
            QMenu::item {{ padding: 8px 25px 8px 10px; border-radius: 4px; background: transparent; }}
            QMenu::item:selected {{ background-color: {THEME['nav_bg']}; }}
        """)
        manage_menu.addAction("Pobierz Całą Bazę Wideo", lambda: self.main_window.start_bulk_download("all"))
        manage_menu.addSeparator()
        manage_menu.addAction("Wyczyść historię (ukryj błędy)", lambda: (self.v_mgr.clear_history(), self.a_mgr.clear_history()))
        manage_menu.addAction("Anuluj oczekujące pobierania", lambda: (self.v_mgr.cancel_all(), self.a_mgr.cancel_all()))
        manage_menu.addAction("Usuń WSZYSTKIE pliki (Audio i Wideo)", lambda: (self.v_mgr.delete_all_files(), self.a_mgr.delete_all_files()))
        self.btn_manage.setMenu(manage_menu)
        header_lay.addWidget(self.btn_manage)

        self.btn_snooze = QPushButton("Wstrzymaj Wideo")
        self.btn_snooze.setStyleSheet(button_style)
        self.btn_snooze.setCursor(Qt.PointingHandCursor)
        self.btn_snooze.clicked.connect(self._toggle_snooze)
        header_lay.addWidget(self.btn_snooze)

        layout.addLayout(header_lay)

        # Kontenery na sekcje Audio i Wideo
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(20)
        self.items_layout.setAlignment(Qt.AlignTop)

        self.audio_section = CollapsibleSection("Muzyka (Audio)")
        self.video_section = CollapsibleSection("Teledyski (Wideo)")

        self.items_layout.addWidget(self.audio_section)
        self.items_layout.addWidget(self.video_section)

        layout.addLayout(self.items_layout)
        layout.addStretch()

        self.item_widgets = {}

        # Podłączanie zdarzeń dla Wideo
        self.v_mgr.queue_updated.connect(self.load)
        self.v_mgr.download_status_changed.connect(self._on_video_status_changed)
        self.v_mgr.download_progress.connect(self._on_video_progress)

        # Podłączanie zdarzeń dla Audio
        self.a_mgr.queue_updated.connect(self.load)
        self.a_mgr.download_status_changed.connect(self._on_audio_status_changed)
        self.a_mgr.download_progress.connect(self._on_audio_progress)

        self.load()

    def _toggle_snooze(self):
        if self.v_mgr.is_snoozed:
            self.v_mgr.set_snooze(0)
        else:
            self.v_mgr.set_snooze(-1)

    def load(self, *args, **kwargs):
        if self.v_mgr.is_snoozed:
            self.btn_snooze.setText("Wznów Wideo")
            self.btn_snooze.setStyleSheet(f"QPushButton {{ background-color: {THEME['accent']}; color: white; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: none; }}")
        else:
            self.btn_snooze.setText("Wstrzymaj Wideo")
            self.btn_snooze.setStyleSheet(f"QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }} QPushButton:hover {{ background-color: {THEME['hover_card']}; }}")

        self.audio_section.clear()
        self.video_section.clear()
        self.item_widgets.clear()

        # Pobieranie danych
        v_rows = self.v_mgr.get_all_downloads()
        a_rows = self.a_mgr.get_all_downloads()

        v_dls, v_sz = self.v_mgr.get_total_download_stats()
        a_dls, a_sz = self.a_mgr.get_total_download_stats()

        total_sz = v_sz + a_sz
        if total_sz > 1024 * 1024 * 1024:
            self.total_size_lbl.setText(f"Zajęte miejsce: {total_sz / (1024**3):.2f} GB")
        elif total_sz > 0:
            self.total_size_lbl.setText(f"Zajęte miejsce: {total_sz / (1024**2):.1f} MB")
        else:
            self.total_size_lbl.setText("Zajęte miejsce: 0 MB")

        self.stats_lbl.setText(f"Audio: {a_dls} plików | Wideo: {v_dls} plików")

        def sort_rows(rows, is_video):
            # Sort: DOWNLOADING, QUEUED, reszta
            return sorted(rows, key=lambda x: 0 if x[2] == "DOWNLOADING" else (1 if x[2] == "QUEUED" else 2))

        # Renderowanie Wideo
        sorted_v = sort_rows(v_rows, True)
        if not sorted_v:
            lbl = QLabel("Brak teledysków w kolejce lub na dysku.")
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px;")
            self.video_section.addWidget(lbl)
        else:
            for r in sorted_v:
                # r: item_id, title, status, cover_id, resolution, file_size
                i_id, t_str, st, cid, res, fsz = r[0], r[1], r[2], r[3] if len(r)>3 else None, r[4] if len(r)>4 else None, r[5] if len(r)>5 else None
                w = DownloadItemWidget(i_id, t_str, st, 'video', lambda ch, x=i_id: self.v_mgr.remove_download(x), cid, res, fsz)
                if cid or i_id:
                    self.main_window.loader.load(self.main_window.client.get_cover_art_url(cid or i_id), w.img)
                self.video_section.addWidget(w)
                self.item_widgets[f"video_{i_id}"] = w

        # Renderowanie Audio
        sorted_a = sort_rows(a_rows, False)
        if not sorted_a:
            lbl = QLabel("Brak utworów w kolejce lub na dysku.")
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px;")
            self.audio_section.addWidget(lbl)
        else:
            for r in sorted_a:
                # r: item_id, title, status, file_size
                i_id, t_str, st, fsz = r[0], r[1], r[2], r[3] if len(r)>3 else None
                w = DownloadItemWidget(i_id, t_str, st, 'audio', lambda ch, x=i_id: self.a_mgr.remove_download(x), i_id, None, fsz)
                self.main_window.loader.load(self.main_window.client.get_cover_art_url(i_id), w.img)
                self.audio_section.addWidget(w)
                self.item_widgets[f"audio_{i_id}"] = w

    def _on_video_status_changed(self, item_id, status):
        key = f"video_{item_id}"
        if key in self.item_widgets:
            if status == "": self.load()
            else: self.item_widgets[key].update_status(status)

    def _on_video_progress(self, item_id, pct):
        key = f"video_{item_id}"
        if key in self.item_widgets:
            self.item_widgets[key].update_progress(pct)

    def _on_audio_status_changed(self, item_id, status):
        key = f"audio_{item_id}"
        if key in self.item_widgets:
            if status == "": self.load()
            else: self.item_widgets[key].update_status(status)

    def _on_audio_progress(self, item_id, pct):
        key = f"audio_{item_id}"
        if key in self.item_widgets:
            self.item_widgets[key].update_progress(pct)