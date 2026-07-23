# PROJECT_CONTEXT.md — ANDROMEDA MUSIC PLAYER (v14.19+)

Dokument kontekstowy dla modeli AI. Zawiera architekturę, konwencje i kluczowe mechanizmy projektu.
Przed modyfikacją jakiegokolwiek pliku — przeczytaj tę dokumentację w całości.

---

## 1. Executive Summary

**Andromeda Music** to premium, open-source odtwarzacz muzyczny dla Linux (KDE/Wayland/X11), napisany w **Python 3 + PySide6 (Qt6)**. Łączy się z serwerami zgodnymi z protokołem **Navidrome/Subsonic** przez REST API. 

Kluczowe funkcje to:
- Synchronizacja audio z teledyskami z YouTube (`yt-dlp` / ARF 3.1).
- System pobierania offline zarówno **teledysków**, jak i **utworów audio** (lokalna baza SQLite).
- Klonowanie biblioteki (Offline-First) i cache'owanie zapytań API.
- Nowoczesna architektura **MVC** (Modularna) z wbudowanym systemem nawigacji (Router), wsparciem językowym (i18n) oraz własnymi motywami wizualnymi.

---

## 2. Drzewo katalogów i odpowiedzialność plików

```text
navidrome-player-v3/
├── AGENTS.md                    # Instrukcje systemowe dla agentów AI
├── api_client.py                # Klient Navidrome REST API (zwraca słowniki, które owijamy w MediaItem)
├── app.py                       # Punkt wejścia: inicjalizuje QApplication, NavidromeClient, MainWindow
├── audio_engine.py              # ZDEPRECIONOWANY (v14.6) -> kieruje do engine/player_engine.py
├── config.ini                   # Fizyczny plik przechowujący parametry ustawień aplikacji
├── config.py                    # Globalny stan: APP_CONFIG, konwersja THEME, enum Pages
├── main.py                      # Proxy wejściowy (wywołuje app.py)
├── mpris_adapter.py             # Integracja MPRIS2 (sterowanie z klawiatury/taskbara Linux)
├── requirements.txt             # Lista zależności Pythona (PySide6, yt-dlp, requests, itd.)
├── utils.py                     # Wspólne narzędzia: AsyncImageLoader, NetworkMonitor, telemetria, logi
│
├── core/
│   ├── backup_manager.py        # Tworzenie i przywracanie kopii zapasowych konfiguracji
│   ├── data_repository.py       # Repozytorium Danych: Cache w RAM i obsługa trybu offline (Offline Fallback)
│   ├── enums.py                 # Enums: EngineState, MediaType, TelemetryEvent, VideoResolution
│   ├── i18n.py                  # Translator i mechanizm wielojęzyczności (PL/EN)
│   ├── library_sync.py          # Synchronizacja bazy serwera do lokalnego SQLite (`library_cache.db`)
│   ├── models.py                # MediaItem, Song, Album, Artist — wrappery DTO dla danych z API
│   ├── paths.py                 # PathsManager: Standardy XDG dla konfiguracji, cache i danych aplikacji
│   └── telemetry_service.py     # Usługa zbierania logów wydajnościowych (18 parametrów)
│
├── engine/
│   ├── arf_manager.py           # ARF 3.1: Auto-Resolution-Fallback (redukcja jakości przy lagach)
│   ├── audio_controller.py      # Abstrakcja odtwarzania audio (QMediaPlayer + QAudioOutput)
│   ├── audio_download_manager.py# Pobieranie plików mp3 (offline_audio.db, worker thread)
│   ├── cache_manager.py         # Cache strumieniowania audio (prefetch .mp3)
│   ├── player_engine.py         # CENTRALNY SILNIK: kolejka, koordynacja A/V, Smart Sync
│   ├── video_controller_online.py# Abstrakcja odtwarzania wideo (QMediaPlayer + QAudioOutput wyciszone)
│   ├── video_download_manager.py# Pobieranie teledysków yt-dlp (offline_videos.db, worker thread)
│   ├── watchdog.py              # Monitor płynności (zakłada Maskę Ochronną przy buforowaniu)
│   └── yt_resolver.py           # Ekstrakcja URL YouTube przez yt-dlp
│
├── ui/
│   ├── main_window.py           # Hub głównego okna, dispatcher zdarzeń, run_async()
│   ├── router.py                # AppRouter: logika nawigacji, historia i animacje przejść
│   ├── theme_manager.py         # ThemeManager: zarządzanie paletą kolorów (tryby system/light/dark/custom)
│   ├── components/              # Cząsteczki UI (logika domeny)
│   │   ├── __init__.py
│   │   ├── headers.py           # MediaHeader, QueueHeader
│   │   ├── hero_section.py      # Wielki baner na stronie głównej
│   │   ├── media_card.py        # Kafelek dla artysty/albumu (z własnym menu PPM)
│   │   ├── sidebar_controller.py# Logika sterowania paskiem bocznym i rozwijaniem playlist
│   │   ├── song_context_menu.py # Menu pod PPM dla każdego wiersza utworu (SongItem)
│   │   └── song_item.py         # Wiersz utworu (SongItem)
│   └── widgets/                 # Atomy UI (uniwersalne, bez logiki biznesowej)
│       ├── __init__.py
│       ├── buttons.py           # HoverIconButton
│       ├── drag_drop.py         # DragDropContainer (Drag & Drop w liście odtwarzania)
│       ├── flow_layout.py       # Mechanizm elastycznej siatki kafelków
│       ├── frames.py            # ClickableFrame
│       ├── images.py            # RoundedImage
│       ├── labels.py            # ClickableLabel, ElidedLabel
│       ├── sliders.py           # PremiumSlider
│       └── smooth_scroll.py     # SmoothScrollArea
│
├── views/                       # Pełne ekrany (strony aplikacji)
│   ├── library_base.py          # Bazowa klasa z wbudowanym SmoothScrollArea i _clear()
│   ├── view_albums.py
│   ├── view_artists.py
│   ├── view_details.py
│   ├── view_dev.py
│   ├── view_downloads.py
│   ├── view_favs.py
│   ├── view_home.py
│   ├── view_now_playing.py
│   ├── view_player_bar.py
│   ├── view_search.py
│   ├── view_settings.py
│   ├── view_sidebar.py
│   ├── view_tracks.py
│   ├── dev/                     # Podstrony dla Trybu DevMode
│   │   ├── tab_logs.py
│   │   ├── tab_telemetry.py
│   │   └── telemetry_window.py
│   └── settings/                # Podstrony dla widoku Ustawień
│       ├── tab_dev.py
│       ├── tab_offline.py
│       ├── tab_server.py
│       ├── tab_theme.py
│       └── tab_video.py
│
├── assets/                      # Obrazki (np. logo.png)
└── lang/                        # Tłumaczenia JSON
    ├── en.json
    └── pl.json
```

---

## 3. Strony aplikacji (Pages enum)

| ID | Nazwa enum | Klasa Widoku |
|---|---|---|
| 0 | `Pages.HOME` | `HomeView` |
| 1 | `Pages.FAVS` | `FavsView` |
| 2 | `Pages.QUEUE` | Aktualnie renderowana wewnątrz `NowPlayingWidget` |
| 3 | `Pages.ALBUMS` | `AlbumsView` |
| 4 | `Pages.DETAILS` | `DetailsView` |
| 5 | `Pages.TRACKS` | `TracksView` |
| 6 | `Pages.ARTISTS` | `ArtistsView` |
| 7 | `Pages.SETTINGS` | `SettingsView` (ładuje taby z `views/settings/`) |
| 8 | `Pages.NOW_PLAYING` | `NowPlayingWidget` |
| 9 | `Pages.DEV_MODE` | `DevModeView` (ładuje taby z `views/dev/`) |
| 10 | `Pages.SEARCH` | `SearchView` |
| 11 | `Pages.DOWNLOADS` | `DownloadsView` |

---

## 4. Kluczowe mechanizmy i klasy

### `MainWindow` & `AppRouter` (`ui/main_window.py`, `ui/router.py`)
- `MainWindow` jest centralnym hubem. Zawiera instancje `DataRepository`, `AsyncImageLoader`, `NetworkMonitor`, `PlayerEngine`.
- **`run_async(task_func, callback_func, page_bound)`** — jedyny dozwolony sposób na wykonywanie blokujących operacji. Żadne wywołanie API lub SQLite nie może zatrzymać głównego wątku. Zabezpieczone przez QThreadPool.
- `AppRouter` izoluje logikę nawigacji (`_navigate`, `go_back`, `show_details`). Wykonuje asynchroniczne, krzyżowe animacje przenikania ekranów (`fade_anim` + `pos_anim`).

### `DataRepository` (`core/data_repository.py`)
- Warstwa pośrednia między aplikacją a API (`NavidromeClient`).
- **Cache in-RAM**: Zapamiętuje odpowiedzi przez 5 minut, co drastycznie obniża czas ładowania widoków.
- **Offline Fallback**: Jeśli `NetworkMonitor` zgłosi brak połączenia, repozytorium automatycznie pobiera dane z lokalnego `LibrarySyncManager` (SQLite).

### Pobieranie Offline (`AudioDownloadManager` & `VideoDownloadManager`)
- Oba działają w architekturze kolejkowej (`PriorityQueue` + dedykowany wątek roboczy `threading.Thread`).
- Bazy danych zarządzają stanem pobrań (QUEUED, DOWNLOADING, COMPLETED, ERROR).
- Emisja sygnału o postępie z wbudowaną "przepustnicą" czasu (throttle), zapobiegająca przeciążeniom zdarzeń Qt.

### `SongContextMenu` (`ui/components/song_context_menu.py`)
- Dynamiczne menu pod PPM dla obiektów `SongItem`. Dekapsuluje gigantyczną ilość zdarzeń z widoku wiersza piosenki. Zawiera system nadpisywania linków YT dla poszczególnych piosenek.

### Zarządzanie ścieżkami (`PathsManager` w `core/paths.py`)
- Klasa dostosowująca aplikację do standardów **XDG Base Directory**. Gwarantuje poprawny podział na konfigurację (`~/.config/`), dane (`~/.local/share/`) i cache (`~/.cache/`).

---

## 5. Konfiguracja (APP_CONFIG / config.ini)

| Grupa ustawień | Klucz | Opis |
|---|---|---|
| **Theme** | `theme_mode`, `language`, `accent` | Tryb (system/dark/light/custom), Język (pl/en), Główny kolor |
| **Video** | `video_resolution`, `video_min_res` | Docelowa i minimalna jakość YT (do działania ARF 3.1) |
| **Video** | `video_auto_res` | Włączenie funkcji ARF (dynamiczny spadek jakości przy słabej sieci) |
| **Video** | `video_dynamic_*`, `video_static_*`| Parametry przezroczystości i rozmycia dla tła w `NowPlaying` |
| **VideoOffline** | `video_smart_auto_play` | Zezwól na automatyczny tryb wideo, jeśli plik istnieje offline |
| **VideoOffline** | `video_auto_dl_favs`, `*_playlists`| Zezwól na natychmiastowe wrzucanie do kolejki przy gwiazdkowaniu/dodaniu do wybranych playlist |
| **AudioOffline** | `audio_auto_dl_favs`, `*_playlists`| To samo co wyżej, ale dla plików MP3. |
| **AudioOffline** | `hide_undownloaded_offline` | Czy w trybie offline ukrywać niedostępne piosenki, czy je wyszarzać. |

---

## 6. Sygnały i przepływ danych (Krytyczne konwencje)

### Cykl życia widoków
- Użytkownik klika kartę -> `AppRouter.navigate()` -> `AppRouter` ustawia nowy widok, nakłada efekt przezroczystości -> Uruchamia `run_async()` pobierające dane (`repo`) -> Gdy dane wrócą, uruchamia `target_widget.load()`.
- W klasach dziedziczących po `LibraryScrollArea` (`views/library_base.py`) funkcja `_clear()` niszczy wszystkie kontrolki w layoutach podczas odświeżania.

### Synchronizacja UI dla Ulubionych (Gwiazdka)
- Wciśnięcie serduszka -> Emisja `fav_clicked` z `SongItem` -> `MainWindow._handle_song_fav` -> Odpytanie API (asynchronicznie) i aktualizacja bazy -> Emisja powrotna `MainWindow.fav_updated`.
- Główna pętla UI przegląda wszystkie renderowane wiersze i aktualizuje wygląd ikon.

### Integracja MPRIS (`mpris_adapter.py`)
- Oparta na `pydbus`. Komunikuje system Linux o tytule, artyście, długości i statusie play/pause. Nasłuchuje na klawisze multimedialne. Operacje wykonywane asynchronicznie przez GLib i emitowane do `PlayerEngine` przez natywne sygnały PySide.

---

## 7. KRYTYCZNE ZASADY KODOWANIA (NIGDY NIE ŁAM)

1. **Qt API pinning:** Środowisko `os.environ["QT_API"] = "pyside6"` **MUSI** znajdować się na samej górze we WSZYSTKICH modyfikowanych lub tworzonych plikach w tym projekcie, tuż po `import os`.
2. **Jedna instrukcja = jedna linia:** Bezwzględny zakaz używania średników (`;`).
3. **Signal(object) dla MediaItem:** Nigdy `Signal(dict)` ani `Signal(str)` dla obiektów domenowych. Naruszenie tego niszczy tzw. properties (Właściwości z modułu `models.py`) na poziomie C++.
4. **Operacje I/O w UI to Zbrodnia:** Nigdy nie otwieraj `open()`, ani `sqlite3.connect()` bezpośrednio w funkcjach przycisków lub ładowania widoków na wątku GUI.
5. **Pathing przez PathsManager:** Nigdy nie koduj na sztywno `~/.cache` w nowych modułach. Zawsze importuj i korzystaj z `PathsManager.get_cache_dir()` (lub analogicznych).
6. **Brak tworzenia słowników ad-hoc z API:** Klient zwraca `dict`, ale Repozytorium lub logika pośrednia pakuje go natychmiastowo w `Song`, `Album`, `Artist` dziedziczące po `MediaItem`.

---

## 8. Persystencja Danych (Gdzie co leży - XDG Standard)

| Kategoria | Ścieżka (domyślna) | Zawartość |
|---|---|---|
| **Config** | `~/.config/andromeda-music/config.ini` | Główne ustawienia aplikacji |
| **Cache API** | `~/.cache/andromeda-music/library_cache.db` | SQLite: Pełna kopia bazy danych serwera (Artists, Albums, Songs) |
| **Cache Obrazów**| `~/.cache/andromeda-music/images/` | Qt Network Disk Cache na okładki HTTP |
| **Zapisane Wideo**| `~/.local/share/andromeda-music/video-offline/` | Pliki teledysków MP4/WEBM |
| **Baza Wideo** | `~/.cache/andromeda-music/offline_videos.db` | Kolejka i historia pobierań yt-dlp + ręczne linki |
| **Zapisane Audio**| `~/.cache/andromeda-music/offline_music/` | Trwale pobrane utwory MP3 offline |
| **Baza Audio** | `~/.cache/andromeda-music/offline_audio.db` | Kolejka i historia pobierań utworów |
| **Custom Wideo** | `~/.local/share/andromeda-music/custom_covers/` | Nadpisane, lokalne zdjęcia dla albumów |
| **Logi & Telemetria**| `~/.local/share/andromeda-music/logs/` | CSV z telemetrią wydajnościową oraz log błędów z `AppLogger` |

Uruchomienie: `python3 main.py` (lub `python3 app.py`)

---

**END OF CONTEXT**
