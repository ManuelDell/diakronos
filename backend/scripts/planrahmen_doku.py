"""Erzeugt die Referenz-Doku des Plan-Rahmens aus Schema + Registries.

Die Referenz liegt IM Python-Paket unter
``backend/src/diakronos_app/planrahmen/doku/REFERENZ.md``, damit sie im Image
vorhanden ist (``docs/`` steht in ``.dockerignore``; NACHTRAG DOCKER). Es gibt
keine Kopie in ``docs/planrahmen/`` mehr — dort steht nur ein Verweis
(``docs/planrahmen/README.md``), damit nichts auseinanderlaeuft.

Aufruf aus dem Repo-Wurzelverzeichnis:

    PYTHONPATH=backend/src python3 backend/scripts/planrahmen_doku.py

Die Datei wird von Hand NICHT gepflegt; ein Test prueft, dass sie zur aktuellen
Deklaration passt (siehe backend/tests/test_planrahmen_schema.py).
"""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

# src auf den Pfad, damit `diakronos_app` importierbar ist (auch ohne editable
# install, z. B. im Container oder auf dem Host).
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend" / "src"))

import diakronos_app.planrahmen  # noqa: E402
from diakronos_app.planrahmen.referenz import erzeuge_referenz  # noqa: E402

# Zielort: die Referenz-Datei direkt im Paket (dort liest sie der Test und die
# Laufzeit ueber importlib.resources). Das Skript laeuft auf dem Host/Container
# mit dem Quellbaum als Dateisystem, daher ist der Ressourcenpfad hier als
# echtes Path ansprechbar.
ZIEL = Path(str(resources.files(diakronos_app.planrahmen) / "doku" / "REFERENZ.md"))


def main() -> int:
    text = erzeuge_referenz()
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(text, encoding="utf-8")
    print(f"REFERENZ.md geschrieben: {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
