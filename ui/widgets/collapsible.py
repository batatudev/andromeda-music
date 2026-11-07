import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt
from config import THEME

class CollapsibleSection(QWidget):
    """
    Uniwersalny widżet sekcji zwijanej (nagłówek z przyciskiem + rozwijany kontener).
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        self.btn_toggle = QPushButton(title)
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                font-size: 16px;
                font-weight: bold;
                text-align: left;
                padding: 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {THEME['hover_card']};
            }}
        """)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle)
        self.layout.addWidget(self.btn_toggle)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 5, 10, 15)
        self.content_layout.setSpacing(10)
        self.layout.addWidget(self.content_widget)

    def toggle(self):
        self.content_widget.setVisible(not self.content_widget.isVisible())

    def addWidget(self, w):
        self.content_layout.addWidget(w)

    def clear(self):
        while self.content_layout.count():
            i = self.content_layout.takeAt(0)
            if i.widget():
                i.widget().deleteLater()