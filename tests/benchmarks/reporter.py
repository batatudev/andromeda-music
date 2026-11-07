import os
os.environ["QT_API"] = "pyside6"

import csv
from pathlib import Path

class BenchmarkReporter:
    """
    Formatuje i generuje zestawienia porównawcze w terminalu, plikach Markdown oraz CSV.
    """

    @staticmethod
    def print_terminal_summary(internal_data: dict, live_data: dict):
        target = live_data.get('target', 'Aplikacja').upper() if live_data else "ANDROMEDA"
        print("\n" + "=" * 70)
        print(f"        RAPORT WYDAJNOŚCI SYSTEMOWEJ: {target}")
        print("=" * 70)

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
            print(f"  • Średnie CPU (Cały procesor):      {live_data.get('avg_cpu_total', 0):.2f} % (1 rdzeń: {live_data.get('avg_cpu_raw', 0):.2f} %)")
            print(f"  • Szczytowe CPU (Max spike):        {live_data.get('max_cpu_total', 0):.2f} % (1 rdzeń: {live_data.get('max_cpu_raw', 0):.2f} %)")
            print(f"  • Średnie GPU (Łączne obciążenie):  {live_data.get('avg_gpu_total', 0):.2f} %")
            print(f"      - GPU 3D / Shadery (Render):    {live_data.get('avg_gpu_render', 0):.2f} %")
            print(f"      - GPU Dekoder (VA-API Video):   {live_data.get('avg_gpu_video', 0):.2f} %")
            print(f"  • Prawdziwy narzut RAM (Średni PSS): {live_data.get('avg_pss_mb', 0):.2f} MB")
            print(f"  • Pamięć fizyczna (Średni RSS):     {live_data.get('avg_rss_mb', 0):.2f} MB")
            print(f"  • Szczyt pamięci (Max RSS):         {live_data.get('max_rss_mb', 0):.2f} MB")
            print(f"  • Liczba procesów systemowych:      {live_data.get('max_processes', 1)}")
            print(f"  • Średnia liczba wątków:            {live_data.get('avg_threads', 0)}")

        print("\n" + "=" * 70 + "\n")

    @staticmethod
    def print_multi_comparison_terminal(results_map: dict):
        col_w = 20
        total_w = 34 + len(results_map) * (col_w + 3)
        print("\n" + "=" * total_w)
        print("          ZESTAWIENIE PORÓWNAWCZE WYDAJNOŚCI ZASOBÓW (LINUX / WAYLAND)")
        print("=" * total_w)

        header = f"{'Metryka':<32}"
        for name in results_map.keys():
            n_short = name.replace("Andromeda", "Andr").replace("(", "").replace(")", "").strip()[:col_w]
            header += f" | {n_short:<{col_w}}"
        print(header)
        print("-" * total_w)

        def print_row(label, val_func):
            row = f"{label:<32}"
            for data in results_map.values():
                val_str = val_func(data)
                row += f" | {val_str:<{col_w}}"
            print(row)

        print_row("Czas startu (Cold Startup)", lambda d: f"{d.get('startup_time_sec', 0):.3f} s")
        print_row("Średnie CPU (Cały procesor)", lambda d: f"{d.get('avg_cpu_total', 0):.2f} %")
        print_row("Średnie CPU (1 rdzeń)", lambda d: f"{d.get('avg_cpu_raw', 0):.2f} %")
        print_row("Szczytowe CPU (Max Spike)", lambda d: f"{d.get('max_cpu_total', 0):.2f} %")
        print_row("Średnie GPU (Łączne)", lambda d: f"{d.get('avg_gpu_total', 0):.2f} %")
        print_row("  -> GPU 3D (Shadery)", lambda d: f"{d.get('avg_gpu_render', 0):.2f} %")
        print_row("  -> GPU Video (VA-API)", lambda d: f"{d.get('avg_gpu_video', 0):.2f} %")
        print_row("Pamięć rzeczywista (PSS)", lambda d: f"{d.get('avg_pss_mb', 0):.1f} MB")
        print_row("Pamięć fizyczna (RSS)", lambda d: f"{d.get('avg_rss_mb', 0):.1f} MB")
        print_row("Liczba procesów", lambda d: str(d.get('max_processes', 1)))
        print("=" * total_w + "\n")

    @staticmethod
    def generate_multi_comparison_markdown(results_map: dict, internal_data: dict = None, scenario: str = "video") -> str:
        md = []
        if scenario == "video":
            md.append("## Raport Porównawczy: Andromeda Music vs Konkurencja (Odtwarzanie Wideo)\n")
            md.append("*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), teledyski 1080p, standaryzowany pomiar jądra (/proc/smaps_rollup & DRM fdinfo)*\n")
        elif scenario == "playback":
            md.append("## Raport Porównawczy: Andromeda Music vs Konkurencja (Audio Playback)\n")
            md.append("*Środowisko testowe: Linux (Fedora / KDE Plasma / Wayland), 2 utwory (120s), pomiar jądra (/proc/smaps_rollup)*\n")
        else:
            md.append("## Raport Wydajnościowy: Andromeda Music (Tryb Spoczynku / Idle)\n")

        headers = ["Metryka"]
        for target in results_map.keys():
            headers.append(target)

        md.append("| " + " | ".join(headers) + " |")
        md.append("| " + " | ".join([":---" if i == 0 else ":---:" for i in range(len(headers))]) + " |")

        def make_row(title, val_func):
            row = [f"**{title}**"]
            for target, data in results_map.items():
                val = val_func(data)
                row.append(f"**{val}**" if "Andromeda" in target else f"{val}")
            return row

        md.append("| " + " | ".join(make_row("Czas startu (Cold Startup)", lambda d: f"{d.get('startup_time_sec', 0):.3f} s")) + " |")
        md.append("| " + " | ".join(make_row("Średnie CPU (Cały procesor)", lambda d: f"{d.get('avg_cpu_total', 0):.2f}%")) + " |")
        md.append("| " + " | ".join(make_row("Średnie CPU (1 rdzeń)", lambda d: f"{d.get('avg_cpu_raw', 0):.2f}%")) + " |")
        md.append("| " + " | ".join(make_row("Szczytowe CPU (Max Spike)", lambda d: f"{d.get('max_cpu_total', 0):.2f}%")) + " |")
        md.append("| " + " | ".join(make_row("Średnie GPU (Łączne)", lambda d: f"{d.get('avg_gpu_total', 0):.2f}%")) + " |")
        md.append("| " + " | ".join(make_row("GPU 3D (Shadery GLSL)", lambda d: f"{d.get('avg_gpu_render', 0):.2f}%")) + " |")
        md.append("| " + " | ".join(make_row("GPU Video (VA-API Dekoder)", lambda d: f"{d.get('avg_gpu_video', 0):.2f}%")) + " |")
        md.append("| " + " | ".join(make_row("Pamięć rzeczywista (PSS)", lambda d: f"{d.get('avg_pss_mb', 0):.1f} MB")) + " |")
        md.append("| " + " | ".join(make_row("Pamięć fizyczna (RSS)", lambda d: f"{d.get('avg_rss_mb', 0):.1f} MB")) + " |")
        md.append("| " + " | ".join(make_row("Liczba procesów systemowych", lambda d: str(d.get('max_processes', 1)))) + " |")

        if internal_data:
            md.append("\n### Wewnętrzne wskaźniki optymalizacji silnika Andromeda:\n")
            md.append(f"- **Inicjalizacja 50 utworów:** {internal_data.get('song_item_50_init_ms', 0):.1f} ms")
            md.append(f"- **Zapytanie bazy SQLite WAL (2000 utworów):** {internal_data.get('sqlite_wal_query_2000_ms', 0):.2f} ms")
            md.append(f"- **Pamięć trwała po 100 widżetach (Retained RAM):** {internal_data.get('retained_ram_100_widgets_kb', 0):.1f} KB\n")

        return "\n".join(md)

    @staticmethod
    def export_csv(data: dict, output_file: Path):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        samples = data.get("samples", [])
        if not samples:
            return
        keys = list(samples[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(samples)