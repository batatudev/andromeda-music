import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: views/view_now_playing.py
# OPIS ZMIAN: Wywołanie hide() przed deleteLater() przy aktualizacji kolejki dla płynności Drag & Drop

import qtawesome as qta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsOpacityEffect, QStackedLayout, QSizePolicy,
    QGraphicsView, QGraphicsScene
)
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSizeF, QPoint, QTimer

from config import THEME, APP_CONFIG
from ui.widgets import DragDropContainer, RoundedImage, ClickableLabel, HoverIconButton, SmoothScrollArea
from ui.components import SongItem
from core.i18n import tr

class VideoGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_scene = QGraphicsScene(self)
        self.setScene(self.video_scene)
        self.video_item = QGraphicsVideoItem()
        self.video_scene.addItem(self.video_item)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        view_size = self.size()
        self.video_scene.setSceneRect(0, 0, view_size.width(), view_size.height())
        size = self.video_item.nativeSize()
        if size.width() > 0 and size.height() > 0:
            scale = max(view_size.width() / size.width(), view_size.height() / size.height())
            new_w = size.width() * scale
            new_h = size.height() * scale
        else:
            new_w = view_size.width()
            new_h = view_size.height()
        self.video_item.setSize(QSizeF(new_w, new_h))
        self.video_item.setPos((view_size.width() - new_w) / 2, (view_size.height() - new_h) / 2)

class NowPlayingWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("NowPlayingWidget")
        self.is_video_dynamic = True
        self.raw_pixmap = None

        self._cached_blurred_pixmap = None
        self._cached_blur_raw = None
        self._cached_blur_val = -1

        self.bg_container = QWidget(self)
        self.bg_layout = QStackedLayout(self.bg_container)
        self.bg_layout.setStackingMode(QStackedLayout.StackOne)

        self.bg_label = QLabel()
        self.bg_label.setScaledContents(True)

        self.video_widget = VideoGraphicsView(self)

        self.bg_layout.addWidget(self.bg_label)
        self.bg_layout.addWidget(self.video_widget)
        self.bg_layout.setCurrentWidget(self.bg_label)

        self.overlay = QLabel(self)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.setStyleSheet(f"background: rgba({THEME['bg_main_rgb']}, 255);")

        self.overlay_opacity = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(self.overlay_opacity)

        self.breath_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.breath_anim.setDuration(2400)
        self.breath_anim.setLoopCount(-1)

        self.breath_restore_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.breath_restore_anim.setDuration(800)
        self.breath_restore_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.crossfade_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.crossfade_anim.setDuration(500)
        self.crossfade_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.crossfade_anim.finished.connect(self._on_crossfade_finished)

        self._dim_base = 0.3
        self._crossfade_callback = None
        self._crossfade_target_mode = None

        self.ui_container = QWidget(self)
        self.ui_container.setStyleSheet("background: transparent;")

        self.bg_container.lower()
        self.overlay.raise_()
        self.ui_container.raise_()

        self.main_layout = QHBoxLayout(self.ui_container)
        self.main_layout.setContentsMargins(50, 50, 50, 50)
        self.main_layout.setSpacing(40)

        self.left_layout = QVBoxLayout()
        self.left_layout.setAlignment(Qt.AlignCenter)

        self.media_container = QWidget()
        self.media_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.media_container.setMinimumSize(400, 300)
        self.media_container.setStyleSheet("background: transparent;")

        self.media_layout = QVBoxLayout(self.media_container)
        self.media_layout.setContentsMargins(0, 0, 0, 0)

        self.art_wrapper = QWidget()
        self.art_wrapper.setStyleSheet("background: transparent;")
        self.art_layout = QVBoxLayout(self.art_wrapper)
        self.art_layout.setAlignment(Qt.AlignCenter)
        self.img = RoundedImage(size=350, radius=15)
        self.art_layout.addWidget(self.img)

        self.media_layout.addWidget(self.art_wrapper)

        not_playing_txt = tr("player.not_playing", "Nic nie gra")
        self.title_lbl = QLabel(not_playing_txt)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setStyleSheet(
            f"font-size: 40px; font-weight: bold; color: {THEME['text_main']}; background: transparent; margin-top: 20px;"
        )

        self.artist_lbl = ClickableLabel(
            "-",
            default_color=THEME["text_muted"],
            hover_color=THEME["text_main"],
            font_size="24px"
        )
        self.artist_lbl.setAlignment(Qt.AlignCenter)

        self.left_layout.addStretch(1)
        self.left_layout.addWidget(self.media_container, 8)
        self.left_layout.addWidget(self.title_lbl)
        self.left_layout.addWidget(self.artist_lbl)
        self.left_layout.addStretch(1)

        self.queue_frame = QFrame()
        self.queue_frame.setObjectName("NowPlayingQueueFrame")
        self.queue_frame.setStyleSheet(
            f"#NowPlayingQueueFrame {{ background-color: rgba({THEME['bg_main_rgb']}, 100); "
            f"border-radius: 12px; border: 1px solid {THEME['border']}; }}"
        )

        qf_layout = QVBoxLayout(self.queue_frame)
        qf_layout.setContentsMargins(15, 15, 15, 15)

        header_layout = QHBoxLayout()
        queue_txt = tr("player.queue_title", "Kolejka odtwarzania")
        self.q_title = QLabel(queue_txt)
        self.q_title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {THEME['text_main']}; background: transparent;"
        )
        header_layout.addWidget(self.q_title)
        header_layout.addStretch()

        btn_base = "QPushButton { background: transparent; border: none; border-radius: 16px; }"

        self.btn_q_shuffle = HoverIconButton('fa5s.random', hover_color=THEME['accent'], icon_size=14)
        self.btn_q_shuffle.setFixedSize(32, 32)
        self.btn_q_shuffle.setStyleSheet(
            f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}"
        )
        self.btn_q_shuffle.setToolTip(tr("player.shuffle", "Losuj"))

        self.btn_q_clear = HoverIconButton('fa5s.trash-alt', hover_color=THEME['accent'], icon_size=14)
        self.btn_q_clear.setFixedSize(32, 32)
        self.btn_q_clear.setStyleSheet(
            f"{btn_base} QPushButton:hover {{ background: {THEME['btn_remove_hover']}; }}"
        )
        self.btn_q_clear.setToolTip(tr("player.clear", "Wyczyść"))

        header_layout.addWidget(self.btn_q_shuffle)
        header_layout.addWidget(self.btn_q_clear)

        qf_layout.addLayout(header_layout)

        self.queue_scroll = SmoothScrollArea()
        self.queue_scroll.setWidgetResizable(True)
        self.queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.queue_scroll.setStyleSheet("background: transparent; border: none;")
        self.queue_scroll.viewport().setAttribute(Qt.WA_TranslucentBackground, True)

        self.queue_content = DragDropContainer()
        self.queue_layout = QVBoxLayout(self.queue_content)
        self.queue_layout.setAlignment(Qt.AlignTop)
        self.queue_layout.setContentsMargins(0, 10, 0, 10)
        self.queue_scroll.setWidget(self.queue_content)

        qf_layout.addWidget(self.queue_scroll)

        self.main_layout.addLayout(self.left_layout, 3)
        self.main_layout.addWidget(self.queue_frame, 2)

        self.right_spacer = QWidget()
        self.right_spacer.setFixedWidth(0)
        self.main_layout.addWidget(self.right_spacer)

        self.update_video_settings()

    def update_queue(self, songs, active_idx, handlers, loader, client):
        """
        Dedykowana metoda budująca listę utworów w widżecie kolejki z zachowaniem scrolla.
        """
        v_bar = self.queue_scroll.verticalScrollBar()
        old_val = v_bar.value()

        while self.queue_layout.count():
            item = self.queue_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        for i, s in enumerate(songs):
            item = SongItem(
                s,
                active=(i == active_idx),
                is_queue=True,
                queue_index=i,
                compact_mode=True
            )
            if 'play' in handlers:
                item.clicked.connect(lambda song, idx=i: handlers['play'](idx))
            if 'fav' in handlers:
                item.fav_clicked.connect(handlers['fav'])
            if 'play_next' in handlers:
                item.play_next_clicked.connect(lambda s_d, idx=i: handlers['play_next'](idx))
            if 'add_to_playlist' in handlers:
                item.add_to_playlist_clicked.connect(handlers['add_to_playlist'])
            if 'remove' in handlers:
                item.remove_clicked.connect(lambda s_d, idx=i: handlers['remove'](idx))
            if 'artist' in handlers:
                item.artist_clicked.connect(handlers['artist'])
            if 'album' in handlers:
                item.album_clicked.connect(handlers['album'])
            if 'set_custom_cover' in handlers:
                item.set_custom_cover_clicked.connect(handlers['set_custom_cover'])
            if 'reset_custom_cover' in handlers:
                item.reset_custom_cover_clicked.connect(handlers['reset_custom_cover'])
            if 'save_image' in handlers:
                item.save_image_clicked.connect(handlers['save_image'])

            self.queue_layout.addWidget(item)
            if s.cover_id and loader and client:
                loader.load(client.get_cover_art_url(s.cover_id), item)

        QTimer.singleShot(0, lambda: self.queue_scroll.verticalScrollBar().setValue(old_val))

    def sync_active_index(self, active_idx):
        """Aktualizuje podświetlenie aktywnego utworu bez przebudowy widżetów."""
        for i in range(self.queue_layout.count()):
            item = self.queue_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), SongItem):
                w = item.widget()
                w.queue_index = i
                w.set_active(w.queue_index == active_idx)

    def scroll_to_active(self, active_idx):
        """Przewija widok kolejki do aktualnie odtwarzanego utworu."""
        if 0 <= active_idx < self.queue_layout.count():
            item = self.queue_layout.itemAt(active_idx)
            if item and item.widget():
                self.queue_scroll.ensureWidgetVisible(item.widget())

    def resizeEvent(self, e):
        self.bg_container.resize(self.size())
        self.overlay.resize(self.size())
        self.ui_container.resize(self.size())

        if getattr(self, 'is_queue_hidden', False):
            if not hasattr(self, 'spacer_anim') or self.spacer_anim.state() != QPropertyAnimation.State.Running:
                try:
                    offset_x = self.mapTo(self.window(), QPoint(0, 0)).x()
                    self.right_spacer.setFixedWidth(offset_x)
                except Exception:
                    pass

        super().resizeEvent(e)

    def _ensure_queue_anim(self):
        if not hasattr(self, 'queue_anim'):
            self.queue_anim = QPropertyAnimation(self.queue_frame, b"maximumWidth")
            self.queue_anim.setDuration(400)
            self.queue_anim.setEasingCurve(QEasingCurve.InOutCubic)
            self.queue_anim.finished.connect(self._on_queue_anim_finished)

            effect = QGraphicsOpacityEffect(self.queue_frame)
            self.queue_frame.setGraphicsEffect(effect)
            self.queue_fade = QPropertyAnimation(effect, b"opacity")
            self.queue_fade.setDuration(300)
            self.queue_fade.setEasingCurve(QEasingCurve.InOutQuad)

            self.spacer_anim = QPropertyAnimation(self.right_spacer, b"minimumWidth")
            self.spacer_anim.setDuration(400)
            self.spacer_anim.setEasingCurve(QEasingCurve.InOutCubic)

            self.is_queue_hidden = False

    def _on_queue_anim_finished(self):
        if getattr(self, 'is_queue_hidden', False):
            self.queue_frame.hide()
            try:
                self.right_spacer.setFixedWidth(self.mapTo(self.window(), QPoint(0, 0)).x())
            except Exception:
                pass
        else:
            self.queue_frame.setMaximumWidth(16777215)
            self.right_spacer.setFixedWidth(0)

    def toggle_queue_visibility(self):
        self._ensure_queue_anim()

        self.queue_anim.stop()
        self.queue_fade.stop()
        self.spacer_anim.stop()

        if not getattr(self, 'is_queue_hidden', False):
            self.is_queue_hidden = True
            current_w = self.queue_frame.width()
            self.queue_anim.setStartValue(current_w)
            self.queue_anim.setEndValue(0)

            self.queue_fade.setStartValue(1.0)
            self.queue_fade.setEndValue(0.0)

            try:
                offset_x = self.mapTo(self.window(), QPoint(0, 0)).x()
            except Exception:
                offset_x = 200
            self.spacer_anim.setStartValue(self.right_spacer.width())
            self.spacer_anim.setEndValue(offset_x)

        else:
            self.is_queue_hidden = False

            self.queue_frame.setMaximumWidth(0)
            self.queue_frame.show()

            target_w = int((self.width() - 140) * 0.4)

            self.queue_anim.setStartValue(0)
            self.queue_anim.setEndValue(target_w)

            self.queue_fade.setStartValue(0.0)
            self.queue_fade.setEndValue(1.0)

            self.spacer_anim.setStartValue(self.right_spacer.width())
            self.spacer_anim.setEndValue(0)

        self.queue_anim.start()
        self.queue_fade.start()
        self.spacer_anim.start()

    def set_seek_blur(self, is_seeking):
        if not is_seeking:
            self.set_buffering_state(False)

    def set_buffering_state(self, is_buffering):
        if is_buffering:
            self.crossfade_anim.stop()
            self.breath_restore_anim.stop()
            if self.breath_anim.state() != QPropertyAnimation.State.Running:
                base = self.overlay_opacity.opacity()
                self.breath_anim.setKeyValueAt(0.0, base)
                self.breath_anim.setKeyValueAt(0.5, base * 0.4)
                self.breath_anim.setKeyValueAt(1.0, base)
                self.breath_anim.start()
        else:
            self.breath_anim.stop()
            self.breath_restore_anim.stop()
            curr_op = self.overlay_opacity.opacity()
            self.breath_restore_anim.setStartValue(curr_op)
            self.breath_restore_anim.setEndValue(self._dim_base)
            self.breath_restore_anim.start()

    def set_image(self, p, animate=True):
        self.is_video_dynamic = True
        self.img.set_image(p, animate)
        self.raw_pixmap = p
        if not p or p.isNull():
            self.bg_label.clear()
            self._cached_blurred_pixmap = None
            self._cached_blur_raw = None
        self.update_video_settings()

    def update_video_settings(self):
        if self.bg_layout.currentWidget() == self.video_widget:
            opacity = APP_CONFIG.get("video_dynamic_opacity", 30)
            blur_val = APP_CONFIG.get("video_dynamic_blur", 0)

            self._dim_base = opacity / 100.0
            self.overlay_opacity.setOpacity(self._dim_base)

            if blur_val > 0:
                from PySide6.QtWidgets import QGraphicsBlurEffect
                blur = QGraphicsBlurEffect()
                blur.setBlurRadius(blur_val)
                self.video_widget.video_item.setGraphicsEffect(blur)
            else:
                self.video_widget.video_item.setGraphicsEffect(None)
        else:
            opacity = APP_CONFIG.get("video_static_opacity", 80)
            blur_val = APP_CONFIG.get("video_static_blur", 60)

            self._dim_base = opacity / 100.0
            self.overlay_opacity.setOpacity(self._dim_base)

            if hasattr(self, 'raw_pixmap') and self.raw_pixmap and not self.raw_pixmap.isNull():
                if (
                    self._cached_blurred_pixmap is not None
                    and self._cached_blur_raw is self.raw_pixmap
                    and self._cached_blur_val == blur_val
                ):
                    self.bg_label.setPixmap(self._cached_blurred_pixmap)
                else:
                    from utils import get_blurred_pixmap
                    blurred = get_blurred_pixmap(self.raw_pixmap, blur_val)
                    self._cached_blurred_pixmap = blurred
                    self._cached_blur_raw = self.raw_pixmap
                    self._cached_blur_val = blur_val
                    self.bg_label.setPixmap(blurred)

    def set_media_mode(self, mode):
        if mode == "video":
            self.bg_layout.setCurrentWidget(self.video_widget)
        else:
            self.bg_layout.setCurrentWidget(self.bg_label)

        self.update_video_settings()
        self.bg_container.lower()
        self.overlay.raise_()
        self.ui_container.raise_()

    def transition_to_audio(self, on_done=None):
        self.crossfade_anim.stop()
        self.breath_anim.stop()
        self.breath_restore_anim.stop()
        curr = self.overlay_opacity.opacity()
        target = APP_CONFIG.get("video_static_opacity", 80) / 100.0
        self.crossfade_anim.setStartValue(curr)
        self.crossfade_anim.setEndValue(target)
        self._crossfade_callback = on_done
        self._crossfade_target_mode = "audio"
        self.crossfade_anim.start()

    def transition_to_video(self):
        self.crossfade_anim.stop()
        self.breath_anim.stop()
        self.breath_restore_anim.stop()
        self.bg_layout.setCurrentWidget(self.video_widget)
        curr = self.overlay_opacity.opacity()
        target = APP_CONFIG.get("video_dynamic_opacity", 30) / 100.0
        self.crossfade_anim.setStartValue(curr)
        self.crossfade_anim.setEndValue(target)
        self._crossfade_callback = None
        self._crossfade_target_mode = "video"
        self.crossfade_anim.start()

    def _on_crossfade_finished(self):
        if self._crossfade_target_mode == "audio":
            self._on_crossfade_to_audio()
        elif self._crossfade_target_mode == "video":
            self._on_crossfade_to_video()

    def _on_crossfade_to_audio(self):
        self.bg_layout.setCurrentWidget(self.bg_label)
        self.update_video_settings()
        cb = self._crossfade_callback
        self._crossfade_callback = None
        if cb:
            cb()

    def _on_crossfade_to_video(self):
        self.update_video_settings()