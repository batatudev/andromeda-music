import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize

from config import THEME
from ui.widgets import RoundedImage
from core.i18n import tr

class HeroSection(QFrame):
    play_clicked = Signal(object)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(240)
        self.setObjectName("HeroSection")

        self.bg_label = QLabel(self)
        self.bg_label.setScaledContents(True)

        self.overlay = QLabel(self)
        self.overlay.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 rgba({THEME['bg_main_rgb']},100), "
            f"stop:0.5 rgba({THEME['bg_main_rgb']},180), "
            f"stop:1 {THEME['bg_main']});"
        )

        l = QHBoxLayout(self)
        l.setContentsMargins(35, 35, 35, 35)
        l.setSpacing(40)

        self.img_container = QWidget()
        self.img_container.setFixedSize(170, 170)
        self.img_container.setStyleSheet("background: transparent;")

        self.img = RoundedImage(size=170, radius=10)
        self.img.setParent(self.img_container)
        self.img.move(0, 0)

        self.cover_overlay = QFrame(self.img_container)
        self.cover_overlay.setFixedSize(170, 170)
        self.cover_overlay.setStyleSheet(
            "border-radius: 10px; background-color: rgba(0,0,0,0.55); border: none;"
        )
        self.cover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.cover_overlay.hide()

        self.play_btn = QPushButton(qta.icon('fa5s.play', color=THEME["play_color"]), "", self.img_container)
        self.play_btn.setFixedSize(46, 46)
        self.play_btn.setIconSize(QSize(20, 20))
        self.play_btn.setStyleSheet(
            f"QPushButton {{ background-color: {THEME['play_bg']}; border-radius: 23px; border: none; }} "
            f"QPushButton:hover {{ background-color: {THEME['accent']}; }}"
        )
        self.play_btn.move(62, 62)
        self.play_btn.hide()
        self.play_btn.clicked.connect(self._on_play_btn_clicked)

        l.addWidget(self.img_container)

        vt = QVBoxLayout()
        vt.setSpacing(8)
        vt.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.hs = QLabel(tr("menu.favs", "Ulubione").upper())
        self.hs.setObjectName("HeroSubtitle")
        self.ht = QLabel("Andromeda Music")
        self.ht.setObjectName("HeroTitle")
        self.ht.setWordWrap(True)
        self.ht.setMinimumHeight(55)
        self.ht.setStyleSheet(
            f"font-size: 42px; font-weight: bold; background: transparent; "
            f"color: {THEME['text_main']}; margin-bottom: 5px;"
        )

        vt.addWidget(self.hs)
        vt.addWidget(self.ht)

        l.addLayout(vt)
        l.addStretch()

        self.song_data = None
        self.setCursor(Qt.PointingHandCursor)

    def _on_play_btn_clicked(self):
        if self.song_data:
            self.play_clicked.emit(self.song_data)

    def enterEvent(self, e):
        self.cover_overlay.show()
        self.play_btn.show()
        self.play_btn.raise_()
        self.img.set_hover(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.cover_overlay.hide()
        self.play_btn.hide()
        self.img.set_hover(False)
        super().leaveEvent(e)

    def resizeEvent(self, e):
        self.bg_label.resize(self.size())
        self.overlay.resize(self.size())
        super().resizeEvent(e)

    def set_image(self, p, animate=True):
        self.img.set_image(p, animate)
        if p and not p.isNull():
            from utils import get_blurred_pixmap
            blurred = get_blurred_pixmap(p, 60)
            self.bg_label.setPixmap(blurred)

    def set_data(self, subtitle, title, song_data):
        self.hs.setText(subtitle)
        self.ht.setText(title)
        self.song_data = song_data

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.song_data:
            self.play_clicked.emit(self.song_data)