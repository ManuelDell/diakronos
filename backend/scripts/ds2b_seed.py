"""Synthetische DS2b-Daten ausschließlich im isolierten Wegwerf-Stack.

Zeigt Mitglieder, Gruppen/Organigramm, Wiki, Beitraege und Lieder mit echten
Daten, damit die Screenshots der Design-System-Abnahme nicht leer sind.
Muster/Guard 1:1 aus ds1_seed.py übernommen.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlsplit

ADMIN_EMAIL = "admin@ds2b.test"
ADMIN_PASSWORT = "Synthetisch-Ds2b-Admin-0003"
MITGLIED_EMAIL = "ds2b-mitglied@ds2b.test"
MITGLIED_PASSWORT = "Synthetisch-Ds2b-Mitglied-0004"


def pruefe_ziel():
    if (os.environ.get("DS2B_DISPOSABLE") != "ds2btest"
            or os.environ.get("APP_ENV", "").lower() in {"prod", "production"}
            or urlsplit(os.environ.get("DATABASE_URL", "")).hostname != "db"
            or urlsplit(os.environ.get("REDIS_URL", "")).hostname != "redis"):
        raise SystemExit("Seed verweigert: kein isolierter DS2b-Wegwerf-Stack.")


def main():
    pruefe_ziel()
    from sqlalchemy import select
    from diakronos_app import db
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Beitrag, BeitragKommentar, Dienstbereich, Gruppe, Gruppenmitgliedschaft,
        Mitglied, WikiArtikel,
    )
    from diakronos_app.models.psalmos import Lied

    with db.SessionLocal.begin() as s:
        if s.scalar(select(Mitglied.name)):
            raise SystemExit("Seed verweigert: Diakonos-Datenbank nicht leer.")
        for name in ("Chor", "Freizeit", "Musik", "Jugend", "Gemeindeleben"):
            if not s.get(Dienstbereich, name):
                s.add(Dienstbereich(name=name))

        vorhanden = {u.name for u in s.scalars(select(User)).all()}
        neu = []
        if MITGLIED_EMAIL not in vorhanden:
            neu.append(User(name=MITGLIED_EMAIL, email=MITGLIED_EMAIL, full_name="Mara Test",
                            enabled=True, password_hash=neuer_hash(MITGLIED_PASSWORT)))
        s.add_all(neu)
        s.flush()
        if not s.scalar(select(HasRole.name).where(HasRole.parent == MITGLIED_EMAIL,
                                                   HasRole.role == "System Manager")):
            s.add(HasRole(name="ds2b-mitglied-role", parent=MITGLIED_EMAIL, parenttype="User",
                          parentfield="roles", role="System Manager"))

        personen = [
            ("Anna Berger", "Mitglied", "anna.berger@example.org", "0170 1111111",
             "Hauptstraße", "12", "74072", "Heilbronn", "1990-03-14"),
            ("Ben Keller", "Mitglied", "ben.keller@example.org", "0170 2222222",
             "Rosenweg", "4", "74074", "Heilbronn", "1985-07-02"),
            ("Clara Winter", "Gast", "clara.winter@example.org", "0170 3333333",
             "Lindenallee", "8", "74076", "Heilbronn", "1998-11-21"),
            ("David Sommer", "Mitglied", "david.sommer@example.org", "0170 4444444",
             "Am Markt", "3", "74072", "Heilbronn", "1979-01-09"),
            ("Eva Neumann", "Kind", "", "", "Bergstraße", "15", "74078",
             "Heilbronn", "2014-05-30"),
            ("Felix Groß", "Mitglied", "felix.gross@example.org", "0170 6666666",
             "Talweg", "22", "74080", "Heilbronn", "1993-09-17"),
            ("Greta Lang", "Inaktiv", "greta.lang@example.org", "", "Schulstraße", "1",
             "74072", "Heilbronn", "1968-02-11"),
            ("Hans Peter", "Mitglied", "hans.peter@example.org", "0170 8888888",
             "Mühlenweg", "7", "74074", "Heilbronn", "1988-12-05"),
        ]
        for i, (name, status, email, tel, strasse, nummer, plz, ort, geb) in enumerate(personen):
            vorname, nachname = name.split(" ", 1)
            kennung = "ds2b-m-" + str(i + 1).zfill(4)
            s.add(Mitglied(name=kennung, vorname=vorname, nachname=nachname, status=status,
                           email=email or None, telefonnummer=tel or None,
                           straße=strasse, nummer=nummer, postleitzahl=plz, wohnort=ort,
                           geburtstag=geb,
                           user=MITGLIED_EMAIL if i == 0 else None))
        s.flush()

        s.add(Gruppe(name="Chor", gruppenname="Chor", beschreibung="Gemeinsamer Probenchor"))
        s.flush()
        for i in range(4):
            s.add(Gruppenmitgliedschaft(
                name=f"ds2b-gm-chor-{i}", parent="Chor", parenttype="Gruppe",
                parentfield="mitglieder", mitglied="ds2b-m-" + str(i + 1).zfill(4),
                status="Aktiv"))
        s.add(Gruppe(name="Technik", gruppenname="Technik", beschreibung="Ton und Licht"))
        s.flush()
        for i in range(2):
            s.add(Gruppenmitgliedschaft(
                name=f"ds2b-gm-technik-{i}", parent="Technik", parenttype="Gruppe",
                parentfield="mitglieder", mitglied="ds2b-m-" + str(6 + i).zfill(4),
                status="Aktiv"))

        for i in range(12):
            s.add(Lied(name=f"DS2b Lied {i + 1:02d}", titel=f"DS2b Lied {i + 1:02d}",
                       aktiv=True, gesangbuch_nummer=str(201 + i)))
        s.add(Lied(name="DS2b Lied ohne Nummer", titel="Lobet den Herrn", aktiv=True))

        for i in range(6):
            s.add(WikiArtikel(
                name=f"ds2b-wiki-{i + 1}", titel=f"Wiki-Artikel {i + 1}",
                kategorie=["allgemein", "musik", "technik"][i % 3],
                inhalt=f"## Abschnitt\nInhalt des Wiki-Artikels {i + 1}.",
                auszug=f"Kurzbeschreibung {i + 1}.", tags="test,abnahme",
                ist_neu=(i < 2)))

        for i in range(5):
            s.add(Beitrag(
                name=f"ds2b-beitrag-{i + 1}", titel=f"Beitrag {i + 1}",
                kategorie=["allgemein", "musik", "gemeindeleben"][i % 3],
                inhalt=f"Text des Beitrags {i + 1}.", auszug=f"Auszug {i + 1}.",
                autor=ADMIN_EMAIL, veroeffentlicht=True))
        s.flush()
        s.add(BeitragKommentar(name="ds2b-kommentar-1", parent="ds2b-beitrag-1",
                               parenttype="Beitrag", parentfield="kommentare",
                               text="Ein Kommentar zur Abnahme.", autor=MITGLIED_EMAIL))
    print(json.dumps({"ok": True, "personen": len(personen), "admin": ADMIN_EMAIL,
                      "mitglied": MITGLIED_EMAIL}, ensure_ascii=False))


if __name__ == "__main__":
    main()
