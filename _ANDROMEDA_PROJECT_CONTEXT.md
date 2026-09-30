# PROJECT_CONTEXT.md — ANDROMEDA MUSIC PLAYER (v14.20+)

Dokument kontekstowy dla modeli AI. Zawiera architekturę, konwencje i kluczowe mechanizmy projektu.
Przed modyfikacją jakiegokolwiek pliku — przeczytaj tę dokumentację w całości.

---

## 1. Executive Summary

**Andromeda Music** to premium, open-source odtwarzacz muzyczny dla Linux (KDE/Wayland/Hyprland/X11), napisany w **Python 3 + PySide6 (Qt6)**. Łączy się z serwerami zgodnymi z protokołem **Navidrome/Subsonic** przez REST API. 

Kluczowe funkcje to:
- Synchronizacja audio z teledyskami z YouTube (`yt-dlp` / ARF 3.1).
- System pobierania offline zarówno **teledysków**, jak i **utworów audio** (lokalne bazy SQLite w trybie WAL).
- Klonowanie biblioteki (Offline-First) i cache'owanie zapytań API.
- Nowoczesna, wysoce modularna architektura **MVC** z wbudowanym routerem nawigacji, wsparciem językowym (i18n), zoptymalizowanym systemem motywów oraz natywną integracją ze standardami Linuksa (XDG, MPRIS2, PipeWire).

---

## 2. Drzewo katalogów i odpowiedzialność plików

```text
andromeda-music/
├── AGENTS.md                    # Instrukcje systemowe dla agentów AI
├── ai_bundler.py                # Narzędzie analityczno-pakujące kod dla modeli AI (z licznikiem LOC)
├── api_client.py                # Klient Navidrome REST API (zwraca słowniki opakowywane w MediaItem)
├── app.py                       # Punkt wejścia: inicjalizuje QApplication, NavidromeClient, MainWindow
├── config.ini                   # Fizyczny plik przechowujący parametry ustawień aplikacji
├── config.py                    # Globalny stan: APP_CONFIG, konwersja THEME, enum Pages, get_app_style()
├── main.py                      # Proxy wejściowy (wywołuje app.py)
├── mpris_adapter.py             # Integracja MPRIS2 (sterowanie z klawiatury/taskbara Linux, DesktopEntry: andromeda-music)
├── requirements.txt             # Lista zależności Pythona (PySide6, yt-dlp, requests, itd.)
├── utils.py                     # Lekkie narzędzia pomocnicze (Worker, get_blurred_pixmap, link overrides)
│
├── core/
│   ├── backup_manager.py        # Tworzenie i przywracanie kopii zapasowych konfiguracji
│   ├── data_repository.py       # Repozytorium Danych: Cache w RAM i obsługa trybu offline (Offline Fallback)
│   ├── enums.py                 # Enums: EngineState, MediaType, TelemetryEvent, VideoResolution
│   ├── i18n.py                  # Translator i mechanizm wielojęzyczności (PL/EN)
│   ├── library_sync.py          # Synchronizacja bazy serwera do lokalnego SQLite (`library_cache.db`)
│   ├── logger.py                # Rejestratory: AppLogger (błędy aplikacji) oraz TelemetryRecorder (CSV)
│   ├── models.py                # MediaItem, Song, Album, Artist — wrappery DTO dla danych z API
│   ├── network_monitor.py       # Wątek monitorujący stan łącza internetowego (1.1.1.1) i ping serwera
│   ├── paths.py                 # PathsManager: Standardy XDG, auto-migracja, połączenia SQLite WAL
│   └── telemetry_service.py     # Usługa zbierania logów wydajnościowych (18 parametrów)
│
├── engine/
│   ├── arf_manager.py           # ARF 3.1: Auto-Resolution-Fallback i dobór rozdzielczości wideo
│   ├── audio_controller.py      # Kontroler audio (QMediaPlayer + dynamiczne przełączanie urządzeń audio)
│   ├── audio_download_manager.py# Pobieranie plików mp3 (dziedziczy po BaseDownloadManager)
│   ├── base_download_manager.py # Abstrakcyjna baza menedżera pobierania (kolejka wątkowa, uśpienie, stan SQLite)
│   ├── cache_manager.py         # Cache strumieniowania audio (prefetch .mp3)
│   ├── header_tag_extractor.py  # Ekstrakcja linków YT z nagłówków plików zdalnych (Range Requests)
│   ├── player_engine.py         # CENTRALNY SILNIK: koordynacja A/V, Smart Sync, fasada odtwarzacza
│   ├── queue_manager.py         # Dedykowany menedżer kolejki utworów (indeksy, shuffle, loop, Drag & Drop)
│   ├── video_controller_online.py# Kontroler wideo online (wyciszone wyjście audio)
│   ├── video_download_manager.py# Pobieranie teledysków yt-dlp (dziedziczy po BaseDownloadManager)
│   ├── watchdog.py              # Monitor płynności (zakłada Maskę Ochronną przy buforowaniu wideo)
│   └── yt_resolver.py           # Ekstrakcja URL YouTube przez yt-dlp
│
├── ui/
│   ├── main_window.py           # Centralny hub okna, dispatcher zdarzeń, run_async()
│   ├── router.py                # AppRouter: logika nawigacji, historia i animacje przejść (Cross-Fade)
│   ├── theme_manager.py         # ThemeManager: zarządzanie motywami wizualnymi (system/dark/light/custom)
│   ├── image_loader.py          # AsyncImageLoader: 3-poziomowy silnik pobierania i buforowania okładek
│   ├── components/              # Cząsteczki UI (logika domeny)
│   │   ├── __init__.py
│   │   ├── bulk_download_handler.py # Obsługa masowych pobrań i auto-syncu ulubionych
│   │   ├── custom_media_manager.py  # Obsługa własnych okładek i grafik wykonawców
│   │   ├── download_item.py     # Wiersz zadania pobierania (DownloadItemWidget)
│   │   ├── headers.py           # MediaHeader, QueueHeader
│   │   ├── hero_section.py      # Wielki baner na stronie głównej
│   │   ├── media_card.py        # Kafelek dla artysty/albumu (z własnym menu PPM)
│   │   ├── sidebar_controller.py# Logika sterowania paskiem bocznym i playlistami
│   │   ├── song_context_menu.py # Menu pod PPM dla wiersza utworu (SongItem)
│   │   └── song_item.py         # Wiersz utworu (SongItem ze sprawdzaniem statusu w RAM O(1))
│   ├── dialogs/                 # Dedykowane okna dialogowe
│   │   ├── __init__.py
│   │   └── playlist_dialog.py   # Okno tworzenia i dodawania utworu do playlisty
│   └── widgets/                 # Atomy UI (uniwersalne kontrolki)
│       ├── __init__.py
│       ├── buttons.py           # HoverIconButton z leniwą inicjalizacją animacji
│       ├── collapsible.py       # CollapsibleSection (uniwersalna sekcja zwijana)
│       ├── drag_drop.py         # DragDropContainer (Drag & Drop w liście odtwarzania)
│       ├── flow_layout.py       # Mechanizm elastycznej siatki kafelków
│       ├── frames.py            # ClickableFrame
│       ├── images.py            # RoundedImage
│       ├── labels.py            # ClickableLabel, ElidedLabel, ClickableElidedLabel
│       ├── sliders.py           # PremiumSlider
│       ├── smooth_scroll.py     # SmoothScrollArea
│       └── toast.py             # ToastNotification (nakładkowe powiadomienia)
│
├── views/                       # Pełne ekrany (strony aplikacji)
│   ├── library_base.py          # Bazowa klasa z wbudowanym SmoothScrollArea i _clear()
│   ├── view_albums.py
│   ├── view_artists.py
│   ├── view_details.py
│   ├── view_dev.py
│   ├── view_downloads.py        # Czysty widok menedżera pobrań
│   ├── view_favs.py
│   ├── view_home.py
│   ├── view_now_playing.py      # NowPlayingWidget (własne zarządzanie kolejką, wideo i tłem)
│   ├── view_player_bar.py
│   ├── view_search.py
│   ├── view_settings.py         # SettingsView (jednorazowa budowa UI + metoda sync_values)
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
├── tests/                       # Skrypty testowe i weryfikacyjne
├── assets/                      # Obrazki statyczne (np. logo.png)
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
| 2 | `Pages.QUEUE` | Renderowana wewnątrz `NowPlayingWidget` |
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

## 4. Kluczowe mechanizmy i architektura

### `MainWindow` & `AppRouter` (`ui/main_window.py`, `ui/router.py`)
- `MainWindow` jest centralnym hubem zdarzeń. Zawiera instancje `DataRepository`, `AsyncImageLoader`, `NetworkMonitor`, `PlayerEngine`.
- **`run_async(task_func, callback_func, page_bound)`** — jedyny dozwolony sposób na wykonywanie blokujących operacji I/O. Zabezpieczone przez `QThreadPool`.
- `AppRouter` izoluje nawigację (`navigate`, `go_back`, `show_details`) i wykonuje płynne animacje przenikania (Cross-Fade 60 FPS).
- Okna dialogowe i operacje na plikach są wydelegowane do dedykowanych komponentów (`PlaylistDialog`, `CustomMediaManager`, `BulkDownloadHandler`).

### `QueueManager` & `PlayerEngine` (`engine/queue_manager.py`, `engine/player_engine.py`)
- Logika zarządzania kolejką utworów (indeksy, losowanie, pętla, rearanżacja Drag & Drop) jest w pełni wyizolowana w `QueueManager`.
- `PlayerEngine` skupia się wyłącznie na koordynacji potoków audio/wideo, synchronizacji czasu A/V oraz obsłudze algorytmu ARF.

### Baza danych i Pobieranie Offline (`BaseDownloadManager`)
- `AudioDownloadManager` oraz `VideoDownloadManager` dziedziczą po wspólnej klasie bazowej `BaseDownloadManager`.
- Wszystkie operacje SQLite korzystają z `PathsManager.get_db_connection()`, który wymusza pragmy `busy_timeout=5000` i `synchronous=NORMAL`, a inicjalizacja tabel włącza trwały tryb `WAL` (`journal_mode=WAL`).
- Czytelnicy z wątku GUI nigdy nie są blokowani przez wątki pobierania w tle.

### Wydajność wierszy `SongItem` (`ui/components/song_item.py`)
- Sprawdzanie dostępności offline odbywa się w pamięci RAM poprzez odpytanie `_path_cache` w managerach pobierania ze złożonością **O(1)** (zero zapytań `os.path.exists()` na wątku GUI).
- Podświetlanie aktywnego utworu opiera się na właściwości dynamicznej `setProperty("active", "true")` powiązanej z regułą CSS `#SongItem[active="true"]` zamiast kosztownego parsowania łańcuchów stylów w locie.

---

## 5. Konfiguracja (APP_CONFIG / config.ini)

| Grupa ustawień | Klucz | Opis |
|---|---|---|
| **Theme** | `theme_mode`, `language`, `accent` | Tryb (system/dark/light/custom), Język (pl/en), Główny kolor akcentu |
| **Video** | `video_resolution`, `video_min_res` | Docelowa i minimalna jakość YT (dla ARF 3.1) |
| **Video** | `video_auto_res` | Włączenie funkcji ARF (dynamiczny spadek jakości przy słabej sieci) |
| **Video** | `video_dynamic_*`, `video_static_*`| Parametry przezroczystości i rozmycia dla tła w `NowPlaying` |
| **VideoOffline** | `video_smart_auto_play` | Zezwól na automatyczny tryb wideo, jeśli plik istnieje offline |
| **VideoOffline** | `video_auto_dl_favs`, `*_playlists`| Automatyczne pobieranie teledysków przy gwiazdkowaniu/dodaniu do playlist |
| **AudioOffline** | `audio_auto_dl_favs`, `*_playlists`| Automatyczne pobieranie plików MP3 przy gwiazdkowaniu/dodaniu do playlist |
| **AudioOffline** | `hide_undownloaded_offline` | Czy w trybie offline ukrywać niedostępne piosenki, czy je wyszarzać |

---

## 6. KRYTYCZNE ZASADY KODOWANIA (NIGDY NIE ŁAM)

1. **Qt API pinning:** Środowisko `os.environ["QT_API"] = "pyside6"` **MUSI** znajdować się na samej górze we WSZYSTKICH modyfikowanych lub tworzonych plikach w tym projekcie, tuż po `import os`.
2. **Jedna instrukcja = jedna linia:** Bezwzględny zakaz używania średników (`;`) oraz jednolinijkowych instrukcji złożonych (`if x: return y`).
3. **Signal(object) dla MediaItem:** Nigdy `Signal(dict)` ani `Signal(str)` dla obiektów domenowych. Naruszenie tego powoduje utratę właściwości w C++.
4. **Operacje I/O w UI to Zbrodnia:** Nigdy nie otwieraj `open()`, ani `sqlite3.connect()` bezpośrednio w funkcjach przycisków lub ładowania widoków na wątku GUI.
5. **Pathing przez PathsManager:** Nigdy nie koduj na sztywno `~/.cache` w modułach. Zawsze importuj i korzystaj z `PathsManager`.
6. **Brak tworzenia słowników ad-hoc z API:** Klient zwraca `dict`, ale Repozytorium lub logika pośrednia pakuje go natychmiastowo w `Song`, `Album`, `Artist` dziedziczące po `MediaItem`.
7. **Kompletność kodu:** Zawsze zwracaj pełny, gotowy do skopiowania kod modyfikowanego pliku, bez skrótów typu `# ... rest of code ...`.

---

## 7. Persystencja Danych (Gdzie co leży - XDG Standard)

| Kategoria | Ścieżka (domyślna) | Zawartość |
|---|---|---|
| **Config** | `~/.config/andromeda-music/config.ini` | Główne ustawienia aplikacji |
| **Cache API** | `~/.cache/andromeda-music/library_cache.db` | SQLite (WAL): Kopia bazy danych serwera (Artists, Albums, Songs) |
| **Cache Obrazów**| `~/.cache/andromeda-music/images/` | QNetworkDiskCache na pobrane okładki HTTP |
| **Zapisane Wideo**| `~/.local/share/andromeda-music/video-offline/` | Trwałe pliki teledysków MP4/WEBM |
| **Baza Wideo** | `~/.cache/andromeda-music/offline_videos.db` | SQLite (WAL): Kolejka i historia pobierań yt-dlp + linki |
| **Zapisane Audio**| `~/.local/share/andromeda-music/audio-offline/` | Trwałe pobrane utwory MP3 offline |
| **Baza Audio** | `~/.cache/andromeda-music/offline_audio.db` | SQLite (WAL): Kolejka i historia pobierań utworów MP3 |
| **Custom Grafiki**| `~/.local/share/andromeda-music/custom_covers/` oraz `custom_artists/` | Nadpisane, lokalne zdjęcia dla albumów i artystów |
| **Logi & Telemetria**| `~/.local/share/andromeda-music/logs/` | CSV z telemetrią wydajnościową oraz log błędów z `AppLogger` |

Uruchomienie: `python3 main.py` (lub `python3 app.py`)

---
