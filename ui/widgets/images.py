import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QPainterPath, QPixmap, QColor, QImage

from config import THEME
from ui.widgets.buttons import get_cached_icon

def is_navidrome_placeholder(image_or_pixmap) -> bool:
    """Niezawodna detekcja szarej gwiazdy Navidrome (analiza próbkowania achromatycznego)."""
    if not image_or_pixmap or image_or_pixmap.isNull():
        return False

    qimg = image_or_pixmap.toImage() if hasattr(image_or_pixmap, 'toImage') else image_or_pixmap
    if qimg.isNull():
        return False

    w = qimg.width()
    h = qimg.height()
    if w < 24 or h < 24:
        return False

    try:
        # Próbkowanie siatki 5x5 wewnątrz okręgu (25 punktów testowych)
        grey_samples = 0
        white_samples = 0
        chromatic_samples = 0
        valid_samples = 0

        step_x = max(1, w // 6)
        step_y = max(1, h // 6)

        for ix in range(1, 6):
            for iy in range(1, 6):
                px = ix * step_x
                py = iy * step_y
                col = qimg.pixelColor(px, py)

                if col.alpha() < 30:
                    continue

                valid_samples += 1
                r, g, b = col.red(), col.green(), col.blue()

                # Czy piksel ma nasycenie kolorystyczne (nie jest odcieniem szarości)
                if abs(r - g) > 12 or abs(g - b) > 12 or abs(r - b) > 12:
                    chromatic_samples += 1
                elif r > 240 and g > 240 and b > 240:
                    white_samples += 1
                elif 180 <= r <= 245 and 180 <= g <= 245 and 180 <= b <= 245:
                    grey_samples += 1

        # Rzeczywiste zdjęcia ludzi mają kolory (skóra, tło, cienie).
        # Placeholder Navidrome jest w 100% achromatyczny (tylko szary okrąg i biała gwiazda).
        if valid_samples >= 15 and chromatic_samples == 0:
            if white_samples >= 3 and grey_samples >= 5:
                return True

        return False
    except Exception:
        return False

class RoundedImage(QWidget):
    def __init__(self, size=None, radius=8, placeholder_icon=None, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.placeholder_icon = placeholder_icon
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
        if pixmap and not pixmap.isNull() and is_navidrome_placeholder(pixmap):
            self.pixmap_cache = None
        else:
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
            placeholder = QPixmap(w, h)
            placeholder.fill(Qt.transparent)

            painter = QPainter(placeholder)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            clip_path = QPainterPath()
            clip_path.addRoundedRect(0, 0, w, h, self.radius, self.radius)
            painter.setClipPath(clip_path)

            bg_color = QColor(THEME.get("nav_bg", "#222222"))
            painter.fillRect(0, 0, w, h, bg_color)

            if self.placeholder_icon:
                icon_name = self.placeholder_icon
            elif self.radius >= 30:
                icon_name = 'fa5s.user'
            else:
                icon_name = 'fa5s.music'

            icon_size = max(16, int(min(w, h) * 0.38))
            icon_color = THEME.get("text_muted", "#888888")
            icon_pix = get_cached_icon(icon_name, color=icon_color).pixmap(icon_size, icon_size)

            icon_x = (w - icon_size) // 2
            icon_y = (h - icon_size) // 2
            painter.drawPixmap(icon_x, icon_y, icon_pix)
            painter.end()

            self.prepared_pixmap = placeholder
            self.update()
            return

        scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        rounded = QPixmap(w, h)
        rounded.fill(Qt.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(0, 0, w, h, self.radius, self.radius)
        painter.setClipPath(clip_path)

        x_off = (scaled.width() - w) // 2
        y_off = (scaled.height() - h) // 2
        painter.drawPixmap(-x_off, -y_off, scaled)
        painter.end()

        self.prepared_pixmap = rounded
        self.update()

    def paintEvent(self, e):
        if not self.prepared_pixmap:
            return

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(self._opacity)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(0, 0, w, h, self.radius, self.radius)
        p.setClipPath(clip_path)

        if self._zoom != 1.0:
            p.translate(w / 2, h / 2)
            p.scale(self._zoom, self._zoom)
            p.translate(-w / 2, -h / 2)

        p.drawPixmap(0, 0, self.prepared_pixmap)
        p.end()