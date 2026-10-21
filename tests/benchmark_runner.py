import os
os.environ["QT_API"] = "pyside6"

import sys
import time
import shutil
import subprocess
import signal
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CLK_TCK = os.sysconf(os.sysconf_names.get('SC_CLK_TCK', 'SC_CLK_TCK')) or 100


class LinuxProcessMonitor:
    """
    Niezależny próbnik procesów oparty o jądro Linuksa (/proc).
    Wykrywa procesy potomne, wątki oraz grupy procesów PGID
    (niezbędne do pełnego pomiaru architektury wieloprocesowej Electron/Chromium).
    """

    @staticmethod
    def get_process_tree_pids(root_pids: set, pgid: int = None) -> set:
        found_pids = set(root_pids)

        def scan_children(p):
            task_dir = Path(f"/proc/{p}/task")
            if task_dir.exists():
                try:
                    for tid in task_dir.iterdir():
                        children_file = tid / "children"
                        if children_file.exists():
                            content = children_file.read_text().strip()
                            if content:
                                for cpid_str in content.split():
                                    cpid = int(cpid_str)
                                    if cpid not in found_pids:
                                        found_pids.add(cpid)
                                        scan_children(cpid)
                except (PermissionError, ProcessLookupError, FileNotFoundError):
                    pass

        for rp in list(found_pids):
            scan_children(rp)

        target_pgid = pgid
        if target_pgid is not None:
            proc_root = Path("/proc")
            try:
                for entry in proc_root.iterdir():
                    if entry.name.isdigit():
                        pid = int(entry.name)
                        stat_file = entry / "stat"
                        if stat_file.exists():
                            try:
                                content = stat_file.read_text()
                                rparen_idx = content.rfind(")")
                                if rparen_idx != -1:
                                    fields = content[rparen_idx + 2:].split()
                                    proc_pgrp = int(fields[2])
                                    if proc_pgrp == target_pgid:
                                        found_pids.add(pid)
                            except (PermissionError, ProcessLookupError, FileNotFoundError, IndexError):
                                pass
            except (PermissionError, FileNotFoundError):
                pass

        return found_pids

    @staticmethod
    def get_process_memory_kb(pids: set) -> dict:
        total_rss_kb = 0
        total_pss_kb = 0
        total_private_dirty_kb = 0

        for pid in pids:
            smaps_rollup = Path(f"/proc/{pid}/smaps_rollup")
            if smaps_rollup.exists():
                try:
                    with open(smaps_rollup, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("Rss:"):
                                total_rss_kb += int(line.split()[1])
                            elif line.startswith("Pss:"):
                                total_pss_kb += int(line.split()[1])
                            elif line.startswith("Private_Dirty:"):
                                total_private_dirty_kb += int(line.split()[1])
                    continue
                except (PermissionError, ProcessLookupError, FileNotFoundError):
                    pass

            status_file = Path(f"/proc/{pid}/status")
            if status_file.exists():
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                total_rss_kb += int(line.split()[1])
                                total_pss_kb += int(line.split()[1])
                except (PermissionError, ProcessLookupError, FileNotFoundError):
                    pass

        return {
            "rss_mb": total_rss_kb / 1024.0,
            "pss_mb": total_pss_kb / 1024.0,
            "private_dirty_mb": total_private_dirty_kb / 1024.0,
        }

    @staticmethod
    def get_process_cpu_ticks(pids: set) -> int:
        total_ticks = 0
        for pid in pids:
            stat_file = Path(f"/proc/{pid}/stat")
            if stat_file.exists():
                try:
                    content = stat_file.read_text()
                    rparen_idx = content.rfind(")")
                    if rparen_idx != -1:
                        fields = content[rparen_idx + 2:].split()
                        utime = int(fields[11])
                        stime = int(fields[12])
                        total_ticks += utime + stime
                except (PermissionError, ProcessLookupError, FileNotFoundError, IndexError):
                    pass
        return total_ticks

    @staticmethod
    def count_threads(pids: set) -> int:
        threads = 0
        for pid in pids:
            task_dir = Path(f"/proc/{pid}/task")
            if task_dir.exists():
                try:
                    threads += len(list(task_dir.iterdir()))
                except (PermissionError, ProcessLookupError, FileNotFoundError):
                    threads += 1
        return max(1, threads)


class TargetAppLocator:
    """
    Automatycznie wykrywa polecenia uruchomieniowe (natywne, Flatpak, AppImage).
    """

    @staticmethod
    def resolve_app(target_name: str, custom_bin: str = None) -> tuple:
        if custom_bin:
            return [custom_bin], False, None

        if target_name == "andromeda":
            return [sys.executable, str(ROOT_DIR / "main.py")], False, None

        flatpak_bin = shutil.which("flatpak")

        if target_name == "feishin":
            if flatpak_bin:
                try:
                    res = subprocess.run([flatpak_bin, "list", "--app"], capture_output=True, text=True)
                    if "org.jeffvli.feishin" in res.stdout:
                        return [flatpak_bin, "run", "org.jeffvli.feishin"], True, "org.jeffvli.feishin"
                except Exception:
                    pass

            bin_path = shutil.which("feishin")
            if bin_path:
                return [bin_path], False, None

            common_locations = [
                Path.home() / "Applications" / "feishin.AppImage",
                Path.home() / ".local" / "bin" / "feishin",
                Path("/usr/bin/feishin"),
                Path("/opt/Feishin/feishin")
            ]
            for loc in common_locations:
                if loc.exists() and os.access(loc, os.X_OK):
                    return [str(loc)], False, None

        if target_name == "spotify":
            if flatpak_bin:
                try:
                    res = subprocess.run([flatpak_bin, "list", "--app"], capture_output=True, text=True)
                    if "com.spotify.Client" in res.stdout:
                        return [flatpak_bin, "run", "com.spotify.Client"], True, "com.spotify.Client"
                except Exception:
                    pass

            bin_path = shutil.which("spotify")
            if bin_path:
                return [bin_path], False, None

            common_locations = [
                Path("/usr/bin/spotify"),
                Path.home() / ".local" / "bin" / "spotify"
            ]
            for loc in common_locations:
                if loc.exists() and os.access(loc, os.X_OK):
                    return [str(loc)], False, None

        return None, False, None


class AndromedaInternalBenchmarks:
    """
    Testy wewnętrzne silnika i komponentów UI w trybie headless.
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
        import tracemalloc
        import gc

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


class LiveProcessBenchmark:
    """
    Uruchamia docelowy program (w tym kontenery Flatpak),
    monitoruje zużycie zasobów całego drzewa procesów i dba o czyste zamykanie.
    """

    def __init__(
        self,
        target_name: str,
        app_cmd: list,
        is_flatpak: bool = False,
        flatpak_app_id: str = None,
        duration_sec: int = 15,
        warmup_sec: int = 15,
        scenario: str = "idle"
    ):
        self.target_name = target_name
        self.app_cmd = app_cmd
        self.is_flatpak = is_flatpak
        self.flatpak_app_id = flatpak_app_id
        self.duration_sec = duration_sec
        self.warmup_sec = warmup_sec
        self.scenario = scenario

    def _get_flatpak_child_pids(self) -> set:
        if not self.is_flatpak or not self.flatpak_app_id:
            return set()
        child_pids = set()
        try:
            res = subprocess.run(
                ["flatpak", "ps", "--columns=application,child-pid"],
                capture_output=True,
                text=True,
                timeout=2
            )
            for line in res.stdout.strip().splitlines():
                if self.flatpak_app_id in line:
                    parts = line.split()
                    if len(parts) >= 2 and parts[-1].isdigit():
                        child_pids.add(int(parts[-1]))
        except Exception:
            pass
        return child_pids

    def execute(self) -> dict:
        # Czysty start: upewnij się, że żadna instancja Flatpak nie wisi w tle
        if self.is_flatpak and self.flatpak_app_id:
            subprocess.run(
                ["flatpak", "kill", self.flatpak_app_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            for _ in range(15):
                if not self._get_flatpak_child_pids():
                    break
                time.sleep(0.2)

        t_before_launch = time.perf_counter()

        proc = subprocess.Popen(
            self.app_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )

        root_pid = proc.pid
        root_pgid = os.getpgid(root_pid)
        startup_time_sec = None
        samples = []

        try:
            # 1. Krok: Pomiar czasu startu (z tolerancją dla Flatpak launcherów)
            flatpak_pids = set()
            for _ in range(300):
                if self.is_flatpak:
                    flatpak_pids = self._get_flatpak_child_pids()
                    if not flatpak_pids and proc.poll() is not None and proc.returncode != 0:
                        raise RuntimeError(f"Proces {self.target_name} zakończył się błędem (kod: {proc.returncode}).")
                else:
                    if proc.poll() is not None:
                        raise RuntimeError(f"Proces {self.target_name} zakończył się przedwcześnie.")

                seed_pids = set(flatpak_pids)
                seed_pids.add(root_pid)

                pids = LinuxProcessMonitor.get_process_tree_pids(seed_pids, root_pgid)
                mem = LinuxProcessMonitor.get_process_memory_kb(pids)

                if mem["rss_mb"] > 25.0:
                    startup_time_sec = time.perf_counter() - t_before_launch
                    break
                time.sleep(0.02)

            if startup_time_sec is None:
                startup_time_sec = time.perf_counter() - t_before_launch

            if self.warmup_sec > 0:
                print(f"[INFO] [{self.target_name.upper()}] Faza rozgrzewki: oczekiwanie {self.warmup_sec}s...")
                time.sleep(self.warmup_sec)

            print(f"[INFO] [{self.target_name.upper()}] Rozpoczynam próbkowanie metryk ({self.duration_sec}s)...")
            start_time = time.perf_counter()
            prev_ticks = 0
            prev_tick_time = start_time

            end_loop_time = time.perf_counter() + self.duration_sec
            while time.perf_counter() < end_loop_time:
                if self.is_flatpak:
                    cur_pids = self._get_flatpak_child_pids()
                    if not cur_pids and proc.poll() is not None:
                        break
                    if cur_pids:
                        flatpak_pids.update(cur_pids)
                else:
                    if proc.poll() is not None:
                        break

                now = time.perf_counter()
                dt = now - prev_tick_time

                seed_pids = set(flatpak_pids)
                seed_pids.add(root_pid)

                pids = LinuxProcessMonitor.get_process_tree_pids(seed_pids, root_pgid)
                mem = LinuxProcessMonitor.get_process_memory_kb(pids)
                current_ticks = LinuxProcessMonitor.get_process_cpu_ticks(pids)
                thread_count = LinuxProcessMonitor.count_threads(pids)

                if prev_ticks > 0 and dt > 0.1:
                    tick_diff = current_ticks - prev_ticks
                    cpu_percent = (tick_diff / CLK_TCK) / dt * 100.0
                else:
                    cpu_percent = 0.0

                prev_ticks = current_ticks
                prev_tick_time = now

                samples.append({
                    "time_offset": round(now - start_time, 2),
                    "cpu_percent": round(max(0.0, cpu_percent), 2),
                    "pss_mb": round(mem["pss_mb"], 2),
                    "rss_mb": round(mem["rss_mb"], 2),
                    "private_dirty_mb": round(mem["private_dirty_mb"], 2),
                    "thread_count": thread_count,
                    "process_count": len(pids),
                })
                time.sleep(0.5)

        finally:
            if self.is_flatpak and self.flatpak_app_id:
                subprocess.run(
                    ["flatpak", "kill", self.flatpak_app_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            try:
                os.killpg(root_pgid, signal.SIGTERM)
                proc.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(root_pgid, signal.SIGKILL)
                except Exception:
                    pass

        if not samples:
            return {}

        avg_cpu = sum(s["cpu_percent"] for s in samples) / len(samples)
        max_cpu = max(s["cpu_percent"] for s in samples)
        avg_pss = sum(s["pss_mb"] for s in samples) / len(samples)
        max_pss = max(s["pss_mb"] for s in samples)
        avg_rss = sum(s["rss_mb"] for s in samples) / len(samples)
        max_rss = max(s["rss_mb"] for s in samples)
        avg_threads = sum(s["thread_count"] for s in samples) / len(samples)
        max_processes = max(s["process_count"] for s in samples)

        return {
            "target": self.target_name,
            "scenario": self.scenario,
            "warmup_sec": self.warmup_sec,
            "duration_sec": self.duration_sec,
            "startup_time_sec": round(startup_time_sec, 3),
            "avg_cpu_percent": round(avg_cpu, 2),
            "max_cpu_percent": round(max_cpu, 2),
            "avg_pss_mb": round(avg_pss, 2),
            "max_pss_mb": round(max_pss, 2),
            "avg_rss_mb": round(avg_rss, 2),
            "max_rss_mb": round(max_rss, 2),
            "avg_threads": round(avg_threads, 1),
            "max_processes": max_processes,
            "samples": samples,
        }


class BenchmarkReporter:
    """
    Formatuje i generuje zestawienia porównawcze w terminalu oraz plikach Markdown.
    """

    @staticmethod
    def print_terminal_summary(internal_data: dict, live_data: dict):
        target = live_data.get('target', 'Aplikacja').upper() if live_data else "ANDROMEDA"
        print("\n" + "=" * 65)
        print(f"        RAPORT WYDAJNOŚCI SYSTEMOWEJ: {target}")
        print("=" * 65)

        if internal_data:
            print("\n[1] MIKROBENCHMARKI KOMPONENTÓW I PAMIĘCI (INTERNAL):")
            print(f"  • Inicjalizacja 50x SongItem:       {internal_data.get('song_item_50_init_ms', 0):.2f} ms")
            print(f"  • Tworzenie 30x MediaCard (Flow):   {internal_data.get('media_card_30_flow_ms', 0):.2f} ms")
            print(f"  • Pamięć trwała po 100 widżetach:   {internal_data.get('retained_ram_100_widgets_kb', 0):.2f} KB")
            print(f"  • Zapytanie SQLite WAL (2000 w.):   {internal_data.get('sqlite_wal_query_2000_ms', 0):.2f} ms")

        if live_data:
            scenario_name = live_data.get('scenario', 'idle').upper()
            warmup_val = live_data.get('warmup_sec', 0)
            print(f"\n[2] METRYKI PROCESU LINUX / WAYLAND ({scenario_name}, WARMUP: {warmup_val}s):")
            print(f"  • Czas startu aplikacji:            {live_data.get('startup_time_sec', 0):.3f} s")
            print(f"  • Prawdziwy narzut RAM (Średni PSS): {live_data.get('avg_pss_mb', 0):.2f} MB")
            print(f"  • Pamięć fizyczna (Średni RSS):     {live_data.get('avg_rss_mb', 0):.2f} MB")
            print(f"  • Szczyt pamięci (Max RSS):         {live_data.get('max_rss_mb', 0):.2f} MB")
            print(f"  • Średnie obciążenie CPU:           {live_data.get('avg_cpu_percent', 0):.2f} %")
            print(f"  • Liczba procesów systemowych:      {live_data.get('max_processes', 1)}")
            print(f"  • Średnia liczba wątków:            {live_data.get('avg_threads', 0)}")

        print("\n" + "=" * 65 + "\n")

    @staticmethod
    def print_multi_comparison_terminal(results_map: dict):
        print("\n" + "=" * 90)
        print("          ZESTAWIENIE PORÓWNAWCZE WYDAJNOŚCI I ZASOBÓW (LINUX / WAYLAND)")
        print("=" * 90)

        header = f"{'Metryka':<32}"
        for name in results_map.keys():
            header += f" | {name.capitalize():<16}"
        print(header)
        print("-" * 90)

        def print_row(label, key, unit=""):
            row = f"{label:<32}"
            for data in results_map.values():
                val = data.get(key, "-")
                if isinstance(val, float):
                    val_str = f"{val:.2f} {unit}".strip()
                elif isinstance(val, int):
                    val_str = f"{val} {unit}".strip()
                else:
                    val_str = str(val)
                row += f" | {val_str:<16}"
            print(row)

        print_row("Czas startu (Cold Startup)", "startup_time_sec", "s")
        print_row("Pamięć rzeczywista (PSS)", "avg_pss_mb", "MB")
        print_row("Pamięć fizyczna (RSS)", "avg_rss_mb", "MB")
        print_row("Średnie CPU (True Idle)", "avg_cpu_percent", "%")
        print_row("Liczba procesów systemowych", "max_processes")
        print("=" * 90 + "\n")

    @staticmethod
    def generate_multi_comparison_markdown(results_map: dict, internal_data: dict = None) -> str:
        md = []
        md.append("## Raport Porównawczy: Andromeda Music vs Konkurencja\n")
        md.append("*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), standaryzowany pomiar jądra (/proc/smaps_rollup)*\n")

        headers = ["Metryka", "Andromeda Music (Qt6)"]
        for target in results_map.keys():
            if target != "andromeda":
                tech = "Electron" if target in ["feishin", "spotify"] else "Natywna"
                headers.append(f"{target.capitalize()} ({tech})")
        headers.append("Przewaga Andromedy")

        md.append("| " + " | ".join(headers) + " |")
        md.append("| " + " | ".join([":---" if i == 0 else (":---:" if i < len(headers) - 1 else ":---") for i in range(len(headers))]) + " |")

        a_data = results_map.get("andromeda", {})
        a_start = a_data.get("startup_time_sec", 0)
        a_pss = a_data.get("avg_pss_mb", 0)
        a_rss = a_data.get("avg_rss_mb", 0)
        a_cpu = a_data.get("avg_cpu_percent", 0)
        a_procs = a_data.get("max_processes", 1)

        # 1. Start time
        row_start = ["**Czas startu (Cold Startup)**", f"**{a_start:.3f} s**"]
        start_ratios = []
        for t, d in results_map.items():
            if t != "andromeda":
                s_val = d.get("startup_time_sec", 0)
                row_start.append(f"{s_val:.3f} s")
                if a_start > 0:
                    start_ratios.append(f"{s_val / a_start:.1f}x")
        diff_start_str = f"**Do {max(start_ratios, default='-')} szybszy start**" if start_ratios else "-"
        row_start.append(diff_start_str)
        md.append("| " + " | ".join(row_start) + " |")

        # 2. PSS
        row_pss = ["**Pamięć rzeczywista (PSS)**", f"**{a_pss:.1f} MB**"]
        pss_savings = []
        for t, d in results_map.items():
            if t != "andromeda":
                pss_val = d.get("avg_pss_mb", 0)
                row_pss.append(f"{pss_val:.1f} MB")
                diff = pss_val - a_pss
                pct = (diff / pss_val * 100) if pss_val > 0 else 0
                pss_savings.append(f"-{diff:.0f} MB (-{pct:.0f}%)")
        row_pss.append(f"**Oszczędność {', '.join(pss_savings)}**" if pss_savings else "-")
        md.append("| " + " | ".join(row_pss) + " |")

        # 3. RSS
        row_rss = ["**Pamięć fizyczna (RSS)**", f"**{a_rss:.1f} MB**"]
        for t, d in results_map.items():
            if t != "andromeda":
                row_rss.append(f"{d.get('avg_rss_mb', 0):.1f} MB")
        row_rss.append("Niska pamięć rezydentna")
        md.append("| " + " | ".join(row_rss) + " |")

        # 4. CPU
        row_cpu = ["**Średnie CPU (True Idle)**", f"**{a_cpu:.2f}%**"]
        for t, d in results_map.items():
            if t != "andromeda":
                row_cpu.append(f"{d.get('avg_cpu_percent', 0):.2f}%")
        row_cpu.append("Pętla zdarzeń Qt6 uśpiona")
        md.append("| " + " | ".join(row_cpu) + " |")

        # 5. Processes
        row_proc = ["**Liczba procesów systemowych**", f"**{a_procs}**"]
        proc_diffs = []
        for t, d in results_map.items():
            if t != "andromeda":
                p_val = d.get("max_processes", 1)
                row_proc.append(f"{p_val}")
                proc_diffs.append(f"-{p_val - a_procs}")
        row_proc.append(f"**Brak narzutu Chromium ({', '.join(proc_diffs)} procesów)**" if proc_diffs else "-")
        md.append("| " + " | ".join(row_proc) + " |")

        if internal_data:
            md.append("\n### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:\n")
            md.append(f"- **Inicjalizacja 50 utworów:** {internal_data.get('song_item_50_init_ms', 0):.1f} ms")
            md.append(f"- **Zapytanie bazy SQLite WAL (2000 utworów):** {internal_data.get('sqlite_wal_query_2000_ms', 0):.2f} ms")
            md.append(f"- **Pamięć trwała po 100 widżetach (Retained RAM):** {internal_data.get('retained_ram_100_widgets_kb', 0):.1f} KB")

        return "\n".join(md)

    @staticmethod
    def export_csv(data: dict, output_file: Path):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        samples = data.get("samples", [])
        if not samples:
            return
        keys = list(samples[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            import csv
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(samples)


def main():
    parser = argparse.ArgumentParser(description="Andromeda Music Benchmark & Multi-Comparison Runner")
    parser.add_argument(
        "--target",
        choices=["andromeda", "feishin", "spotify", "compare"],
        default="compare",
        help="Cel testu: andromeda, feishin, spotify lub compare (uruchamia wszystkie dostępne programy)"
    )
    parser.add_argument("--scenario", choices=["idle", "playback"], default="idle", help="Scenariusz testu live")
    parser.add_argument("--warmup", type=int, default=15, help="Czas rozgrzewki przed pomiarem w sekundach (domyślnie 15s)")
    parser.add_argument("--duration", type=int, default=15, help="Czas trwania próbkowania (sekundy)")
    parser.add_argument("--save-md", action="store_true", help="Zapisz tabelę do benchmark_report.md")
    parser.add_argument("--save-csv", action="store_true", help="Zapisz próbki telemetryczne do tests/results/")
    args = parser.parse_args()

    internal_results = {}
    results_map = {}

    targets_to_run = []
    if args.target == "compare":
        targets_to_run = ["andromeda", "feishin", "spotify"]
    else:
        targets_to_run = [args.target]

    if "andromeda" in targets_to_run:
        print("[INFO] Uruchamianie wewnętrznych mikrobenchmarków Andromedy...")
        internal_results = AndromedaInternalBenchmarks.run_all_internal()

    for target in targets_to_run:
        app_cmd, is_flatpak, flatpak_id = TargetAppLocator.resolve_app(target)
        if not app_cmd:
            print(f"[OSTRZEŻENIE] Program '{target}' nie został znaleziony w systemie. Pomijam.")
            continue

        print(f"\n[INFO] Uruchamianie testu: {target.upper()} (Flatpak={is_flatpak}, warmup: {args.warmup}s, próbkowanie: {args.duration}s)...")
        runner = LiveProcessBenchmark(
            target_name=target,
            app_cmd=app_cmd,
            is_flatpak=is_flatpak,
            flatpak_app_id=flatpak_id,
            duration_sec=args.duration,
            warmup_sec=args.warmup,
            scenario=args.scenario
        )
        live_data = runner.execute()
        if live_data:
            results_map[target] = live_data

    if len(results_map) > 1:
        BenchmarkReporter.print_multi_comparison_terminal(results_map)
    elif len(results_map) == 1:
        single_target = list(results_map.keys())[0]
        BenchmarkReporter.print_terminal_summary(
            internal_results if single_target == "andromeda" else {},
            results_map[single_target]
        )

    if args.save_md and results_map:
        md_content = BenchmarkReporter.generate_multi_comparison_markdown(results_map, internal_results)
        report_path = ROOT_DIR / "benchmark_report.md"
        report_path.write_text(md_content, encoding="utf-8")
        print(f"[SUKCES] Zaktualizowano raport Markdown w: {report_path}")

    if args.save_csv and results_map:
        res_dir = ROOT_DIR / "tests" / "results"
        ts = int(time.time())
        for target, data in results_map.items():
            BenchmarkReporter.export_csv(data, res_dir / f"{target}_{args.scenario}_{ts}.csv")
        print(f"[SUKCES] Zapisano próbki telemetryczne CSV do: {res_dir}")


if __name__ == "__main__":
    main()