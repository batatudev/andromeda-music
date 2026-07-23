import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from config import THEME, APP_CONFIG
from utils import telemetry_recorder
from views.dev.telemetry_window import TelemetryWindow

class TabTelemetry(QWidget):
    def __init__(self, dev_view):
        super().__init__()
        self.dev_view = dev_view
        self.main_window = dev_view.main_window
        self.telemetry_window = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(20)

        live_group = QFrame()
        live_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        live_layout = QVBoxLayout(live_group)
        
        live_title = QLabel("Panel Diagnostyczny")
        live_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        live_layout.addWidget(live_title)
        
        btn_open_telemetry = QPushButton("Otwórz okno telemetrii")
        btn_open_telemetry.setMinimumWidth(250)
        btn_open_telemetry.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_open_telemetry.setStyleSheet(f"background-color: {THEME['accent']}; color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold;")
        btn_open_telemetry.setCursor(Qt.PointingHandCursor)
        btn_open_telemetry.clicked.connect(self._open_telemetry)
        live_layout.addWidget(btn_open_telemetry)

        self.layout.addWidget(live_group)
        
        rec_group = QFrame()
        rec_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        rec_layout = QVBoxLayout(rec_group)
        
        rec_title = QLabel("Dane telemetryczne")
        rec_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        rec_layout.addWidget(rec_title)
        
        btn_export = QPushButton("Eksportuj telemetrię na Pulpit (.csv)")
        btn_export.setMinimumWidth(280)
        btn_export.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_export.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 10px 20px; border-radius: 5px; font-weight: bold;")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._export_telemetry)
        
        self.export_status_lbl = QLabel("")
        self.export_status_lbl.setStyleSheet(f"color: {THEME['accent']}; font-size: 13px; margin-left: 15px; font-weight: bold; background: transparent;")
        
        rec_h = QHBoxLayout()
        rec_h.addWidget(btn_export)
        rec_h.addWidget(self.export_status_lbl)
        rec_h.addStretch()
        
        rec_layout.addLayout(rec_h)
        self.layout.addWidget(rec_group)

        sys_group = QFrame()
        sys_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        sys_layout = QVBoxLayout(sys_group)
        
        sys_title = QLabel("Środowisko Uruchomieniowe")
        sys_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        sys_layout.addWidget(sys_title)
        
        info_txt = f"""
        <b>Silnik graficzny (Qt):</b> {os.environ.get('QT_API', 'pyside6').upper()}<br><br>
        <b>Serwer Docelowy:</b> {APP_CONFIG.get('url', 'Brak')}<br><br>
        <b>Kanał Audio:</b> PulseAudio (Role=music)
        """
        sys_lbl = QLabel(info_txt)
        sys_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; background: transparent;")
        sys_layout.addWidget(sys_lbl)
        
        self.layout.addWidget(sys_group)
        self.layout.addStretch()

    def _export_telemetry(self):
        msg = telemetry_recorder.export_to_desktop()
        self.export_status_lbl.setText(msg)
        QTimer.singleShot(5000, lambda: self.export_status_lbl.setText(""))

    def _open_telemetry(self):
        if not self.telemetry_window:
            self.telemetry_window = TelemetryWindow(self.main_window)
        self.telemetry_window.show()
