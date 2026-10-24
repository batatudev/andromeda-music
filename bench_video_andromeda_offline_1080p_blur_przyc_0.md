======================================================================
        RAPORT WYDAJNOŚCI SYSTEMOWEJ: ANDROMEDA (VIDEO OFFLINE)
======================================================================

[1] MIKROBENCHMARKI KOMPONENTÓW I PAMIĘCI (INTERNAL):
  • Inicjalizacja 50x SongItem:       243.18 ms
  • Tworzenie 30x MediaCard (Flow):   34.18 ms
  • Pamięć trwała po 100 widżetach:   1283.58 KB
  • Zapytanie SQLite WAL (2000 w.):   0.26 ms

[2] METRYKI PROCESU LINUX / WAYLAND (VIDEO, WARMUP: 15s):
  • Czas startu aplikacji:            0.188 s
  • Średnie CPU (Cały procesor):      1.89 % (1 rdzeń: 15.15 %)
  • Szczytowe CPU (Max spike):        17.13 % (1 rdzeń: 137.01 %)
  • Średnie GPU (Łączne obciążenie):  36.09 %
      - GPU 3D / Shadery (Render):    32.64 %
      - GPU Dekoder (VA-API Video):   3.61 %
  • Prawdziwy narzut RAM (Średni PSS): 275.83 MB
  • Pamięć fizyczna (Średni RSS):     405.14 MB
  • Szczyt pamięci (Max RSS):         406.45 MB
  • Liczba procesów systemowych:      1
  • Średnia liczba wątków:            41.7

======================================================================
