import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QCheckBox, QGraphicsOpacityEffect, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen
import qtawesome as qta

from config import THEME, APP_CONFIG
from core.paths import PathsManager
from core.i18n import tr
from ui.widgets import SmoothScrollArea

def get_check_icon_path() -> str:
    cache_dir = PathsManager.get_cache_dir()
    p = cache_dir / "check_white.png"
    if not p.exists():
        pix = QPixmap(14, 14)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(2, 7, 5, 11)
        painter.drawLine(5, 11, 12, 3)
        painter.end()
        pix.save(str(p), "PNG")
    return str(p).replace("\\", "/")

class PlaylistSyncModal(QWidget):
    """
    Wewnętrzna nakładka modalna (In-App Modal Overlay) wyboru playlist
    do automatycznego pobierania offline (audio/wideo) w stylu Spotify Dark.
    """
    def __init__(self, main_window, playlists, media_type, on_saved=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.playlists = playlists
        self.media_type = media_type
        self.on_saved = on_saved
        self.checkboxes = {}

        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._init_ui()

        if self.main_window:
            self.main_window.installEventFilter(self)

    def _init_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setAlignment(Qt.AlignCenter)
        root_lay.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("ModalCard")
        self.card.setFixedSize(460, 540)
        self.card.setStyleSheet(f"""
            #ModalCard {{
                background-color: {THEME.get('bg_card', '#121212')};
                border: 1px solid {THEME.get('border', '#282828')};
                border-radius: 14px;
            }}
        """)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(24, 20, 24, 22)
        card_lay.setSpacing(14)

        header_lay = QHBoxLayout()
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(10)

        header_info = QVBoxLayout()
        header_info.setSpacing(6)

        type_text = tr("common.music_videos", "Teledyski") if self.media_type == "video" else tr("common.music", "Muzyka")
        base_title = tr("settings.offline.select_playlists_title", "Wybierz playlisty")
        lbl_title = QLabel(f"{base_title} — {type_text}")
        lbl_title.setStyleSheet(f"""
            font-size: 17px;
            font-weight: bold;
            color: {THEME.get('text_main', '#ffffff')};
            background: transparent;
        """)

        lbl_subtitle = QLabel(tr("settings.offline.sync_hint", "Zaznacz playlisty do automatycznego pobierania offline."))
        lbl_subtitle.setStyleSheet(f"""
            font-size: 12px;
            color: {THEME.get('text_muted', '#888888')};
            background: transparent;
        """)

        header_info.addWidget(lbl_title)
        header_info.addWidget(lbl_subtitle)
        header_lay.addLayout(header_info)
        header_lay.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {THEME.get('text_muted', '#888888')};
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {THEME.get('nav_bg', '#222222')};
                color: {THEME.get('text_main', '#ffffff')};
            }}
        """)
        btn_close.clicked.connect(self.close_modal)
        header_lay.addWidget(btn_close)

        card_lay.addLayout(header_lay)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {THEME.get('border', '#242424')}; max-height: 1px; margin: 2px 0px;")
        card_lay.addWidget(line)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.pl_list_layout = QVBoxLayout(self.scroll_content)
        self.pl_list_layout.setContentsMargins(0, 4, 0, 4)
        self.pl_list_layout.setSpacing(4)

        conf_key = "video_auto_dl_playlists" if self.media_type == "video" else "audio_auto_dl_playlists"
        current_selected = APP_CONFIG.get(conf_key, [])

        check_icon = get_check_icon_path()

        cb_style = f"""
            QCheckBox {{
                color: {THEME.get('text_main', '#ffffff')};
                spacing: 12px;
                font-size: 13px;
                font-weight: 500;
                padding: 10px 12px;
                border-radius: 6px;
                background: transparent;
            }}
            QCheckBox:hover {{
                background-color: {THEME.get('nav_bg', '#222222')};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {THEME.get('border', '#4a4a4a')};
                background-color: {THEME.get('bg_main', '#0a0a0a')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {THEME.get('nav_hover', '#666666')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME.get('accent', '#1db954')};
                border-color: {THEME.get('accent', '#1db954')};
                image: url("{check_icon}");
            }}
        """

        if not self.playlists:
            lbl_empty = QLabel(tr("playlists.empty", "Brak utworzonych playlist."))
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet(f"color: {THEME.get('text_muted', '#888888')}; font-size: 13px; margin-top: 30px; background: transparent;")
            self.pl_list_layout.addWidget(lbl_empty)
        else:
            fallback_unnamed = tr("playlists.unnamed", "Bez nazwy")
            for pl in self.playlists:
                pl_id = pl.get('id')
                pl_name = pl.get('name') or fallback_unnamed

                cb = QCheckBox(pl_name)
                cb.setStyleSheet(cb_style)
                cb.setCursor(Qt.PointingHandCursor)
                if pl_id in current_selected:
                    cb.setChecked(True)

                self.pl_list_layout.addWidget(cb)
                self.checkboxes[pl_id] = cb

            self.pl_list_layout.addStretch()

        self.scroll.setWidget(self.scroll_content)
        card_lay.addWidget(self.scroll)

        line_bot = QFrame()
        line_bot.setFrameShape(QFrame.HLine)
        line_bot.setStyleSheet(f"background-color: {THEME.get('border', '#242424')}; max-height: 1px; margin: 2px 0px;")
        card_lay.addWidget(line_bot)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(12)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(f"""
            color: {THEME.get('text_muted', '#888888')};
            background: transparent;
            font-size: 12px;
            font-weight: 500;
        """)
        self._update_counter()

        for cb in self.checkboxes.values():
            cb.toggled.connect(self._update_counter)

        btn_cancel = QPushButton(tr("dialogs.cancel", "Anuluj"))
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME.get('nav_bg', '#222222')};
                color: {THEME.get('text_main', '#ffffff')};
                padding: 0px 18px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {THEME.get('border', '#3a3a3a')};
            }}
            QPushButton:hover {{
                background-color: {THEME.get('nav_hover', '#383838')};
            }}
        """)
        btn_cancel.clicked.connect(self.close_modal)

        btn_save = QPushButton(tr("dialogs.save", "Zapisz"))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(36)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME.get('accent', '#1db954')};
                color: white;
                padding: 0px 22px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_save.clicked.connect(self._save_and_close)

        btn_row.addWidget(self.lbl_count)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)

        card_lay.addLayout(btn_row)
        root_lay.addWidget(self.card)

    def _update_counter(self):
        selected_cnt = sum(1 for cb in self.checkboxes.values() if cb.isChecked())
        total_cnt = len(self.checkboxes)
        msg = tr("dialogs.playlist_sync_counter", "Zaznaczono: {selected} z {total}").format(
            selected=selected_cnt, total=total_cnt
        )
        self.lbl_count.setText(msg)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 185))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if not self.card.geometry().contains(pos):
                self.close_modal()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_modal()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.main_window and event.type() == QEvent.Resize:
            self.resize(self.main_window.size())
        return super().eventFilter(obj, event)

    def show_modal(self):
        if self.main_window:
            self.resize(self.main_window.size())
        self.show()
        self.raise_()
        self.setFocus()

        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def close_modal(self):
        if self.main_window:
            try:
                self.main_window.removeEventFilter(self)
            except Exception:
                pass

        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._anim.setDuration(150)
        self._anim.setStartValue(self._opacity_effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self._cleanup)
        self._anim.start()

    def _cleanup(self):
        self.hide()
        self.deleteLater()

    def _save_and_close(self):
        selected_ids = [pid for pid, cb in self.checkboxes.items() if cb.isChecked()]
        if self.on_saved:
            self.on_saved(self.media_type, selected_ids)
        self.close_modal()