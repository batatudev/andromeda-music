## Description

Please provide a clear and concise summary of the changes proposed in this Pull Request.

Fixes #(issue)

---

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change fixing an issue)
- [ ] ✨ New feature (non-breaking change adding functionality)
- [ ] ⚡ Performance optimization (rendering, memory, or caching)
- [ ] 📝 Documentation update (README, translations, docstrings)
- [ ] 🔧 Refactoring / Code hygiene

---

## Architectural Verification Checklist

Before submitting your PR, please verify that your changes adhere to Andromeda Music's core invariants:

- [ ] **Automated Tests:** Running `python3 tests/test_integrity.py` passes with zero errors.
- [ ] **Syntax Compilation:** Running `python3 -m py_compile $(git ls-files '*.py')` succeeds.
- [ ] **GUI Thread Safety:** Zero blocking I/O (network requests, SQLite queries, or disk writes) executed on the PySide6 main thread.
- [ ] **Audio-First Invariant:** Any failure in video stream resolving or playback gracefully falls back to pure audio without interrupting playback.
- [ ] **GPU Acceleration:** Live video effects use `QQuickWidget` and QML `MultiEffect` shaders (no `QGraphicsBlurEffect` on video).
- [ ] **XDG Compliance:** All paths resolve dynamically through `core.paths.PathsManager` (no hardcoded `/home/$USER` paths).
- [ ] **Internationalization:** All user-facing strings utilize `tr('key', 'Default text')` from `core.i18n`.
- [ ] **Linux Integration:** Tested under Wayland and/or X11 display servers.