# PROJECT_CONTEXT.md — ANDROMEDA MUSIC PLAYER (v14.19)

Dokument kontekstowy dla modeli AI. Zawiera architekturę, konwencje i kluczowe mechanizmy projektu.
Przed modyfikacją jakiegokolwiek pliku — przeczytaj tę dokumentację w całości.

---

## 1. Executive Summary

**Andromeda Music** to premium, open-source odtwarzacz muzyczny dla Linux (KDE/Wayland/X11), napisany w **Python 3 + PySide6 (Qt6)**. Łączy się z serwerami zgodnymi z protokołem **Navidrome/Subsonic** przez REST API. Kluczową funkcją jest synchronizacja audio z teledyskami z YouTube (`yt-dlp`) oraz system pobierania teledysków offline. Architektura to nowoczesne **MVC** powstałe z dekonstrukcji monolit → moduły.

---

## 2. Drzewo katalogów i odpowiedzialność plików

```
navidrome-player-v3/
├── main.py                      # Proxy wejściowy (wywołuje app.py)
├── app.py                       # Prawdziwy punkt wejścia: inicjalizuje QApplication, load_config, NavidromeClient, MainWindow
├── api_client.py                # Klient Navidrome REST API; zwraca obiekty MediaItem (NIE dict)
├── config.py                    # Globalny stan: APP_CONFIG (dict), THEME (dict), Pages (IntEnum), get_app_style()
├── utils.py                     # Wspólne narzędzia: Worker, AsyncImageLoader, NetworkMonitor, logger, telemetry_recorder
├── mpris_adapter.py             # Integracja MPRIS2 (Linux media keys, taskbar info)
│
├── core/
│   ├── enums.py                 # Enums: EngineState, MediaType, TelemetryEvent, VideoResolution
│   ├── media_item.py            # Klasa MediaItem — wrapper danych piosenki/albumu/artysty
│   └── telemetry_service.py    # Rejestracja parametrów wydajnościowych (18 param, CSV)
│
├── engine/
│   ├── player_engine.py         # CENTRALNY SILNIK: zarządzanie kolejką, QMediaPlayer (audio), synchronizacja wideo
│   ├── video_download_manager.py# Menedżer pobierania wideo offline (SQLite, yt-dlp worker thread)
│   ├── yt_resolver.py           # Asynchroniczny resolver URL YouTube przez yt-dlp
│   ├── arf_manager.py           # ARF 3.1: Auto-Resolution-Fallback — dynamiczne obniżanie jakości wideo
│   ├── cache_manager.py         # Cache audio (lokalne pliki, prefetch następnego utworu)
│   └── watchdog.py              # WatchdogService: guard UI/wideo, wykrywanie zawieszenia odtwarzania
│
├── ui/
│   ├── main_window.py           # MainWindow: QMainWindow, router nawigacji, dispatcher sygnałów, run_async()
│   ├── widgets/                 # Atomy UI (bez logiki biznesowej)
│   │   ├── buttons.py           # HoverIconButton — ikona z efektem hover
│   │   ├── images.py            # RoundedImage — zaokrąglone zdjęcie z animacją fade-in/zoom
│   │   ├── sliders.py           # PremiumSlider — niestandardowy QSlider
│   │   ├── labels.py            # ClickableLabel, MarqueeLabel (przewijający tekst)
│   │   ├── frames.py            # Thin wrappers QFrame
│   │   ├── drag_drop.py         # DragDropContainer — drag & drop w kolejce
│   │   ├── flow_layout.py       # FlowLayout — układa karty jak tekst (wrap)
│   │   └── smooth_scroll.py     # SmoothScrollArea — wygładzone przewijanie (QScroller)
│   └── components/              # Cząsteczki UI (logika domeny)
│       ├── song_item.py         # SongItem — wiersz piosenki (fav, download, playlist, drag)
│       ├── media_card.py        # MediaCard — kafelek albumu/artysty (PPM menu, download signal)
│       ├── headers.py           # MediaHeader, QueueHeader — nagłówki sekcji
│       └── hero_section.py      # HeroSection — duży hero banner na stronie głównej
│
└── views/                       # Pełne ekrany (strony aplikacji)
    ├── library_base.py          # LibraryScrollArea — bazowy scroll area dla widoków biblioteki
    ├── view_home.py             # HomeView — dashboard (ulubione, losowe albumy/artyści/utwory)
    ├── view_albums.py           # AlbumsView — lista wszystkich albumów
    ├── view_artists.py          # ArtistsView — lista wszystkich artystów
    ├── view_tracks.py           # TracksView — lista wszystkich utworów
    ├── view_favs.py             # FavsView — ulubione utwory
    ├── view_search.py           # SearchView — wyszukiwarka (piosenki, albumy, artyści)
    ├── view_details.py          # DetailsView — strona albumu/artysty/playlisty
    ├── view_now_playing.py      # NowPlayingWidget — imersyjny widok odtwarzacza + wideo
    ├── view_player_bar.py       # PlayerBarWidget — dolny pasek sterowania odtwarzaniem
    ├── view_sidebar.py          # SidebarWidget — boczny panel nawigacji + playlisty
    ├── view_settings.py         # SettingsView — ustawienia (serwer, wygląd, wideo, offline, dev)
    ├── view_downloads.py        # DownloadsView — menadżer pobierania teledysków offline
    └── view_dev.py              # DevModeView — narzędzia deweloperskie (telemetria, logi)
```

---

## 3. Strony aplikacji (Pages enum)

| ID | Nazwa enum | Widok |
|---|---|---|
| 0 | `Pages.HOME` | `HomeView` |
| 1 | `Pages.FAVS` | `FavsView` |
| 2 | `Pages.QUEUE` | kolejka (inline QScrollArea) |
| 3 | `Pages.ALBUMS` | `AlbumsView` |
| 4 | `Pages.DETAILS` | `DetailsView` |
| 5 | `Pages.TRACKS` | `TracksView` |
| 6 | `Pages.ARTISTS` | `ArtistsView` |
| 7 | `Pages.SETTINGS` | `SettingsView` |
| 8 | `Pages.NOW_PLAYING` | `NowPlayingWidget` |
| 9 | `Pages.DEV_MODE` | `DevModeView` |
| 10 | `Pages.SEARCH` | `SearchView` |
| 11 | `Pages.DOWNLOADS` | `DownloadsView` |

Pasek boczny (`view_sidebar.py`) wyświetla na dole (od dołu): Ustawienia → Pobrane → Dev mode (tylko gdy włączony).

---

## 4. Kluczowe klasy i ich role

### `MainWindow` (`ui/main_window.py`)
- Centralny hub, jedyna klasa z dostępem do wszystkiego.
- `self.client` → `NavidromeClient`
- `self.engine` → `PlayerEngine`
- `self.loader` → `AsyncImageLoader`
- `self.threadpool` → `QThreadPool` (dla workerów)
- `self.downloads_view` → `DownloadsView`
- **`run_async(task_func, callback_func, page_bound)`** — kluczowa metoda ochrony UI przed blokowaniem wątku głównego. Każde zapytanie do API MUSI przez nią przechodzić. `page_bound=True` anuluje callback gdy użytkownik zmienił stronę.
- **`_navigate(page_idx, data, type_str)`** — jedyna poprawna metoda nawigacji. Zawiera fade animację i ochronę `_is_fetching`.
- **`_handle_download_videos(data, type_str)`** — trigger pobierania masowego z MediaCard (Album/Artist PPM).
- **`start_bulk_download(bulk_type, ...)`** — pobieranie masowe async (Ulubione, All, Album, Artist).
- **`_handle_song_fav(song, new_state)`** — obsługuje gwiazdkę; jeśli `video_auto_dl_favs=True`, automatycznie dodaje do kolejki pobierania.

### `PlayerEngine` (`engine/player_engine.py`)
- Zarządza `QMediaPlayer` (audio) i `QMediaPlayer` (wideo, oddzielny) + `QAudioOutput`.
- `self.queue` — lista `MediaItem` (nie dict!).
- `self.idx` — indeks aktualnie odtwarzanego.
- `self.video_download_manager` → `VideoDownloadManager` (inicjalizowany wewnątrz).
- Sygnały: `track_changed(object)`, `state_changed(bool)`, `position_changed(int)`, `duration_changed(int)`, `queue_updated`, `queue_cleared`, `has_video_signal(bool)`, `video_ready_to_show()`.
- **`load_and_play_video(force_mid_track=False)`** — ładuje wideo (offline lub streaming YT). Sprawdza `video_download_manager.get_video_path()` jako priorytet.
- **`play_list(songs, start_idx)`** — ładuje nową kolejkę.

### `VideoDownloadManager` (`engine/video_download_manager.py`)
- Działa na własnym wątku `threading.Thread` (nie QThread).
- Baza SQLite: `~/.cache/navidrome-player-v3/offline_videos.db`
- Schemat tabeli `downloads`: `item_id, title, yt_link, file_path, status, quality, added_at, cover_id, resolution, file_size`
- Statusy: `QUEUED`, `DOWNLOADING`, `COMPLETED`, `ERROR`, `PAUSED`
- **`add_to_queue(item_id, yt_link, title, high_priority, cover_id)`** — główna metoda kolejkowania; idempotentna (nie duplikuje).
- **`get_video_path(item_id)`** — zwraca ścieżkę lokalną lub `None` jeśli brak/błąd.
- **`set_snooze(hours)`** — wstrzymuje pobieranie: `0`=wznów, `-1`=na stałe, `-2`=do restartu, `N`=na N godzin.
- Sygnały: `download_progress(str, float)`, `download_status_changed(str, str)`, `queue_updated`.

### `NavidromeClient` (`api_client.py`)
- Autentykacja Subsonic MD5+salt.
- Kluczowe metody zwracające `MediaItem`: `get_starred(limit)`, `get_random_albums(n)`, `get_random_songs(n)`, `get_album(id)`, `get_artists()`, `get_top_songs_for_artist(name, limit)`.
- `get_cover_art_url(cover_id, size=400)` — akceptuje zarówno `cover_id` jak i `item_id` (song_id) — Navidrome zwróci okładkę w obu przypadkach.
- `get_playlists()`, `update_playlist(pid, song_id_to_add)`, `create_playlist(name, song_ids)`.

### `AsyncImageLoader` (`utils.py`)
- Singleton-like (jeden per `MainWindow`).
- **`load(url, target)`** — ładuje obraz asynchronicznie; `target` musi mieć metodę `set_image(pixmap)`. Klasa `RoundedImage` tę metodę ma.
- Wbudowana deduplikacja in-flight (nie wysyła 2x tego samego URL).
- Dyskowy cache obrazów w `~/.cache/navidrome-player-images`.
- Wspiera customowe okładki: `~/.local/share/navidrome-player/custom_covers/` i `custom_artists/`.

### `MediaItem` (`core/media_item.py`)
- Wrapper dict dla danych API. Dostęp przez atrybuty: `song.item_id`, `song.title`, `song.artist`, `song.album`, `song.cover_id`, `song.is_starred`, `song.yt_link`.
- **KRYTYCZNE:** Sygnały przekazujące `MediaItem` MUSZĄ używać `Signal(object)`, nie `Signal(dict)`.

---

## 5. Konfiguracja (APP_CONFIG / config.ini)

| Klucz | Typ | Opis |
|---|---|---|
| `url` | str | URL serwera Navidrome |
| `username`, `password` | str | Dane logowania |
| `dark_mode` | bool | Motyw ciemny/jasny |
| `accent` | str | Kolor akcentu (hex) |
| `volume` | int | Głośność (0-100) |
| `video_resolution` | str | Preferowana jakość YT (1080p/720p/480p/240p) |
| `video_min_res` | str | Min. jakość ARF fallback |
| `video_auto_res` | bool | ARF 3.1 aktywny |
| `video_dynamic_opacity` | int | Przyciemnienie w trybie wideo z ruchem (0-100) |
| `video_dynamic_blur` | int | Rozmycie wideo z ruchem (0-100) |
| `video_static_opacity` | int | Przyciemnienie dla statycznej okładki |
| `video_static_blur` | int | Rozmycie dla statycznej okładki |
| `dev_mode` | bool | Tryb dewelopera (dodatkowa zakładka w sidebarze) |
| `video_offline_path` | str | Ścieżka zapisu teledysków offline |
| `video_offline_quality` | str | Jakość pobieranych offline (1080p/720p/480p) |
| `video_smart_auto_play` | bool | Automatyczne odtwarzanie wideo offline bez włączania trybu wideo |
| `video_auto_dl_favs` | bool | Auto-pobieranie teledysku przy dodaniu do ulubionych |
| `video_auto_dl_playlists` | bool | Auto-pobieranie przy dodaniu do playlisty |

---

## 6. Sygnały i przepływ danych

### Główne sygnały wychodzące z PlayerEngine:
```
track_changed(object)         → MainWindow._on_track_changed → aktualizacja PlayerBar + NowPlaying
state_changed(bool)           → MainWindow._on_state_changed → zmiana ikony play/pause
has_video_signal(bool)        → MainWindow._on_has_video → logika Smart Auto-play
video_ready_to_show()         → MainWindow._show_video_layer → przejście do widoku wideo
queue_updated / queue_cleared → MainWindow._on_queue_updated/_on_queue_cleared
```

### Broadcast stanu pobierania offline:
```
VideoDownloadManager.download_status_changed(item_id, status)
  → MainWindow.offline_status_changed(item_id, status)   [re-emitowany sygnał]
  → SongItem (każdy aktywny) → aktualizuje ikonę statusu pobierania
  → DownloadsView._on_status_changed → aktualizuje widget listy
```

### Logika Smart Auto-play teledysków:
```
Zmiana utworu → PlayerEngine emituje has_video_signal(bool)
  → MainWindow._on_has_video():
      if offline_path exists:
          if video_smart_auto_play=True  → engine.load_and_play_video()  (bez zmiany przycisku!)
          if video_smart_auto_play=False → tylko gdy btn_video_toggle.isChecked()
      else (streaming):
          if btn_video_toggle.isChecked() and has_video → streaming YT
```

### Pobieranie masowe:
```
MediaCard PPM → download_videos_clicked(data, type_str)
  → MainWindow._handle_download_videos()
  → MainWindow.start_bulk_download(bulk_type, ...)
  → run_async(fetch_songs) → QMessageBox z szacowanym rozmiarem
  → VideoDownloadManager.add_to_queue() × N
```

---

## 7. Krytyczne zasady kodowania (NIGDY nie łam)

1. **Qt API pinning:** `os.environ["QT_API"] = "pyside6"` MUSI być na samej górze pliku, tuż pod `import os`, przed jakimkolwiek importem Qt.
2. **Jedna instrukcja = jedna linia:** Zakaz średników (`;`).
3. **Signal(object) dla MediaItem:** Nigdy `Signal(dict)` ani `Signal(str)` dla obiektów domenowych — powoduje utratę atrybutów Python (C++ slicing).
4. **run_async() dla API:** Żadne zapytanie HTTP nie może blokować wątku głównego Qt. Zawsze przez `main_window.run_async()`.
6. **Dependency Injection:** Serwisy (`WatchdogService`, `TelemetryService`) inicjalizowane w `MainWindow.__init__`, nie jako globale.
7. **MediaItem, nie dict:** `api_client.py` zwraca obiekty `MediaItem`. Nie rzutuj ich na dict w warstwie widoku.

---

## 8. Wzorce implementacyjne (gotowe receptury)

### Dodawanie nowej strony (View):
1. Utwórz `views/view_xyz.py` z klasą `XyzView(LibraryScrollArea)` lub `XyzView(QWidget)`.
2. Dodaj `Pages.XYZ = N` do `config.py` (IntEnum).
3. Zainicjuj w `MainWindow._init_ui()` analogicznie do np. `DOWNLOADS`.
4. Podepnij nawigację w `view_sidebar.py`.
5. Dodaj `Pages.XYZ` do listy w `_navigate()` i `_refresh_current()`.

### Ładowanie obrazów asynchronicznie w widoku:
```python
# W metodzie load() widoku, po stworzeniu widgetu:
if item.cover_id:
    url = self.main_window.client.get_cover_art_url(item.cover_id)
    self.main_window.loader.load(url, widget_z_metoda_set_image)
```

### Wywołanie API bez blokowania UI:
```python
def some_action(self):
    def fetch():
        return self.main_window.client.get_album(album_id)
    def on_ready(result):
        if result:
            self._render(result)
    self.main_window.run_async(fetch, on_ready, page_bound=True)
```

### Dodawanie do kolejki pobierania offline:
```python
link = getattr(song, 'yt_link', None)
if link:
    self.engine.video_download_manager.add_to_queue(
        song.item_id, link, song.title,
        high_priority=False, cover_id=song.cover_id
    )
```

---

## 9. Dane persystentne

| Ścieżka | Format | Zawartość |
|---|---|---|
| `config.ini` | INI | Ustawienia aplikacji (CWD projektu) |
| `~/.cache/navidrome-player-v3/offline_videos.db` | SQLite | Kolejka i historia pobierań wideo |
| `~/.cache/navidrome-player-v3/video-offline/` | MP4/WEBM | Pobrane teledyski |
| `~/.cache/navidrome-player-images/` | HTTP cache | Cache miniatur (QNetworkDiskCache) |
| `~/.local/share/navidrome-player/custom_covers/` | JPG/PNG | Własne okładki albumów |
| `~/.local/share/navidrome-player/custom_artists/` | JPG/PNG | Własne zdjęcia artystów |
| `~/.local/share/navidrome-player/telemetry/` | CSV | Logi wydajnościowe |

---

## 10. Zależności zewnętrzne

```
PySide6          # Qt6 bindings (UI, multimedia, networking)
qtawesome        # Ikony FontAwesome w Qt
yt-dlp           # Pobieranie i rozwiązywanie URL YouTube (opcjonalne, wideo wyłączone bez niego)
requests         # HTTP dla API Navidrome i pobierania obrazów
```

Uruchomienie: `python3 main.py` (lub `python3 app.py`)

---

## 11. Aktualny stan projektu (v14.19)

### Funkcje działające:
- ✅ Odtwarzanie audio z serwera Navidrome (streaming + cache lokalny)
- ✅ Synchronizacja teledysków YouTube (ARF 3.1 — dynamiczna jakość)
- ✅ Pobieranie teledysków offline (kolejka, baza SQLite, wątek tła)
- ✅ Smart Auto-play offline (bez konieczności włączania trybu wideo)
- ✅ Auto-pobieranie przy polubieniu / dodaniu do playlisty (opcja w ustawieniach)
- ✅ Pobieranie masowe dla albumu, artysty, ulubionych (PPM + menu Akcje masowe)
- ✅ Menadżer pobrań z okładkami, rozdzielczością, rozmiarem pliku, wstrzymaniem
- ✅ Własne okładki albumów i zdjęcia artystów (lokalny override)
- ✅ MPRIS2 (sterowanie z klawiatury/taskbara Linux)
- ✅ Tryb Dev (telemetria, logi w czasie rzeczywistym)
- ✅ Motyw ciemny/jasny, własny kolor akcentu

### Znane ograniczenia:
- Pobieranie "Wybranych Playlist" w Akcjach masowych — stub (modal wyboru playlist do zaimplementowania).
- Stare wpisy w `offline_videos.db` mają `cover_id = NULL` — fallback na `item_id` rozwiązuje to dla okładek.

---

**END OF CONTEXT — v14.19**
