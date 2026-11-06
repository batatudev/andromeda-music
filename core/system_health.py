import os
os.environ["QT_API"] = "pyside6"

import sys
import shutil
import platform
import subprocess
from urllib.parse import urlparse

from utils import logger
from core.i18n import tr
from config import APP_NAME, APP_VERSION, APP_CODENAME, APP_CONFIG

class SystemHealthChecker:
    @staticmethod
    def check_ffmpeg() -> bool:
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def check_mpris() -> bool:
        try:
            import pydbus
            import gi
            return True
        except ImportError:
            return False

    @classmethod
    def perform_startup_check(cls, main_window):
        if not cls.check_ffmpeg():
            logger.log("OSTRZEŻENIE: Brak narzędzia 'ffmpeg' w systemie!")
            if hasattr(main_window, 'show_toast'):
                msg = tr(
                    "health.ffmpeg_missing",
                    "Brak pakietu ffmpeg w systemie. Scalanie wideo i pobieranie 1080p może nie działać poprawnie."
                )
                main_window.show_toast(
                    msg,
                    title=tr("health.warning", "Ostrzeżenie systemowe"),
                    icon_str="fa5s.exclamation-triangle",
                    icon_color="#e67e22",
                    duration=7000
                )

    @classmethod
    def get_linux_distro(cls) -> str:
        try:
            if hasattr(platform, "freedesktop_os_release"):
                rel = platform.freedesktop_os_release()
                return rel.get("PRETTY_NAME", rel.get("NAME", "Linux"))
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        return platform.platform()

    @classmethod
    def get_audio_server_info(cls) -> str:
        if shutil.which("pactl"):
            try:
                res = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=1.5)
                for line in res.stdout.splitlines():
                    if "Server Name:" in line:
                        server_name = line.split(":", 1)[1].strip()
                        if "PipeWire" in server_name:
                            return f"PipeWire ({server_name})"
                        return server_name
            except Exception:
                pass
        if shutil.which("pipewire"):
            return "PipeWire"
        if shutil.which("pulseaudio"):
            return "PulseAudio"
        return "Unknown / ALSA"

    @classmethod
    def get_ffmpeg_version(cls) -> str:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            return "Missing (Not found in PATH)"
        try:
            res = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=1.5)
            first_line = res.stdout.splitlines()[0] if res.stdout else "Installed"
            return first_line.split("Copyright")[0].strip()
        except Exception:
            return "Installed (Version detection failed)"

    @classmethod
    def get_ytdlp_version(cls) -> str:
        try:
            import yt_dlp
            return getattr(yt_dlp.version, "__version__", "Installed")
        except ImportError:
            return "Missing (ImportError)"

    @classmethod
    def get_masked_server_url(cls) -> str:
        raw_url = APP_CONFIG.get("url", "")
        if not raw_url:
            return "None configured"
        try:
            parsed = urlparse(raw_url)
            port_str = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{parsed.hostname or 'configured'}{port_str}"
        except Exception:
            return "Invalid URL"

    @classmethod
    def generate_diagnostic_report(cls) -> str:
        import PySide6
        from PySide6.QtCore import qVersion

        distro = cls.get_linux_distro()
        kernel = platform.release()
        display_server = os.environ.get("XDG_SESSION_TYPE", "unknown")
        desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "unknown")
        python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        pyside_ver = PySide6.__version__
        qt_ver = qVersion()
        audio_server = cls.get_audio_server_info()
        ffmpeg_info = cls.get_ffmpeg_version()
        ytdlp_info = cls.get_ytdlp_version()
        mpris_available = cls.check_mpris()
        server_info = cls.get_masked_server_url()
        active_server_id = APP_CONFIG.get("active_server_id", "demo")

        report = f"""### Andromeda Music Diagnostics
```yaml
application:
  name: "{APP_NAME}"
  version: "{APP_VERSION}"
  codename: "{APP_CODENAME}"

environment:
  distribution: "{distro}"
  kernel: "{kernel}"
  display_server: "{display_server}"
  desktop_environment: "{desktop_env}"

runtime:
  python_version: "{python_ver}"
  pyside6_version: "{pyside_ver}"
  qt_version: "{qt_ver}"
  audio_subsystem: "{audio_server}"
  mpris_support: {mpris_available}

dependencies:
  ffmpeg: "{ffmpeg_info}"
  yt_dlp: "{ytdlp_info}"

server_configuration:
  active_server_id: "{active_server_id}"
  server_endpoint: "{server_info}"
  stream_quality: "{APP_CONFIG.get('audio_stream_quality', 'raw')}"
  video_target_resolution: "{APP_CONFIG.get('video_resolution', '1080p')}"
  video_adaptive_quality: {APP_CONFIG.get('video_auto_res', True)}
```"""
        return report

    @classmethod
    def print_diagnostics(cls):
        print(cls.generate_diagnostic_report())