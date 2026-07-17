# WERSJA PROJEKTU: 14.12
# MODYFIKOWANY PLIK: views/view_downloads.py
# OPIS ZMIAN: Stworzono nowy widok dla Menadżera Pobrań Wideo Offline.

import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QProgressBar
)
from PySide6.QtCore import Qt
from config import THEME
from ui.widgets import HoverIconButton

class DownloadItemWidget(QFrame):
    def __init__(self, item_id, title, status, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("Card")
        self.setStyleSheet(f"#Card {{ background-color: {THEME['bg_card']}; border-radius: 8px; }}")
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        # Info
        info_lay = QVBoxLayout()
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {THEME['text_main']}; background: transparent;")
        
        self.status_lbl = QLabel(self._translate_status(status))
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {THEME['text_muted']}; background: transparent;")
        
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

    def update_status(self, new_status):
        self.status_lbl.setText(self._translate_status(new_status))
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

        # Nagłówek
        header_lay = QHBoxLayout()
        title = QLabel("Menadżer Pobrań (Offline)")
        title.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {THEME['text_main']};")
        header_lay.addWidget(title)
        header_lay.addStretch()

        # Kontrolki
        self.btn_snooze = QPushButton("Wstrzymaj na 2h")
        self.btn_snooze.setCursor(Qt.PointingHandCursor)
        self.btn_snooze.setStyleSheet(f"""
            QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 10px 20px; border-radius: 8px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {THEME['hover_card']}; }}
        """)
        self.btn_snooze.clicked.connect(self._toggle_snooze)
        header_lay.addWidget(self.btn_snooze)
        
        layout.addLayout(header_lay)

        # Kontener na listę
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(10)
        self.items_layout.setAlignment(Qt.AlignTop)
        layout.addLayout(self.items_layout)
        layout.addStretch()

        self.item_widgets = {}

        # Podpięcie sygnałów z Menedżera
        self.mgr.queue_updated.connect(self.load)
        self.mgr.download_status_changed.connect(self._on_status_changed)
        self.mgr.download_progress.connect(self._on_progress)

    def load(self, *args, **kwargs):
        # Aktualizacja przycisku snooze
        if self.mgr.is_snoozed:
            self.btn_snooze.setText("Wznów pobieranie")
            self.btn_snooze.setStyleSheet(f"""
                QPushButton {{ background-color: {THEME['accent']}; color: {THEME['bg_main']}; padding: 10px 20px; border-radius: 8px; font-weight: bold; }}
                QPushButton:hover {{ opacity: 0.8; }}
            """)
        else:
            self.btn_snooze.setText("Wstrzymaj na 2h")
            self.btn_snooze.setStyleSheet(f"""
                QPushButton {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; padding: 10px 20px; border-radius: 8px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {THEME['hover_card']}; }}
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

        for r in rows:
            item_id, title, status = r
            w = DownloadItemWidget(item_id, title, status)
            w.btn_remove.clicked.connect(lambda ch, i_id=item_id: self.mgr.remove_download(i_id))
            self.items_layout.addWidget(w)
            self.item_widgets[item_id] = w

    def _toggle_snooze(self):
        if self.mgr.is_snoozed:
            self.mgr.set_snooze(0) # Wznów
        else:
            self.mgr.set_snooze(2) # Uśpij na 2h

    def _on_status_changed(self, item_id, status):
        if item_id in self.item_widgets:
            if status == "": # Oznacza usunięcie
                self.load()
            else:
                self.item_widgets[item_id].update_status(status)

    def _on_progress(self, item_id, pct):
        if item_id in self.item_widgets:
            self.item_widgets[item_id].update_progress(pct)
