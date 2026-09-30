import os
os.environ["QT_API"] = "pyside6"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys
import time
import tracemalloc
import gc
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtCore import Qt

app = QApplication.instance()
if not app:
    app = QApplication(["-platform", "offscreen"])

from ui.theme_manager import theme_manager
theme_manager.reload_theme()

from core.models import Song, Album
from ui.components.song_item import SongItem
from ui.components.media_card import MediaCard
from ui.widgets.flow_layout import FlowLayout
from core.enums import MediaType


class PerformanceBenchmarkSuite:
    def __init__(self):
        self.results = []

    def log_metric(self, name, duration_ms, budget_ms, details="", is_baseline=False):
        reset = "\033[0m"
        if is_baseline:
            status = "INFO"
            color = "\033[94m"
            budget_str = "(Pomiar referencyjny)"
        else:
            status = "OK"
            if duration_ms > budget_ms:
                status = "CRITICAL BOTTLENECK"
            color = "\033[92m" if status == "OK" else "\033[91m"
            budget_str = f"(Budżet: {budget_ms:.1f} ms)"
            self.results.append((name, duration_ms, budget_ms, status, details))

        print(f"  {color}[{status}]{reset} {name}: {duration_ms:.2f} ms {budget_str} {details}")

    def benchmark_song_item_generation(self):
        print("\n--- 1. BENCHMARK: TWORZENIE WIDŻETÓW SongItem (Widget Thrashing & CSS) ---")

        dummy_container = QWidget()
        dummy_song = Song({"id": "warmup", "title": "Warmup Song", "artist": "Warmup Artist"})
        dummy_item = SongItem(dummy_song, parent=dummy_container)
        dummy_item.deleteLater()
        dummy_container.deleteLater()
        app.processEvents()

        songs_first_chunk = [
            Song({
                "id": f"song_chunk_{i}",
                "title": f"Visible Song {i}",
                "artist": "Artist Name",
                "album": "Album Title",
                "duration": 200 + i
            })
            for i in range(12)
        ]

        container_chunk = QWidget()
        t_start = time.perf_counter_ns()
        _ = [SongItem(s, parent=container_chunk) for s in songs_first_chunk]
        t_chunk = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric(
            "Renderowanie pierwszej widocznej paczki (12x SongItem - First Frame)",
            t_chunk,
            100.0,
            f"Średnio: {t_chunk / 12.0:.2f} ms/wiersz"
        )

        songs = [
            Song({
                "id": f"song_{i}",
                "title": f"Test Title Number {i}",
                "artist": "Test Artist Name",
                "album": "Benchmark Album Title",
                "duration": 180 + i,
                "starred": "True" if i % 2 == 0 else None
            })
            for i in range(50)
        ]

        container = QWidget()
        layout = QVBoxLayout(container)
        container.setUpdatesEnabled(True)

        t_start = time.perf_counter_ns()
        items = [SongItem(s, parent=container) for s in songs]
        t_init = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric(
            "Instancjonowanie pełnej paczki 50x SongItem (~900 kontrolek C++)",
            t_init,
            400.0,
            f"Średnio: {t_init / 50.0:.2f} ms/wiersz"
        )

        t_start = time.perf_counter_ns()
        for it in items:
            layout.addWidget(it)
        app.processEvents()
        t_layout = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric("Dodanie do Layoutu + processEvents (Przeliczenie CSS i geometrii)", t_layout, 60.0)

        t_start = time.perf_counter_ns()
        while layout.count():
            w_item = layout.takeAt(0)
            if w_item.widget():
                w_item.widget().hide()
                w_item.widget().deleteLater()
        app.processEvents()
        t_cleanup = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric("Czyszczenie 50x SongItem (hide + deleteLater + processEvents)", t_cleanup, 25.0)

    def benchmark_media_card_flow(self):
        print("\n--- 2. BENCHMARK: TWORZENIE MediaCard W FlowLayout ---")

        albums = [
            Album({
                "id": f"alb_{i}",
                "name": f"Studio Album {i}",
                "artist": f"Famous Artist {i % 5}",
                "year": 2020 + (i % 6)
            })
            for i in range(30)
        ]

        container = QWidget()
        container.resize(1200, 800)
        flow = FlowLayout(container)

        t_start = time.perf_counter_ns()
        cards = [MediaCard(a, MediaType.ALBUM, parent=container) for a in albums]
        for c in cards:
            flow.addWidget(c)
        app.processEvents()
        t_total = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric(
            "Utworzenie 30x MediaCard + FlowLayout compute + CSS",
            t_total,
            100.0,
            f"Średnio: {t_total / 30.0:.2f} ms/kafelek"
        )

        while flow.count():
            item = flow.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        app.processEvents()

    def benchmark_pixmap_scaling_cpu_cost(self):
        print("\n--- 3. BENCHMARK: KOSZT SKALOWANIA QPixmap NA CPU (Wątek GUI) ---")

        large_pixmap = QPixmap(1000, 1000)
        large_pixmap.fill(QColor(40, 40, 40))
        painter = QPainter(large_pixmap)
        painter.setPen(QColor(255, 0, 0))
        painter.drawRect(50, 50, 900, 900)
        painter.end()

        t_start = time.perf_counter_ns()
        for _ in range(20):
            _ = large_pixmap.scaled(200, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        t_smooth = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric(
            "20x Skalowanie 1000x1000 (Qt.SmoothTransformation na GUI CPU)",
            t_smooth,
            40.0,
            f"Średnio: {t_smooth / 20.0:.2f} ms/okładkę"
        )

        t_start = time.perf_counter_ns()
        for _ in range(20):
            _ = large_pixmap.scaled(200, 200, Qt.KeepAspectRatioByExpanding, Qt.FastTransformation)
        t_fast = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric(
            "20x Skalowanie 1000x1000 (Qt.FastTransformation)",
            t_fast,
            10.0,
            f"Średnio: {t_fast / 20.0:.2f} ms/okładkę"
        )

    def benchmark_network_concurrency(self):
        print("\n--- 4. BENCHMARK: MODEL ZAPYTAŃ SIECIOWYCH (Sekwencyjny vs Współbieżny) ---")

        def mock_subsonic_request(endpoint_name):
            time.sleep(0.080)
            return {"endpoint": endpoint_name, "status": "ok"}

        endpoints = ["getStarred", "getRandomAlbums", "getRandomSongs", "getArtists"]

        t_start = time.perf_counter_ns()
        _ = [mock_subsonic_request(ep) for ep in endpoints]
        t_seq = (time.perf_counter_ns() - t_start) / 1_000_000.0
        self.log_metric(
            "Stary model sekwencyjny 4x API (Punkt odniesienia)",
            t_seq,
            100.0,
            f"Suma opóźnień RTT: {t_seq:.1f} ms",
            is_baseline=True
        )

        t_start = time.perf_counter_ns()
        with ThreadPoolExecutor(max_workers=4) as executor:
            _ = list(executor.map(mock_subsonic_request, endpoints))
        t_par = (time.perf_counter_ns() - t_start) / 1_000_000.0
        speedup = t_seq / t_par if t_par > 0 else 1.0
        self.log_metric(
            "Zoptymalizowany model równoległy 4x API (Aktywny w HomeView)",
            t_par,
            100.0,
            f"Przyspieszenie: {speedup:.1f}x"
        )

    def benchmark_ram_leak_profile(self):
        print("\n--- 5. BENCHMARK: PROFIL PAMIĘCI RAM I WYKRYWANIE WYCIEKÓW (tracemalloc) ---")

        gc.collect()
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        container = QWidget()
        layout = QVBoxLayout(container)
        items = []

        for i in range(100):
            s = Song({"id": f"mem_{i}", "title": f"RAM Test Track {i}", "artist": "RAM Artist"})
            item = SongItem(s, parent=container)
            layout.addWidget(item)
            items.append(item)
        app.processEvents()

        snapshot_peak = tracemalloc.take_snapshot()
        peak_diff = snapshot_peak.compare_to(snapshot_start, "lineno")
        peak_kb = sum(stat.size_diff for stat in peak_diff) / 1024.0

        for it in items:
            it.hide()
            it.deleteLater()
        items.clear()

        while layout.count():
            item = layout.takeAt(0)

        app.processEvents()
        app.sendPostedEvents(None, 52)
        gc.collect()

        snapshot_end = tracemalloc.take_snapshot()
        leak_diff = snapshot_end.compare_to(snapshot_start, "lineno")
        retained_kb = sum(stat.size_diff for stat in leak_diff) / 1024.0

        tracemalloc.stop()

        self.log_metric("Alokacja pamięci dla 100x SongItem", peak_kb, 5000.0, f"+{peak_kb:.1f} KB w RAM")
        self.log_metric("Pamięć trwała po usunięciu (Retained RAM)", retained_kb, 150.0, f"Pozostało w RAM: {retained_kb:.1f} KB")

    def run_all(self):
        print("================================================================")
        print("    ANDROMEDA MUSIC — PAKIET BENCHMARKÓW WYDAJNOŚCI (v14.20+)   ")
        print("================================================================")

        self.benchmark_song_item_generation()
        self.benchmark_media_card_flow()
        self.benchmark_pixmap_scaling_cpu_cost()
        self.benchmark_network_concurrency()
        self.benchmark_ram_leak_profile()

        print("\n================================================================")
        print(" PODSUMOWANIE ANALIZY WYDAJNOŚCIOWEJ")
        print("================================================================")
        bottlenecks = [r for r in self.results if r[3] == "CRITICAL BOTTLENECK"]
        if bottlenecks:
            print(f"Wykryto {len(bottlenecks)} krytycznych wąskich gardeł wpływających na zacięcia:")
            for b in bottlenecks:
                print(f"  * {b[0]}: {b[1]:.2f} ms (Przekroczenie budżetu o {b[1] - b[2]:.2f} ms)")
        else:
            print("\033[92m[SUKCES] Wszystkie metryki mieszczą się w budżecie produkcyjnym!\033[0m")
            print("Interfejs i silnik aplikacji osiągnęły pełną płynność działania.")


if __name__ == "__main__":
    suite = PerformanceBenchmarkSuite()
    suite.run_all()