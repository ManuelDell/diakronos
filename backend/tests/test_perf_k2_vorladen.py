"""PERF-K2 — Merker je Aufruf in Kalender-Funktionen: Zusagen und Rutschfestigkeit.

Die neuen Vorab-Ladungen (`rechte.vorladen`) legen Antworten unter den
Schluesseln ab, die `rechte.kern._gemerkt` benutzt. Vier Dinge muessen dabei
gelten — alle hier festgehalten:

  1. OHNE Merkungsrahmen (Skripte, CLI, Tests ohne Request) tut das Vorabladen
     NICHTS, und jede Frage wird frisch gerechnet.
  2. Ein Schreibvorgang im selben Aufruf (Flush/Commit/`sess.execute(delete)`)
     leert den Merker: eine entzogene Freigabe wirkt SOFORT — auch wenn sie
     eben erst vorabgeladen wurde.
  3. Das Vorabladen ueberschreibt NIE eine vorhandene Antwort.
  4. Kalender ohne Rechte-Objekt werden NICHT vorab beantwortet; dort bleibt
     die Einzelfrage zustaendig (und antwortet wie bisher `objekt_unbekannt`).
"""
from __future__ import annotations

import pytest

from diakronos_app import rechte as R
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
from diakronos_app.models.kronos import Kalender
from diakronos_app.models.rechte import (
    RechteFreigabe,
    RechteGruppenrolle,
    RechteModul,
    RechteObjekt,
)


@pytest.fixture()
def welt(patched_db):
    """Zwei Gruppen, drei Kalender: A (eigene), B (fremde Gruppe, nur lesen),
    C (gar kein Rechte-Objekt), D (eigene Gruppe, NUR moderieren — kein
    Schreibrecht: der Fall aus PERF-K2b/SOLL 2)."""
    s = patched_db()
    for name in ("hv@x.org", "mitglied@x.org", "moderator@x.org"):
        s.add(User(name=name, email=name, enabled=1))
        s.add(Mitglied(name=f"M-{name}", vorname=name[:2], nachname="X",
                       email=name, user=name, status="Aktiv"))
    s.add_all([Gruppe(name="G-A", gruppenname="A"),
               Gruppe(name="G-B", gruppenname="B")])
    s.flush()
    s.add_all([
        Gruppenmitgliedschaft(name="gm-1", parent="G-A", parentfield="mitglieder",
                              mitglied="M-hv@x.org", status="Aktiv"),
        Gruppenmitgliedschaft(name="gm-2", parent="G-A", parentfield="mitglieder",
                              mitglied="M-mitglied@x.org", status="Aktiv"),
        Gruppenmitgliedschaft(name="gm-3", parent="G-B", parentfield="mitglieder",
                              mitglied="M-mitglied@x.org", status="Aktiv"),
        Gruppenmitgliedschaft(name="gm-4", parent="G-A", parentfield="mitglieder",
                              mitglied="M-moderator@x.org", status="Aktiv"),
        RechteGruppenrolle(gruppe="G-A", benutzer="hv@x.org", rolle="HV"),
        RechteModul(gruppe="G-A", modul="kalender"),
        RechteModul(gruppe="G-B", modul="kalender"),
    ])
    s.add_all([Kalender(name="KAL-A", calendar_name="Kalender A"),
               Kalender(name="KAL-B", calendar_name="Kalender B"),
               Kalender(name="KAL-C", calendar_name="Kalender C"),
               Kalender(name="KAL-D", calendar_name="Kalender D")])
    s.flush()
    s.add_all([
        RechteObjekt(typ="kalender", objekt="KAL-A", gruppe="G-A",
                     gemeinde_status="aus", gruppe_status="aus"),
        RechteObjekt(typ="kalender", objekt="KAL-B", gruppe="G-B",
                     gemeinde_status="aus", gruppe_status="aus"),
        RechteObjekt(typ="kalender", objekt="KAL-D", gruppe="G-A",
                     gemeinde_status="aus", gruppe_status="aus"),
        RechteFreigabe(typ="kalender", objekt="KAL-A", gruppe="G-A",
                       lesen=True, schreiben=True, moderieren=True),
        RechteFreigabe(typ="kalender", objekt="KAL-B", gruppe="G-B",
                       lesen=True, schreiben=False, moderieren=False),
        # SOLL 2: Moderation OHNE Schreibfreigabe — `write` in der Liste ist
        # hier true, `darf(SCHREIBEN)` aber false. Genau daran vergiftete der
        # Nachtrag aus R1 den Merker.
        RechteFreigabe(typ="kalender", objekt="KAL-D", gruppe="G-A",
                       lesen=True, schreiben=False, moderieren=True),
    ])
    s.commit()
    return s


def _liste(sitzung) -> dict[str, dict]:
    """`get_accessible_calendars` in der Sitzung der Fixture (wie ein Request)."""
    from diakronos_app.api.kronos.permissions import get_accessible_calendars
    from diakronos_app.db import als_aktuelle_sitzung

    with als_aktuelle_sitzung(sitzung):
        return {c["name"]: c for c in get_accessible_calendars()}


def test_ohne_merkungsrahmen_wird_nichts_vorabgeladen(welt):
    """Skripte/CLI: ohne Rahmen keine Wirkung — die Antwort bleibt dieselbe."""
    from diakronos_app.rechte.kern import _MERKER
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    set_user("hv@x.org")
    assert _MERKER.get() is None
    kalender_rechte_vorladen("hv@x.org", ["KAL-A", "KAL-B", "KAL-C"])
    assert _MERKER.get() is None, "ohne Rahmen darf kein Merker entstehen"
    # Und die Liste ist dieselbe wie mit Vorabladen (siehe Gleichheitstest).
    assert _liste(welt)["KAL-A"]["is_moderator"] is True


def test_vorabladen_belegt_die_schluessel(welt):
    """Sonst waere der Gleichheitstest leer: die Schluessel muessen stehen.

    Und zwar mit WERTEN, nicht nur als Schluessel: der Vorrat muss genau das
    enthalten, was der Kern ohne Merker rechnet (R1/SOLL 2).
    """
    from diakronos_app.rechte import kern as K
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    frisch = {
        name: (K._darf_roh("hv@x.org", K.LESEN, "kalender", name),
               K._pruefstufen_roh("hv@x.org", "kalender", name),
               K._moderationsstufen_roh("hv@x.org", "kalender", name))
        for name in ("KAL-A", "KAL-B")
    }
    with merkungsrahmen() as merker:
        kalender_rechte_vorladen("hv@x.org", ["KAL-A", "KAL-B", "KAL-C"])
        assert merker is not None
        assert ("pruefstufen", "hv@x.org", "kalender", "KAL-A") in merker
        assert ("moderationsstufen", "hv@x.org", "kalender", "KAL-A") in merker
        assert ("objekt_kontext", "kalender", "KAL-A", "hv@x.org") in merker
        # KAL-C hat KEIN Rechte-Objekt -> nichts vorab (die Einzelfrage antwortet).
        assert not any(k[0] == "objekt_kontext" and k[2] == "KAL-C" for k in merker)
        # WERTE: dieselbe Antwort wie die frische Einzelfrage.
        for name, (darf, pruef, stufen) in frisch.items():
            assert merker[("darf", "hv@x.org", K.LESEN, "kalender", name,
                           None, None, None, (), K.STUFE_GEMEINDE)] == darf
            assert tuple(merker[("pruefstufen", "hv@x.org", "kalender", name)]) == tuple(pruef)
            assert tuple(merker[("moderationsstufen", "hv@x.org", "kalender", name)]) == tuple(stufen)


def test_vorabladen_ueberschreibt_nichts(welt):
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    with merkungsrahmen() as merker:
        assert merker is not None
        merker[("pruefstufen", "hv@x.org", "kalender", "KAL-A")] = ["VORHER"]
        kalender_rechte_vorladen("hv@x.org", ["KAL-A"])
        assert merker[("pruefstufen", "hv@x.org", "kalender", "KAL-A")] == ["VORHER"]


def test_schreiben_leert_den_merker_und_der_vorrat_rechnet_frisch(welt):
    """Der harte Punkt: nach einem Schreibvorgang wird NICHT der alte Vorrat geliefert.

    Nachgestellt mit der echten Aufruf-Sitzung (`SessionLocal`, wie
    `_endpunkt` sie fuehrt): ein `flush` dort leert den Rechte-Merker
    (`db._rechte_merker_nach_flush`). Der zweite Aufruf von
    `kalender_rechte_vorladen` im selben Rahmen rechnet die Antworten deshalb
    NEU — nachgewiesen an der entzogenen Moderationsfreigabe, die danach nicht
    mehr im Vorrat steht. Ohne das Leeren stuende dort der Stand von VOR dem
    Schreiben.
    """
    from sqlalchemy import select

    from diakronos_app import db as _db
    from diakronos_app.models.rechte import RechteFreigabe as RF
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    freigabe_id = welt.execute(
        select(RF.id).where(RF.objekt == "KAL-A", RF.gruppe == "G-A")
    ).scalar_one()
    set_user("hv@x.org")
    aufruf = _db.SessionLocal()
    try:
        with merkungsrahmen() as merker, _db.als_aktuelle_sitzung(aufruf):
            assert merker is not None
            kalender_rechte_vorladen("hv@x.org", ["KAL-A"])
            assert bool(R.pruefstufen("hv@x.org", "kalender", "KAL-A"))
            # Moderationsfreigabe im selben Aufruf entziehen (OR/M-Objekt,
            # damit `after_flush` greift — wie eine Aenderung ueber die
            # Rechte-Verwaltung).
            aufruf.get(RF, freigabe_id).moderieren = False
            aufruf.flush()
            # Der Merker ist geleert -> die Frage rechnet frisch (ohne die
            # entzogene Stufe "gemeinde"; "gruppe" bleibt aus der HV-Rolle).
            assert "gemeinde" not in R.pruefstufen("hv@x.org", "kalender", "KAL-A"), \
                "der Flush hat den Merker nicht geleert"
            kalender_rechte_vorladen("hv@x.org", ["KAL-A"])
            assert "gemeinde" not in merker[("pruefstufen", "hv@x.org", "kalender", "KAL-A")], \
                "der Vorrat hat den Stand von vor dem Schreiben geliefert"
    finally:
        aufruf.rollback()
        aufruf.close()


def test_fremder_kalender_bleibt_unsichtbar(welt):
    """Fremde Gruppe ohne Leitung: lesen ja, moderieren nein; ohne Objekt: nicht da."""
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user("mitglied@x.org")  # in G-A UND G-B Mitglied
    with merkungsrahmen():
        sichtbar = _liste(welt)
    assert sichtbar["KAL-B"], "KAL-B ist ueber die Gruppen-Freigabe lesbar"
    assert not sichtbar["KAL-B"]["is_moderator"]
    assert "KAL-C" not in sichtbar


def test_vorabladen_ist_wiederholbar_und_gleich(welt):
    """Zweimal vorabladen (zwei Kalender, zwei Aufrufe) aendert die Liste nicht."""
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    set_user("mitglied@x.org")
    erst = _liste(welt)
    with merkungsrahmen():
        kalender_rechte_vorladen("mitglied@x.org", ["KAL-A"])
        kalender_rechte_vorladen("mitglied@x.org", ["KAL-B"])
        zweit = _liste(welt)
    assert erst == zweit


def test_liste_und_existenz_werden_gemerkt_und_gleichen_frisch(welt):
    """R1: was die Liste belegt, steht vollstaendig und richtig im Merker.

    Geprueft werden die beiden neuen Vorraete, die aus der FERTIGEN Liste
    kommen (`kalender_existenz_merken`) sowie der Einmal-Aufbau der Liste
    (`kalenderliste`):
      * ohne Rahmen: nichts gemerkt,
      * mit Rahmen: `darf`/`pruefstufen`/`moderationsstufen` je Kalender
        gleich der frischen Einzelfrage,
      * Existenz: sichtbar = ja, nicht sichtbar/verwaist/unbekannt = nein,
      * zweiter Aufruf im selben Rahmen trifft keinen SQL-Kanal mehr und
        liefert dieselbe Liste.

    PERF-K2b/SOLL 2: Der Moderator OHNE Schreibrecht (`moderator@x.org` auf
    KAL-D) gehoert in diese Welt — er ist der Fall, an dem sich eine Ableitung
    `write = schreiben` sofort verraet: in der Liste steht `write` true,
    `darf(SCHREIBEN)` ist aber false.
    """
    from sqlalchemy import event

    from diakronos_app import rechte as R
    from diakronos_app.db import als_aktuelle_sitzung, engine
    from diakronos_app.rechte import kern as K
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_existiert

    for nutzer in ("hv@x.org", "mitglied@x.org", "moderator@x.org"):
        set_user(nutzer)
        with als_aktuelle_sitzung(welt):
            frisch = {
                name: tuple(bool(R.darf(nutzer, a, "kalender", name))
                            for a in (R.LESEN, R.SCHREIBEN, R.VORSCHLAGEN))
                for name in ("KAL-A", "KAL-B", "KAL-D")
            }
            exists = {n: kalender_existiert(n) for n in ("KAL-A", "KAL-B", "KAL-C", "KAL-WEG")}

        zaehler = {"n": 0}

        def _zaehle(conn, cursor, statement, parameters, context, executemany):
            zaehler["n"] += 1

        with merkungsrahmen() as merker:
            with als_aktuelle_sitzung(welt):
                erst = _liste(welt)
            assert merker is not None
            for name, werte in frisch.items():
                assert tuple(bool(R.darf(nutzer, a, "kalender", name))
                             for a in (R.LESEN, R.SCHREIBEN, R.VORSCHLAGEN)) == werte
            for n, wert in exists.items():
                assert kalender_existiert(n) is wert, (nutzer, n)
            assert kalender_existiert("KAL-C") is True   # existiert, nur ohne Rechte
            assert kalender_existiert("KAL-WEG") is False

            # Zweiter Aufbau: kommt aus dem Merker, ohne eine einzige Abfrage.
            event.listen(engine, "before_cursor_execute", _zaehle)
            try:
                with als_aktuelle_sitzung(welt):
                    zweit = _liste(welt)
            finally:
                event.remove(engine, "before_cursor_execute", _zaehle)
            assert zweit == erst
            assert zaehler["n"] == 0, f"{zaehler['n']} Abfragen statt 0 im Merker"
            # Und der Merker behaelt seine Instanz (Rahmen bleibt gueltig).
            assert K._MERKER.get() is merker
