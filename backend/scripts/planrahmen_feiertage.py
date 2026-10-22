"""
Erzeugt den Feiertags-Katalog als JSON fuer die Oberflaeche (K4).

Die Oberflaeche braucht die Feiertagsnamen, um Kennungen wie
``1_weihnachtstag`` lesbar anzuzeigen. Vorher fuehrte sie den Katalog in
EIGENEN, bereits abweichenden Listen (``editor.mjs``: „Gründonnerstag“,
``anlaesse.mjs``: „Gründonnerstag“/„Grüendonnerstag“-Streuung, „Buss-“).
Hier wird der Katalog aus ``feiertage.py`` einmal als JSON geschrieben; ein
Test prueft, dass die Datei aktuell ist, und ein Node-Test vergleicht sie mit
der Liste der Oberflaeche. So gibt es EINE Quelle und einen echten Vergleich.

Aufruf aus dem Repo-Wurzelverzeichnis:

    PYTHONPATH=backend/src python3 backend/scripts/planrahmen_feiertage.py

Zielort ist das Paket (``diakronos_app/planrahmen/doku/feiertage.json``), damit
die Datei im Image vorhanden ist — ``docs/`` fehlt dort (NACHTRAG DOCKER).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend" / "src"))

from diakronos_app.planrahmen.feiertage import FEIERTAGE  # noqa: E402

ZIEL = _ROOT / "backend" / "src" / "diakronos_app" / "planrahmen" / "doku" / "feiertage.json"


def katalog_text() -> str:
    """Der Katalog als stabiles JSON (gleiche Reihenfolge wie ``FEIERTAGE``)."""
    eintraege = [{"schluessel": f.schluessel, "name": f.name, "art": f.art} for f in FEIERTAGE]
    return json.dumps(eintraege, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    text = katalog_text()
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(text, encoding="utf-8")
    print(f"feiertage.json geschrieben: {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
