# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: ui/widgets/images.py
# OPIS ZMIAN: Wyodrębnienie RoundedImage z ui_core.py.

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
        
        if size:
            self.size_px = size
            self.setFixedSize(size, size)
        else:
            self.size_px = None
            
        self.zoom_anim = QPropertyAnimation(self, b"zoom")
        self.zoom_anim.setDuration(250)
        self.zoom_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.opacity_anim = QPropertyAnimation(self, b"opacity")
        self.opacity_anim.setDuration(400)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)

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
        self.zoom_anim.stop()
        self.zoom_anim.setEndValue(1.05 if is_hover else 1.0)
        self.zoom_anim.start()

    def set_image(self, pixmap, animate=True):
        self.pixmap_cache = pixmap
        self._prepare_pixmap()
        
        if animate:
            self.opacity_anim.stop()
            self._opacity = 0.0
            self.opacity_anim.setStartValue(0.0)
            self.opacity_anim.setEndValue(1.0)
            self.opacity_anim.start()
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
