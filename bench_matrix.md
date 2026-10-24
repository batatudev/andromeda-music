## Raport Porównawczy: Andromeda Music vs Konkurencja (Odtwarzanie Wideo)

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), teledyski 1080p, standaryzowany pomiar jądra (/proc/smaps_rollup & DRM fdinfo)*

| Metryka | Andromeda Video (RAW - Bez efektów) | Andromeda Video (+ Przyciemnienie 30%) | Andromeda Video (+ Blur 40) | Andromeda Video (Full Ambient 40/30%) |
| :--- | :---: | :---: | :---: | :---: |
| **Czas startu (Cold Startup)** | **0.237 s** | **0.299 s** | **0.269 s** | **0.299 s** |
| **Średnie CPU (Cały procesor)** | **2.47%** | **2.08%** | **2.12%** | **3.24%** |
| **Średnie CPU (1 rdzeń)** | **19.78%** | **16.62%** | **17.00%** | **25.90%** |
| **Szczytowe CPU (Max Spike)** | **12.74%** | **14.52%** | **12.43%** | **14.74%** |
| **Średnie GPU (Łączne)** | **31.17%** | **31.69%** | **28.80%** | **55.36%** |
| **GPU 3D (Shadery GLSL)** | **30.47%** | **31.00%** | **28.44%** | **54.80%** |
| **GPU Video (VA-API Dekoder)** | **0.73%** | **0.72%** | **0.36%** | **0.63%** |
| **Pamięć rzeczywista (PSS)** | **297.8 MB** | **294.6 MB** | **298.8 MB** | **301.5 MB** |
| **Pamięć fizyczna (RSS)** | **429.2 MB** | **426.4 MB** | **429.8 MB** | **433.0 MB** |
| **Liczba procesów systemowych** | **1** | **1** | **1** | **1** |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 213.6 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.29 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1284.8 KB
