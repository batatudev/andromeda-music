import os
os.environ["QT_API"] = "pyside6"

import threading
import requests
from PySide6.QtCore import QTimer
from utils import logger
from core.enums import EngineState

AUDIO_EXTENSIONS = ('.flac', '.opus', '.mp3', '.m4a', '.ogg', '.wav')

AUDIO_MIME_MAP = {
    'audio/flac': 'flac',
    'audio/x-flac': 'flac',
    'audio/opus': 'opus',
    'audio/x-opus': 'opus',
    'audio/ogg': 'ogg',
    'audio/vorbis': 'ogg',
    'audio/mp4': 'm4a',
    'audio/x-m4a': 'm4a',
    'audio/aac': 'm4a',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
}

class CacheManager:
    def __init__(self, engine):
        self.engine = engine

    def cleanup_cache(self):
        def task():
            try:
                active_ids = {s.item_id for s in getattr(self.engine, 'queue', []) if s.item_id}
                files = []
                cache_dir = self.engine.cache_dir
                if not os.path.exists(cache_dir):
                    return
                for f in os.listdir(cache_dir):
                    for ext in AUDIO_EXTENSIONS:
                        if f.endswith(ext):
                            song_id = f[:-len(ext)]
                            if song_id not in active_ids:
                                files.append(os.path.join(cache_dir, f))
                            break
                if len(files) > 100:
                    files.sort(key=os.path.getatime)
                    for f in files[:-100]:
                        try:
                            os.remove(f)
                        except OSError:
                            pass
            except Exception as e:
                logger.log(f"Błąd czyszczenia cache audio: {e}")

        threading.Thread(target=task, daemon=True).start()

    def start_audio_download(self, song, is_prefetch=False):
        song_id = song.item_id
        if not song_id:
            return
        url = self.engine.client.get_stream_url(song_id)
        if not is_prefetch:
            if self.engine.cancel_event:
                self.engine.cancel_event.set()
            self.engine.cancel_event = threading.Event()
            event = self.engine.cancel_event
        else:
            event = threading.Event()

        def task():
            part_path = os.path.join(self.engine.cache_dir, f"{song_id}.part")

            for ext in AUDIO_EXTENSIONS:
                candidate = os.path.join(self.engine.cache_dir, f"{song_id}{ext}")
                if os.path.exists(candidate):
                    if not is_prefetch:
                        self.engine.audio_track_cached.emit(song_id, candidate)
                    return

            try:
                session = getattr(self.engine.client, 'session', requests)
                res = session.get(url, stream=True, timeout=(3.0, 10.0))
                res.raise_for_status()

                content_type = res.headers.get('content-type', '').split(';')[0].strip().lower()
                detected_ext = AUDIO_MIME_MAP.get(content_type)
                if not detected_ext:
                    detected_ext = getattr(song, 'suffix', '') or 'mp3'

                final_path = os.path.join(self.engine.cache_dir, f"{song_id}.{detected_ext}")

                with open(part_path, "wb") as f:
                    for chunk in res.iter_content(chunk_size=65536):
                        if event.is_set():
                            break
                        if chunk:
                            f.write(chunk)

                if event.is_set():
                    if os.path.exists(part_path):
                        try:
                            os.remove(part_path)
                        except OSError:
                            pass
                    return

                if os.path.exists(part_path):
                    try:
                        os.rename(part_path, final_path)
                    except OSError:
                        pass

                if not is_prefetch and os.path.exists(final_path):
                    self.engine.audio_track_cached.emit(song_id, final_path)

            except Exception as e:
                if not event.is_set():
                    logger.log(f"Błąd pobierania audio ({song_id}): {e}")
                    if not is_prefetch:
                        self.engine.loading_changed.emit(False)
                        self.engine.current_engine_state = EngineState.AUDIO_ERROR
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass

        threading.Thread(target=task, daemon=True).start()