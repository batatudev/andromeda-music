# WERSJA PROJEKTU: 14.19
# MODYFIKOWANY PLIK: views/view_downloads.py
# OPIS ZMIAN: Naprawiono ładowanie okładek - używamy item_id jako fallback dla cover_id (Navidrome getCoverArt akceptuje song_id).

import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QProgressBar, QMenu, QToolButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from config import THEME
from ui.widgets import HoverIconButton, RoundedImage
from utils import AsyncImageLoader

class DownloadItemWidget(QFrame):
    def __init__(self, item_id, title, status, cover_id=None, resolution=None, file_size=None, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("Card")
        self.setStyleSheet(f"#Card {{ background-color: {THEME['bg_card']}; border-radius: 8px; }}")
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        # Okładka
        self.img = RoundedImage(size=50, radius=8)
        self.img.setFixedSize(50, 50)
        layout.addWidget(self.img)

        # Info
        info_lay = QVBoxLayout()
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {THEME['text_main']}; background: transparent;")
        
        # Generowanie tekstu statusu
        status_text = self._translate_status(status)
        if status == "COMPLETED" and file_size:
            sz_mb = file_size / (1024 * 1024)
            res_str = resolution if resolution else "1080p"
            status_text += f" • {res_str} • {sz_mb:.1f} MB"
            
        self.status_lbl = QLabel(status_text)
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {THEME['text_muted']}; background: transparent;")
        
        self.base_status = status
        self.resolution = resolution
        self.file_size = file_size
        
        info_lay.addWidget(self.title_lbl)
        info_lay.addWidget(self.status_lbl)
        
        layout.addLayout(info_lay)
        layout.addStretch()

        # Progress bar (widoczny tylko dla DOWNLOADING)
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

    def update_status(self, new_status, file_size=None, resolution=None):
        self.base_status = new_status
        if file_size is not None:
            self.file_size = file_size
        if resolution is not None:
            self.resolution = resolution
            
        status_text = self._translate_status(new_status)
        if new_status == "COMPLETED" and self.file_size:
            sz_mb = self.file_size / (1024 * 1024)
            res_str = self.resolution if self.resolution else "1080p"
            status_text += f" • {res_str} • {sz_mb:.1f} MB"
            
        self.status_lbl.setText(status_text)
        self.progress.setVisible(new_status == "DOWNLOADING")

    def update_progress(self, pct):
        self.progress.setValue(int(pct))

class DownloadsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.mgr = main_window.engine.video_download_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Tytuł i rozmiar
        header_lay = QHBoxLayout()
        title_lay = QVBoxLayout()
        title_lbl = QLabel("Menadżer Pobrań (Offline)")
        title_lbl.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {THEME['text_main']};")
        
        self.total_size_lbl = QLabel("Zajęte miejsce: 0 MB")
        self.total_size_lbl.setStyleSheet(f"font-size: 13px; color: {THEME['text_muted']};")
        
        title_lay.addWidget(title_lbl)
        title_lay.addWidget(self.total_size_lbl)
        header_lay.addLayout(title_lay)
        header_lay.addStretch()

        # Przycisk "Akcje masowe"
        self.btn_bulk = QToolButton()
        self.btn_bulk.setText("Akcje masowe")
        self.btn_bulk.setPopupMode(QToolButton.InstantPopup)
        self.btn_bulk.setCursor(Qt.PointingHandCursor)
        self.btn_bulk.setStyleSheet(f"""
            QToolButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }}
            QToolButton:hover {{ background-color: {THEME['hover_card']}; }}
            QToolButton::menu-indicator {{ image: none; }}
        """)
        bulk_menu = QMenu(self)
        bulk_menu.setStyleSheet(self._menu_style())
        bulk_menu.addAction("Pobierz Ulubione", lambda: self._start_bulk("favorites"))
        bulk_menu.addAction("Pobierz Wybrane Playlisty", lambda: self._start_bulk("playlists"))
        bulk_menu.addSeparator()
        bulk_menu.addAction("Pobierz Wszystkie (cała baza)", lambda: self._start_bulk("all"))
        self.btn_bulk.setMenu(bulk_menu)
        header_lay.addWidget(self.btn_bulk)

        # Przycisk wstrzymania
        self.btn_snooze = QToolButton()
        self.btn_snooze.setText("Wstrzymaj")
        self.btn_snooze.setPopupMode(QToolButton.InstantPopup)
        self.btn_snooze.setCursor(Qt.PointingHandCursor)
        self.btn_snooze.setStyleSheet(f"""
            QToolButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }}
            QToolButton:hover {{ background-color: {THEME['hover_card']}; }}
            QToolButton::menu-indicator {{ image: none; }}
        """)
        
        snooze_menu = QMenu(self)
        snooze_menu.setStyleSheet(self._menu_style())
        snooze_menu.addAction("Wznów (anuluj wstrzymanie)", lambda: self.mgr.set_snooze(0))
        snooze_menu.addSeparator()
        snooze_menu.addAction("Wstrzymaj na stałe", lambda: self.mgr.set_snooze(-1))
        snooze_menu.addAction("Wstrzymaj do ponownego uruchomienia", lambda: self.mgr.set_snooze(-2))
        snooze_menu.addAction("Wstrzymaj na 30 min", lambda: self.mgr.set_snooze(0.5))
        snooze_menu.addAction("Wstrzymaj na 1h", lambda: self.mgr.set_snooze(1))
        snooze_menu.addAction("Wstrzymaj na 2h", lambda: self.mgr.set_snooze(2))
        snooze_menu.addAction("Wstrzymaj na 12h", lambda: self.mgr.set_snooze(12))
        snooze_menu.addAction("Wstrzymaj na 24h", lambda: self.mgr.set_snooze(24))
        self.btn_snooze.setMenu(snooze_menu)
        
        header_lay.addWidget(self.btn_snooze)
        
        layout.addLayout(header_lay)

        # Kontener na listę
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(10)
        self.items_layout.setAlignment(Qt.AlignTop)
        layout.addLayout(self.items_layout)
        layout.addStretch()

        self.item_widgets = {}

        self.mgr.queue_updated.connect(self.load)
        self.mgr.download_status_changed.connect(self._on_status_changed)
        self.mgr.download_progress.connect(self._on_progress)
        
        self.load() # Załaduj przy inicjalizacji

    def _menu_style(self):
        return f"""
            QMenu {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 6px; padding: 4px; }}
            QMenu::item {{ padding: 8px 25px 8px 10px; border-radius: 4px; background: transparent; }}
            QMenu::item:selected {{ background-color: {THEME['nav_bg']}; }}
            QMenu::separator {{ height: 1px; background: {THEME['border']}; margin: 4px 10px; }}
        """

    def _start_bulk(self, bulk_type):
        # Tymczasowy alert - pełna implementacja za moment
        msg = QMessageBox(self)
        msg.setWindowTitle("Akcje masowe")
        msg.setText(f"Opcja {bulk_type} będzie dostępna po wdrożeniu logiki liczenia.")
        msg.exec()

    def load(self, *args, **kwargs):
        # Aktualizacja przycisku snooze
        if self.mgr.is_snoozed:
            self.btn_snooze.setText("Wznów pobieranie")
            self.btn_snooze.setStyleSheet(f"""
                QToolButton {{ background-color: {THEME['accent']}; color: {THEME['bg_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; }}
                QToolButton:hover {{ opacity: 0.8; }}
                QToolButton::menu-indicator {{ image: none; }}
            """)
        else:
            self.btn_snooze.setText("Wstrzymaj")
            self.btn_snooze.setStyleSheet(f"""
                QToolButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 6px; font-weight: bold; border: 1px solid {THEME['border']}; }}
                QToolButton:hover {{ background-color: {THEME['hover_card']}; }}
                QToolButton::menu-indicator {{ image: none; }}
            """)

        # Ładowanie z bazy
        rows = self.mgr.get_all_downloads()
        
        # Oczyść układ (bardzo proste odświeżanie, w przyszłości do zrobienia diff)
        while self.items_layout.count():
            i = self.items_layout.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
        self.item_widgets.clear()

        if not rows:
            lbl = QLabel("Brak zadań w kolejce. Kliknij prawym przyciskiem na utwór, aby pobrać teledysk.")
            lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px;")
            self.items_layout.addWidget(lbl)
            return

        total_bytes = 0

        for r in rows:
            # item_id, title, status, cover_id, resolution, file_size
            item_id = r[0]
            title = r[1]
            status = r[2]
            cover_id = r[3] if len(r) > 3 else None
            resolution = r[4] if len(r) > 4 else None
            file_size = r[5] if len(r) > 5 else None
            
            if status == "COMPLETED" and file_size:
                total_bytes += file_size
                
            w = DownloadItemWidget(item_id, title, status, cover_id, resolution, file_size)
            # Fallback: jeśli cover_id jest puste, użyj item_id
            # Navidrome getCoverArt akceptuje ID piosenki bezpośrednio
            art_id = cover_id if cover_id else item_id
            if art_id:
                url = self.main_window.client.get_cover_art_url(art_id)
                self.main_window.loader.load(url, w.img)
            w.btn_remove.clicked.connect(lambda ch, i_id=item_id: self.mgr.remove_download(i_id))
            self.items_layout.addWidget(w)
            self.item_widgets[item_id] = w
            
        if total_bytes > 0:
            if total_bytes > 1024 * 1024 * 1024:
                gb = total_bytes / (1024 * 1024 * 1024)
                self.total_size_lbl.setText(f"Zajęte miejsce: {gb:.2f} GB")
            else:
                mb = total_bytes / (1024 * 1024)
                self.total_size_lbl.setText(f"Zajęte miejsce: {mb:.1f} MB")
        else:
            self.total_size_lbl.setText("Zajęte miejsce: 0 MB")

    def _on_status_changed(self, item_id, status):
        if item_id in self.item_widgets:
            if status == "": # Oznacza usunięcie
                self.load()
            else:
                self.item_widgets[item_id].update_status(status)

    def _on_progress(self, item_id, pct):
        if item_id in self.item_widgets:
            self.item_widgets[item_id].update_progress(pct)
