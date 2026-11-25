"""PERF-K4a — Nachmessung: `get_kanban_board_data` im Wegwerf-Stack (-p perfk3).

Gemessen wird NUR der eine Endpunkt dieser Karte, je Rolle (Admin/HV/Mitglied),
mit demselben Messwerkzeug wie PERF-K3 (`before_cursor_execute`, eigener
Merkerrahmen je Aufruf = je Request).

Aufruf (im Container, VORHER- und NACHHER-Image):

    PYTHONPATH=/app/src:/app/tests/perf \
      python /app/tests/perf/messung_k4a.py --laeufe 3 --json /tmp/k4a.json

Die Welt legt `fabrik.py` (PERF-K3) an: 2240 Termine, 472 Vorschlaege,
160 Konflikte, 14 Kalender, 134 Mitglieder.

WICHTIG: Dieses Skript ist KEIN pytest-Test (kein `test_`-Praefix) — der
Marker `perf` in `test_perf_k3_waechter.py` haelt das Verzeichnis aus der
normalen Suite heraus.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import traceback

os.environ.setdefault("DIAKRONOS_TEST_MODUS", "1")

_AKTIV = {"an": False}
_ZEILEN: list[dict] = []


def _zaehle(conn, cursor, statement, parameters, context, executemany):
    if not _AKTIV["an"]:
        return
    herkunft = []
    for fr in traceback.extract_stack()[:-2]:
        pfad = fr.filename or ""
        if "diakronos_app" not in pfad:
            continue
        herkunft.append(f"{os.path.basename(pfad)}:{fr.lineno}:{fr.name}")
        if len(herkunft) >= 3:
            break
    _ZEILEN.append({"sql": " ".join(statement.split()), "herkunft": " <- ".join(herkunft)})


def _top(n: int = 6) -> list[dict]:
    zaehlung: dict[str, int] = {}
    herkunft: dict[str, dict[str, int]] = {}
    for z in _ZEILEN:
        k = z["sql"][:120]
        zaehlung[k] = zaehlung.get(k, 0) + 1
        herkunft.setdefault(k, {})
        herkunft[k][z["herkunft"]] = herkunft[k].get(z["herkunft"], 0) + 1
    return [
        {"anzahl": v, "sql": k,
         "herkunft": sorted(herkunft[k].items(), key=lambda kv: -kv[1])[:2]}
        for k, v in sorted(zaehlung.items(), key=lambda kv: -kv[1])[:n]
    ]


def _messe(fn) -> dict:
    from diakronos_app.rechte.kern import merkungsrahmen

    _ZEILEN.clear()
    fehler = None
    t0 = time.perf_counter()
    with merkungsrahmen():
        _AKTIV["an"] = True
        try:
            erg = fn()
        except Exception as exc:  # noqa: BLE001 — Fehlerweg wird GEMESSEN
            fehler = f"{type(exc).__name__}: {exc}"
            erg = None
        finally:
            _AKTIV["an"] = False
    return {
        "ms": (time.perf_counter() - t0) * 1000.0,
        "sql": len(_ZEILEN),
        "zeilen": list(_ZEILEN),
        "fehler": fehler,
        "anzahl": {
            k: len(v) for k, v in (erg or {}).items() if isinstance(v, (list, dict))
        },
    }


def _messe_n(fn, laeufe: int = 3) -> dict:
    roh = [_messe(fn) for _ in range(laeufe)]
    letzter = roh[-1]
    return {
        "ms_median": round(statistics.median(r["ms"] for r in roh), 1),
        "ms_min": round(min(r["ms"] for r in roh), 1),
        "sql": letzter["sql"],
        "anzahl": letzter["anzahl"],
        "fehler": letzter["fehler"],
        "top": _top(),
    }


def messen(laeufe: int = 3) -> dict:
    from diakronos_app.api.kronos.kanban_api import get_kanban_board_data
    from diakronos_app.frappe_compat.session import set_user, testnaht

    from fabrik import ADMIN, HV, MITGLIED

    rollen = {"Admin (System Manager)": ADMIN, "HV (GR-01)": HV,
              "Mitglied (GR-01)": MITGLIED}
    ausgabe = {}
    naht = testnaht()
    naht.__enter__()
    try:
        for rolle, konto in rollen.items():
            set_user(konto)
            ausgabe[rolle] = {"konto": konto, **_messe_n(get_kanban_board_data, laeufe)}
    finally:
        naht.__exit__(None, None, None)
    return ausgabe


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None)
    parser.add_argument("--laeufe", type=int, default=3)
    args = parser.parse_args(argv)

    from sqlalchemy import event, func, select

    import diakronos_app.db as dbmod
    import fabrik
    from diakronos_app.models.kronos import Element

    with dbmod.SessionLocal() as sess:
        vorhanden = sess.scalar(select(func.count()).select_from(Element)) or 0
        if vorhanden >= fabrik.TERMINE:
            kennzahlen = {"vorhanden": True, "termine": vorhanden}
        else:
            kennzahlen = fabrik.aufbauen(sess) | {"vorhanden": False}

    event.listen(dbmod.engine, "before_cursor_execute", _zaehle)
    daten = {
        "daten": kennzahlen,
        "db": dbmod.engine.url.render_as_string(hide_password=True),
        "laeufe": args.laeufe,
        "rollen": messen(laeufe=args.laeufe),
    }
    text = json.dumps(daten, indent=2, ensure_ascii=False)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
