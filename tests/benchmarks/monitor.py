import os
os.environ["QT_API"] = "pyside6"

import shutil
import subprocess
from pathlib import Path

CLK_TCK = os.sysconf(os.sysconf_names.get('SC_CLK_TCK', 'SC_CLK_TCK')) or 100

class LinuxProcessMonitor:
    """
    Niezależny próbnik procesów oparty o jądro Linuksa (/proc) oraz dynamiczny kontroler D-Bus MPRIS.
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

    # --- DYNAMICZNE WYKRYWANIE MPRIS ---

    @staticmethod
    def get_all_mpris_players() -> list:
        players = []
        if shutil.which("playerctl"):
            try:
                res = subprocess.run(["playerctl", "-l"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    players = res.stdout.splitlines()
            except Exception:
                pass
        
        if not players:
            try:
                res = subprocess.run([
                    "dbus-send", "--session", "--dest=org.freedesktop.DBus",
                    "--type=method_call", "--print-reply", "/org/freedesktop/DBus",
                    "org.freedesktop.DBus.ListNames"
                ], capture_output=True, text=True, timeout=2)
                players = [line.split('"')[1] for line in res.stdout.splitlines() if 'string "org.mpris.MediaPlayer2.' in line]
            except Exception:
                pass
        
        return players

    @staticmethod
    def get_player_title(player_name: str) -> str:
        if shutil.which("playerctl") and not player_name.startswith("org.mpris"):
            try:
                res = subprocess.run(["playerctl", "-p", player_name, "metadata", "xesam:title"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass
        
        dest = player_name if player_name.startswith("org.mpris") else f"org.mpris.MediaPlayer2.{player_name}"
        try:
            res = subprocess.run([
                "dbus-send", "--session", f"--dest={dest}", "--type=method_call",
                "--print-reply", "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties.Get",
                "string:org.mpris.MediaPlayer2.Player", "string:Metadata"
            ], capture_output=True, text=True, timeout=1)
            lines = res.stdout.splitlines()
            for i, l in enumerate(lines):
                if 'string "xesam:title"' in l:
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if 'variant' in lines[j] and 'string "' in lines[j]:
                            return lines[j].split('"')[1]
                        elif 'string "' in lines[j]:
                            return lines[j].split('"')[1]
        except Exception:
            pass
        return ""

    @staticmethod
    def get_player_status(player_name: str) -> str:
        if shutil.which("playerctl") and not player_name.startswith("org.mpris"):
            try:
                res = subprocess.run(["playerctl", "-p", player_name, "status"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass
        
        dest = player_name if player_name.startswith("org.mpris") else f"org.mpris.MediaPlayer2.{player_name}"
        try:
            res = subprocess.run([
                "dbus-send", "--session", f"--dest={dest}", "--type=method_call",
                "--print-reply", "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties.Get",
                "string:org.mpris.MediaPlayer2.Player", "string:PlaybackStatus"
            ], capture_output=True, text=True, timeout=1)
            for pline in res.stdout.splitlines():
                if "variant" in pline and "string" in pline:
                    return pline.split('"')[1]
        except Exception:
            pass
        return "Stopped"

    @staticmethod
    def send_cmd_to_player(player_name: str, cmd: str) -> bool:
        if not player_name: return False
        if shutil.which("playerctl") and not player_name.startswith("org.mpris"):
            try:
                subprocess.run(["playerctl", "-p", player_name, cmd.lower()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                return True
            except Exception:
                pass
        
        dest = player_name if player_name.startswith("org.mpris") else f"org.mpris.MediaPlayer2.{player_name}"
        try:
            subprocess.run([
                "dbus-send", "--type=method_call", f"--dest={dest}",
                "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{cmd}"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            return True
        except Exception:
            return False

class LinuxGpuMonitor:
    """
    Próbnik sprzętowej telemetrii GPU oparty o natywny interfejs jądra Linuksa (/proc/<pid>/fdinfo).
    Mierzy czas pracy procesora graficznego w nanosekundach bez praw roota:
    - drm-engine-render / gfx: shadery 3D, QtQuick GLSL, kompozytor
    - drm-engine-video / dec: sprzętowy dekoder wideo (Intel VA-API / AMD / Nouveau)
    """

    @staticmethod
    def get_process_gpu_time_ns(pids: set) -> dict:
        total_render_ns = 0
        total_video_ns = 0
        total_other_ns = 0

        for pid in pids:
            fd_dir = Path(f"/proc/{pid}/fdinfo")
            if not fd_dir.exists():
                continue
            try:
                for fd_file in fd_dir.iterdir():
                    try:
                        content = fd_file.read_text(encoding="utf-8", errors="ignore")
                        if "drm-driver" not in content and "drm-engine-" not in content:
                            continue

                        for line in content.splitlines():
                            line_str = line.strip()
                            if line_str.startswith(("drm-engine-render:", "drm-engine-gfx:")):
                                parts = line_str.split()
                                if len(parts) >= 2 and parts[1].isdigit():
                                    total_render_ns += int(parts[1])
                            elif line_str.startswith(("drm-engine-video:", "drm-engine-dec:", "drm-engine-vcs:")):
                                parts = line_str.split()
                                if len(parts) >= 2 and parts[1].isdigit():
                                    total_video_ns += int(parts[1])
                            elif line_str.startswith("drm-engine-"):
                                parts = line_str.split()
                                if len(parts) >= 2 and parts[1].isdigit():
                                    total_other_ns += int(parts[1])
                    except (PermissionError, ProcessLookupError, FileNotFoundError, OSError):
                        pass
            except (PermissionError, ProcessLookupError, FileNotFoundError, OSError):
                pass

        return {
            "render_ns": total_render_ns,
            "video_ns": total_video_ns,
            "total_ns": total_render_ns + total_video_ns + total_other_ns
        }