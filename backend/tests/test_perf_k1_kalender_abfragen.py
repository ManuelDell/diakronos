"""PERF-K1 — Obergrenze der SQL-Abfragen des Kalender-Endpunkts.

BEFUND (Manuel, 17.11.): „Kalenderdaten brauchen sehr lange zum Laden“.
Gemessen im Vorbau-Image (`--network none`, eigene Wegwerf-DB, 10 Kalender /
50 Nutzer / 312 Termine):

  * VORHER: `get_calendar_events` = 60 069 ms und **110 803** SQL-Abfragen fuer
    EINE Monatsansicht — der Rechte-Kern wurde JE TERMIN erneut befragt
    (`_ist_moderator` -> `get_accessible_calendars` -> je Kalender 3x
    `rechte.*`, und jede Frage las `Mitglied` + `User` vollstaendig).
  * NACHHER: 14 087 ms / **20 723** Abfragen (gleiche Seed-Daten).

Der Test haelt die OBERGRENZE fest, damit ein Rueckfall in das Muster
„je Termin eine Rechtepruefung“ sofort rot wird. Er ist bewusst eine
GROBE Schranke (Faktor ~2 ueber dem Ist-Wert nach der Behebung, Faktor ~5
unter dem Befund): eine enge Zahl waere bei jeder legitimen Aenderung an
Legende/Formatierung sofort falsch.

Wichtig fuer die Aussage: Der Merkungsrahmen (`rechte.kern.merkungsrahmen`)
wird hier NICHT vorgewaermt — die Messung startet mit leerem Merker, wie ein
echter Request.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
from diakronos_app.models.kronos import Element, Kalender
from diakronos_app.models.rechte import RechteFreigabe, RechteGruppenrolle, RechteObjekt

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren/Registrierung

KAL_PFAD = "/api/method/diakronos.kronos.api.calendar_get."

# Obergrenze fuer EINE Monatsansicht (FullCalendar-Fenster einer Monatsansicht:
# 6 Wochen) mit 10 Kalendern und 312 Terminen. Ist-Wert nach PERF-K1: 20 723.
# Befund vor der Behebung: 110 803.
HOECHSTENS_ABFRAGEN = 40000



@pytest.fixture()
def rechtewelt(patched_db):
    """10 Kalender, 50 Nutzer, 312 Termine (240 frei + 6 Serien x 12).

    Die Fixture gibt die SITZUNG zurueck. Sie COMMITTET: der Endpunkt laeuft
    ueber eigene Sitzungen (`lesesitzung`, `db.count`, `get_value`) — mit
    ungeflushten Zeilen sieht er eine andere Transaktion und der Seed waere
    fuer ihn unsichtbar (im Test belegt: 0 Termine, „nicht_angemeldet“).
    """
    sess = patched_db()

    nutzer = [User(name=f"perf{i:02d}@example.org", email=f"perf{i:02d}@example.org",
                   full_name=f"Person {i:02d}", enabled=True,
                   user_type="System User") for i in range(50)]
    sess.add_all(nutzer)
    # FLUSH VOR DEM NAECHSTEN SCHRITT: ohnehin noetig, UND der Commit unten
    # macht die Zeilen dauerhaft (sonst ist die Test-Transaktion leer).
    sess.commit()
    sess.add_all([
        HasRole(name=f"HR-P{i}", parent=n.name, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1) for i, n in enumerate(nutzer)
    ])
    sess.add(Gruppe(name="GR-P", gruppenname="Gemeinde", docstatus=0, idx=0))
    sess.flush()
    mitglieder = [
        Mitglied(name=f"MIT-P{i:02d}", vorname="Person", nachname=f"{i:02d}",
                 email=n.email, user=n.name, status="Aktiv", ausgeschlossen=0,
                 docstatus=0, idx=i)
        for i, n in enumerate(nutzer)
    ]
    sess.add_all(mitglieder)
    sess.flush()
    sess.add_all([
        Gruppenmitgliedschaft(name=f"GM-P{i:02d}", parent="GR-P", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=m.name, status="Aktiv",
                              docstatus=0, idx=i)
        for i, m in enumerate(mitglieder)
    ])
    sess.flush()
    # Der Messnutzer ist HV der Gruppe (schreibt + moderiert).
    sess.add(RechteGruppenrolle(gruppe="GR-P", untergruppe=None,
                                benutzer=nutzer[0].name, rolle="HV"))
    from diakronos_app.models.rechte import RechteModul

    sess.add(RechteModul(gruppe="GR-P", modul="kalender"))
    sess.flush()

    kalender = [
        Kalender(name=f"KAL-P{i}", calendar_name=f"Kalender {i}",
                 calendar_color=f"#3366{i:02d}", selbstverwaltet=(i % 3 == 0),
                 docstatus=0, idx=i)
        for i in range(10)
    ]
    sess.add_all(kalender)
    sess.flush()
    sess.add_all([
        RechteObjekt(typ="kalender", objekt=k.name, gruppe="GR-P",
                     gemeinde_status="aktiv", gruppe_status="aktiv")
        for k in kalender
    ])
    sess.flush()
    sess.add_all([
        RechteFreigabe(typ="kalender", objekt=k.name, gruppe="GR-P",
                       lesen=True, schreiben=True, moderieren=(i < 4))
        for i, k in enumerate(kalender)
    ])
    sess.flush()

    elemente = []
    start = datetime(2026, 11, 1, 9, 0)
    for i in range(240):
        s = start + timedelta(days=i % 29, hours=(i % 8))
        elemente.append(Element(
            name=f"EL-P{i:03d}", element_name=f"Termin {i}",
            element_calendar=f"KAL-P{i % 10}", element_start=s,
            element_end=s + timedelta(hours=1), all_day=(i % 7 == 0),
            status=("Festgelegt" if i % 5 else "Vorschlag"),
            owner=nutzer[i % 50].name, repeat_this_event=0, docstatus=0, idx=i))
    for k in range(6):
        for j in range(12):
            s = datetime(2026, 10, 5, 18, 0) + timedelta(days=7 * j)
            elemente.append(Element(
                name=f"EL-PS{k}-{j:02d}", element_name=f"Serie {k} Folge {j}",
                element_calendar=f"KAL-P{k}", element_start=s,
                element_end=s + timedelta(hours=2), all_day=False,
                status="Festgelegt", series_id=f"SER-P{k}",
                owner=nutzer[k].name, repeat_this_event=0, docstatus=0,
                idx=1000 + k * 20 + j))
    sess.add_all(elemente)
    sess.commit()
    return sess


def _zaehle_direkt(engine, view_mode="edit"):
    """SQL-Abfragen EINES `get_calendar_events`-Laufs (Fachaufruf, ohne HTTP).

    Warum nicht ueber den TestClient: der Endpunkt liefert je Eintrag einen
    Wert aus `extendedProps`, den `JSONResponse` nicht serialisieren kann — der
    HTTP-Weg endet im Image 2026-11-17 in einer Endlosschleife (AnyIO-Portal
    wartet auf eine Antwort, die nie kommt). Fuer die ABFRAGEZAHL ist der
    HTTP-Mantel ohne Bedeutung: er fuehrt keine Endpunkt-Abfragen aus.
    Dieselbe Funktion, dieselbe Sitzung, derselbe Zaehler.
    """
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.rechte.kern import merkungsrahmen

    zaehler = {"n": 0}

    def _zaehle_sql(conn, cursor, statement, parameters, context, executemany):
        zaehler["n"] += 1

    event.listen(engine, "before_cursor_execute", _zaehle_sql)
    try:
        # Der Produktivpfad oeffnet den Merker je Request
        # (`RequestContextMiddleware`); der Fachaufruf allein hat keinen.
        with merkungsrahmen():
            termine = get_calendar_events(
                "2026-10-26", "2026-12-06",
                json.dumps([f"KAL-P{i}" for i in range(10)]), view_mode,
            )
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle_sql)
    return termine, zaehler["n"]


def test_perf_k1_monatsansicht_bleibt_unter_der_abfragegrenze(rechtewelt, engine):
    """PERF-K1: Eine Monatsansicht kostet NICHT je Termin eine Rechtepruefung.

    VORHER (gemessen im Vorbau-Image, dieselbe Datenmenge): 110 803 Abfragen —
    der Test ist vor der Behebung rot und danach gruen.
    """
    # Die Autouse-Fixture schaltet die Test-Naht bereits ein (conftest.py).
    set_user("perf00@example.org")
    # Die Sitzung der Fixture verbindet die App NICHT mit der Test-Datenbank:
    # `patched_db` ersetzt `SessionLocal`, und `lesesitzung()` oeffnet bei
    # fehlender Aufruf-Sitzung eine NEUE — die sieht eine andere (leere)
    # Datenbank. Deshalb laeuft der Endpunkt hier IM Rahmen der Fixture-Sitzung
    # (`als_aktuelle_sitzung`) — dasselbe Muster wie ein Request-Rahmen.
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    with merkungsrahmen():
        with als_aktuelle_sitzung(rechtewelt):
            termine, abfragen = _zaehle_direkt(engine, "edit")

    assert len(termine) >= 200, len(termine)
    assert abfragen < HOECHSTENS_ABFRAGEN, (
        f"{abfragen} SQL-Abfragen fuer eine Monatsansicht "
        f"(Obergrenze {HOECHSTENS_ABFRAGEN}; Befund PERF-K1: 110 803)"
    )


def test_perf_k1_lesemodus_unter_der_abfragegrenze(rechtewelt, engine):
    """Dieselbe Zusage im Lesemodus (view) — andere Statusfilter, gleiche Zahl."""
    set_user("perf00@example.org")
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    with merkungsrahmen():
        with als_aktuelle_sitzung(rechtewelt):
            termine, abfragen = _zaehle_direkt(engine, "view")

    assert len(termine) >= 100, len(termine)
    assert abfragen < HOECHSTENS_ABFRAGEN, (
        f"{abfragen} SQL-Abfragen im Lesemodus "
        f"(Obergrenze {HOECHSTENS_ABFRAGEN}; Befund PERF-K1: 110 803)"
    )


def test_perf_k1_rechte_merker_ueberlebt_reine_lesevorgaenge(patched_db) -> None:
    """Ein LESE-Vorgang darf den Merker NICHT leeren (Review 17.11.).

    Befund im Messlauf (10 Kalender / 50 Nutzer / 312 Termine): `lesesitzung()`
    leerte den Merker nach JEDER Rechte-Lesefrage — 28 116 Leerungen fuer EINEN
    Kalender-Aufruf, 64 973 statt 20 723 SQL-Abfragen. Der Merker traf nie.

    Zusage jetzt: Lesen laesst den Stand stehen, ein SCHREIBVORGANG im selben
    Aufruf leert ihn (das deckt der `after_flush`-Zuhoerer ab, Test unten).
    """
    from diakronos_app import rechte as R
    from diakronos_app.db import lesesitzung
    from diakronos_app.rechte.kern import _MERKER

    with R.merkungsrahmen(), lesesitzung():
        R.gruppenrolle("perf00@example.org", "G-PERF")
        nach_erster = len(_MERKER.get() or {})
        R.gruppenrolle("perf00@example.org", "G-PERF")
        nach_zweiter = len(_MERKER.get() or {})
    assert nach_erster > 0, "die erste Frage muss etwas merken"
    assert nach_zweiter == nach_erster, (
        "ein reiner Lesevorgang hat den Merker geleert — dann traegt er nie "
        f"(Befund 17.11.: 28 116 Leerungen je Aufruf; {nach_erster} -> {nach_zweiter})"
    )


def test_perf_k1_rechte_merker_wird_nach_dem_schreiben_geleert():
    """Der Rechte-Merker darf eine Rechte-Aenderung nicht verschleiern.

    Zusage: Innerhalb eines Aufrufs wird dieselbe Frage EINMAL gerechnet
    (`_gemerkt`), nach einem Schreibvorgang (`merker_leeren`) aber wieder
    frisch — sonst wirkte ein entzogenes Recht erst beim naechsten Request.
    """
    from diakronos_app.rechte.kern import _MERKER, _gemerkt, merker_leeren, merkungsrahmen

    with merkungsrahmen():
        assert _gemerkt(("probe",), lambda: 1) == 1
        assert _gemerkt(("probe",), lambda: 2) == 1, "zweite Frage muss gemerkt sein"
        assert len(_MERKER.get() or {}) == 1
        merker_leeren()
        assert _gemerkt(("probe",), lambda: 2) == 2, "nach dem Leeren wieder frisch"
        # GELEERT wird die vorhandene Instanz: der Rahmen muss denselben
        # Stand sehen (ein Ersetzen liesse ihn auf dem alten Woerterbuch).
        assert len(_MERKER.get() or {}) == 1


def test_perf_k1_ohne_rahmen_wird_jede_frage_gerechnet():
    """Ohne Merkungsrahmen (Skripte, CLI, Tests) verhaelt sich alles wie zuvor."""
    from diakronos_app.rechte.kern import _MERKER, _gemerkt

    assert _MERKER.get() is None
    assert _gemerkt(("probe",), lambda: 1) == 1
    assert _gemerkt(("probe",), lambda: 2) == 2


def test_perf_k1_flush_in_der_aufrufsitzung_leert_den_merker(patched_db) -> None:
    """Operator-Review: ein Schreibvorgang im selben Aufruf (nur flush, noch kein
    Commit, Aufruf-Sitzung geliehen) darf keine veraltete Rechte-Antwort lassen."""
    from diakronos_app import db as _db
    from diakronos_app import rechte as R
    from diakronos_app.models.rechte import RechteModul

    sess = patched_db()
    sess.add(User(name="neu@x.org", email="neu@x.org", enabled=1))
    sess.add(Mitglied(name="M-neu", vorname="Ne", nachname="U", email="neu@x.org", user="neu@x.org"))
    sess.add(Gruppe(name="G-F", gruppenname="G-F"))
    sess.add(RechteModul(gruppe="G-F", modul="wiki"))
    sess.commit()
    with R.merkungsrahmen(), _db.als_aktuelle_sitzung(sess):
        assert R.gruppenrolle("neu@x.org", "G-F") is None
        sess.add(RechteGruppenrolle(gruppe="G-F", benutzer="neu@x.org", rolle="HV"))
        sess.flush()
        assert R.gruppenrolle("neu@x.org", "G-F") == "HV"
    sess.rollback()
    sess.close()


def test_perf_k1_gemerkte_liste_wird_nicht_geteilt() -> None:
    from diakronos_app.rechte import kern

    with kern.merkungsrahmen():
        a = kern._gemerkt(("probe",), lambda: ["gruppe"])
        a.append("verfaelscht")
        assert kern._gemerkt(("probe",), lambda: ["anders"]) == ["gruppe"]


def test_perf_k1_massen_schreibbefehl_und_rollback_leeren_den_merker(patched_db) -> None:
    """Operator-Review: `sess.execute(delete(...))` (ohne Flush) und Rollback
    duerfen keine veraltete Rechte-Antwort im Merker lassen."""
    from sqlalchemy import delete

    from diakronos_app import db as _db
    from diakronos_app import rechte as R

    sess = patched_db()
    sess.add(User(name="bulk@x.org", email="bulk@x.org", enabled=1))
    sess.add(Mitglied(name="M-bulk", vorname="Bu", nachname="L", email="bulk@x.org", user="bulk@x.org"))
    sess.add(Gruppe(name="G-B", gruppenname="G-B"))
    sess.add(RechteGruppenrolle(gruppe="G-B", benutzer="bulk@x.org", rolle="HV"))
    sess.commit()
    with R.merkungsrahmen(), _db.als_aktuelle_sitzung(sess):
        assert R.gruppenrolle("bulk@x.org", "G-B") == "HV"
        sess.execute(delete(RechteGruppenrolle).where(RechteGruppenrolle.benutzer == "bulk@x.org"))
        assert R.gruppenrolle("bulk@x.org", "G-B") is None
        sess.rollback()
        assert R.gruppenrolle("bulk@x.org", "G-B") == "HV"
    sess.close()
