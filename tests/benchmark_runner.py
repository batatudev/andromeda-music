import os
os.environ["QT_API"] = "pyside6"

import sys
import time
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.benchmarks.monitor import LinuxProcessMonitor, LinuxGpuMonitor
from tests.benchmarks.locator import TargetAppLocator, DEFAULT_YT_PLAYLIST_URL
from tests.benchmarks.internal import AndromedaInternalBenchmarks
from tests.benchmarks.runner import LiveProcessBenchmark
from tests.benchmarks.reporter import BenchmarkReporter

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
    parser = argparse.ArgumentParser(description="Andromeda Music Benchmark & Telemetry Runner")
    parser.add_argument(
        "--target",
        type=str,
        default="andromeda",
        help="Cel testu: 'andromeda', 'brave', 'firefox', 'compare', 'compare-video', 'matrix-ambient' lub lista po przecinku"
    )
    parser.add_argument("--scenario", choices=["idle", "playback", "video"], default="video", help="Scenariusz testu live")
    parser.add_argument("--video-mode", choices=["live-1080p", "live-480p", "offline"], default="live-1080p", help="Tryb wideo dla Andromedy")
    parser.add_argument("--playlist-name", type=str, default="benchmark2", help="Nazwa playlisty dla Andromedy")
    parser.add_argument("--warmup", type=int, default=15, help="Czas rozgrzewki bufora w sekundach (domyślnie 15s)")
    parser.add_argument("--duration", type=int, default=120, help="Czas trwania próbkowania (domyślnie 120s)")
    parser.add_argument("--yt-url", type=str, default=DEFAULT_YT_PLAYLIST_URL, help="Link do playlisty z wideo na YouTube Music")
    parser.add_argument("--save-md", action="store_true", help="Zapisz tabelę wyników do benchmark_report.md")
    parser.add_argument("--save-csv", action="store_true", help="Zapisz próbki telemetryczne do tests/results/")
    parser.add_argument("--setup-browsers", action="store_true", help="Uruchom kreator logowania profili przeglądarek")
    args = parser.parse_args()

    if args.setup_browsers:
        setup_browser_profiles()
        return

    internal_results = {}
    results_map = {}
    target_arg = args.target.strip()

    if target_arg == "matrix-ambient":
        configs_to_run = [
            ("andromeda", "live-1080p", "Andromeda Video (RAW - Bez efektów)", 0, 0),
            ("andromeda", "live-1080p", "Andromeda Video (+ Przyciemnienie 30%)", 0, 30),
            ("andromeda", "live-1080p", "Andromeda Video (+ Blur 40)", 40, 0),
            ("andromeda", "live-1080p", "Andromeda Video (Full Ambient 40/30%)", 40, 30)
        ]
        args.scenario = "video"
    elif target_arg == "compare-video":
        configs_to_run = [
            ("andromeda", "live-1080p", "Andromeda (Video 1080p Live)", None, None),
            ("andromeda", "live-480p", "Andromeda (Video 480p Live)", None, None),
            ("andromeda", "offline", "Andromeda (Video Offline)", None, None),
            ("brave", None, "Brave (YouTube Music)", None, None),
            ("firefox", None, "Firefox (YouTube Music)", None, None)
        ]
        args.scenario = "video"
    elif target_arg == "compare":
        configs_to_run = [
            ("andromeda", args.video_mode, None, None, None),
            ("feishin", None, None, None, None),
            ("spotify", None, None, None, None),
            ("brave", None, None, None, None),
            ("firefox", None, None, None, None)
        ]
    else:
        raw_targets = [t.strip().lower() for t in target_arg.split(",") if t.strip()]
        configs_to_run = [
            (t, args.video_mode if t == "andromeda" else None, None, None, None)
            for t in raw_targets
        ]

    if any(c[0] == "andromeda" for c in configs_to_run):
        print("[INFO] Uruchamianie wewnętrznych mikrobenchmarków Andromedy...")
        internal_results = AndromedaInternalBenchmarks.run_all_internal()

    for item in configs_to_run:
        target = item[0]
        v_mode = item[1]
        custom_label = item[2]
        blur_val = item[3]
        opacity_val = item[4]

        app_cmd, is_flatpak, flatpak_id, _ = TargetAppLocator.resolve_app(
            target,
            scenario=args.scenario,
            video_mode=v_mode,
            playlist_name=args.playlist_name,
            yt_url=args.yt_url,
            blur_val=blur_val,
            opacity_val=opacity_val
        )

        if not app_cmd:
            print(f"[OSTRZEŻENIE] Program '{target}' nie został znaleziony w systemie. Pomijam.")
            continue

        label_str = custom_label or f"{target.upper()}{f' ({v_mode})' if v_mode else ''}"
        print(f"\n[INFO] Uruchamianie testu: {label_str} (Scenariusz={args.scenario}, warmup: {args.warmup}s, czas: {args.duration}s)...")

        runner = LiveProcessBenchmark(
            target_name=target,
            app_cmd=app_cmd,
            is_flatpak=is_flatpak,
            flatpak_app_id=flatpak_id,
            duration_sec=args.duration,
            warmup_sec=args.warmup,
            scenario=args.scenario,
            video_mode=v_mode,
            playlist_name=args.playlist_name,
            display_label=custom_label
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
        for target_name, data in results_map.items():
            safe_name = target_name.replace(" ", "_").replace("(", "").replace(")", "").replace("+", "").replace("-", "_").lower()
            BenchmarkReporter.export_csv(data, res_dir / f"{safe_name}_{args.scenario}_{ts}.csv")
        print(f"[SUKCES] Zapisano próbki telemetryczne CSV do: {res_dir}")

if __name__ == "__main__":
    main()