import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsOpacityEffect, QStackedLayout, QSizePolicy, QGraphicsView, QGraphicsScene
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSizeF, QPoint

from config import THEME, APP_CONFIG
from ui.widgets import DragDropContainer, RoundedImage, ClickableLabel, HoverIconButton, SmoothScrollArea
from ui.components import SongItem

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

        self.title_lbl = QLabel("Nic nie gra")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setStyleSheet(f"font-size: 40px; font-weight: bold; color: {THEME['text_main']}; background: transparent; margin-top: 20px;")

        self.artist_lbl = ClickableLabel("-", default_color=THEME["text_muted"], hover_color=THEME["text_main"], font_size="24px")
        self.artist_lbl.setAlignment(Qt.AlignCenter)

        self.left_layout.addStretch(1)
        self.left_layout.addWidget(self.media_container, 8)
        self.left_layout.addWidget(self.title_lbl)
        self.left_layout.addWidget(self.artist_lbl)
        self.left_layout.addStretch(1)

        self.queue_frame = QFrame()
        self.queue_frame.setObjectName("NowPlayingQueueFrame")
        self.queue_frame.setStyleSheet(f"#NowPlayingQueueFrame {{ background-color: rgba({THEME['bg_main_rgb']}, 100); border-radius: 12px; border: 1px solid {THEME['border']}; }}")

        qf_layout = QVBoxLayout(self.queue_frame)
        qf_layout.setContentsMargins(15, 15, 15, 15)

        header_layout = QHBoxLayout()
        self.q_title = QLabel("Kolejka odtwarzania")
        self.q_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {THEME['text_main']}; background: transparent;")
        header_layout.addWidget(self.q_title)
        header_layout.addStretch()

        btn_base = "QPushButton { background: transparent; border: none; border-radius: 16px; }"

        self.btn_q_shuffle = HoverIconButton('fa5s.random', hover_color=THEME['accent'], icon_size=14)
        self.btn_q_shuffle.setFixedSize(32, 32)
        self.btn_q_shuffle.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")
        self.btn_q_shuffle.setToolTip("Losuj")

        self.btn_q_clear = HoverIconButton('fa5s.trash-alt', hover_color=THEME['accent'], icon_size=14)
        self.btn_q_clear.setFixedSize(32, 32)
        self.btn_q_clear.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_remove_hover']}; }}")
        self.btn_q_clear.setToolTip("Wyczyść kolejkę")

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

    def toggle_queue_visibility(self):
        if not hasattr(self, 'queue_anim'):
            self.queue_anim = QPropertyAnimation(self.queue_frame, b"maximumWidth")
            self.queue_anim.setDuration(400)
            self.queue_anim.setEasingCurve(QEasingCurve.InOutCubic)

            effect = QGraphicsOpacityEffect(self.queue_frame)
            self.queue_frame.setGraphicsEffect(effect)
            self.queue_fade = QPropertyAnimation(effect, b"opacity")
            self.queue_fade.setDuration(300)
            self.queue_fade.setEasingCurve(QEasingCurve.InOutQuad)

            self.spacer_anim = QPropertyAnimation(self.right_spacer, b"minimumWidth")
            self.spacer_anim.setDuration(400)
            self.spacer_anim.setEasingCurve(QEasingCurve.InOutCubic)

            self.is_queue_hidden = False

        self.queue_anim.stop()
        self.queue_fade.stop()
        self.spacer_anim.stop()

        try:
            self.queue_anim.finished.disconnect()
        except Exception:
            pass

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

            def hide_after():
                self.queue_frame.hide()
                try:
                    self.right_spacer.setFixedWidth(self.mapTo(self.window(), QPoint(0, 0)).x())
                except Exception:
                    pass

            self.queue_anim.finished.connect(hide_after)

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

            def restore_after():
                self.queue_frame.setMaximumWidth(16777215)
                self.right_spacer.setFixedWidth(0)

            self.queue_anim.finished.connect(restore_after)

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