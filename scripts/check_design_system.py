#!/usr/bin/env python3
"""
Design-System Compliance Check
Prüft, ob Vue-Pages das zentrale Design-System aus index.css verwenden.
"""
import os
import re
import sys

PAGES_DIR = "frontend/src/diakonos/pages"
FORBIDDEN_PATTERNS = [
    # Hartcodierte Tailwind-Farben, die durch Design-System-Tokens ersetzt werden sollten
    (r'\bbg-blue-\d+\b', 'bg-blue-*'),
    (r'\bbg-indigo-\d+\b', 'bg-indigo-*'),
    (r'\bbg-green-\d+\b', 'bg-green-*'),
    (r'\bbg-red-\d+\b', 'bg-red-*'),
    (r'\bbg-yellow-\d+\b', 'bg-yellow-*'),
    (r'\bbg-gray-\d+\b', 'bg-gray-*'),
    (r'\btext-blue-\d+\b', 'text-blue-*'),
    (r'\btext-indigo-\d+\b', 'text-indigo-*'),
    (r'\btext-green-\d+\b', 'text-green-*'),
    (r'\btext-red-\d+\b', 'text-red-*'),
    (r'\btext-yellow-\d+\b', 'text-yellow-*'),
    (r'\btext-gray-\d+\b', 'text-gray-*'),
    (r'\bborder-blue-\d+\b', 'border-blue-*'),
    (r'\bborder-indigo-\d+\b', 'border-indigo-*'),
    (r'\bborder-green-\d+\b', 'border-green-*'),
    (r'\bborder-red-\d+\b', 'border-red-*'),
    (r'\bborder-yellow-\d+\b', 'border-yellow-*'),
    (r'\bborder-gray-\d+\b', 'border-gray-*'),
]

def check_file(path):
    violations = []
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    has_dk_screen = 'class="dk-screen' in content or "class='dk-screen" in content
    has_page_class = 'class="page"' in content or "class='page'" in content

    if has_page_class:
        violations.append((0, "Root-Element nutzt noch '.page' statt '.dk-screen dk-screen-enter'"))

    for lineno, line in enumerate(lines, 1):
        # Überspringe Kommentare und script/style Blöcke (einfache Heuristik)
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
            continue
        for pattern, name in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                violations.append((lineno, f"Verbotene hartcodierte Farbe: {name}"))

    return violations, has_dk_screen

def main():
    if not os.path.isdir(PAGES_DIR):
        print(f"FEHLER: Verzeichnis {PAGES_DIR} nicht gefunden")
        sys.exit(1)

    total_violations = 0
    files_checked = 0

    for fname in sorted(os.listdir(PAGES_DIR)):
        if not fname.endswith('.vue'):
            continue
        fpath = os.path.join(PAGES_DIR, fname)
        violations, has_dk = check_file(fpath)
        files_checked += 1

        if violations:
            total_violations += len(violations)
            print(f"\n❌ {fname}")
            for lineno, msg in violations:
                print(f"   Zeile {lineno}: {msg}")
        else:
            print(f"✅ {fname}")

    print(f"\n{'='*60}")
    print(f"Dateien geprüft: {files_checked}")
    print(f"Verstöße: {total_violations}")

    if total_violations > 0:
        print("\nBitte hartcodierte Tailwind-Farben durch Design-System-Tokens ersetzen.")
        print("Siehe frontend/src/diakonos/index.css für verfügbare Klassen.")
        sys.exit(1)
    else:
        print("\nAlle Vue-Pages sind Design-System-konform.")
        sys.exit(0)

if __name__ == "__main__":
    main()
