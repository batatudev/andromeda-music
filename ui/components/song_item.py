import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QApplication
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction

from config import THEME
from ui.widgets import (
    RoundedImage, ElidedLabel, ClickableElidedLabel, DragHandle,
    HoverIconButton, get_cached_icon
)
from core.enums import MediaType

_MAIN_WINDOW_REF = None
_STATUS_PIXMAP_CACHE = {}


def _get_status_pixmap(status_key):
    global _STATUS_PIXMAP_CACHE
    if status_key in _STATUS_PIXMAP_CACHE:
        return _STATUS_PIXMAP_CACHE[status_key]

    accent = THEME.get('accent', '#1db954')
    border = THEME.get('border', '#444444')

    if status_key == "both":
        pix = get_cached_icon('fa5s.check-double', color=accent).pixmap(14, 14)
    elif status_key == "audio":
        pix = get_cached_icon('fa5s.check-circle', color=accent).pixmap(14, 14)
    elif status_key == "video":
        pix = get_cached_icon('fa5s.film', color=accent).pixmap(14, 14)
    else:
        pix = get_cached_icon('fa5s.cloud', color=border).pixmap(14, 14)

    _STATUS_PIXMAP_CACHE[status_key] = pix
    return pix


def _get_main_window():
    global _MAIN_WINDOW_REF
    if _MAIN_WINDOW_REF is not None:
        return _MAIN_WINDOW_REF
    app = QApplication.instance()
    if not app:
        return None
    for w in app.topLevelWidgets():
        if hasattr(w, 'engine') and hasattr(w.engine, 'video_download_manager'):
            _MAIN_WINDOW_REF = w
            return _MAIN_WINDOW_REF
    return None


class SongItem(QFrame):
    clicked = Signal(object)
    fav_clicked = Signal(object, bool)
    add_to_queue_clicked = Signal(object)
    add_to_playlist_clicked = Signal(object)

    remove_clicked = Signal(object)
    play_next_clicked = Signal(object)
    remove_from_playlist_clicked = Signal(object, int)

    artist_clicked = Signal(object, str)
    album_clicked = Signal(object, str)
    set_custom_cover_clicked = Signal(object, str)
    reset_custom_cover_clicked = Signal(object, str)
    save_image_clicked = Signal(object, str)

    def __init__(
        self,
        song,
        active=False,
        is_queue=False,
        queue_index=-1,
        track_number=None,
        is_playlist=False,
        playlist_index=-1,
        compact_mode=False
    ):
        super().__init__()
        self.song = song
        self.is_queue = is_queue
        self.queue_index = queue_index
        self.is_playlist = is_playlist
        self.playlist_index = playlist_index
        self.compact_mode = compact_mode

        self.setObjectName("SongItem")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setFixedHeight(65)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 15, 0)

        self.img_container = QWidget()
        self.img_container.setFixedSize(48, 48)
        self.img_container.setStyleSheet("background: transparent;")

        self.img = RoundedImage(size=48, radius=6)
        self.img.setParent(self.img_container)
        self.img.move(0, 0)

        self.cover_overlay = QFrame(self.img_container)
        self.cover_overlay.setObjectName("SongCoverOverlay")
        self.cover_overlay.setFixedSize(48, 48)
        self.cover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.cover_overlay.hide()

        self.play_btn = QPushButton(get_cached_icon('fa5s.play', color=THEME["play_color"]), "", self.img_container)
        self.play_btn.setObjectName("SongPlayBtn")
        self.play_btn.setFixedSize(28, 28)
        self.play_btn.setIconSize(QSize(12, 12))
        self.play_btn.move(10, 10)
        self.play_btn.hide()
        self.play_btn.clicked.connect(lambda: self.clicked.emit(self.song))

        v_box = QVBoxLayout()
        v_box.setSpacing(2)
        v_box.setContentsMargins(15, 0, 0, 0)

        self.title_lbl = ElidedLabel(song.title)
        self.title_lbl.setObjectName("SongTitle")

        h_info = QHBoxLayout()
        h_info.setSpacing(5)
        h_info.setContentsMargins(0, 0, 0, 0)

        self.artist_lbl = ClickableElidedLabel(song.artist, font_size="12px")
        self.artist_lbl.setObjectName("SongArtist")
        self.artist_lbl.clicked.connect(self._on_artist_click)

        self.album_lbl = ClickableElidedLabel(song.album, font_size="12px")
        self.album_lbl.setObjectName("SongAlbum")
        self.album_lbl.clicked.connect(self._on_album_click)

        self.dot_lbl = QLabel("•")
        self.dot_lbl.setObjectName("SongDot")

        h_info.addWidget(self.artist_lbl)
        h_info.addWidget(self.dot_lbl)
        h_info.addWidget(self.album_lbl)
        h_info.addStretch()

        v_box.addWidget(self.title_lbl)
        v_box.addLayout(h_info)

        if self.is_queue or self.is_playlist:
            self.drag_handle = DragHandle(self.queue_index if self.is_queue else self.playlist_index, parent_item=self)
            layout.addWidget(self.drag_handle)
            layout.addWidget(self.img_container)
        elif track_number is not None:
            self.track_lbl = QLabel(str(track_number))
            self.track_lbl.setObjectName("SongTrackNum")
            self.track_lbl.setFixedSize(20, 40)
            self.track_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.track_lbl)
            layout.addWidget(self.img_container)
        else:
            layout.addWidget(self.img_container)

        layout.addLayout(v_box, 1)

        self.dl_status_lbl = QLabel()
        self.dl_status_lbl.setObjectName("SongDlStatus")
        self.dl_status_lbl.setFixedSize(16, 16)
        layout.addWidget(self.dl_status_lbl)

        d = song.duration_sec
        dur_lbl = QLabel(f"{int(d // 60)}:{int(d % 60):02d}")
        dur_lbl.setObjectName("SongDuration")
        layout.addWidget(dur_lbl)

        if not self.compact_mode:
            if self.is_queue:
                self.btn_play_next = HoverIconButton('fa5s.angle-double-up', icon_size=14)
                self.btn_play_next.setObjectName("SongPlayNextBtn")
                self.btn_play_next.setFixedSize(32, 32)
                self.btn_play_next.setToolTip("Odtwórz jako następny")
                self.btn_play_next.clicked.connect(lambda: self.play_next_clicked.emit(self.song))

                self.btn_add_pl = HoverIconButton('fa5s.folder-plus', icon_size=14)
                self.btn_add_pl.setObjectName("SongAddPlBtn")
                self.btn_add_pl.setFixedSize(32, 32)
                self.btn_add_pl.setToolTip("Dodaj do playlisty")
                self.btn_add_pl.clicked.connect(lambda: self.add_to_playlist_clicked.emit(self.song))

                self.btn_remove = HoverIconButton('fa5s.times', icon_size=14)
                self.btn_remove.setObjectName("SongRemoveBtn")
                self.btn_remove.setFixedSize(32, 32)
                self.btn_remove.setToolTip("Usuń z kolejki")
                self.btn_remove.clicked.connect(lambda: self.remove_clicked.emit(self.song))

                layout.addWidget(self.btn_play_next)
                layout.addWidget(self.btn_add_pl)
                layout.addWidget(self.btn_remove)

            elif self.is_playlist:
                self.btn_add = HoverIconButton('fa5s.plus', icon_size=14)
                self.btn_add.setObjectName("SongAddBtn")
                self.btn_add.setFixedSize(32, 32)
                self.btn_add.setToolTip("Dodaj do kolejki")
                self.btn_add.clicked.connect(lambda: self.add_to_queue_clicked.emit(self.song))

                self.btn_add_pl = HoverIconButton('fa5s.folder-plus', icon_size=14)
                self.btn_add_pl.setObjectName("SongAddPlBtn")
                self.btn_add_pl.setFixedSize(32, 32)
                self.btn_add_pl.setToolTip("Dodaj do playlisty")
                self.btn_add_pl.clicked.connect(lambda: self.add_to_playlist_clicked.emit(self.song))

                self.btn_remove_pl = HoverIconButton('fa5s.times', icon_size=14)
                self.btn_remove_pl.setObjectName("SongRemoveBtn")
                self.btn_remove_pl.setFixedSize(32, 32)
                self.btn_remove_pl.setToolTip("Usuń z playlisty")
                self.btn_remove_pl.clicked.connect(lambda: self.remove_from_playlist_clicked.emit(self.song, self.playlist_index))

                layout.addWidget(self.btn_add)
                layout.addWidget(self.btn_add_pl)
                layout.addWidget(self.btn_remove_pl)

            else:
                self.btn_add_pl = HoverIconButton('fa5s.folder-plus', icon_size=14)
                self.btn_add_pl.setObjectName("SongAddPlBtn")
                self.btn_add_pl.setFixedSize(32, 32)
                self.btn_add_pl.setToolTip("Dodaj do playlisty")
                self.btn_add_pl.clicked.connect(lambda: self.add_to_playlist_clicked.emit(self.song))

                self.btn_add = HoverIconButton('fa5s.plus', icon_size=14)
                self.btn_add.setObjectName("SongAddBtn")
                self.btn_add.setFixedSize(32, 32)
                self.btn_add.setToolTip("Dodaj do kolejki")
                self.btn_add.clicked.connect(lambda: self.add_to_queue_clicked.emit(self.song))

                layout.addWidget(self.btn_add_pl)
                layout.addWidget(self.btn_add)

        self.btn_fav = HoverIconButton(
            'fa5s.heart' if song.is_starred else 'fa5.heart',
            default_color=THEME["accent"] if song.is_starred else THEME["heart_inactive"],
            icon_size=14
        )
        self.btn_fav.setObjectName("SongFavBtn")
        self.btn_fav.setFixedSize(32, 32)
        self.btn_fav.clicked.connect(self._on_fav)
        layout.addWidget(self.btn_fav)

        self.btn_more = HoverIconButton('fa5s.ellipsis-h', icon_size=14)
        self.btn_more.setObjectName("SongMoreBtn")
        self.btn_more.setFixedSize(32, 32)
        self.btn_more.setToolTip("Więcej opcji")
        self.btn_more.clicked.connect(self._show_context_menu)
        layout.addWidget(self.btn_more)

        self.setProperty("active", "true" if active else "false")
        self._update_dl_status_icon()
        self._connect_signals()

    def _find_main_window(self):
        return _get_main_window()

    def _connect_signals(self):
        win = _get_main_window()
        if win:
            if hasattr(win, 'offline_status_changed'):
                win.offline_status_changed.connect(self._on_offline_status_updated)
            if hasattr(win, 'fav_updated'):
                win.fav_updated.connect(self._on_fav_updated_signal)

    def _on_fav_updated_signal(self, song_id, is_fav):
        if self.song and self.song.item_id == song_id:
            self.update_fav_state(is_fav)

    def _on_offline_status_updated(self, item_id, status):
        if self.song and item_id == self.song.item_id:
            self._update_dl_status_icon()

    def _show_context_menu(self):
        from ui.components.song_context_menu import SongContextMenu
        SongContextMenu.show(self)

    def _update_dl_status_icon(self):
        win = _get_main_window()
        if not win or not hasattr(win, 'engine'):
            self.dl_status_lbl.setPixmap(_get_status_pixmap("cloud"))
            return

        from config import APP_CONFIG

        is_offline = False
        if hasattr(win, 'network_monitor'):
            is_offline = not getattr(win.network_monitor, 'is_online', True)

        hide_undownloaded = str(APP_CONFIG.get('hide_undownloaded_offline', 'False')).lower() == 'true'

        has_audio = False
        has_video = False

        item_id = self.song.item_id
        if hasattr(win.engine, 'audio_download_manager'):
            has_audio = item_id in win.engine.audio_download_manager._path_cache

        if hasattr(win.engine, 'video_download_manager'):
            has_video = item_id in win.engine.video_download_manager._path_cache

        if has_audio and has_video:
            self.dl_status_lbl.setPixmap(_get_status_pixmap("both"))
            self.dl_status_lbl.setToolTip("Pobrane Audio i Wideo")
        elif has_audio:
            self.dl_status_lbl.setPixmap(_get_status_pixmap("audio"))
            self.dl_status_lbl.setToolTip("Pobrane Audio")
        elif has_video:
            self.dl_status_lbl.setPixmap(_get_status_pixmap("video"))
            self.dl_status_lbl.setToolTip("Pobrane Wideo")
        else:
            self.dl_status_lbl.setPixmap(_get_status_pixmap("cloud"))
            self.dl_status_lbl.setToolTip("Dostępne w chmurze (Online)")

        if is_offline and not has_audio:
            if hide_undownloaded:
                self.setVisible(False)
            else:
                self.setVisible(True)
                self.setEnabled(False)
        else:
            self.setVisible(True)
            self.setEnabled(True)

    def set_active(self, is_active):
        new_val = "true" if is_active else "false"
        if self.property("active") != new_val:
            self.setProperty("active", new_val)
            self.style().unpolish(self)
            self.style().polish(self)

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

    def _on_artist_click(self):
        artist_id = self.song.get('artistId')
        if artist_id:
            self.artist_clicked.emit({"id": artist_id, "name": self.song.artist}, MediaType.ARTIST)

    def _on_album_click(self):
        album_id = self.song.get('albumId')
        if album_id:
            self.album_clicked.emit({"id": album_id, "name": self.song.album}, MediaType.ALBUM)

    def _on_fav(self):
        new_state = not self.song.is_starred
        self.fav_clicked.emit(self.song, new_state)

    def update_fav_state(self, is_fav):
        self.song.set_starred(is_fav)
        if is_fav:
            self.btn_fav.set_default_color(THEME["accent"])
            self.btn_fav.update_icon('fa5s.heart')
        else:
            self.btn_fav.set_default_color(THEME["heart_inactive"])
            self.btn_fav.update_icon('fa5.heart')

    def set_image(self, p, animate=True):
        self.img.set_image(p, animate)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.song)