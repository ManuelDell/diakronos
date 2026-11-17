"""PERF-K1 — Messung der Kalender-Startaufrufe (Wegwerf-DB, keine Netzverbindung).

Laeuft IM Vorbau-Image mit `--network none` und eigener SQLite-DB:

    docker run --rm --network none -e DIAKRONOS_TEST_MODUS=1 \
        -v <hier>:/mess:ro --entrypoint python <vorbau-image> /mess/perf_k1_messung.py

Gemessen wird die Reihenfolge, die `Kalender.vue` beim Seitenaufbau ausloest
(Monatsansicht, Moderator mit 4 sichtbaren Kalendern), je Aufruf:

  * Zeit (Median aus n Laeufen)
  * Anzahl SQL-ABFRAGEN (SQLAlchemy-Event-Zaehler, `before_cursor_execute`)
  * Anzahl offener Sitzungen (Hinweis auf Sitzungs-Churn)

Zusaetzlich wird gezaehlt, wie oft der Rechte-Kern (`rechte.darf`,
`pruefstufen`, `moderationsstufen`) je Aufruf laeuft — der Verdacht
„Rechtepruefung ist der Engpass“ wird damit gemessen statt geraten.

Die Datenmenge ist realistisch geseedet: 10 Kalender, 50 Nutzer, 300 Termine
inkl. 6 Serien (je 12 Folgetermine) — Vorgabe der Karte PERF-K1.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import traceback

os.environ.setdefault("DIAKRONOS_TEST_MODUS", "1")

from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

# ── Zaehler ────────────────────────────────────────────────────────────────
_ZAEHLER = {"sql": 0, "sql_zeit": 0.0, "sql_text": []}


def _zaehle_sql(conn, cursor, statement, parameters, context, executemany):
    _ZAEHLER["sql"] += 1
    if len(_ZAEHLER["sql_text"]) < 20000:
        _ZAEHLER["sql_text"].append(" ".join(statement.split())[:160])


def _zuruecksetzen():
    _ZAEHLER["sql"] = 0
    _ZAEHLER["sql_zeit"] = 0.0
    _ZAEHLER["sql_text"] = []


def _messe(fn, *args, mit_rahmen=True, **kwargs):
    """Ein Aufruf wie EIN Request: eigener Merkungsrahmen je Messung."""
    try:  # Basis-Stand (vor PERF-K1) kennt keinen Merker
        from diakronos_app.rechte.kern import merkungsrahmen
    except ImportError:
        merkungsrahmen = None
    if merkungsrahmen is None or not mit_rahmen:
        ergebnis = _messe_roh(fn, *args, **kwargs)
        ergebnis["merker_nach"] = None
        return ergebnis

    if mit_rahmen:
        with merkungsrahmen():
            ergebnis = _messe_roh(fn, *args, **kwargs)
        from diakronos_app.rechte.kern import _MERKER

        ergebnis["merker_nach"] = len(_MERKER.get() or {})
        return ergebnis
    return _messe_roh(fn, *args, **kwargs)


def _messe_roh(fn, *args, **kwargs):
    _zuruecksetzen()
    t0 = time.perf_counter()
    try:
        ergebnis = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — Fehlerweg wird mitgemessen
        return {"ms": round((time.perf_counter() - t0) * 1000.0, 2),
                "sql": _ZAEHLER["sql"], "sql_text": list(_ZAEHLER["sql_text"]),
                "fehler": type(exc).__name__, "ergebnis": None}
    dauer = (time.perf_counter() - t0) * 1000.0
    return {"ms": round(dauer, 2), "sql": _ZAEHLER["sql"],
            "sql_text": list(_ZAEHLER["sql_text"]), "ergebnis": ergebnis}


# ── DB-Aufbau (eigene Wegwerf-DB: SQLite in-memory, StaticPool) ────────────
def baue_db():
    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401
    from diakronos_app.models.base import Base

    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool, future=True)
    event.listen(eng, "before_cursor_execute", _zaehle_sql)
    Base.metadata.create_all(eng)
    fabrik = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)

    dbmod.engine = eng
    dbmod.SessionLocal = fabrik
    for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                    "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
        mod = __import__(modname, fromlist=["_"])
        if hasattr(mod, "SessionLocal"):
            mod.SessionLocal = fabrik
    return eng, fabrik


def seede(fabrik):
    """10 Kalender, 50 Nutzer, 300 Termine inkl. Serien (Vorgabe PERF-K1)."""
    from datetime import datetime, timedelta

    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Gruppe, Gruppenmitgliedschaft, Mitglied,
    )
    from diakronos_app.models.rechte import RechteGruppenrolle
    from diakronos_app.models.kronos import Element, Eventkategorie, Kalender, Ressource

    sess = fabrik()

    # 50 Nutzer + Mitglieder (je eindeutige E-Mail, Fachentscheidung SEC-b).
    nutzer = []
    for i in range(50):
        name = f"person{i:02d}@example.org"
        nutzer.append(User(name=name, email=name, full_name=f"Person {i:02d}", enabled=True))
    sess.add_all(nutzer)
    sess.flush()
    sess.add_all([
        HasRole(name=f"HR-{i}", parent=n.name, parenttype="User", parentfield="roles",
                role=("Kalender Moderation" if i < 3 else "Mitglied"), docstatus=0, idx=1)
        for i, n in enumerate(nutzer)
    ])
    sess.flush()

    sess.add(Gruppe(name="GR-1", gruppenname="Gemeinde", docstatus=0, idx=0))
    sess.flush()
    mitglieder = []
    for i, n in enumerate(nutzer):
        m = Mitglied(name=f"MIT-{i:02d}", vorname=f"Person",
                     nachname=f"{i:02d}", email=n.email, user=n.name, status="Aktiv",
                     ausgeschlossen=0, docstatus=0, idx=i)
        mitglieder.append(m)
    sess.add_all(mitglieder)
    sess.flush()
    sess.add_all([
        Gruppenmitgliedschaft(name=f"GM-{i:02d}", parent="GR-1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=m.name, status="Aktiv",
                              docstatus=0, idx=i)
        for i, m in enumerate(mitglieder)
    ])
    # Der Messnutzer ist HV der Gruppe (damit er moderiert/schreibt).
    sess.add(RechteGruppenrolle(gruppe="GR-1", untergruppe=None,
                                benutzer=nutzer[0].name, rolle="HV"))
    sess.flush()

    kalender = []
    for i in range(10):
        kalender.append(Kalender(
            name=f"KAL-{i}", calendar_name=f"Kalender {i}",
            calendar_color=f"#3366{i:02d}", selbstverwaltet=(i % 3 == 0),
            docstatus=0, idx=i))
    sess.add_all(kalender)
    sess.flush()

    from diakronos_app.models.rechte import RechteFreigabe, RechteModul, RechteObjekt

    # PERF-K1 (Review 17.11.): Das Modul „kalender“ muss fuer die Gruppe AKTIV
    # sein, sonst antwortet der Rechte-Kern auf JEDE Frage `modul_aus`
    # (`rechte.kern.modul_aktiv`) und der Endpunkt liefert 0 Termine — der
    # Messlauf maß dann den leeren Weg statt der Monatsansicht.
    sess.add(RechteModul(gruppe="GR-1", modul="kalender"))
    sess.flush()
    for i, k in enumerate(kalender):
        sess.add(RechteObjekt(typ="kalender", objekt=k.name, gruppe="GR-1",
                              untergruppe=None, gemeinde_status="aktiv",
                              gruppe_status="aktiv"))
    sess.flush()
    for i, k in enumerate(kalender):
        sess.add(RechteFreigabe(
            typ="kalender", objekt=k.name, benutzer=None, gruppe="GR-1",
            lesen=True, schreiben=True, moderieren=(i < 4)))

    sess.add_all([
        Eventkategorie(name=f"KAT-{i}", event_category_name=f"Kategorie {i}",
                       farbe="#3366ff", docstatus=0, idx=i) for i in range(5)
    ])
    sess.add_all([
        Ressource(name=f"RES-{i}", ressource_name=f"Raum {i}", docstatus=0, idx=i)
        for i in range(8)
    ])
    sess.flush()

    # 240 Einzeltermine im November 2026 + 6 Serien mit je 12 Folgeterminen (300 gesamt).
    elemente = []
    start = datetime(2026, 11, 1, 9, 0)
    for i in range(240):
        s = start + timedelta(days=i % 29, hours=(i % 8))
        elemente.append(Element(
            name=f"EL-{i:03d}", element_name=f"Termin {i}",
            element_calendar=f"KAL-{i % 10}",
            element_start=s, element_end=s + timedelta(hours=1),
            all_day=(i % 7 == 0), status=("Festgelegt" if i % 5 else "Vorschlag"),
            element_category=f"KAT-{i % 5}", ressource=(f"RES-{i % 8}" if i % 4 == 0 else None),
            owner=nutzer[i % 50].name, repeat_this_event=0, docstatus=0, idx=i))
    for k in range(6):
        serie = f"SER-{k}"
        s0 = datetime(2026, 10, 5, 18, 0)
        for j in range(12):
            s = s0 + timedelta(days=7 * j)
            elemente.append(Element(
                name=f"EL-S{k}-{j:02d}", element_name=f"Serie {k} Folge {j}",
                element_calendar=f"KAL-{k}", element_start=s,
                element_end=s + timedelta(hours=2), all_day=False, status="Festgelegt",
                series_id=serie, owner=nutzer[k].name, repeat_this_event=0,
                docstatus=0, idx=1000 + k * 20 + j))
    sess.add_all(elemente)
    sess.commit()
    sess.close()
    return {"kalender": 10, "nutzer": 50, "termine": len(elemente)}


# ── Startaufrufe wie Kalender.vue ──────────────────────────────────────────
def messe_start(rahmen=True):
    import importlib
    _se = importlib.import_module("diakronos_app.frappe_compat.session")
    import diakronos_app.api  # noqa: F401 — Registrierung
    from diakronos_app.api.kronos.permissions import get_accessible_calendars
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.api.kronos.kanban_api import get_kanban_board_data, get_moderation_count
    from diakronos_app.api.kronos.kalender_verwaltung import get_kalender_verwaltung
    from diakronos_app.api.session import get_current_user_context

    ausgabe = {}
    _naht = _se.testnaht()  # ContextManager-Objekt FESTHALTEN (nicht neu erzeugen)
    _naht.__enter__()
    # Der Produktivpfad oeffnet den Rahmen je Request
    # (`RequestContextMiddleware`); `_messe` bildet das je Messung nach.
    _se.set_user(os.environ.get("PERF_K1_NUTZER", "person00@example.org"))
    try:
        # 1. get_accessible_calendars (useKronosStore.fetchAccessibleCalendars)
        laeufe = [_messe(get_accessible_calendars) for _ in range(3)]
        ausgabe["get_accessible_calendars"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"],
            "sql_text": laeufe[-1]["sql_text"],
            "anzahl_kalender": len(laeufe[-1]["ergebnis"] or []),
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
        # 2. get_kalender_verwaltung
        # Ohne Verwaltungsrecht wirft der Endpunkt (403) — gemessen wird dann
        # der Fehlerweg, damit die Zahl trotzdem belastbar ist.
        laeufe = [_messe(get_kalender_verwaltung) for _ in range(3)]
        ausgabe["get_kalender_verwaltung"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"], "sql_text": laeufe[-1]["sql_text"],
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
        # 3. get_current_user_context
        laeufe = [_messe(get_current_user_context) for _ in range(3)]
        ausgabe["get_current_user_context"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"], "sql_text": laeufe[-1]["sql_text"],
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
        # 4. get_moderation_count
        laeufe = [_messe(get_moderation_count) for _ in range(3)]
        ausgabe["get_moderation_count"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"], "sql_text": laeufe[-1]["sql_text"],
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
        # 5. get_calendar_events — Monatsansicht November 2026 (FullCalendar-Fenster)
        filter_json = json.dumps([f"KAL-{i}" for i in range(10)])
        laeufe = [_messe(get_calendar_events, "2026-10-26", "2026-12-06", filter_json, "view")
                  for _ in range(3)]
        ausgabe["get_calendar_events_view"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"], "sql_text": laeufe[-1]["sql_text"],
            "anzahl_termine": len(laeufe[-1]["ergebnis"] or []),
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
        laeufe = [_messe(get_calendar_events, "2026-10-26", "2026-12-06", filter_json, "edit")
                  for _ in range(3)]
        ausgabe["get_calendar_events_edit"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"], "sql_text": laeufe[-1]["sql_text"],
            "anzahl_termine": len(laeufe[-1]["ergebnis"] or []),
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
        # 6. get_kanban_board_data (Prüf-Spalte)
        laeufe = [_messe(get_kanban_board_data) for _ in range(3)]
        ausgabe["get_kanban_board_data"] = {
            "ms_median": statistics.median(r["ms"] for r in laeufe),
            "sql": laeufe[-1]["sql"], "sql_text": laeufe[-1]["sql_text"],
            "fehler": laeufe[-1].get("fehler"),
            "merker": laeufe[-1].get("merker_nach"),
        }
    finally:
        _naht.__exit__(None, None, None)
    return ausgabe


def _gruppiere(sql_text):
    """SQL-Texte nach Vorlage gruppieren (Werte abgeschnitten)."""
    import re
    zaehlung = {}
    for t in sql_text:
        schluessel = re.sub(r"'[^']*'|\d+", "?", t)[:90]
        zaehlung[schluessel] = zaehlung.get(schluessel, 0) + 1
    return dict(sorted(zaehlung.items(), key=lambda kv: -kv[1])[:12])


def main():
    daten = {}
    eng, fabrik = baue_db()
    from diakronos_app.frappe_compat import benutzer_status, sitzungen, loginversuche
    from redis_stub import StubRedis

    stub = StubRedis()
    sitzungen._client = lambda: stub
    loginversuche._client = lambda: stub
    benutzer_status._client = lambda: stub

    daten["seed"] = seede(fabrik)
    roh = messe_start()
    # PERF-K1: Der Merker wird NICHT vorgewaermt — jede Messung startet mit
    # leerem Merker (eigener Rahmen in `_messe`), sonst waere die Abfragezahl
    # geschoent.
    try:
        from diakronos_app.rechte.kern import _MERKER

        daten["merker_rest"] = len(_MERKER.get() or {})
    except ImportError:  # Basis-Stand (vor PERF-K1): keinen Merker
        daten["merker_rest"] = None
    for name, wert in roh.items():
        wert["sql_vorlagen"] = _gruppiere(wert.pop("sql_text", []))
    daten["aufrufe"] = roh
    daten["summe_sql"] = sum(v["sql"] for v in roh.values())
    daten["summe_ms"] = round(sum(v["ms_median"] for v in roh.values()), 2)
    print(json.dumps(daten, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
