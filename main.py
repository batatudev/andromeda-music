# WERSJA PROJEKTU: 14.7
# MODYFIKOWANY PLIK: main.py
# OPIS ZMIAN: Etap 4 Dekonstrukcji – main.py zdegradowany do roli cienkiego
# proxy uruchamiającego aplikację przez app.py. Logika przeniesiona do:
#   - ui/main_window.py  (klasa MainWindow)
#   - engine/watchdog.py (Strażnik Maski)
#   - core/telemetry_service.py (Czarna Skrzynka)
#   - app.py (korzeń uruchomieniowy)

import os
os.environ["QT_API"] = "pyside6"
os.environ["PULSE_PROP_application.name"] = "Navidrome Player"
os.environ["PULSE_PROP_application.icon_name"] = "multimedia-audio-player"
os.environ["PULSE_PROP_media.role"] = "music"

from app import run

if __name__ == "__main__":
    run()