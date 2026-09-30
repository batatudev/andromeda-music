import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: ui/components/download_item.py
# OPIS ZMIAN: Wyświetlanie prędkości i rozmiaru na żywo w status_lbl oraz płynny pasek postępu

import qtawesome as qta
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar
from config import THEME
from ui.widgets import HoverIconButton, RoundedImage
from core.i18n import tr

class DownloadItemWidget(QFrame):
    """
    Wiersz reprezentujący pojedyncze zadanie w menedżerze pobierania.
    """
    def __init__(
        self,
        item_id,
        title,
        status,
        media_type,
        remove_cb,
        cover_id=None,
        resolution=None,
        file_size=None,
        parent=None
    ):
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("Card")
        self.setStyleSheet(f"#Card {{ background-color: {THEME['bg_card']}; border-radius: 8px; }}")
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        self.img = RoundedImage(size=50, radius=6)
        self.img.setFixedSize(50, 50)
        layout.addWidget(self.img)

        info_lay = QVBoxLayout()
        info_lay.setSpacing(3)
        info_lay.setContentsMargins(0, 0, 0, 0)

        icon_str = 'fa5s.music' if media_type == 'audio' else 'fa5s.film'
        icon_color = THEME['accent'] if media_type == 'audio' else '#e74c3c'

        title_lay = QHBoxLayout()
        title_lay.setContentsMargins(0, 0, 0, 0)
        title_lay.setSpacing(5)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_str, color=icon_color).pixmap(12, 12))

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {THEME['text_main']}; background: transparent;"
        )

        title_lay.addWidget(icon_lbl)
        title_lay.addWidget(self.title_lbl)
        title_lay.addStretch()

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

        self.progress = QProgressBar()
        self.progress.setFixedWidth(160)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background-color: {THEME['nav_bg']}; border-radius: 4px; border: none; }}
            QProgressBar::chunk {{ background-color: {THEME['accent']}; border-radius: 4px; }}
        """)
        self.progress.setVisible(status == "DOWNLOADING")
        layout.addWidget(self.progress)

        self.btn_remove = HoverIconButton('fa5s.times', icon_size=14)
        self.btn_remove.setFixedSize(32, 32)
        self.btn_remove.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 16px; }} "
            f"QPushButton:hover {{ background: {THEME['btn_remove_hover']}; }}"
        )
        self.btn_remove.setToolTip(tr("dialogs.delete", "Usuń"))
        self.btn_remove.clicked.connect(remove_cb)
        layout.addWidget(self.btn_remove)

    def _translate_status(self, st):
        trans = {
            "QUEUED": tr("downloads.status_queued", "Oczekuje w kolejce"),
            "DOWNLOADING": tr("downloads.status_downloading", "Pobieranie..."),
            "COMPLETED": tr("downloads.status_completed", "Pobrano"),
            "ERROR": tr("downloads.status_error", "Błąd"),
            "PAUSED": tr("downloads.status_paused", "Wstrzymano")
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
        if file_size is not None:
            self.file_size = file_size
        if resolution is not None:
            self.resolution = resolution
        self.status_lbl.setText(self._build_status_text())
        is_dl = (new_status == "DOWNLOADING")
        self.progress.setVisible(is_dl)
        if not is_dl:
            self.progress.setValue(0)

    def update_progress(self, pct, stats_str=None):
        if not self.progress.isVisible():
            self.progress.setVisible(True)
        self.progress.setValue(int(pct))

        dl_txt = tr("downloads.status_downloading", "Pobieranie...")
        if stats_str:
            pct_part = f" ({int(pct)}%)" if pct > 0 else ""
            self.status_lbl.setText(f"{dl_txt} • {stats_str}{pct_part}")
        else:
            self.status_lbl.setText(f"{dl_txt} • {int(pct)}%")