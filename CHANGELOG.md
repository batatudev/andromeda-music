# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.0.0-rc1] - 2026-11-06 ("Sirrah")

### Added
- **Subsonic REST API Client:** Full compliance with Subsonic REST API v1.16.1 (Navidrome) featuring MD5 salt+token authentication and HTTP connection pooling.
- **Circuit Breaker Protection:** Automatic 60-second backoff upon 3 consecutive network failures to protect self-hosted servers from query flooding.
- **Hardware-Accelerated Video Ambient:** Live YouTube music video synchronization with GPU-driven GLSL shader blurring via QML `MultiEffect` (~2-3% CPU overhead).
- **Auto-Resolution-Fallback (ARF 3.1):** Adaptive bitrate management scaling video from 1080p down to 720p/480p and graceful soft-fallback to pure audio on buffer lag.
- **Zenith-Style Transfer Center:** Multi-state transfer queue with live physical NVMe storage meters, rate-limit circuit breakers, and batch downloads for playlists and albums.
- **Offline-First Architecture:** Local SQLite database in WAL mode allowing full library browsing and playback during network outages.
- **Desktop MPRIS2 Interface:** Complete remote playback, volume, and metadata control via standard Linux D-Bus desktop applets (`org.mpris.MediaPlayer2.AndromedaMusic`).
- **Dynamic PipeWire / PulseAudio Routing:** Automated handling of audio device switching (`media.role="music"`) without A/V desynchronization.
- **Diagnostics CLI:** Built-in `--diagnostics` and `--sysinfo` flags to instantly dump sanitized system, audio, and graphics telemetry for bug reporting.
- **Multi-Language Support:** Comprehensive internationalization support for Polish (`pl`) and English (`en`).
- **XDG Base Directory Compliance:** Strict sandboxing and isolation for configurations, caches, logs, and downloaded media.
- **Tiling Window Manager Support:** Zero-minimum-width responsive card layout (`ResponsiveCardRow`) preventing window geometry lockups in Hyprland, Sway, and i3.