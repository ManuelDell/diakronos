"""Bestandsuebernahme ins Rechtesystem — EINE Quelle fuer Migration, Demo und Tests.

Die Abbildung „alte Verantwortungs-/Leserechte-Zeilen -> HV/MV/GL, Module,
Objekte, Freigaben“ steht genau einmal: in ``uebernehmen()`` der Migration
``r1_rechte_kern``. Die Migration wendet sie beim Upgrade auf den Bestand an.

Wer NACH der Migration Daten am Rechtesystem vorbei anlegt (Demo-Seed
``tools/demo/musterhausen.py``, Test-Fixtures), ruft hier dieselbe Funktion —
sonst haette eine frische Demo Gruppen ohne HV, niemand duerfte dort anlegen und
Gruppenaufgaben waeren unsichtbar (R-12j, Befund aus UI-R9b).

``uebernehmen`` ist idempotent: bestehende Rollen, Objekte und Freigaben bleiben
unberuehrt, ergaenzt wird nur, was fehlt.

Der Pfad ist im Repo (``backend/src/diakronos_app/rechte`` -> ``backend/alembic``)
und im Image (``/app/src/diakronos_app/rechte`` -> ``/app/alembic``) derselbe:
drei Ebenen ueber diesem Paket.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "r1_rechte_kern.py"


def _modul():
    spec = importlib.util.spec_from_file_location("r1_rechte_kern_bestand", MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Migration r1_rechte_kern nicht gefunden: {MIGRATION}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def uebernehmen(sess) -> dict[str, int]:
    """Bestand auf der Verbindung der Sitzung ins Rechtesystem uebernehmen.

    Flusht vorher (damit eben angelegte Zeilen sichtbar sind), committet NICHT —
    das entscheidet der Aufrufer. Rueckgabe: Zaehler der neu angelegten Zeilen.
    """
    sess.flush()
    return _modul().uebernehmen(sess.connection())
