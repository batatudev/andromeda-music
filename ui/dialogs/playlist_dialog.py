import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
    QScrollArea, QGraphicsOpacityEffect, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPainter, QColor
import qtawesome as qta

from config import THEME, APP_CONFIG
from core.i18n import tr
from ui.widgets import SmoothScrollArea

class PlaylistDialog(QWidget):
    """
    Wewnętrzna nakładka modalna (In-App Modal Overlay) w stylu Spotify Dark.
    Renderuje się bezpośrednio wewnątrz geometrii MainWindow bez tworzenia
    osobnego okna systemowego (brak paska tytułowego i obramowań KDE/Wayland).
    """
    def __init__(self, parent, client, song, video_download_manager, on_playlists_changed=None):
        super().__init__(parent)
        self.main_window = parent
        self.client = client
        self.song = song
        self.v_mgr = video_download_manager
        self.on_playlists_changed = on_playlists_changed

        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._init_ui()

        if self.main_window:
            self.main_window.installEventFilter(self)

        self._fetch_playlists()

    def _init_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setAlignment(Qt.AlignCenter)
        root_lay.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("ModalCard")
        self.card.setFixedSize(440, 520)
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
        header_info.setSpacing(2)

        lbl_title = QLabel(tr("dialogs.playlist_add_title", "Dodaj do playlisty"))
        lbl_title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {THEME.get('text_main', '#ffffff')};
            background: transparent;
        """)

        song_title = getattr(self.song, 'title', '')
        song_artist = getattr(self.song, 'artist', '')
        lbl_subtitle = QLabel(f"{song_title} • {song_artist}")
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

        new_pl_layout = QHBoxLayout()
        new_pl_layout.setContentsMargins(0, 4, 0, 0)
        new_pl_layout.setSpacing(8)

        self.inp_new_pl = QLineEdit()
        self.inp_new_pl.setPlaceholderText(tr("dialogs.playlist_new_placeholder", "Nowa playlista..."))
        self.inp_new_pl.setStyleSheet(f"""
            QLineEdit {{
                background: {THEME.get('bg_main', '#0a0a0a')};
                color: {THEME.get('text_main', '#ffffff')};
                padding: 8px 12px;
                border: 1px solid {THEME.get('border', '#282828')};
                border-radius: 6px;
                font-size: 13px;
                height: 20px;
            }}
            QLineEdit:focus {{
                border: 1px solid {THEME.get('accent', '#1db954')};
            }}
        """)
        self.inp_new_pl.returnPressed.connect(self._create_playlist)

        btn_new_pl = QPushButton(tr("dialogs.create", "Utwórz"))
        btn_new_pl.setCursor(Qt.PointingHandCursor)
        btn_new_pl.setFixedHeight(38)
        btn_new_pl.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME.get('accent', '#1db954')};
                color: white;
                padding: 0px 18px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_new_pl.clicked.connect(self._create_playlist)

        new_pl_layout.addWidget(self.inp_new_pl)
        new_pl_layout.addWidget(btn_new_pl)
        card_lay.addLayout(new_pl_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {THEME.get('border', '#242424')}; max-height: 1px; margin: 4px 0px;")
        card_lay.addWidget(line)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.pl_list_layout = QVBoxLayout(self.scroll_content)
        self.pl_list_layout.setContentsMargins(0, 0, 0, 0)
        self.pl_list_layout.setSpacing(6)

        lbl_loading = QLabel(tr("common.loading", "Wczytywanie playlist..."))
        lbl_loading.setAlignment(Qt.AlignCenter)
        lbl_loading.setStyleSheet(f"color: {THEME.get('text_muted', '#888888')}; font-size: 13px; margin-top: 30px;")
        self.pl_list_layout.addWidget(lbl_loading)

        self.scroll.setWidget(self.scroll_content)
        card_lay.addWidget(self.scroll)

        root_lay.addWidget(self.card)

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

    def exec(self):
        """Zgodność wsteczna z wywołaniami .exec()."""
        self.show_modal()

    def show_modal(self):
        if self.main_window:
            self.resize(self.main_window.size())
        self.show()
        self.raise_()
        self.setFocus()
        self.inp_new_pl.setFocus()

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

    def _fetch_playlists(self):
        def task():
            params = self.client._get_auth_params()
            res = self.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            while self.pl_list_layout.count():
                item = self.pl_list_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()

            if not playlists:
                lbl_empty = QLabel(tr("playlists.empty", "Brak utworzonych playlist."))
                lbl_empty.setAlignment(Qt.AlignCenter)
                lbl_empty.setStyleSheet(f"color: {THEME.get('text_muted', '#888888')}; font-size: 13px; margin-top: 30px;")
                self.pl_list_layout.addWidget(lbl_empty)
                return

            for pl in playlists:
                pl_name = pl.get('name', 'Bez nazwy')
                pl_id = pl.get('id')

                btn = QPushButton()
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFixedHeight(44)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        padding: 0px 14px;
                        border-radius: 8px;
                        background: {THEME.get('bg_card', '#111111')};
                        color: {THEME.get('text_main', '#ffffff')};
                        border: 1px solid {THEME.get('border', '#222222')};
                    }}
                    QPushButton:hover {{
                        background-color: {THEME.get('nav_bg', '#222222')};
                        border-color: {THEME.get('nav_hover', '#383838')};
                    }}
                """)

                btn_lay = QHBoxLayout(btn)
                btn_lay.setContentsMargins(12, 0, 12, 0)
                btn_lay.setSpacing(12)

                icon_lbl = QLabel()
                icon_lbl.setPixmap(qta.icon('fa5s.list', color=THEME.get('accent', '#1db954')).pixmap(14, 14))
                icon_lbl.setStyleSheet("background: transparent; border: none;")

                name_lbl = QLabel(pl_name)
                name_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {THEME.get('text_main', '#ffffff')}; background: transparent; border: none;")

                btn_lay.addWidget(icon_lbl)
                btn_lay.addWidget(name_lbl)
                btn_lay.addStretch()

                btn.clicked.connect(lambda ch=False, pid=pl_id, name=pl_name: self._select_playlist(pid, name))
                self.pl_list_layout.addWidget(btn)

            self.pl_list_layout.addStretch()

        if hasattr(self.main_window, 'run_async'):
            self.main_window.run_async(task, on_ready, page_bound=False)

    def _create_playlist(self):
        name = self.inp_new_pl.text().strip()
        if not name:
            return
        self.close_modal()

        def task():
            p = self.client._get_auth_params()
            p['name'] = name
            p['songId'] = [self.song.item_id]
            self.client._make_request("createPlaylist", p)

            if APP_CONFIG.get("video_auto_dl_playlists", False):
                link = getattr(self.song, 'yt_link', None) or getattr(self.song, 'youtube_url', None)
                if link and self.v_mgr:
                    self.v_mgr.add_to_queue(
                        self.song.item_id, link, self.song.title,
                        high_priority=False, cover_id=self.song.cover_id
                    )

        def on_ready(_):
            if self.on_playlists_changed:
                self.on_playlists_changed()
            if hasattr(self.main_window, 'show_toast'):
                self.main_window.show_toast(
                    f"Utworzono playlistę \"{name}\" i dodano utwór.",
                    title="Playlista",
                    icon_str="fa5s.check-circle",
                    icon_color=THEME.get("accent", "#1db954")
                )

        if hasattr(self.main_window, 'run_async'):
            self.main_window.run_async(task, on_ready, page_bound=False)

    def _select_playlist(self, pid, pl_name):
        self.close_modal()

        def task():
            self.client.update_playlist(pid, song_id_to_add=self.song.item_id)
            if APP_CONFIG.get("video_auto_dl_playlists", False):
                link = getattr(self.song, 'yt_link', None) or getattr(self.song, 'youtube_url', None)
                if link and self.v_mgr:
                    self.v_mgr.add_to_queue(
                        self.song.item_id, link, self.song.title,
                        high_priority=False, cover_id=self.song.cover_id
                    )

        def on_ready(_):
            if hasattr(self.main_window, 'show_toast'):
                self.main_window.show_toast(
                    f"Dodano \"{self.song.title}\" do playlisty \"{pl_name}\".",
                    title="Playlista",
                    icon_str="fa5s.check-circle",
                    icon_color=THEME.get("accent", "#1db954")
                )

        if hasattr(self.main_window, 'run_async'):
            self.main_window.run_async(task, on_ready, page_bound=False)