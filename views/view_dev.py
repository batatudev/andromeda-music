# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: view_dev.py
# OPIS ZMIAN: Poszerzenie okna telemetrii (do 520px) i całkowita zmiana nomenklatury parametrów na bardziej profesjonalną (inżynierską). Usunięcie żargonu programistycznego i dopisków. Zmiana wymiarowania przycisków na setMinimumWidth.

import os
import sys
import shutil
import time

os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QMainWindow, QTextEdit, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer

from config import THEME, APP_CONFIG
from utils import logger, telemetry_recorder


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
        
        self.layout.addStretch()
        
        lbl_logs = QLabel("Rejestr Decyzyjny:")
        lbl_logs.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; font-weight: bold; margin-top: 5px;")
        self.layout.addWidget(lbl_logs)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet(f"background-color: {THEME['bg_card']}; color: {THEME['text_muted']}; font-family: monospace; font-size: 11px; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 6px;")
        self.log_console.setFixedHeight(160)
        self.layout.addWidget(self.log_console)
        
        self.last_log_count = len(logger.session_logs)
        if self.last_log_count > 0:
            html_lines =[self._format_log_line(l) for l in logger.session_logs[-20:]]
            self.log_console.setHtml("<br>".join(html_lines))
            self.log_console.verticalScrollBar().setValue(self.log_console.verticalScrollBar().maximum())
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(500)
        
    def _format_log_line(self, line):
        color = THEME['text_muted']
        if "[ARF 3.1]" in line or "[DEFIBRYLATOR]" in line:
            color = "#e74c3c"
        elif "[WATCHDOG]" in line:
            color = "#f39c12"
        elif "[PREFETCH]" in line or "[SYNC-START]" in line:
            color = "#2ecc71"
        safe_line = line.replace("<", "&lt;").replace(">", "&gt;")
        return f'<span style="color: {color};">{safe_line}</span>'
        
    def update_stats(self):
        try:
            net = self.main_window.network_monitor
            is_online = getattr(net, 'is_online', True)
            self.labels["net_link"].setText("Aktywny" if is_online else "Brak")
            self.labels["net_link"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {'#2ecc71' if is_online else '#e74c3c'};")
            
            ping = getattr(net, 'net_ping', 0)
            self.labels["net_ping"].setText(f"{ping} ms" if ping != -1 else "Brak")
            if ping == -1 or ping > 1000:
                self.labels["net_ping"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")
            elif ping > 200:
                self.labels["net_ping"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
            else:
                self.labels["net_ping"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")

            loc = getattr(net, 'loc_lat', 0)
            self.labels["loc_lat"].setText(f"{loc} ms" if loc != -1 else "Brak")
            if loc == -1 or loc > 500:
                self.labels["loc_lat"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")
            else:
                self.labels["loc_lat"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")

            state_str = self.main_window.engine.current_engine_state
            self.labels["state"].setText(state_str)
            if "Buforowanie" in state_str or "Pobieranie" in state_str or "Rozwiązywanie" in state_str or "Oczekiwanie" in state_str:
                self.labels["state"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
            elif "ARF" in state_str or "wyłączone" in state_str:
                self.labels["state"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")
            elif "Płynne" in state_str:
                self.labels["state"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")
            else:
                self.labels["state"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {THEME['text_main']};")

            sync_locked = getattr(self.main_window.engine, 'sync_locked', False)
            self.labels["sync_lock"].setText("Aktywna" if sync_locked else "Brak")
            self.labels["sync_lock"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {'#e74c3c' if sync_locked else '#2ecc71'};")

            is_playing = (self.main_window.engine.video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
            if is_playing:
                a_pos = self.main_window.engine.player.position()
                v_pos = self.main_window.engine.video_player.position()
                delta = abs(a_pos - v_pos)
                self.labels["av_sync"].setText(f"{delta} ms")
                if delta > 800:
                    self.labels["av_sync"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")
                elif delta > 200:
                    self.labels["av_sync"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
                else:
                    self.labels["av_sync"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")
            else:
                self.labels["av_sync"].setText("-")
                self.labels["av_sync"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {THEME['text_muted']};")

            rate = self.main_window.engine.video_player.playbackRate()
            self.labels["rate"].setText(f"{rate:.1f}x")
            self.labels["rate"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {'#f39c12' if rate != 1.0 else THEME['text_main']};")
            
            h_sync_cnt = getattr(self.main_window.engine, 'h_sync_count', 0)
            self.labels["h_sync"].setText(str(h_sync_cnt))
            self.labels["h_sync"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {'#e74c3c' if h_sync_cnt > 0 else THEME['text_main']};")

            grace_active = (time.time() < getattr(self.main_window, '_seek_grace_until', 0))
            self.labels["grace"].setText("W toku" if grace_active else "Brak")
            self.labels["grace"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {'#2ecc71' if grace_active else THEME['text_muted']};")

            buf_pct = self.main_window.engine.video_player.bufferProgress() * 100
            buf_sec = self.main_window.engine.get_buf_sec()
            self.labels["v_health"].setText(f"{buf_sec:.1f} s ({int(buf_pct)}%)")
            
            if buf_sec < 5.0 and buf_pct < 100:
                self.labels["v_health"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")
            elif buf_sec < 15.0 and buf_pct < 100:
                self.labels["v_health"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
            else:
                self.labels["v_health"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")

            score = self.main_window.now_playing_view.video_widget.last_motion_score
            self.labels["motion"].setText(f"{score:.2f}")
            if score > 6.0:
                self.labels["motion"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")
            else:
                self.labels["motion"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {THEME['text_muted']};")

            fps = self.main_window.now_playing_view.video_widget.current_fps
            fps_lbl = self.labels["fps"]
            fps_lbl.setText(f"{fps} kl/s")
            if fps == 0:
                fps_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {THEME['text_muted']};")
            elif fps >= 25:
                fps_lbl.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")
            elif fps >= 15:
                fps_lbl.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
            else:
                fps_lbl.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")

            z_fps_cnt = getattr(self.main_window, '_zero_fps_cycles', 0)
            self.labels["z_fps"].setText(str(z_fps_cnt))
            self.labels["z_fps"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {'#e74c3c' if z_fps_cnt > 2 else THEME['text_main']};")

            res_c = APP_CONFIG.get("video_resolution", "1080p")
            self.labels["res_conf"].setText(res_c)
            
            act_res = getattr(self.main_window.engine, 'current_video_resolution', "1080p")
            self.labels["res_act"].setText(f"{act_res} ({self.main_window.now_playing_view.video_widget.actual_resolution})")
            
            is_dyn = self.main_window.now_playing_view.is_video_dynamic
            is_mask = getattr(self.main_window, '_current_mask_state', False)
            
            if is_mask:
                self.labels["filter"].setText("Blur Mask (Kompensacja)")
                self.labels["filter"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
            else:
                if fps > 0:
                    self.labels["filter"].setText("Wideo Dynamiczne" if is_dyn else "Wideo Statyczne")
                    self.labels["filter"].setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")
                else:
                    self.labels["filter"].setText("Brak Wideo")
                    self.labels["filter"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {THEME['text_muted']};")
            
            def get_buf_color(status):
                if "Gotowe" in status or "Zbuforowano" in status: return "#2ecc71"
                if "Buforowanie" in status or "Ładowanie" in status: return "#f39c12"
                if "Zacięcie" in status or "Błąd" in status: return "#e74c3c"
                return THEME['text_main']
            
            vbuf = self.main_window.engine.video_status_str
            self.labels["v_buf"].setText(vbuf)
            self.labels["v_buf"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {get_buf_color(vbuf)};")
            
            abuf = self.main_window.engine.audio_status_str
            self.labels["a_buf"].setText(abuf)
            self.labels["a_buf"].setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {get_buf_color(abuf)};")
            
            resolve_time = self.main_window.engine.last_resolve_time
            res_lbl = self.labels["resolve"]
            res_lbl.setText(f"{resolve_time} ms")
            if resolve_time == 0:
                res_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; text-align: right; color: {THEME['text_muted']};")
            elif resolve_time < 1500:
                res_lbl.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #2ecc71;")
            elif resolve_time < 3000:
                res_lbl.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #f39c12;")
            else:
                res_lbl.setStyleSheet("font-size: 13px; font-weight: bold; text-align: right; color: #e74c3c;")
            
            self.labels["img_q"].setText(str(len(self.main_window.loader.queue)))
            threads = self.main_window.threadpool.activeThreadCount()
            self.labels["threads"].setText(str(threads))
            
            current_log_count = len(logger.session_logs)
            if current_log_count > self.last_log_count:
                new_logs = logger.session_logs[self.last_log_count:]
                for log_line in new_logs:
                    self.log_console.append(self._format_log_line(log_line))
                self.last_log_count = current_log_count
                self.log_console.verticalScrollBar().setValue(self.log_console.verticalScrollBar().maximum())
                
        except Exception:
            pass


class DevModeView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.telemetry_window = None
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        lbl_title = QLabel("Tryb Dewelopera i Diagnostyka")
        lbl_title.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {THEME['text_main']}; margin-bottom: 20px; background: transparent;")
        self.main_layout.addWidget(lbl_title)

        live_group = QFrame()
        live_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        live_layout = QVBoxLayout(live_group)
        
        live_title = QLabel("Panel Diagnostyczny (HUD)")
        live_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        live_layout.addWidget(live_title)
        
        btn_open_telemetry = QPushButton("Otwórz okno telemetrii")
        btn_open_telemetry.setMinimumWidth(250)
        btn_open_telemetry.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_open_telemetry.setStyleSheet(f"background-color: {THEME['accent']}; color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold;")
        btn_open_telemetry.setCursor(Qt.PointingHandCursor)
        btn_open_telemetry.clicked.connect(self._open_telemetry)
        live_layout.addWidget(btn_open_telemetry)

        self.main_layout.addWidget(live_group)
        
        rec_group = QFrame()
        rec_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        rec_layout = QVBoxLayout(rec_group)
        
        rec_title = QLabel("Zrzut Telemetrii (Czarna Skrzynka)")
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
        self.main_layout.addWidget(rec_group)

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
        
        self.main_layout.addWidget(sys_group)

        cache_group = QFrame()
        cache_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        cache_layout = QVBoxLayout(cache_group)
        
        cache_title = QLabel("Pamięć Podręczna Okładek")
        cache_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        cache_layout.addWidget(cache_title)
        
        self.cache_size_lbl = QLabel("Obliczanie rozmiaru...")
        self.cache_size_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; background: transparent; margin-bottom: 10px;")
        cache_layout.addWidget(self.cache_size_lbl)
        
        btn_clear_cache = QPushButton("Opróżnij Cache")
        btn_clear_cache.setMinimumWidth(200)
        btn_clear_cache.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_clear_cache.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 10px 20px; border-radius: 5px;")
        btn_clear_cache.setCursor(Qt.PointingHandCursor)
        btn_clear_cache.clicked.connect(self._clear_cache)
        cache_layout.addWidget(btn_clear_cache)
        
        self.main_layout.addWidget(cache_group)

        path_group = QFrame()
        path_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        path_layout = QVBoxLayout(path_group)
        
        path_title = QLabel("Ścieżki Systemowe")
        path_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        path_layout.addWidget(path_title)
        
        cfg_path = os.path.abspath('config.ini')
        cache_path = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-images")
        log_path = logger.log_file
        tele_path = telemetry_recorder.log_file
        
        paths_txt = f"<b>Konfiguracja:</b> {cfg_path}<br><br><b>Okładki:</b> {cache_path}<br><br><b>Dziennik Błędów:</b> {log_path}<br><br><b>Zrzut Telemetrii:</b> {tele_path}"
        paths_lbl = QLabel(paths_txt)
        paths_lbl.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 13px; background: transparent;")
        paths_lbl.setWordWrap(True)
        path_layout.addWidget(paths_lbl)
        
        self.main_layout.addWidget(path_group)

        log_group = QFrame()
        log_group.setStyleSheet(f"background-color: {THEME['bg_card']}; border-radius: 10px; padding: 20px;")
        log_layout = QVBoxLayout(log_group)
        
        log_title = QLabel("Dziennik Zdarzeń")
        log_title.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {THEME['text_main']}; margin-bottom: 10px; background: transparent;")
        log_layout.addWidget(log_title)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"background-color: {THEME['bg_main']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 5px; padding: 10px; font-family: monospace;")
        self.log_text.setFixedHeight(180)
        log_layout.addWidget(self.log_text)
        
        log_btns = QHBoxLayout()
        log_btns.setSpacing(10)
        
        btn_refresh_logs = QPushButton("Odśwież")
        btn_refresh_logs.setMinimumWidth(100)
        btn_refresh_logs.setCursor(Qt.PointingHandCursor)
        btn_refresh_logs.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 5px;")
        btn_refresh_logs.clicked.connect(self._refresh_logs)
        
        btn_open_logs = QPushButton("Otwórz plik")
        btn_open_logs.setMinimumWidth(100)
        btn_open_logs.setCursor(Qt.PointingHandCursor)
        btn_open_logs.setStyleSheet(f"background-color: {THEME['nav_bg']}; color: {THEME['text_main']}; padding: 8px 15px; border-radius: 5px;")
        btn_open_logs.clicked.connect(self._open_logs)
        
        btn_clear_logs = QPushButton("Wyczyść historię")
        btn_clear_logs.setMinimumWidth(120)
        btn_clear_logs.setCursor(Qt.PointingHandCursor)
        btn_clear_logs.setStyleSheet(f"background-color: {THEME['accent']}; color: white; padding: 8px 15px; border-radius: 5px; font-weight: bold;")
        btn_clear_logs.clicked.connect(self._clear_logs)
        
        log_btns.addWidget(btn_refresh_logs)
        log_btns.addWidget(btn_open_logs)
        log_btns.addWidget(btn_clear_logs)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)
        
        self.main_layout.addWidget(log_group)

        lbl_version = QLabel("Wersja programu: 11.6 (Static Layout, Pro-HUD)")
        lbl_version.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; margin-top: 20px; background: transparent;")
        lbl_version.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(lbl_version)

        self.main_layout.addStretch()
        
        QTimer.singleShot(100, self._calculate_cache)
        self._refresh_logs()

    def _export_telemetry(self):
        msg = telemetry_recorder.export_to_desktop()
        self.export_status_lbl.setText(msg)
        QTimer.singleShot(5000, lambda: self.export_status_lbl.setText(""))

    def _calculate_cache(self):
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-images")
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
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "navidrome-player-images")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
        self._calculate_cache()

    def _open_telemetry(self):
        if not self.telemetry_window:
            self.telemetry_window = TelemetryWindow(self.main_window)
        self.telemetry_window.show()

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