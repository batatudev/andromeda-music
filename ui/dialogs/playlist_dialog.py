import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from config import THEME, APP_CONFIG, get_app_style
from core.i18n import tr


class PlaylistDialog(QDialog):
    """
    Dedykowane okno dialogowe tworzenia i dodawania utworu do playlisty.
    """
    def __init__(self, parent, client, song, video_download_manager, on_playlists_changed=None):
        super().__init__(parent)
        self.main_window = parent
        self.client = client
        self.song = song
        self.v_mgr = video_download_manager
        self.on_playlists_changed = on_playlists_changed

        self._init_ui()
        self._fetch_playlists()

    def _init_ui(self):
        title_txt = tr("dialogs.playlist_add_title", "Dodaj do playlisty")
        self.setWindowTitle(title_txt)
        self.setFixedSize(320, 450)
        self.setStyleSheet(get_app_style())
        self.main_layout = QVBoxLayout(self)

        lbl_title = QLabel(title_txt)
        lbl_title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {THEME['text_main']}; margin-bottom: 10px;"
        )
        self.main_layout.addWidget(lbl_title)

        new_pl_layout = QHBoxLayout()
        self.inp_new_pl = QLineEdit()
        self.inp_new_pl.setPlaceholderText(tr("dialogs.playlist_new_placeholder", "Nowa playlista..."))
        self.inp_new_pl.setStyleSheet(
            f"background: {THEME['bg_main']}; color: {THEME['text_main']}; padding: 8px; "
            f"border: 1px solid {THEME['border']}; border-radius: 5px;"
        )

        btn_new_pl = QPushButton(tr("dialogs.create", "Utwórz"))
        btn_new_pl.setCursor(Qt.PointingHandCursor)
        btn_new_pl.setStyleSheet(
            f"background: {THEME['accent']}; color: white; padding: 8px; border-radius: 5px; font-weight: bold;"
        )
        btn_new_pl.clicked.connect(self._create_playlist)

        new_pl_layout.addWidget(self.inp_new_pl)
        new_pl_layout.addWidget(btn_new_pl)
        self.main_layout.addLayout(new_pl_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {THEME['border']}; margin: 10px 0px;")
        self.main_layout.addWidget(line)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.pl_list_layout = QVBoxLayout(self.scroll_content)
        self.pl_list_layout.setContentsMargins(0, 0, 0, 0)
        self.pl_list_layout.setSpacing(5)

        self.scroll.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll)

    def _fetch_playlists(self):
        def task():
            params = self.client._get_auth_params()
            res = self.client._make_request("getPlaylists", params)
            return res.get('playlists', {}).get('playlist', [])

        def on_ready(playlists):
            while self.pl_list_layout.count():
                item = self.pl_list_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()

            for pl in playlists:
                btn = QPushButton(pl.get('name'))
                btn.setStyleSheet(
                    f"text-align: left; padding: 10px; border-radius: 5px; background: {THEME['bg_card']}; "
                    f"color: {THEME['text_main']}; border: none;"
                )
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda ch=False, pid=pl.get('id'): self._select_playlist(pid))
                self.pl_list_layout.addWidget(btn)

            self.pl_list_layout.addStretch()

        if hasattr(self.main_window, 'run_async'):
            self.main_window.run_async(task, on_ready, page_bound=False)

    def _create_playlist(self):
        name = self.inp_new_pl.text().strip()
        if not name:
            return
        self.accept()

        def task():
            p = self.client._get_auth_params()
            p['name'] = name
            p['songId'] = [self.song.item_id]
            self.client._make_request("createPlaylist", p)

            if APP_CONFIG.get("video_auto_dl_playlists", False):
                link = getattr(self.song, 'yt_link', None) or getattr(self.song, 'youtube_url', None)
                if link and self.v_mgr:
                    self.v_mgr.add_to_queue(
                        self.song.item_id, link, self.song.title,
                        high_priority=False, cover_id=self.song.cover_id
                    )

        def on_ready(_):
            if self.on_playlists_changed:
                self.on_playlists_changed()

        if hasattr(self.main_window, 'run_async'):
            self.main_window.run_async(task, on_ready, page_bound=False)

    def _select_playlist(self, pid):
        self.accept()

        def task():
            self.client.update_playlist(pid, song_id_to_add=self.song.item_id)
            if APP_CONFIG.get("video_auto_dl_playlists", False):
                link = getattr(self.song, 'yt_link', None) or getattr(self.song, 'youtube_url', None)
                if link and self.v_mgr:
                    self.v_mgr.add_to_queue(
                        self.song.item_id, link, self.song.title,
                        high_priority=False, cover_id=self.song.cover_id
                    )

        if hasattr(self.main_window, 'run_async'):
            self.main_window.run_async(task, None, page_bound=False)