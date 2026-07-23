import os
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer
from config import THEME

class TelemetryWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        self.setWindowTitle("Diagnostyka Systemu")
        self.setFixedSize(520, 980)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        self.setStyleSheet(f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; border-radius: 8px;")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)
        self.layout.setContentsMargins(25, 20, 25, 20)
        self.layout.setSpacing(6)
        
        title = QLabel("Telemetry 3.2")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME['accent']}; border-bottom: 1px solid {THEME['border']}; padding-bottom: 5px;")
        self.layout.addWidget(title)
        
        self.labels = {}
        
        def add_metric(key, label_text):
            row = QHBoxLayout()
            lbl_name = QLabel(label_text)
            lbl_name.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; font-weight: bold;")
            lbl_val = QLabel("-")
            lbl_val.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right;")
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_val)
            self.layout.addLayout(row)
            self.labels[key] = lbl_val

        def add_section_header(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {THEME['accent']}; font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-top: 10px;")
            self.layout.addWidget(lbl)

        def add_separator():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"background-color: {THEME['border']}; margin: 2px 0px;")
            self.layout.addWidget(line)

        add_section_header("ŁĄCZNOŚĆ I OPÓŹNIENIA")
        add_metric("net_link", "Dostęp do Internetu:")
        add_metric("net_ping", "Globalne Opóźnienie (ICMP):")
        add_metric("loc_lat", "Opóźnienie Serwera (RTT):")
        
        add_separator()

        add_section_header("SYNCHRONIZACJA I BUFOROWANIE")
        add_metric("state", "Status Odtwarzania:")
        add_metric("sync_lock", "Stabilizacja Obrazu:")
        add_metric("av_sync", "Desynchronizacja (Delta A/V):")
        add_metric("rate", "Korekta Prędkości (Soft-Sync):")
        add_metric("h_sync", "Korekty Twarde (Hard-Sync):")
        add_metric("grace", "Czas Ochronny Bufora:")
        add_metric("v_health", "Zapas Sekundowy Bufora:")
        
        add_separator()
        
        add_section_header("ANALIZA STRUMIENIA WIDEO")
        add_metric("fps", "Tempo Renderowania (FPS):")
        add_metric("z_fps", "Zanik Ciągłości Strumienia:")
        add_metric("res_conf", "Rozdzielczość (Target):")
        add_metric("res_act", "Rozdzielczość Adaptacyjna:")
        add_metric("motion", "Wskaźnik Dynamiki (Motion):")
        add_metric("filter", "Warstwa Wizualna:")
        add_metric("resolve", "Czas Przygotowania Wideo:")
        
        add_separator()

        add_section_header("ZASOBY I WYDAJNOŚĆ")
        add_metric("v_buf", "Status Dekodera Wideo:")
        add_metric("a_buf", "Status Dekodera Audio:")
        add_metric("img_q", "Kolejka Obrazów Pamięci:")
        add_metric("threads", "Zajętość Wątków I/O:")
        
        add_separator()

        add_section_header("STAN TECHNICZNY (DIAGNOSTYKA)")
        add_metric("arf_profile", "Aktywny Profil ARF:")
        add_metric("drop_rate", "Wskaźnik Gubionych Klatek:")
        add_metric("recoveries", "Ilość Przywróceń Strumienia:")
        
        add_separator()
        
        add_section_header("POBIERANIE WIDEO (YT-DLP)")
        add_metric("dl_active", "Aktywne pobierania:")
        add_metric("dl_queue", "Oczekujące:")
        add_metric("dl_speed", "Prędkość pobierania:")
        add_metric("dl_health", "Status silnika:")

        self.layout.addStretch()
        
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(100)

    def _update_stats(self):
        engine = self.main_window.engine
        
        try:
            from core.telemetry_service import get_telemetry
            t_data = get_telemetry()
            
            for key, val in t_data.items():
                if key in self.labels:
                    self.labels[key].setText(str(val))
        except Exception:
            pass

    def closeEvent(self, event):
        self.update_timer.stop()
        if hasattr(self.parent(), 'telemetry_window'):
            self.parent().telemetry_window = None
        event.accept()
