import os
os.environ["QT_API"] = "pyside6"

import sys
import time
import signal
import subprocess
from pathlib import Path

from .monitor import LinuxProcessMonitor, LinuxGpuMonitor, CLK_TCK

class LiveProcessBenchmark:
    """
    Uruchamia aplikację testową, weryfikuje start odtwarzania przez D-Bus MPRIS,
    stabilizuje bufor w fazie warmup i próbuje telemetrię CPU, RAM oraz GPU.
    """

    def __init__(
        self,
        target_name: str,
        app_cmd: list,
        is_flatpak: bool = False,
        flatpak_app_id: str = None,
        duration_sec: int = 120,
        warmup_sec: int = 15,
        scenario: str = "video",
        video_mode: str = "live-1080p",
        playlist_name: str = "benchmark2",
        display_label: str = None
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
        self.cpu_cores = os.cpu_count() or 1

        if display_label:
            self.display_name = display_label
        elif self.target_name == "andromeda":
            if self.scenario == "video":
                if self.video_mode == "offline":
                    self.display_name = "Andromeda (Video Offline)"
                elif self.video_mode == "live-480p":
                    self.display_name = "Andromeda (Video 480p Live)"
                else:
                    self.display_name = "Andromeda (Video 1080p Live)"
            elif self.scenario == "playback":
                self.display_name = "Andromeda (Audio Playback)"
            else:
                self.display_name = "Andromeda (Idle)"
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

            if self.scenario in ["playback", "video"]:
                expected_kw = "przysz" if self.scenario == "playback" else "nieba"
                expected_title = "Przyszłość" if self.scenario == "playback" else "WIĘCEJ NIEBA"
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
                            print(f"[OK] [{self.display_name.upper()}] Wykryto prawidłowy Utwór 1: '{title or expected_title}'!")
                            break

            if self.warmup_sec > 0:
                print(f"[INFO] [{self.display_name.upper()}] Faza rozgrzewki: stabilizacja buforów ({self.warmup_sec}s)...")
                time.sleep(self.warmup_sec)

            print(f"[INFO] [{self.display_name.upper()}] Rozpoczynam próbkowanie metryk (czas trwania: {self.duration_sec}s)...")
            start_time = time.perf_counter()
            prev_ticks = 0
            prev_tick_time = start_time
            prev_gpu = None
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
                current_gpu = LinuxGpuMonitor.get_process_gpu_time_ns(pids)
                thread_count = LinuxProcessMonitor.count_threads(pids)

                if prev_ticks > 0 and dt > 0.1:
                    tick_diff = current_ticks - prev_ticks
                    cpu_percent_raw = (tick_diff / CLK_TCK) / dt * 100.0
                else:
                    cpu_percent_raw = 0.0

                cpu_percent_total = cpu_percent_raw / self.cpu_cores

                if prev_gpu is not None and dt > 0.1:
                    dt_ns = dt * 1_000_000_000.0
                    render_diff = max(0, current_gpu["render_ns"] - prev_gpu["render_ns"])
                    video_diff = max(0, current_gpu["video_ns"] - prev_gpu["video_ns"])
                    total_gpu_diff = max(0, current_gpu["total_ns"] - prev_gpu["total_ns"])

                    gpu_render_pct = (render_diff / dt_ns) * 100.0
                    gpu_video_pct = (video_diff / dt_ns) * 100.0
                    gpu_total_pct = (total_gpu_diff / dt_ns) * 100.0
                else:
                    gpu_render_pct = 0.0
                    gpu_video_pct = 0.0
                    gpu_total_pct = 0.0

                prev_ticks = current_ticks
                prev_gpu = current_gpu
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

                sys.stdout.write(
                    f"\r[{self.display_name:<26}] [{mins:02d}:{secs:02d}/{tot_mins:02d}:{tot_secs:02d}] "
                    f"CPU: {cpu_percent_total:4.1f}% (Rdzeń: {cpu_percent_raw:5.1f}%) | "
                    f"GPU: {gpu_total_pct:4.1f}% (3D: {gpu_render_pct:4.1f}%, Dec: {gpu_video_pct:4.1f}%) | "
                    f"PSS: {mem['pss_mb']:5.1f}MB"
                )
                sys.stdout.flush()

                samples.append({
                    "time_offset": round(elapsed, 2),
                    "cpu_percent_raw": round(max(0.0, cpu_percent_raw), 2),
                    "cpu_percent_total": round(max(0.0, cpu_percent_total), 2),
                    "gpu_total_percent": round(max(0.0, gpu_total_pct), 2),
                    "gpu_render_percent": round(max(0.0, gpu_render_pct), 2),
                    "gpu_video_percent": round(max(0.0, gpu_video_pct), 2),
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

        avg_cpu_raw = sum(s["cpu_percent_raw"] for s in samples) / len(samples)
        max_cpu_raw = max(s["cpu_percent_raw"] for s in samples)
        avg_cpu_total = sum(s["cpu_percent_total"] for s in samples) / len(samples)
        max_cpu_total = max(s["cpu_percent_total"] for s in samples)

        avg_gpu_total = sum(s["gpu_total_percent"] for s in samples) / len(samples)
        max_gpu_total = max(s["gpu_total_percent"] for s in samples)
        avg_gpu_render = sum(s["gpu_render_percent"] for s in samples) / len(samples)
        avg_gpu_video = sum(s["gpu_video_percent"] for s in samples) / len(samples)

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
            "avg_cpu_total": round(avg_cpu_total, 2),
            "max_cpu_total": round(max_cpu_total, 2),
            "avg_cpu_raw": round(avg_cpu_raw, 2),
            "max_cpu_raw": round(max_cpu_raw, 2),
            "avg_gpu_total": round(avg_gpu_total, 2),
            "max_gpu_total": round(max_gpu_total, 2),
            "avg_gpu_render": round(avg_gpu_render, 2),
            "avg_gpu_video": round(avg_gpu_video, 2),
            "avg_pss_mb": round(avg_pss, 2),
            "max_pss_mb": round(max_pss, 2),
            "avg_rss_mb": round(avg_rss, 2),
            "max_rss_mb": round(max_rss, 2),
            "avg_threads": round(avg_threads, 1),
            "max_processes": max_processes,
            "samples": samples,
        }