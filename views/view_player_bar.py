# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: view_player_bar.py
# OPIS ZMIAN: Zmiana ikony ładowania na czyste, nowoczesne `fa5s.circle-notch` (sam łuk bez strzałki). Zachowano szybki obrót (step=6). Zlikwidowano absolutnie wszystkie średniki i wymuszono jedną instrukcję na linię.

import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize

from config import THEME
from ui.widgets import ClickableFrame, RoundedImage, ClickableElidedLabel, HoverIconButton, PremiumSlider, ClickableLabel

class PlayerBarWidget(ClickableFrame):
    play_pause_requested = Signal()
    next_requested = Signal()
    prev_requested = Signal()
    skip_f_requested = Signal()
    skip_b_requested = Signal()
    loop_requested = Signal()
    shuffle_requested = Signal()
    video_toggle_requested = Signal()
    mute_requested = Signal()
    queue_requested = Signal()
    volume_changed = Signal(int)
    seek_requested = Signal(int)
    seek_started = Signal()
    fav_toggled = Signal()
    title_clicked = Signal()
    artist_clicked = Signal()
    album_clicked = Signal()
    
    def __init__(self, initial_volume=80):
        super().__init__()
        self.setObjectName("PlayerBar")
        self.setFixedHeight(110)
        self._slider_is_pressed = False
        self._current_duration = 0
        self._show_remaining_time = False
        self._is_loading = False
        self._last_playing_state = False
        self._init_ui(initial_volume)
        
    def _init_ui(self, initial_volume):
        p_lay = QHBoxLayout(self)
        p_lay.setContentsMargins(20, 0, 20, 0)
        p_lay.setSpacing(0)

        self.pb_left = QWidget()
        self.pb_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.pb_left.setMinimumWidth(0)
        
        l_lay = QHBoxLayout(self.pb_left)
        l_lay.setContentsMargins(0, 0, 10, 0)
        l_lay.setSpacing(0)
        
        self.pb_img = RoundedImage(size=80, radius=8)

        v_info = QVBoxLayout()
        v_info.setSpacing(2)
        v_info.setContentsMargins(15, 0, 0, 0)

        self.pb_t = ClickableElidedLabel("Nic nie gra", default_color=THEME["text_main"], hover_color=THEME["accent"], font_weight="bold", font_size="18px")
        self.pb_a = ClickableElidedLabel("-", default_color=THEME["text_muted"], hover_color=THEME["text_main"], font_size="14px")
        self.pb_alb = ClickableElidedLabel("-", default_color=THEME["text_muted"], hover_color=THEME["text_main"], font_size="14px")

        self.pb_fav_btn = HoverIconButton('fa5.heart', default_color=THEME["text_muted"], icon_size=16)
        self.pb_fav_btn.setFixedSize(32, 32)
        self.pb_fav_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: 16px; }} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        h_info = QHBoxLayout()
        h_info.setSpacing(5)
        h_info.setContentsMargins(0, 0, 0, 0)
        h_info.addWidget(self.pb_a)

        self.pb_dot = QLabel("•")
        self.pb_dot.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")

        h_info.addWidget(self.pb_dot)
        h_info.addWidget(self.pb_alb)
        h_info.addWidget(self.pb_fav_btn)
        h_info.addStretch()

        v_info.addWidget(self.pb_t)
        v_info.addLayout(h_info)

        l_lay.addWidget(self.pb_img)
        l_lay.addLayout(v_info)
        l_lay.addStretch()

        self.pb_mid = QWidget()
        self.pb_mid.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.pb_mid.setFixedWidth(520) 
        
        m_lay = QVBoxLayout(self.pb_mid)
        m_lay.setAlignment(Qt.AlignCenter)
        m_lay.setSpacing(8)
        
        btns = QHBoxLayout()
        btns.setSpacing(10)
        
        btn_base = "QPushButton { background: transparent; border: none; border-radius: 18px; }"

        self.btn_shuffle = HoverIconButton('fa5s.random', icon_size=16)
        self.btn_shuffle.setFixedSize(36, 36)
        self.btn_shuffle.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        self.btn_skip_b = HoverIconButton('fa5s.backward', icon_size=16)
        self.btn_skip_b.setFixedSize(36, 36)
        self.btn_skip_b.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")
        self.btn_skip_b.setToolTip("-10s")

        self.btn_prev = HoverIconButton('fa5s.step-backward', icon_size=16)
        self.btn_prev.setFixedSize(36, 36)
        self.btn_prev.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        self.btn_play = QPushButton(qta.icon('fa5s.play', color=THEME["play_color"]), "")
        self.btn_play.setObjectName("PlayPauseBtn")
        self.btn_play.setFixedSize(46, 46)
        self.btn_play.setIconSize(QSize(20, 20))
        self.btn_play.setCursor(Qt.PointingHandCursor)

        self.btn_next = HoverIconButton('fa5s.step-forward', icon_size=16)
        self.btn_next.setFixedSize(36, 36)
        self.btn_next.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        self.btn_skip_f = HoverIconButton('fa5s.forward', icon_size=16)
        self.btn_skip_f.setFixedSize(36, 36)
        self.btn_skip_f.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")
        self.btn_skip_f.setToolTip("+10s")

        self.btn_loop = HoverIconButton('fa5s.sync-alt', icon_size=16)
        self.btn_loop.setFixedSize(36, 36)
        self.btn_loop.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        self.btn_video_toggle = HoverIconButton('fa5s.video', icon_size=16)
        self.btn_video_toggle.setFixedSize(36, 36)
        self.btn_video_toggle.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")
        self.btn_video_toggle.setToolTip("Teledysk z YouTube")
        self.btn_video_toggle.setCheckable(True)

        btns.addStretch()
        btns.addWidget(self.btn_shuffle)
        btns.addWidget(self.btn_skip_b)
        btns.addWidget(self.btn_prev)
        btns.addWidget(self.btn_play)
        btns.addWidget(self.btn_next)
        btns.addWidget(self.btn_skip_f)
        btns.addWidget(self.btn_loop)
        btns.addWidget(self.btn_video_toggle)
        btns.addStretch()

        prog = QHBoxLayout()
        self.cur_time = QLabel("0:00")
        self.cur_time.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px;")
        self.cur_time.setFixedWidth(40)
        self.cur_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.slider = PremiumSlider(Qt.Horizontal)
        self.slider.setFixedWidth(400)
        
        self.total_time = ClickableLabel("0:00", default_color=THEME["text_muted"], hover_color=THEME["text_main"], font_size="12px")
        self.total_time.setFixedWidth(40)
        self.total_time.setToolTip("Przełącz: Czas całkowity / Czas pozostały")
        self.total_time.clicked.connect(self._toggle_time_display)
        
        prog.addStretch()
        prog.addWidget(self.cur_time)
        prog.addWidget(self.slider)
        prog.addWidget(self.total_time)
        prog.addStretch()
        
        m_lay.addLayout(btns)
        m_lay.addLayout(prog)

        self.pb_right = QWidget()
        self.pb_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.pb_right.setMinimumWidth(0)
        
        r_lay = QHBoxLayout(self.pb_right)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(8)
        
        r_lay.addStretch(1)

        self.btn_q = HoverIconButton('fa5s.list-ul', icon_size=18)
        self.btn_q.setFixedSize(36, 36)
        self.btn_q.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        vol_c = QWidget()
        vol_c.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        vol_l = QHBoxLayout(vol_c)
        vol_l.setContentsMargins(0, 0, 0, 0)
        vol_l.setSpacing(5)

        self.btn_mute = HoverIconButton('fa5s.volume-up', icon_size=16)
        self.btn_mute.setFixedSize(36, 36)
        self.btn_mute.setStyleSheet(f"{btn_base} QPushButton:hover {{ background: {THEME['btn_hover_bg']}; }}")

        self.v_s = PremiumSlider(Qt.Horizontal)
        self.v_s.setFixedWidth(100)
        self.v_s.setValue(initial_volume)

        vol_l.addWidget(self.btn_mute)
        vol_l.addWidget(self.v_s)

        r_lay.addWidget(self.btn_q)
        r_lay.addWidget(vol_c)

        p_lay.addWidget(self.pb_left, 1)
        p_lay.addWidget(self.pb_mid, 0)
        p_lay.addWidget(self.pb_right, 1)
        
        self.btn_play.clicked.connect(self.play_pause_requested.emit)
        self.btn_next.clicked.connect(self.next_requested.emit)
        self.btn_prev.clicked.connect(self.prev_requested.emit)
        self.btn_skip_b.clicked.connect(self.skip_b_requested.emit)
        self.btn_skip_f.clicked.connect(self.skip_f_requested.emit)
        self.btn_loop.clicked.connect(self.loop_requested.emit)
        self.btn_video_toggle.clicked.connect(self.video_toggle_requested.emit)
        self.btn_shuffle.clicked.connect(self.shuffle_requested.emit)
        self.btn_q.clicked.connect(self.queue_requested.emit)
        self.v_s.valueChanged.connect(self.volume_changed.emit)
        self.btn_mute.clicked.connect(self.mute_requested.emit)
        self.pb_fav_btn.clicked.connect(self.fav_toggled.emit)
        self.pb_t.clicked.connect(self.title_clicked.emit)
        self.pb_a.clicked.connect(self.artist_clicked.emit)
        self.pb_alb.clicked.connect(self.album_clicked.emit)

        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.sliderMoved.connect(self._on_slider_moved)

    def set_loading_state(self, is_loading):
        self._is_loading = is_loading
        if is_loading:
            spinner_anim = qta.Spin(self.btn_play, interval=10, step=6)
            self.btn_play.setIcon(qta.icon('fa5s.circle-notch', color=THEME["play_color"], animation=spinner_anim))
        else:
            self.set_playing_state(self._last_playing_state)

    def set_playing_state(self, is_playing):
        self._last_playing_state = is_playing
        if not self._is_loading:
            icon = 'fa5s.pause' if is_playing else 'fa5s.play'
            self.btn_play.setIcon(qta.icon(icon, color=THEME["play_color"]))

    def _toggle_time_display(self):
        self._show_remaining_time = not self._show_remaining_time
        self._update_time_labels(self.slider.value())

    def _update_time_labels(self, p):
        self.cur_time.setText(f"{int(p//60000)}:{int((p%60000)//1000):02d}")
        if self._current_duration > 0:
            if self._show_remaining_time:
                rem = max(0, self._current_duration - p)
                self.total_time.setText(f"-{int(rem//60000)}:{int((rem%60000)//1000):02d}")
            else:
                d = self._current_duration
                self.total_time.setText(f"{int(d//60000)}:{int((d%60000)//1000):02d}")

    def _on_slider_pressed(self):
        self._slider_is_pressed = True
        self.seek_started.emit()

    def _on_slider_released(self):
        self._slider_is_pressed = False
        self.seek_requested.emit(self.slider.value())

    def _on_slider_moved(self, p):
        self._update_time_labels(p)

    def set_track_info(self, title, artist, album, is_fav):
        self.pb_t.setText(title)
        self.pb_a.setText(artist)
        self.pb_alb.setText(album)
        self.pb_fav_btn.set_default_color(THEME["accent"] if is_fav else THEME["text_muted"])
        self.pb_fav_btn.update_icon('fa5s.heart' if is_fav else 'fa5.heart')

    def update_position(self, p):
        if not self._slider_is_pressed:
            self.slider.setValue(p)
            self._update_time_labels(p)

    def update_duration(self, d):
        self._current_duration = d
        if d > 0:
            self.slider.setRange(0, d)
            self._update_time_labels(self.slider.value())

    def set_loop_state(self, is_looping):
        self.btn_loop.set_default_color(THEME['accent'] if is_looping else THEME['text_muted'])

    def set_shuffle_state(self, is_shuffled):
        self.btn_shuffle.set_default_color(THEME['accent'] if is_shuffled else THEME['text_muted'])

    def set_video_available(self, has_video):
        self.btn_video_toggle.setEnabled(True)
        if not has_video:
            self.btn_video_toggle.set_default_color(THEME["text_muted"])

    def set_video_active(self, is_active):
        self.btn_video_toggle.set_default_color(THEME["accent"] if is_active else THEME["text_muted"])
        
    def set_mute_state(self, is_muted):
        self.btn_mute.update_icon('fa5s.volume-mute' if is_muted else 'fa5s.volume-up')
        
    def reset(self):
        self.pb_t.setText("Nic nie gra")
        self.pb_a.setText("-")
        self.pb_alb.setText("-")
        self.pb_img.set_image(None, animate=False)
        self.slider.setValue(0)
        self._current_duration = 0
        self.cur_time.setText("0:00")
        self.total_time.setText("0:00")
        self.set_loading_state(False)
        self.set_playing_state(False)
        self.pb_fav_btn.set_default_color(THEME["text_muted"])
        self.pb_fav_btn.update_icon('fa5.heart')