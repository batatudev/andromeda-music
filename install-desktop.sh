#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Andromeda Music — Instalator integracji pulpitu (XDG) ==="
echo "Katalog projektu: ${PROJECT_DIR}"

PYTHON_BIN=""
if [ -x "${PROJECT_DIR}/.venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python3"
elif [ -x "${PROJECT_DIR}/venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_DIR}/venv/bin/python3"
else
    PYTHON_BIN="$(command -v python3 || true)"
fi

if [ -z "${PYTHON_BIN}" ]; then
    echo "BŁĄD: Nie znaleziono interpretera Python 3 w systemie ani środowisku wirtualnym!" >&2
    exit 1
fi

echo "Wykryty interpreter: ${PYTHON_BIN}"

ICON_DIR="${HOME}/.local/share/icons/hicolor/512x512/apps"
mkdir -p "${ICON_DIR}"
if [ -f "${PROJECT_DIR}/assets/logo.png" ]; then
    cp "${PROJECT_DIR}/assets/logo.png" "${ICON_DIR}/andromeda-music.png"
    echo "Zainstalowano ikonę: ${ICON_DIR}/andromeda-music.png"
fi

DESKTOP_DIR="${HOME}/.local/share/applications"
mkdir -p "${DESKTOP_DIR}"
DESKTOP_FILE="${DESKTOP_DIR}/andromeda-music.desktop"

cat <<EOF > "${DESKTOP_FILE}"
[Desktop Entry]
Version=1.0
Type=Application
Name=Andromeda Music
GenericName=Odtwarzacz muzyki
Comment=Odtwarzacz muzyki Andromeda z integracją Navidrome i YouTube
Exec=${PYTHON_BIN} ${PROJECT_DIR}/main.py
Path=${PROJECT_DIR}
Icon=andromeda-music
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupWMClass=andromeda-music
EOF

chmod +x "${DESKTOP_FILE}"
echo "Zarejestrowano skrót: ${DESKTOP_FILE}"

echo "Odświeżanie bazy aplikacji systemowych..."
update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true

echo "=== Sukces! Andromeda Music została pomyślnie zainstalowana w systemie. ==="