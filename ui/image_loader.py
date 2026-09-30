import os
os.environ["QT_API"] = "pyside6"

import time
import threading
import weakref
from urllib.parse import urlparse, parse_qs
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QNetworkDiskCache
from core.paths import PathsManager

class AsyncImageLoader(QObject):
    """
    Asynchroniczny silnik pobierania i buforowania okładek oraz zdjęć artystów.
    Obsługuje 3 poziomy pamięci: RAM cache, lokalny cache dyskowy oraz pobieranie HTTP (QNetworkDiskCache).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.disk_cache = QNetworkDiskCache(self)

        cp = PathsManager.get_images_cache_dir()
        cp.mkdir(parents=True, exist_ok=True)
        self.disk_cache.setCacheDirectory(str(cp))
        self.manager.setCache(self.disk_cache)

        self.custom_artists_dir = PathsManager.get_data_dir() / "custom_artists"
        self.custom_artists_dir.mkdir(parents=True, exist_ok=True)

        self.custom_covers_dir = PathsManager.get_data_dir() / "custom_covers"
        self.custom_covers_dir.mkdir(parents=True, exist_ok=True)

        self.covers_cache_dir = PathsManager.get_cache_dir() / "covers"
        self.covers_cache_dir.mkdir(parents=True, exist_ok=True)

        self.queue = []
        self.active_reqs = 0
        self.MAX_ACTIVE = 10
        self._in_flight = {}

        self._ram_cache = {}
        self.MAX_RAM_CACHE_SIZE = 300
        self._custom_artists_files = set()
        self._custom_covers_files = set()
        self._covers_cache_files = set()
        self.refresh_file_indexes()

    def refresh_file_indexes(self):
        try:
            self._custom_artists_files = set(os.listdir(self.custom_artists_dir))
        except Exception:
            self._custom_artists_files = set()

        try:
            self._custom_covers_files = set(os.listdir(self.custom_covers_dir))
        except Exception:
            self._custom_covers_files = set()

        try:
            self._covers_cache_files = set(os.listdir(self.covers_cache_dir))
        except Exception:
            self._covers_cache_files = set()

        self._add_to_ram_cache_safe()

    def _add_to_ram_cache_safe(self):
        pass

    def _add_to_ram_cache(self, url: str, pix: QPixmap):
        if not pix or pix.isNull():
            return
        if url in self._ram_cache:
            return
        if len(self._ram_cache) >= self.MAX_RAM_CACHE_SIZE:
            first_key = next(iter(self._ram_cache))
            del self._ram_cache[first_key]
        self._ram_cache[url] = pix

    def load(self, url: str, target):
        if not url or target is None:
            return

        target_ref = weakref.ref(target)

        if url in self._ram_cache:
            pix = self._ram_cache[url]
            t = target_ref()
            if t:
                t.set_image(pix, animate=False)
            return

        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if 'id' in qs:
                cover_id = qs['id'][0]
                found_path = None
                for ext in ['.jpg', '.jpeg', '.png']:
                    fname = f"{cover_id}{ext}"
                    if fname in self._custom_artists_files:
                        found_path = os.path.join(self.custom_artists_dir, fname)
                        break
                    if fname in self._custom_covers_files:
                        found_path = os.path.join(self.custom_covers_dir, fname)
                        break

                if not found_path:
                    fname = f"{cover_id}.jpg"
                    if fname in self._covers_cache_files:
                        found_path = os.path.join(self.covers_cache_dir, fname)

                if found_path and os.path.exists(found_path):
                    pix = QPixmap(found_path)
                    if not pix.isNull():
                        self._add_to_ram_cache(url, pix)
                        t = target_ref()
                        if t:
                            t.set_image(pix, animate=False)
                        return
        except Exception:
            pass

        if url in self._in_flight:
            if target_ref not in self._in_flight[url]:
                self._in_flight[url].append(target_ref)
            return

        self.queue.append((url, target_ref))
        self._process()

    def _process(self):
        while self.queue and self.active_reqs < self.MAX_ACTIVE:
            url, target_ref = self.queue.pop(0)
            target = target_ref()
            if target is None:
                continue
            self._in_flight[url] = [target_ref]
            self.active_reqs += 1
            req = QNetworkRequest(QUrl(url))
            reply = self.manager.get(req)
            reply.setProperty("url", url)
            reply.setProperty("start_time", time.time())
            reply.finished.connect(self._done)

        def _done(self):
            pass

    def _done(self):
        self.active_reqs -= 1
        reply = self.sender()
        url = reply.property("url")
        start_time = reply.property("start_time")
        duration = time.time() - start_time
        is_fast_cache = (duration < 0.05)
        target_refs = self._in_flight.pop(url, [])

        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            raw_bytes = data.data()
            pix = QPixmap()
            pix.loadFromData(data)

            if not pix.isNull():
                self._add_to_ram_cache(url, pix)

            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                if 'id' in qs:
                    cid = qs['id'][0]
                    fname = f"{cid}.jpg"
                    cached_path = os.path.join(self.covers_cache_dir, fname)

                    def save_cover():
                        try:
                            with open(cached_path, "wb") as f:
                                f.write(raw_bytes)
                            self._covers_cache_files.add(fname)
                        except Exception:
                            pass

                    threading.Thread(target=save_cover, daemon=True).start()
            except Exception:
                pass

            for target_ref in target_refs:
                try:
                    target = target_ref()
                    if target:
                        target.set_image(pix, animate=(not is_fast_cache))
                except RuntimeError:
                    pass

        reply.deleteLater()
        self._process()