"""PERF-K2 — Top-Wiederholer je Nutzerrolle.

Gleicher Aufbau wie `perf_k2_messung.py` (PERF-K1-Welt), aber je Nutzer:
  * Admin            (System Manager)
  * Mitglied         (Mitglied der Gruppe)
  * Gast             (angemeldet, aber kein Mitglied/keine Rolle)
  * Moderator        (HV der Gruppe — moderiert 4 Kalender)

Je Nutzer: Abfragezahl, Dauer, Top-10-Vorlagen, Rechte-Zaehler.
"""
from __future__ import annotations

import json
import os
import re
import time

os.environ.setdefault("DIAKRONOS_TEST_MODUS", "1")

_ZEILEN: list[str] = []
_AKTIV = {"an": False}


def _zaehle(conn, cursor, statement, parameters, context, executemany):
    if _AKTIV["an"]:
        _ZEILEN.append(" ".join(statement.split()))


def _normalisiere(sql: str) -> str:
    t = re.sub(r"'[^']*'", "?", sql)
    t = re.sub(r"\b\d+(\.\d+)?\b", "?", t)
    return t[:170]


def _top(n=10):
    zaehlung: dict[str, int] = {}
    for sql in _ZEILEN:
        k = _normalisiere(sql)
        zaehlung[k] = zaehlung.get(k, 0) + 1
    return [{"anzahl": v, "vorlage": k}
            for k, v in sorted(zaehlung.items(), key=lambda kv: -kv[1])[:n]]


def main() -> None:
    from sqlalchemy import event

    from perf_k2_messung import world_setup, _rechte_zaehler

    sess = world_setup()
    from diakronos_app.db import als_aktuelle_sitzung, engine
    from diakronos_app.frappe_compat.session import set_user, testnaht
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.api.kronos.calendar_get import get_calendar_events

    event.listen(engine, "before_cursor_execute", _zaehle)
    naht = testnaht()
    naht.__enter__()

    # Admin-Konto anlegen (System Manager), Gast-Konto ohne Mitglied.
    from diakronos_app.models.core import HasRole, User

    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True, user_type="System User"))
    sess.add(User(name="gast@example.org", email="gast@example.org",
                  full_name="Gast", enabled=True, user_type="System User"))
    sess.flush()
    sess.add(HasRole(name="HR-ADM", parent="admin@example.org", parenttype="User",
                     parentfield="roles", role="System Manager", docstatus=0, idx=1))
    sess.commit()

    filter_json = json.dumps([f"KAL-P{i}" for i in range(10)])
    nutzer = {
        "Moderator": "perf00@example.org",   # HV der Gruppe
        "Mitglied": "perf05@example.org",    # einfaches Mitglied
        "Gast": "gast@example.org",          # angemeldet, kein Mitglied
        "Admin": "admin@example.org",        # System Manager
    }
    ausgabe = {}
    for rolle, name in nutzer.items():
        for modus in ("edit", "view"):
            _ZEILEN.clear()
            set_user(name)
            zaehler, original = _rechte_zaehler()
            _AKTIV["an"] = True
            t0 = time.perf_counter()
            with merkungsrahmen():
                with als_aktuelle_sitzung(sess):
                    termine = get_calendar_events("2026-10-26", "2026-12-06", filter_json, modus)
            dauer = (time.perf_counter() - t0) * 1000.0
            _AKTIV["an"] = False
            from diakronos_app import rechte as R
            from diakronos_app.rechte import kern

            for n, fn in original.items():
                setattr(kern, n, fn)
                if n in ("darf", "pruefstufen", "moderationsstufen"):
                    setattr(R, n, fn)
            ausgabe[f"{rolle}/{modus}"] = {
                "termine": len(termine), "ms": round(dauer, 1),
                "sql": len(_ZEILEN),
                "je_termin": round(len(_ZEILEN) / max(1, len(termine)), 2),
                "top": _top(12),
                "rechte": {k: v for k, v in zaehler.items() if v},
            }
    print(json.dumps(ausgabe, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
