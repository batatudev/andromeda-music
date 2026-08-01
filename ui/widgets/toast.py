import os
os.environ["QT_API"] = "pyside6"

import qtawesome as qta

from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor

from config import THEME


class ToastNotification(QFrame):
    """
    Nakładkowe powiadomienie Toast wyświetlane na środku u góry okna nadrzędnego.
    Pojawia się z animacją Fade-In i samoistnie znika po `duration` ms z Fade-Out.
    Można je zamknąć kliknięciem.
    """

    def __init__(self, parent, message, title="Powiadomienie",
                 icon_str="fa5s.check-circle", icon_color=None, duration=5000):
        super().__init__(parent)
        self.setObjectName("ToastNotification")

        if icon_color is None:
            icon_color = THEME.get("accent", "#1db954")

        # Bezramkowy widget-nakładka nad interfejsem
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setCursor(Qt.PointingHandCursor)

        accent = THEME.get("accent", "#1db954")
        bg = THEME.get("bg_card", "#111111")
        border = THEME.get("border", "#1e1e1e")
        text_main = THEME.get("text_main", "#ffffff")
        text_muted = THEME.get("text_muted", "#888888")

        from PySide6.QtWidgets import QGraphicsOpacityEffect
        self.setStyleSheet(f"""
            #ToastNotification {{
                background-color: {bg};
                border: 1px solid {border};
                border-left: 3px solid {accent};
                border-radius: 10px;
            }}
        """)

        # Efekt przezroczystości do animacji
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self.setMinimumWidth(520)
        self.setFixedHeight(46)

        # Układ główny
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(16, 8, 16, 8)
        main_lay.setSpacing(12)

        # Ikona
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setPixmap(qta.icon(icon_str, color=icon_color).pixmap(20, 20))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        main_lay.addWidget(icon_lbl)

        # Tekst jednolinijkowy
        if title:
            combined_text = f"<span style='font-weight: bold; color: {text_main};'>{title}:</span> <span style='color: {text_muted};'>{message}</span>"
        else:
            combined_text = f"<span style='color: {text_main};'>{message}</span>"

        msg_lbl = QLabel(combined_text)
        msg_lbl.setStyleSheet("font-size: 13px; background: transparent; border: none;")
        main_lay.addWidget(msg_lbl, 1)

        # Przycisk zamknięcia X
        close_lbl = QLabel("✕")
        close_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {text_muted}; background: transparent; border: none;"
        )
        close_lbl.setAlignment(Qt.AlignCenter)
        main_lay.addWidget(close_lbl)

        self._fade_in_anim = None
        self._fade_out_anim = None

        # Timer auto-znikania
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(duration)
        self._hide_timer.timeout.connect(self._start_fade_out)

    def show_toast(self):
        """Wyświetla toast z animacją Fade-In i uruchamia timer znikania."""
        self._reposition()
        self.show()
        self.raise_()

        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in_anim.setDuration(250)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in_anim.start()

        self._hide_timer.start()

    def _reposition(self):
        """Centruje toast poziomo u góry okna nadrzędnego z gwarancją szerszego układu w 1 linii."""
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        pw = parent.width()
        w = max(540, self.sizeHint().width() + 30)
        w = min(w, pw - 40)
        self.resize(w, 46)
        x = (pw - w) // 2
        y = 20
        self.move(x, y)

    def _start_fade_out(self):
        """Uruchamia animację Fade-Out i usuwa widget po jej zakończeniu."""
        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out_anim.setDuration(300)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out_anim.finished.connect(self._cleanup)
        self._fade_out_anim.start()

    def _cleanup(self):
        """Usuwa widget ze stosu po zakończeniu animacji wyjścia."""
        self.hide()
        self.deleteLater()

    def mousePressEvent(self, event):
        """Zamknięcie po kliknięciu."""
        self._hide_timer.stop()
        self._start_fade_out()
