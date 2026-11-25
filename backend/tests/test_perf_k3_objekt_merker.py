"""PERF-K3 — die Rechte-Objekt-Zeile wird je Aufruf EINMAL gelesen.

Messung PERF-K3 (Postgres, 14 Kalender): `get_accessible_calendars` las je
(Kalender x Aktion) die Zeile aus `rechte_objekt` erneut — 71 von ~120
Abfragen. Jetzt merkt `kern._objekt` die Zeile (Schluessel
``("objekt", typ, objekt)``), und `rechte.vorladen` legt sie aus seiner
Sammelabfrage dort ab — auch das "gibt es nicht" (None).

Zusagen:
  1. Fuenf Aktionen an einem Objekt: EINE Abfrage auf rechte_objekt.
  2. Nach dem Vorabladen: KEINE Abfrage auf rechte_objekt mehr, auch nicht
     fuer Kalender ohne Rechte-Objekt (die bleiben `objekt_unbekannt`).
  3. Ein im selben Aufruf neu registriertes Objekt wirkt sofort (der Flush
     leert den Merker — das gemerkte None haelt nicht fest).
  4. Ohne Merkungsrahmen: jede Frage liest frisch.
"""
from __future__ import annotations

from sqlalchemy import event

from diakronos_app import rechte as R
from diakronos_app.frappe_compat.session import set_user

from test_perf_k2_vorladen import welt  # noqa: F401 — dieselbe Welt wie PERF-K2

AKTIONEN = (R.LESEN, R.SCHREIBEN, R.VORSCHLAGEN, R.MODERIEREN, R.VERWALTEN)


class _Zaehler:
    """Zaehlt SQL-Abfragen auf rechte_objekt (Tabelle im FROM)."""

    def __init__(self, engine):
        self.engine = engine
        self.n = 0

    def _zaehle(self, conn, cursor, statement, parameters, context, executemany):
        if "FROM rechte_objekt" in statement:
            self.n += 1

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._zaehle)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._zaehle)


def test_fuenf_aktionen_eine_objektabfrage(welt, engine):
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user("hv@x.org")
    with merkungsrahmen(), _Zaehler(engine) as z:
        antworten = [bool(R.darf("hv@x.org", a, "kalender", "KAL-A")) for a in AKTIONEN]
    assert z.n == 1, f"{z.n} Abfragen auf rechte_objekt statt 1"
    # Gegenprobe ohne Rahmen: gleiche Antworten.
    assert antworten == [bool(R.darf("hv@x.org", a, "kalender", "KAL-A")) for a in AKTIONEN]


def test_ohne_rahmen_liest_jede_frage_frisch(welt, engine):
    set_user("hv@x.org")
    with _Zaehler(engine) as z:
        for a in AKTIONEN:
            R.darf("hv@x.org", a, "kalender", "KAL-A")
    assert z.n >= len(AKTIONEN), "ohne Rahmen darf nichts gemerkt werden"


def test_nach_vorladen_keine_objektabfrage(welt, engine):
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    namen = ["KAL-A", "KAL-B", "KAL-C", "KAL-D"]
    erwartet = {(n, a): R.darf("mitglied@x.org", a, "kalender", n)
                for n in namen for a in AKTIONEN}
    set_user("mitglied@x.org")
    with merkungsrahmen() as merker:
        kalender_rechte_vorladen("mitglied@x.org", namen)
        assert merker[("objekt", "kalender", "KAL-C")] is None
        with _Zaehler(engine) as z:
            ist = {(n, a): R.darf("mitglied@x.org", a, "kalender", n)
                   for n in namen for a in AKTIONEN}
            stufen = R.erforderliche_stufen("kalender", "KAL-A")
    assert z.n == 0, f"{z.n} Abfragen auf rechte_objekt nach dem Vorabladen"
    assert {k: bool(v) for k, v in ist.items()} == {k: bool(v) for k, v in erwartet.items()}
    assert ist[("KAL-C", R.LESEN)].grund == "objekt_unbekannt"
    assert stufen == R.erforderliche_stufen("kalender", "KAL-A")


def test_neu_registriertes_objekt_wirkt_sofort(welt):
    from diakronos_app import db as _db
    from diakronos_app.models.rechte import RechteFreigabe, RechteObjekt
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    set_user("mitglied@x.org")
    aufruf = _db.SessionLocal()
    try:
        with merkungsrahmen() as merker, _db.als_aktuelle_sitzung(aufruf):
            kalender_rechte_vorladen("mitglied@x.org", ["KAL-C"])
            assert R.darf("mitglied@x.org", R.LESEN, "kalender", "KAL-C").grund == "objekt_unbekannt"
            aufruf.add(RechteObjekt(typ="kalender", objekt="KAL-C", gruppe="G-A",
                                    gemeinde_status="aus", gruppe_status="aus"))
            aufruf.add(RechteFreigabe(typ="kalender", objekt="KAL-C", gruppe="G-A",
                                      lesen=True, schreiben=False, moderieren=False))
            aufruf.flush()
            assert ("objekt", "kalender", "KAL-C") not in merker, "Flush hat den Merker nicht geleert"
            e = R.darf("mitglied@x.org", R.LESEN, "kalender", "KAL-C")
            assert e.grund != "objekt_unbekannt" and bool(e), e
    finally:
        aufruf.rollback()
        aufruf.close()
