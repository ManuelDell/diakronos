# scripts/get_hashed_asset.py
# Gibt NUR den korrekten Browser-Pfad zurück (ohne /public/)

import os
import glob
import sys
from pathlib import Path

def get_app_name():
    hooks_path = Path(__file__).parent.parent / "hooks.py"
    if not hooks_path.exists():
        raise FileNotFoundError(f"hooks.py nicht gefunden: {hooks_path}")

    with open(hooks_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('app_name ='):
                return line.split('=')[1].strip().strip('"').strip("'")
    raise ValueError("app_name nicht in hooks.py gefunden")

def find_latest_hashed_file(base_name: str, extension="css") -> str:
    app_name = get_app_name()
    dist_dir = Path(__file__).parent.parent / "public" / "dist"

    pattern = str(dist_dir / "**" / f"{base_name}*.{extension}")
    files = glob.glob(pattern, recursive=True)

    if not files:
        raise FileNotFoundError(f"Keine Datei gefunden, die mit '{base_name}' beginnt in {dist_dir}")

    latest_file = max(files, key=os.path.getmtime)
    # Relativen Pfad ab /public/dist berechnen → dist/...
    relative_path = Path(latest_file).relative_to(dist_dir.parent)  # bis public
    url = f"/assets/{app_name}/{relative_path.as_posix()}"
    return url

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python get_hashed_asset.py <basisname>")
        print("Beispiel: python get_hashed_asset.py kronos.bundle.css")
        sys.exit(1)

    base_name = sys.argv[1]
    extension = "css" if base_name.endswith(".css") else "js" if base_name.endswith(".js") else "css"
    base_name = base_name.rsplit(".", 1)[0]  # Endung entfernen

    try:
        hashed_url = find_latest_hashed_file(base_name, extension)
        print(hashed_url)  # Nur der reine Pfad
    except Exception as e:
        print(f"Fehler: {e}")
        sys.exit(1)