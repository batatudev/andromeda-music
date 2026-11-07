import os
os.environ["QT_API"] = "pyside6"

import re
import json
from pathlib import Path

RE_YT_URL = re.compile(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s",&]+)')

_DEMO_LINKS_CACHE = None
_DEMO_LINKS_MTIME = 0

def _normalize_str(text: str) -> str:
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r'[\(\[\{].*?[\)\]\}]', '', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned

def _load_demo_links():
    global _DEMO_LINKS_CACHE, _DEMO_LINKS_MTIME

    root_dir = Path(__file__).resolve().parent.parent
    candidate_paths = [
        root_dir / "demo_links.json",
        Path.home() / ".config" / "andromeda-music" / "demo_links.json",
        Path.home() / ".config" / "andromeda-test" / "demo_links.json"
    ]

    target_file = None
    for p in candidate_paths:
        if p.exists():
            target_file = p
            break

    if not target_file:
        _DEMO_LINKS_CACHE = {}
        return _DEMO_LINKS_CACHE

    try:
        mtime = target_file.stat().st_mtime
        if _DEMO_LINKS_CACHE is not None and mtime == _DEMO_LINKS_MTIME:
            return _DEMO_LINKS_CACHE

        _DEMO_LINKS_MTIME = mtime
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        parsed_links = {}

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    t = _normalize_str(item.get("title", ""))
                    a = _normalize_str(item.get("artist", ""))
                    u = str(item.get("url", "")).strip()
                    if t and u and ("youtube.com" in u or "youtu.be" in u):
                        parsed_links[(t, a)] = u
        elif isinstance(data, dict):
            for key, val in data.items():
                u = str(val).strip()
                if "youtube.com" in u or "youtu.be" in u:
                    if " - " in key:
                        parts = key.split(" - ", 1)
                        a = _normalize_str(parts[0])
                        t = _normalize_str(parts[1])
                        parsed_links[(t, a)] = u
                    else:
                        t = _normalize_str(key)
                        parsed_links[(t, "")] = u

        _DEMO_LINKS_CACHE = parsed_links
        return _DEMO_LINKS_CACHE
    except Exception:
        _DEMO_LINKS_CACHE = {}
        return _DEMO_LINKS_CACHE

def get_demo_catalog_link(title: str, artist: str) -> str | None:
    links = _load_demo_links()
    if not links:
        return None

    norm_title = _normalize_str(title)
    norm_artist = _normalize_str(artist)

    match = links.get((norm_title, norm_artist))
    if match:
        return match

    for (t, a), url in links.items():
        if t == norm_title and (not a or a in norm_artist or norm_artist in a):
            return url

    return None

class MediaItem(dict):
    """
    Inteligentny adapter (Wrapper) danych z Navidrome API.
    Zachowuje się jak zwykły słownik (kompatybilność wsteczna i sygnały Qt),
    ale udostępnia bezpieczne, ujednolicone właściwości (Properties).
    """
    @property
    def item_id(self):
        return self.get('id', '')

    @property
    def title(self):
        return self.get('title') or self.get('name') or 'Unknown'

    @property
    def artist(self):
        return self.get('artist', 'Unknown')

    @property
    def album(self):
        return self.get('album', 'Unknown')

    @property
    def cover_id(self):
        return self.get('coverArt') or self.get('albumId') or self.get('id', '')

    @property
    def suffix(self):
        return self.get('suffix', '').lower().strip()

    @property
    def is_starred(self):
        return self.get('starred') is not None

    def set_starred(self, state: bool):
        if state:
            self['starred'] = "True"
        else:
            self.pop('starred', None)

    @property
    def duration_sec(self):
        return int(self.get('duration', 0))

    @property
    def yt_link(self):
        import utils
        override = utils._YT_LINK_OVERRIDES.get(self.item_id)
        if override:
            return override
        for field in ('purl', 'PURL', 'comment'):
            text = self.get(field, '')
            if not text:
                continue
            if 'youtube.com' in text or 'youtu.be' in text:
                m = RE_YT_URL.search(text)
                if m:
                    return m.group(0)
            elif field in ('purl', 'PURL') and (text.startswith('http://') or text.startswith('https://')):
                return text.strip()

        return get_demo_catalog_link(self.title, self.artist)

class Song(MediaItem):
    """ DTO reprezentujące pojedynczy utwór (Track). """
    pass

class Album(MediaItem):
    """ DTO reprezentujące album. Zawiera listę utworów (Song). """
    @property
    def songs(self):
        return self.get('song', [])

class Artist(MediaItem):
    """ DTO reprezentujące artystę. Zawiera listę albumów (Album). """
    @property
    def albums(self):
        return self.get('album', [])

    @property
    def cover_id(self):
        from core.paths import PathsManager
        target_dir = PathsManager.get_custom_artists_dir()
        art_id = self.item_id
        if art_id:
            for ext in ['.jpg', '.jpeg', '.png']:
                if (target_dir / f"{art_id}{ext}").exists():
                    return art_id

        cover_art = self.get('coverArt', '')
        has_real_image = bool(
            self.get('artistImageUrl') or
            self.get('largeImageUrl') or
            self.get('mediumImageUrl') or
            self.get('smallImageUrl')
        )

        if str(cover_art).startswith('ar-') and not has_real_image:
            return ""

        return cover_art or self.get('id', '')