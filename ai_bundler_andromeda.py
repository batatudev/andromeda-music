import os
import datetime
import re

PROJECT_DIR = "."
OUTPUT_FILE = "_AI_CURRENT_CODE.txt"

# Ignorujemy tylko katalogi systemowe, venv i cache
IGNORE_DIRS = {
    '.git', '__pycache__', 'venv', '.venv', 'env', '.env',
    'build', 'dist', '.idea', '.vscode', '.commandcode'
}

# Ignorujemy sam plik wyjściowy i skrypt pakujący
IGNORE_FILES = {
    OUTPUT_FILE,
    'ai_bundler.py', '.cursorrules', '.gitignore', 'AGENTS.md', '_ANDROMEDA_PROJECT_CONTEXT.md'
}

# Ignorujemy wyłącznie pliki binarne (obrazy, multimedia, bazy sqlite), aby nie uszkodzić kodowania UTF-8
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp',
    '.mp3', '.mp4', '.m4a', '.wav', '.flac', '.webm',
    '.db', '.sqlite', '.sqlite3', '.pyc', '.so', '.dll',
    '.exe', '.zip', '.tar', '.gz', '.7z', '.woff', '.woff2', '.ttf'
}

def is_text_file(filename):
    if filename in IGNORE_FILES:
        return False
    ext = os.path.splitext(filename)[1].lower()
    if ext in BINARY_EXTENSIONS:
        return False
    return True

def clean_code_for_ai(content):
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    return content.strip()

def generate_file_tree(startpath, file_stats):
    tree_lines = []
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        filtered_files = [f for f in files if is_text_file(f)]
        if not filtered_files and not dirs:
            continue

        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level

        basename = os.path.basename(root)
        if basename == "" or basename == ".":
            basename = "andromeda-music"

        tree_lines.append(f"{indent}📁 {basename}/")

        subindent = ' ' * 4 * (level + 1)
        for f in sorted(filtered_files):
            rel_path = os.path.relpath(os.path.join(root, f), startpath).replace('\\', '/')
            lines_info = ""
            if rel_path in file_stats:
                lines_info = f" ({file_stats[rel_path]} linii)"
            tree_lines.append(f"{subindent}📄 {f}{lines_info}")

    return "\n".join(tree_lines)

def bundle_project():
    total_chars = 0
    total_lines = 0
    collected_files = []

    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if is_text_file(file):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, PROJECT_DIR).replace('\\', '/')
                collected_files.append((filepath, rel_path))

    collected_files.sort(key=lambda item: item[1])

    # Krok 1: Wstępny odczyt i policzenie linii dla każdego pliku
    file_contents = {}
    file_stats = {}

    for filepath, rel_path in collected_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as infile:
                raw_text = infile.read()
                cleaned = clean_code_for_ai(raw_text)
                lines_cnt = len(cleaned.splitlines()) if cleaned else 0
                file_contents[rel_path] = cleaned
                file_stats[rel_path] = lines_cnt
                total_chars += len(cleaned)
                total_lines += lines_cnt
        except UnicodeDecodeError:
            # Pomijamy pliki, które okazały się binarne mimo braku rozszerzenia
            continue
        except Exception as e:
            file_contents[rel_path] = f"<!-- BŁĄD ODCZYTU: {e} -->"
            file_stats[rel_path] = 0

    # Krok 2: Generowanie pliku zbiorczego
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        outfile.write("<repository>\n")
        outfile.write(f"<!-- Zrzut repozytorium Andromeda Music wygenerowany: {timestamp} -->\n")
        outfile.write(f"<!-- Łącznie plików: {len(file_stats)} | Łącznie linii kodu: {total_lines} -->\n\n")

        outfile.write("<directory_tree>\n")
        outfile.write(generate_file_tree(PROJECT_DIR, file_stats))
        outfile.write("\n</directory_tree>\n\n")

        outfile.write("<files>\n")

        for rel_path, content in file_contents.items():
            lines_cnt = file_stats.get(rel_path, 0)
            outfile.write(f'<file path="{rel_path}" lines="{lines_cnt}">\n')
            outfile.write(content)
            outfile.write('\n</file>\n\n')

        outfile.write("</files>\n")
        outfile.write("</repository>\n")

    estimated_tokens = total_chars // 4

    print("=" * 60)
    print(f"✅ Zoptymalizowany plik gotowy: {OUTPUT_FILE}")
    print(f"📊 Statystyki ogólne: {len(file_stats)} plików, {total_lines} linii, {total_chars} znaków (~{estimated_tokens} tokenów).")
    print("=" * 60)

    # Krok 3: Raport największych plików do refaktoryzacji
    sorted_by_lines = sorted(file_stats.items(), key=lambda x: x[1], reverse=True)
    print("\n📈 TOP 15 NAJWIĘKSZYCH PLIKÓW (CEL DLA REFAKTORYZACJI):")
    print("-" * 60)
    for idx, (path, lines) in enumerate(sorted_by_lines[:15], 1):
        print(f"  {idx:2d}. {path:<42} : {lines:>5d} linii")
    print("-" * 60)

if __name__ == "__main__":
    bundle_project()
