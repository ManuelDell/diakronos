"""ON-3b — Ersteinrichtung ist kein Dauerzustand (Orchestrator-Nachtrag 2026-11-03).

Vertrag, den die Oberflaeche braucht:

* ``boot.einrichtung_offen`` ist ``True``, solange
  ``einrichtung_stand.assistent_abgeschlossen`` false ist, und ``False``
  danach. Die SPA leitet daraus ab, ob sie einen Admin beim Oeffnen der App
  auf den Assistenten fuehrt bzw. ob ``#/einrichtung`` ueberhaupt noch
  existiert (danach: ``#/einstellungen``).
* Ohne Stand-Zeile (niemand angelegt) ist der Wert ``False`` — es gibt keine
  Sitzung, die geleitet werden koennte; der EinrichtungsLINK fuehrt selbst.
* Ein Lesefehler ist ebenfalls ``False``: eine kaputte Statuszeile darf
  niemanden in einer Schleife festhalten (der Server prueft weiter selbst).

Datenbank: ausschliesslich ``patched_db`` (SQLite) — nie der Betrieb.
"""
from __future__ import annotations

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
import diakronos_app.spa as spa
from diakronos_app.models.einrichtung import EINRICHTUNG_STAND_NAME, EinrichtungStand


def _stand(patched_db, abgeschlossen: bool) -> None:
    from sqlalchemy.orm import Session

    sess: Session = patched_db()
    zeile = sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
    if zeile is None:
        zeile = EinrichtungStand(name=EINRICHTUNG_STAND_NAME)
        sess.add(zeile)
    zeile.assistent_abgeschlossen = abgeschlossen
    sess.commit()
    sess.close()


def test_offen_solange_nicht_abgeschlossen(patched_db):
    _stand(patched_db, False)
    assert spa._einrichtung_offen() is True


def test_geschlossen_nach_dem_abschluss(patched_db):
    _stand(patched_db, True)
    assert spa._einrichtung_offen() is False


def test_ohne_stand_zeile_geschlossen(patched_db):
    """Niemand angelegt -> keine Leitung (die Einrichtungsseite entscheidet)."""
    from sqlalchemy.orm import Session

    sess: Session = patched_db()
    zeile = sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
    if zeile is not None:
        sess.delete(zeile)
        sess.commit()
    sess.close()
    assert spa._einrichtung_offen() is False


def test_lesefehler_haelt_niemanden_fest(monkeypatch):
    """Ein kaputter Stand ist ``False`` (keine Endlos-Leitung), kein Absturz."""

    class Kaputt:
        def __enter__(self):
            raise RuntimeError("DB weg")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("diakronos_app.db.SessionLocal", lambda: Kaputt())
    assert spa._einrichtung_offen() is False


def test_boot_objekt_traegt_den_stand(patched_db):
    """Das Boot-Objekt der SPA nennt den Wert (eine Quelle fuer die Leitung)."""
    _stand(patched_db, False)
    boot = spa.boot_fuer_request()
    assert "einrichtung_offen" in boot, "Schluessel fehlt im Boot-Objekt"
    assert boot["einrichtung_offen"] is True

    _stand(patched_db, True)
    assert spa.boot_fuer_request()["einrichtung_offen"] is False


def test_admin_anlage_legt_die_stand_zeile_an(patched_db):
    """ON-3b: mit dem Admin beginnt die Ersteinrichtung (Zeile existiert).

    Sonst meldet `einrichtung_offen` beim ERSTEN Oeffnen der App ``False``
    (keine Zeile = kein Stand) und der frisch angelegte Admin landet NICHT im
    Assistenten — genau der Befund aus dem Wegwerf-Stack.
    """
    from diakronos_app.anmeldung.einrichtung_routen import _stand_anlegen

    # Vorher: keine Zeile -> geschlossen.
    sess = patched_db()
    zeile = sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
    if zeile is not None:
        sess.delete(zeile)
        sess.commit()
    sess.close()
    assert spa._einrichtung_offen() is False

    sess = patched_db()
    _stand_anlegen(sess)
    sess.commit()
    sess.close()
    assert spa._einrichtung_offen() is True, "Admin-Anlage legt keine Stand-Zeile an"

    # Idempotent: ein zweiter Aufruf darf einen laufenden Assistenten NICHT
    # zuruecksetzen.
    sess = patched_db()
    zeile = sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
    zeile.assistent_abgeschlossen = True
    sess.commit()
    _stand_anlegen(sess)
    sess.commit()
    sess.close()
    sess = patched_db()
    assert sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME).assistent_abgeschlossen is True
    sess.close()
