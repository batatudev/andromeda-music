import re

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
        # 1. Najpierw sprawdz reczny override uzytkownika
        override = utils._YT_LINK_OVERRIDES.get(self.item_id)
        if override:
            return override
        # 2. Fallback: parsuj link YT z pola 'comment'
        text = self.get('comment', '')
        if not text:
            return None
        if 'youtube.com' in text or 'youtu.be' in text:
            urls = re.findall(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s",&]+)', text)
            if urls:
                return urls[0]
        return None

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
