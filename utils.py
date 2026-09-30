import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtCore import QRunnable
from core.logger import logger, telemetry_recorder, AppLogger, TelemetryRecorder
from core.network_monitor import NetworkMonitor
from ui.image_loader import AsyncImageLoader
from core.models import MediaItem, Song, Album, Artist

_YT_LINK_OVERRIDES: dict = {}

def _set_yt_link_override(item_id: str, url):
    if url:
        _YT_LINK_OVERRIDES[item_id] = url
    else:
        _YT_LINK_OVERRIDES.pop(item_id, None)

class Worker(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.setAutoDelete(True)

    def run(self):
        self.fn()

def get_blurred_pixmap(pixmap, radius):
    if not pixmap or pixmap.isNull():
        return pixmap
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
    from PySide6.QtCore import Qt

    scaled = pixmap.scaledToWidth(800, Qt.SmoothTransformation)
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(scaled)
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(radius)
    item.setGraphicsEffect(blur)
    scene.addItem(item)

    result = QPixmap(scaled.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    scene.render(painter)
    painter.end()
    return result