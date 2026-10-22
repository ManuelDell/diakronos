"""MAIL-1: Testkonten für den isolierten Wegwerf-Stack (nur Abnahme).

Legt zwei Konten an, mehr nicht:
* ``ma1-admin@synthetisch.invalid``      — System Manager (darf den Mailversand)
* ``ma1-verwalter@synthetisch.invalid``  — Mitgliederadministrator (sieht nur ja/nein)

Das SMTP-Postfach wird NICHT hier gesetzt, sondern in der Oberfläche — genau
das ist der Prüfgegenstand der Karte.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

ADMIN_EMAIL = "ma1-admin@synthetisch.invalid"
ADMIN_PASSWORT = "Synthetisch-MA1-Admin-Test"  # ausschließlich synthetisch, Testwert
VERWALTER_EMAIL = "ma1-verwalter@synthetisch.invalid"
VERWALTER_PASSWORT = "Synthetisch-MA1-Verwalter-Test"  # ausschließlich synthetisch, Testwert


def pruefe_ziel():
    if (os.environ.get("MA1_DISPOSABLE") != "ma1-test"
            or os.environ.get("APP_ENV", "").lower() in {"prod", "production"}
            or urlsplit(os.environ.get("DATABASE_URL", "")).hostname != "db"
            or urlsplit(os.environ.get("REDIS_URL", "")).hostname != "redis"):
        raise SystemExit("Seed verweigert: kein isolierter MAIL-1-Wegwerf-Stack.")


def main():
    pruefe_ziel()  # vor Anwendungsimporten / Verbindung
    from sqlalchemy import select

    from diakronos_app import db
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    with db.SessionLocal.begin() as s:
        if s.scalar(select(User.name).where(User.name == ADMIN_EMAIL)):
            raise SystemExit("Seed verweigert: Testkonten gibt es schon.")
        s.add_all([
            User(name=ADMIN_EMAIL, email=ADMIN_EMAIL, full_name="MAIL-1 Hauptadmin",
                 enabled=True, password_hash=neuer_hash(ADMIN_PASSWORT)),
            User(name=VERWALTER_EMAIL, email=VERWALTER_EMAIL, full_name="MAIL-1 Verwalterin",
                 enabled=True, password_hash=neuer_hash(VERWALTER_PASSWORT)),
        ])
        s.flush()
        s.add_all([
            HasRole(name="ma1-admin-role", parent=ADMIN_EMAIL, parenttype="User",
                    parentfield="roles", role="System Manager", docstatus=0, idx=1),
            HasRole(name="ma1-admin-role-v", parent=ADMIN_EMAIL, parenttype="User",
                    parentfield="roles", role="Mitgliederadministrator", docstatus=0, idx=2),
            HasRole(name="ma1-verwalter-role", parent=VERWALTER_EMAIL, parenttype="User",
                    parentfield="roles", role="Mitgliederadministrator", docstatus=0, idx=1),
        ])
        # Eine Person mit offenem Löschantrag: ohne Mailversand darf „freigeben“
        # nicht durchgehen, mit Mailversand muss die Meldung rausgehen.
        s.add(Mitglied(name="MA1-Person", vorname="Lea", nachname="Beispiel",
                       email="lea.beispiel@synthetisch.invalid", status="Mitglied"))
    print("MAIL-1: Testkonten angelegt.")


if __name__ == "__main__":
    main()
