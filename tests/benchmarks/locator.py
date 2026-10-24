import os
os.environ["QT_API"] = "pyside6"

import sys
import shutil
import subprocess
from pathlib import Path

class TargetAppLocator:
    """
    Automatycznie wykrywa polecenia uruchomieniowe i konfiguruje profile testowe aplikacji.
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
        scenario: str = "video",
        video_mode: str = "live-1080p",
        playlist_name: str = "benchmark2",
        yt_url: str = None,
        custom_bin: str = None,
        blur_val: int = None,
        opacity_val: int = None
    ) -> tuple:
        root_dir = Path(__file__).resolve().parent.parent.parent

        if custom_bin:
            return [custom_bin], False, None, None

        if target_name == "andromeda":
            cmd = [sys.executable, str(root_dir / "main.py")]
            if scenario in ["playback", "video"]:
                cmd.extend(["--play-playlist", playlist_name])
            if scenario == "video":
                cmd.append("--video")
                if video_mode == "live-1080p":
                    cmd.extend(["--force-live", "--force-res", "1080p"])
                elif video_mode == "live-480p":
                    cmd.extend(["--force-live", "--force-res", "480p"])

            if blur_val is not None:
                cmd.extend(["--force-blur", str(blur_val)])
            if opacity_val is not None:
                cmd.extend(["--force-opacity", str(opacity_val)])

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
                ]

                if yt_url:
                    cmd.append(yt_url)
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
                    str(bench_dir)
                ]

                if yt_url:
                    cmd.append(yt_url)
                return cmd, False, None, bench_dir

        return None, False, None, None