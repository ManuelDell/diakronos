#!/usr/bin/env python3
"""
Import-Konsistenz-Check für Diakronos.

Prüft ob alle Namen, die in __init__.py via `from .module import name`
importiert werden, im jeweiligen Modul tatsächlich definiert sind.

Kein Frappe nötig – reine AST-Analyse.
"""

import ast
import sys
from pathlib import Path


def get_defined_names(filepath: Path) -> set[str]:
    """Gibt alle auf Modul-Ebene definierten Namen zurück (def, class, Variablen)."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError as e:
        print(f"  SYNTAX-FEHLER in {filepath}: {e}")
        return set()

    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
    return names


def check_init_file(init_path: Path) -> list[str]:
    """
    Prüft einen __init__.py auf Import-Konsistenz.
    Gibt Liste von Fehlermeldungen zurück.
    """
    errors = []
    try:
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [f"{init_path}: Syntax-Fehler – {e}"]

    package_dir = init_path.parent

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        # node.level == 0  → absoluter Import (z.B. "import frappe") → überspringen
        # node.level == 1  → "from .module import ..." → prüfen
        # node.level >= 2  → "from ..sibling import ..." → zu komplex, überspringen
        if node.level != 1 or not node.module:
            continue

        relative_module = node.module  # bei level=1 ist das bereits "module" ohne Punkt

        target_file = package_dir / f"{relative_module}.py"
        if not target_file.exists():
            # Könnte ein Paket sein
            target_file = package_dir / relative_module / "__init__.py"
            if not target_file.exists():
                errors.append(
                    f"{init_path}:{node.lineno}: "
                    f"Modul '.{relative_module}' nicht gefunden"
                )
                continue

        defined = get_defined_names(target_file)

        for alias in node.names:
            if alias.name == "*":
                continue  # wildcard-Import: nicht prüfbar
            if alias.name not in defined:
                errors.append(
                    f"{init_path}:{node.lineno}: "
                    f"'{alias.name}' existiert nicht in '.{relative_module}' "
                    f"(gefunden: {sorted(defined)[:5]}{'...' if len(defined) > 5 else ''})"
                )

    return errors


def syntax_check_all(root: Path) -> list[str]:
    """Prüft alle .py Dateien auf Syntax-Fehler."""
    errors = []
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        try:
            ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errors.append(f"{py_file}:{e.lineno}: Syntax-Fehler – {e.msg}")
    return errors


def main() -> int:
    root = Path(__file__).parent.parent  # Repo-Root

    print("=" * 60)
    print("Diakronos – Python CI Checks")
    print("=" * 60)

    # ── 1. Syntax-Check ──────────────────────────────────────────
    print("\n[1/2] Syntax-Check aller .py Dateien ...")
    syntax_errors = syntax_check_all(root)
    if syntax_errors:
        print(f"  ✗ {len(syntax_errors)} Fehler gefunden:")
        for e in syntax_errors:
            print(f"    {e}")
    else:
        py_count = sum(1 for f in root.rglob("*.py") if "__pycache__" not in f.parts)
        print(f"  ✓ {py_count} Dateien – keine Syntax-Fehler")

    # ── 2. Import-Konsistenz in __init__.py ──────────────────────
    print("\n[2/2] Import-Konsistenz in __init__.py ...")
    init_files = [
        f for f in root.rglob("__init__.py")
        if "__pycache__" not in f.parts
    ]
    import_errors = []
    for init_file in sorted(init_files):
        import_errors.extend(check_init_file(init_file))

    if import_errors:
        print(f"  ✗ {len(import_errors)} Fehler gefunden:")
        for e in import_errors:
            print(f"    {e}")
    else:
        print(f"  ✓ {len(init_files)} __init__.py Dateien – alle Imports konsistent")

    # ── Ergebnis ─────────────────────────────────────────────────
    total_errors = len(syntax_errors) + len(import_errors)
    print("\n" + "=" * 60)
    if total_errors:
        print(f"FEHLGESCHLAGEN – {total_errors} Problem(e) gefunden")
        return 1
    else:
        print("ERFOLGREICH – alle Checks bestanden")
        return 0


if __name__ == "__main__":
    sys.exit(main())
