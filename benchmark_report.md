## Raport Porównawczy: Andromeda Music vs Konkurencja (Odtwarzanie Wideo)

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), teledyski 1080p, standaryzowany pomiar jądra (/proc/smaps_rollup)*

| Metryka | Andromeda (Video 1080p Live) | Andromeda (Video 480p Live) | Andromeda (Video Offline) | Brave | Firefox |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Czas startu (Cold Startup)** | **0.195 s** | **0.307 s** | **0.273 s** | 0.104 s | 0.277 s |
| **Pamięć rzeczywista (PSS)** | **300.2 MB** | **295.2 MB** | **255.0 MB** | 490.6 MB | 813.5 MB |
| **Pamięć fizyczna (RSS)** | **430.6 MB** | **425.3 MB** | **382.5 MB** | 1567.7 MB | 1456.0 MB |
| **Średnie CPU (Odtwarzanie Wideo)** | **20.17%** | **24.87%** | **24.06%** | 30.95% | 41.83% |
| **Szczytowe CPU (Max Spike)** | **123.79%** | **108.76%** | **110.35%** | 196.73% | 234.01% |
| **Liczba procesów systemowych** | **1 ** | **1 ** | **1 ** | 15  | 10  |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 240.8 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.24 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1280.8 KB