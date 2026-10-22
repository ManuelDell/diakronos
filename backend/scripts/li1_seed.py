"""LI1-Abnahmedaten ausschliesslich im isolierten Wegwerf-Stack.

Legt einen Anmeldebenutzer mit Schreibrecht (Verantwortlicher im Dienstbereich
„Musik und Worship“) und einen zweiten ohne Schreibrecht an, dazu die
Planvorlage `chorplan` mit dem Merkmal „Thema“ und ein paar Liedern.

Der Seed verweigert den Lauf ausserhalb des isolierten LI1-Teststacks.
"""
from __future__ import annotations

import json
import os
from datetime import date
from urllib.parse import urlsplit

SCHREIBER = "schreiber@li1.test"
SCHREIBER_PW = "Li1SchreiberPw123"
LESER = "leser@li1.test"
LESER_PW = "Li1LeserPw123"


def pruefe_ziel():
    if (os.environ.get("LI1_DISPOSABLE") != "li1-test"
            or os.environ.get("APP_ENV", "").lower() in {"prod", "production"}
            or urlsplit(os.environ.get("DATABASE_URL", "")).hostname != "db"
            or urlsplit(os.environ.get("REDIS_URL", "")).hostname != "redis"):
        raise SystemExit("Seed verweigert: kein isolierter LI1-Wegwerf-Stack.")


def main():
    pruefe_ziel()  # vor Anwendungsimporten / Verbindung
    from sqlalchemy import select

    from diakronos_app import db
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        DienstbereichVerantwortlicher,
        Gruppe,
        Mitglied,
    )
    from diakronos_app.models.psalmos import Lied, Liedkategorie
    from diakronos_app.planrahmen import ressourcen
    from diakronos_app.planrahmen.dienste import Dienste

    with db.SessionLocal.begin() as s:
        if s.scalar(select(Lied.name)):
            raise SystemExit("Seed verweigert: Liedtabelle nicht leer.")
        for name in ("Chor", "Freizeit", "Musik und Worship"):
            if not s.get(Dienstbereich, name):
                s.add(Dienstbereich(name=name))
        for name, mail, pw, voll in ((SCHREIBER, SCHREIBER, SCHREIBER_PW, "Sina Schreiber"),
                                     (LESER, LESER, LESER_PW, "Leo Leser")):
            s.add(User(name=name, email=mail, full_name=voll, enabled=True,
                       password_hash=neuer_hash(pw)))
        s.flush()
        for name in (SCHREIBER, LESER):
            s.add(Mitglied(name=name, vorname=name.split("@")[0].title(), nachname="Li1",
                           status="Mitglied", user=name, email=name))
        # Anlegerecht für die Planvorlage (plantyp_speichern verlangt
        # Administratorrechte oder Bereichsverantwortung des Plantyp-Bereichs).
        # Dieselbe Rolle wie in den Abnahmen der Karten UI2/ST3: System Manager.
        s.add(HasRole(name="li1-admin-role", parent=SCHREIBER, parenttype="User",
                      parentfield="roles", role="System Manager"))
        # Schreibrecht über die Psalmos-Regel: Verantwortlicher des Bereichs
        # „Musik und Worship“.
        s.add(DienstbereichVerantwortlicher(name="li1-bv-musik", parent="Musik und Worship",
                                            parenttype="Dienstbereich",
                                            parentfield="verantwortliche", user=SCHREIBER))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add_all([Liedkategorie(name="Lob", kategoriename="Lob"),
                   Liedkategorie(name="Abendmahl", kategoriename="Abendmahl")])
        s.add_all([
            Lied(name="LI1 Bestand", titel="Bestandslied", aktiv=True, quelle="buch",
                 buch="JN", gesangbuch_nummer="1"),
        ])
        s.flush()

        d = Dienste(s, SCHREIBER)
        d.plantyp_speichern(ressourcen.kochbuch_laden("chorplan"), date(2026, 1, 1),
                            "LI1 Wegwerf-Abnahme")
        print(json.dumps({"ok": True, "schreiber": SCHREIBER, "leser": LESER},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
