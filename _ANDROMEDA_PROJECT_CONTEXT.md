# PROJECT_CONTEXT.md — ANDROMEDA MUSIC PLAYER (v14.20+)

Dokument kontekstowy dla modeli AI. Zawiera architekturę, konwencje, mechanizmy wydajnościowe i kluczowe moduły projektu.
Przed modyfikacją jakiegokolwiek pliku — przeczytaj tę dokumentację w całości.

---

## 1. Executive Summary

**Andromeda Music** to nowoczesny, wysoce zoptymalizowany, open-source odtwarzacz muzyczny dla Linux (KDE/Wayland/Hyprland/X11), napisany w **Python 3 + PySide6 (Qt6)**. Łączy się z serwerami zgodnymi z protokołem **Navidrome/Subsonic** przez REST API.

Kluczowe funkcje to:
- Synchronizacja audio z teledyskami z YouTube (`yt-dlp` / ARF 3.1).
- Zoptymalizowany system pobierania offline teledysków oraz utworów audio (lokalne bazy SQLite w trybie WAL z `temp_store=MEMORY` i `busy_timeout=5000`).
- Klonowanie biblioteki (Offline-First) i zaawansowany wielopoziomowy cache zapytań API.
- Nowoczesna architektura **MVC** z routerem nawigacji, wielojęzycznością (i18n PL/EN), systemem motywów oraz natywną integracją z Linuksem (XDG, MPRIS2, PipeWire).
- **Wydajność klasy produkcyjnej:** Błyskawiczny start okna (~1.2 s), eliminacja wycieków pamięci (Retained RAM < 50 KB), progresywne renderowanie kawałkowe (Chunked Rendering ~44 ms), brak zamrażania wątku GUI przez inline CSS oraz asynchroniczny potok grafiki w tle.

---

## 2. Drzewo katalogów i odpowiedzialność plików

```text
andromeda-music/
├── AGENTS.md                    # Instrukcje systemowe dla agentów AI
├── ai_bundler.py                # Narzędzie analityczno-pakujące kod dla modeli AI
├── api_client.py                # Klient Navidrome REST API (z pulą HTTPAdapter 30 conn)
├── app.py                       # Punkt wejścia: inicjalizacja QApplication, pre-warming fontów, MainWindow
├── config.example.ini           # Przykładowy, bezpieczny szablon konfiguracji
├── config.ini                   # Prywatny plik ustawień użytkownika (wykluczony z gita)
├── config.py                    # Globalny stan: APP_CONFIG, słownik THEME, Pages enum, skompilowany get_app_style()
├── main.py                      # Proxy wejściowy (konfiguracja PulseAudio/PipeWire i start app.py)
├── mpris_adapter.py             # Integracja MPRIS2 (D-Bus SessionBus, DesktopEntry: andromeda-music)
├── requirements.txt             # Zależności Pythona (PySide6, yt-dlp, requests, mutagen, darkdetect)
├── utils.py                     # Narzędzia pomocnicze (Worker, get_blurred_pixmap, link overrides)
│
├── core/
│   ├── backup_manager.py        # Tworzenie i przywracanie kopii zapasowych konfiguracji
│   ├── data_repository.py       # Repozytorium Danych: Cache w RAM (TTL) i obsługa trybu offline (Offline Fallback)
│   ├── enums.py                 # Enums: EngineState, MediaType, TelemetryEvent, VideoResolution
│   ├── i18n.py                  # Translator i mechanizm wielojęzyczności (PL/EN) z funkcją tr()
│   ├── library_sync.py          # Synchronizacja bazy serwera do SQLite (`library_cache.db`) z executemany()
│   ├── logger.py                # Rejestratory: AppLogger (błędy) oraz TelemetryRecorder (CSV)
│   ├── models.py                # MediaItem, Song, Album, Artist — wrappery DTO dla danych z API
│   ├── network_monitor.py       # Wątek monitorujący stan łącza (1.1.1.1) i ping serwera
│   ├── paths.py                 # PathsManager: Standardy XDG, migracja, połączenia SQLite WAL + MEMORY
│   └── telemetry_service.py     # Usługa zbierania telemetrii wydajnościowej
│
├── engine/
│   ├── arf_manager.py           # ARF 3.1: Auto-Resolution-Fallback i dobór rozdzielczości wideo
│   ├── audio_controller.py      # Kontroler audio (QMediaPlayer + dynamiczne przełączanie urządzeń)
│   ├── audio_download_manager.py# Pobieranie plików mp3 (dziedziczy po BaseDownloadManager)
│   ├── base_download_manager.py # Baza menedżera pobierania (kolejka wątkowa, uśpienie, stan SQLite)
│   ├── cache_manager.py         # Cache strumieniowania audio (prefetch .mp3)
│   ├── header_tag_extractor.py  # Ekstrakcja linków YT z nagłówków plików zdalnych (Range Requests)
│   ├── player_engine.py         # CENTRALNY SILNIK: koordynacja A/V, Smart Sync, odłączanie timerów na pauzie
│   ├── queue_manager.py         # Dedykowany menedżer kolejki (indeksy, shuffle, loop, Drag & Drop)
│   ├── video_controller_online.py# Kontroler wideo online (wyciszone wyjście audio)
│   ├── video_download_manager.py# Pobieranie teledysków yt-dlp (dziedziczy po BaseDownloadManager)
│   ├── watchdog.py              # Monitor buforowania (zatrzymywany w trybie pure-audio i na pauzie)
│   └── yt_resolver.py           # Ekstrakcja URL YouTube przez yt-dlp
│
├── ui/
│   ├── main_window.py           # Centralny hub okna, Lazy Loading podstron, dispatcher zdarzeń, run_async()
│   ├── router.py                # AppRouter: nawigacja, historia i animacje przejść z czyszczeniem efektów
│   ├── theme_manager.py         # ThemeManager: zarządzanie motywami (system/dark/light/custom)
│   ├── image_loader.py          # AsyncImageLoader: wielowątkowe dekodowanie QImage i downsampling w tle
│   ├── components/              # Cząsteczki UI (logika domeny)
│   │   ├── __init__.py
│   │   ├── bulk_download_handler.py # Masowe pobieranie i auto-sync ulubionych
│   │   ├── custom_media_manager.py  # Własne okładki i zdjęcia artystów
│   │   ├── download_item.py     # Wiersz zadania pobierania ze statystykami MB/s na żywo
│   │   ├── headers.py           # MediaHeader, QueueHeader
│   │   ├── hero_section.py      # Wielki baner na stronie głównej
│   │   ├── media_card.py        # Kafelek dla artysty/albumu (bez inline CSS)
│   │   ├── sidebar_controller.py# Logika paska bocznego i playlist
│   │   ├── song_context_menu.py # Menu PPM dla utworu (pobieranie, linki YT, okładki)
│   │   └── song_item.py         # Wiersz utworu (Zero inline CSS, pre-cached pixmaps, disconnect na zniszczeniu)
│   ├── dialogs/                 # Dedykowane okna dialogowe
│   │   ├── __init__.py
│   │   └── playlist_dialog.py   # Okno dodawania utworu do playlisty (z wdrożonym wzorcem hide->deleteLater)
│   └── widgets/                 # Atomy UI (uniwersalne kontrolki)
│       ├── __init__.py
│       ├── buttons.py           # HoverIconButton z leniwą inicjalizacją animacji i parent=None
│       ├── collapsible.py       # CollapsibleSection (sekcja zwijana)
│       ├── drag_drop.py         # DragDropContainer (Drag & Drop kolejki/playlisty dla Wayland i X11)
│       ├── flow_layout.py       # Elastyczna siatka kafelków
│       ├── frames.py            # ClickableFrame
│       ├── images.py            # RoundedImage (pre-baked rounded pixmaps, brak setClipPath w paintEvent)
│       ├── labels.py            # ElidedLabel, ClickableLabel, ClickableElidedLabel (leniwe metryki fontów)
│       ├── sliders.py           # PremiumSlider
│       ├── smooth_scroll.py     # SmoothScrollArea
│       └── toast.py             # ToastNotification (nakładkowe powiadomienia)
│
├── views/                       # Pełne ekrany (strony aplikacji z Tab Caching i Chunked Rendering)
│   ├── library_base.py          # Bazowa klasa z czyszczeniem w.hide() -> w.setParent(None) -> w.deleteLater()
│   ├── view_albums.py           # Widok albumów z Chunked Rendering i predictive pre-fetching
│   ├── view_artists.py          # Widok artystów z Chunked Rendering
│   ├── view_details.py          # Szczegóły albumu/artysty/playlisty (likwidacja zapytań N+1)
│   ├── view_dev.py              # Widok trybu dewelopera
│   ├── view_downloads.py        # Menedżer pobrań (audio i wideo)
│   ├── view_favs.py             # Ulubione utwory z czystymi domknięciami
│   ├── view_home.py             # Strona główna z równoległym pobieraniem 4x API (ThreadPoolExecutor)
│   ├── view_now_playing.py      # NowPlayingWidget (własne zarządzanie kolejką, wideo i tłem)
│   ├── view_player_bar.py       # Dolny pasek odtwarzacza z throttlingiem pozycji czasu do 1 Hz
│   ├── view_search.py           # Wyszukiwarka biblioteki
│   ├── view_settings.py         # SettingsView (zarządzanie ustawieniami)
│   ├── view_sidebar.py          # Pasek boczny z czyszczeniem widżetów
│   ├── view_tracks.py           # Wszystkie utwory z Chunked Rendering i czystymi indeksami
│   ├── dev/                     # Podstrony DevMode (tab_logs, tab_telemetry, telemetry_window)
│   └── settings/                # Podstrony Ustawień (tab_server, tab_theme, tab_video, tab_offline, tab_dev)
│
├── tests/                       # Zestaw testów automatycznych
│   ├── test_integrity.py        # Test poprawności, modeli, kolejki, SQLite WAL, i18n i Subsonic API
│   ├── test_performance_benchmarks.py # Benchmark wydajnościowy (CSS lag, widgety, RAM leak, sieć)
│   ├── profile_startup.py       # Narzędzie profilowania ścieżki startowej aplikacji
│   └── profile_main_window.py   # Profiler komponentów MainWindow
├── assets/                      # Obrazki statyczne (logo.png)
└── lang/                        # Tłumaczenia JSON
    ├── en.json
    └── pl.json
```

---

## 3. Strony aplikacji (Pages enum)

| ID | Nazwa enum | Klasa Widoku | Ładowanie (Lazy/Eager) |
|---|---|---|---|
| 0 | `Pages.HOME` | `HomeView` | **Eager** (Tworzony na starcie w `_init_ui`) |
| 1 | `Pages.FAVS` | `FavsView` | **Lazy** (Na żądanie przy nawigacji) |
| 2 | `Pages.QUEUE` | Renderowana wewnątrz `NowPlayingWidget` | **Lazy** |
| 3 | `Pages.ALBUMS` | `AlbumsView` | **Lazy** (Tab Cached + Chunked) |
| 4 | `Pages.DETAILS` | `DetailsView` | **Lazy** (Brak N+1) |
| 5 | `Pages.TRACKS` | `TracksView` | **Lazy** (Tab Cached + Chunked) |
| 6 | `Pages.ARTISTS` | `ArtistsView` | **Lazy** (Tab Cached + Chunked) |
| 7 | `Pages.SETTINGS` | `SettingsView` (tably z `views/settings/`) | **Lazy** |
| 8 | `Pages.NOW_PLAYING` | `NowPlayingWidget` | **Eager** (Lekki kontener A/V) |
| 9 | `Pages.DEV_MODE` | `DevModeView` (tably z `views/dev/`) | **Lazy** |
| 10 | `Pages.SEARCH` | `SearchView` | **Lazy** |
| 11 | `Pages.DOWNLOADS` | `DownloadsView` | **Lazy** |

---

## 4. Kluczowe mechanizmy i architektura wydajnościowa

### `MainWindow` & Ścieżka Startowa (~1.2 s)
- **True Lazy View Creation:** `MainWindow._init_ui()` tworzy na starcie wyłącznie `HomeView`. Pozostałe 11 stron powstaje w ułamku milisekundy w metodzie `get_or_create_page(page_idx)` przy pierwszym kliknięciu użytkownika.
- **Odłożone operacje D-Bus i GPU:** Inicjalizacja MPRIS (`_init_mpris`) startuje 300 ms po `w.show()`, a sondowanie sterowników sprzętowych FFmpeg/VA-API (`setVideoOutput`) jest odroczone o 1500 ms.
- **`run_async(task_func, callback_func, page_bound)`** — jedyny dozwolony sposób na operacje I/O / sieć na `QThreadPool`.

### Wydajność UI & Silnik CSS (Zero Inline Styling)
- Wszystkie style widżetów (`SongItem`, `MediaCard`, `Buttons`, `Labels`) są skompilowane w `config.py: get_app_style()`.
- Wiersze `SongItem` nie wywołują `setStyleSheet(...)` w konstruktorze — używają selektorów `#SongTitle`, `#SongCoverOverlay`, `#SongItemBtn`, `#SongDlStatus` itp. Czas przeliczenia kaskady CSS wynosi **<10 ms**.
- Ikony statusu offline korzystają z gotowego `_STATUS_PIXMAP_CACHE` (brak powtórnej rasteryzacji fontów).

### Cykl Życia Pamięci i Eliminacja Wycieków (Retained RAM < 50 KB)
- `SongItem` odłącza sygnały okna głównego w zdarzeniu `self.destroyed.connect(self._disconnect_signals)`.
- Metoda `LibraryScrollArea._clear_layout()` stosuje wzorzec: `w.hide() -> w.setParent(None) -> w.deleteLater()`.
- Widoki listowe eliminują domknięcia lambd `sl=songs`, przekazując wyłącznie indeks liczbowy utworu.

### Warstwa Sieciowa & Baza Danych
- `api_client.py`: Pula `HTTPAdapter(pool_connections=30, pool_maxsize=30)` zapobiega zrzucaniu połączeń TCP.
- `HomeView.fetch()`: Równoległe pobieranie 4 endpointów przez `ThreadPoolExecutor(max_workers=4)`.
- `library_sync.py`: Zapis masowy przez `c.executemany(...)` oraz pragmy `temp_store=MEMORY`, `busy_timeout=5000` i `journal_mode=WAL`.

---

## 5. KRYTYCZNE ZASADY KODOWANIA (NIGDY NIE ŁAM)

1. **Qt API pinning:** Środowisko `os.environ["QT_API"] = "pyside6"` **MUSI** znajdować się na samej górze we WSZYSTKICH modyfikowanych lub tworzonych plikach, tuż po `import os`.
2. **Jedna instrukcja = jedna linia:** Bezwzględny zakaz używania średników (`;`) oraz jednolinijkowych instrukcji złożonych (`if x: return y` jest zabronione).
3. **Brak nagłówków GPV:** Nie dodawaj nagłówków wersji (`# WERSJA PROJEKTU...`).
4. **Signal(object) dla MediaItem:** Zawsze `Signal(object)` dla encji domenowych.
5. **Zero blokującego I/O w UI:** Wszelkie zapytania sieciowe i ciężkie operacje dyskowe wykonuj przez `run_async()`.
6. **Wielojęzyczność:** Zawsze używaj `tr("klucz", "Fallback")` z `core.i18n`.
7. **Kompletność kodu:** Zawsze zwracaj pełny, gotowy do skopiowania kod modyfikowanego pliku, bez skrótów typu `# ... rest of code ...`.
8. **Próg dzielenia odpowiedzi:** Dziel odpowiedź na części dopiero wtedy, gdy łączna długość generowanego kodu przekracza ~1000 linii.

---

## 6. Persystencja Danych (XDG Standard)

| Kategoria | Ścieżka (domyślna) | Zawartość |
|---|---|---|
| **Config** | `~/.config/andromeda-music/config.ini` | Główne ustawienia aplikacji |
| **Cache API** | `~/.cache/andromeda-music/library_cache.db` | SQLite (WAL + MEMORY): Kopia bazy serwera |
| **Cache Obrazów**| `~/.cache/andromeda-music/images/` | QNetworkDiskCache na pobrane okładki HTTP |
| **Zapisane Wideo**| `~/.local/share/andromeda-music/video-offline/` | Trwałe pliki teledysków MP4/WEBM |
| **Baza Wideo** | `~/.cache/andromeda-music/offline_videos.db` | SQLite (WAL): Kolejka i historia yt-dlp |
| **Zapisane Audio**| `~/.local/share/andromeda-music/audio-offline/` | Trwałe pobrane pliki MP3 |
| **Baza Audio** | `~/.cache/andromeda-music/offline_audio.db` | SQLite (WAL): Kolejka i historia pobrań MP3 |
| **Custom Grafiki**| `~/.local/share/andromeda-music/custom_covers/` oraz `custom_artists/` | Lokalne zdjęcia albumów i artystów |
| **Logi & Telemetria**| `~/.local/share/andromeda-music/logs/` | CSV z telemetrią oraz log błędów |

Uruchomienie: `python3 main.py` (lub `python3 app.py`)
Testy: `python3 tests/test_integrity.py` oraz `python3 tests/test_performance_benchmarks.py`
```

---

### PROMPT INICJUJĄCY DO WKLEJENIA NA NOWYM CHACIE:

```markdown
Cześć! Kontynuujemy rozwój i przygotowanie do otwartej publikacji (Open Source) odtwarzacza muzycznego Andromeda Music (v14.20+).
Projekt tworzony jest w Pythonie 3 + PySide6 (Qt6) na Linuksa (KDE/Wayland, Hyprland, X11) i łączy się z serwerami zgodnymi z protokołem Navidrome / Subsonic (z opcją synchronizacji teledysków YouTube przez yt-dlp).

---

### KRYTYCZNE ZASADY KODOWANIA (BEZWZGLĘDNE):
1. Inicjalizacja Qt API: `os.environ["QT_API"] = "pyside6"` MUSI znajdować się na samej górze każdego pliku Qt, tuż pod `import os`.
2. PEP8 i instrukcje: Bezwzględnie jedna instrukcja w linii. Kategoryczny ZAKAZ używania średników (`;`) oraz instrukcji jednolinijkowych (`if x: return y` jest zabronione).
3. Brak nagłówków GPV: NIE dodawaj nagłówków wersji (`# WERSJA PROJEKTU...`).
4. Sygnały Qt: Przy obiektach domenowych (`MediaItem`, `Song`, `Album`, `Artist`) ZAWSZE używaj `Signal(object)` – nigdy `Signal(dict)` ani `Signal(str)`.
5. Wątek GUI (Zero blokującego I/O): Blokujące operacje I/O/sieć wykonujemy wyłącznie w tle przez `run_async()`. Ścieżki zawsze pobieramy z `PathsManager` (standardy XDG).
6. Czyszczenie widżetów Qt: W metodach czyszczących (`_clear`, `_clear_layout`, `set_playlists` itp.) zawsze wywołuj `w.hide() -> w.setParent(None) -> w.deleteLater()`.
7. Wielojęzyczność: Używaj `tr("klucz", "Fallback")` z `core.i18n`. Nie wpisuj tekstów UI na sztywno.
8. Kompletność kodu: Zawsze zwracaj CAŁY, kompletny kod modyfikowanego pliku, bez skrótów typu `# ... rest of code ...`.
9. Dzielenie wiadomości: Dziel odpowiedź na mniejsze pakiety dopiero powyżej ~1000 linii kodu.
10. Deklaracja trybu: Rozpoczynaj każdą odpowiedź od trybu: `[BURZA MÓZGÓW]`, `[WDRAŻAMY]` / `[KOD]` lub `[DEBUG]`.
11. Język: Komunikacja i komentarze w języku polskim.

---

### BIEŻĄCY STAN PROJEKTU (CO ZOSTAŁO ZROBIONE):
1. Krok 1: Bezpieczeństwo i higiena (`config.example.ini`, `.gitignore`, usunięcie hardcoded ścieżek deweloperskich).
2. Krok 2: Wielojęzyczność i oczyszczenie UI (kompletne słowniki `lang/pl.json` i `lang/en.json`, wpięcie `tr()`, naprawa Drag & Drop, na żywo statystyki pobierania).
3. Kompleksowy audyt i optymalizacja wydajnościowa (Sekcje 1-6):
   - Zlikwidowano 600+ inline `setStyleSheet` (czas przeliczenia CSS spadł z 314 ms do 7.9 ms).
   - Zlikwidowano wyciek pamięci RAM (Retained RAM spadł z 1402 KB do 45 KB).
   - Zlikwidowano zapytania N+1 w `view_details.py` i wprowadzono równoległe pobieranie w `view_home.py` (przyspieszenie 3.8x).
   - Przeniesiono dekodowanie i skalowanie grafik do wątku roboczego (`AsyncImageLoader`), zoptymalizowano `RoundedImage`.
   - Zoptymalizowano ścieżkę startową aplikacji (True Lazy View Creation w `MainWindow`, odłożenie MPRIS i sondowania wideo FFmpeg/VA-API — czas startu okna spadł z 15 s do ~1.2 s!).
   - Wdrożono pakiet testów: `tests/test_integrity.py` oraz `tests/test_performance_benchmarks.py` (wszystkie testy przechodzą w 100% na zielono [OK]).
