"""PERF-K2 — Messung: WELCHE Abfragen wiederholen sich je Termin?

Aufruf (Wegwerf-Container, netzlos, eigenes `--project`):

    docker run --rm --network none \
        -e DIAKRONOS_TEST_MODUS=1 -e PYTHONPATH=/app \
        -v <repo>/backend:/app:ro --entrypoint python \
        <vorbau-image> /app/tests/perf_k2_messung.py

Der Datenaufbau ist der von PERF-K1 (`test_perf_k1_kalender_abfragen.py`,
10 Kalender / 50 Nutzer / 312 Termine). Gezaehlt wird per
`before_cursor_execute`, gruppiert nach normalisiertem SQL mit den Parametern
als Platzhalter — so wird sichtbar, ob dieselbe Abfrage je Termin erneut
laeuft.

Ausgabe: JSON mit Gesamtzahl, Zeit und den Top-Wiederholern (Anzahl + SQL).
Zusaetzlich die Anzahl der Aufrufe je Rechte-Kern-Funktion (Huelle zaehlt mit).
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time

os.environ.setdefault("DIAKRONOS_TEST_MODUS", "1")

_ZEILEN: list[tuple[str, str]] = []
_AKTIV = {"an": False}


def _zaehle(conn, cursor, statement, parameters, context, executemany):
    if not _AKTIV["an"]:
        return
    _ZEILEN.append((" ".join(statement.split()), str(parameters)[:120]))


def _normalisiere(sql: str) -> str:
    """Werte weg — Vorlage der Abfrage (fuer die Gruppierung)."""
    t = re.sub(r"'[^']*'", "?", sql)
    t = re.sub(r"\b\d+(\.\d+)?\b", "?", t)
    return t[:180]


def _top(zeilen, n=15):
    zaehlung: dict[str, int] = {}
    beispiel: dict[str, str] = {}
    for sql, _par in zeilen:
        k = _normalisiere(sql)
        zaehlung[k] = zaehlung.get(k, 0) + 1
        beispiel.setdefault(k, sql[:200])
    sortiert = sorted(zaehlung.items(), key=lambda kv: -kv[1])[:n]
    return [{"anzahl": v, "vorlage": k, "beispiel": beispiel[k]} for k, v in sortiert]


def _rechte_zaehler():
    """Wie oft wird jede Rechte-Kern-Funktion befragt (Huelle)?."""
    from diakronos_app import rechte as R
    from diakronos_app.rechte import kern

    namen = ["darf", "pruefstufen", "moderationsstufen", "gruppenrolle",
             "untergruppenrolle", "modul_aktiv", "ist_admin", "hat_systemrolle",
             "hauptgruppe_von", "rollen_vorladen", "_freigaben_roh",
             "_objekt_und_kontext", "_pruefstufen_roh", "_moderationsstufen_roh"]
    zaehler = {n: 0 for n in namen}
    original = {}
    for n in namen:
        fn = getattr(kern, n, None)
        if fn is None:
            continue
        original[n] = fn

        def _huelle(*a, __n=n, __fn=fn, **kw):
            zaehler[__n] += 1
            return __fn(*a, **kw)

        if n in ("darf", "pruefstufen", "moderationsstufen"):
            setattr(R, n, _huelle)
        setattr(kern, n, _huelle)
    return zaehler, original


def main() -> None:
    from sqlalchemy import event

    rechte_sess = world_setup()
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.frappe_compat.session import set_user, testnaht
    from diakronos_app.rechte.kern import merkungsrahmen

    engine = _engine()
    event.listen(engine, "before_cursor_execute", _zaehle)
    from diakronos_app.api.kronos.calendar_get import get_calendar_events

    naht = testnaht()
    naht.__enter__()
    set_user("perf00@example.org")
    filter_json = json.dumps([f"KAL-P{i}" for i in range(10)])

    ergebnis = {}
    for modus in ("edit", "view"):
        _AKTIV["an"] = False
        _ZEILEN.clear()
        zaehler, original = _rechte_zaehler()
        _AKTIV["an"] = True
        t0 = time.perf_counter()
        with merkungsrahmen():
            with als_aktuelle_sitzung(rechte_sess):
                termine = get_calendar_events("2026-10-26", "2026-12-06", filter_json, modus)
        dauer = (time.perf_counter() - t0) * 1000.0
        _AKTIV["an"] = False
        from diakronos_app import rechte as R
        from diakronos_app.rechte import kern

        for n, fn in original.items():
            setattr(kern, n, fn)
            if n in ("darf", "pruefstufen", "moderationsstufen"):
                setattr(R, n, fn)
        ergebnis[modus] = {
            "termine": len(termine),
            "ms": round(dauer, 1),
            "sql_gesamt": len(_ZEILEN),
            "je_termin": round(len(_ZEILEN) / max(1, len(termine)), 1),
            "top": _top(_ZEILEN),
            "rechte_aufrufe": zaehler,
        }
    print(json.dumps(ergebnis, indent=2, ensure_ascii=False))


def _engine():
    from diakronos_app.db import engine

    return engine


def world_setup():
    """Baut die PERF-K1-Welt direkt auf (ohne pytest-Fixture-Magie)."""
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401 — Tabellen registrieren
    from diakronos_app.models.base import Base
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
    from diakronos_app.models.kronos import Element, Kalender
    from diakronos_app.models.rechte import (
        RechteFreigabe,
        RechteGruppenrolle,
        RechteModul,
        RechteObjekt,
    )

    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool, future=True)
    Base.metadata.create_all(eng)
    fabrik = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    dbmod.engine = eng
    dbmod.SessionLocal = fabrik
    for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                    "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
        mod = __import__(modname, fromlist=["_"])
        if hasattr(mod, "SessionLocal"):
            mod.SessionLocal = fabrik

    sess = fabrik()
    nutzer = [User(name=f"perf{i:02d}@example.org", email=f"perf{i:02d}@example.org",
                   full_name=f"Person {i:02d}", enabled=True,
                   user_type="System User") for i in range(50)]
    sess.add_all(nutzer)
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
    sess.add(RechteGruppenrolle(gruppe="GR-P", untergruppe=None,
                                benutzer=nutzer[0].name, rolle="HV"))
    sess.add(RechteModul(gruppe="GR-P", modul="kalender"))
    sess.flush()

    kalender = [Kalender(name=f"KAL-P{i}", calendar_name=f"Kalender {i}",
                         calendar_color=f"#3366{i:02d}", selbstverwaltet=(i % 3 == 0),
                         docstatus=0, idx=i) for i in range(10)]
    sess.add_all(kalender)
    sess.flush()
    sess.add_all([RechteObjekt(typ="kalender", objekt=k.name, gruppe="GR-P",
                               gemeinde_status="aktiv", gruppe_status="aktiv")
                  for k in kalender])
    sess.flush()
    sess.add_all([RechteFreigabe(typ="kalender", objekt=k.name, gruppe="GR-P",
                                 lesen=True, schreiben=True, moderieren=(i < 4))
                  for i, k in enumerate(kalender)])
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


if __name__ == "__main__":
    main()
