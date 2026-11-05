import os
os.environ["QT_API"] = "pyside6"

import threading
import requests
from PySide6.QtCore import QTimer
from utils import logger
from core.enums import EngineState

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
                    if f.endswith('.mp3'):
                        song_id = f.replace('.mp3', '')
                        if song_id not in active_ids:
                            files.append(os.path.join(cache_dir, f))
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
            final_path = os.path.join(self.engine.cache_dir, f"{song_id}.mp3")
            part_path = final_path + ".part"

            if os.path.exists(final_path):
                if not is_prefetch:
                    self.engine.audio_track_cached.emit(song_id, final_path)
                return

            try:
                session = getattr(self.engine.client, 'session', requests)
                res = session.get(url, stream=True, timeout=(3.0, 10.0))
                res.raise_for_status()
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