## Raport Porównawczy: Andromeda Music vs Konkurencja (Odtwarzanie Wideo)

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), teledyski 1080p, standaryzowany pomiar jądra (/proc/smaps_rollup)*

| Metryka | Andromeda (Video 1080p Live) | Andromeda (Video 480p Live) | Andromeda (Video Offline) | Brave | Firefox |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Czas startu (Cold Startup)** | **0.227 s** | **0.253 s** | **0.256 s** | 0.120 s | 0.149 s |
| **Pamięć rzeczywista (PSS)** | **330.0 MB** | **291.6 MB** | **257.2 MB** | 502.5 MB | 736.7 MB |
| **Pamięć fizyczna (RSS)** | **459.2 MB** | **421.7 MB** | **384.4 MB** | 1572.4 MB | 1384.9 MB |
| **Średnie CPU (Odtwarzanie Wideo)** | **96.80%** | **102.29%** | **103.18%** | 31.58% | 41.33% |
| **Szczytowe CPU (Max Spike)** | **133.57%** | **125.67%** | **134.47%** | 146.93% | 229.26% |
| **Liczba procesów systemowych** | **1 ** | **1 ** | **1 ** | 14  | 10  |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 220.6 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.28 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1277.4 KB