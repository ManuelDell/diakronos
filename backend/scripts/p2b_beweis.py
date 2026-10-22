"""P2b-Beweis: die portierten Endpunkte laufen end-to-end mit echten Daten.

Laeuft gegen die Compose-Umgebung (Postgres). Legt Fixtures in einer
Transaktion an, misst die HTTP-Antworten ueber TestClient und raeumt wieder auf.

Aufruf:
    docker run --rm --network diakronos-standalone_default \
      -v "$PWD/backend:/w" -e PYTHONPATH=/w/src -e PYTHONDONTWRITEBYTECODE=1 \
      -e DATABASE_URL=... -e REDIS_URL=... \
      -w /w diakronos-standalone-app:latest python /w/scripts/p2b_beweis.py
"""

from __future__ import annotations

import json
import sys

from fastapi.testclient import TestClient
from sqlalchemy import text

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.main import app

FAILURES: list[str] = []
CHECKS = 0

# Rollen fuer den Test injizieren: die echte Rollenquelle ist P3
# (`permissions.get_roles()` liefert bis dahin fail-closed `[]`).
_ROLE_OVERRIDE: list[str] = []


def _install_role_override() -> None:
	from diakronos_app.frappe_compat import permissions as perms

	perms.get_roles = lambda user=None: list(_ROLE_OVERRIDE)



def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    from diakronos_app.db import engine

    c = TestClient(app)
    set_user("Administrator")
    _install_role_override()

    # ── Fixtures ────────────────────────────────────────────────────────────
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM mitglied WHERE name LIKE 'P2BTEST-%'"))
        conn.execute(
            text(
                """
                INSERT INTO mitglied (name, vorname, nachname, email, status, wohnort,
                                      postleitzahl, "straße", geschlecht, familienstand,
                                      ancestor_path, telefonnummer, docstatus, idx,
                                      benutzer_mit_mitglied_anlegen, auf_bemerkung_gesetzt,
                                      ausgeschlossen, datenschutz_einwilligung,
                                      foto_einwilligung, werbeeinwilligung)
                VALUES
                  ('P2BTEST-1', 'Anna',  'Muster',   'anna@example.org',  'Mitglied',
                   'Heilbronn', '74072', 'Marktplatz 1', 'weiblich', 'ledig',
                   '/Gruppe-A/Bereich-Nord/', '+491111', 0, 0,
                   false, false, false, true, false, true),
                  ('P2BTEST-2', 'Berta', 'Beispiel', 'berta@example.org', 'Gast',
                   'Neckarsulm', '74172', 'Hauptstr. 2', 'weiblich', 'ledig',
                   '/Gruppe-B/', '+492222', 0, 0,
                   false, false, false, false, false, false),
                  ('P2BTEST-3', 'Carl',  'Muster',   'carl@example.org',  'Mitglied',
                   'Heilbronn', '74074', 'Alleestr. 3', 'maennlich', 'verheiratet',
                   '/Gruppe-A/', '+493333', 0, 0,
                   false, false, false, true, true, false)
                """
            )
        )

    print("== get_mitglieder_liste: Admin-Rolle sieht alle ==")
    _ROLE_OVERRIDE[:] = ["Mitgliederadministrator"]
    try:
        r = c.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
        body = r.json()["message"]
        check("HTTP 200", r.status_code == 200, str(r.status_code))
        check("success=True", body.get("success") is True)
        names = sorted(d["name"] for d in body["data"] if d["name"].startswith("P2BTEST-"))
        check("3 Fixtures sichtbar", len(names) == 3, str(names))
        check("total >= 3", body["total"] >= 3, str(body["total"]))
    finally:
        pass

    print()
    print("== Antwortstruktur == (Vertrag: data/total/start/limit) ==")
    for key in ("success", "data", "total", "start", "limit"):
        check(f"Schluessel {key!r}", key in body)
    row = next(d for d in body["data"] if d["name"] == "P2BTEST-1")
    for field in ("name", "vorname", "nachname", "full_name", "email", "status",
                  "wohnort", "postleitzahl", "geburtstag", "ancestor_path"):
        check(f"Feld {field!r}", field in row)
    check("full_name kombiniert", row["full_name"] == "Anna Muster", row["full_name"])

    print()
    print("== suche ==")
    r = c.get("/api/method/mitglieder.get_mitglieder_liste",
              params={"suche": "Muster", "limit": 50})
    found = sorted(d["name"] for d in r.json()["message"]["data"]
                   if d["name"].startswith("P2BTEST-"))
    check("'Muster' -> P2BTEST-1 + P2BTEST-3", found == ["P2BTEST-1", "P2BTEST-3"], str(found))
    r = c.get("/api/method/mitglieder.get_mitglieder_liste",
              params={"suche": "berta@example", "limit": 50})
    found = [d["name"] for d in r.json()["message"]["data"] if d["name"].startswith("P2BTEST-")]
    check("E-Mail-Suche findet Berta", found == ["P2BTEST-2"], str(found))

    print()
    print("== status-Filter ==")
    r = c.get("/api/method/mitglieder.get_mitglieder_liste",
              params={"status": "Gast", "limit": 50})
    msg = r.json()["message"]
    found = [d["name"] for d in msg["data"] if d["name"].startswith("P2BTEST-")]
    check("status=Gast -> nur P2BTEST-2", found == ["P2BTEST-2"], str(found))
    check("total zaehlt denselben Filter", msg["total"] == len(msg["data"]),
          f"total={msg['total']} len={len(msg['data'])}")

    print()
    print("== Sortierung + Pagination ==")
    r = c.get("/api/method/mitglieder.get_mitglieder_liste",
              params={"sort_by": "vorname", "sort_order": "desc", "status": "Mitglied",
                      "limit": 50})
    vornamen = [d["vorname"] for d in r.json()["message"]["data"] if d["name"].startswith("P2BTEST-")]
    check("sort desc nach vorname", vornamen == sorted(vornamen, reverse=True), str(vornamen))
    all_rows = c.get("/api/method/mitglieder.get_mitglieder_liste",
                     params={"status": "Mitglied", "limit": 50}).json()["message"]["data"]
    page1 = c.get("/api/method/mitglieder.get_mitglieder_liste",
                  params={"status": "Mitglied", "limit": 1, "start": 0}).json()["message"]
    page2 = c.get("/api/method/mitglieder.get_mitglieder_liste",
                  params={"status": "Mitglied", "limit": 1, "start": 1}).json()["message"]
    check("Pagination offset verschiebt", page1["data"][0]["name"] != page2["data"][0]["name"],
          f"{page1['data'][0]['name']} vs {page2['data'][0]['name']}")
    check("limit wirkt", len(page1["data"]) == 1 and len(page2["data"]) == 1)
    check("total bleibt Gesamtzahl", page1["total"] == page2["total"] == len(all_rows),
          f"{page1['total']}/{page2['total']}/{len(all_rows)}")

    print()
    print("== Sort-Whitelist blockt Injection ==")
    r = c.get("/api/method/mitglieder.get_mitglieder_liste",
              params={"sort_by": "name; DROP TABLE mitglied--", "limit": 1})
    check("boeser sort_by -> 200 (auf 'name' zurueckgesetzt)", r.status_code == 200,
          str(r.status_code))
    still = c.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 1})
    check("Tabelle existiert noch", still.status_code == 200)

    print()
    print("== get_mitglied_detail: kein Zugriff (fail closed) ==")
    _ROLE_OVERRIDE[:] = []  # keine Rolle -> muss verweigern
    r = c.get("/api/method/mitglieder.get_mitglied_detail",
              params={"mitglied_id": "P2BTEST-1"})
    check("403 ohne Rolle", r.status_code == 403, f"{r.status_code} {r.text[:80]}")
    check("exception=PermissionError",
          r.json().get("exception") == "PermissionError", r.text[:80])

    print()
    print("== get_mitglied_detail: Admin mit Rolle ==")
    _ROLE_OVERRIDE[:] = ["Mitgliederadministrator"]
    try:
        r = c.get("/api/method/mitglieder.get_mitglied_detail",
                  params={"mitglied_id": "P2BTEST-1"})
        check("HTTP 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        if r.status_code == 200:
            msg = r.json()["message"]
            check("success=True", msg.get("success") is True)
            data = msg["data"]
            check("richtiges Mitglied", data.get("name") == "P2BTEST-1", str(data.get("name")))
            check("vorname", data.get("vorname") == "Anna", str(data.get("vorname")))
            check("DSGVO-Block vorhanden", isinstance(data.get("dsgvo"), dict))
            for key in ("datenschutz", "datenschutz_datum", "foto", "foto_datum",
                        "werbung", "werbung_datum"):
                check(f"dsgvo.{key}", key in data.get("dsgvo", {}))
            check("gruppenmitgliedschaften ist Liste",
                  isinstance(data.get("gruppenmitgliedschaften"), list))
            p = msg["permissions"]
            check("permissions.can_view True", p.get("can_view") is True)
            check("permissions.can_edit True", p.get("can_edit") is True)
            check("permissions.can_view_sensitive True", p.get("can_view_sensitive") is True)
            check("permissions.can_delete False (wie Original)", p.get("can_delete") is False)
            check("permissions.reason=admin_role", p.get("reason") == "admin_role")
    finally:
        _ROLE_OVERRIDE[:] = []

    print()
    print("== get_mitglied_detail: fehlendes Mitglied ==")
    _ROLE_OVERRIDE[:] = ["Mitgliederadministrator"]
    try:
        r = c.get("/api/method/mitglieder.get_mitglied_detail",
                  params={"mitglied_id": "P2BTEST-GIBTSNICHT"})
        check("404 statt 500", r.status_code == 404, f"{r.status_code} {r.text[:120]}")
        check("exception=DoesNotExistError",
              r.json().get("exception") == "DoesNotExistError", r.text[:120])
    finally:
        _ROLE_OVERRIDE[:] = []

    print()
    print("== Nicht-Admin ohne Mitglied: Sichtbarkeit leer, nicht alles ==")
    _ROLE_OVERRIDE[:] = []
    set_user("kein-mitglied@example.org")
    try:
        r = c.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
        msg = r.json()["message"]
        check("HTTP 200", r.status_code == 200, str(r.status_code))
        check("keine Daten sichtbar", msg["data"] == [], json.dumps(msg)[:120])
        check("total == 0", msg["total"] == 0, str(msg["total"]))
    finally:
        _ROLE_OVERRIDE[:] = []
        set_user("Administrator")

    print()
    print("== Admin-Rolle: Liste zeigt alle Fixtures ==")
    _ROLE_OVERRIDE[:] = ["Mitgliederadministrator"]
    try:
        r = c.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
        msg = r.json()["message"]
        found = sorted(d["name"] for d in msg["data"] if d["name"].startswith("P2BTEST-"))
        check("3 Fixtures sichtbar", found == ["P2BTEST-1", "P2BTEST-2", "P2BTEST-3"], str(found))
        check("total zaehlt 3", msg["total"] == 3, str(msg["total"]))
        check("alle Felder da",
              all(k in msg["data"][0] for k in ("name", "vorname", "nachname", "email", "status")))
    finally:
        _ROLE_OVERRIDE[:] = []

    print()
    print("== Guest wird abgewiesen ==")
    set_user("Guest")
    try:
        r = c.get("/api/method/mitglieder.get_mitglieder_liste")
        check("403 fuer Guest", r.status_code == 403, str(r.status_code))
        check("Meldung wie Original", r.json().get("message") == "Zugriff verweigert.",
              r.text[:120])
    finally:
        set_user("Administrator")

    print()
    print("== Endpunkt ist registriert ==")
    from diakronos_app.frappe_compat.registry import lookup, options_for
    for path in ("mitglieder.get_mitglieder_liste", "mitglieder.get_mitglied_detail"):
        fn = lookup(path)
        check(f"{path} registriert", fn is not None)
        if fn:
            check(f"{path} allow_guest=False",
                  options_for(fn).get("allow_guest") is False,
                  str(options_for(fn)))

    # ── Cleanup ─────────────────────────────────────────────────────────────
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM mitglied WHERE name LIKE 'P2BTEST-%'"))
    with engine.connect() as conn:
        left = conn.execute(
            text("SELECT count(*) FROM mitglied WHERE name LIKE 'P2BTEST-%'")
        ).scalar()
    print()
    check("Fixtures aufgeraeumt", left == 0, f"{left} verbleiben")

    print()
    print(f"───────────────  {CHECKS - len(FAILURES)}/{CHECKS} Checks bestanden  ───────────────")
    if FAILURES:
        print("FEHLGESCHLAGEN:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALLE CHECKS BESTANDEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
