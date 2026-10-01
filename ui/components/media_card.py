import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFrame, QMenu
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction

from config import THEME
from ui.widgets import RoundedImage, ClickableElidedLabel, ElidedLabel, get_cached_icon
from core.enums import MediaType
from core.i18n import tr

class MediaCard(QFrame):
    clicked = Signal(object, str)
    play_clicked = Signal(object, str)
    add_to_queue_clicked = Signal(object, str)
    artist_clicked = Signal(object, str)
    set_custom_image_clicked = Signal(object, str)
    reset_custom_image_clicked = Signal(object, str)
    set_custom_cover_clicked = Signal(object, str)
    reset_custom_cover_clicked = Signal(object, str)
    save_image_clicked = Signal(object, str)
    download_videos_clicked = Signal(object, str)

    def __init__(self, data, type_str, parent=None):
        super().__init__(parent)
        self.data = data
        self.type_str = type_str

        if type_str == MediaType.ARTIST:
            self.setObjectName("ArtistCard")
        else:
            self.setObjectName("Card")

        self.setProperty("mediaType", "artist" if type_str == MediaType.ARTIST else "album")
        self.setMinimumSize(160, 240)
        self.setMaximumSize(300, 400)
        self.setCursor(Qt.PointingHandCursor)

        self.radius = 95 if type_str == MediaType.ARTIST else 12
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        self.img_container = QWidget(self)
        self.img_container.setObjectName("CardImgContainer")

        self.img = RoundedImage(size=None, radius=self.radius)
        self.img.setParent(self.img_container)

        self.overlay = QFrame(self.img_container)
        if type_str == MediaType.ARTIST:
            self.overlay.setObjectName("CardOverlayArtist")
        else:
            self.overlay.setObjectName("CardOverlay")

        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.hide()

        self.play_btn = QPushButton(
            get_cached_icon('fa5s.play', color=THEME["play_color"]), "", self.img_container
        )
        self.play_btn.setObjectName("CardPlayBtn")
        self.play_btn.setFixedSize(46, 46)
        self.play_btn.setIconSize(QSize(20, 20))
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.hide()
        self.play_btn.clicked.connect(lambda: self.play_clicked.emit(self.data, self.type_str))

        self.title_lbl = ElidedLabel(data.title, parent=self)
        self.title_lbl.setObjectName("CardTitle")

        self.artist_lbl = ClickableElidedLabel(data.artist, font_size="13px", parent=self)
        self.artist_lbl.setObjectName("CardArtist")

        if type_str == MediaType.ALBUM:
            self.artist_lbl.clicked.connect(self._on_artist_click)
        else:
            self.title_lbl.setAlignment(Qt.AlignCenter)
            self.artist_lbl.hide()

        layout.addWidget(self.img_container, alignment=Qt.AlignCenter)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.artist_lbl)
        layout.addStretch()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        w = self.width() - 30
        if w <= 0:
            return
        self.img_container.setFixedSize(w, w)
        self.img.setFixedSize(w, w)

        rad = (w // 2) if self.type_str == MediaType.ARTIST else 12
        self.img.radius = rad
        self.overlay.setFixedSize(w, w)

        btn_s = 46
        self.play_btn.move((w - btn_s) // 2, (w - btn_s) // 2)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 25px 8px 10px;
                border-radius: 4px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background-color: {THEME['nav_bg']};
            }}
            QMenu::icon {{
                padding-left: 10px;
            }}
            QMenu::separator {{
                height: 1px;
                background: {THEME['border']};
                margin: 4px 10px;
            }}
        """)

        act_play = QAction(
            qta.icon('fa5s.play', color=THEME['text_main']),
            tr("context.play", "Odtwórz"),
            self
        )
        act_play.triggered.connect(lambda: self.play_clicked.emit(self.data, self.type_str))
        menu.addAction(act_play)

        act_queue = QAction(
            qta.icon('fa5s.plus', color=THEME['text_main']),
            tr("context.add_queue", "Dodaj do kolejki"),
            self
        )
        act_queue.triggered.connect(lambda: self.add_to_queue_clicked.emit(self.data, self.type_str))
        menu.addAction(act_queue)

        if self.type_str == MediaType.ALBUM:
            menu.addSeparator()
            act_artist = QAction(
                qta.icon('fa5s.user', color=THEME['text_main']),
                tr("context.go_artist", "Przejdź do wykonawcy"),
                self
            )
            act_artist.triggered.connect(self._on_artist_click)
            menu.addAction(act_artist)

            act_dl_videos = QAction(
                qta.icon('fa5s.video', color=THEME['text_main']),
                tr("context.download_video", "Pobierz teledysk"),
                self
            )
            act_dl_videos.triggered.connect(lambda: self.download_videos_clicked.emit(self.data, self.type_str))
            menu.addAction(act_dl_videos)

            menu.addSeparator()

            act_custom_cov = QAction(
                qta.icon('fa5s.image', color=THEME['text_main']),
                tr("context.custom_cover", "Ustaw własną okładkę"),
                self
            )
            act_custom_cov.triggered.connect(lambda: self.set_custom_cover_clicked.emit(self.data, self.type_str))
            menu.addAction(act_custom_cov)

            act_reset_cov = QAction(
                qta.icon('fa5s.undo', color=THEME['text_main']),
                tr("context.reset_cover", "Przywróć domyślną"),
                self
            )
            act_reset_cov.triggered.connect(lambda: self.reset_custom_cover_clicked.emit(self.data, self.type_str))
            menu.addAction(act_reset_cov)

            act_save_cov = QAction(
                qta.icon('fa5s.download', color=THEME['text_main']),
                tr("context.save_cover", "Zapisz okładkę do pliku"),
                self
            )
            act_save_cov.triggered.connect(lambda: self.save_image_clicked.emit(self.data, self.type_str))
            menu.addAction(act_save_cov)

        if self.type_str == MediaType.ARTIST:
            menu.addSeparator()

            act_dl_videos = QAction(
                qta.icon('fa5s.video', color=THEME['text_main']),
                tr("context.download_video", "Pobierz teledysk"),
                self
            )
            act_dl_videos.triggered.connect(lambda: self.download_videos_clicked.emit(self.data, self.type_str))
            menu.addAction(act_dl_videos)

            menu.addSeparator()

            act_custom_img = QAction(
                qta.icon('fa5s.image', color=THEME['text_main']),
                tr("context.custom_artist_img", "Ustaw własne zdjęcie"),
                self
            )
            act_custom_img.triggered.connect(lambda: self.set_custom_image_clicked.emit(self.data, self.type_str))
            menu.addAction(act_custom_img)

            act_reset_img = QAction(
                qta.icon('fa5s.undo', color=THEME['text_main']),
                tr("context.reset_cover", "Przywróć domyślną"),
                self
            )
            act_reset_img.triggered.connect(lambda: self.reset_custom_image_clicked.emit(self.data, self.type_str))
            menu.addAction(act_reset_img)

            act_save_img = QAction(
                qta.icon('fa5s.download', color=THEME['text_main']),
                tr("context.save_cover", "Zapisz okładkę do pliku"),
                self
            )
            act_save_img.triggered.connect(lambda: self.save_image_clicked.emit(self.data, self.type_str))
            menu.addAction(act_save_img)

        menu.exec(pos)

    def _on_artist_click(self):
        artist_id = self.data.get('artistId')
        if artist_id:
            self.artist_clicked.emit({"id": artist_id, "name": self.data.artist}, MediaType.ARTIST)

    def set_image(self, p, animate=True):
        self.img.set_image(p, animate)

    def enterEvent(self, e):
        self.overlay.show()
        self.play_btn.show()
        self.play_btn.raise_()
        self.img.set_hover(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.overlay.hide()
        self.play_btn.hide()
        self.img.set_hover(False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.data, self.type_str)
        elif e.button() == Qt.RightButton:
            self._show_context_menu(e.globalPos())