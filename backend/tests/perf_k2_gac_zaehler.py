"""PERF-K2 — Zaehlt, wie oft `get_accessible_calendars` je Aufruf laeuft."""
from __future__ import annotations

import json
import os

os.environ.setdefault("DIAKRONOS_TEST_MODUS", "1")


def main() -> None:
    from perf_k2_messung import world_setup

    sess = world_setup()
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.frappe_compat.session import set_user, testnaht
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.api.kronos import calendar_get, permissions

    zaehler = {"get_accessible_calendars": 0}
    echt = permissions.get_accessible_calendars

    def _w(*a, **kw):
        zaehler["get_accessible_calendars"] += 1
        return echt(*a, **kw)

    calendar_get.get_accessible_calendars = _w
    permissions.get_accessible_calendars = _w
    naht = testnaht()
    naht.__enter__()
    ausgabe = {}
    for nutzer in ("perf00@example.org", "perf05@example.org", "admin@example.org"):
        zaehler["get_accessible_calendars"] = 0
        set_user(nutzer)
        with merkungsrahmen(), als_aktuelle_sitzung(sess):
            termine = calendar_get.get_calendar_events(
                "2026-10-26", "2026-12-06",
                json.dumps([f"KAL-P{i}" for i in range(10)]), "edit")
        ausgabe[nutzer] = {"aufrufe": zaehler["get_accessible_calendars"],
                           "termine": len(termine)}
    print(json.dumps(ausgabe, indent=2))


if __name__ == "__main__":
    main()
