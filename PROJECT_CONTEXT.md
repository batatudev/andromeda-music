# PROJECT_CONTEXT.md - NAVIDROME PLAYER V2 (v14.7)

System Instruction for AI context and architecture understanding.

## 1. Executive Summary
Navidrome Player V2 is a premium, open-source music player designed for Navidrome and Subsonic-compatible servers. Built using **Python 3** and **PySide6 (Qt6)** on Linux, it features a highly modular **MVC-inspired architecture**. The project focuses on high-performance audio/video synchronization (YouTube integration), intelligent bandwidth management (ARF 3.1), and a modern, fluid user interface.

## 2. Directory Tree
```text
/home/mateusz/navidrome-player-v2/
├── app.py                  # Real Entry Point (Initialization & Start)
├── main.py                 # Entry Point Proxy (backward compatibility)
├── api_client.py           # Navidrome API Handler
├── config.py               # Global State, Themes & Constants
├── utils.py                # Shared Utilities (Workers, Image Loader, Networking)
├── core/                   # Business Logic & Data Models
│   ├── enums.py            # System-wide Enums (EngineState, MediaType)
│   ├── media_item.py       # Data Wrapper (MediaItem Class)
│   └── telemetry_service.py # Performance Logging (v3.2)
├── engine/                 # System Engines (The "C" in MVC)
│   ├── player_engine.py    # Core Media Management
│   ├── arf_manager.py      # Auto-Resolution-Fallback (ARF 3.1)
│   ├── watchdog.py         # UI/Video Guard (Watchdog Service)
│   ├── yt_resolver.py      # YouTube URL Extractor
│   ├── cache_manager.py    # Audio/Video Cache System
│   └── mpris_adapter.py    # Linux MPRIS Integration
├── ui/                     # UI Layer (The "V" in MVC)
│   ├── main_window.py      # Main Window & Navigation Controller
│   ├── widgets/            # Low-level UI Elements (Atomic)
│   │   ├── buttons.py      # HoverIconButton
│   │   ├── images.py       # RoundedImage
│   │   ├── sliders.py      # PremiumSlider
│   │   └── ...
│   └── components/         # High-level UI Blocks (Molecules)
│       ├── song_item.py    # Individual Song Row
│       ├── media_card.py   # Album/Artist Card
│       └── ...
└── views/                  # Screen-level Widgets (Pages)
    ├── view_home.py        # Dashboard View
    ├── view_now_playing.py # Immersive Player View
    └── ...
```

## 3. Architecture Mapping
| Old File (v13.x) | New Module (v14.7+) | Responsibility |
| :--- | :--- | :--- |
| `main.py` (Monolith) | `app.py` & `ui/main_window.py` | App init (app.py) vs Navigation/UI (main_window.py). |
| `audio_engine.py` | `engine/player_engine.py` | Media playback synchronization. |
| `ui_core.py` | `ui/widgets/` | Generic UI atoms (Buttons, Sliders, Layouts). |
| `ui_cards.py` | `ui/components/` | Domain-specific UI blocks (SongItem, MediaCard). |
| `telemetry.py` | `core/telemetry_service.py` | Performance monitoring (18 parameters CSV). |

## 4. Key Design Patterns & Rules
*   **Qt API Pinning:** `os.environ["QT_API"] = "pyside6"` MUST be at the very top of every file (immediately after `import os`) to prevent library conflicts.
*   **One Instruction Per Line:** Categorical ban on semicolons (`;`). Every statement must occupy exactly one line.
*   **Signal Integrity:** Use `Signal(object)` for passing `MediaItem` instances. Using `Signal(dict)` or `Signal(str)` causes C++ object slicing and loss of Python properties.
*   **GPV Header:** Every file must start with a `# WERSJA PROJEKTU: 14.7` header and `# OPIS ZMIAN` (Description of changes).
*   **Dependency Injection:** Services (like `Watchdog`, `Telemetry`) are passed to the `MainWindow` during initialization, not created as globals.

## 5. Critical Dependencies & Entry Point
*   **Entry Point:** `app.py`.
*   **Execution:** `python3 app.py` (or `python3 main.py` for proxy start).
*   **Core Deps:** `PySide6`, `qtawesome`, `yt-dlp`, `requests`.
*   **System Req:** Linux with PulseAudio/PipeWire for sound role properties.

## 6. Current Status & Gotchas

---
**END OF CONTEXT**
