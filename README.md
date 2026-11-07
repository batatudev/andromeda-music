<div align="center">

<img src="assets/logo.png" alt="Andromeda Music Logo" width="140" height="140" />

# Andromeda Music
### *High-performance Linux music player & ambient video visualizer for Navidrome & YouTube*

[![Version](https://img.shields.io/badge/Release-v1.0.0--rc1%20%22Sirrah%22-8A2BE2.svg?style=flat-square)](https://github.com/batatudev/andromeda-music/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![GUI: PySide6 / Qt6](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-41CD52.svg?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20(Wayland%20%2F%20X11)-FCC624.svg?style=flat-square&logo=linux&logoColor=black)](https://www.kernel.org/)
[![Audio: PipeWire & PulseAudio](https://img.shields.io/badge/Audio-PipeWire%20%2F%20PulseAudio-00A4DC.svg?style=flat-square)](https://pipewire.org/)

<p align="center">
  <a href="#why-i-built-andromeda-music">Why I Built It</a> •
  <a href="#the-manifesto">Manifesto</a> •
  <a href="#key-features">Key Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#system-requirements">Requirements</a> •
  <a href="#license">License</a>
</p>

</div>

---

## Why I Built Andromeda Music (Author's Note)

> *"I created Andromeda Music because none of the existing Linux music players met my expectations. The available apps were either sluggish Electron wrappers consuming gigabytes of RAM or bloated with cluttered, dated menus — and none offered unique visual features like a cinematic ambient music video backdrop.*
>
> *It all started out of pure curiosity: 'Can I use AI as an engineering partner to build a simple Python script to play music from my private Navidrome server?' What began as a weekend experiment turned into over half a year of dedicated development, hundreds of hours of fine-tuning, and more than 130 commits.*
>
> *At a certain point, I realized this project had evolved into a full-fledged, rock-solid desktop application that outshines existing alternatives. I decided to polish it to production standards, publish the code, and give back to the Linux open-source community."*
>
> — **batatudev**, Creator of Andromeda Music

---

## The Manifesto: Native, Lightweight & Independent

* **Say NO to Electron Bloat:** Web-wrapped desktop players easily consume 800 MB to 1.5 GB of RAM just to play an audio track. Andromeda Music is written natively in **Python 3 and PySide6 (Qt6)**. It utilizes direct GPU hardware shaders via **Qt RHI and QML MultiEffect**, sipping just **~120 MB of RAM** and maintaining **<450 ms cold startup times**.
* **Zero Walled Gardens (Self-Hosted Freedom):** Your music library lives on your own self-hosted **Navidrome / Subsonic** server. No streaming platform can revoke your favorite albums due to regional licensing deals.
* **Cinematic Video with True Audio-First Reliability:** YouTube music videos provide a gorgeous, blurred kinetic ambiance behind your tracks. However, audio is sacred: network drops or video glitches will **never interrupt or stall your music playback**.

---

## Key Features

### 1. ⚡ Native Lightweight Performance (Zero Electron)
* **Spotify Dark Ergonomics:** Clean, distraction-free interface engineered for usability and visual harmony.
* **Tiling Window Manager Ready:** Built with flexible, non-breaking card containers (`ResponsiveCardRow`) with zero rigid width locks. Scales effortlessly from full-screen 4K desktops down to narrow split-views in **Hyprland, Sway, i3, KDE Plasma, and GNOME**.
* **Fractional Scaling on Wayland:** Crisp vector iconography (QtAwesome) and high-DPI cover art rendering at 125%, 150%, 175%, and 200% scale factors.

### 2. 🎵 Hi-Fi Lossless Audio & Offline-First Browsing
* **Direct Stream Playback:** Native bitstream playback of **FLAC, ALAC, Opus, AAC, and MP3** files directly from your server without lossy server-side transcoding.
* **Instant SQLite WAL Cache:** Library browsing is backed by a local SQLite database running in Write-Ahead Logging (WAL) mode. If your server goes down or your Wi-Fi drops, Andromeda switches to **Offline-First fallback** instantly without throwing errors.
* **Multi-Server Partitioning:** Connect to multiple Navidrome servers with fully isolated caches, offline databases, and custom artwork per profile.

### 3. 🎬 Cinematic Video Ambient (GPU Zero-Copy)
* **One-Click Video Switcher:** Seamlessly toggle between album cover art and live synchronized YouTube music videos.
* **Hardware-Accelerated GLSL Blur:** Ambient live video blurring runs entirely on your GPU shaders via QML `MultiEffect`. It consumes only **2–3% CPU** (compared to software blur filters that saturate modern CPUs at 100%).
* **Auto-Resolution-Fallback (ARF 3.1):** An adaptive watchdog continuously monitors buffer health. During network throttling, it gracefully steps down video resolution (`1080p` $\to$ `720p` $\to$ `480p` $\to$ pure audio mode) to guarantee uninterrupted music.
* **Sub-Second PURL Range Sniffing:** Extracts YouTube video links from audio file ID3 tags using partial 256 KB HTTP Range requests without downloading entire audio files.

### 4. 💾 Zenith-Style Offline Storage & Download Center
* **Complete Offline Storage Control:** No hidden black-box caches. You have full visibility over downloaded music and video files.
* **Physical NVMe Storage Meter:** Real-time visual disk bar showing exact space consumed by audio, videos, and remaining storage on your drive.
* **One-Click Bulk Downloads:** Download entire playlists, full albums, artist discographies, or liked songs in one click — available as raw audio or 1080p video files.
* **Smart Background Queue:** Features multi-state filtering (Downloading, Queued, Completed, Errors), temporary file (`.part`) sanitization, and automatic rate-limit circuit breakers.

### 5. 🐧 True Linux Desktop Citizen
* **Native MPRIS2 D-Bus:** Full playback control, volume synchronization, track metadata, and cover art displayed in KDE Plasma audio applets, GNOME Media Controls, Waybar, Polybar, and `playerctl`.
* **Dynamic PipeWire / PulseAudio Routing:** Properly sets stream role (`media.role="music"`) and gracefully handles on-the-fly output device switching (Bluetooth headphones, USB DACs, speakers).
* **Strict XDG Standard Compliance:** Completely clean home directory. All files reside in standard directories: `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, and `$XDG_CACHE_HOME`.

---

## User Interface

<div align="center">
  <img src="assets/screenshots/now_playing.png" alt="Now Playing View with Cinematic Ambient Blur" width="85%" />
  <p><em>Now Playing screen with GPU-accelerated live video ambient blur</em></p>
</div>

<div align="center">
  <img src="assets/screenshots/home_grid.png" alt="Andromeda Music Home Library View" width="48%" />
  <img src="assets/screenshots/downloads_view.png" alt="Zenith-style Download and Storage Center" width="48%" />
  <p><em>Responsive Library Grid (Left) and Offline Storage & Download Center (Right)</em></p>
</div>

---

## Installation

### Method 1: Universal Linux Installer (Recommended)

Clone the repository and run the automated installer script. It sets up an isolated Python virtual environment with system D-Bus bindings and registers desktop launchers:

```bash
# 1. Clone the repository
git clone https://github.com/batatudev/andromeda-music.git
cd andromeda-music

# 2. Run the Linux installation script
./install.sh
```

Launch Andromeda Music from your application launcher (KDE / GNOME / Rofi) or via terminal:
```bash
andromeda-music
```

### Method 2: Manual Development Setup

If you prefer to configure your own environment:

```bash
# Create virtual environment with system site-packages (required for D-Bus / MPRIS)
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run the automated integrity test suite
python3 tests/test_integrity.py

# Run the application
python3 main.py
```

### Method 3: Flatpak (Flathub)
> *Flatpak package manifest (`io.github.batatudev.AndromedaMusic`) is currently being prepared for official Flathub submission.*

---

## System Requirements

| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| **Operating System** | Linux (Kernel 5.15+, glibc 2.35+) | Fedora 40+, Arch Linux, Ubuntu 24.04+, openSUSE |
| **Display Server** | X11 or Wayland | Wayland (KDE Plasma 6, GNOME 46+, Hyprland) |
| **Python** | 3.10 | 3.11 or 3.12 |
| **Audio Server** | PulseAudio | PipeWire with WirePlumber |
| **External Utilities** | `ffmpeg` | `ffmpeg` 6.0+ |
| **GPU Acceleration** | OpenGL 3.3 / Mesa Drivers | Intel (VA-API), AMD (RADV), Nvidia (GBM) |

---

## Configuration & Data Paths

All configuration is managed through the in-app **Settings** view and stored in strict compliance with the XDG Base Directory specification:
* **Configuration:** `~/.config/andromeda-music/config.ini`
* **Data & Downloads:** `~/.local/share/andromeda-music/`
* **Caches & Databases:** `~/.cache/andromeda-music/`

### YouTube Anti-Bot & Cookies Configuration
If your IP address encounters YouTube rate-limiting (HTTP 429), place an exported Netscape `cookies.txt` file into your data directory to bypass verification:
```bash
cp /path/to/exported/cookies.txt ~/.local/share/andromeda-music/cookies.txt
```
Andromeda will automatically detect and prioritize this file for all streaming and download operations.

---

## Contributing

Contributions, bug reports, and feedback are warmly welcomed!
1. Check existing issues or open a new one to discuss suggestions.
2. Fork the repository and create your feature branch: `git checkout -b feature/awesome-feature`.
3. Verify that the test suite passes: `python3 tests/test_integrity.py`.
4. Commit your changes and open a Pull Request.

---

## License

This project is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.  
See the [LICENSE](LICENSE) file for the full license text.

Copyright (C) 2026 **batatudev** and Andromeda Music Authors.