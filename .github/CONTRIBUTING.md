# Contributing to Andromeda Music

Thank you for your interest in contributing to **Andromeda Music**! We are committed to building a fast, lightweight, and cinematic music experience for the Linux desktop.

---

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please be respectful and considerate in all interactions.

---

## Development Setup

Andromeda Music runs natively on Linux using Python 3 and PySide6 (Qt6).

### 1. Clone the repository
```bash
git clone https://github.com/batatudev/andromeda-music.git
cd andromeda-music
```

### 2. Create a virtual environment
A virtual environment initialized with `--system-site-packages` is required for native D-Bus and MPRIS integration:
```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Run the automated test suite
Before making any changes, ensure all tests pass:
```bash
python3 tests/test_integrity.py
```

---

## Architectural Guidelines

To maintain rock-solid stability and zero-crash reliability, all contributions must adhere to the following principles:

1. **Zero-Blocking Main Thread:** Network calls (`requests`), SQLite queries, and file I/O must never run on the Qt GUI thread. Always use `main_window.run_async()`, `QThreadPool`, or dedicated worker threads.
2. **Audio-First Invariant:** Video fetching or rendering failures must never interrupt, stall, or terminate audio playback. Graceful degradation to pure audio is required.
3. **Hardware Acceleration:** Ambient video blurring must rely on GPU shaders via `QQuickWidget` and QML `MultiEffect`. Never use `QGraphicsBlurEffect` on live video frames.
4. **Strict XDG Standard:** Paths must resolve through `core.paths.PathsManager`. Never hardcode `/home/$USER` or relative paths.
5. **Clean Code & Internationalization:** All code, inline documentation, variable names, and commit messages must be written in English. User-facing strings must use `tr('key', 'Default text')` from `core.i18n`.

---

## Submitting Pull Requests

1. Fork the repository and create a descriptive branch:
   ```bash
   git checkout -b feature/amazing-feature
   ```
2. Make your changes and write automated tests if applicable.
3. Verify that tests pass:
   ```bash
   python3 tests/test_integrity.py
   python3 -m py_compile $(git ls-files '*.py')
   ```
4. Commit your changes with clear, concise messages.
5. Push to your fork and submit a Pull Request against the `main` branch.
```