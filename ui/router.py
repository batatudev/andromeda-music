# ui/router.py
import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtCore import QObject, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QStackedWidget, QScrollArea, QGraphicsOpacityEffect
from config import Pages
from core.enums import MediaType

class AppRouter(QObject):
    """
    Zarządza nawigacją pomiędzy widokami aplikacji.
    Odpowiada za historię odwiedzonych stron oraz animacje przejść.
    """
    def __init__(self, main_window):
        super().__init__()
        self.win = main_window
        self.stack = None
        self.pages = []
        self.history = []
        self.current_route = None

    def setup(self, stack: QStackedWidget, pages_list: list):
        self.stack = stack
        self.pages = pages_list

    def navigate(self, page_idx, data=None, type_str=None, is_back=False):
        if getattr(self.win, '_is_fetching', False):
            return

        if self.stack.currentIndex() == Pages.SETTINGS and page_idx != Pages.SETTINGS:
            if hasattr(self.win, 'settings_view'):
                self.win.settings_view.revert_changes()

        if page_idx == Pages.SETTINGS and self.stack.currentIndex() != Pages.SETTINGS:
            if hasattr(self.win, 'settings_view'):
                self.win.settings_view.sync_values()

        is_initial_navigation = (self.current_route is None)

        if not is_back and self.current_route:
            if self.current_route.get("page") != page_idx or self.current_route.get("data") != data:
                self.history.append(self.current_route)
                if len(self.history) > 50:
                    self.history.pop(0)

        self.win.current_page_task_id += 1
        self.current_route = {"page": page_idx, "data": data, "type": type_str}

        page_widget = self.win.get_or_create_page(page_idx)
        target_widget = None

        if hasattr(page_widget, 'load'):
            target_widget = page_widget
        elif isinstance(page_widget, QScrollArea) and hasattr(page_widget.widget(), 'load'):
            target_widget = page_widget.widget()

        if target_widget:
            if page_idx == Pages.DETAILS:
                target_widget.load(data, type_str)
            elif page_idx in [Pages.HOME, Pages.FAVS, Pages.ALBUMS, Pages.TRACKS, Pages.ARTISTS, Pages.SEARCH, Pages.DOWNLOADS]:
                if not is_back:
                    target_widget.load()

        if hasattr(self.win, 'fade_anim') and self.win.fade_anim and self.win.fade_anim.state() == QPropertyAnimation.State.Running:
            self.win.fade_anim.stop()
            if hasattr(self.win, 'current_anim_page') and self.win.current_anim_page:
                self.win.current_anim_page.setGraphicsEffect(None)
                self.win.current_anim_page.move(0, 0)

        if hasattr(self.win, 'page_effect') and self.win.page_effect:
            try:
                self.win.page_effect.deleteLater()
            except Exception:
                pass
            self.win.page_effect = None

        self.stack.setCurrentIndex(page_idx)
        self.win.current_anim_page = self.stack.currentWidget()

        if is_initial_navigation or page_idx == Pages.NOW_PLAYING:
            if hasattr(self.win, 'current_anim_page') and self.win.current_anim_page:
                self.win.current_anim_page.move(0, 0)
            self.win._update_sidebar_active_state()
            self.win.setFocus()
            return

        self.win.page_effect = QGraphicsOpacityEffect(self.win.current_anim_page)
        self.win.current_anim_page.setGraphicsEffect(self.win.page_effect)

        self.win.fade_anim = QPropertyAnimation(self.win.page_effect, b"opacity")
        self.win.fade_anim.setDuration(180)
        self.win.fade_anim.setStartValue(0.0)
        self.win.fade_anim.setEndValue(1.0)
        self.win.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        def on_fade_finished():
            if hasattr(self.win, 'current_anim_page') and self.win.current_anim_page:
                self.win.current_anim_page.setGraphicsEffect(None)
                self.win.current_anim_page.move(0, 0)
            if hasattr(self.win, 'page_effect') and self.win.page_effect:
                try:
                    self.win.page_effect.deleteLater()
                except Exception:
                    pass
                self.win.page_effect = None

        self.win.fade_anim.finished.connect(on_fade_finished)
        self.win.page_effect.setOpacity(0.0)
        self.win.fade_anim.start()

        self.win._update_sidebar_active_state()

    def go_back(self):
        if getattr(self.win, '_is_fetching', False):
            return
        if not self.history:
            return
        prev = self.history.pop()
        self.navigate(prev["page"], prev.get("data"), prev.get("type"), is_back=True)

    def switch_page(self, idx):
        self.navigate(idx)

    def show_details(self, data, type_str):
        self.navigate(Pages.DETAILS, data, type_str)