import os
os.environ["QT_API"] = "pyside6"

import time
import tracemalloc
import gc
from pathlib import Path

class AndromedaInternalBenchmarks:
    """
    Testy wewnętrzne silnika i komponentów UI Andromedy w trybie headless.
    """

    @staticmethod
    def run_all_internal() -> dict:
        from PySide6.QtWidgets import QApplication, QWidget
        from core.models import Song, Album
        from ui.components.song_item import SongItem
        from ui.components.media_card import MediaCard
        from ui.widgets.flow_layout import FlowLayout
        from core.enums import MediaType
        from ui.theme_manager import theme_manager

        app = QApplication.instance()
        if not app:
            app = QApplication(["-platform", "offscreen"])

        theme_manager.reload_theme()
        results = {}

        # 1. Tworzenie 50x SongItem
        songs = [
            Song({
                "id": f"trk_{i}",
                "title": f"Benchmark Song {i}",
                "artist": "Benchmark Artist",
                "album": "Benchmark Album",
                "duration": 210,
            })
            for i in range(50)
        ]

        t_start = time.perf_counter()
        items = [SongItem(s) for s in songs]
        app.processEvents()
        t_items = (time.perf_counter() - t_start) * 1000.0
        results["song_item_50_init_ms"] = t_items

        for it in items:
            it.hide()
            it.deleteLater()
        app.processEvents()

        # 2. Tworzenie 30x MediaCard w FlowLayout
        container = QWidget()
        container.resize(1200, 800)
        flow = FlowLayout(container)

        albums = [
            Album({
                "id": f"alb_{i}",
                "name": f"Studio Album {i}",
                "artist": f"Artist {i}",
            })
            for i in range(30)
        ]

        t_start = time.perf_counter()
        cards = [MediaCard(a, MediaType.ALBUM, parent=container) for a in albums]
        for c in cards:
            flow.addWidget(c)
        app.processEvents()
        t_cards = (time.perf_counter() - t_start) * 1000.0
        results["media_card_30_flow_ms"] = t_cards

        for c in cards:
            c.hide()
            c.deleteLater()
        container.deleteLater()
        app.processEvents()

        # 3. Test wycieków pamięci
        gc.collect()
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        leak_items = [
            SongItem(Song({"id": f"leak_{i}", "title": f"Leak Test {i}", "artist": "Artist"}))
            for i in range(100)
        ]
        app.processEvents()

        for it in leak_items:
            it.hide()
            it.deleteLater()
        leak_items.clear()
        app.processEvents()
        gc.collect()

        snapshot_end = tracemalloc.take_snapshot()
        leak_diff = snapshot_end.compare_to(snapshot_start, "lineno")
        retained_kb = sum(stat.size_diff for stat in leak_diff) / 1024.0
        tracemalloc.stop()
        results["retained_ram_100_widgets_kb"] = max(0.0, retained_kb)

        # 4. Wydajność bazy SQLite WAL w RAM
        from core.paths import PathsManager
        db_path = PathsManager.get_cache_dir() / "benchmark_test.db"
        PathsManager.enable_wal_mode(db_path)
        conn = PathsManager.get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS test_lib (id TEXT PRIMARY KEY, title TEXT)")
        sample_records = [(f"id_{i}", f"Title Number {i}") for i in range(2000)]
        cursor.executemany("INSERT OR REPLACE INTO test_lib VALUES (?, ?)", sample_records)
        conn.commit()

        t_start = time.perf_counter()
        cursor.execute("SELECT id, title FROM test_lib WHERE title LIKE '%100%'")
        _ = cursor.fetchall()
        t_db = (time.perf_counter() - t_start) * 1000.0
        results["sqlite_wal_query_2000_ms"] = t_db

        conn.close()
        if db_path.exists():
            db_path.unlink()
        wal_p = Path(f"{db_path}-wal")
        if wal_p.exists():
            wal_p.unlink()
        shm_p = Path(f"{db_path}-shm")
        if shm_p.exists():
            shm_p.unlink()

        return results