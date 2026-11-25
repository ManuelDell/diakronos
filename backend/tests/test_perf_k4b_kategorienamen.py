"""PERF-K4b — Kategorienamen gesammelt laden: gleiche Antwort, eine Abfrage.

BEFUND (PERF-K3, Messung im Wegwerf-Stack `perfk3`, 2000 Termine / 1314 im
Fenster): `get_calendar_events` braucht 1200–1292 SQL-Abfragen, davon **1158**
aus `kronos/calendar_get.py`:

    SELECT eventkategorie.event_category_name FROM eventkategorie WHERE name = ?

— eine `get_value`-Abfrage JE TERMIN, obwohl es nur ~6 Kategorien gibt.

Dieser Test haelt BEIDES fest:

  1. GLEICHHEIT (SOLL: Byte-gleich). Der alte Weg (Einzelabfrage je Termin,
     hier als `_alter_name` wortgleich nachgebaut) und der neue Vorrat
     liefern fuer Admin/HV/Mitglied dieselbe Antwort — Feld fuer Feld, in der
     Reihenfolge der Liste, inklusive
       * Termin mit GELOESCHTER Kategorie (keine Zeile mehr -> Kennung),
       * Termin mit Kategorie ohne Anzeigenamen (`event_category_name` NULL
         -> Kennung),
       * Termin ohne Kategorie (`""`).
  2. ABFRAGE-OBERGRENZE: 300 Termine mit 3 Kategorien kosten HOECHSTENS EINE
     Kategorie-Abfrage (vorher 300).

Die Mutation ist im Karten-Kommentar belegt: Vorrat absichtlich leer (oder
ohne die Kennung) -> Gleichheit und Zaehler werden rot.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren/Registrierung
from diakronos_app.frappe_compat.api_helpers import get_value
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
from diakronos_app.models.kronos import Element, Eventkategorie, Kalender
from diakronos_app.models.rechte import RechteFreigabe, RechteGruppenrolle, RechteModul, RechteObjekt

# Kalender und Kategorien der Testwelt.
KALENDER = [f"KAL-K4-{i}" for i in range(3)]
#: Vorhandene Kategorien: die dritte hat KEINEN Anzeigenamen (NULL).
KATEGORIEN = {
    "KAT-GD": "Gottesdienst",
    "KAT-JUG": "Jugend",
    "KAT-LEER": None,
}
#: Kennung einer Kategorie, deren Zeile es NICHT (mehr) gibt — geloescht.
KAT_WEG = "KAT-GELOESCHT"

#: Termine je Kalender. 300 Termine ist der Karten-Wert fuer die Obergrenze.
JE_KALENDER = 100

NUTZER = {
    "Admin": "k4-admin@example.org",       # Administrator (System Manager)
    "HV": "k4-hv@example.org",             # HV der Gruppe (Moderator der Kalender)
    "Mitglied": "k4-mitglied@example.org", # einfaches Mitglied
}


@pytest.fixture()
def kategoriewelt(patched_db):
    """3 Kalender, 300 Termine, 3 Kategorien + 1 geloeschte Kennung.

    Die Fixture COMMITTET: der Endpunkt liest ueber eigene Sitzungen
    (`lesesitzung`, `get_all`, `get_value`) und saehe ungeflushte Zeilen
    sonst nicht (dasselbe Muster wie `test_perf_k1_kalender_abfragen.py`).
    """
    sess = patched_db()

    nutzer = [
        User(name=f"k4-n{i:02d}@example.org", email=f"k4-n{i:02d}@example.org",
             full_name=f"Person {i:02d}", enabled=True, user_type="System User")
        for i in range(5)
    ]
    nutzer[0] = User(name=NUTZER["Admin"], email=NUTZER["Admin"], full_name="Admin",
                     enabled=True, user_type="System User")
    nutzer[1] = User(name=NUTZER["HV"], email=NUTZER["HV"], full_name="HV",
                     enabled=True, user_type="System User")
    nutzer[2] = User(name=NUTZER["Mitglied"], email=NUTZER["Mitglied"],
                     full_name="Mitglied", enabled=True, user_type="System User")
    sess.add_all(nutzer)
    sess.commit()
    sess.add_all([
        HasRole(name=f"HR-K4{i}", parent=n.name, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1) for i, n in enumerate(nutzer)
    ])
    # Das Admin-Konto traegt die Systemrolle Administrator.
    sess.add(HasRole(name="HR-K4-ADMIN", parent=NUTZER["Admin"], parenttype="User",
                     parentfield="roles", role="System Manager", docstatus=0, idx=2))
    sess.add(Gruppe(name="GR-K4", gruppenname="Gemeinde K4", docstatus=0, idx=0))
    sess.flush()
    mitglieder = [
        Mitglied(name=f"MIT-K4{i}", vorname="Person", nachname=f"{i:02d}", email=n.email,
                 user=n.name, status="Aktiv", ausgeschlossen=0, docstatus=0, idx=i)
        for i, n in enumerate(nutzer)
    ]
    sess.add_all(mitglieder)
    sess.flush()
    sess.add_all([
        Gruppenmitgliedschaft(name=f"GM-K4{i}", parent="GR-K4", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=m.name, status="Aktiv",
                              docstatus=0, idx=i)
        for i, m in enumerate(mitglieder)
    ])
    sess.flush()
    sess.add(RechteGruppenrolle(gruppe="GR-K4", untergruppe=None,
                                benutzer=NUTZER["HV"], rolle="HV"))
    sess.add(RechteModul(gruppe="GR-K4", modul="kalender"))
    sess.flush()

    sess.add_all([
        Kalender(name=k, calendar_name=f"Kalender {k}", calendar_color=f"#4b4b{i:02d}",
                 docstatus=0, idx=i) for i, k in enumerate(KALENDER)
    ])
    sess.flush()
    sess.add_all([
        RechteObjekt(typ="kalender", objekt=k, gruppe="GR-K4",
                     gemeinde_status="aktiv", gruppe_status="aktiv") for k in KALENDER
    ])
    sess.flush()
    sess.add_all([
        RechteFreigabe(typ="kalender", objekt=k, gruppe="GR-K4",
                       lesen=True, schreiben=True, moderieren=True) for k in KALENDER
    ])
    sess.flush()

    sess.add_all([
        Eventkategorie(name=name, event_category_name=anzeige, farbe="#3366ff",
                       docstatus=0, idx=i)
        for i, (name, anzeige) in enumerate(KATEGORIEN.items())
    ])
    sess.flush()

    # Verteilung der Kategorien ueber die Termine: 2/3 vorhanden, der Rest
    # geloescht bzw. OHNE Kategorie — so kommt jeder Zweig durch den Endpunkt.
    kategorie_namen = list(KATEGORIEN)
    elemente = []
    start = datetime(2026, 11, 1, 8, 0)
    for i in range(JE_KALENDER * len(KALENDER)):
        s = start + timedelta(hours=i)
        rest = i % 10
        if rest < 6:
            kategorie = kategorie_namen[rest % len(kategorie_namen)]
        elif rest < 8:
            kategorie = KAT_WEG          # Zeile geloescht -> Kennung
        else:
            kategorie = None             # gar keine Kategorie
        elemente.append(Element(
            name=f"EL-K4-{i:04d}", element_name=f"Termin {i}",
            element_calendar=KALENDER[i % len(KALENDER)], element_start=s,
            element_end=s + timedelta(minutes=45), all_day=False,
            element_category=kategorie, status="Festgelegt",
            owner=nutzer[i % len(nutzer)].name, repeat_this_event=0,
            docstatus=0, idx=i))
    sess.add_all(elemente)
    sess.commit()
    return sess


def _alter_name(kategorie):
    """Der ABGELOESTE Weg: Einzelabfrage je Termin (vor PERF-K4b).

    Wortgleich das, was in `calendar_get.py` stand — inklusive des frueheren
    `except`, das die Kennung als Fallback nahm.
    """
    try:
        return get_value("Eventkategorie", kategorie, "event_category_name") or kategorie
    except Exception:  # noqa: BLE001 — wie im Altcode: Fallback auf ID
        return None


def _lauf(sitzung, nutzer: str, view_mode: str = "edit"):
    """Terminliste des Endpunkts unter einem Nutzer (eigener Merkungsrahmen)."""
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(nutzer)
    with merkungsrahmen():
        with als_aktuelle_sitzung(sitzung):
            return get_calendar_events(
                "2026-10-26", "2026-12-06", json.dumps(KALENDER), view_mode
            )


def _kategorie_paare(termine):
    """(element_category, event_category_name) je Zeile — der Vergleichswert."""
    return [(t["extendedProps"]["element_category"],
             t["extendedProps"]["event_category_name"]) for t in termine]


@pytest.mark.parametrize("rolle", list(NUTZER))
@pytest.mark.parametrize("view_mode", ["edit", "view"])
def test_perf_k4b_kategorienamen_gleich_wie_einzelabfrage(kategoriewelt, rolle, view_mode):
    """Neu streichgleich zum Altcode — fuer Admin, HV und Mitglied.

    Die Zusage ist EINE Rechnung: fuer jede gelieferte Zeile muss
    `event_category_name` genau das sein, was der ALTE Weg (Einzelabfrage
    `get_value` auf `eventkategorie`) fuer dieselbe Kennung ergaebe —
    inklusive der beiden Fallback-Faelle (Kategorie-Zeile geloescht ->
    Kennung, Anzeigename NULL -> Kennung) und `""` bei Terminen ohne
    Kategorie.

    Warum das traegt (und nicht nur mit sich selbst vergleicht): `_alter_name`
    liest den Namen aus einer EIGENEN Abfrage auf `eventkategorie`, nicht aus
    einer zweiten Kopie des neuen Vorrats. Laesst der Vorrat eine Kennung aus
    oder ordnet er zwei falsch zu, weicht die Antwort ab und der Test wird rot
    (so im Karten-Kommentar belegt).

    Zusaetzlich geprueft: die vorhandenen Kategorien zeigen wirklich NAMEN.
    Ohne diese Zeile waere eine Antwort, die ueberall nur die Kennung
    ausgibt, „Altcode-gleich“ — aber still kaputt.
    """
    termine = _lauf(kategoriewelt, NUTZER[rolle], view_mode)
    assert len(termine) == JE_KALENDER * len(KALENDER), len(termine)

    paare = _kategorie_paare(termine)
    # Alle drei Faelle kommen wirklich vor (sonst prueft der Test nichts).
    gesehen = {kennung for kennung, _ in paare}
    assert set(KATEGORIEN) <= gesehen
    assert KAT_WEG in gesehen
    assert None in gesehen

    for kennung, anzeige in paare:
        if not kennung:
            assert anzeige == ""
            continue
        assert anzeige == _alter_name(kennung), (kennung, anzeige)

    # Der Vorrat ist nicht heimlich leer: die vorhandenen Kategorien zeigen
    # mindestens einen echten Namen (nicht nur ihre Kennung).
    vorhandene = [(kennung, anzeige) for kennung, anzeige in paare
                  if kennung in KATEGORIEN]
    assert any(anzeige and anzeige != kennung for kennung, anzeige in vorhandene), \
        vorhandene
    # … und die Kategorie MIT Anzeigename zeigt genau ihn.
    mit_namen = {kennung for kennung, _ in vorhandene if KATEGORIEN[kennung]}
    assert mit_namen, "Testwelt hat keine Kategorie mit Anzeigenamen"
    for kennung, anzeige in vorhandene:
        if KATEGORIEN[kennung]:
            assert anzeige == KATEGORIEN[kennung], (kennung, anzeige)


def test_perf_k4b_geloeschte_kategorie_bleibt_kennung(kategoriewelt):
    """Fehlende/geloeschte Kategorie: wie `get_value` -> None -> Kennung."""
    termine = _lauf(kategoriewelt, NUTZER["HV"])
    weg = [t for t in termine if t["extendedProps"]["element_category"] == KAT_WEG]
    assert weg, "Testwelt enthaelt keinen Termin mit geloeschter Kategorie"
    for t in weg:
        # Altcode: `get_value(...) or element_category` -> die Kennung.
        assert t["extendedProps"]["event_category_name"] == KAT_WEG
    # Und die Kategorie OHNE Anzeigenamen ebenso (NULL -> Kennung).
    leer = [t for t in termine if t["extendedProps"]["element_category"] == "KAT-LEER"]
    assert leer
    for t in leer:
        assert t["extendedProps"]["event_category_name"] == "KAT-LEER"


def test_perf_k4b_kategorie_abfragen_hoechstens_eine(kategoriewelt, engine):
    """300 Termine -> HOECHSTENS EINE Abfrage auf `eventkategorie` (vorher 300)."""
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    gesehen: list[str] = []

    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        sql = " ".join(statement.split()).lower()
        if "eventkategorie" in sql:
            gesehen.append(sql)

    set_user(NUTZER["HV"])
    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        with merkungsrahmen():
            with als_aktuelle_sitzung(kategoriewelt):
                termine = get_calendar_events(
                    "2026-10-26", "2026-12-06", json.dumps(KALENDER), "edit"
                )
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    assert len(termine) == 300, len(termine)
    assert len(gesehen) <= 1, (
        f"{len(gesehen)} Abfragen auf `eventkategorie` fuer {len(termine)} Termine "
        f"(Obergrenze 1; Befund PERF-K3: eine je Termin) — {gesehen[:3]}"
    )
    # Die eine Abfrage ist die GESAMMELTE (IN-Liste), keine Einzelabfrage.
    if gesehen:
        assert " in (" in gesehen[0].replace("in(", "in ("), gesehen[0]


def test_perf_k4b_vorrat_eine_abfrage_fuer_alle_kennungen(kategoriewelt, engine):
    """Der Vorrat holt ALLE vorkommenden Kennungen in EINER Abfrage.

    Die Gleichheitspruefung allein koennte einen „Vorrat mit Luecke“ decken:
    fehlt eine Kennung, liefert der Rueckfall `or element_category` genau die
    Kennung — fuer eine Kategorie mit `event_category_name IS NULL` ist das
    ohnehin der Sollwert, aus der Antwort ist beides nicht zu unterscheiden.
    Diese Zusage ist die Eigenschaft, die ein lueckenhafter Vorrat NICHT
    erfuellen kann: EINE Abfrage, und in ihrer Werteliste steht jede
    vorkommende Kennung.
    """
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    gesehen: list[tuple[str, str]] = []

    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        if "eventkategorie" in " ".join(statement.split()).lower():
            gesehen.append((" ".join(statement.split()), str(parameters)))

    set_user(NUTZER["HV"])
    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        with merkungsrahmen():
            with als_aktuelle_sitzung(kategoriewelt):
                termine = get_calendar_events(
                    "2026-10-26", "2026-12-06", json.dumps(KALENDER), "edit"
                )
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    # Die Kennungen aus DIESEM Lauf — nicht aus einer eigenen Abfrage: sonst
    # prueften wir eine Werteliste, die der Endpunkt gar nicht gebaut hat, und
    # ein im Endpunkt ausgelassener Schluessel bliebe unsichtbar (beim
    # Mutationslauf genau so passiert).
    vorkommend = sorted({str(k) for k, _ in _kategorie_paare(termine) if k})
    assert vorkommend, "Testwelt liefert keine Kategorie-Kennung"
    assert [k for k in vorkommend if k in KATEGORIEN], vorkommend

    assert len(gesehen) == 1, [g[0] for g in gesehen]
    abfrage, werte = gesehen[0]
    # Eine IN-Liste, nicht mehrere Einzelabfragen („IN (?, ?, ?, ?)“).
    assert " in (" in abfrage.lower(), abfrage
    # Jede vorkommende Kennung stand in der Werteliste — eine Luecke im Vorrat
    # heisst: der Endpunkt fragt sie erst gar nicht ab.
    for kennung in vorkommend:
        assert kennung in werte, (kennung, werte)


def test_perf_k4b_ohne_kategorien_keine_abfrage(patched_db, engine):
    """Ohne Kategorie-Werte im Fenster wird gar nicht gefragt (wie vorher)."""
    sess = patched_db()
    sess.add(User(name="k4-leer@example.org", email="k4-leer@example.org",
                  full_name="Leer", enabled=True, user_type="System User"))
    sess.commit()
    sess.add(HasRole(name="HR-K4-LEER", parent="k4-leer@example.org", parenttype="User",
                     parentfield="roles", role="Mitglied", docstatus=0, idx=1))
    sess.add(Gruppe(name="GR-K4L", gruppenname="Gemeinde leer", docstatus=0, idx=0))
    sess.flush()
    sess.add(Mitglied(name="MIT-K4L", vorname="Leer", nachname="Person",
                      email="k4-leer@example.org", user="k4-leer@example.org",
                      status="Aktiv", ausgeschlossen=0, docstatus=0, idx=0))
    sess.flush()
    sess.add(Gruppenmitgliedschaft(name="GM-K4L", parent="GR-K4L", parenttype="Gruppe",
                                   parentfield="mitglieder", mitglied="MIT-K4L",
                                   status="Aktiv", docstatus=0, idx=0))
    sess.add(RechteModul(gruppe="GR-K4L", modul="kalender"))
    sess.add(Kalender(name="KAL-K4L", calendar_name="Leer", calendar_color="#111111",
                      docstatus=0, idx=0))
    sess.flush()
    sess.add(RechteObjekt(typ="kalender", objekt="KAL-K4L", gruppe="GR-K4L",
                          gemeinde_status="aktiv", gruppe_status="aktiv"))
    sess.add(RechteFreigabe(typ="kalender", objekt="KAL-K4L", gruppe="GR-K4L",
                            lesen=True, schreiben=True, moderieren=False))
    s = datetime(2026, 11, 5, 10, 0)
    sess.add(Element(name="EL-K4L", element_name="Ohne Kategorie",
                     element_calendar="KAL-K4L", element_start=s,
                     element_end=s + timedelta(hours=1), all_day=False,
                     status="Festgelegt", owner="k4-leer@example.org",
                     repeat_this_event=0, docstatus=0, idx=0))
    sess.commit()

    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    gesehen: list[str] = []

    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        if "eventkategorie" in " ".join(statement.split()).lower():
            gesehen.append(statement)

    set_user("k4-leer@example.org")
    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        with merkungsrahmen():
            with als_aktuelle_sitzung(sess):
                termine = get_calendar_events(
                    "2026-10-26", "2026-12-06", json.dumps(["KAL-K4L"]), "edit"
                )
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    assert [t["extendedProps"]["event_category_name"] for t in termine] == [""]
    assert gesehen == []
