#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${PROJECT_DIR}/build_release"
RELEASE_NAME="andromeda-music"
RELEASE_DIR="${BUILD_DIR}/${RELEASE_NAME}"
ARCHIVE_NAME="andromeda-music-tester-preview.tar.gz"

C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[32m'
C_BLUE='\033[34m'
C_YELLOW='\033[33m'

echo -e "${C_BOLD}${C_BLUE}======================================================================${C_RESET}"
echo -e "${C_BOLD}${C_BLUE}    ANDROMEDA MUSIC — GENERATOR PACZKI DLA TESTERA (RELEASE)          ${C_RESET}"
echo -e "${C_BOLD}${C_BLUE}======================================================================${C_RESET}\n"

# 1. Czyszczenie poprzednich kompilacji
if [ -d "${BUILD_DIR}" ]; then
    rm -rf "${BUILD_DIR}"
fi
mkdir -p "${RELEASE_DIR}"

echo -e "[1/5] Kopiowanie struktury projektu..."

# Kopiowanie głównych plików wykonywalnych i modułów
cp "${PROJECT_DIR}/main.py" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/app.py" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/api_client.py" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/config.py" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/config.example.ini" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/mpris_adapter.py" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/requirements.txt" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/utils.py" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/install.sh" "${RELEASE_DIR}/"
cp "${PROJECT_DIR}/uninstall.sh" "${RELEASE_DIR}/"

# Kopiowanie instrukcji dla twórcy
if [ -f "${PROJECT_DIR}/INSTRUKCJA_TESTERA.md" ]; then
    cp "${PROJECT_DIR}/INSTRUKCJA_TESTERA.md" "${RELEASE_DIR}/"
fi

# Kopiowanie katalogów źródłowych
cp -r "${PROJECT_DIR}/core" "${RELEASE_DIR}/"
cp -r "${PROJECT_DIR}/engine" "${RELEASE_DIR}/"
cp -r "${PROJECT_DIR}/ui" "${RELEASE_DIR}/"
cp -r "${PROJECT_DIR}/views" "${RELEASE_DIR}/"
cp -r "${PROJECT_DIR}/lang" "${RELEASE_DIR}/"
cp -r "${PROJECT_DIR}/assets" "${RELEASE_DIR}/"

echo -e "\n[2/5] Przygotowywanie konfiguracji z fabrycznym serwerem Demo..."
# Przygotowanie gotowego config.ini z publicznym serwerem demo (tester nie musi nic konfigurować)
cp "${PROJECT_DIR}/config.example.ini" "${RELEASE_DIR}/config.ini"

echo -e "\n[3/5] Sanityzacja i czyszczenie plików deweloperskich..."
# Usunięcie zbędnych plików i cache
find "${RELEASE_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${RELEASE_DIR}" -type f -name "*.pyc" -delete
find "${RELEASE_DIR}" -type f -name "*.pyo" -delete
find "${RELEASE_DIR}" -type f -name "*.part" -delete
find "${RELEASE_DIR}" -type f -name "*.tmp" -delete
find "${RELEASE_DIR}" -type f -name "*.db*" -delete
find "${RELEASE_DIR}" -type f -name "*.log" -delete

# Nadanie praw wykonywalności
chmod +x "${RELEASE_DIR}/install.sh"
chmod +x "${RELEASE_DIR}/uninstall.sh"
chmod +x "${RELEASE_DIR}/main.py"

echo -e "\n[4/5] Pakowanie do archiwum .tar.gz z zachowaniem uprawnień..."
cd "${BUILD_DIR}"
tar -czf "${ARCHIVE_NAME}" "${RELEASE_NAME}"
cd "${PROJECT_DIR}"

OUTPUT_PATH="${PROJECT_DIR}/${ARCHIVE_NAME}"
mv "${BUILD_DIR}/${ARCHIVE_NAME}" "${OUTPUT_PATH}"
rm -rf "${BUILD_DIR}"

SIZE_MB="$(du -m "${OUTPUT_PATH}" | cut -f1)"

echo -e "\n${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}        PACZKA TESTOWA ZOSTAŁA POMYŚLNIE WYGENEROWANA!               ${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "Gotowy plik do wysłania: ${C_BOLD}${OUTPUT_PATH}${C_RESET} (~${SIZE_MB} MB)"
echo -e "\nPaczka zawiera:"
echo -e "  • Prekonfigurowany serwer publiczny demo Navidrome (działa od razu po instalacji)"
echo -e "  • Skrypty install.sh i uninstall.sh (zgodne z openSUSE, KDE Plasma 6 i Waylandem)"
echo -e "  • Przejrzysty przewodnik INSTRUKCJA_TESTERA.md\n"