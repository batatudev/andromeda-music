import os
os.environ["QT_API"] = "pyside6"

import threading
import time
from pathlib import Path
from PySide6.QtCore import QUrl
from config import APP_CONFIG
from utils import logger
from core.enums import EngineState, VideoResolution
from core.paths import PathsManager

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

class YtErrorType:
    INVALID_LINK = "INVALID_LINK"
    BLOCKED_OR_REMOVED = "BLOCKED_OR_REMOVED"
    RATE_LIMIT = "RATE_LIMIT"
    BOT_CHECK = "BOT_CHECK"
    AGE_RESTRICTED = "AGE_RESTRICTED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    UNKNOWN = "UNKNOWN"

def classify_yt_error(error_or_msg) -> str:
    msg = str(error_or_msg).lower()

    if (
        "is not a valid url" in msg
        or "incomplete youtube id" in msg
        or "unsupported url" in msg
        or "no suitable extractor" in msg
        or "invalid url" in msg
        or "url is not valid" in msg
    ):
        return YtErrorType.INVALID_LINK

    if "429" in msg or "too many requests" in msg or "rate-limit" in msg or "rate limit" in msg:
        return YtErrorType.RATE_LIMIT

    if "confirm you're not a bot" in msg or "bot verification" in msg or "automated traffic" in msg or "captcha" in msg:
        return YtErrorType.BOT_CHECK

    if "sign in to confirm your age" in msg or "age-restricted" in msg or "age restricted" in msg:
        return YtErrorType.AGE_RESTRICTED

    if (
        "unavailable" in msg
        or "not available" in msg
        or "private video" in msg
        or "has been removed" in msg
        or "members-only" in msg
        or "does not exist" in msg
        or "copyright" in msg
        or "blocked it in your country" in msg
    ):
        return YtErrorType.BLOCKED_OR_REMOVED

    if (
        "timed out" in msg
        or "timeout" in msg
        or "connection reset" in msg
        or "network is unreachable" in msg
        or "unable to download webpage" in msg
    ):
        return YtErrorType.NETWORK_TIMEOUT

    return YtErrorType.UNKNOWN

class YTResolver:
    def __init__(self, engine):
        self.engine = engine
        self._last_rate_limit_toast_time = 0

    def get_cached_url(self, h_limit):
        info = getattr(self.engine, '_current_yt_info_dict', None)
        if not info:
            return None
        try:
            formats = info.get('formats', [])
            best_url = None
            best_h = -1
            best_vcodec = ""
            for f in formats:
                if f.get('vcodec') and f.get('vcodec') != 'none':
                    h = f.get('height', 0)
                    vc = f.get('vcodec', '')
                    if h and h <= h_limit:
                        if ('avc1' in vc and 'avc1' not in best_vcodec) or (h > best_h and ('avc1' in vc or 'avc1' not in best_vcodec)):
                            best_url = f.get('url')
                            best_h = h
                            best_vcodec = vc
            return best_url
        except Exception:
            return None

    def _build_base_ydl_opts(self, h_limit, abort_check):
        target_fps = APP_CONFIG.get("video_fps", "60")
        fps_filter = "[fps<=30]" if str(target_fps) == "30" else "[fps<=60]"

        format_selector = (
            f'bestvideo[height<={h_limit}]{fps_filter}[vcodec!*=av01][vcodec^=avc1]/'
            f'bestvideo[height<={h_limit}]{fps_filter}[vcodec!*=av01][vcodec^=vp09]/'
            f'bestvideo[height<={h_limit}]{fps_filter}[vcodec!*=av01]/'
            f'bestvideo[height<={h_limit}][vcodec!*=av01]/'
            f'best[height<={h_limit}][vcodec!*=av01]/best'
        )

        return {
            'format': format_selector,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'match_filter': abort_check,
            'retries': 1,
            'socket_timeout': 5.0,
        }

    def prefetch_video_url(self, song):
        if not HAS_YTDLP:
            return
        self.engine.prefetched_song_id = song.item_id
        if getattr(self.engine, 'prefetch_cancel_event', None):
            self.engine.prefetch_cancel_event.set()
        self.engine.prefetch_cancel_event = threading.Event()
        current_event = self.engine.prefetch_cancel_event

        def fetch():
            yt_link = getattr(song, 'yt_link', None) or getattr(song, 'youtube_url', None)
            if not yt_link and hasattr(self.engine, 'client') and self.engine.client:
                from engine.header_tag_extractor import check_and_cache_remote_header
                yt_link = check_and_cache_remote_header(
                    self.engine.client, song, getattr(self.engine, 'video_download_manager', None)
                )
            if not yt_link or current_event.is_set():
                return

            rl = APP_CONFIG.get("video_resolution", "1080p")
            if rl == VideoResolution.RES_1080P:
                h_limit = 1080
            elif rl == VideoResolution.RES_720P:
                h_limit = 720
            elif rl == VideoResolution.RES_480P:
                h_limit = 480
            else:
                h_limit = 240

            def abort_check(info_dict):
                if current_event.is_set():
                    raise ValueError("Prefetch aborted")
                return None

            ydl_opts = self._build_base_ydl_opts(h_limit, abort_check)
            cookies_file = PathsManager.get_cookies_file()
            if cookies_file.exists():
                ydl_opts['cookiefile'] = str(cookies_file)

            if current_event.is_set():
                return

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(yt_link, download=False)
                    if 'url' in info and not current_event.is_set():
                        self.engine.prefetched_yt_url = info['url']
                        self.engine.prefetched_yt_info_dict = info
                except ValueError:
                    return
                except Exception:
                    pass

        threading.Thread(target=fetch, daemon=True).start()

    def load_and_play_video(self, force_mid_track=False):
        if getattr(self.engine, 'yt_cancel_event', None):
            self.engine.yt_cancel_event.set()
        self.engine.yt_cancel_event = threading.Event()
        current_event = self.engine.yt_cancel_event

        current_resolve_id = self.engine.resolve_id
        if force_mid_track:
            self.engine._sync_start_active = False
            self.engine.video_needs_sync_on_load = True
        elif getattr(self.engine, '_is_new_track_starting', False):
            self.engine._sync_start_active = True
            self.engine._is_new_track_starting = False
            self.engine.video_needs_sync_on_load = False
            self.engine.sync_timeout_timer.start(6000)
        else:
            self.engine.video_needs_sync_on_load = True

        if getattr(self.engine, 'prefetched_song_id', None) == self.engine.queue[self.engine.idx].item_id:
            if getattr(self.engine, 'prefetched_yt_url', None):
                logger.decision("PREFETCH", "Kolejny utwór wywołany do gry", "Używam gotowego linku z tła (Zero-Wait)")
                self.engine.last_resolve_time = 0
                self.engine.video_ready.emit(self.engine.prefetched_yt_url)
                self.engine.prefetched_song_id = None
                self.engine.prefetched_yt_url = None
                return

        self.engine.current_engine_state = EngineState.RESOLVING_YTDLP

        def fetch():
            if self.engine.queue and 0 <= self.engine.idx < len(self.engine.queue):
                song = self.engine.queue[self.engine.idx]
                fresh_link = song.yt_link
                if not fresh_link and hasattr(self.engine, 'client') and self.client:
                    from engine.header_tag_extractor import check_and_cache_remote_header
                    fresh_link = check_and_cache_remote_header(
                        self.client, song, getattr(self.engine, 'video_download_manager', None)
                    )
                self.engine.current_yt_link = fresh_link

            if not self.engine.current_yt_link or current_event.is_set():
                if self.engine.resolve_id == current_resolve_id:
                    self.engine.video_resolve_failed.emit(YtErrorType.INVALID_LINK)
                return

            start_time = time.time()
            rl = self.engine.current_video_resolution
            if rl == VideoResolution.RES_1080P:
                h_limit = 1080
            elif rl == VideoResolution.RES_720P:
                h_limit = 720
            elif rl == VideoResolution.RES_480P:
                h_limit = 480
            else:
                h_limit = 240

            if getattr(self.engine, '_current_yt_info_dict', None):
                cached_url = self.get_cached_url(h_limit)
                if cached_url:
                    if self.engine.resolve_id == current_resolve_id:
                        self.engine.last_resolve_time = int((time.time() - start_time) * 1000)
                        logger.decision("ARF SMART CACHE", f"Przełączenie na {self.engine.current_video_resolution}", "Natychmiastowe rozwiązanie z pamięci lokalnej (Zero-Wait)")
                        self.engine.video_ready.emit(cached_url)
                    return

            def abort_check(info_dict):
                if current_event.is_set():
                    raise ValueError("YT-DLP Cancelled by Kill-Switch")
                return None

            success_url = None
            last_error_type = None
            cookies_file = PathsManager.get_cookies_file()

            if cookies_file.exists():
                try:
                    ydl_opts_file = self._build_base_ydl_opts(h_limit, abort_check)
                    ydl_opts_file['cookiefile'] = str(cookies_file)
                    with yt_dlp.YoutubeDL(ydl_opts_file) as ydl:
                        info = ydl.extract_info(self.engine.current_yt_link, download=False)
                        if 'url' in info:
                            success_url = info['url']
                            self.engine._current_yt_info_dict = info
                except ValueError:
                    return
                except Exception as e:
                    last_error_type = classify_yt_error(e)
                    logger.log(f"Błąd użycia cookies.txt ({last_error_type}): {e}")

            if not success_url and not current_event.is_set():
                try:
                    ydl_opts_fast = self._build_base_ydl_opts(h_limit, abort_check)
                    with yt_dlp.YoutubeDL(ydl_opts_fast) as ydl:
                        info = ydl.extract_info(self.engine.current_yt_link, download=False)
                        if 'url' in info:
                            success_url = info['url']
                            self.engine._current_yt_info_dict = info
                except ValueError:
                    return
                except Exception as e:
                    last_error_type = classify_yt_error(e)

            if (
                not success_url
                and not current_event.is_set()
                and not cookies_file.exists()
                and last_error_type not in (YtErrorType.INVALID_LINK, YtErrorType.BLOCKED_OR_REMOVED)
            ):
                browsers = ['firefox', 'chrome', 'brave', 'chromium']
                for browser in browsers:
                    if current_event.is_set():
                        return
                    try:
                        ydl_opts_browser = self._build_base_ydl_opts(h_limit, abort_check)
                        ydl_opts_browser['cookiesfrombrowser'] = (browser,)
                        with yt_dlp.YoutubeDL(ydl_opts_browser) as ydl:
                            info = ydl.extract_info(self.engine.current_yt_link, download=False)
                            if 'url' in info:
                                success_url = info['url']
                                self.engine._current_yt_info_dict = info
                                break
                    except ValueError:
                        return
                    except Exception as e:
                        last_error_type = classify_yt_error(e)
                        logger.log(f"Fallback przeglądarki {browser} pominięty: {e}")
                        continue

            if current_event.is_set():
                return

            if (
                not success_url
                and not current_event.is_set()
                and last_error_type not in (YtErrorType.RATE_LIMIT, YtErrorType.INVALID_LINK, YtErrorType.BLOCKED_OR_REMOVED)
            ):
                try:
                    ydl_opts_tv = self._build_base_ydl_opts(h_limit, abort_check)
                    ydl_opts_tv['extractor_args'] = {'youtube': {'player_client': ['tv']}}
                    with yt_dlp.YoutubeDL(ydl_opts_tv) as ydl:
                        info = ydl.extract_info(self.engine.current_yt_link, download=False)
                        if 'url' in info:
                            success_url = info['url']
                            self.engine._current_yt_info_dict = info
                except ValueError:
                    return
                except Exception as e:
                    last_error_type = classify_yt_error(e)
                    logger.log(f"Awaryjny klient TV zawiódł: {e}")

            if self.engine.resolve_id == current_resolve_id:
                self.engine.last_resolve_time = int((time.time() - start_time) * 1000)
                if success_url:
                    self.engine.video_ready.emit(success_url)
                else:
                    final_err = last_error_type or YtErrorType.BLOCKED_OR_REMOVED
                    logger.log(f"yt-dlp: Rozwiązanie wideo zakończone niepowodzeniem (Klasyfikacja: {final_err}).")
                    self.engine.video_resolve_failed.emit(final_err)

        threading.Thread(target=fetch, daemon=True).start()

    def on_video_resolved(self, direct_url):
        if not direct_url:
            self.on_video_resolve_failed(YtErrorType.BLOCKED_OR_REMOVED)
            return
        self.engine.video_stream_start_time = time.time()
        self.engine.video_player.setSource(QUrl(direct_url))

    def on_video_resolve_failed(self, error_type=None):
        if getattr(self.engine, '_sync_start_active', False):
            self.engine.sync_timeout_timer.stop()
            self.engine._sync_start_active = False
            self.engine.loading_changed.emit(False)
            if getattr(self.engine, '_audio_loaded_for_sync', False):
                self.engine.player.play()
        else:
            self.engine.loading_changed.emit(False)

        self.engine.video_killed_for_track = True
        self.engine.current_engine_state = EngineState.VIDEO_DISABLED
        self.engine.video_player.stop()
        self.engine.video_player.setSource(QUrl(""))
        self.engine.video_player.setPlaybackRate(1.0)
        self.engine._deactivate_sync_timer()
        self.engine.has_video_signal.emit(False)

        self._notify_user_of_failure(error_type)

    def _notify_user_of_failure(self, error_type=None):
        now = time.time()
        final_type = error_type or YtErrorType.BLOCKED_OR_REMOVED

        if final_type in (YtErrorType.RATE_LIMIT, YtErrorType.BOT_CHECK):
            if (now - self._last_rate_limit_toast_time) > 600:
                self._last_rate_limit_toast_time = now
                self.engine.video_error_occurred.emit(final_type, "")
        else:
            self.engine.video_error_occurred.emit(final_type, "")