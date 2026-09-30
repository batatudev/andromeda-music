import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QPainterPath

from config import THEME


class RoundedImage(QWidget):
    def __init__(self, size=None, radius=8):
        super().__init__()
        self.radius = radius
        self.pixmap_cache = None
        self.prepared_pixmap = None
        self._zoom = 1.0
        self._opacity = 1.0
        self._zoom_anim = None
        self._opacity_anim = None

        if size:
            self.size_px = size
            self.setFixedSize(size, size)
        else:
            self.size_px = None

    def _ensure_zoom_anim(self):
        if self._zoom_anim is None:
            self._zoom_anim = QPropertyAnimation(self, b"zoom")
            self._zoom_anim.setDuration(250)
            self._zoom_anim.setEasingCurve(QEasingCurve.OutQuad)
        return self._zoom_anim

    def _ensure_opacity_anim(self):
        if self._opacity_anim is None:
            self._opacity_anim = QPropertyAnimation(self, b"opacity")
            self._opacity_anim.setDuration(400)
            self._opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        return self._opacity_anim

    @Property(float)
    def zoom(self):
        return self._zoom

    @zoom.setter
    def zoom(self, v):
        self._zoom = v
        self.update()

    @Property(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, v):
        self._opacity = v
        self.update()

    def set_hover(self, is_hover):
        anim = self._ensure_zoom_anim()
        anim.stop()
        anim.setEndValue(1.05 if is_hover else 1.0)
        anim.start()

    def set_image(self, pixmap, animate=True):
        self.pixmap_cache = pixmap
        self._prepare_pixmap()

        if animate:
            anim = self._ensure_opacity_anim()
            anim.stop()
            self._opacity = 0.0
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.start()
        else:
            self._opacity = 1.0
            self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._prepare_pixmap()

    def _prepare_pixmap(self):
        w = self.size_px if self.size_px else self.width()
        h = self.size_px if self.size_px else self.height()
        if w <= 0 or h <= 0:
            return

        pixmap = self.pixmap_cache
        if not pixmap or pixmap.isNull():
            pixmap = qta.icon('fa5s.music', color=THEME["text_muted"]).pixmap(w // 2, h // 2)

        scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        x_off = (scaled.width() - w) // 2
        y_off = (scaled.height() - h) // 2
        self.prepared_pixmap = scaled.copy(x_off, y_off, w, h)
        self.update()

    def paintEvent(self, e):
        if not self.prepared_pixmap:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(self._opacity)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.radius, self.radius)
        p.setClipPath(path)

        p.translate(self.width() / 2, self.height() / 2)
        p.scale(self._zoom, self._zoom)
        p.translate(-self.width() / 2, -self.height() / 2)

        p.drawPixmap(0, 0, self.prepared_pixmap)
        p.end()