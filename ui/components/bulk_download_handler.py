import os
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QMessageBox
from config import APP_CONFIG, THEME
from core.models import MediaItem
from utils import logger

class BulkDownloadHandler:
    """
    Zarządza operacjami masowego pobierania oraz automatyczną synchronizacją ulubionych.
    """
    @staticmethod
    def sync_auto_downloads(main_window):
        def fetch():
            video_songs = []
            audio_songs = []

            if APP_CONFIG.get("video_auto_dl_favs", False):
                video_songs.extend(main_window.client.get_starred(1000))
            if APP_CONFIG.get("audio_auto_dl_favs", False):
                audio_songs.extend(main_window.client.get_starred(1000))

            v_pl_ids = APP_CONFIG.get("video_auto_dl_playlists", [])
            for pid in v_pl_ids:
                try:
                    params = main_window.client._get_auth_params()
                    params["id"] = pid
                    res = main_window.client._make_request("getPlaylist", params)
                    entry = res.get("playlist", {}).get("entry", [])
                    video_songs.extend([MediaItem(s) for s in entry])
                except Exception as e:
                    logger.log(f"Auto-sync wideo playlist {pid} failed: {e}")

            a_pl_ids = APP_CONFIG.get("audio_auto_dl_playlists", [])
            for pid in a_pl_ids:
                try:
                    params = main_window.client._get_auth_params()
                    params["id"] = pid
                    res = main_window.client._make_request("getPlaylist", params)
                    entry = res.get("playlist", {}).get("entry", [])
                    audio_songs.extend([MediaItem(s) for s in entry])
                except Exception as e:
                    logger.log(f"Auto-sync audio playlist {pid} failed: {e}")

            return video_songs, audio_songs

        def on_ready(result):
            if not result:
                return
            video_songs, audio_songs = result

            v_items_to_add = []
            for s in video_songs:
                link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
                if link:
                    v_items_to_add.append((s.item_id, link, s.title, s.cover_id))
            if v_items_to_add:
                main_window.engine.video_download_manager.add_to_queue_bulk(v_items_to_add, high_priority=False)

            a_items_to_add = [(s.item_id, s.title) for s in audio_songs]
            if a_items_to_add:
                main_window.engine.audio_download_manager.add_to_queue_bulk(a_items_to_add, high_priority=False)

        main_window.run_async(fetch, on_ready, page_bound=False)

    @staticmethod
    def start_bulk_download(main_window, bulk_type, target_id=None, target_name=None, media_type="video"):
        if main_window._is_fetching:
            return

        def fetch():
            songs = []
            if bulk_type == "favorites":
                songs = main_window.client.get_starred(1000)
            elif bulk_type == "playlist":
                params = main_window.client._get_auth_params()
                params["id"] = target_id
                res = main_window.client._make_request("getPlaylist", params)
                entry = res.get("playlist", {}).get("entry", [])
                songs = [MediaItem(s) for s in entry]
            elif bulk_type == "album":
                songs = main_window.client.get_album(target_id).get('song', [])
            elif bulk_type == "artist":
                songs = main_window.client.get_top_songs_for_artist(target_id, limit=500)
            elif bulk_type == "all":
                if hasattr(main_window, 'repo'):
                    return main_window.repo.library_sync.get_all_songs()
                else:
                    songs = main_window.client.get_random_songs(1000)
            return songs

        def on_ready(songs):
            if not songs:
                QMessageBox.information(main_window, "Brak utworów", "Nie znaleziono utworów do pobrania.")
                return

            if media_type == "video":
                valid_songs = [s for s in songs if getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)]
                if not valid_songs:
                    QMessageBox.information(main_window, "Brak linków", "Znalezione utwory nie posiadają linków do wideo.")
                    return

                quality = APP_CONFIG.get("video_offline_quality", "1080p")
                avg_mb = 25
                if quality == "720p":
                    avg_mb = 15
                elif quality == "480p":
                    avg_mb = 10

                count = len(valid_songs)
                est_mb = count * avg_mb
                est_str = f"{est_mb / 1024:.2f} GB" if est_mb > 1024 else f"{est_mb} MB"

                msg = f"Znaleziono {count} utworów z teledyskami.\nSzacowany rozmiar do pobrania: ~{est_str} (Jakość: {quality}).\n\nCzy chcesz rozpocząć pobieranie wideo?"
                ans = QMessageBox.question(main_window, "Potwierdzenie pobierania", msg, QMessageBox.Yes | QMessageBox.No)

                if ans == QMessageBox.Yes:
                    items_to_add = []
                    for s in valid_songs:
                        link = getattr(s, 'yt_link', None) or getattr(s, 'youtube_url', None)
                        if link:
                            items_to_add.append((s.item_id, link, s.title, s.cover_id))
                    if items_to_add:
                        main_window.engine.video_download_manager.add_to_queue_bulk(items_to_add, high_priority=False)
                    main_window.show_toast(
                        f"Dodano zadania ({len(items_to_add)}) do kolejki pobierania wideo.",
                        title="Pobieranie Wideo",
                        icon_str="fa5s.film",
                        icon_color="#e74c3c"
                    )

            elif media_type == "audio":
                valid_songs = [s if isinstance(s, MediaItem) else MediaItem(s) for s in songs]

                avg_mb = 6
                count = len(valid_songs)
                est_mb = count * avg_mb
                est_str = f"{est_mb / 1024:.2f} GB" if est_mb > 1024 else f"{est_mb} MB"

                msg = f"Znaleziono {count} utworów audio.\nSzacowany rozmiar do pobrania: ~{est_str}.\n\nCzy chcesz rozpocząć pobieranie muzyki?"
                ans = QMessageBox.question(main_window, "Potwierdzenie pobierania", msg, QMessageBox.Yes | QMessageBox.No)

                if ans == QMessageBox.Yes:
                    items_to_add = [(s.item_id, s.title) for s in valid_songs]
                    if items_to_add:
                        main_window.engine.audio_download_manager.add_to_queue_bulk(items_to_add, high_priority=False)
                    main_window.show_toast(
                        f"Dodano zadania ({len(items_to_add)}) do kolejki pobierania audio.",
                        title="Pobieranie Audio",
                        icon_str="fa5s.music",
                        icon_color=THEME.get("accent", "#1db954")
                    )

        main_window.run_async(fetch, on_ready, page_bound=False)