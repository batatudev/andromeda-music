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

# Kopiowanie ikony do standardów XDG oraz pixmaps
ICON_SRC="${PROJECT_DIR}/assets/logo.png"
if [ -f "${ICON_SRC}" ]; then
    HICOLOR_DIR="${HOME}/.local/share/icons/hicolor/512x512/apps"
    PIXMAPS_DIR="${HOME}/.local/share/pixmaps"
    mkdir -p "${HICOLOR_DIR}" "${PIXMAPS_DIR}"
    
    cp "${ICON_SRC}" "${HICOLOR_DIR}/andromeda-music.png"
    cp "${ICON_SRC}" "${PIXMAPS_DIR}/andromeda-music.png"
    
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
    fi
    echo "Zainstalowano ikonę w katalogach systemowych XDG."
fi

# Generowanie pliku .desktop z bezpośrednią ścieżką do ikony
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
Icon=${ICON_SRC}
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupWMClass=andromeda-music
EOF

chmod +x "${DESKTOP_FILE}"
echo "Zarejestrowano skrót: ${DESKTOP_FILE}"

# Odświeżenie bazy aplikacji systemowych w KDE Plasma
echo "Odświeżanie bazy aplikacji..."
update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true

echo "=== Sukces! Ikona i skrót Andromeda Music działają poprawnie. ==="