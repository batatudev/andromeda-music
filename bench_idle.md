## Raport Wydajnościowy: Andromeda Music (Tryb Spoczynku / Idle)

| Metryka | Andromeda (Idle) | Spotify | Feishin | Brave | Firefox |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Czas startu (Cold Startup)** | **0.189 s** | 0.408 s | 0.374 s | 0.158 s | 0.199 s |
| **Średnie CPU (Cały procesor)** | **0.01%** | 1.04% | 1.03% | 0.49% | 1.74% |
| **Średnie CPU (1 rdzeń)** | **0.12%** | 8.30% | 8.26% | 3.88% | 13.90% |
| **Szczytowe CPU (Max Spike)** | **0.23%** | 12.19% | 16.72% | 10.64% | 4.97% |
| **Średnie GPU (Łączne)** | **0.00%** | 0.00% | 0.15% | 0.04% | 0.13% |
| **GPU 3D (Shadery GLSL)** | **0.00%** | 0.00% | 0.15% | 0.04% | 0.13% |
| **GPU Video (VA-API Dekoder)** | **0.00%** | 0.00% | 0.00% | 0.00% | 0.00% |
| **Pamięć rzeczywista (PSS)** | **233.7 MB** | 922.1 MB | 455.4 MB | 505.8 MB | 695.5 MB |
| **Pamięć fizyczna (RSS)** | **359.9 MB** | 1561.0 MB | 888.9 MB | 1569.4 MB | 1205.5 MB |
| **Liczba procesów systemowych** | **1** | 11 | 14 | 14 | 14 |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 225.8 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.20 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1290.2 KB
