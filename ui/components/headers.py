# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: ui/components/headers.py
# OPIS ZMIAN: Wyodrębnienie MediaHeader i QueueHeader z ui_cards.py.

import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QGraphicsBlurEffect
)
from PySide6.QtCore import Qt, Signal

from config import THEME
from ui.widgets import RoundedImage

class MediaHeader(QFrame):
    play_clicked = Signal()
    def __init__(self, title, stats_text):
        super().__init__()
        self.setFixedHeight(280)
        self.setObjectName("MediaHeader")

        self.bg_label = QLabel(self)
        self.bg_label.setScaledContents(True)
        self.blur = QGraphicsBlurEffect()
        self.blur.setBlurRadius(60)
        self.bg_label.setGraphicsEffect(self.blur)

        self.overlay = QLabel(self)
        self.overlay.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba({THEME['bg_main_rgb']},100), stop:0.5 rgba({THEME['bg_main_rgb']},180), stop:1 {THEME['bg_main']});")

        l = QHBoxLayout(self)
        l.setContentsMargins(35, 35, 35, 35)
        l.setSpacing(30)

        self.img = RoundedImage(size=200, radius=10)
        l.addWidget(self.img)

        v = QVBoxLayout()
        v.addStretch()

        self.title_lbl = QLabel(title)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setMinimumHeight(70)
        self.title_lbl.setStyleSheet(f"font-size: 48px; font-weight: bold; color: {THEME['text_main']}; background: transparent; margin-bottom: 5px;")

        bl = QHBoxLayout()
        bl.setSpacing(15)
        bl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        bs = f"QPushButton {{ background: {THEME['play_bg']}; color: {THEME['play_color']}; font-weight: bold; padding: 10px 25px; border-radius: 22px; font-size: 15px; border: none; }} QPushButton:hover {{ background: {THEME['accent']}; color: white; }}"

        self.btn_play = QPushButton(qta.icon('fa5s.play', color=THEME['play_color']), " Odtwarzaj")
        self.btn_play.setStyleSheet(bs)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.play_clicked.emit)

        self.stats_lbl = QLabel(stats_text)
        self.stats_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 14px; background: transparent; margin-left: 10px;")

        bl.addWidget(self.btn_play)
        bl.addWidget(self.stats_lbl)
        bl.addStretch()

        v.addWidget(self.title_lbl)
        v.addSpacing(10)
        v_layout = v
        v_layout.addLayout(bl)
        v_layout.addStretch()

        l.addLayout(v_layout)
        l.addStretch()

    def resizeEvent(self, e):
        self.bg_label.resize(self.size())
        self.overlay.resize(self.size())
        super().resizeEvent(e)

    def set_image(self, p, animate=True):
        self.img.set_image(p, animate)
        if p and not p.isNull():
            self.bg_label.setPixmap(p)

class QueueHeader(QFrame):
    play_clicked = Signal()
    shuffle_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self, title, subtitle):
        super().__init__()
        self.setFixedHeight(290)
        self.setObjectName("QueueHeader")

        self.bg_label = QLabel(self)
        self.bg_label.setScaledContents(True)
        self.blur = QGraphicsBlurEffect()
        self.blur.setBlurRadius(60)
        self.bg_label.setGraphicsEffect(self.blur)

        self.overlay = QLabel(self)
        self.overlay.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba({THEME['bg_main_rgb']},100), stop:0.5 rgba({THEME['bg_main_rgb']},180), stop:1 {THEME['bg_main']}); border-radius: 15px;")

        l = QHBoxLayout(self)
        l.setContentsMargins(35, 35, 35, 35)
        l.setSpacing(30)

        self.img = RoundedImage(size=200, radius=10)
        l.addWidget(self.img)

        v = QVBoxLayout()
        v.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['accent']}; letter-spacing: 2px; background: transparent;")

        self.title_lbl = QLabel(title)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setMinimumHeight(75)
        self.title_lbl.setStyleSheet(f"font-size: 48px; font-weight: bold; color: {THEME['text_main']}; background: transparent; margin-bottom: 10px;")

        bl = QHBoxLayout()
        bl.setSpacing(15)
        bl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        bs_play = f"QPushButton {{ background: {THEME['play_bg']}; color: {THEME['play_color']}; font-weight: bold; padding: 10px 25px; border-radius: 22px; font-size: 15px; border: none; }} QPushButton:hover {{ background: {THEME['accent']}; color: white; }} QPushButton:disabled {{ background: {THEME['btn_hover_bg']}; color: {THEME['text_muted']}; }}"
        bs_other = f"QPushButton {{ background: {THEME['btn_hover_bg']}; color: {THEME['text_main']}; font-weight: bold; padding: 10px 20px; border-radius: 22px; font-size: 14px; border: none; }} QPushButton:hover {{ background: {THEME['border']}; }} QPushButton:disabled {{ color: {THEME['text_muted']}; }}"

        self.btn_play = QPushButton(qta.icon('fa5s.play', color=THEME["play_color"]), " Odtwarzaj")
        self.btn_play.setStyleSheet(bs_play)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setFixedHeight(44)
        self.btn_play.clicked.connect(self.play_clicked.emit)

        self.btn_shuffle = QPushButton(qta.icon('fa5s.random', color=THEME["text_main"]), " Losuj")
        self.btn_shuffle.setStyleSheet(bs_other)
        self.btn_shuffle.setCursor(Qt.PointingHandCursor)
        self.btn_shuffle.setFixedHeight(44)
        self.btn_shuffle.clicked.connect(self.shuffle_clicked.emit)

        self.btn_clear = QPushButton(qta.icon('fa5s.trash-alt', color=THEME["text_main"]), " Wyczyść")
        self.btn_clear.setStyleSheet(bs_other)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setFixedHeight(44)
        self.btn_clear.clicked.connect(self.clear_clicked.emit)

        bl.addWidget(self.btn_play)
        bl.addWidget(self.btn_shuffle)
        bl.addWidget(self.btn_clear)
        bl.addStretch()

        v.addWidget(self.sub_lbl)
        v.addWidget(self.title_lbl)
        v.addSpacing(15)
        v.addLayout(bl)

        l.addLayout(v)
        l.addStretch()

    def set_empty_state(self, is_empty):
        if is_empty:
            self.title_lbl.setText("Twoja kolejka jest pusta")
            self.sub_lbl.setText("KOLEJKA ODTWARZANIA")
            self.bg_label.clear()
            self.overlay.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 {THEME['bg_main']}); border-radius: 15px;")
            self.btn_play.setEnabled(False)
            self.btn_play.setIcon(qta.icon('fa5s.play', color=THEME['text_muted']))
            self.btn_shuffle.setEnabled(False)
            self.btn_shuffle.setIcon(qta.icon('fa5s.random', color=THEME['text_muted']))
            self.btn_clear.setEnabled(False)
            self.btn_clear.setIcon(qta.icon('fa5s.trash-alt', color=THEME['text_muted']))
            self.img.set_image(None, animate=False)
        else:
            self.btn_play.setEnabled(True)
            self.btn_play.setIcon(qta.icon('fa5s.play', color=THEME['play_color']))
            self.btn_shuffle.setEnabled(True)
            self.btn_shuffle.setIcon(qta.icon('fa5s.random', color=THEME['text_main']))
            self.btn_clear.setEnabled(True)
            self.btn_clear.setIcon(qta.icon('fa5s.trash-alt', color=THEME['text_main']))
            self.overlay.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba({THEME['bg_main_rgb']},100), stop:0.5 rgba({THEME['bg_main_rgb']},180), stop:1 {THEME['bg_main']}); border-radius: 15px;")

    def resizeEvent(self, e):
        self.bg_label.resize(self.size())
        self.overlay.resize(self.size())
        super().resizeEvent(e)

    def set_image(self, p, animate=True):
        self.img.set_image(p, animate)
        if p and not p.isNull():
            self.bg_label.setPixmap(p)
