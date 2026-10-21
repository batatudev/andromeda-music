## Raport Porównawczy: Andromeda Music vs Konkurencja

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), standaryzowany pomiar jądra (/proc/smaps_rollup)*

| Metryka | Andromeda Music (Qt6) | Feishin (Electron) | Spotify (Electron) | Przewaga Andromedy |
| :--- | :---: | :---: | :---: | :--- |
| **Czas startu (Cold Startup)** | **0.182 s** | 0.407 s | 0.412 s | **Do 2.3x szybszy start** |
| **Pamięć rzeczywista (PSS)** | **224.4 MB** | 455.5 MB | 948.6 MB | **Oszczędność -231 MB (-51%), -724 MB (-76%)** |
| **Pamięć fizyczna (RSS)** | **339.8 MB** | 887.0 MB | 1657.4 MB | Niska pamięć rezydentna |
| **Średnie CPU (True Idle)** | **0.06%** | 5.16% | 4.62% | Pętla zdarzeń Qt6 uśpiona |
| **Liczba procesów systemowych** | **1** | 14 | 11 | **Brak narzutu Chromium (-13, -10 procesów)** |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 202.4 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.22 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1285.6 KB