## Raport Porównawczy: Andromeda Music vs Konkurencja (Audio Playback)

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), 2 utwory (120s), pomiar jądra (/proc/smaps_rollup)*

| Metryka | Andromeda (Audio Playback) | Spotify | Feishin | Brave | Firefox |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Czas startu (Cold Startup)** | **0.186 s** | 0.401 s | 0.447 s | 0.168 s | 0.269 s |
| **Średnie CPU (Cały procesor)** | **1.15%** | 4.64% | 2.19% | 1.51% | 1.93% |
| **Średnie CPU (1 rdzeń)** | **9.24%** | 37.12% | 17.55% | 12.06% | 15.46% |
| **Szczytowe CPU (Max Spike)** | **4.67%** | 27.43% | 11.61% | 30.93% | 24.56% |
| **Średnie GPU (Łączne)** | **7.14%** | 18.46% | 0.34% | 0.67% | 0.56% |
| **GPU 3D (Shadery GLSL)** | **7.14%** | 18.25% | 0.34% | 0.67% | 0.56% |
| **GPU Video (VA-API Dekoder)** | **0.00%** | 0.21% | 0.00% | 0.00% | 0.00% |
| **Pamięć rzeczywista (PSS)** | **241.7 MB** | 902.8 MB | 455.8 MB | 510.4 MB | 767.0 MB |
| **Pamięć fizyczna (RSS)** | **369.1 MB** | 1545.0 MB | 893.9 MB | 1585.8 MB | 1412.8 MB |
| **Liczba procesów systemowych** | **1** | 11 | 14 | 14 | 15 |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 215.9 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.21 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1288.5 KB
