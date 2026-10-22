"""LN1-Abnahmedaten ausschliesslich im isolierten Wegwerf-Stack.

Legt Lieder in allen drei Quellen an (Kopie, Liederbuch mit Nummer, Liederbuch
mit Seite) plus je einen Plan fuer den Chorplan und das Programm, damit die
Anzeige 'Kopie'/'JN 1297'/'WH S. 150' in Liste, Plan-Tabelle und Programm
sichtbar wird.

Der Seed verweigert den Lauf ausserhalb des isolierten LN1-Teststacks.
"""
from __future__ import annotations

import json
import os
from datetime import date
from urllib.parse import urlsplit

ADMIN_EMAIL = "admin@ln1.test"
ADMIN_PASSWORT = "Synthetisch-Ln1-Admin-0005"  # ausschliesslich synthetisch


def pruefe_ziel():
    if (os.environ.get("LN1_DISPOSABLE") != "ln1-test"
            or os.environ.get("APP_ENV", "").lower() in {"prod", "production"}
            or urlsplit(os.environ.get("DATABASE_URL", "")).hostname != "db"
            or urlsplit(os.environ.get("REDIS_URL", "")).hostname != "redis"):
        raise SystemExit("Seed verweigert: kein isolierter LN1-Wegwerf-Stack.")


def main():
    pruefe_ziel()  # vor Anwendungsimporten / Verbindung
    from sqlalchemy import select

    from diakronos_app import db
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
    )
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
        if not s.get(User, ADMIN_EMAIL):
            s.add(User(name=ADMIN_EMAIL, email=ADMIN_EMAIL, full_name="LN1 Admin",
                       enabled=True, password_hash=neuer_hash(ADMIN_PASSWORT)))
        s.flush()
        s.add(HasRole(name="ln1-admin-role", parent=ADMIN_EMAIL, parenttype="User",
                      parentfield="roles", role="System Manager"))
        for i, name in enumerate(("Mara", "Tim", "Lisa", "Jonas")):
            s.add(Mitglied(name=f"ln1-m-{i + 1:04d}", vorname=name, nachname="Lied",
                           status="Mitglied", user=ADMIN_EMAIL if i == 0 else None,
                           email=ADMIN_EMAIL if i == 0 else None))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        for i in range(4):
            s.add(Gruppenmitgliedschaft(name=f"ln1-gm-chor-{i}", parent="Chor",
                                        parenttype="Gruppe", parentfield="mitglieder",
                                        mitglied=f"ln1-m-{i + 1:04d}", status="Aktiv"))

        # LN1-Kern: drei Quellen. gesangbuch_nummer wird wie nach der Migration
        # gesetzt (Buch/Nummer getrennt), damit die ANZEIGE geprueft wird.
        s.add_all([
            Lied(name="LN1 Kopie", titel="Loses Blatt (Kopie)", aktiv=True,
                 quelle="kopie", gesangbuch_nummer=None, buch=None, seite=None),
            Lied(name="LN1 Buchlied", titel="Buchlied JN", aktiv=True,
                 quelle="buch", buch="JN", gesangbuch_nummer="1297"),
            Lied(name="LN1 Seitenlied", titel="Buchlied WH (nur Seite)", aktiv=True,
                 quelle="buch", buch="WH", seite="150"),
            Lied(name="LN1 Ohne", titel="Lied ohne Angabe", aktiv=True, quelle="ohne"),
        ])
        s.flush()

        d = Dienste(s, ADMIN_EMAIL)
        for name in ("chorplan", "programm"):
            d.plantyp_speichern(ressourcen.kochbuch_laden(name), date(2026, 1, 1),
                                "LN1 Wegwerf-Abnahme")
        d.merkmale_pflegen("chorplan", [
            {"ziel": "person", "ziel_id": f"ln1-m-{i + 1:04d}",
             "schluessel": m, "wert": True}
            for i in range(4) for m in ("dirigent", "klavier")])
        # Ein Lied je Quelle im Chorplan vorbelegen (Dirigent), damit die
        # Tabellen-Formatvorlage sie zeigt.
        d.merkmale_pflegen("chorplan", [
            {"ziel": "sammlung:lieder", "ziel_id": l,
             "schluessel": m, "wert": "ln1-m-0001"}
            for l in ("LN1 Kopie", "LN1 Buchlied", "LN1 Seitenlied")
            for m in ("dirigent", "klavier")])

        chorplan = d.plan_anlegen("chorplan", "LN1 Chorplan", date(2026, 10, 1),
                                  date(2026, 12, 31), {})["id"]
        # Zwei Termine mit je den drei Liedern in der Sammlungs-Spalte 'lieder'
        # (Felder lieder[0..2] tragen je ein Lied der Sammlung 'lieder').
        termine = d.plan_holen(chorplan)["termine"]
        for t in termine[:2]:
            for i, l in enumerate(("LN1 Kopie", "LN1 Buchlied", "LN1 Seitenlied")):
                d.eintrag_setzen(chorplan, t["id"], f"lieder[{i}]", l)

        # Programmablauf (C4): nummerierte Lieder im Ablauf-Element 'lied'.
        programm = d.plan_anlegen(
            "programm", "LN1 Adventssingen", date(2026, 12, 13), date(2026, 12, 13),
            {"datum": "2026-12-13", "uhrzeit": "17:00", "motto": "Adventssingen",
             "untertitel": "Gemeinsam singen", "schlusswort": "Frieden"})["id"]
        termin_p = d.plan_holen(programm)["termine"][0]["id"]
        for lied in ("LN1 Kopie", "LN1 Buchlied", "LN1 Seitenlied"):
            d.ablauf_aendern(programm, termin_p, "ablauf", "hinzufuegen", element_typ="lied")
        # Die neu angelegten Ablauf-Elemente ermitteln und fuellen.
        st = d.termin_struktur(programm, termin_p)
        lied_pfade = [s["feld_pfad"] for s in st["slots"]
                      if s["feld_pfad"].startswith("ablauf/") and s["feld_pfad"].endswith(".lied")]
        for pfad, lied in zip(sorted(lied_pfade), ("LN1 Kopie", "LN1 Buchlied", "LN1 Seitenlied")):
            d.eintrag_setzen(programm, termin_p, pfad, lied)

        print(json.dumps({"ok": True, "chorplan": chorplan, "programm": programm,
                          "admin": ADMIN_EMAIL}, ensure_ascii=False))


if __name__ == "__main__":
    main()
