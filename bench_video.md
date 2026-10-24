## Raport Porównawczy: Andromeda Music vs Konkurencja (Odtwarzanie Wideo)

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), teledyski 1080p, standaryzowany pomiar jądra (/proc/smaps_rollup & DRM fdinfo)*

| Metryka | Andromeda (Video 1080p Live) | Andromeda (Video 480p Live) | Andromeda (Video Offline) | Brave (YouTube Music) | Firefox (YouTube Music) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Czas startu (Cold Startup)** | **0.187 s** | **0.305 s** | **0.255 s** | 0.152 s | 0.198 s |
| **Średnie CPU (Cały procesor)** | **2.80%** | **3.33%** | **3.04%** | 3.87% | 4.91% |
| **Średnie CPU (1 rdzeń)** | **22.41%** | **26.64%** | **24.35%** | 30.93% | 39.28% |
| **Szczytowe CPU (Max Spike)** | **15.25%** | **10.94%** | **14.74%** | 21.55% | 28.76% |
| **Średnie GPU (Łączne)** | **58.30%** | **58.48%** | **56.18%** | 8.05% | 7.28% |
| **GPU 3D (Shadery GLSL)** | **57.69%** | **57.87%** | **55.83%** | 7.13% | 6.57% |
| **GPU Video (VA-API Dekoder)** | **0.64%** | **0.66%** | **0.64%** | 0.92% | 0.84% |
| **Pamięć rzeczywista (PSS)** | **293.7 MB** | **298.9 MB** | **250.3 MB** | 495.8 MB | 766.4 MB |
| **Pamięć fizyczna (RSS)** | **425.9 MB** | **428.9 MB** | **379.7 MB** | 1465.2 MB | 1410.9 MB |
| **Liczba procesów systemowych** | **1** | **1** | **1** | 13 | 10 |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 218.1 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.22 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1274.0 KB
