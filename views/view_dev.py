import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QPushButton
)
from PySide6.QtCore import Qt

from config import THEME

from views.dev.tab_telemetry import TabTelemetry
from views.dev.tab_logs import TabLogs

class DevModeView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(15)

        center_widget = QWidget()
        center_widget.setMaximumWidth(800)
        center_widget.setMinimumWidth(600)
        center_lay = QVBoxLayout(center_widget)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(20)

        header_lay = QHBoxLayout()
        lbl_title = QLabel("Tryb Dewelopera")
        lbl_title.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {THEME['text_main']}; background: transparent;")
        header_lay.addWidget(lbl_title)
        
        lbl_version = QLabel("Andromeda Music")
        lbl_version.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; background: transparent;")
        header_lay.addStretch()
        header_lay.addWidget(lbl_version)
        
        center_lay.addLayout(header_lay)

        tab_bar_lay = QHBoxLayout()
        tab_bar_lay.setSpacing(10)
        
        self.buttons = []
        self.stacked_widget = QStackedWidget()

        tabs_info = [
            ("Telemetria", TabTelemetry),
            ("Pamięć i Logi", TabLogs)
        ]

        for i, (name, WidgetClass) in enumerate(tabs_info):
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME['bg_card']};
                    color: {THEME['text_main']};
                    padding: 8px 16px;
                    border-radius: 15px;
                    font-weight: bold;
                    border: 1px solid transparent;
                }}
                QPushButton:hover {{
                    background-color: {THEME['nav_bg']};
                }}
                QPushButton:checked {{
                    background-color: {THEME['accent']};
                    color: white;
                }}
            """)
            
            btn.clicked.connect(lambda checked, index=i: self._switch_tab(index))
            tab_bar_lay.addWidget(btn)
            self.buttons.append(btn)
            
            tab_widget = WidgetClass(self)
            self.stacked_widget.addWidget(tab_widget)

        tab_bar_lay.addStretch()
        center_lay.addLayout(tab_bar_lay)
        center_lay.addWidget(self.stacked_widget)

        wrap_lay = QHBoxLayout()
        wrap_lay.addStretch()
        wrap_lay.addWidget(center_widget)
        wrap_lay.addStretch()

        self.main_layout.addLayout(wrap_lay)
        self.main_layout.addStretch()

    def _switch_tab(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.stacked_widget.setCurrentIndex(index)