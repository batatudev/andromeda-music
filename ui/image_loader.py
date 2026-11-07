import os
os.environ["QT_API"] = "pyside6"

import time
import threading
import weakref
from urllib.parse import urlparse, parse_qs

from PySide6.QtCore import QObject, QUrl, Signal, Qt
from PySide6.QtGui import QPixmap, QImage, QImageReader
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QNetworkDiskCache

from core.paths import PathsManager
from ui.widgets.images import is_navidrome_placeholder

class AsyncImageLoader(QObject):
    """
    Wielowątkowy silnik asynchronicznego pobierania i buforowania okładek.
    Dekodowanie i skalowanie grafik odbywa się w tle z eliminacją fałszywych placeholderów serwera.
    """
    image_decoded = Signal(str, object, list, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.disk_cache = QNetworkDiskCache(self)

        cp = PathsManager.get_images_cache_dir()
        cp.mkdir(parents=True, exist_ok=True)
        self.disk_cache.setCacheDirectory(str(cp))
        self.manager.setCache(self.disk_cache)

        self.custom_artists_dir = PathsManager.get_custom_artists_dir()
        self.custom_artists_dir.mkdir(parents=True, exist_ok=True)

        self.custom_covers_dir = PathsManager.get_custom_covers_dir()
        self.custom_covers_dir.mkdir(parents=True, exist_ok=True)

        self.covers_cache_dir = PathsManager.get_covers_cache_dir()
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

        self.image_decoded.connect(self._on_image_decoded)

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
                    reader = QImageReader(found_path)
                    orig_size = reader.size()
                    if orig_size.width() > 500 or orig_size.height() > 500:
                        scaled_size = orig_size.scaled(500, 500, Qt.KeepAspectRatio)
                        reader.setScaledSize(scaled_size)
                    img = reader.read()
                    if not img.isNull():
                        if is_navidrome_placeholder(img):
                            try:
                                os.remove(found_path)
                            except Exception:
                                pass
                        else:
                            pix = QPixmap.fromImage(img)
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
        self.active_reqs -= 1
        reply = self.sender()
        url = reply.property("url")
        start_time = reply.property("start_time")
        duration = time.time() - start_time
        is_fast_cache = (duration < 0.05)
        target_refs = self._in_flight.pop(url, [])

        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            raw_bytes = bytes(data)

            def decode_task(raw, u, refs, fast):
                img = QImage()
                img.loadFromData(raw)
                if not img.isNull():
                    if is_navidrome_placeholder(img):
                        self.image_decoded.emit(u, None, refs, fast)
                        return

                    if img.width() > 500 or img.height() > 500:
                        img = img.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_decoded.emit(u, img, refs, fast)

                try:
                    parsed = urlparse(u)
                    qs = parse_qs(parsed.query)
                    if 'id' in qs:
                        cid = qs['id'][0]
                        fname = f"{cid}.jpg"
                        cached_path = os.path.join(self.covers_cache_dir, fname)
                        with open(cached_path, "wb") as f:
                            f.write(raw)
                        self._covers_cache_files.add(fname)
                except Exception:
                    pass

            threading.Thread(
                target=decode_task,
                args=(raw_bytes, url, target_refs, is_fast_cache),
                daemon=True
            ).start()

        reply.deleteLater()
        self._process()

    def _on_image_decoded(self, url, img, target_refs, is_fast_cache):
        if not img or img.isNull():
            for target_ref in target_refs:
                try:
                    target = target_ref()
                    if target:
                        target.set_image(None, animate=False)
                except RuntimeError:
                    pass
            return

        pix = QPixmap.fromImage(img)
        self._add_to_ram_cache(url, pix)
        for target_ref in target_refs:
            try:
                target = target_ref()
                if target:
                    target.set_image(pix, animate=(not is_fast_cache))
            except RuntimeError:
                pass