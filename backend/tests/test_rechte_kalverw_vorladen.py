"""RECHTE-KALVERW — `get_kalender_verwaltung` fragt die Anlege-Rechte gesammelt.

Vorher lief je Gruppe und je Untergruppe ein eigenes `rechte.darf(ANLEGEN)` —
jedes mit 4–6 Einzelabfragen (Gruppe lebt? Modul an? Rolleneintrag?
Mitgliedschaft?). Bei 26 Gruppen der Gemeinde ergab das über hundert
Abfragen nur für die beiden Listen „wo darf ich Kalender anlegen“.

Jetzt legt `rechte.rollen_vorladen` dieselben Antworten in wenigen
Sammelabfragen ab; entschieden wird weiter über `rechte.darf`.

Zwei Zusagen:
  1. Die Zahl der Abfragen wächst NICHT mit der Zahl der Gruppen.
  2. Die Antwort ist dieselbe wie mit Einzelfragen ohne Merker.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

import diakronos_app.api  # noqa: E402,F401 — Registrierung

NUTZER = "leitung@x.org"


def _welt(sess, anzahl: int) -> None:
    """`anzahl` Gruppen mit je 2 Untergruppen; Kalender-Modul in jeder zweiten.

    Der Nutzer ist HV in G-00, GL in UG-01-a, Mitglied in G-02 und UG-03-b —
    so liefern beide Listen Treffer UND Nicht-Treffer.
    """
    sess.add(User(name=NUTZER, email=NUTZER, full_name="Lea Leitung", enabled=True))
    sess.add(Mitglied(name="M-lea", vorname="Lea", nachname="Leitung", email=NUTZER,
                      user=NUTZER, status="Mitglied", ausgeschlossen=0, docstatus=0, idx=0))
    for i in range(anzahl):
        g = f"G-{i:02d}"
        sess.add(Gruppe(name=g, gruppenname=f"Gruppe {i:02d}", ancestor_path=f"/{g}/",
                        docstatus=0, idx=0))
        for k in ("a", "b"):
            sess.add(Untergruppe(name=f"UG-{i:02d}-{k}", untergruppenname=f"UG {i:02d}{k}",
                                 gruppe=g, ancestor_path=f"/UG-{i:02d}-{k}/{g}/",
                                 docstatus=0, idx=0))
        if i % 2 == 0 or i == 1:
            sess.add(RechteModul(gruppe=g, modul="kalender"))
    sess.flush()
    sess.add_all([
        RechteGruppenrolle(gruppe="G-00", benutzer=NUTZER, rolle="HV"),
        RechteGruppenrolle(gruppe="G-01", untergruppe="UG-01-a", benutzer=NUTZER, rolle="GL"),
        Gruppenmitgliedschaft(name="GM-lea", parent="G-02", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-lea", status="Aktiv",
                              docstatus=0, idx=1),
        Untergruppenmitgliedschaft(name="UGM-lea", parent="UG-03-b", parenttype="Untergruppe",
                                   parentfield="mitglieder", mitglied="M-lea", status="Aktiv",
                                   docstatus=0, idx=1),
    ])
    sess.commit()


def _aufruf_gezaehlt(engine) -> tuple[dict, int]:
    from diakronos_app.api.kronos.kalender_verwaltung import get_kalender_verwaltung
    from diakronos_app.rechte.kern import merkungsrahmen

    zaehler = {"n": 0}

    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        zaehler["n"] += 1

    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        with merkungsrahmen():
            antwort = get_kalender_verwaltung()
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)
    return antwort, zaehler["n"]


@pytest.mark.parametrize("anzahl", [8, 26])
def test_kalverw_anlegelisten_wie_einzelfragen(patched_db, engine, anzahl) -> None:
    from diakronos_app import rechte

    sess = patched_db()
    _welt(sess, anzahl)
    set_user(NUTZER)
    antwort, _ = _aufruf_gezaehlt(engine)

    # Gegenprobe OHNE Merkungsrahmen: jede Frage einzeln, kein Vorrat.
    erwartet_g = [f"G-{i:02d}" for i in range(anzahl)
                  if rechte.darf(NUTZER, rechte.ANLEGEN, "kalender", gruppe=f"G-{i:02d}")]
    erwartet_u = [f"UG-{i:02d}-{k}" for i in range(anzahl) for k in ("a", "b")
                  if rechte.darf(NUTZER, rechte.ANLEGEN, "kalender",
                                 untergruppe=f"UG-{i:02d}-{k}")]
    assert sorted(antwort["anlegen_gruppen"]) == sorted(erwartet_g) == ["G-00"]
    # HV von G-00 legt in beiden Untergruppen an; GL von UG-01-a in seiner.
    assert sorted(antwort["anlegen_untergruppen"]) == sorted(erwartet_u) \
        == ["UG-00-a", "UG-00-b", "UG-01-a"]
    sess.close()


def test_kalverw_abfragen_wachsen_nicht_mit_den_gruppen(patched_db, engine) -> None:
    sess = patched_db()
    _welt(sess, 8)
    set_user(NUTZER)
    _, klein = _aufruf_gezaehlt(engine)
    # Dieselbe Welt um 18 Gruppen (36 Untergruppen) erweitern.
    for i in range(8, 26):
        g = f"G-{i:02d}"
        sess.add(Gruppe(name=g, gruppenname=f"Gruppe {i:02d}", ancestor_path=f"/{g}/",
                        docstatus=0, idx=0))
        for k in ("a", "b"):
            sess.add(Untergruppe(name=f"UG-{i:02d}-{k}", untergruppenname=f"UG {i:02d}{k}",
                                 gruppe=g, ancestor_path=f"/UG-{i:02d}-{k}/{g}/",
                                 docstatus=0, idx=0))
        if i % 2 == 0:
            sess.add(RechteModul(gruppe=g, modul="kalender"))
    sess.commit()
    _, gross = _aufruf_gezaehlt(engine)
    # Vorher: je zusaetzlicher Einheit mehrere Abfragen (54 Einheiten mehr ->
    # weit ueber 100). Jetzt: hoechstens eine Handvoll Unterschied.
    assert gross - klein <= 5, f"{klein} -> {gross} Abfragen"
    sess.close()
