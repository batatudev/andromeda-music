#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR_NAME="$(basename "${PROJECT_DIR}")"
VENV_DIR="${PROJECT_DIR}/.venv"

C_RESET='\033[0m'
C_BOLD='\033[1m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_GREEN='\033[32m'

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
    echo -e "${C_BOLD}${C_YELLOW}     ANDROMEDA MUSIC — DEINSTALATOR PROFILU TESTOWEGO                 ${C_RESET}"
    echo -e "${C_BOLD}${C_YELLOW}======================================================================${C_RESET}"
    echo -e "[TRYB] ${C_YELLOW}Usuwanie wyłącznie instancji testowej: ${APP_NAME} (${APP_ID})${C_RESET}\n"
else
    APP_ID="andromeda-music"
    APP_NAME="Andromeda Music"
    echo -e "${C_BOLD}${C_RED}======================================================================${C_RESET}"
    echo -e "${C_BOLD}${C_RED}     ANDROMEDA MUSIC — DEINSTALATOR SYSTEMOWY (PRODUKCJA)             ${C_RESET}"
    echo -e "${C_BOLD}${C_RED}======================================================================${C_RESET}\n"
fi

echo -e "[1/3] Usuwanie integracji systemowej (${APP_ID})..."

DESKTOP_FILE="${HOME}/.local/share/applications/${APP_ID}.desktop"
if [ -f "${DESKTOP_FILE}" ]; then
    rm -f "${DESKTOP_FILE}"
    echo -e "[OK] Usunięto skrót: ${DESKTOP_FILE}"
fi

WRAPPER_FILE="${HOME}/.local/bin/${APP_ID}"
if [ -f "${WRAPPER_FILE}" ]; then
    rm -f "${WRAPPER_FILE}"
    echo -e "[OK] Usunięto polecenie terminala: ${WRAPPER_FILE}"
fi

HICOLOR_ICON="${HOME}/.local/share/icons/hicolor/512x512/apps/${APP_ID}.png"
if [ -f "${HICOLOR_ICON}" ]; then
    rm -f "${HICOLOR_ICON}"
fi

PIXMAP_ICON="${HOME}/.local/share/pixmaps/${APP_ID}.png"
if [ -f "${PIXMAP_ICON}" ]; then
    rm -f "${PIXMAP_ICON}"
fi
echo -e "[OK] Usunięto zarejestrowane ikony."

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 </dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 </dev/null || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    timeout 2s kbuildsycoca6 >/dev/null 2>&1 </dev/null || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    timeout 2s kbuildsycoca5 >/dev/null 2>&1 </dev/null || true
fi

echo -e "\n[2/3] Czyszczenie środowiska wirtualnego (.venv) i pamięci podręcznej..."
if [ -d "${VENV_DIR}" ]; then
    rm -rf "${VENV_DIR}"
    echo -e "[OK] Usunięto folder: ${VENV_DIR}"
fi

find "${PROJECT_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo -e "[OK] Usunięto pliki cache __pycache__."

echo -e "\n[3/3] Czyszczenie danych użytkownika profilu [${C_BOLD}${APP_ID}${C_RESET}]..."
echo -e "${C_YELLOW}Czy chcesz usunąć katalogi danych przypisane WYŁĄCZNIE do [${APP_ID}]?${C_RESET}"
echo -e "Katalogi do usunięcia:"
echo -e "  • Konfiguracja: ~/.config/${APP_ID}"
echo -e "  • Pobrane pliki (Audio/Wideo): ~/.local/share/${APP_ID}"
echo -e "  • Bazy SQLite i okładki: ~/.cache/${APP_ID}"
read -r -p "Usunąć dane profilu ${APP_ID}? [t/N]: " USER_CHOICE

case "${USER_CHOICE}" in
    [tT][aA][kK]|[tT]|[yY][eE][sS]|[yY])
        rm -rf "${HOME}/.config/${APP_ID}"
        rm -rf "${HOME}/.local/share/${APP_ID}"
        rm -rf "${HOME}/.cache/${APP_ID}"
        echo -e "${C_GREEN}[OK] Pomyślnie usunięto dane profilu: ${APP_ID}.${C_RESET}"
        ;;
    *)
        echo -e "[INFO] Dane profilu ${APP_ID} pozostały zachowane na dysku."
        ;;
esac

echo -e "\n${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}        DEINSTALACJA PROFILU ${APP_ID} ZAKOŃCZONA POMYŚLNIE           ${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}======================================================================${C_RESET}\n"

exit 0