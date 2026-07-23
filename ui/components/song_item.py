import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QMenu
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QAction

from config import THEME
from ui.widgets import RoundedImage, ElidedLabel, ClickableElidedLabel, DragHandle, HoverIconButton
from core.enums import MediaType

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

    def __init__(self, song, active=False, is_queue=False, queue_index=-1, track_number=None, is_playlist=False, playlist_index=-1, compact_mode=False):
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
        self.cover_overlay.setFixedSize(48, 48)
        self.cover_overlay.setStyleSheet("border-radius: 6px; background-color: rgba(0,0,0,0.55); border: none;")
        self.cover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.cover_overlay.hide()

        self.play_btn = QPushButton(qta.icon('fa5s.play', color=THEME["play_color"]), "", self.img_container)
        self.play_btn.setFixedSize(28, 28)
        self.play_btn.setIconSize(QSize(12, 12))
        self.play_btn.setStyleSheet(f"QPushButton {{ background-color: {THEME['play_bg']}; border-radius: 14px; border: none; }} QPushButton:hover {{ background-color: {THEME['accent']}; }}")
        self.play_btn.move(10, 10)
        self.play_btn.hide()
        self.play_btn.clicked.connect(lambda: self.clicked.emit(self.song))

        v_box = QVBoxLayout()
        v_box.setSpacing(2)
        v_box.setContentsMargins(15, 0, 0, 0)

        self.title_lbl = ElidedLabel(song.title)
        self.title_lbl.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {THEME['text_main']}; background: transparent; margin: 0px; padding: 0px;")

        h_info = QHBoxLayout()
        h_info.setSpacing(5)
        h_info.setContentsMargins(0, 0, 0, 0)

        self.artist_lbl = ClickableElidedLabel(song.artist, default_color=THEME["text_muted"], hover_color=THEME["text_main"], font_size="12px")
        self.artist_lbl.clicked.connect(self._on_artist_click)

        self.album_lbl = ClickableElidedLabel(song.album, default_color=THEME["text_muted"], hover_color=THEME["text_main"], font_size="12px")
        self.album_lbl.clicked.connect(self._on_album_click)

        h_info.addWidget(self.artist_lbl)

        self.dot_lbl = QLabel("•")
        self.dot_lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent; font-size: 12px;")

        h_info.addWidget(self.dot_lbl)
        h_info.addWidget(self.album_lbl)
        h_info.addStretch()

        v_box.addWidget(self.title_lbl)
        v_box.addLayout(h_info)

        if self.is_queue or self.is_playlist:
            # KLUCZOWA ZMIANA: Przekazujemy self (rodzica) do DragHandle
            self.drag_handle = DragHandle(self.queue_index if self.is_queue else self.playlist_index, parent_item=self)
            layout.addWidget(self.drag_handle)
            layout.addWidget(self.img_container)
        elif track_number is not None:
            self.track_lbl = QLabel(str(track_number))
            self.track_lbl.setFixedSize(20, 40)
            self.track_lbl.setAlignment(Qt.AlignCenter)
            self.track_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; font-weight: bold; background: transparent;")
            layout.addWidget(self.track_lbl)
            layout.addWidget(self.img_container)
        else:
            layout.addWidget(self.img_container)

        layout.addLayout(v_box, 1)

        self.dl_status_lbl = QLabel()
        self.dl_status_lbl.setFixedSize(16, 16)
        self.dl_status_lbl.setStyleSheet("background: transparent;")
        layout.addWidget(self.dl_status_lbl)

        d = song.duration_sec
        dur_lbl = QLabel(f"{int(d//60)}:{int(d%60):02d}")
        dur_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; background: transparent; margin-right: 15px;")
        layout.addWidget(dur_lbl)

        btn_base_style = "QPushButton { background: transparent; border: none; border-radius: 16px; }"

        if not self.compact_mode:
            if self.is_queue:
                self.btn_play_next = HoverIconButton('fa5s.angle-double-up', icon_size=14)
                self.btn_play_next.setFixedSize(32, 32)
                self.btn_play_next.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_play_next_hover']}; }}")
                self.btn_play_next.setToolTip("Odtwórz jako następny")
                self.btn_play_next.clicked.connect(lambda: self.play_next_clicked.emit(self.song))

                self.btn_add_pl = HoverIconButton('fa5s.folder-plus', icon_size=14)
                self.btn_add_pl.setFixedSize(32, 32)
                self.btn_add_pl.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_add_pl_hover']}; }}")
                self.btn_add_pl.setToolTip("Dodaj do playlisty")
                self.btn_add_pl.clicked.connect(lambda: self.add_to_playlist_clicked.emit(self.song))

                self.btn_remove = HoverIconButton('fa5s.times', icon_size=14)
                self.btn_remove.setFixedSize(32, 32)
                self.btn_remove.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_remove_hover']}; }}")
                self.btn_remove.setToolTip("Usuń z kolejki")
                self.btn_remove.clicked.connect(lambda: self.remove_clicked.emit(self.song))

                layout.addWidget(self.btn_play_next)
                layout.addWidget(self.btn_add_pl)
                layout.addWidget(self.btn_remove)

            elif self.is_playlist:
                self.btn_add = HoverIconButton('fa5s.plus', icon_size=14)
                self.btn_add.setFixedSize(32, 32)
                self.btn_add.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_add_hover']}; }}")
                self.btn_add.setToolTip("Dodaj do kolejki")
                self.btn_add.clicked.connect(lambda: self.add_to_queue_clicked.emit(self.song))

                self.btn_add_pl = HoverIconButton('fa5s.folder-plus', icon_size=14)
                self.btn_add_pl.setFixedSize(32, 32)
                self.btn_add_pl.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_add_pl_hover']}; }}")
                self.btn_add_pl.setToolTip("Dodaj do playlisty")
                self.btn_add_pl.clicked.connect(lambda: self.add_to_playlist_clicked.emit(self.song))

                self.btn_remove_pl = HoverIconButton('fa5s.times', icon_size=14)
                self.btn_remove_pl.setFixedSize(32, 32)
                self.btn_remove_pl.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_remove_hover']}; }}")
                self.btn_remove_pl.setToolTip("Usuń z playlisty")
                self.btn_remove_pl.clicked.connect(lambda: self.remove_from_playlist_clicked.emit(self.song, self.playlist_index))

                layout.addWidget(self.btn_add)
                layout.addWidget(self.btn_add_pl)
                layout.addWidget(self.btn_remove_pl)

            else:
                self.btn_add_pl = HoverIconButton('fa5s.folder-plus', icon_size=14)
                self.btn_add_pl.setFixedSize(32, 32)
                self.btn_add_pl.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_add_pl_hover']}; }}")
                self.btn_add_pl.setToolTip("Dodaj do playlisty")
                self.btn_add_pl.clicked.connect(lambda: self.add_to_playlist_clicked.emit(self.song))

                self.btn_add = HoverIconButton('fa5s.plus', icon_size=14)
                self.btn_add.setFixedSize(32, 32)
                self.btn_add.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_add_hover']}; }}")
                self.btn_add.setToolTip("Dodaj do kolejki")
                self.btn_add.clicked.connect(lambda: self.add_to_queue_clicked.emit(self.song))

                layout.addWidget(self.btn_add_pl)
                layout.addWidget(self.btn_add)

        self.btn_fav = HoverIconButton('fa5s.heart' if song.is_starred else 'fa5.heart',
                                       default_color=THEME["accent"] if song.is_starred else THEME["heart_inactive"],
                                       icon_size=14)
        self.btn_fav.setFixedSize(32, 32)
        self.btn_fav.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")
        self.btn_fav.clicked.connect(self._on_fav)
        layout.addWidget(self.btn_fav)

        self.btn_more = HoverIconButton('fa5s.ellipsis-h', icon_size=14)
        self.btn_more.setFixedSize(32, 32)
        self.btn_more.setStyleSheet(f"{btn_base_style} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")
        self.btn_more.setToolTip("Więcej opcji")
        self.btn_more.clicked.connect(self._show_context_menu)
        layout.addWidget(self.btn_more)

        self.set_active(active)
        self.style().polish(self)

        self._update_dl_status_icon()
        self._connect_offline_signal()

    @staticmethod
    def _find_main_window():
        from PySide6.QtWidgets import QApplication
        for w in QApplication.instance().topLevelWidgets():
            if hasattr(w, 'engine') and hasattr(w.engine, 'video_download_manager'):
                return w
        return None

    def _connect_offline_signal(self):
        win = self._find_main_window()
        if win and hasattr(win, 'offline_status_changed'):
            win.offline_status_changed.connect(self._on_offline_status_updated)

    def _on_offline_status_updated(self, item_id, status):
        if item_id == self.song.item_id:
            self._update_dl_status_icon()

    def _show_context_menu(self):
        from ui.components.song_context_menu import SongContextMenu
        SongContextMenu.show(self)

    def _update_dl_status_icon(self):
        win = self._find_main_window()
        if not win or not hasattr(win, 'engine'): return

        from config import APP_CONFIG
        
        is_offline = False
        if hasattr(win, 'network_monitor'):
            is_offline = not getattr(win.network_monitor, 'is_online', True)
            
        hide_undownloaded = str(APP_CONFIG.get('hide_undownloaded_offline', 'False')).lower() == 'true'
        
        has_audio = False
        has_video = False
        vid_status = None
        
        if hasattr(win.engine, 'audio_download_manager'):
            has_audio = win.engine.audio_download_manager.is_downloaded(self.song.item_id)
            
        if hasattr(win.engine, 'video_download_manager'):
            import sqlite3
            try:
                conn = sqlite3.connect(win.engine.video_download_manager.db_path)
                c = conn.cursor()
                c.execute("SELECT status FROM downloads WHERE item_id = ?", (self.song.item_id,))
                row = c.fetchone()
                conn.close()
                if row:
                    vid_status = row[0]
                    if vid_status == "COMPLETED":
                        has_video = True
            except:
                pass
                
        # Ustalanie ikony
        if has_audio and has_video:
            self.dl_status_lbl.setPixmap(qta.icon('fa5s.check-double', color=THEME['accent']).pixmap(14, 14))
            self.dl_status_lbl.setToolTip("Pobrane Audio i Wideo")
        elif has_audio:
            self.dl_status_lbl.setPixmap(qta.icon('fa5s.check-circle', color=THEME['accent']).pixmap(14, 14))
            self.dl_status_lbl.setToolTip("Pobrane Audio")
        elif has_video:
            self.dl_status_lbl.setPixmap(qta.icon('fa5s.film', color=THEME['accent']).pixmap(14, 14))
            self.dl_status_lbl.setToolTip("Pobrane Wideo")
        elif vid_status in ["QUEUED", "DOWNLOADING"]:
            self.dl_status_lbl.setPixmap(qta.icon('fa5s.spinner', color=THEME['text_muted']).pixmap(14, 14))
            self.dl_status_lbl.setToolTip("Pobieranie...")
        elif vid_status == "ERROR":
            self.dl_status_lbl.setPixmap(qta.icon('fa5s.exclamation-circle', color='#e74c3c').pixmap(14, 14))
            self.dl_status_lbl.setToolTip("Błąd pobierania")
        else:
            self.dl_status_lbl.setPixmap(qta.icon('fa5s.cloud', color=THEME['border']).pixmap(14, 14))
            self.dl_status_lbl.setToolTip("Dostępne w chmurze (Online)")
            
        # Logika Offline UX
        if is_offline and not has_audio:
            if hide_undownloaded:
                self.setVisible(False)
            else:
                self.setVisible(True)
                self.setEnabled(False) # Powoduje "wyszarzenie" i zablokowanie kliknięć
        else:
            self.setVisible(True)
            self.setEnabled(True)

    def set_active(self, is_active):
        bg = THEME['accent_rgba'] if is_active else "transparent"
        self.setStyleSheet(f"#SongItem {{ background-color: {bg}; border-radius: 8px; padding: 8px 12px; }} #SongItem:hover {{ background-color: {THEME['bg_card']}; }}")

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