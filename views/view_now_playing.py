import os
os.environ["QT_API"] = "pyside6"

import sys
import qtawesome as qta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QStackedLayout, QSizePolicy
)
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer, QUrl, Property
from PySide6.QtGui import QPainter, QColor

from config import THEME, APP_CONFIG
from core.paths import PathsManager
from ui.widgets import DragDropContainer, RoundedImage, ClickableLabel, HoverIconButton, SmoothScrollArea
from ui.components import SongItem
from core.i18n import tr

QML_BACKGROUND_CODE = """
import QtQuick
import QtQuick.Effects
import QtMultimedia

Item {
    id: root
    anchors.fill: parent

    property alias videoSink: videoOutput.videoSink
    property alias videoOutputItem: videoOutput
    property real blurStrength: 0.0

    // Ciemne tło zapobiegające białym przebłyskom z domyślnego bufora FBO
    Rectangle {
        anchors.fill: parent
        color: "#050505"
        z: -2
    }

    // 1. Warstwa wideo (GPU zero-copy) z marginesem -24px, by shader nie próbkował krawędzi
    VideoOutput {
        id: videoOutput
        anchors.fill: parent
        anchors.margins: -24
        fillMode: VideoOutput.PreserveAspectCrop
        visible: root.blurStrength <= 0.01
    }

    // 2. Warstwa MultiEffect (kinowy GPU shader blur)
    MultiEffect {
        id: blurEffect
        anchors.fill: parent
        anchors.margins: -24
        source: videoOutput
        visible: root.blurStrength > 0.01
        blurEnabled: root.blurStrength > 0.01
        blur: root.blurStrength
        blurMax: 64
        autoPaddingEnabled: false
    }
}
"""

class VideoQuickWidget(QQuickWidget):
    """
    Sprzętowo akcelerowany widżet wideo oparty o QtQuick / Qt RHI.
    Renderuje wideo zdekodowane przez VA-API bezpośrednio na GPU i aplikuje
    kinowy GLSL blur shader w jednym przejściu (Zero CPU overhead).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_fps = 30
        self.last_motion_score = 1.0
        self._target_sink = None

        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.setAttribute(Qt.WA_AlwaysStackOnTop, False)
        self.setClearColor(QColor(5, 5, 5))
        self.setStyleSheet("background: #050505; border: none;")

        qml_path = PathsManager.get_cache_dir() / "video_background.qml"
        try:
            qml_path.write_text(QML_BACKGROUND_CODE.strip(), encoding="utf-8")
        except Exception:
            pass

        self.setSource(QUrl.fromLocalFile(str(qml_path)))
        self.statusChanged.connect(self._on_status_changed)

    def _on_status_changed(self, status):
        if status == QQuickWidget.Status.Ready:
            root = self.rootObject()
            if root:
                self._target_sink = root.property("videoSink")

    @property
    def video_item(self):
        """Zwraca interfejs wejścia wideo dla QMediaPlayer."""
        if self._target_sink:
            return self._target_sink
        root = self.rootObject()
        if root:
            sink = root.property("videoSink")
            if sink:
                self._target_sink = sink
                return sink
            item = root.property("videoOutputItem")
            if item:
                return item
        return None

    def set_blur(self, blur_ratio: float):
        root = self.rootObject()
        if root:
            root.setProperty("blurStrength", float(blur_ratio))

VideoGraphicsView = VideoQuickWidget

class DimOverlay(QWidget):
    """
    Lekka, sprzętowo zoptymalizowana nakładka przyciemniająca.
    Eliminuje powolny filtr programowy QGraphicsOpacityEffect, rysując
    kolor o zadanym kanale alfa w jednej instrukcji fillRect na GPU.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._opacity = 0.3

    @Property(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, val):
        self._opacity = max(0.0, min(1.0, float(val)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        r = 5
        g = 5
        b = 5
        try:
            rgb_str = THEME.get('bg_main_rgb', '5,5,5')
            parts = [int(p.strip()) for p in rgb_str.split(',')]
            if len(parts) == 3:
                r, g, b = parts
        except Exception:
            pass
        alpha = int(self._opacity * 255)
        painter.fillRect(self.rect(), QColor(r, g, b, alpha))
        painter.end()

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

        self.video_widget = VideoQuickWidget(self)

        self.bg_layout.addWidget(self.bg_label)
        self.bg_layout.addWidget(self.video_widget)
        self.bg_layout.setCurrentWidget(self.bg_label)

        self.overlay = DimOverlay(self)

        self.breath_anim = QPropertyAnimation(self.overlay, b"opacity")
        self.breath_anim.setDuration(2400)
        self.breath_anim.setLoopCount(-1)

        self.breath_restore_anim = QPropertyAnimation(self.overlay, b"opacity")
        self.breath_restore_anim.setDuration(800)
        self.breath_restore_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.crossfade_anim = QPropertyAnimation(self.overlay, b"opacity")
        self.crossfade_anim.setDuration(500)
        self.crossfade_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.crossfade_anim.finished.connect(self._on_crossfade_finished)

        self._dim_base = 0.3
        self._crossfade_callback = None
        self._crossfade_target_mode = None

        self.ui_container = QWidget(self)
        self.ui_container.setObjectName("NowPlayingUiContainer")

        self.bg_container.lower()
        self.overlay.raise_()
        self.ui_container.raise_()

        self.main_layout = QHBoxLayout(self.ui_container)
        self.main_layout.setContentsMargins(50, 50, 50, 50)
        self.main_layout.setSpacing(40)

        self.left_layout = QVBoxLayout()
        self.left_layout.setAlignment(Qt.AlignCenter)

        self.media_container = QWidget()
        self.media_container.setObjectName("NowPlayingMediaContainer")
        self.media_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.media_container.setMinimumSize(400, 300)

        self.media_layout = QVBoxLayout(self.media_container)
        self.media_layout.setContentsMargins(0, 0, 0, 0)

        self.art_wrapper = QWidget()
        self.art_wrapper.setObjectName("NowPlayingArtWrapper")
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
        self.queue_scroll.setObjectName("NowPlayingQueueScroll")
        self.queue_scroll.setWidgetResizable(True)
        self.queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.queue_scroll.viewport().setAttribute(Qt.WA_TranslucentBackground, True)

        self.queue_content = DragDropContainer()
        self.queue_content.setObjectName("NowPlayingQueueContent")
        self.queue_layout = QVBoxLayout(self.queue_content)
        self.queue_layout.setAlignment(Qt.AlignTop)
        self.queue_layout.setContentsMargins(0, 10, 0, 10)
        self.queue_scroll.setWidget(self.queue_content)

        qf_layout.addWidget(self.queue_scroll)

        self.main_layout.addLayout(self.left_layout, 3)
        self.main_layout.addWidget(self.queue_frame, 2)

        self.right_spacer = QWidget()
        self.right_spacer.setObjectName("NowPlayingRightSpacer")
        self.right_spacer.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.right_spacer.setFixedWidth(0)
        self.main_layout.addWidget(self.right_spacer)

        self.update_video_settings()

    def update_queue(self, songs, active_idx, handlers, loader, client):
        """
        Buduje listę utworów w widżecie kolejki z zachowaniem scrolla.
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

            from PySide6.QtWidgets import QGraphicsOpacityEffect
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
                base = self.overlay.opacity
                self.breath_anim.setKeyValueAt(0.0, base)
                self.breath_anim.setKeyValueAt(0.5, base * 0.4)
                self.breath_anim.setKeyValueAt(1.0, base)
                self.breath_anim.start()
        else:
            self.breath_anim.stop()
            self.breath_restore_anim.stop()
            curr_op = self.overlay.opacity
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

            if "--force-opacity" in sys.argv:
                try:
                    idx = sys.argv.index("--force-opacity")
                    if idx + 1 < len(sys.argv):
                        opacity = int(sys.argv[idx + 1])
                except Exception:
                    pass

            if "--force-blur" in sys.argv:
                try:
                    idx = sys.argv.index("--force-blur")
                    if idx + 1 < len(sys.argv):
                        blur_val = int(sys.argv[idx + 1])
                except Exception:
                    pass

            self._dim_base = opacity / 100.0
            self.overlay.opacity = self._dim_base

            if blur_val > 0:
                blur_ratio = min(1.0, (blur_val / 100.0) ** 0.55)
            else:
                blur_ratio = 0.0
            self.video_widget.set_blur(blur_ratio)
        else:
            opacity = APP_CONFIG.get("video_static_opacity", 80)
            blur_val = APP_CONFIG.get("video_static_blur", 60)

            self._dim_base = opacity / 100.0
            self.overlay.opacity = self._dim_base

            if hasattr(self, 'raw_pixmap') and self.raw_pixmap and not self.raw_pixmap.isNull():
                if (
                    self._cached_blurred_pixmap is not None
                    and self._cached_blur_raw is self.raw_pixmap
                    and self._cached_blur_val == blur_val
                ):
                    self.bg_label.setPixmap(self._cached_blurred_pixmap)
                else:
                    if blur_val <= 0:
                        self._cached_blurred_pixmap = self.raw_pixmap
                        self._cached_blur_raw = self.raw_pixmap
                        self._cached_blur_val = 0
                        self.bg_label.setPixmap(self.raw_pixmap)
                    else:
                        from utils import get_blurred_pixmap
                        effective_blur = max(1, int(blur_val * 0.21))
                        blurred = get_blurred_pixmap(self.raw_pixmap, effective_blur)
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
        curr = self.overlay.opacity
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
        curr = self.overlay.opacity
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