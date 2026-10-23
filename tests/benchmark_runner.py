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
DEFAULT_YT_PLAYLIST_URL = "https://music.youtube.com/watch?v=xxFSf9l3dtg&list=PLKU7Ur1sVjeI"


class LinuxProcessMonitor:
    """
    Niezależny próbnik procesów oparty o jądro Linuksa (/proc) oraz kontroler D-Bus MPRIS.
    Wykrywa procesy potomne, wątki oraz całe drzewa PGID.
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

    @staticmethod
    def send_mpris_cmd(target_name: str, cmd: str = "Next") -> bool:
        if shutil.which("playerctl"):
            try:
                subprocess.run(
                    ["playerctl", cmd.lower()],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1
                )
                return True
            except Exception:
                pass

        try:
            res = subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--dest=org.freedesktop.DBus",
                    "--type=method_call",
                    "--print-reply",
                    "/org/freedesktop/DBus",
                    "org.freedesktop.DBus.ListNames"
                ],
                capture_output=True,
                text=True,
                timeout=2
            )
            mpris_names = []
            for line in res.stdout.splitlines():
                if 'string "org.mpris.MediaPlayer2.' in line:
                    mpris_names.append(line.split('"')[1])

            target_lower = target_name.lower()
            matching = [n for n in mpris_names if target_lower in n.lower() or (target_lower == "andromeda" and "andromeda" in n.lower())]

            for dest in matching:
                subprocess.run(
                    [
                        "dbus-send",
                        "--type=method_call",
                        f"--dest={dest}",
                        "/org/mpris/MediaPlayer2",
                        f"org.mpris.MediaPlayer2.Player.{cmd}"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1
                )
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def get_playback_status(target_name: str) -> str:
        try:
            res = subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--dest=org.freedesktop.DBus",
                    "--type=method_call",
                    "--print-reply",
                    "/org/freedesktop/DBus",
                    "org.freedesktop.DBus.ListNames"
                ],
                capture_output=True,
                text=True,
                timeout=2
            )
            mpris_names = []
            for line in res.stdout.splitlines():
                if 'string "org.mpris.MediaPlayer2.' in line:
                    n = line.split('"')[1]
                    mpris_names.append(n)

            target_lower = target_name.lower()
            matching = [n for n in mpris_names if target_lower in n.lower() or (target_lower == "andromeda" and "andromeda" in n.lower())]

            for dest in matching:
                prop_res = subprocess.run(
                    [
                        "dbus-send",
                        "--session",
                        f"--dest={dest}",
                        "--type=method_call",
                        "--print-reply",
                        "/org/mpris/MediaPlayer2",
                        "org.freedesktop.DBus.Properties.Get",
                        "string:org.mpris.MediaPlayer2.Player",
                        "string:PlaybackStatus"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                for pline in prop_res.stdout.splitlines():
                    if "variant" in pline and "string" in pline:
                        val = pline.split('"')[1]
                        return val
        except Exception:
            pass
        return "Stopped"

    @staticmethod
    def get_mpris_metadata(target_name: str) -> dict:
        meta = {}
        if shutil.which("playerctl"):
            try:
                res = subprocess.run(
                    ["playerctl", "metadata", "xesam:title"],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if res.returncode == 0 and res.stdout.strip():
                    meta["title"] = res.stdout.strip()
                    return meta
            except Exception:
                pass

        try:
            res = subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--dest=org.freedesktop.DBus",
                    "--type=method_call",
                    "--print-reply",
                    "/org/freedesktop/DBus",
                    "org.freedesktop.DBus.ListNames"
                ],
                capture_output=True,
                text=True,
                timeout=2
            )
            mpris_names = []
            for line in res.stdout.splitlines():
                if 'string "org.mpris.MediaPlayer2.' in line:
                    mpris_names.append(line.split('"')[1])

            target_lower = target_name.lower()
            matching = [n for n in mpris_names if target_lower in n.lower() or (target_lower == "andromeda" and "andromeda" in n.lower())]

            for dest in matching:
                prop_res = subprocess.run(
                    [
                        "dbus-send",
                        "--session",
                        f"--dest={dest}",
                        "--type=method_call",
                        "--print-reply",
                        "/org/mpris/MediaPlayer2",
                        "org.freedesktop.DBus.Properties.Get",
                        "string:org.mpris.MediaPlayer2.Player",
                        "string:Metadata"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                lines = prop_res.stdout.splitlines()
                for i, l in enumerate(lines):
                    if 'string "xesam:title"' in l:
                        for j in range(i + 1, min(i + 5, len(lines))):
                            if 'string "' in lines[j]:
                                meta["title"] = lines[j].split('"')[1]
                                return meta
        except Exception:
            pass
        return meta


class TargetAppLocator:
    """
    Automatycznie wykrywa polecenia uruchomieniowe i konfiguruje profile.
    """

    @staticmethod
    def get_bench_profiles_dir() -> Path:
        from core.paths import PathsManager
        base_dir = PathsManager.get_cache_dir() / "bench_profiles"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @staticmethod
    def clean_browser_sessions(target_name: str, bench_dir: Path):
        """
        Usuwa pliki otwartych kart z poprzednich sesji,
        pozostawiając w 100% nienaruszone ciasteczka i dane logowania.
        """
        if target_name == "brave":
            sessions_dir = bench_dir / "Default" / "Sessions"
            if sessions_dir.exists():
                shutil.rmtree(sessions_dir, ignore_errors=True)
            storage_dir = bench_dir / "Default" / "Session Storage"
            if storage_dir.exists():
                shutil.rmtree(storage_dir, ignore_errors=True)

        elif target_name == "firefox":
            sessionstore = bench_dir / "sessionstore.jsonlz4"
            if sessionstore.exists():
                sessionstore.unlink(missing_ok=True)
            backups = bench_dir / "sessionstore-backups"
            if backups.exists():
                shutil.rmtree(backups, ignore_errors=True)

    @staticmethod
    def resolve_app(
        target_name: str,
        scenario: str = "playback",
        video_mode: str = "live-1080p",
        playlist_name: str = "benchmark",
        yt_url: str = DEFAULT_YT_PLAYLIST_URL,
        custom_bin: str = None
    ) -> tuple:
        if custom_bin:
            return [custom_bin], False, None, None

        if target_name == "andromeda":
            cmd = [sys.executable, str(ROOT_DIR / "main.py")]
            if scenario in ["playback", "video"]:
                cmd.extend(["--play-playlist", playlist_name])
            if scenario == "video":
                cmd.append("--video")
                if video_mode == "live-1080p":
                    cmd.extend(["--force-live", "--force-res", "1080p"])
                elif video_mode == "live-480p":
                    cmd.extend(["--force-live", "--force-res", "480p"])
            return cmd, False, None, None

        flatpak_bin = shutil.which("flatpak")

        if target_name == "feishin":
            if flatpak_bin:
                try:
                    res = subprocess.run([flatpak_bin, "list", "--app"], capture_output=True, text=True)
                    if "org.jeffvli.feishin" in res.stdout:
                        return [flatpak_bin, "run", "org.jeffvli.feishin"], True, "org.jeffvli.feishin", None
                except Exception:
                    pass

            bin_path = shutil.which("feishin")
            if bin_path:
                return [bin_path], False, None, None

            common_locations = [
                Path.home() / "Applications" / "feishin.AppImage",
                Path.home() / ".local" / "bin" / "feishin",
                Path("/usr/bin/feishin"),
                Path("/opt/Feishin/feishin")
            ]
            for loc in common_locations:
                if loc.exists() and os.access(loc, os.X_OK):
                    return [str(loc)], False, None, None

        if target_name == "spotify":
            if flatpak_bin:
                try:
                    res = subprocess.run([flatpak_bin, "list", "--app"], capture_output=True, text=True)
                    if "com.spotify.Client" in res.stdout:
                        return [flatpak_bin, "run", "com.spotify.Client"], True, "com.spotify.Client", None
                except Exception:
                    pass

            bin_path = shutil.which("spotify")
            if bin_path:
                return [bin_path], False, None, None

            common_locations = [
                Path("/usr/bin/spotify"),
                Path.home() / ".local" / "bin" / "spotify"
            ]
            for loc in common_locations:
                if loc.exists() and os.access(loc, os.X_OK):
                    return [str(loc)], False, None, None

        if target_name == "brave":
            bin_path = shutil.which("brave-browser") or shutil.which("brave") or "/usr/bin/brave-browser"
            if Path(bin_path).exists() or shutil.which(bin_path):
                bench_dir = TargetAppLocator.get_bench_profiles_dir() / "brave"
                bench_dir.mkdir(parents=True, exist_ok=True)
                TargetAppLocator.clean_browser_sessions("brave", bench_dir)

                first_run_sentinel = bench_dir / "First Run"
                first_run_sentinel.touch(exist_ok=True)

                cmd = [
                    bin_path,
                    f"--user-data-dir={bench_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-session-crashed-bubble",
                    "--disable-fre",
                    "--disable-search-engine-choice-screen",
                    "--disable-features=BraveP3A,BraveRewards,SearchEngineChoiceScreen,BraveNews,BraveVPN,BraveWallet",
                    yt_url
                ]
                return cmd, False, None, bench_dir

        if target_name == "firefox":
            bin_path = shutil.which("firefox") or "/usr/bin/firefox"
            if Path(bin_path).exists() or shutil.which(bin_path):
                bench_dir = TargetAppLocator.get_bench_profiles_dir() / "firefox"
                bench_dir.mkdir(parents=True, exist_ok=True)
                TargetAppLocator.clean_browser_sessions("firefox", bench_dir)

                user_js = bench_dir / "user.js"
                prefs = (
                    'user_pref("browser.aboutwelcome.enabled", false);\n'
                    'user_pref("trailhead.firstrun.didSeeAboutWelcome", true);\n'
                    'user_pref("browser.startup.page", 1);\n'
                    'user_pref("browser.startup.homepage", "about:blank");\n'
                    'user_pref("browser.shell.checkDefaultBrowser", false);\n'
                    'user_pref("datareporting.policy.dataSubmissionPolicyAccepted", true);\n'
                    'user_pref("datareporting.policy.dataSubmissionPolicyBypassAcceptance", true);\n'
                    'user_pref("browser.newtabpage.enabled", false);\n'
                    'user_pref("browser.search.choice_screen.enabled", false);\n'
                    'user_pref("doh-rollout.doneFirstRun", true);\n'
                    'user_pref("browser.sessionstore.resume_from_crash", false);\n'
                    'user_pref("browser.sessionstore.max_resumed_crashes", 0);\n'
                    'user_pref("media.hardwaremediakeys.enabled", true);\n'
                )
                user_js.write_text(prefs, encoding="utf-8")

                cmd = [
                    bin_path,
                    "--new-instance",
                    "--no-remote",
                    "--profile",
                    str(bench_dir),
                    yt_url
                ]
                return cmd, False, None, bench_dir

        return None, False, None, None


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
    Uruchamia docelowy program, weryfikuje start właściwego Utworu,
    zapewnia równą rozgrzewkę bufora dla każdego programu,
    zegar na żywo w konsoli oraz automatyczne przełączanie sygnałem MPRIS.
    """

    def __init__(
        self,
        target_name: str,
        app_cmd: list,
        is_flatpak: bool = False,
        flatpak_app_id: str = None,
        duration_sec: int = 120,
        warmup_sec: int = 15,
        scenario: str = "playback",
        video_mode: str = "live-1080p",
        playlist_name: str = "benchmark"
    ):
        self.target_name = target_name
        self.app_cmd = app_cmd
        self.is_flatpak = is_flatpak
        self.flatpak_app_id = flatpak_app_id
        self.duration_sec = duration_sec
        self.warmup_sec = warmup_sec
        self.scenario = scenario
        self.video_mode = video_mode
        self.playlist_name = playlist_name

        if self.target_name == "andromeda":
            if self.scenario == "video":
                if self.video_mode == "offline":
                    self.display_name = "Andromeda (Video Offline)"
                elif self.video_mode == "live-480p":
                    self.display_name = "Andromeda (Video 480p Live)"
                else:
                    self.display_name = "Andromeda (Video 1080p Live)"
            else:
                self.display_name = "Andromeda (Qt6)"
        else:
            self.display_name = self.target_name.capitalize()

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
            # 1. Krok: Pomiar czasu startu okna
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

            # 2. Krok: Weryfikacja startu właściwego Utworu 1
            if self.scenario in ["playback", "video"]:
                if self.scenario == "playback":
                    expected_kw = "przysz"
                    expected_title = "Przyszłość"
                else:
                    expected_kw = "nieba"
                    expected_title = "WIĘCEJ NIEBA"

                is_playing_correct = False

                LinuxProcessMonitor.send_mpris_cmd(self.target_name, "Play")
                time.sleep(1.0)

                for _ in range(5):
                    status = LinuxProcessMonitor.get_playback_status(self.target_name)
                    meta = LinuxProcessMonitor.get_mpris_metadata(self.target_name)
                    title = meta.get("title", "")
                    if status == "Playing" and (expected_kw in title.lower() or not title):
                        is_playing_correct = True
                        break
                    time.sleep(0.5)

                if not is_playing_correct:
                    curr_title = LinuxProcessMonitor.get_mpris_metadata(self.target_name).get("title", "Brak")
                    print(f"\n[INFO] [{self.display_name.upper()}] Wykryty utwór w odtwarzaczu: '{curr_title}'.")
                    print(f"       -> Otwórz playlistę '{self.playlist_name}' i kliknij Utwór 1 ('{expected_title}') w oknie!")
                    for _ in range(60):
                        time.sleep(0.5)
                        status = LinuxProcessMonitor.get_playback_status(self.target_name)
                        meta = LinuxProcessMonitor.get_mpris_metadata(self.target_name)
                        title = meta.get("title", "")
                        if status == "Playing" and (expected_kw in title.lower() or not title):
                            is_playing_correct = True
                            print(f"[OK] [{self.display_name.upper()}] Wykryto prawidłowy Utwór 1: '{title or expected_title}'!")
                            break

            # 3. Krok: Równa rozgrzewka bufora audio/wideo
            if self.warmup_sec > 0:
                print(f"[INFO] [{self.display_name.upper()}] Faza rozgrzewki: Utwór 1 gra, stabilizacja bufora PipeWire/FFmpeg ({self.warmup_sec}s)...")
                time.sleep(self.warmup_sec)

            print(f"[INFO] [{self.display_name.upper()}] Rozpoczynam próbkowanie metryk (czas trwania: {self.duration_sec}s)...")
            start_time = time.perf_counter()
            prev_ticks = 0
            prev_tick_time = start_time
            next_track_triggered = False

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
                elapsed = now - start_time

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

                if self.scenario in ["playback", "video"] and not next_track_triggered and elapsed >= (self.duration_sec / 2):
                    next_track_triggered = True
                    sys.stdout.write(f"\n[INFO] [{self.display_name.upper()}] >>> [{int(self.duration_sec/2)}s] PRZEŁĄCZANIE: WYSYŁANIE SYGNAŁU D-BUS MPRIS (NEXT) <<<\n")
                    sys.stdout.flush()
                    LinuxProcessMonitor.send_mpris_cmd(self.target_name, "Next")

                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                tot_mins = int(self.duration_sec // 60)
                tot_secs = int(self.duration_sec % 60)
                
                if self.scenario == "video":
                    track_label = "Utwór 1 (WIĘCEJ NIEBA)" if elapsed < (self.duration_sec / 2) else "Utwór 2 (JESTEM WOLNY)"
                else:
                    track_label = "Utwór 1 (Przyszłość)" if elapsed < (self.duration_sec / 2) else "Utwór 2 (MIĘSO)"
                
                sys.stdout.write(
                    f"\r[{self.display_name:<20}] [{mins:02d}:{secs:02d} / {tot_mins:02d}:{tot_secs:02d}] "
                    f"[{track_label}] CPU: {cpu_percent:5.1f}% | PSS: {mem['pss_mb']:6.1f} MB | Procesy: {len(pids)}"
                )
                sys.stdout.flush()

                samples.append({
                    "time_offset": round(elapsed, 2),
                    "cpu_percent": round(max(0.0, cpu_percent), 2),
                    "pss_mb": round(mem["pss_mb"], 2),
                    "rss_mb": round(mem["rss_mb"], 2),
                    "private_dirty_mb": round(mem["private_dirty_mb"], 2),
                    "thread_count": thread_count,
                    "process_count": len(pids),
                })
                time.sleep(0.5)

            sys.stdout.write("\n")
            sys.stdout.flush()

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
            "target": self.display_name,
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
            scenario_name = live_data.get('scenario', 'playback').upper()
            warmup_val = live_data.get('warmup_sec', 0)
            print(f"\n[2] METRYKI PROCESU LINUX / WAYLAND ({scenario_name}, WARMUP: {warmup_val}s):")
            print(f"  • Czas startu aplikacji:            {live_data.get('startup_time_sec', 0):.3f} s")
            print(f"  • Prawdziwy narzut RAM (Średni PSS): {live_data.get('avg_pss_mb', 0):.2f} MB")
            print(f"  • Pamięć fizyczna (Średni RSS):     {live_data.get('avg_rss_mb', 0):.2f} MB")
            print(f"  • Szczyt pamięci (Max RSS):         {live_data.get('max_rss_mb', 0):.2f} MB")
            print(f"  • Średnie obciążenie CPU:           {live_data.get('avg_cpu_percent', 0):.2f} %")
            print(f"  • Szczytowe CPU (Max spike):        {live_data.get('max_cpu_percent', 0):.2f} %")
            print(f"  • Liczba procesów systemowych:      {live_data.get('max_processes', 1)}")
            print(f"  • Średnia liczba wątków:            {live_data.get('avg_threads', 0)}")

        print("\n" + "=" * 65 + "\n")

    @staticmethod
    def print_multi_comparison_terminal(results_map: dict):
        print("\n" + "=" * 135)
        print("          ZESTAWIENIE PORÓWNAWCZE WYDAJNOŚCI ZASOBÓW (LINUX / WAYLAND)")
        print("=" * 135)

        header = f"{'Metryka':<32}"
        for name in results_map.keys():
            # Name in terminal can be slightly abbreviated to fit
            n_short = name.replace("Andromeda", "Andr").replace("(", "").replace(")", "").strip()
            header += f" | {n_short:<18}"
        print(header)
        print("-" * 135)

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
                row += f" | {val_str:<18}"
            print(row)

        print_row("Czas startu (Cold Startup)", "startup_time_sec", "s")
        print_row("Pamięć rzeczywista (PSS)", "avg_pss_mb", "MB")
        print_row("Pamięć fizyczna (RSS)", "avg_rss_mb", "MB")
        print_row("Średnie CPU (Odtwarzanie)", "avg_cpu_percent", "%")
        print_row("Szczytowe CPU (Max Spike)", "max_cpu_percent", "%")
        print_row("Liczba procesów systemowych", "max_processes")
        print("=" * 135 + "\n")

    @staticmethod
    def generate_multi_comparison_markdown(results_map: dict, internal_data: dict = None, scenario: str = "video") -> str:
        md = []
        if scenario == "video":
            md.append("## Raport Porównawczy: Andromeda Music vs Konkurencja (Odtwarzanie Wideo)\n")
            md.append("*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), teledyski 1080p, standaryzowany pomiar jądra (/proc/smaps_rollup)*\n")
        else:
            md.append("## Raport Porównawczy: Andromeda Music vs Konkurencja (Audio Playback)\n")
            md.append("*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), 2 utwory (120s), standaryzowany pomiar jądra (/proc/smaps_rollup)*\n")

        headers = ["Metryka"]
        for target in results_map.keys():
            headers.append(target)
        
        # We don't append "Przewaga" automatically if there are many Andromedas (like in video test)
        if scenario != "video":
            headers.append("Wnioski")

        md.append("| " + " | ".join(headers) + " |")
        md.append("| " + " | ".join([":---" if i == 0 else (":---:" if i < len(headers) - 1 else ":---") for i in range(len(headers))]) + " |")

        # Get the first Andromeda data for baseline comparison if needed
        base_a_data = None
        for k, v in results_map.items():
            if "Andromeda" in k:
                base_a_data = v
                break
        if not base_a_data:
            base_a_data = {}

        a_start = base_a_data.get("startup_time_sec", 0)
        a_pss = base_a_data.get("avg_pss_mb", 0)
        a_rss = base_a_data.get("avg_rss_mb", 0)
        a_cpu = base_a_data.get("avg_cpu_percent", 0)
        a_max_cpu = base_a_data.get("max_cpu_percent", 0)
        a_procs = base_a_data.get("max_processes", 1)

        def make_row(title, key, unit, precision=1, lower_is_better=True):
            row = [f"**{title}**"]
            for target in results_map.keys():
                val = results_map[target].get(key, 0)
                if precision == 3:
                    row.append(f"**{val:.3f} {unit}**" if "Andromeda" in target else f"{val:.3f} {unit}")
                elif precision == 2:
                    row.append(f"**{val:.2f}{unit}**" if "Andromeda" in target else f"{val:.2f}{unit}")
                elif precision == 0:
                    row.append(f"**{val} {unit}**" if "Andromeda" in target else f"{val} {unit}")
                else:
                    row.append(f"**{val:.1f} {unit}**" if "Andromeda" in target else f"{val:.1f} {unit}")
            
            if scenario != "video":
                row.append("-")
            return row

        # 1. Start time
        row_start = make_row("Czas startu (Cold Startup)", "startup_time_sec", "s", 3)
        md.append("| " + " | ".join(row_start) + " |")

        # 2. PSS
        row_pss = make_row("Pamięć rzeczywista (PSS)", "avg_pss_mb", "MB", 1)
        md.append("| " + " | ".join(row_pss) + " |")

        # 3. RSS
        row_rss = make_row("Pamięć fizyczna (RSS)", "avg_rss_mb", "MB", 1)
        md.append("| " + " | ".join(row_rss) + " |")

        # 4. CPU Avg
        row_cpu = make_row(f"Średnie CPU ({'Odtwarzanie Wideo' if scenario == 'video' else 'Odtwarzanie Audio'})", "avg_cpu_percent", "%", 2)
        md.append("| " + " | ".join(row_cpu) + " |")

        # 5. CPU Max
        row_max_cpu = make_row("Szczytowe CPU (Max Spike)", "max_cpu_percent", "%", 2)
        md.append("| " + " | ".join(row_max_cpu) + " |")

        # 6. Processes
        row_proc = make_row("Liczba procesów systemowych", "max_processes", "", 0)
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


def setup_browser_profiles():
    print("\n" + "=" * 70)
    print("      KREATOR PRZYGOTOWANIA PROFILI PRZEGLĄDAREK DO BENCHMARKU")
    print("=" * 70)

    brave_cmd, _, _, _ = TargetAppLocator.resolve_app("brave")
    if brave_cmd:
        print("\n[1/2] Uruchamianie Brave...")
        print("  -> Upewnij się, że jesteś zalogowany i przełącznik u góry to 'Wideo' (lub 'Utwór').")
        print("  -> Zamknij okno Brave, gdy skończysz.\n")
        proc = subprocess.Popen(brave_cmd)
        proc.wait()
        print("[OK] Zapisano sesję dla Brave.")

    ff_cmd, _, _, _ = TargetAppLocator.resolve_app("firefox")
    if ff_cmd:
        print("\n[2/2] Uruchamianie Firefox...")
        print("  -> Upewnij się, że jesteś zalogowany i przełącznik u góry to 'Wideo' (lub 'Utwór').")
        print("  -> Zamknij okno Firefox, gdy skończysz.\n")
        proc = subprocess.Popen(ff_cmd)
        proc.wait()
        print("[OK] Zapisano sesję dla Firefox.")

    print("\n" + "=" * 70)
    print("[SUKCES] Profile gotowe!")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Andromeda Music Benchmark & Multi-Comparison Runner")
    parser.add_argument(
        "--target",
        type=str,
        default="compare",
        help="Cel testu: np. 'andromeda', 'brave', 'compare' lub 'compare-video'"
    )
    parser.add_argument("--scenario", choices=["idle", "playback", "video"], default="video", help="Scenariusz testu live")
    parser.add_argument("--video-mode", choices=["live-1080p", "live-480p", "offline"], default="live-1080p", help="Tryb wideo dla Andromedy")
    parser.add_argument("--playlist-name", type=str, default="benchmark2", help="Nazwa playlisty dla Andromedy")
    parser.add_argument("--warmup", type=int, default=15, help="Czas rozgrzewki przed pomiarem w sekundach (domyślnie 15s)")
    parser.add_argument("--duration", type=int, default=120, help="Czas trwania próbkowania")
    parser.add_argument("--yt-url", type=str, default="https://music.youtube.com/watch?v=xxFSf9l3dtg&list=PLSOIc_dAyPn8", help="Bezpośredni link do playlisty z wideo na YouTube Music")
    parser.add_argument("--save-md", action="store_true", help="Zapisz tabelę do benchmark_report.md")
    parser.add_argument("--save-csv", action="store_true", help="Zapisz próbki telemetryczne do tests/results/")
    parser.add_argument("--setup-browsers", action="store_true", help="Uruchom kreator logowania w profilach przeglądarek")
    args = parser.parse_args()

    if args.setup_browsers:
        setup_browser_profiles()
        return

    internal_results = {}
    results_map = {}

    target_arg = args.target.strip()
    
    # Tryb compare-video uruchamia 5 wariantów dla wideo
    if target_arg == "compare-video":
        configs_to_run = [
            ("andromeda", "live-1080p"),
            ("andromeda", "live-480p"),
            ("andromeda", "offline"),
            ("brave", None),
            ("firefox", None)
        ]
        args.scenario = "video"
    elif target_arg == "compare":
        configs_to_run = [
            ("andromeda", args.video_mode),
            ("feishin", None),
            ("spotify", None),
            ("brave", None),
            ("firefox", None)
        ]
    else:
        raw_targets = [t.strip().lower() for t in target_arg.split(",") if t.strip()]
        configs_to_run = [(t, args.video_mode if t == "andromeda" else None) for t in raw_targets]

    if any(c[0] == "andromeda" for c in configs_to_run):
        print("[INFO] Uruchamianie wewnętrznych mikrobenchmarków Andromedy...")
        internal_results = AndromedaInternalBenchmarks.run_all_internal()

    for target, v_mode in configs_to_run:
        app_cmd, is_flatpak, flatpak_id, _ = TargetAppLocator.resolve_app(
            target, 
            scenario=args.scenario, 
            video_mode=v_mode, 
            playlist_name=args.playlist_name, 
            yt_url=args.yt_url
        )
        
        if not app_cmd:
            print(f"[OSTRZEŻENIE] Program '{target}' nie został znaleziony w systemie. Pomijam.")
            continue

        mode_str = f" ({v_mode})" if v_mode else ""
        print(f"\n[INFO] Uruchamianie testu: {target.upper()}{mode_str} (Scenariusz={args.scenario}, warmup: {args.warmup}s, czas: {args.duration}s)...")
        
        runner = LiveProcessBenchmark(
            target_name=target,
            app_cmd=app_cmd,
            is_flatpak=is_flatpak,
            flatpak_app_id=flatpak_id,
            duration_sec=args.duration,
            warmup_sec=args.warmup,
            scenario=args.scenario,
            video_mode=v_mode,
            playlist_name=args.playlist_name
        )
        live_data = runner.execute()
        if live_data:
            display_name = live_data["target"]
            results_map[display_name] = live_data

    if len(results_map) > 1:
        BenchmarkReporter.print_multi_comparison_terminal(results_map)
    elif len(results_map) == 1:
        single_target = list(results_map.keys())[0]
        BenchmarkReporter.print_terminal_summary(
            internal_results if "Andromeda" in single_target else {},
            results_map[single_target]
        )

    if args.save_md and results_map:
        md_content = BenchmarkReporter.generate_multi_comparison_markdown(results_map, internal_results, scenario=args.scenario)
        report_path = ROOT_DIR / "benchmark_report.md"
        report_path.write_text(md_content, encoding="utf-8")
        print(f"[SUKCES] Zaktualizowano raport Markdown w: {report_path}")

    if args.save_csv and results_map:
        res_dir = ROOT_DIR / "tests" / "results"
        ts = int(time.time())
        for target, data in results_map.items():
            safe_name = target.replace(" ", "_").replace("(", "").replace(")", "").lower()
            BenchmarkReporter.export_csv(data, res_dir / f"{safe_name}_{args.scenario}_{ts}.csv")
        print(f"[SUKCES] Zapisano próbki telemetryczne CSV do: {res_dir}")


if __name__ == "__main__":
    main()