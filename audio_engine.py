# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: audio_engine.py
# OPIS ZMIAN: PLIK ZDEPRECJONOWANY. Klasa PlayerEngine przeniesiona do engine/player_engine.py
# w ramach Etapu 3 dekonstrukcji. Ten plik jest pusty i bezpieczny do usunięcia.
#
# Historia migracji:
#   - engine/player_engine.py  ← główna klasa PlayerEngine (QObject, sygnały, sync A/V)
#   - engine/cache_manager.py  ← logika pobierania i cache'owania audio
#   - engine/arf_manager.py    ← ARF 3.1 (Smart Bandwidth, dynamiczna rozdzielczość)
#   - engine/yt_resolver.py    ← resolver yt-dlp, prefetch linków wideo
#
# Ten plik można bezpiecznie usunąć.

raise ImportError(
    "audio_engine.py jest zdeprecjonowany od v14.6. "
    "Użyj: from engine.player_engine import PlayerEngine"
)