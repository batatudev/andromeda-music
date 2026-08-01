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

        self.setStyleSheet(f"""
            #ToastNotification {{
                background-color: {bg};
                border: 1px solid {border};
                border-left: 3px solid {accent};
                border-radius: 10px;
            }}
        """)

        # Cień
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        # Układ główny
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(14, 12, 14, 12)
        main_lay.setSpacing(12)

        # Ikona
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setPixmap(qta.icon(icon_str, color=icon_color).pixmap(22, 22))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        main_lay.addWidget(icon_lbl)

        # Tekst
        text_lay = QVBoxLayout()
        text_lay.setSpacing(2)
        text_lay.setContentsMargins(0, 0, 0, 0)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {text_main};"
                f"background: transparent; border: none;"
            )
            text_lay.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"font-size: 12px; color: {text_muted}; background: transparent; border: none;"
        )
        text_lay.addWidget(msg_lbl)
        main_lay.addLayout(text_lay, 1)

        # Przycisk zamknięcia X
        close_lbl = QLabel("✕")
        close_lbl.setStyleSheet(
            f"font-size: 11px; color: {text_muted}; background: transparent; border: none;"
        )
        close_lbl.setAlignment(Qt.AlignTop | Qt.AlignRight)
        main_lay.addWidget(close_lbl)

        # Animacja opacity
        self._opacity_effect = None
        self._fade_in_anim = None
        self._fade_out_anim = None

        # Timer auto-znikania
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(duration)
        self._hide_timer.timeout.connect(self._start_fade_out)

    def show_toast(self):
        """Wyświetla toast z animacją Fade-In i uruchamia timer znikania."""
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._reposition()
        self.show()
        self.raise_()

        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in_anim.setDuration(300)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in_anim.start()

        self._hide_timer.start()

    def _reposition(self):
        """Centruje toast poziomo u góry okna nadrzędnego."""
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        pw = parent.width()
        w = self.width()
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
