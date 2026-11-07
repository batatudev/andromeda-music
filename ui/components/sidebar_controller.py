import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from config import THEME
from core.i18n import tr

class SidebarController(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.win = main_window
        self.sidebar = self.win.sidebar
        self.sidebar_collapsed = False
        self.manual_sidebar_override = False

        self.sidebar.toggle_sidebar_requested.connect(self.manual_toggle_sidebar)

    def manual_toggle_sidebar(self):
        self.toggle_sidebar(manual=True)

    def toggle_sidebar(self, manual=False):
        if manual:
            self.manual_sidebar_override = True
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.sidebar.set_collapsed(self.sidebar_collapsed)

    def handle_resize(self, width):
        if not self.manual_sidebar_override:
            if width < 1050 and not self.sidebar_collapsed:
                self.toggle_sidebar(manual=False)
            elif width >= 1050 and self.sidebar_collapsed:
                self.toggle_sidebar(manual=False)

    def update_active_state(self, router):
        if not getattr(router, 'current_route', None):
            return

        from core.enums import MediaType
        active_idx = router.current_route["page"]
        active_playlist_id = None
        if router.current_route["type"] == MediaType.PLAYLIST and router.current_route.get("data"):
            active_playlist_id = router.current_route["data"].get("id")

        self.sidebar.update_active_state(active_idx, active_playlist_id)

    def load_playlists(self):
        def fetch():
            try:
                params = self.win.client._get_auth_params()
                res = self.win.client._make_request("getPlaylists", params)
                return res.get('playlists', {}).get('playlist', [])
            except Exception:
                return []

        def on_ready(data):
            self.sidebar.set_playlists(data)
            for i in range(self.sidebar.playlist_layout.count()):
                w = self.sidebar.playlist_layout.itemAt(i).widget()
                if w:
                    w.setContextMenuPolicy(Qt.CustomContextMenu)
                    w.customContextMenuRequested.connect(lambda pos, widget=w: self.show_playlist_context_menu(widget, pos))

        self.win.run_async(fetch, on_ready, page_bound=False)

    def show_playlist_context_menu(self, widget, pos):
        pl_id = widget.property("pl_id")
        if not pl_id:
            return
        menu = QMenu(self.win)
        menu.setStyleSheet(f"QMenu {{ background-color: {THEME['bg_card']}; color: {THEME['text_main']}; border: 1px solid {THEME['border']}; border-radius: 6px; padding: 4px; }} QMenu::item {{ padding: 8px 25px 8px 10px; border-radius: 4px; background: transparent; }} QMenu::item:selected {{ background-color: {THEME['btn_remove_hover']}; }}")
        act_del = QAction(tr("context.delete_playlist", "Usuń playlistę"), self.win)
        act_del.triggered.connect(lambda: self.delete_playlist(pl_id))
        menu.addAction(act_del)
        menu.exec(widget.mapToGlobal(pos))

    def delete_playlist(self, pl_id):
        def on_ready(res):
            if self.win.router.current_route and self.win.router.current_route.get("data", {}).get("id") == pl_id:
                self.win.router.go_back()
            self.load_playlists()
        self.win.run_async(lambda: self.win.client.delete_playlist(pl_id), on_ready, page_bound=False)