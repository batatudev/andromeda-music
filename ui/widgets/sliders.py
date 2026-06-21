# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: ui/widgets/sliders.py
# OPIS ZMIAN: Wyodrębnienie PremiumSlider z ui_core.py.

import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QSlider
from PySide6.QtCore import Qt

from config import THEME

class PremiumSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)
        self._is_hovered = False
        self.setFixedHeight(20)
        self._update_style()

    def enterEvent(self, e):
        self._is_hovered = True
        self._update_style()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._is_hovered = False
        self._update_style()
        super().leaveEvent(e)

    def _update_style(self):
        if self._is_hovered:
            self.setStyleSheet(f"""
                QSlider {{ background: transparent; }}
                QSlider::groove:horizontal {{ height: 6px; background: {THEME['nav_bg']}; border-radius: 3px; }}
                QSlider::sub-page:horizontal {{ background: {THEME['accent']}; border-radius: 3px; }}
                QSlider::handle:horizontal {{ background: {THEME['text_main']}; width: 12px; height: 12px; margin: -3px 0; border-radius: 6px; }}
            """)
        else:
            self.setStyleSheet(f"""
                QSlider {{ background: transparent; }}
                QSlider::groove:horizontal {{ height: 4px; background: {THEME['bg_main']}; border-radius: 2px; }}
                QSlider::sub-page:horizontal {{ background: {THEME['text_main']}; border-radius: 2px; }}
                QSlider::handle:horizontal {{ width: 0px; height: 0px; margin: 0px; }}
            """)
