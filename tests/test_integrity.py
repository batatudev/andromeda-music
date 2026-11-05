import os
os.environ["QT_API"] = "pyside6"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys
import json
import sqlite3
import tempfile
import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication

app = QApplication.instance()
if not app:
    app = QApplication(["-platform", "offscreen"])

from core.models import MediaItem, Song, Album, Artist
from engine.queue_manager import QueueManager
from core.paths import PathsManager
from core.i18n import tr, _translator
from api_client import NavidromeClient
from engine.yt_resolver import YtErrorType, classify_yt_error
import utils

class IntegrityTestSuite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_true(self, condition, test_name):
        if condition:
            self.passed += 1
            print(f"  [PASS] {test_name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {test_name}")
            self.errors.append(test_name)

    def assert_equal(self, actual, expected, test_name):
        if actual == expected:
            self.passed += 1
            print(f"  [PASS] {test_name}")
        else:
            self.failed += 1
            msg = f"{test_name} -> Oczekiwano: {expected}, Otrzymano: {actual}"
            print(f"  [FAIL] {msg}")
            self.errors.append(msg)

    def test_domain_models(self):
        print("\n--- 1. TEST MODELI DOMENOWYCH I WRAPPERÓW DTO ---")

        raw_song = {
            "id": "trk_101",
            "title": "Starlight",
            "artist": "Muse",
            "album": "Black Holes and Revelations",
            "albumId": "alb_55",
            "coverArt": "cov_99",
            "duration": 240,
            "comment": "Official video: https://www.youtube.com/watch?v=R8A0T_T9U-8",
            "starred": "2026-09-30T10:00:00Z"
        }

        song = Song(raw_song)

        self.assert_equal(song.item_id, "trk_101", "Model: mapowanie item_id")
        self.assert_equal(song.title, "Starlight", "Model: mapowanie title")
        self.assert_equal(song.artist, "Muse", "Model: mapowanie artist")
        self.assert_equal(song.album, "Black Holes and Revelations", "Model: mapowanie album")
        self.assert_equal(song.cover_id, "cov_99", "Model: priorytet cover_id")
        self.assert_equal(song.duration_sec, 240, "Model: duration_sec int cast")
        self.assert_true(song.is_starred, "Model: detekcja is_starred")

        song.set_starred(False)
        self.assert_true(not song.is_starred, "Model: zmiana set_starred(False)")
        song.set_starred(True)
        self.assert_true(song.is_starred, "Model: zmiana set_starred(True)")

        expected_yt = "https://www.youtube.com/watch?v=R8A0T_T9U-8"
        self.assert_equal(song.yt_link, expected_yt, "Model: ekstrakcja linku YouTube z pola comment")

        utils._set_yt_link_override("trk_101", "https://youtu.be/custom_override_id")
        self.assert_equal(song.yt_link, "https://youtu.be/custom_override_id", "Model: dynamiczny override linku YT")
        utils._set_yt_link_override("trk_101", None)
        self.assert_equal(song.yt_link, expected_yt, "Model: przywrócenie linku domyślnego po usunięciu override")

        album = Album({"id": "alb_1", "name": "Album Test", "song": [song]})
        self.assert_equal(album.title, "Album Test", "Model: Album fallback name do title")
        self.assert_equal(len(album.songs), 1, "Model: Album lista songs")

    def test_queue_manager_logic(self):
        print("\n--- 2. TEST SILNIKA KOLEJKI (QueueManager) ---")

        qm = QueueManager()
        s1 = Song({"id": "s1", "title": "Track 1"})
        s2 = Song({"id": "s2", "title": "Track 2"})
        s3 = Song({"id": "s3", "title": "Track 3"})
        s4 = Song({"id": "s4", "title": "Track 4"})

        qm.set_queue([s1, s2, s3, s4], start_idx=0)
        self.assert_equal(len(qm.queue), 4, "QueueManager: set_queue rozmiar")
        self.assert_equal(qm.current_song().item_id, "s1", "QueueManager: current_song indeks 0")
        self.assert_equal(qm.next_song_item().item_id, "s2", "QueueManager: next_song_item")

        advanced = qm.advance()
        self.assert_true(advanced and qm.idx == 1, "QueueManager: advance do indeksu 1")
        self.assert_equal(qm.current_song().item_id, "s2", "QueueManager: poprawność aktywnego utworu po advance")

        went_back = qm.previous()
        self.assert_true(went_back and qm.idx == 0, "QueueManager: previous do indeksu 0")

        qm.idx = 1
        qm.handle_drop(3, 0)
        self.assert_equal(qm.queue[0].item_id, "s4", "QueueManager: handle_drop przeniesienie s4 na początek")
        self.assert_equal(qm.current_song().item_id, "s2", "QueueManager: zachowanie śledzenia aktywnego utworu po Drag&Drop")

        qm.set_queue([s1, s2, s3, s4], start_idx=2)
        should_play, should_clear = qm.remove(0)
        self.assert_true(not should_play and not should_clear, "QueueManager: usunięcie utworu przed aktywnym nie zmienia odtwarzania")
        self.assert_equal(qm.idx, 1, "QueueManager: dekrementacja indeksu po usunięciu poprzednika")
        self.assert_equal(qm.current_song().item_id, "s3", "QueueManager: aktywny utwór nadal spójny")

        should_play, should_clear = qm.remove(1)
        self.assert_true(should_play and not should_clear, "QueueManager: usunięcie grającego utworu wymusza odtworzenie następcy")

        qm.set_queue([s1], start_idx=0)
        should_play, should_clear = qm.remove(0)
        self.assert_true(should_clear, "QueueManager: usunięcie jedynego utworu czyści kolejkę")

        qm.set_queue([s1, s2, s3, s4], start_idx=1)
        qm.shuffle()
        self.assert_equal(qm.idx, 0, "QueueManager: po shuffle grający utwór ma indeks 0")
        self.assert_equal(qm.current_song().item_id, "s2", "QueueManager: shuffle zachowuje grający utwór na początku")

    def test_database_and_wal_mode(self):
        print("\n--- 3. TEST POŁĄCZEŃ SQLITE I TRYBU WAL (PathsManager) ---")

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db_path = tmp.name

        try:
            PathsManager.enable_wal_mode(tmp_db_path)
            conn = PathsManager.get_db_connection(tmp_db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0].upper()
            self.assert_equal(journal_mode, "WAL", "SQLite: włączenie trwałego trybu WAL")

            cursor.execute("PRAGMA busy_timeout")
            busy_timeout = cursor.fetchone()[0]
            self.assert_equal(busy_timeout, 5000, "SQLite: pragma busy_timeout = 5000ms")

            cursor.execute("PRAGMA synchronous")
            sync_mode = cursor.fetchone()[0]
            self.assert_equal(sync_mode, 1, "SQLite: pragma synchronous = 1 (NORMAL)")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    item_id TEXT PRIMARY KEY,
                    title TEXT,
                    status TEXT,
                    added_at INTEGER,
                    file_size INTEGER
                )
            ''')
            cursor.execute(
                "INSERT INTO downloads VALUES (?, ?, ?, ?, ?)",
                ("id_001", "Song Test", "COMPLETED", 1000, 5000000)
            )
            conn.commit()

            cursor.execute("SELECT title, file_size FROM downloads WHERE item_id = ?", ("id_001",))
            row = cursor.fetchone()
            self.assert_equal(row, ("Song Test", 5000000), "SQLite: integralność zapisu i odczytu danych")

            conn.close()
        finally:
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)
            wal_file = f"{tmp_db_path}-wal"
            shm_file = f"{tmp_db_path}-shm"
            if os.path.exists(wal_file):
                os.remove(wal_file)
            if os.path.exists(shm_file):
                os.remove(shm_file)

    def test_i18n_symmetry_and_fallbacks(self):
        print("\n--- 4. TEST SPÓJNOŚCI SŁOWNIKÓW I18N (PL vs EN) ---")

        pl_path = ROOT_DIR / "lang" / "pl.json"
        en_path = ROOT_DIR / "lang" / "en.json"

        self.assert_true(pl_path.exists(), "i18n: istnienie pliku pl.json")
        self.assert_true(en_path.exists(), "i18n: istnienie pliku en.json")

        with open(pl_path, "r", encoding="utf-8") as f:
            pl_dict = json.load(f)

        with open(en_path, "r", encoding="utf-8") as f:
            en_dict = json.load(f)

        pl_keys = set(pl_dict.keys())
        en_keys = set(en_dict.keys())

        missing_in_en = pl_keys - en_keys
        missing_in_pl = en_keys - pl_keys

        self.assert_equal(missing_in_en, set(), "i18n: brakujące klucze w en.json względem pl.json")
        self.assert_equal(missing_in_pl, set(), "i18n: brakujące klucze w pl.json względem en.json")

        empty_pl = [k for k, v in pl_dict.items() if not str(v).strip()]
        empty_en = [k for k, v in en_dict.items() if not str(v).strip()]

        self.assert_equal(empty_pl, [], "i18n: brak pustych wartości w pl.json")
        self.assert_equal(empty_en, [], "i18n: brak pustych wartości w en.json")

        _translator.load_language("pl")
        self.assert_equal(tr("player.play", "Fallback"), pl_dict.get("player.play"), "i18n: translacja klucza w języku PL")
        self.assert_equal(tr("non.existent.key.xyz", "AwaryjnyTekst"), "AwaryjnyTekst", "i18n: poprawność fallbacku dla nieistniejącego klucza")

    def test_subsonic_auth_protocol(self):
        print("\n--- 5. TEST PROTOKOŁU AUTORYZACJI SUBSONIC (MD5 SALT+TOKEN) ---")

        client = NavidromeClient("http://localhost:4533", "testuser", "securepass123")
        params = client._get_auth_params()

        self.assert_equal(params.get("u"), "testuser", "Subsonic API: parametr 'u' (login)")
        self.assert_equal(params.get("f"), "json", "Subsonic API: format odpowiedzi JSON")
        self.assert_equal(params.get("v"), "1.16.1", "Subsonic API: wersja API 1.16.1")

        salt = params.get("s")
        token = params.get("t")

        self.assert_true(bool(salt and len(salt) == 6), "Subsonic API: sól 's' o długości 6 znaków")

        expected_token = hashlib.md5(("securepass123" + salt).encode("utf-8")).hexdigest()
        self.assert_equal(token, expected_token, "Subsonic API: token 't' zgodny ze standardem md5(password + salt)")

    def test_yt_error_classifier(self):
        print("\n--- 6. TEST KLASYFIKATORA BŁĘDÓW YOUTUBE (YtErrorClassifier) ---")

        self.assert_equal(
            classify_yt_error("HTTP Error 429: Too Many Requests"),
            YtErrorType.RATE_LIMIT,
            "YtClassifier: wykrywanie błędu HTTP 429 (Rate Limit)"
        )
        self.assert_equal(
            classify_yt_error("ERROR: Sign in to confirm you're not a bot. This helps protect our community."),
            YtErrorType.BOT_CHECK,
            "YtClassifier: wykrywanie weryfikacji bota (BotGuard / Cloudflare)"
        )
        self.assert_equal(
            classify_yt_error("ERROR: [youtube] 00000000000: This video is unavailable"),
            YtErrorType.UNAVAILABLE,
            "YtClassifier: wykrywanie wideo niedostępnego ('This video is unavailable')"
        )
        self.assert_equal(
            classify_yt_error("ERROR: [youtube] Video unavailable. This video is private."),
            YtErrorType.UNAVAILABLE,
            "YtClassifier: wykrywanie wideo prywatnego / zablokowanego"
        )
        self.assert_equal(
            classify_yt_error("ERROR: Sign in to confirm your age. This video may be inappropriate for some users."),
            YtErrorType.AGE_RESTRICTED,
            "YtClassifier: wykrywanie ograniczenia wiekowego"
        )
        self.assert_equal(
            classify_yt_error("urllib.error.URLError: <urlopen error timed out>"),
            YtErrorType.NETWORK_TIMEOUT,
            "YtClassifier: wykrywanie przekroczenia limitu czasu sieci (Timeout)"
        )
        self.assert_equal(
            classify_yt_error("Some completely unexpected generic exception"),
            YtErrorType.UNKNOWN,
            "YtClassifier: poprawny fallback dla nieznanych błędów"
        )

    def run_all(self):
        print("================================================================")
        print("     ANDROMEDA MUSIC — PAKIET TESTÓW INTEGRALNOŚCI (v14.20+)     ")
        print("================================================================")

        self.test_domain_models()
        self.test_queue_manager_logic()
        self.test_database_and_wal_mode()
        self.test_i18n_symmetry_and_fallbacks()
        self.test_subsonic_auth_protocol()
        self.test_yt_error_classifier()

        print("\n================================================================")
        print(f" WYNIKI: Wszystkich testów: {self.passed + self.failed} | Zaliczono: {self.passed} | Błędy: {self.failed}")
        print("================================================================")

        if self.failed > 0:
            print("\nBŁĘDY DO POPRAWY:")
            for err in self.errors:
                print(f"  - {err}")
            return 1
        return 0

if __name__ == "__main__":
    suite = IntegrityTestSuite()
    sys.exit(suite.run_all())