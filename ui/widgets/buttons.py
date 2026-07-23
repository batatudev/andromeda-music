import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property

from config import THEME

class HoverIconButton(QPushButton):
    def __init__(self, icon_name, default_color=THEME["text_muted"], hover_color="white", icon_size=16, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_name = icon_name
        self.default_color = default_color
        self.hover_color = hover_color
        self.base_icon_size = icon_size
        self._scale = 1.0
        
        self.setIcon(qta.icon(self.icon_name, color=self.default_color))
        self.setIconSize(QSize(self.base_icon_size, self.base_icon_size))
        self.setCursor(Qt.PointingHandCursor)
        
        self.anim = QPropertyAnimation(self, b"iconScale")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.OutBack)

    @Property(float)
    def iconScale(self):
        return self._scale

    @iconScale.setter
    def iconScale(self, val):
        self._scale = val
        new_size = int(self.base_icon_size * val)
        self.setIconSize(QSize(new_size, new_size))

    def set_default_color(self, color):
        self.default_color = color
        self.setIcon(qta.icon(self.icon_name, color=self.default_color))

    def update_icon(self, icon_name):
        self.icon_name = icon_name
        self.setIcon(qta.icon(self.icon_name, color=self.default_color))

    def enterEvent(self, e):
        self.setIcon(qta.icon(self.icon_name, color=self.hover_color))
        self.anim.stop()
        self.anim.setEndValue(1.15)
        self.anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.setIcon(qta.icon(self.icon_name, color=self.default_color))
        self.anim.stop()
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().leaveEvent(e)
