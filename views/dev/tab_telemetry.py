import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from config import THEME, APP_CONFIG
from utils import telemetry_recorder
from core.i18n import tr
from views.dev.telemetry_window import TelemetryWindow

class TabTelemetry(QWidget):
    def __init__(self, dev_view):
        super().__init__()
        self.dev_view = dev_view
        self.main_window = dev_view.main_window
        self.telemetry_window = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(16)

        card_style = (
            f"#DevCard {{ background-color: {THEME['bg_card']}; border-radius: 12px; "
            f"padding: 24px 30px; border: 1px solid {THEME['border']}; }}"
        )

        live_group = QFrame()
        live_group.setObjectName("DevCard")
        live_group.setStyleSheet(card_style)
        live_layout = QVBoxLayout(live_group)
        live_layout.setSpacing(12)

        live_title = QLabel(tr("dev.telemetry.diag_title", "Panel diagnostyczny"))
        live_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        live_layout.addWidget(live_title)

        btn_open_telemetry = QPushButton(tr("dev.telemetry.btn_open_window", "Otwórz okno telemetrii"))
        btn_open_telemetry.setMinimumWidth(240)
        btn_open_telemetry.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_open_telemetry.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent']};
                color: white;
                padding: 9px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_open_telemetry.setCursor(Qt.PointingHandCursor)
        btn_open_telemetry.clicked.connect(self._open_telemetry)
        live_layout.addWidget(btn_open_telemetry)

        self.layout.addWidget(live_group)

        rec_group = QFrame()
        rec_group.setObjectName("DevCard")
        rec_group.setStyleSheet(card_style)
        rec_layout = QVBoxLayout(rec_group)
        rec_layout.setSpacing(12)

        rec_title = QLabel(tr("dev.telemetry.data_title", "Dane telemetryczne"))
        rec_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        rec_layout.addWidget(rec_title)

        btn_export = QPushButton(tr("dev.telemetry.btn_export_csv", "Eksportuj telemetrię na Pulpit (.csv)"))
        btn_export.setMinimumWidth(260)
        btn_export.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                padding: 9px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """)
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._export_telemetry)

        self.export_status_lbl = QLabel("")
        self.export_status_lbl.setStyleSheet(
            f"color: {THEME['accent']}; font-size: 13px; margin-left: 15px; font-weight: bold; background: transparent;"
        )

        rec_h = QHBoxLayout()
        rec_h.addWidget(btn_export)
        rec_h.addWidget(self.export_status_lbl)
        rec_h.addStretch()

        rec_layout.addLayout(rec_h)
        self.layout.addWidget(rec_group)

        sys_group = QFrame()
        sys_group.setObjectName("DevCard")
        sys_group.setStyleSheet(card_style)
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setSpacing(12)

        sys_title = QLabel(tr("dev.telemetry.env_title", "Środowisko uruchomieniowe"))
        sys_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        sys_layout.addWidget(sys_title)

        lbl_engine = tr("dev.telemetry.graphics_engine", "Silnik graficzny (Qt):")
        lbl_target = tr("dev.telemetry.target_server", "Serwer docelowy:")
        lbl_audio = tr("dev.telemetry.audio_channel", "Kanał audio:")
        none_str = tr("common.none", "Brak")
        server_url = APP_CONFIG.get('url', none_str) or none_str

        info_txt = f"""
        <b>{lbl_engine}</b> {os.environ.get('QT_API', 'pyside6').upper()}<br><br>
        <b>{lbl_target}</b> {server_url}<br><br>
        <b>{lbl_audio}</b> PulseAudio (Role=music)
        """
        sys_lbl = QLabel(info_txt)
        sys_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; background: transparent;")
        sys_layout.addWidget(sys_lbl)

        self.layout.addWidget(sys_group)
        self.layout.addStretch()

    def _clear_status_text(self):
        try:
            if hasattr(self, 'export_status_lbl') and self.export_status_lbl:
                self.export_status_lbl.setText("")
        except RuntimeError:
            pass

    def _export_telemetry(self):
        msg = telemetry_recorder.export_to_desktop()
        self.export_status_lbl.setText(msg)
        QTimer.singleShot(5000, self, self._clear_status_text)

    def _open_telemetry(self):
        if not self.telemetry_window:
            self.telemetry_window = TelemetryWindow(self.main_window)
        self.telemetry_window.show()