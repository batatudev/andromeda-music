import os
os.environ["QT_API"] = "pyside6"

import shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices

from config import THEME
from utils import logger, telemetry_recorder
from core.paths import PathsManager

class TabLogs(QWidget):
    def __init__(self, dev_view):
        super().__init__()
        self.dev_view = dev_view

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(16)

        card_style = (
            f"#DevCard {{ background-color: {THEME['bg_card']}; border-radius: 12px; "
            f"padding: 24px 30px; border: 1px solid {THEME['border']}; }}"
        )

        cache_group = QFrame()
        cache_group.setObjectName("DevCard")
        cache_group.setStyleSheet(card_style)
        cache_layout = QVBoxLayout(cache_group)
        cache_layout.setSpacing(10)

        cache_title = QLabel("Pamięć Podręczna Okładek")
        cache_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        cache_layout.addWidget(cache_title)

        self.cache_size_lbl = QLabel("Obliczanie rozmiaru...")
        self.cache_size_lbl.setStyleSheet(
            f"color: {THEME['text_muted']}; font-size: 13px; background: transparent; margin-bottom: 6px;"
        )
        cache_layout.addWidget(self.cache_size_lbl)

        btn_clear_cache = QPushButton("Opróżnij Cache")
        btn_clear_cache.setMinimumWidth(180)
        btn_clear_cache.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_clear_cache.setStyleSheet(f"""
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
        btn_clear_cache.setCursor(Qt.PointingHandCursor)
        btn_clear_cache.clicked.connect(self._clear_cache)
        cache_layout.addWidget(btn_clear_cache)

        self.layout.addWidget(cache_group)

        path_group = QFrame()
        path_group.setObjectName("DevCard")
        path_group.setStyleSheet(card_style)
        path_layout = QVBoxLayout(path_group)
        path_layout.setSpacing(10)

        path_title = QLabel("Ścieżki Systemowe (XDG)")
        path_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        path_layout.addWidget(path_title)

        cfg_path = str(PathsManager.get_config_file())
        cache_path = str(PathsManager.get_images_cache_dir())
        log_path = logger.log_file
        tele_path = telemetry_recorder.log_file

        paths_txt = (
            f"<b>Konfiguracja:</b> {cfg_path}<br><br>"
            f"<b>Okładki:</b> {cache_path}<br><br>"
            f"<b>Dziennik Błędów:</b> {log_path}<br><br>"
            f"<b>Zrzut Telemetrii:</b> {tele_path}"
        )
        paths_lbl = QLabel(paths_txt)
        paths_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; background: transparent;")
        paths_lbl.setWordWrap(True)
        path_layout.addWidget(paths_lbl)

        self.layout.addWidget(path_group)

        log_group = QFrame()
        log_group.setObjectName("DevCard")
        log_group.setStyleSheet(card_style)
        log_layout = QVBoxLayout(log_group)
        log_layout.setSpacing(10)

        log_title = QLabel("Dziennik Zdarzeń")
        log_title.setStyleSheet(
            f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 4px; background: transparent;"
        )
        log_layout.addWidget(log_title)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {THEME['bg_main']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 10px;
                font-family: monospace;
            }}
        """)
        self.log_text.setFixedHeight(180)
        log_layout.addWidget(self.log_text)

        log_btns = QHBoxLayout()
        log_btns.setSpacing(10)

        btn_style_nav = f"""
            QPushButton {{
                background-color: {THEME['nav_bg']};
                color: {THEME['text_main']};
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME['nav_hover']};
            }}
        """

        btn_refresh_logs = QPushButton("Odśwież")
        btn_refresh_logs.setMinimumWidth(90)
        btn_refresh_logs.setCursor(Qt.PointingHandCursor)
        btn_refresh_logs.setStyleSheet(btn_style_nav)
        btn_refresh_logs.clicked.connect(self._refresh_logs)

        btn_open_logs = QPushButton("Otwórz plik")
        btn_open_logs.setMinimumWidth(100)
        btn_open_logs.setCursor(Qt.PointingHandCursor)
        btn_open_logs.setStyleSheet(btn_style_nav)
        btn_open_logs.clicked.connect(self._open_logs)

        btn_clear_logs = QPushButton("Wyczyść historię")
        btn_clear_logs.setMinimumWidth(120)
        btn_clear_logs.setCursor(Qt.PointingHandCursor)
        btn_clear_logs.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent']};
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_clear_logs.clicked.connect(self._clear_logs)

        log_btns.addWidget(btn_refresh_logs)
        log_btns.addWidget(btn_open_logs)
        log_btns.addWidget(btn_clear_logs)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)

        self.layout.addWidget(log_group)
        self.layout.addStretch()

        QTimer.singleShot(100, self._calculate_cache)
        self._refresh_logs()

    def _calculate_cache(self):
        cache_dir = str(PathsManager.get_images_cache_dir())
        total_size = 0
        if os.path.exists(cache_dir):
            for dirpath, _, filenames in os.walk(cache_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        mb = total_size / (1024 * 1024)
        self.cache_size_lbl.setText(f"Aktualny rozmiar na dysku: <b>{mb:.2f} MB</b>")

    def _clear_cache(self):
        cache_dir = str(PathsManager.get_images_cache_dir())
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
        self._calculate_cache()

    def _refresh_logs(self):
        logger.flush()
        self.log_text.setText("\n".join(logger.session_logs))
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _open_logs(self):
        logger.flush()
        QDesktopServices.openUrl(QUrl.fromLocalFile(logger.log_file))

    def _clear_logs(self):
        logger.clear_logs()
        self._refresh_logs()