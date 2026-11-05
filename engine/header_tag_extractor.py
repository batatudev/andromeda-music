import io
import re
import requests
from core.models import RE_YT_URL
from utils import logger, _set_yt_link_override

def fetch_purl_from_remote_header(api_client, item_id: str) -> str | None:
    """
    Pobiera pierwsze 256KB pliku audio z serwera Navidrome (Range Request)
    i odczytuje tag 'purl' / link YouTube z nagłówka pliku.
    """
    if not api_client or not item_id:
        return None

    try:
        stream_url = api_client.get_stream_url(item_id)
        if not stream_url:
            return None

        headers = {'Range': 'bytes=0-262144'}
        session = getattr(api_client, 'session', requests)
        resp = session.get(stream_url, headers=headers, timeout=4.0, stream=True)
        if resp.status_code not in (200, 206):
            return None

        content_chunk = resp.content
        if not content_chunk:
            return None

        found_url = None

        # 1. Próba parsowania przez mutagen
        try:
            import mutagen
            file_obj = io.BytesIO(content_chunk)
            audio = mutagen.File(file_obj)
            if audio and hasattr(audio, 'tags') and audio.tags:
                tags = audio.tags
                for key in ('purl', 'PURL', 'pURL', 'WXXX:PURL', 'WXXX'):
                    if key in tags:
                        val = str(tags[key])
                        if 'youtube.com' in val or 'youtu.be' in val:
                            m = RE_YT_URL.search(val)
                            if m:
                                found_url = m.group(0).strip()
                                break
                        elif val.startswith(('http://', 'https://')):
                            found_url = val.strip()
                            break

                if not found_url:
                    for k, v in tags.items():
                        val_str = str(v)
                        if 'youtube.com' in val_str or 'youtu.be' in val_str:
                            m = RE_YT_URL.search(val_str)
                            if m:
                                found_url = m.group(0).strip()
                                break
        except Exception as e:
            logger.log(f"[HeaderExtractor] Mutagen parse note: {e}")

        # 2. Resilient Regex Fallback na surowym buforze bajtów (gdy mutagen nie rozpoznaje niepełnego pliku)
        if not found_url:
            text_decoded = content_chunk.decode('latin1', errors='ignore')
            if 'youtube.com' in text_decoded or 'youtu.be' in text_decoded:
                m = RE_YT_URL.search(text_decoded)
                if m:
                    found_url = m.group(0).strip()

        if found_url:
            logger.log(f"[HeaderExtractor] Sukces! Wykryto link YT z nagłówka dla ID {item_id}: {found_url}")
            return found_url

    except Exception as e:
        logger.log(f"[HeaderExtractor] Błąd odczytu nagłówka dla ID {item_id}: {e}")

    return None

def check_and_cache_remote_header(api_client, song, video_download_manager=None) -> str | None:
    """
    Sprawdza, czy dla danego utworu można wyciągnąć link YT z nagłówka zdalnego pliku,
    i w przypadku powodzenia zapisuje go trwale do bazy nadpisań.
    """
    if not song or not api_client:
        return None

    item_id = getattr(song, 'item_id', None) or song.get('id') if isinstance(song, dict) else None
    if not item_id:
        return None

    existing = getattr(song, 'yt_link', None)
    if existing:
        return existing

    url = fetch_purl_from_remote_header(api_client, item_id)
    if url:
        _set_yt_link_override(item_id, url)
        if video_download_manager and hasattr(video_download_manager, 'save_yt_link_override'):
            try:
                title = getattr(song, 'title', '') or song.get('title', '') if isinstance(song, dict) else ''
                video_download_manager.save_yt_link_override(item_id, url, title)
            except Exception as e:
                logger.log(f"[HeaderExtractor] Zapis do bazy nie powiódł się: {e}")
        return url

    return None