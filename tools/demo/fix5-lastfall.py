"""FIX-5 (Operator-Auflage 2) — Gruppen-Detail/Liste unter Last nachstellen.

Der erste Abnahmelauf zeigte vorher/nachher byte-gleiche Bilder: mit den
Musterhausen-Daten trat weder der seitliche Überlauf (DEV-1) noch eine
Avatar-Überlappung auf. Diese Datei legt im Wegwerf-Stack gezielt die Fälle
an, die den Befund auslösen können:

  * Gruppe mit langem, unumbrüchlichem Namen und sechs Verantwortlichen
    (darunter ein sehr langer Name) → die Zeile „Verantwortliche“ in der
    Detailkarte wird sehr breit.
  * Erste Verantwortliche: Person „Daniela Sommer“ mit Initialen „DS“ und
    OHNE Foto (`mitglied.foto = NULL`) → der Avatar im Seitenkopf zeigt Text
    statt Bild (Befund „Avatar DS überlappt“).
  * Beschreibung mit langer URL-artiger Zeichenkette ohne Leerzeichen.
  * Eine zweite Gruppe mit ebenso langem Namen, damit auch die
    Gruppenliste (DEV-1) eine lange Kachel hat.

Die Verantwortlichen hängen laut API an ``gruppe_verantwortlicher.user``
(Accountname). Die angelegten Personen bekommen deshalb ein Konto.

Anlegen IM app-Container des eigenen Wegwerf-Stacks (dort läuft die eigene
Datenbank, NIE die Betriebs-DB)::

    docker compose -p fix5t905 --env-file <env> exec -T app \\
        python /app/tools/demo/fix5-lastfall.py

Entfernen (vor `down -v` nicht nötig, aber möglich)::

    docker compose -p fix5t905 --env-file <env> exec -T app \\
        python /app/tools/demo/fix5-lastfall.py --entfernen
"""
from __future__ import annotations

import sys
from datetime import date, datetime

GRUPPE = "fix5-lastfall-gemeinschaftsteam"
GRUPPENNAME = "Jugendgemeinschaft-Musterhausen-Nord-Ost-Kirchengemeinde"
GRUPPE2 = "fix5-lastfall-krabbelgruppe"
GRUPPENNAME2 = "Krabbelgruppe-Musterhausen-Sued-West-Familienzentrum"

BESCHREIBUNG = (
    "Offener Treff für Jugendliche ab 12 Jahren. Anmeldung und Programm: "
    "https://musterhausen-beispiel.example.org/jugendgemeinschaft/"
    "veranstaltungen/uebersicht-der-wochenendtreffen-2026"
)

#: (Vorname, Nachname, E-Mail) — erste Person: „DS“ ohne Foto.
PERSONEN = [
    ("Daniela", "Sommer", "fix5.daniela.sommer@example.org"),
    ("Bartholomäus", "Wiesenbrück-Kirchhoff", "fix5.bartholomaeus@example.org"),
    ("Jonas", "Musterhausen", "fix5.jonas@example.org"),
    ("Miriam", "Beispiel", "fix5.miriam@example.org"),
    ("Thomas", "Mustermann", "fix5.thomas@example.org"),
    ("Anna", "Beispiel", "fix5.anna@example.org"),
]


def _mitglieder(s) -> list:
    """Die Personen aus PERSONEN — vorhandene wiederverwenden.

    ``gruppe_verantwortlicher.user`` ist ein FK auf ``user.name``; die
    Verantwortlichen-Zeile braucht deshalb ein KONTO. Jede Person bekommt
    eines (Name = E-Mail), ``mitglied.user`` zeigt darauf.
    """
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    jetzt = datetime(2026, 11, 2, 9, 0, 0)
    ergebnis = []
    for vorname, nachname, email in PERSONEN:
        if s.get(User, email) is None:
            s.add(User(
                name=email, email=email,
                full_name=f"{vorname} {nachname}",
                enabled=True, user_type="System User", user_image=None,
                password_hash=None,
            ))
            s.flush()
        m = (
            s.query(Mitglied)
            .filter(Mitglied.vorname == vorname, Mitglied.nachname == nachname)
            .first()
        )
        if m is None:
            kennung = f"{vorname}-{nachname}-fix5".lower().replace("ä", "ae").replace("ü", "ue")
            m = Mitglied(
                name=kennung,
                vorname=vorname, nachname=nachname, email=email,
                foto=None,  # Absicht: Initialen statt Bild
                geburtstag=date(1994, 5, 12),
                status="Aktiv", user=email,
                docstatus=0, idx=0, creation=jetzt, modified=jetzt,
                owner="Administrator", modified_by="Administrator",
            )
            s.add(m)
            s.flush()
        else:
            # Vorhandene Seed-Person (z. B. „Miriam Beispiel“): Sie hat eine
            # EIGENE Adresse und oft kein Konto. Für die Verantwortlichen-Zeile
            # braucht sie eines — sonst verletzt der FK auf `user.name`.
            if m.user and m.user != email:
                # Konto der Person gibt es schon (aus dem Seed) — das benutzen.
                email = m.user
                if s.get(User, email) is None:
                    s.add(User(name=email, email=email,
                               full_name=f"{vorname} {nachname}",
                               enabled=True, user_type="System User",
                               user_image=None, password_hash=None))
                    s.flush()
            else:
                m.user = email
                s.flush()
        ergebnis.append(m)
    return ergebnis


def _gruppe_anlegen(s, name: str, anzeige: str, personen: list, jetzt) -> None:
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        GruppeVerantwortlicher,
    )

    if s.get(Gruppe, name) is not None:
        print(f"vorhanden: {name}")
        return
    s.add(Gruppe(
        name=name, gruppenname=anzeige,
        dienstbereich=None, gruppentyp=None, status="Aktiv",
        sichtbarkeit="Alle Mitglieder",
        beschreibung=BESCHREIBUNG,
        treffpunkt="Gemeindehaus Musterhausen, Saal 2 (barrierefrei)",
        treffzeit="Freitags 18:30–20:30 Uhr",
        ancestor_path=f"/{anzeige}/",
        docstatus=0, idx=0, creation=jetzt, modified=jetzt,
        owner="Administrator", modified_by="Administrator",
    ))
    s.flush()
    for idx, m in enumerate(personen, start=1):
        # Verantwortliche hängen an `user` (Accountname). Ohne Konto bleibt
        # die Zeile in der Detailkarte leer — für die Messung unbrauchbar.
        s.add(GruppeVerantwortlicher(
            name=f"{name}-verantwortlich-{idx}",
            parent=name, parenttype="Gruppe", parentfield="verantwortliche",
            user=m.user,
            docstatus=0, idx=idx, creation=jetzt, modified=jetzt,
            owner="Administrator", modified_by="Administrator",
        ))
        s.add(Gruppenmitgliedschaft(
            name=f"{name}-mitglied-{idx}",
            parent=name, parenttype="Gruppe", parentfield="mitglieder",
            mitglied=m.name, rolle=("Leitung" if idx == 1 else "Mitglied"),
            status="Aktiv", beitrittsdatum=date(2021, 1, 1),
            docstatus=0, idx=idx, creation=jetzt, modified=jetzt,
            owner="Administrator", modified_by="Administrator",
        ))
    print(f"angelegt: {name} ({anzeige!r}) mit {len(personen)} Verantwortlichen")


def anlegen() -> int:
    from diakronos_app.db import SessionLocal

    jetzt = datetime(2026, 11, 2, 9, 0, 0)
    with SessionLocal() as s:
        personen = _mitglieder(s)
        print("erste Person:", personen[0].vorname, personen[0].nachname,
              "foto =", repr(personen[0].foto))
        _gruppe_anlegen(s, GRUPPE, GRUPPENNAME, personen, jetzt)
        _gruppe_anlegen(s, GRUPPE2, GRUPPENNAME2, personen[:3], jetzt)
        s.commit()
    return 0


def entfernen() -> int:
    from sqlalchemy import text

    from diakronos_app.db import SessionLocal

    with SessionLocal() as s:
        for gruppe in (GRUPPE, GRUPPE2):
            for tabelle in ("gruppe_verantwortlicher", "gruppenmitgliedschaft"):
                s.execute(
                    text(f"DELETE FROM {tabelle} WHERE parent = :p"), {"p": gruppe}
                )
            s.execute(text("DELETE FROM gruppe WHERE name = :p"), {"p": gruppe})
        s.commit()
    print("entfernt:", GRUPPE, GRUPPE2)
    return 0


if __name__ == "__main__":
    sys.exit(entfernen() if "--entfernen" in sys.argv else anlegen())
