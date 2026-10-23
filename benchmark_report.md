## Raport Porównawczy: Andromeda Music vs Konkurencja (Audio Playback)

*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), 2 utwory ('Przyszłość' + 'MIĘSO', 120s z przełączeniem MPRIS w 60s), standaryzowany pomiar jądra (/proc/smaps_rollup)*

| Metryka | Andromeda (Qt6) | Feishin (Electron) | Spotify (Electron) | Brave (Chromium Web) | Firefox (Gecko Web) | Przewaga Andromedy |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Czas startu (Cold Startup)** | **0.132 s** | 0.285 s | 0.331 s | 0.095 s | 0.128 s | **Do 2.5x szybszy start** |
| **Pamięć rzeczywista (PSS)** | **228.5 MB** | 489.3 MB | 913.8 MB | 522.8 MB | 814.5 MB | **Oszczędność -261 MB (-53%), -685 MB (-75%), -294 MB (-56%), -586 MB (-72%)** |
| **Pamięć fizyczna (RSS)** | **340.7 MB** | 894.2 MB | 1553.3 MB | 1573.0 MB | 1458.9 MB | Niska pamięć rezydentna |
| **Średnie CPU (Odtwarzanie Audio)** | **10.49%** | 19.40% | 36.45% | 18.06% | 24.77% | Natywny potok audio PipeWire |
| **Szczytowe CPU (Max Spike)** | **25.47%** | 57.27% | 190.90% | 135.20% | 162.43% | Płynne przełączenie bez zacięć |
| **Liczba procesów systemowych** | **1** | 14 | 11 | 14 | 10 | **Brak narzutu przeglądarek (-13, -10, -13, -9 procesów)** |

### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:

- **Inicjalizacja 50 utworów:** 131.4 ms
- **Zapytanie bazy SQLite WAL (2000 utworów):** 0.18 ms
- **Pamięć trwała po 100 widżetach (Retained RAM):** 1286.6 KB