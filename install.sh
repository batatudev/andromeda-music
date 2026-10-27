#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR_NAME="$(basename "${PROJECT_DIR}")"
VENV_DIR="${PROJECT_DIR}/.venv"

C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[32m'
C_BLUE='\033[34m'
C_YELLOW='\033[33m'
C_RED='\033[31m'

# Detekcja profilu instalacji (izolacja testowa vs produkcja)
IS_TEST_MODE=false
if [ "$1" == "--test" ] || [ "$1" == "-t" ]; then
    IS_TEST_MODE=true
elif [[ "${DIR_NAME}" =~ (test|preview|demo) ]]; then
    IS_TEST_MODE=true
fi

if [ "${IS_TEST_MODE}" = true ]; then
    APP_ID="andromeda-test"
    APP_NAME="Andromeda Music (Test)"
    echo -e "${C_BOLD}${C_YELLOW}======================================================================${C_RESET}"
    echo -e "${C_BOLD}${C_YELLOW}     ANDROMEDA MUSIC — INSTALATOR PROFILU TESTOWEGO (IZOLACJA)        ${C_RESET}"
    echo -e "${C_BOLD}${C_YELLOW}======================================================================${C_RESET}"
    echo -e "[TRYB] ${C_YELLOW}Wykryto bezpieczną kopię testową: ${APP_NAME} (${APP_ID})${C_RESET}"
    echo -e "[BEZPIECZEŃSTWO] Katalogi programu i baza danych będą odizolowane od głównej wersji.\n"
else
    APP_ID="andromeda-music"
    APP_NAME="Andromeda Music"
    echo -e "${C_BOLD}${C_BLUE}======================================================================${C_RESET}"
    echo -e "${C_BOLD}${C_BLUE}     ANDROMEDA MUSIC — INSTALATOR SYSTEMOWY LINUX (XDG)               ${C_RESET}"
    echo -e "${C_BOLD}${C_BLUE}======================================================================${C_RESET}"
    echo -e "[TRYB] ${C_GREEN}Profil standardowy: PRODUKCJA (${APP_ID})${C_RESET}\n"
fi

echo -e "Katalog instalacji: ${C_GREEN}${PROJECT_DIR}${C_RESET}\n"

# 1. Sprawdzenie Pythona
PYTHON_SYS="$(command -v python3 || true)"
if [ -z "${PYTHON_SYS}" ]; then
    echo -e "${C_RED}[BŁĄD] Nie znaleziono interpretera Python 3 w systemie!${C_RESET}" >&2
    exit 1
fi

PY_VER="$(${PYTHON_SYS} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo -e "[INFO] Wykryto interpreter: ${C_GREEN}${PYTHON_SYS}${C_RESET} (wersja ${PY_VER})"

# 2. Rozpoznanie menedżera pakietów dystrybucji
PKG_MANAGER=""
INSTALL_CMD=""

if command -v zypper >/dev/null 2>&1; then
    PKG_MANAGER="openSUSE (zypper)"
    INSTALL_CMD="sudo zypper install ffmpeg python3-pip python3-devel python3-gobject"
elif command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="Fedora / RHEL (dnf)"
    INSTALL_CMD="sudo dnf install ffmpeg python3-pip python3-devel python3-gobject"
elif command -v pacman >/dev/null 2>&1; then
    PKG_MANAGER="Arch Linux / Omarchy (pacman)"
    INSTALL_CMD="sudo pacman -S ffmpeg python-pip python-gobject"
elif command -v apt >/dev/null 2>&1; then
    PKG_MANAGER="Debian / Ubuntu (apt)"
    INSTALL_CMD="sudo apt install ffmpeg python3-pip python3-venv python3-gi"
else
    PKG_MANAGER="Niezależna dystrybucja Linux"
    INSTALL_CMD="Zainstaluj pakiety: ffmpeg, python3-pip, python3-gobject"
fi

echo -e "[INFO] Rozpoznano system: ${C_BLUE}${PKG_MANAGER}${C_RESET}"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${C_YELLOW}[OSTRZEŻENIE] Brak narzędzia 'ffmpeg' w systemie!${C_RESET}"
    echo -e "Zalecana instalacja przed pierwszym uruchomieniem:"
    echo -e "  ${C_BOLD}${INSTALL_CMD}${C_RESET}\n"
else
    echo -e "[OK] Narzędzie 'ffmpeg' jest zainstalowane."
fi

# 3. Wirtualne środowisko z flagą --system-site-packages
echo -e "\n[1/5] Przygotowywanie wirtualnego środowiska (.venv)..."
if [ ! -d "${VENV_DIR}" ]; then
    ${PYTHON_SYS} -m venv --system-site-packages "${VENV_DIR}"
    echo -e "[OK] Utworzono środowisko: ${VENV_DIR} (flaga --system-site-packages)"
else
    echo -e "[INFO] Istniejące środowisko .venv zostanie wykorzystane."
fi

# 4. Instalacja pakietów z pip
echo -e "\n[2/5] Weryfikacja i instalacja pakietów Pythona (pip)..."
"${VENV_DIR}/bin/python3" -m pip install --upgrade pip --quiet
"${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt" --quiet
echo -e "[OK] Pakiety z requirements.txt zainstalowane pomyślnie."

# 5. Wdrożenie początkowej konfiguracji XDG (~/.config/<APP_ID>/config.ini)
echo -e "\n[3/5] Weryfikacja i wdrażanie konfiguracji w ~/.config/${APP_ID}..."
CONFIG_DIR="${HOME}/.config/${APP_ID}"
mkdir -p "${CONFIG_DIR}"
if [ ! -f "${CONFIG_DIR}/config.ini" ]; then
    if [ -f "${PROJECT_DIR}/config.ini" ]; then
        cp "${PROJECT_DIR}/config.ini" "${CONFIG_DIR}/config.ini"
        echo -e "[OK] Wdrożono plik konfiguracyjny: ${CONFIG_DIR}/config.ini"
    elif [ -f "${PROJECT_DIR}/config.example.ini" ]; then
        cp "${PROJECT_DIR}/config.example.ini" "${CONFIG_DIR}/config.ini"
        echo -e "[OK] Zainicjalizowano plik konfiguracyjny z szablonu: ${CONFIG_DIR}/config.ini"
    fi
else
    echo -e "[INFO] Istniejący plik ${CONFIG_DIR}/config.ini został zachowany."
fi

# 6. Kopiowanie ikon XDG
echo -e "\n[4/5] Instalacja ikon aplikacji w standardzie XDG..."
ICON_SRC="${PROJECT_DIR}/assets/logo.png"
if [ -f "${ICON_SRC}" ]; then
    HICOLOR_DIR="${HOME}/.local/share/icons/hicolor/512x512/apps"
    PIXMAPS_DIR="${HOME}/.local/share/pixmaps"
    mkdir -p "${HICOLOR_DIR}" "${PIXMAPS_DIR}"

    cp "${ICON_SRC}" "${HICOLOR_DIR}/${APP_ID}.png"
    cp "${ICON_SRC}" "${PIXMAPS_DIR}/${APP_ID}.png"

    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 </dev/null || true
    fi
    echo -e "[OK] Zainstalowano ikonę pod identyfikatorem: ${APP_ID}.png"
fi

# 7. Rejestracja skrótu .desktop i launchera w ~/.local/bin
echo -e "\n[5/5] Rejestracja skrótu aplikacji w menu systemowym (KDE / GNOME)..."
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"
WRAPPER_FILE="${BIN_DIR}/${APP_ID}"

cat <<EOF > "${WRAPPER_FILE}"
#!/usr/bin/env bash
export ANDROMEDA_APP_ID="${APP_ID}"
export ANDROMEDA_APP_NAME="${APP_NAME}"
exec "${VENV_DIR}/bin/python3" "${PROJECT_DIR}/main.py" "\$@"
EOF

chmod +x "${WRAPPER_FILE}"
echo -e "[OK] Utworzono polecenie uruchomieniowe: ${WRAPPER_FILE}"

DESKTOP_DIR="${HOME}/.local/share/applications"
mkdir -p "${DESKTOP_DIR}"
DESKTOP_FILE="${DESKTOP_DIR}/${APP_ID}.desktop"

cat <<EOF > "${DESKTOP_FILE}"
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
GenericName=Odtwarzacz muzyki
Comment=Odtwarzacz muzyki z integracją Navidrome i YouTube
Exec=${WRAPPER_FILE}
Path=${PROJECT_DIR}
Icon=${APP_ID}
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupWMClass=${APP_ID}
EOF

chmod +x "${DESKTOP_FILE}"
echo -e "[OK] Utworzono plik skrótu: ${DESKTOP_FILE}"

# Odświeżenie baz systemowych z pełnym odcięciem deskryptorów i limitem czasu
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 </dev/null || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    timeout 2s kbuildsycoca6 >/dev/null 2>&1 </dev/null || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    timeout 2s kbuildsycoca5 >/dev/null 2>&1 </dev/null || true
fi

echo -e "\n${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}       SUKCES! ${APP_NAME} ZOSTAŁA ZAINSTALOWANA                      ${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "Aplikację możesz uruchomić:"
echo -e "  1. Z menu aplikacji KDE Plasma / GNOME (${APP_NAME})"
echo -e "  2. Wpisując w terminalu polecenie: ${C_BOLD}${APP_ID}${C_RESET}"
echo -e "  3. Bezpośrednio przez launcher: ${C_BOLD}${WRAPPER_FILE}${C_RESET}\n"

exit 0