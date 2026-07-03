# WERSJA PROJEKTU: 14.11
# MODYFIKOWANY PLIK: view_sidebar.py
# OPIS ZMIAN: Zastąpienie QScrollArea przez SmoothScrollArea dla playlist (płynne przewijanie).

import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, Property

from config import THEME, Pages
from ui.widgets import HoverIconButton, SmoothScrollArea

class SidebarWidget(QFrame):
    page_requested = Signal(int)
    back_requested = Signal()
    refresh_requested = Signal()
    toggle_sidebar_requested = Signal()
    playlist_requested = Signal(str, str)
    settings_requested = Signal()
    dev_requested = Signal()

    def __init__(self, dev_mode=False):
        super().__init__()
        self.setObjectName("Sidebar")
        self._current_width = 200
        self.setFixedWidth(self._current_width)
        self.nav_btns = {}
        self.is_collapsed = False
        
        self.anim = QPropertyAnimation(self, b"sidebarWidth")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.finished.connect(self._on_anim_finished)
        
        side_l = QVBoxLayout(self)
        side_l.setContentsMargins(0, 10, 0, 0)
        side_l.setSpacing(5)

        top = QWidget()
        top.setFixedHeight(60)
        nav_lay = QHBoxLayout(top)
        nav_lay.setContentsMargins(15, 10, 15, 10)
        nav_lay.setSpacing(5)

        self.btn_toggle_side = QPushButton()
        self.btn_toggle_side.setIcon(qta.icon('fa5s.bars', color=THEME["text_muted"]))
        self.btn_toggle_side.setIconSize(QSize(16, 16))
        self.btn_toggle_side.setObjectName("NavBtn")
        self.btn_toggle_side.setFixedSize(36, 36)
        self.btn_toggle_side.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_side.clicked.connect(self.toggle_sidebar_requested.emit)

        self.btn_back = QPushButton()
        self.btn_back.setIcon(qta.icon('fa5s.arrow-left', color=THEME["text_muted"]))
        self.btn_back.setIconSize(QSize(16, 16))
        self.btn_back.setObjectName("NavBtn")
        self.btn_back.setFixedSize(36, 36)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.back_requested.emit)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color=THEME["text_muted"]))
        self.btn_refresh.setIconSize(QSize(16, 16))
        self.btn_refresh.setObjectName("NavBtn")
        self.btn_refresh.setFixedSize(36, 36)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)

        nav_lay.addWidget(self.btn_toggle_side)
        nav_lay.addWidget(self.btn_back)
        nav_lay.addWidget(self.btn_refresh)
        nav_lay.addStretch()
        side_l.addWidget(top)

        items =[
            ("Główna", 'fa5s.home', Pages.HOME),
            ("Szukaj", 'fa5s.search', Pages.SEARCH),
            ("Utwory", 'fa5s.music', Pages.TRACKS),
            ("Albumy", 'fa5s.compact-disc', Pages.ALBUMS),
            ("Artyści", 'fa5s.users', Pages.ARTISTS),
            ("Ulubione", 'fa5s.heart', Pages.FAVS)
        ]

        for name, icon, idx in items:
            btn = HoverIconButton(icon, hover_color=THEME["text_main"])
            btn.setText(f"  {name}")
            btn.setProperty("isMenu", "true")
            btn.clicked.connect(lambda ch, i=idx: self.page_requested.emit(i))
            side_l.addWidget(btn)
            self.nav_btns[idx] = btn

        self.lbl_pl = QLabel("  PLAYLISTY")
        self.lbl_pl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-top: 15px; margin-bottom: 5px; background: transparent;")
        side_l.addWidget(self.lbl_pl)

        self.playlist_scroll = SmoothScrollArea()
        self.playlist_scroll.setWidgetResizable(True)
        self.playlist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.playlist_scroll.setStyleSheet("background: transparent; border: none;")
        self.playlist_content = QWidget()
        self.playlist_content.setStyleSheet("background: transparent;")
        self.playlist_layout = QVBoxLayout(self.playlist_content)
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_layout.setSpacing(2)
        self.playlist_layout.setAlignment(Qt.AlignTop)
        self.playlist_scroll.setWidget(self.playlist_content)
        side_l.addWidget(self.playlist_scroll)

        self.btn_dev = HoverIconButton('fa5s.code', hover_color=THEME["text_main"])
        self.btn_dev.setText("  Dev mode")
        self.btn_dev.setProperty("isMenu", "true")
        self.btn_dev.clicked.connect(self.dev_requested.emit)
        self.btn_dev.setVisible(dev_mode)
        side_l.addWidget(self.btn_dev)

        self.btn_settings = HoverIconButton('fa5s.cog', hover_color=THEME["text_main"])
        self.btn_settings.setText("  Ustawienia")
        self.btn_settings.setProperty("isMenu", "true")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        side_l.addWidget(self.btn_settings)

    @Property(int)
    def sidebarWidth(self):
        return self._current_width

    @sidebarWidth.setter
    def sidebarWidth(self, val):
        self._current_width = val
        self.setFixedWidth(val)

    def set_playlists(self, data):
        while self.playlist_layout.count():
            i = self.playlist_layout.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
        
        if not data:
            return
        
        for pl in data:
            pl_name = pl.get('name')
            pl_id = pl.get('id')
            btn = HoverIconButton('fa5s.list', hover_color=THEME["text_main"])
            btn.setText(f"  {pl_name}")
            btn.setProperty("isMenu", "true")
            btn.setProperty("pl_name", pl_name)
            btn.setProperty("pl_id", pl_id)

            if self.is_collapsed:
                btn.setText("")
                btn.setToolTip(pl_name)

            btn_style = f"QPushButton {{ background-color: transparent; border: none; text-align: left; padding: 12px 15px; font-size: 13px; border-radius: 6px; color: {THEME['text_muted']}; margin: 2px 10px; }} QPushButton:hover {{ color: {THEME['text_main']}; background-color: {THEME['bg_card']}; }} QPushButton[active=\"true\"] {{ background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; font-weight: bold; }}"
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda ch, pid=pl_id, pname=pl_name: self.playlist_requested.emit(pid, pname))
            self.playlist_layout.addWidget(btn)

    def set_collapsed(self, collapsed):
        if self.is_collapsed == collapsed:
            return
        
        self.is_collapsed = collapsed
        self.anim.stop()
        
        if collapsed:
            self._update_text_visibility(show_text=False)
            self.anim.setStartValue(self.width())
            self.anim.setEndValue(70)
        else:
            self.anim.setStartValue(self.width())
            self.anim.setEndValue(200)
            
        self.anim.start()

    def _on_anim_finished(self):
        if not self.is_collapsed:
            self._update_text_visibility(show_text=True)

    def _update_text_visibility(self, show_text):
        if not show_text:
            self.btn_back.hide()
            self.btn_refresh.hide()
            self.lbl_pl.hide()
            self.btn_settings.setText("")
            self.btn_settings.setToolTip("Ustawienia")
            self.btn_dev.setText("")
            self.btn_dev.setToolTip("Dev mode")
            for btn in self.nav_btns.values():
                btn.setToolTip(btn.text().strip())
                btn.setText("")
            for i in range(self.playlist_layout.count()):
                w = self.playlist_layout.itemAt(i).widget()
                if w:
                    w.setToolTip(w.property("pl_name") or "")
                    w.setText("")
        else:
            self.btn_back.show()
            self.btn_refresh.show()
            self.lbl_pl.show()
            self.btn_settings.setText("  Ustawienia")
            self.btn_settings.setToolTip("")
            self.btn_dev.setText("  Dev mode")
            self.btn_dev.setToolTip("")
            names = {Pages.HOME: "Główna", Pages.SEARCH: "Szukaj", Pages.TRACKS: "Utwory", Pages.ALBUMS: "Albumy", Pages.ARTISTS: "Artyści", Pages.FAVS: "Ulubione"}
            for idx, btn in self.nav_btns.items():
                btn.setText(f"  {names.get(idx, '')}")
            for i in range(self.playlist_layout.count()):
                w = self.playlist_layout.itemAt(i).widget()
                if w and w.property("pl_name"):
                    w.setText(f"  {w.property('pl_name')}")

    def update_active_state(self, active_idx, active_playlist_id):
        for i, b in self.nav_btns.items():
            is_active = (i == active_idx)
            b.setProperty("active", str(is_active).lower())
            b.style().polish(b)
            if hasattr(b, 'set_default_color'):
                b.set_default_color(THEME["accent"] if is_active else THEME["text_muted"])

        is_settings_active = (active_idx == Pages.SETTINGS)
        self.btn_settings.setProperty("active", str(is_settings_active).lower())
        self.btn_settings.style().polish(self.btn_settings)
        if hasattr(self.btn_settings, 'set_default_color'):
            self.btn_settings.set_default_color(THEME["accent"] if is_settings_active else THEME["text_muted"])

        is_dev_active = (active_idx == Pages.DEV_MODE)
        self.btn_dev.setProperty("active", str(is_dev_active).lower())
        self.btn_dev.style().polish(self.btn_dev)
        if hasattr(self.btn_dev, 'set_default_color'):
            self.btn_dev.set_default_color(THEME["accent"] if is_dev_active else THEME["text_muted"])

        for i in range(self.playlist_layout.count()):
            w = self.playlist_layout.itemAt(i).widget()
            if w:
                p_id = w.property("pl_id")
                is_pl_active = (p_id == active_playlist_id) if active_playlist_id else False
                w.setProperty("active", str(is_pl_active).lower())
                w.style().polish(w)
                if hasattr(w, 'set_default_color'):
                    w.set_default_color(THEME["accent"] if is_pl_active else THEME["text_muted"])