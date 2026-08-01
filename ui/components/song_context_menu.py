import qtawesome as qta
from PySide6.QtWidgets import QMenu, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PySide6.QtCore import QPoint
from core.enums import MediaType
from config import THEME
from utils import logger

class SongContextMenu:
    @staticmethod
    def show(song_item):
        menu = QMenu(song_item)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 25px 8px 10px;
                border-radius: 4px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background-color: {THEME['nav_bg']};
            }}
            QMenu::icon {{
                padding-left: 10px;
            }}
            QMenu::separator {{
                height: 1px;
                background: {THEME['border']};
                margin: 4px 10px;
            }}
        """)

        if song_item.compact_mode:
            if song_item.is_queue:
                act_next = menu.addAction(qta.icon('fa5s.angle-double-up', color=THEME['text_main']), "Odtwórz jako następny")
                act_next.triggered.connect(lambda: song_item.play_next_clicked.emit(song_item.song))

                act_add_pl = menu.addAction(qta.icon('fa5s.folder-plus', color=THEME['text_main']), "Dodaj do playlisty")
                act_add_pl.triggered.connect(lambda: song_item.add_to_playlist_clicked.emit(song_item.song))

                act_rm = menu.addAction(qta.icon('fa5s.times', color=THEME['text_main']), "Usuń z kolejki")
                act_rm.triggered.connect(lambda: song_item.remove_clicked.emit(song_item.song))

            elif song_item.is_playlist:
                act_add = menu.addAction(qta.icon('fa5s.plus', color=THEME['text_main']), "Dodaj do kolejki")
                act_add.triggered.connect(lambda: song_item.add_to_queue_clicked.emit(song_item.song))

                act_rm_pl = menu.addAction(qta.icon('fa5s.times', color=THEME['text_main']), "Usuń z playlisty")
                act_rm_pl.triggered.connect(lambda: song_item.remove_from_playlist_clicked.emit(song_item.song, song_item.playlist_index))

            else:
                act_add = menu.addAction(qta.icon('fa5s.plus', color=THEME['text_main']), "Dodaj do kolejki")
                act_add.triggered.connect(lambda: song_item.add_to_queue_clicked.emit(song_item.song))

                act_add_pl = menu.addAction(qta.icon('fa5s.folder-plus', color=THEME['text_main']), "Dodaj do playlisty")
                act_add_pl.triggered.connect(lambda: song_item.add_to_playlist_clicked.emit(song_item.song))

            menu.addSeparator()

        act_album = menu.addAction(qta.icon('fa5s.compact-disc', color=THEME['text_main']), "Przejdź do albumu")
        act_album.triggered.connect(song_item._on_album_click)

        act_artist = menu.addAction(qta.icon('fa5s.user', color=THEME['text_main']), "Przejdź do wykonawcy")
        act_artist.triggered.connect(song_item._on_artist_click)

        act_dl_audio = menu.addAction(qta.icon('fa5s.music', color=THEME['text_main']), "Pobierz utwór offline")
        act_dl_audio.triggered.connect(lambda: SongContextMenu._download_audio(song_item))

        act_dl = menu.addAction(qta.icon('fa5s.download', color=THEME['text_main']), "Pobierz teledysk offline")
        act_dl.triggered.connect(lambda: SongContextMenu._download_video(song_item))

        act_set_yt = menu.addAction(qta.icon('fa5s.link', color=THEME['text_muted']), "Ustaw link YouTube")
        act_set_yt.triggered.connect(lambda: SongContextMenu._set_yt_link_dialog(song_item))

        menu.addSeparator()

        act_custom_cov = menu.addAction(qta.icon('fa5s.image', color=THEME['text_main']), "Ustaw własną okładkę")
        act_custom_cov.triggered.connect(lambda: song_item.set_custom_cover_clicked.emit(song_item.song, MediaType.SONG))

        act_reset_cov = menu.addAction(qta.icon('fa5s.undo', color=THEME['text_main']), "Przywróć domyślną")
        act_reset_cov.triggered.connect(lambda: song_item.reset_custom_cover_clicked.emit(song_item.song, MediaType.SONG))

        act_save_img = menu.addAction(qta.icon('fa5s.download', color=THEME['text_main']), "Zapisz okładkę do pliku")
        act_save_img.triggered.connect(lambda: song_item.save_image_clicked.emit(song_item.song, MediaType.SONG))

        global_pos = song_item.btn_more.mapToGlobal(QPoint(0, song_item.btn_more.height()))
        menu.exec(global_pos)

    @staticmethod
    def _set_yt_link_dialog(song_item):
        from utils import _YT_LINK_OVERRIDES
        song = song_item.song
        current_override = _YT_LINK_OVERRIDES.get(song.item_id, "")
        current_from_comment = song.yt_link if not current_override else None

        dlg = QDialog(song_item)
        dlg.setWindowTitle(f"Link YouTube — {song.title}")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {THEME['bg_main']}; color: {THEME['text_main']}; }}
            QLabel {{ background: transparent; }}
            QLineEdit {{
                background: {THEME['bg_card']};
                color: {THEME['text_main']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 13px;
            }}
            QPushButton {{
                background: {THEME['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {THEME['nav_hover']}; }}
            QPushButton#btn_clear {{
                background: {THEME['bg_card']};
                color: {THEME['text_muted']};
                border: 1px solid {THEME['border']};
            }}
            QPushButton#btn_cancel {{
                background: transparent;
                color: {THEME['text_muted']};
                border: 1px solid {THEME['border']};
            }}
        """)

        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        info_lbl = QLabel()
        info_lbl.setWordWrap(True)
        if current_override:
            info_lbl.setText(f"<b>Aktualny override:</b> {current_override}")
            info_lbl.setStyleSheet(f"color: {THEME['accent']}; background: transparent;")
        elif current_from_comment:
            info_lbl.setText(f"<b>Link z tagów (purl/komentarz):</b> {current_from_comment}")
            info_lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        else:
            info_lbl.setText("Ten utwór nie ma przypisanego linku YouTube.")
            info_lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        lay.addWidget(info_lbl)

        url_input = QLineEdit()
        url_input.setPlaceholderText("https://www.youtube.com/watch?v=... lub https://youtu.be/...")
        url_input.setText(current_override)
        lay.addWidget(url_input)

        status_lbl = QLabel(" ")
        status_lbl.setStyleSheet(f"color: #e74c3c; background: transparent; font-size: 12px;")
        lay.addWidget(status_lbl)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Usuń override")
        btn_clear.setObjectName("btn_clear")
        btn_clear.setEnabled(bool(current_override))
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.setObjectName("btn_cancel")
        btn_save = QPushButton("Zapisz")
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

        def validate_and_save():
            url = url_input.text().strip()
            if not url:
                status_lbl.setText("URL nie może być pusty. Użyj 'Usuń override' aby skasować.")
                return
            if not ('youtube.com/watch' in url or 'youtu.be/' in url):
                status_lbl.setText("Nieprawidłowy link. Wklej pełny link YouTube lub youtu.be.")
                return
            win = song_item._find_main_window()
            if win:
                win.engine.video_download_manager.save_yt_link_override(
                    song.item_id, url, song.title
                )
            song_item._update_dl_status_icon()
            dlg.accept()

        def clear_override():
            win = song_item._find_main_window()
            if win:
                win.engine.video_download_manager.delete_yt_link_override(song.item_id)
            song_item._update_dl_status_icon()
            dlg.accept()

        btn_save.clicked.connect(validate_and_save)
        btn_cancel.clicked.connect(dlg.reject)
        btn_clear.clicked.connect(clear_override)
        url_input.returnPressed.connect(validate_and_save)

        dlg.exec()

    @staticmethod
    def _download_video(song_item):
        song = song_item.song
        yt_link = getattr(song, 'yt_link', None) or getattr(song, 'youtube_url', None)
        if not yt_link:
            comment = (song.get('comment', '') or '') + ' ' + (song.get('purl', '') or '') + ' ' + (song.get('PURL', '') or '')
            has_youtube_comment = 'youtube.com' in comment.lower() or 'youtu.be' in comment.lower()

            if has_youtube_comment:
                msg = (f"\"{ song.title }\" posiada opis z YouTube, ale bezpośredni link do klipu "
                       f"nie jest poprawnie odczytany z taga purl ani komentarza.\n\n"
                       f"Aby można było pobrać teledysk offline, dodaj link YouTube (np. "
                       f"https://youtu.be/VIDEO_ID) do pola PURL lub komentarza.")
            else:
                msg = (f"\"{ song.title }\" nie posiada linku YouTube w tagach PURL ani komentarzu.\n\n"
                       f"Aby pobrać teledysk offline, dodaj link YouTube (np. "
                       f"https://youtu.be/VIDEO_ID) w tagu PURL lub komentarzu do tego utworu.")

            QMessageBox.warning(song_item, "Brak linku YouTube", msg)
            logger.log(f"Brak linku YT dla utworu {song.title}")
            return

        win = song_item._find_main_window()
        if win:
            mgr = win.engine.video_download_manager
            import sqlite3
            conn = sqlite3.connect(mgr.db_path)
            c = conn.cursor()
            c.execute("SELECT status FROM downloads WHERE item_id = ?", (song.item_id,))
            row = c.fetchone()

            if row and row[0] == "ERROR":
                ans = QMessageBox.question(song_item, "Błąd pobierania",
                                          "Ten teledysk napotkał wcześniej błąd podczas pobierania (np. brak dostępu, nieistniejący film lub problem z siecią).\n\nCzy chcesz spróbować pobrać go ponownie?",
                                          QMessageBox.Yes | QMessageBox.No)
                if ans == QMessageBox.No:
                    conn.close()
                    return
                c.execute("UPDATE downloads SET is_hidden = 0 WHERE item_id = ?", (song.item_id,))
                conn.commit()

            conn.close()

            mgr.add_to_queue(
                song.item_id,
                yt_link,
                song.title,
                high_priority=True,
                cover_id=song.cover_id
            )
            song_item._update_dl_status_icon()
            QMessageBox.information(song_item, "Pobieranie", "Dodano do kolejki pobierania (lub wznowiono zadanie).")
        else:
            logger.log("Nie można połączyć z Download Managerem")

    @staticmethod
    def _download_audio(song_item):
        win = song_item._find_main_window()
        if win and hasattr(win, 'engine') and hasattr(win.engine, 'audio_download_manager'):
            mgr = win.engine.audio_download_manager
            
            if mgr.is_downloaded(song_item.song.item_id):
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(song_item, "Pobieranie Audio", "Ten utwór jest już pobrany na dysk.")
                return
                
            mgr.add_to_queue(song_item.song.item_id, song_item.song.title, high_priority=True)
            song_item._update_dl_status_icon()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(song_item, "Pobieranie Audio", "Utwór został dodany do kolejki pobierania offline.")
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(song_item, "Błąd", "Audio Download Manager nie jest dostępny.")
