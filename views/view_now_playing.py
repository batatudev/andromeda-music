# WERSJA PROJEKTU: 14.8
# MODYFIKOWANY PLIK: view_now_playing.py
# OPIS ZMIAN: Detekcja ruchu wideo przeniesiona do wątku daemon.
# Bajty QImage kopiowane bezpiecznie na wątku głównym, porównanie w tle,
# wynik wraca przez QTimer.singleShot(0). Eliminacja blokującej pętli pikselowej.

import os
os.environ["QT_API"] = "pyside6"

import threading
import qtawesome as qta

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsOpacityEffect, QStackedLayout, QScrollArea, QSizePolicy
from PySide6.QtMultimedia import QVideoSink
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect, Property
from PySide6.QtGui import QPainter, QImage

from config import THEME, APP_CONFIG
from ui.widgets import DragDropContainer, RoundedImage, ClickableLabel, HoverIconButton
from ui.components import SongItem

class VideoBackgroundWidget(QWidget):
    video_type_detected = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.current_image = None
        self.snapshot_image = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.frames_received = 0
        self.reference_frame = None
        self.last_motion_score = 0.0

        self.fps_counter = 0
        self.current_fps = 0
        self.actual_resolution = "Brak"

        self._crossfade = 0.0
        self.crossfade_anim = QPropertyAnimation(self, b"crossfade")
        self.crossfade_anim.setDuration(1200)
        self.crossfade_anim.setStartValue(1.0)
        self.crossfade_anim.setEndValue(0.0)

        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._update_fps)
        self.fps_timer.start(500)

    @Property(float)
    def crossfade(self):
        return self._crossfade

    @crossfade.setter
    def crossfade(self, val):
        self._crossfade = val
        self.update()

    def prepare_snapshot(self):
        if self.current_image and not self.current_image.isNull():
            self.snapshot_image = self.current_image.copy()
        self._crossfade = 1.0
        self.current_image = None
        self.frames_received = 0
        self.reference_frame = None
        self.last_motion_score = 0.0
        self.current_fps = 0
        self.fps_counter = 0
        self.actual_resolution = "Brak"
        self.update()

    def clear(self):
        self.current_image = None
        self.snapshot_image = None
        self._crossfade = 0.0
        self.frames_received = 0
        self.reference_frame = None
        self.last_motion_score = 0.0
        self.current_fps = 0
        self.fps_counter = 0
        self.actual_resolution = "Brak"
        self.update()

    def _update_fps(self):
        self.current_fps = self.fps_counter * 2
        self.fps_counter = 0

    def _calculate_difference_threaded(self, ref_bytes, cur_bytes):
        """Uruchamiana w wątku daemon. Porównuje bajty dwóch obrazów 32x32."""
        total = sum(abs(ref_bytes[i] - cur_bytes[i]) for i in range(len(ref_bytes)))
        diff = total / max(len(ref_bytes), 1)
        return diff

    def _on_frame(self, frame):
        if frame.isValid():
            try:
                size = frame.size()
                if size.width() > 0 and size.height() > 0:
                    self.actual_resolution = f"{size.width()}x{size.height()}"

                self.fps_counter += 1
                self.current_image = frame.toImage()
                
                if self._crossfade > 0 and self.crossfade_anim.state() != QPropertyAnimation.State.Running:
                    self.crossfade_anim.start()
                    
                self.update()

                self.frames_received += 1
                cycle_frame = self.frames_received % 150
                
                if cycle_frame == 45:
                    self.reference_frame = (
                        self.current_image
                        .scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        .convertToFormat(QImage.Format_Grayscale8)
                    )
                elif cycle_frame == 90 and self.reference_frame:
                    current_small = (
                        self.current_image
                        .scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        .convertToFormat(QImage.Format_Grayscale8)
                    )
                    # Kopiujemy bajty na wątku głównym (bezpieczny dostęp do QImage)
                    # i przekażujemy surowe bajty do wątku tła (brak obiektów Qt)
                    try:
                        ref_bytes = bytes(self.reference_frame.bits())
                        cur_bytes = bytes(current_small.bits())
                    except Exception:
                        ref_bytes = None
                        cur_bytes = None

                    if ref_bytes and cur_bytes and len(ref_bytes) == len(cur_bytes):
                        def _run_diff(rb, cb):
                            diff = self._calculate_difference_threaded(rb, cb)
                            self.last_motion_score = diff
                            is_dynamic = diff > 6.0
                            QTimer.singleShot(0, lambda d=is_dynamic: self.video_type_detected.emit(d))
                        threading.Thread(
                            target=_run_diff,
                            args=(ref_bytes, cur_bytes),
                            daemon=True
                        ).start()
            except Exception:
                pass

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect()

        has_current = self.current_image and not self.current_image.isNull()
        has_snapshot = self.snapshot_image and not self.snapshot_image.isNull()

        if has_current:
            img_size = self.current_image.size()
            scale = max(rect.width() / img_size.width(), rect.height() / img_size.height())
            new_w = int(img_size.width() * scale)
            new_h = int(img_size.height() * scale)
            x = (rect.width() - new_w) // 2
            y = (rect.height() - new_h) // 2
            p.drawImage(QRect(x, y, new_w, new_h), self.current_image)

        if has_snapshot and self._crossfade > 0:
            p.setOpacity(self._crossfade)
            img_size = self.snapshot_image.size()
            scale = max(rect.width() / img_size.width(), rect.height() / img_size.height())
            new_w = int(img_size.width() * scale)
            new_h = int(img_size.height() * scale)
            x = (rect.width() - new_w) // 2
            y = (rect.height() - new_h) // 2
            p.drawImage(QRect(x, y, new_w, new_h), self.snapshot_image)
            p.setOpacity(1.0)

class NowPlayingWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("NowPlayingWidget")
        self.is_video_dynamic = True
        self.raw_pixmap = None

        self.bg_container = QWidget(self)
        self.bg_layout = QStackedLayout(self.bg_container)
        self.bg_layout.setStackingMode(QStackedLayout.StackOne)

        self.bg_label = QLabel()
        self.bg_label.setScaledContents(True)

        self.video_widget = VideoBackgroundWidget()
        self.video_widget.video_type_detected.connect(self._on_video_type_detected)

        self.bg_layout.addWidget(self.bg_label)
        self.bg_layout.addWidget(self.video_widget)
        self.bg_layout.setCurrentWidget(self.bg_label)

        self.overlay = QLabel(self)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.overlay_opacity = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(self.overlay_opacity)
        
        self.breath_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.breath_anim.setDuration(2400)
        self.breath_anim.setKeyValueAt(0.0, 1.0)
        self.breath_anim.setKeyValueAt(0.5, 0.4)
        self.breath_anim.setKeyValueAt(1.0, 1.0)
        self.breath_anim.setLoopCount(-1)

        self.breath_restore_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.breath_restore_anim.setDuration(800)
        self.breath_restore_anim.setEndValue(1.0)
        self.breath_restore_anim.setEasingCurve(QEasingCurve.OutCubic)

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

        self.right_layout = QVBoxLayout()
        
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

        self.queue_scroll = QScrollArea()
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
        self.right_layout.addWidget(self.queue_frame)

        self.main_layout.addLayout(self.left_layout, 3)
        self.main_layout.addLayout(self.right_layout, 2)
        self.update_video_settings()

    def resizeEvent(self, e):
        self.bg_container.resize(self.size())
        self.overlay.resize(self.size())
        self.ui_container.resize(self.size())
        super().resizeEvent(e)

    def _on_video_type_detected(self, is_dynamic):
        if self.is_video_dynamic != is_dynamic:
            self.is_video_dynamic = is_dynamic
            self.update_video_settings()

    def set_seek_blur(self, is_seeking):
        if not is_seeking:
            self.set_buffering_state(False)

    def set_buffering_state(self, is_buffering):
        if is_buffering:
            self.breath_restore_anim.stop()
            if self.breath_anim.state() != QPropertyAnimation.State.Running:
                self.overlay_opacity.setOpacity(1.0)
                self.breath_anim.start()
        else:
            self.breath_anim.stop()
            self.breath_restore_anim.stop()
            curr_op = self.overlay_opacity.opacity()
            self.breath_restore_anim.setStartValue(curr_op)
            self.breath_restore_anim.start()

    def set_image(self, p, animate=True):
        self.is_video_dynamic = True
        self.video_widget.prepare_snapshot()
        self.img.set_image(p, animate)
        self.raw_pixmap = p
        if not p or p.isNull():
            self.bg_label.clear()
        self.update_video_settings()

    def update_video_settings(self):
        if self.bg_layout.currentWidget() == self.video_widget:
            if self.is_video_dynamic:
                opacity = APP_CONFIG.get("video_dynamic_opacity", 30)
            else:
                opacity = APP_CONFIG.get("video_static_opacity", 80)

            alpha = int((opacity / 100.0) * 255)
            self.overlay.setStyleSheet(f"background: rgba({THEME['bg_main_rgb']}, {alpha});")
        else:
            opacity = APP_CONFIG.get("video_static_opacity", 80)
            blur_val = APP_CONFIG.get("video_static_blur", 60)
            alpha = int((opacity / 100.0) * 255)
            self.overlay.setStyleSheet(f"background: rgba({THEME['bg_main_rgb']}, {alpha});")
            if hasattr(self, 'raw_pixmap') and self.raw_pixmap and not self.raw_pixmap.isNull():
                from utils import get_blurred_pixmap
                blurred = get_blurred_pixmap(self.raw_pixmap, blur_val)
                self.bg_label.setPixmap(blurred)

    def set_media_mode(self, mode):
        if mode == "video":
            self.bg_layout.setCurrentWidget(self.video_widget)
        else:
            self.video_widget.clear()
            self.bg_layout.setCurrentWidget(self.bg_label)

        self.update_video_settings()
        self.bg_container.lower()
        self.overlay.raise_()
        self.ui_container.raise_()