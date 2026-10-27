# PROJECT_CONTEXT.md — ANDROMEDA MUSIC PLAYER (v14.25+)

Dokument kontekstowy dla modeli AI. Zawiera architekturę, konwencje, mechanizmy wydajnościowe i kluczowe moduły projektu.
Przed modyfikacją jakiegokolwiek pliku — przeczytaj tę dokumentację w całości.

---

## 1. Executive Summary

**Andromeda Music** to nowoczesny, wysoce zoptymalizowany, open-source odtwarzacz muzyczny dla Linux (KDE/Wayland/Hyprland/Omarchy/X11), napisany w **Python 3 + PySide6 (Qt6)**. Łączy się z serwerami zgodnymi z protokołem **Navidrome/Subsonic** przez REST API.

Kluczowe funkcje i fundamenty architektoniczne:
- **Akceleracja Sprzętowa i Potok Zero-Copy GPU (Qt RHI):** Rendering wideo odbywa się z użyciem `QQuickWidget` i natywnych shaderów GLSL (`MultiEffect`). Dekodowanie wideo przez VA-API i kompozycja efektów (kinowy blur) dzieją się całkowicie na karcie graficznej, redukując użycie CPU z ~100% do ~3%.
- **Synchronizacja Audio/Wideo:** Koordynacja odtwarzania audio z teledyskami z YouTube w czasie rzeczywistym (`yt-dlp` / ARF 3.1 / Smart Sync).
- **Zoptymalizowany silnik resolvera wideo:** Wielostopniowa, odporna ścieżka pozyskiwania strumieni (priorytetowy `cookies.txt` $\to$ natychmiastowy Fast-Path bez cookies $\to$ bezpieczny fallback na profile przeglądarek z ochroną przed blokadami baz SQLite $\to$ awaryjny klient TV).
- **Offline-First & Magazyn SQLite:** Lokalne bazy SQLite w trybie WAL z `temp_store=MEMORY` i `busy_timeout=5000`. Klonowanie metadanych biblioteki i pobieranie plików MP3 oraz teledysków MP4 na dysk.
- **Centrum Transferów i Magazynu (Styl Zenith Video Player):** Graficzna karta pamięci masowej NVMe offline (`shutil.disk_usage`), filtry stanów w pigułkach (`Wszystkie`, `W trakcie`, `W kolejce`, `Ukończone`, `Błędy`), filtr źródeł, wspólne sortowanie chronologiczne (`added_at DESC`), paginacja ukończonych zadań oraz trwałe czyszczenie historii.
- **Responsywny interfejs dla Tiling WM (Hyprland / Omarchy):** Płynna adaptacja do zmiennych rozmiarów okien, jednowierszowy niełamliwy kontener `ResponsiveCardRow` w `HomeView`. Aplikacja uruchamia się domyślnie w trybie zmaksymalizowanym (`showMaximized()`).
- **Natywne Benchmarki Systemowe:** Wbudowany system profilowania odczytujący dane prosto z jądra Linuksa (`/proc/smaps_rollup`, `/proc/<pid>/stat`, `/proc/<pid>/fdinfo` DRM) do mierzenia realnego zużycia RAM (PSS/RSS), CPU oraz izolowanego obciążenia GPU (3D Render vs Video Decode).
- **Integracja systemowa Linux (XDG):** Autonomiczny instalator `install-desktop.sh`, detekcja D-Bus MPRIS (z obsługą quirks przeglądarek) oraz PipeWire/PulseAudio (`media.role=music`).

---

## 2. Drzewo katalogów i odpowiedzialność plików

```text
andromeda-music/
├── AGENTS.md                    # Instrukcje systemowe dla agentów AI
├── ai_bundler.py                # Narzędzie analityczno-pakujące kod dla modeli AI
├── api_client.py                # Klient Navidrome REST API (z pulą HTTPAdapter 30 conn)
├── app.py                       # Punkt wejścia: format powierzchni (8-bit alpha), inicjalizacja QApplication, MainWindow
├── config.example.ini           # Przykładowy, bezpieczny szablon konfiguracji
├── config.ini                   # Prywatny plik ustawień użytkownika (wykluczony z gita)
├── config.py                    # Globalny stan: APP_CONFIG, słownik THEME, Pages enum, skompilowany get_app_style()
├── install-desktop.sh           # Dynamiczny instalator integracji pulpitu (XDG .desktop, ikony hicolor, venv)
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
│   ├── library_sync.py          # Synchronizacja bazy serwera do SQLite (`library_cache.db`) z bezpieczną metodą stop()
│   ├── logger.py                # Rejestratory: AppLogger (błędy) oraz TelemetryRecorder (CSV)
│   ├── models.py                # MediaItem, Song, Album, Artist — wrappery DTO dla danych z API
│   ├── network_monitor.py       # Wątek monitorujący stan łącza (1.1.1.1) i ping serwera
│   ├── paths.py                 # PathsManager: Standardy XDG, migracja, połączenia SQLite WAL + MEMORY
│   ├── system_health.py         # SystemHealthChecker: weryfikacja binarki ffmpeg oraz modułów MPRIS D-Bus
│   └── telemetry_service.py     # Usługa zbierania telemetrii wydajnościowej
│
├── engine/
│   ├── arf_manager.py           # ARF 3.1: Auto-Resolution-Fallback i dobór rozdzielczości wideo
│   ├── audio_controller.py      # Kontroler audio (QMediaPlayer + dynamiczne przełączanie urządzeń)
│   ├── audio_download_manager.py# Pobieranie plików mp3 (dziedziczy po BaseDownloadManager, stop(), czyszczenie .tmp)
│   ├── base_download_manager.py # Baza menedżera pobierania (kolejka wątkowa, uśpienie, stan SQLite, Clean Exit)
│   ├── cache_manager.py         # Cache strumieniowania audio (prefetch .mp3)
│   ├── header_tag_extractor.py  # Ekstrakcja linków YT z nagłówków plików zdalnych (Range Requests)
│   ├── player_engine.py         # CENTRALNY SILNIK: koordynacja A/V, Smart Sync, odłączanie timerów na pauzie
│   ├── queue_manager.py         # Dedykowany menedżer kolejki (indeksy, shuffle, loop, Drag & Drop)
│   ├── video_controller_online.py# Kontroler wideo online (wyciszone wyjście audio)
│   ├── video_download_manager.py# Pobieranie teledysków yt-dlp (dziedziczy po BaseDownloadManager, stop(), czyszczenie .part)
│   ├── watchdog.py              # Monitor buforowania (zatrzymywany w trybie pure-audio i na pauzie)
│   └── yt_resolver.py           # Ekstrakcja URL YouTube przez yt-dlp (Fast-Path, cookies.txt, bezpieczny fallback)
│
├── ui/
│   ├── main_window.py           # Centralny hub okna, Lazy Loading, dispatcher zdarzeń, run_async(), Clean Exit
│   ├── router.py                # AppRouter: nawigacja, historia i animacje przejść z czyszczeniem efektów
│   ├── theme_manager.py         # ThemeManager: zarządzanie motywami (system/dark/light/custom)
│   ├── image_loader.py          # AsyncImageLoader: wielowątkowe dekodowanie QImage i downsampling w tle
│   ├── components/              # Cząsteczki UI (logika domeny)
│   │   ├── __init__.py
│   │   ├── bulk_download_handler.py # Masowe pobieranie i auto-sync ulubionych
│   │   ├── custom_media_manager.py  # Własne okładki i zdjęcia artystów
│   │   ├── download_item.py     # Wiersz zadania pobierania ze statystykami MB/s na żywo i stałym przyciskiem ✕
│   │   ├── headers.py           # MediaHeader, QueueHeader
│   │   ├── hero_section.py      # Wielki prostokątny baner na stronie głównej (bez dziurawych rogów)
│   │   ├── media_card.py        # Kafelek dla artysty/albumu (responsywne skalowanie w wierszu)
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
│       ├── flow_layout.py       # Elastyczna siatka kafelków wielowierszowa dla pełnych bibliotek
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
│   ├── view_dev.py              # Widok trybu dewelopera (karty dopasowane do szerokości roboczej)
│   ├── view_downloads.py        # Centrum Transferów w stylu Zenith: karta NVMe, pigułki filtrów, paginacja
│   ├── view_favs.py             # Ulubione utwory z czystymi domknięciami
│   ├── view_home.py             # Strona główna z ResponsiveCardRow (1 pełny wiersz Albumów i Artystów)
│   ├── view_now_playing.py      # NowPlayingWidget: Sprzętowy QQuickWidget dla wideo z QML MultiEffect i zero-copy GPU
│   ├── view_player_bar.py       # Dolny pasek odtwarzacza z throttlingiem pozycji czasu do 1 Hz
│   ├── view_search.py           # Wyszukiwarka biblioteki
│   ├── view_settings.py         # SettingsView (zbalansowana wycentrowana kolumna 880 px)
│   ├── view_sidebar.py          # Pasek boczny z czyszczeniem widżetów
│   ├── view_tracks.py           # Wszystkie utwory z Chunked Rendering i czystymi indeksami
│   ├── dev/                     # Podstrony DevMode (tab_logs, tab_telemetry, telemetry_window)
│   └── settings/                # Podstrony Ustawień (tab_server, tab_theme, tab_video, tab_offline, tab_dev)
│
├── tests/                       # Zestaw testów automatycznych
│   ├── benchmark_runner.py      # Główny CLI systemu benchmarków wydajnościowych aplikacji
│   ├── test_integrity.py        # Test poprawności, modeli, kolejki, SQLite WAL, i18n i Subsonic API
│   ├── profile_startup.py       # Narzędzie profilowania ścieżki startowej aplikacji
│   ├── profile_main_window.py   # Profiler komponentów MainWindow
│   └── benchmarks/              # Modułowy system Black-Box Profiling (Linuksowe wywołania systemowe)
│       ├── __init__.py
│       ├── internal.py          # Mikrobenchmarki Qt w trybie headless
│       ├── locator.py           # Detekcja binarek, przeglądarek i układu monitorów (kscreen-doctor)
│       ├── monitor.py           # Próbnik jądra: smaps_rollup (RAM), stat (CPU), DRM fdinfo (GPU Render/Video) i D-Bus MPRIS
│       ├── reporter.py          # Generator raportów CSV oraz tabel Markdown
│       └── runner.py            # Cykl życia benchmarku na żywo (Warmup, PID Tree tracking)
│
├── assets/                      # Obrazki statyczne (logo.png)
└── lang/                        # Tłumaczenia JSON
    ├── en.json
    └── pl.json
```

---

## 3. Strony aplikacji (Pages enum)

| ID | Nazwa enum | Klasa Widoku | Ładowanie (Lazy/Eager) |
|---|---|---|---|
| 0 | `Pages.HOME` | `HomeView` | **Eager** (Tworzony na starcie w `_init_ui`, jednowierszowe `ResponsiveCardRow`) |
| 1 | `Pages.FAVS` | `FavsView` | **Lazy** (Na żądanie przy nawigacji) |
| 2 | `Pages.QUEUE` | Renderowana wewnątrz `NowPlayingWidget` | **Lazy** |
| 3 | `Pages.ALBUMS` | `AlbumsView` | **Lazy** (Tab Cached + Chunked) |
| 4 | `Pages.DETAILS` | `DetailsView` | **Lazy** (Brak N+1) |
| 5 | `Pages.TRACKS` | `TracksView` | **Lazy** (Tab Cached + Chunked) |
| 6 | `Pages.ARTISTS` | `ArtistsView` | **Lazy** (Tab Cached + Chunked) |
| 7 | `Pages.SETTINGS` | `SettingsView` (tably z `views/settings/`) | **Lazy** (Zbalansowana wycentrowana kolumna 880 px) |
| 8 | `Pages.NOW_PLAYING` | `NowPlayingWidget` | **Eager** (Lekki kontener A/V ze sprzętowym tłem `QQuickWidget`) |
| 9 | `Pages.DEV_MODE` | `DevModeView` (tably z `views/dev/`) | **Lazy** |
| 10 | `Pages.SEARCH` | `SearchView` | **Lazy** |
| 11 | `Pages.DOWNLOADS` | `DownloadsView` | **Lazy** (Centrum Transferów Zenith: NVMe, pigułki filtrów, paginacja) |

---

## 4. Kluczowe mechanizmy i architektura wydajnościowa

### Akceleracja Sprzętowa i Potok GPU (Qt RHI)
- **`QQuickWidget` z QML `MultiEffect`:** Tło wideo na ekranie `NowPlayingWidget` jest sprzętowo renderowane na karcie graficznej. Wideo zdekodowane przez VA-API trafia jako tekstura prosto do bufora FBO `QQuickWidget`. Rozmycie Gaussa jest obliczane przez shader GLSL. Eliminuje to zabójczy dla CPU software'owy `QGraphicsBlurEffect`.
- **Czysta przezroczystość UI:** Ustawienie `QSurfaceFormat` z 8-bitowym kanałem alfa (`setAlphaBufferSize(8)`) w `app.py` zapobiega utracie przezroczystości i czarnym tłom dla widgetów rastrowych nakładanych na okno z kontekstem sprzętowym na Waylandzie.
- **`DimOverlay`:** Zamiast software'owego `QGraphicsOpacityEffect`, przyciemnienie wideo jest realizowane jednorazowym rysowaniem na ekranie półprzezroczystego koloru w `paintEvent`, ograniczając zużycie CPU w tym aspekcie niemal do zera.

### Natywne Benchmarki Systemowe (Linux DRM & smaps_rollup)
- Projekt posiada zaawansowany pakiet testowy w `tests/benchmarks/`. Zamiast polegać na wewnętrznym pomiarze kodu, skrypt sprawdza struktury jądra Linuksa wywoływane przez aplikację:
  - **RAM (PSS/RSS):** `/proc/<pid>/smaps_rollup` do dokładnego śledzenia realnie zużytej i współdzielonej pamięci.
  - **CPU:** `/proc/<pid>/stat` do pomiaru globalnego czasu procesora zdenormalizowanego do wszystkich wątków systemowych.
  - **GPU (DRM fdinfo):** Odpytywanie deskryptorów urządzeń renderujących (`/proc/<pid>/fdinfo`) w celu pomiaru wykorzystania silnika sprzętowego cieniowania (`drm-engine-render`) oraz dedykowanego dekodera wideo (`drm-engine-video` / VA-API). Umożliwia to testy Black-Box bez roota.
  - **MPRIS Dynamic Track Detection:** Skrypt benchmarkowy automatycznie komunikuje się przez D-Bus SessionBus ze wszystkimi odtwarzaczami, kontrolując weryfikację startu testu w czasie rzeczywistym.

### Stabilność Procesów, Wątki & Clean Exit
- **Flagi cyklu życia wątków (`_is_running`):** Menedżery pobierania oraz synchronizator biblioteki implementują `stop()`, uniemożliwiając wiszenie procesów.
- **Procedura `MainWindow.closeEvent`:** Zatrzymuje pobierania, synchronizację biblioteki, monitory sieci i odczekuje kontrolowane `threadpool.waitForDone(600)`.

### Odporny Silnik Rozwiązywania Wideo (`YTResolver`)
- **Priorytetowy plik ciasteczek:** Jeśli w XDG znajduje się `cookies.txt`, jest używany bezpośrednio.
- **Fast-Path bez ciasteczek:** Natychmiastowe pobieranie strumienia bez przeglądarek (90% teledysków).
- **Ochrona przed blokadą SQLite:** Wyłapywanie błędu otwartej przeglądarki podczas używania `cookiesfrombrowser` w `yt-dlp`.

### Responsywność UI dla Tiling WM (Hyprland / Omarchy)
- **`ResponsiveCardRow` w `HomeView`:** Kontener `QHBoxLayout`, który nigdy nie łamie wiersza, wyliczający dynamicznie optymalną liczbę kafelków. Zwraca `minimumSizeHint = QSize(0, 0)`, by nie blokować okna przed zmniejszaniem.

---

## 5. KRYTYCZNE ZASADY KODOWANIA (NIGDY NIE ŁAM)

1. **Qt API pinning:** Środowisko `os.environ["QT_API"] = "pyside6"` **MUSI** znajdować się na samej górze we WSZYSTKICH modyfikowanych lub tworzonych plikach, tuż po `import os`.
2. **Jedna instrukcja = jedna linia:** Bezwzględny zakaz używania średników (`;`) oraz jednolinijkowych instrukcji złożonych (`if x: return y` jest zabronione).
3. **Brak nagłówków GPV:** Nie dodawaj nagłówków wersji (`# WERSJA PROJEKTU...`).
4. **Signal(object) dla MediaItem:** Zawsze `Signal(object)` dla encji domenowych. Nie rzutuj na dict!
5. **Zero blokującego I/O w UI:** Wszelkie zapytania sieciowe i ciężkie operacje dyskowe wykonuj przez `run_async()`.
6. **Wielojęzyczność:** Zawsze używaj `tr("klucz", "Fallback")` z `core.i18n`.
7. **Kompletność kodu:** Zawsze zwracaj pełny, gotowy do skopiowania kod modyfikowanego pliku, bez skrótów typu `# ... rest of code ...`.
8. **Próg dzielenia odpowiedzi:** Dziel odpowiedź na części dopiero wtedy, gdy łączna długość generowanego kodu przekracza ~1000 linii.
9. **Kategoryczny zakaz `QGraphicsBlurEffect` dla wideo:** Do rozmywania tła wideo ZAWSZE używamy `QQuickWidget` z QML `MultiEffect`. Odciąża to w 100% CPU komputera.

---

## 6. Persystencja Danych (XDG Standard)

| Kategoria | Ścieżka (domyślna) | Zawartość |
|---|---|---|
| **Config** | `~/.config/andromeda-music/config.ini` | Główne ustawienia aplikacji |
| **Cache API** | `~/.cache/andromeda-music/library_cache.db` | SQLite (WAL + MEMORY): Kopia bazy serwera |
| **Cache Obrazów**| `~/.cache/andromeda-music/images/` | QNetworkDiskCache na pobrane okładki HTTP |
| **Zapisane Wideo**| `~/.local/share/andromeda-music/video-offline/` | Trwałe pliki teledysków MP4/WEBM |
| **Baza Wideo** | `~/.cache/andromeda-music/offline_videos.db` | SQLite (WAL): Kolejka, historia yt-dlp i nadpisania linków |
| **Zapisane Audio**| `~/.local/share/andromeda-music/audio-offline/` | Trwałe pobrane pliki MP3 |
| **Baza Audio** | `~/.cache/andromeda-music/offline_audio.db` | SQLite (WAL): Kolejka i historia pobrań MP3 |
| **Custom Grafiki**| `~/.local/share/andromeda-music/custom_covers/` oraz `custom_artists/` | Lokalne zdjęcia albumów i artystów |
| **Logi & Telemetria**| `~/.local/share/andromeda-music/logs/` | CSV z telemetrią oraz log błędów |
| **Skrót Pulpitu** | `~/.local/share/applications/andromeda-music.desktop` | Rejestracja aplikacji w KDE/GNOME przez `install-desktop.sh` |
| **Ikony Pulpitu** | `~/.local/share/icons/hicolor/512x512/apps/andromeda-music.png` | Oficjalna ikona aplikacji XDG |

Uruchomienie: `python3 main.py` lub ikona programu
Testy: pakiet `tests/benchmarks/` oraz `tests/test_integrity.py`
