import os
os.environ["QT_API"] = "pyside6"

import shutil
import requests
from PySide6.QtWidgets import QFileDialog
from utils import logger
from core.enums import MediaType

class CustomMediaManager:
    """
    Kontroler zarządzania własnymi okładkami albumów i zdjęciami wykonawców.
    """
    @staticmethod
    def set_custom_artist_image(parent, data, type_str, loader, on_finish):
        if type_str != MediaType.ARTIST:
            return

        artist_id = data.item_id
        cover_id = data.cover_id

        if not artist_id and not cover_id:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            parent, "Wybierz zdjęcie artysty", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        target_dir = loader.custom_artists_dir

        for cid in [artist_id, cover_id]:
            if not cid:
                continue
            for old_ext in ['.jpg', '.jpeg', '.png']:
                old_file = os.path.join(target_dir, f"{cid}{old_ext}")
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass

        try:
            if cover_id:
                shutil.copy2(file_path, os.path.join(target_dir, f"{cover_id}{ext}"))
            if artist_id and artist_id != cover_id:
                shutil.copy2(file_path, os.path.join(target_dir, f"{artist_id}{ext}"))

            loader.refresh_file_indexes()
            loader._ram_cache.clear()
            logger.log(f"Ustawiono własne zdjęcie dla artysty {artist_id or cover_id}")
            if on_finish:
                on_finish()
        except Exception as e:
            logger.log(f"Błąd kopiowania zdjęcia artysty: {e}")

    @staticmethod
    def reset_custom_artist_image(parent, data, type_str, loader, on_finish):
        if type_str != MediaType.ARTIST:
            return

        artist_id = data.item_id
        cover_id = data.cover_id

        target_dir = loader.custom_artists_dir
        deleted = False

        for cid in [artist_id, cover_id]:
            if not cid:
                continue
            for ext in ['.jpg', '.jpeg', '.png']:
                file_path = os.path.join(target_dir, f"{cid}{ext}")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted = True
                    except Exception:
                        pass

        if deleted:
            loader.refresh_file_indexes()
            loader._ram_cache.clear()
            logger.log(f"Przywrócono domyślne zdjęcie dla artysty {artist_id or cover_id}")
            if on_finish:
                on_finish()

    @staticmethod
    def set_custom_album_cover(parent, data, type_str, loader, on_finish, on_refresh_player_bar=None):
        if type_str not in [MediaType.ALBUM, MediaType.SONG]:
            return

        album_id = data.get('albumId') if type_str == MediaType.SONG else data.item_id
        cover_id = data.cover_id

        if not album_id and not cover_id:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            parent, "Wybierz okładkę", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        target_dir = loader.custom_covers_dir

        for cid in [album_id, cover_id]:
            if not cid:
                continue
            for old_ext in ['.jpg', '.jpeg', '.png']:
                old_file = os.path.join(target_dir, f"{cid}{old_ext}")
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass

        try:
            if cover_id:
                shutil.copy2(file_path, os.path.join(target_dir, f"{cover_id}{ext}"))
            if album_id and album_id != cover_id:
                shutil.copy2(file_path, os.path.join(target_dir, f"{album_id}{ext}"))

            loader.refresh_file_indexes()
            loader._ram_cache.clear()
            logger.log(f"Ustawiono własną okładkę dla {album_id or cover_id}")
            if on_finish:
                on_finish()
            if on_refresh_player_bar:
                on_refresh_player_bar(album_id, cover_id)
        except Exception as e:
            logger.log(f"Błąd kopiowania okładki: {e}")

    @staticmethod
    def reset_custom_album_cover(parent, data, type_str, loader, on_finish, on_refresh_player_bar=None):
        if type_str not in [MediaType.ALBUM, MediaType.SONG]:
            return

        album_id = data.get('albumId') if type_str == MediaType.SONG else data.item_id
        cover_id = data.cover_id

        target_dir = loader.custom_covers_dir
        deleted = False

        for cid in [album_id, cover_id]:
            if not cid:
                continue
            for ext in ['.jpg', '.jpeg', '.png']:
                file_path = os.path.join(target_dir, f"{cid}{ext}")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted = True
                    except Exception:
                        pass

        if deleted:
            loader.refresh_file_indexes()
            loader._ram_cache.clear()
            logger.log(f"Przywrócono domyślną okładkę dla {album_id or cover_id}")
            if on_finish:
                on_finish()
            if on_refresh_player_bar:
                on_refresh_player_bar(album_id, cover_id)

    @staticmethod
    def save_image_to_file(parent, client, data, type_str, run_async_fn):
        cover_id = data.cover_id
        if not cover_id:
            return

        default_name = f"{data.artist} - {data.title}.jpg"
        file_path, _ = QFileDialog.getSaveFileName(
            parent, "Zapisz obrazek jako...", default_name, "Images (*.jpg)"
        )
        if not file_path:
            return

        size = 600 if type_str != MediaType.ARTIST else 1000
        url = client.get_cover_art_url(cover_id, size=size)

        def task():
            try:
                res = requests.get(url, timeout=15)
                res.raise_for_status()
                with open(file_path, "wb") as f:
                    f.write(res.content)
                return True
            except Exception as e:
                logger.log(f"Błąd zapisu obrazka do pliku: {e}")
                return False

        def on_done(success):
            if success:
                logger.log("Zapisano grafikę do pliku.")

        run_async_fn(task, on_done)