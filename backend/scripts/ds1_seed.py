"""Synthetische DS1-Daten ausschließlich im isolierten Wegwerf-Stack.

Zeigt die Plan-Rahmen-Seiten mit echten Daten (Chorplan, Freizeit,
Musikteams, Programm) und der Lied-Pflege (Merkmal-Klartextnamen).
"""
from __future__ import annotations

import json
import os
from datetime import date
from urllib.parse import urlsplit

ADMIN_EMAIL = "admin@ds1.test"
ADMIN_PASSWORT = "Synthetisch-Ds1-Admin-0001"  # ausschließlich synthetisch
MITGLIED_EMAIL = "ds1-mitglied@ds1.test"
MITGLIED_PASSWORT = "Synthetisch-Ds1-Mitglied-0002"  # ausschließlich synthetisch


def pruefe_ziel():
    if (os.environ.get("DS1_DISPOSABLE") != "ds1test"
            or os.environ.get("APP_ENV", "").lower() in {"prod", "production"}
            or urlsplit(os.environ.get("DATABASE_URL", "")).hostname != "db"
            or urlsplit(os.environ.get("REDIS_URL", "")).hostname != "redis"):
        raise SystemExit("Seed verweigert: kein isolierter DS1-Wegwerf-Stack.")


def main():
    pruefe_ziel()  # vor Anwendungsimporten / Verbindung
    from sqlalchemy import select
    from diakronos_app import db
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Dienstbereich, Mitglied, Gruppe, Gruppenmitgliedschaft
    from diakronos_app.models.psalmos import Lied
    from diakronos_app.models.planrahmen import Plantyp
    from diakronos_app.planrahmen import ressourcen
    from diakronos_app.planrahmen.dienste import Dienste

    with db.SessionLocal.begin() as s:
        if s.scalar(select(Plantyp.id)):
            raise SystemExit("Seed verweigert: Planrahmen-Datenbank nicht leer.")
        for name in ("Chor", "Freizeit", "Musik"):
            if not s.get(Dienstbereich, name):
                s.add(Dienstbereich(name=name))
        # Der Entrypoint legt den Startbenutzer bereits an (ADMIN_EMAIL); nur
        # ergänzen, wenn er fehlt (z. B. bei manuellem Lauf).
        vorhanden = {u.name for u in s.scalars(select(User)).all()}
        neu = []
        if ADMIN_EMAIL not in vorhanden:
            neu.append(User(name=ADMIN_EMAIL, email=ADMIN_EMAIL, full_name="DS1 Admin", enabled=True,
                            password_hash=neuer_hash(ADMIN_PASSWORT)))
        if MITGLIED_EMAIL not in vorhanden:
            neu.append(User(name=MITGLIED_EMAIL, email=MITGLIED_EMAIL, full_name="Mara Test", enabled=True,
                            password_hash=neuer_hash(MITGLIED_PASSWORT)))
        s.add_all(neu)
        s.flush()
        if not s.scalar(select(HasRole.name).where(HasRole.parent == ADMIN_EMAIL,
                                                   HasRole.role == "System Manager")):
            s.add(HasRole(name="ds1-admin-role", parent=ADMIN_EMAIL, parenttype="User",
                          parentfield="roles", role="System Manager"))
        for i, name in enumerate(("Mara", "Tim", "Lisa", "Jonas", "Nina", "Finn")):
            kennung = "ds1-m-" + str(i + 1).zfill(4)
            s.add(Mitglied(name=kennung, vorname=name, nachname="Test", status="Mitglied",
                           user=MITGLIED_EMAIL if i == 0 else None,
                           email=MITGLIED_EMAIL if i == 0 else None))
        for i in range(15):
            s.add(Lied(name=f"DS1 Lied {i + 1:02d}", titel=f"DS1 Lied {i + 1:02d}",
                       aktiv=True, gesangbuch_nummer=str(101 + i)))
        s.add(Gruppe(name="Musikteams", gruppenname="Musikteams"))
        s.flush()
        for i in range(3):
            s.add(Gruppe(name=f"Gruppe {i + 1}", gruppenname=f"Gruppe {i + 1}", obergruppe="Musikteams"))
        s.flush()
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        for i in range(6):
            kennung = "ds1-m-" + str(i + 1).zfill(4)
            s.add(Gruppenmitgliedschaft(name=f"ds1-gm-chor-{i}", parent="Chor",
                                       parenttype="Gruppe", parentfield="mitglieder", mitglied=kennung,
                                       status="Aktiv"))
        for i in range(6):
            kennung = "ds1-m-" + str(i + 1).zfill(4)
            s.add(Gruppenmitgliedschaft(name=f"ds1-gm-{i}", parent=f"Gruppe {i // 2 + 1}",
                                       parenttype="Gruppe", parentfield="mitglieder", mitglied=kennung,
                                       status="Aktiv"))
        s.flush()
        d = Dienste(s, ADMIN_EMAIL)
        for name in ("chorplan", "freizeit", "musikteams", "programm"):
            d.plantyp_speichern(ressourcen.kochbuch_laden(name), date(2026, 1, 1), "DS1 Wegwerf-Abnahme")
        d.merkmale_pflegen("chorplan", [
            {"ziel": "person", "ziel_id": "ds1-m-" + str(i + 1).zfill(4),
             "schluessel": merkmal, "wert": True}
            for i in range(6) for merkmal in ("dirigent", "klavier", "einsingen")])
        d.merkmale_pflegen("chorplan", [
            {"ziel": "sammlung:lieder", "ziel_id": f"DS1 Lied {i + 1:02d}",
             "schluessel": m, "wert": "ds1-m-0002"}
            for i in range(15) for m in ("dirigent", "klavier")])
        d.merkmale_pflegen("musikteams", [
            {"ziel": "person", "ziel_id": "ds1-m-" + str(i + 1).zfill(4),
             "schluessel": "saenger", "wert": True} for i in range(6)])
        plans = {}
        for name, von, bis, parameter in (
                ("chorplan", date(2026, 6, 21), date(2026, 7, 19), {}),
                ("musikteams", date(2026, 10, 1), date(2026, 12, 31), {}),
                ("freizeit", date(2026, 11, 2), date(2026, 11, 6),
                 {"zeitraum": ["2026-11-02", "2026-11-06"], "thema": "DS1 Testfreizeit"}),
                ("programm", date(2026, 12, 13), date(2026, 12, 13),
                 {"datum": "2026-12-13", "uhrzeit": "17:00", "motto": "Adventssingen",
                  "untertitel": "Gemeinsam singen", "schlusswort": "Frieden"})):
            plans[name] = d.plan_anlegen(name, "DS1 " + name, von, bis, parameter)["id"]
        d.sammlung_pflegen("freizeit", "bibelarbeiten", [
            {"daten": {"titel": f"Thema {i + 1}"}, "reihenfolge": i}
            for i in range(5)], plan=plans["freizeit"])
        d.sammlung_pflegen("freizeit", "spiele", [{"daten": {"titel": "Ballspiel"}}])
        termin = d.plan_holen(plans["programm"])["termine"][0]["id"]
        for typ in ("lied", "szene", "lied", "predigt"):
            d.ablauf_aendern(plans["programm"], termin, "ablauf", "hinzufuegen", element_typ=typ)
    print(json.dumps({"ok": True, "plaene": plans, "admin": ADMIN_EMAIL,
                      "mitglied": MITGLIED_EMAIL}, ensure_ascii=False))


if __name__ == "__main__":
    main()
