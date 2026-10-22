"""Demo-Daten „Evangelische Gemeinde Musterhausen“ fuer Diakronos.

Zweck: eine LEERE Datenbank mit einer glaubwuerdigen, vollstaendig ERFUNDENEN
Gemeinde fuellen — fuer Bilder in der README, Vorfuehrungen und zum Ausprobieren.
Alle Namen, Adressen, Telefonnummern, Mailadressen und Geburtstage sind
erfunden; die Domains sind example.org (RFC 2606). Nichts hier stammt aus einer
echten Gemeinde.

Arbeitsweise
------------
Das Skript arbeitet ausschliesslich ueber die ECHTEN Schnittstellen der App
(Modelle und Dienste aus ``diakronos_app``) — nicht per Roh-SQL. Damit legt es
dieselben Datensaetze an, die auch die Oberflaeche anlegt, und die App sieht
anschliessend genau das Erwartete.

Aufruf (IM app-Image — die Datenbank muss leer sein)::

    python tools/demo/musterhausen.py            # anlegen / nachziehen
    python tools/demo/musterhausen.py --pruefen  # nur pruefen, nichts schreiben
    python tools/demo/musterhausen.py --entfernen

Idempotent: jeder Datensatz hat eine feste Kennung; ein zweiter Lauf findet ihn
und laesst ihn unveraendert. Das Skript eignet sich damit auch zum Nachziehen
einer halb gefuellten Datenbank.

Konfiguration kommt aus der Umgebung (siehe ``settings.py``), also im Container
aus ``DATABASE_URL`` — es gibt KEINE zweiten Zugangsdaten im Skript.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

# ── Erfundene Stammdaten ────────────────────────────────────────────────────
# Eine Wahrheit fuer alle Werte: Aenderungen hier wirken ueberall.

GEMEINDE = "Evangelische Gemeinde Musterhausen"
ADMIN_EMAIL = "admin@example.org"
ADMIN_PASSWORT = "musterhausen-demo"  # noqa: S105 — Demo-Konto, oeffentlich, Testwert
# Mitglied, das das Verwaltungskonto traegt (Profilseite braucht die Zuordnung).
ADMIN_PERSON = "Miriam Sonnleitner"
#: Traeger des Mitglieder-Kontos (`MITGLIED_EMAIL`) — der Anzeigename des
#: Kontos ist die Person (siehe `konten_anlegen`).
MITGLIED_PERSON = "Anna Beispiel"
MITGLIED_EMAIL = "anna.beispiel@example.org"
MITGLIED_PASSWORT = "musterhausen-demo"  # noqa: S105 — Demo-Konto, oeffentlich, Testwert
ORT = "Musterhausen"
PLZ = "12345"
TELEFON_VORWAHL = "0123 456789"

# Referenzdatum der Demo: die Termine laufen ueber zwei Monate AB diesem Tag.
# Ohne Angabe wird der Tag des Laufs genommen (die Bilder zeigen so einen
# aktuellen Kalender); fuer reproduzierbare Bilder laesst er sich festsetzen.
STANDARD_STICHTAG = date(2026, 11, 2)

# Status sind AUSSCHLIESSLICH die vier Werte der App (``api/mitglieder.py:
# MITGLIED_STATUS``: Mitglied, Gast, Passives Mitglied, Passiver Gast) — einen
# Status „Aktiv“ gibt es nicht, ein solcher Eintrag faellt in jedem Statusfilter
# durch (Befund PUB-2b/B1). „Ausgetreten“ entsteht NICHT hier, sondern ueber den
# echten Austritts-Weg (``api/austritt.py: mitglied_austritt``, siehe
# ``MITGLIEDER_AUSGETRETEN``).
# (Vorname, Nachname, Geburtstag (M,T), Geschlecht, Familienstand,
#  Mitglied seit, Status)
MITGLIEDER: list[dict[str, Any]] = [
    {"vorname": "Anna", "nachname": "Beispiel", "geb": (5, 14), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2004, "status": "Mitglied"},
    {"vorname": "Jonas", "nachname": "Beispiel", "geb": (9, 3), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2004, "status": "Mitglied"},
    {"vorname": "Miriam", "nachname": "Beispiel", "geb": (2, 21), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2010, "status": "Mitglied", "kind_von": "Anna Beispiel"},
    {"vorname": "Elvira", "nachname": "Dorn", "geb": (11, 9), "geschlecht": "weiblich",
     "familienstand": "verwitwet", "seit": 1998, "status": "Mitglied"},
    {"vorname": "Theodor", "nachname": "Dorn", "geb": (3, 27), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 1998, "status": "Mitglied"},
    {"vorname": "Hedwig", "nachname": "Dorn", "geb": (7, 2), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2012, "status": "Mitglied"},
    {"vorname": "Samuel", "nachname": "Fink", "geb": (1, 16), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2015, "status": "Mitglied"},
    {"vorname": "Rebekka", "nachname": "Fink", "geb": (6, 8), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2015, "status": "Mitglied"},
    {"vorname": "Tobias", "nachname": "Gerlach", "geb": (4, 30), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2009, "status": "Mitglied"},
    {"vorname": "Susanne", "nachname": "Gerlach", "geb": (10, 12), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2009, "status": "Mitglied"},
    {"vorname": "Lukas", "nachname": "Gerlach", "geb": (12, 1), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2009, "status": "Mitglied",
     "kind_von": "Tobias Gerlach"},
    {"vorname": "Marta", "nachname": "Haas", "geb": (8, 25), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2018, "status": "Gast"},
    {"vorname": "Benedikt", "nachname": "Imhof", "geb": (5, 5), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2001, "status": "Mitglied"},
    {"vorname": "Clara", "nachname": "Imhof", "geb": (2, 17), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2001, "status": "Mitglied"},
    {"vorname": "Niklas", "nachname": "Jäger", "geb": (9, 19), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2019, "status": "Gast"},
    {"vorname": "Franziska", "nachname": "Kellner", "geb": (3, 11), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2016, "status": "Mitglied"},
    {"vorname": "Albrecht", "nachname": "Krause", "geb": (11, 23), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 1995, "status": "Passives Mitglied"},
    {"vorname": "Ruth", "nachname": "Krause", "geb": (12, 6), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 1995, "status": "Passives Mitglied"},
    {"vorname": "Daniel", "nachname": "Lindner", "geb": (6, 28), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2020, "status": "Mitglied"},
    {"vorname": "Esther", "nachname": "Moser", "geb": (1, 7), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2011, "status": "Mitglied"},
    {"vorname": "Philipp", "nachname": "Moser", "geb": (7, 15), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2011, "status": "Mitglied"},
    {"vorname": "Johanna", "nachname": "Neubauer", "geb": (10, 30), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2021, "status": "Mitglied"},
    {"vorname": "Konrad", "nachname": "Osterloh", "geb": (2, 3), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2006, "status": "Mitglied"},
    {"vorname": "Dorothea", "nachname": "Osterloh", "geb": (5, 20), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2006, "status": "Mitglied"},
    {"vorname": "Simon", "nachname": "Pahl", "geb": (8, 4), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2017, "status": "Mitglied"},
    {"vorname": "Nadine", "nachname": "Quandt", "geb": (3, 18), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2013, "status": "Mitglied"},
    {"vorname": "Matthias", "nachname": "Reuter", "geb": (9, 26), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2003, "status": "Mitglied"},
    {"vorname": "Judith", "nachname": "Reuter", "geb": (4, 9), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2003, "status": "Mitglied"},
    {"vorname": "Elias", "nachname": "Reuter", "geb": (11, 2), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2003, "status": "Mitglied",
     "kind_von": "Matthias Reuter"},
    {"vorname": "Gertrud", "nachname": "Sandmann", "geb": (12, 14), "geschlecht": "weiblich",
     "familienstand": "verwitwet", "seit": 1989, "status": "Passives Mitglied"},
    {"vorname": "Oskar", "nachname": "Theiss", "geb": (6, 22), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2022, "status": "Gast"},
    {"vorname": "Leonie", "nachname": "Uhl", "geb": (1, 29), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2022, "status": "Gast"},
    {"vorname": "Valentin", "nachname": "Vogel", "geb": (7, 11), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 2008, "status": "Mitglied"},
    {"vorname": "Marlene", "nachname": "Vogel", "geb": (10, 5), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 2008, "status": "Mitglied"},
    {"vorname": "Friederike", "nachname": "Wenzel", "geb": (4, 24), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2014, "status": "Passiver Gast"},
    {"vorname": "Alina", "nachname": "Winter", "geb": (5, 31), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2020, "status": "Mitglied"},
    {"vorname": "Bertram", "nachname": "Zimmer", "geb": (8, 13), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 1999, "status": "Mitglied"},
    {"vorname": "Katharina", "nachname": "Zimmer", "geb": (2, 27), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 1999, "status": "Mitglied"},
    {"vorname": "Benjamin", "nachname": "Adler", "geb": (11, 17), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2023, "status": "Passiver Gast"},
    {"vorname": "Sophie", "nachname": "Bergmann", "geb": (6, 2), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2024, "status": "Gast"},
    # Traegt das Verwaltungskonto `admin@example.org` (siehe ADMIN_PERSON): jedes
    # Konto braucht ein Mitglied, sonst zeigt „Profil“ nur einen Hinweis
    # (profile.get_my_profile antwortet ohne Zuordnung mit 417). Kein
    # `konto: True` — die Zuordnung setzt `mitglied_konten_verknuepfen`.
    #
    # PUB-2b/B2: Diese Person ist die Gemeindeleitung des Beispielbestands und
    # steht deshalb auch in Gruppen und in den Plaenen — sonst sind
    # „Übersicht“, „Dienstplan“ und „Meine Dienste“ fuer das Verwaltungskonto
    # leer (Sichtpruefung).
    {"vorname": "Miriam", "nachname": "Sonnleitner", "geb": (1, 12), "geschlecht": "weiblich",
     "familienstand": "verheiratet", "seit": 1999, "status": "Mitglied"},
    # Traegt das Mitglieder-Konto `MITGLIED_EMAIL` (siehe `konto: True` oben).
    {"vorname": "Gregor", "nachname": "Sandmann", "geb": (4, 18), "geschlecht": "männlich",
     "familienstand": "ledig", "seit": 2021, "status": "Mitglied",
     "kind_von": "Gertrud Sandmann"},
]

#: Personen, die den Austritt ueber den ECHTEN Weg gehen (`mitglied_austritt`).
#: Nicht in ``MITGLIEDER`` doppelt fuehren — der Status „Ausgetreten“ entsteht
#: erst durch den Austritt, nicht durch das Anlegen.
MITGLIEDER_AUSGETRETEN: list[dict[str, Any]] = [
    {"vorname": "Hildegard", "nachname": "Bauer", "geb": (9, 9), "geschlecht": "weiblich",
     "familienstand": "ledig", "seit": 2007, "status": "Mitglied"},
    {"vorname": "Rainer", "nachname": "Kolb", "geb": (2, 19), "geschlecht": "männlich",
     "familienstand": "verheiratet", "seit": 1997, "status": "Mitglied"},
]

# Familienbeziehungen: (Person, Person, Typ) — die Gegenrichtung legt das
# Skript selbst an (``ist_spiegel``), damit „Elternteil von“ und „Kind von“
# zusammenpassen.
BEZIEHUNGEN: list[tuple[str, str, str]] = [
    ("Anna Beispiel", "Jonas Beispiel", "Ehepartner"),
    ("Anna Beispiel", "Miriam Beispiel", "Kind"),
    ("Jonas Beispiel", "Miriam Beispiel", "Kind"),
    ("Elvira Dorn", "Theodor Dorn", "Kind"),
    ("Elvira Dorn", "Hedwig Dorn", "Kind"),
    ("Tobias Gerlach", "Susanne Gerlach", "Ehepartner"),
    ("Tobias Gerlach", "Lukas Gerlach", "Kind"),
    ("Susanne Gerlach", "Lukas Gerlach", "Kind"),
    ("Benedikt Imhof", "Clara Imhof", "Ehepartner"),
    ("Albrecht Krause", "Ruth Krause", "Ehepartner"),
    ("Esther Moser", "Philipp Moser", "Ehepartner"),
    ("Konrad Osterloh", "Dorothea Osterloh", "Ehepartner"),
    ("Matthias Reuter", "Judith Reuter", "Ehepartner"),
    ("Matthias Reuter", "Elias Reuter", "Kind"),
    ("Judith Reuter", "Elias Reuter", "Kind"),
    ("Valentin Vogel", "Marlene Vogel", "Ehepartner"),
    ("Bertram Zimmer", "Katharina Zimmer", "Ehepartner"),
]

# Dienstbereiche (Arbeitszweige der Gemeinde). Der Anzeigename steht in
# `ministry`; die Plantypen der Kochbuch-Sammlung binden an diese Namen.
DIENSTBEREICHE: list[dict[str, Any]] = [
    {"name": "gottesdienst", "anzeige": "Gottesdienst", "farbe": "#7c3aed",
     "beschreibung": "Sonntagsgottesdienste, Predigt und Moderation."},
    {"name": "musik", "anzeige": "Musik", "farbe": "#0ea5e9",
     "beschreibung": "Chor, Lobpreis und Musikteams."},
    {"name": "kinder", "anzeige": "Kinder", "farbe": "#f59e0b",
     "beschreibung": "Kindergottesdienst und Kinderdienst."},
    {"name": "jugend", "anzeige": "Jugend", "farbe": "#10b981",
     "beschreibung": "Jugendkreis und Freizeiten."},
    {"name": "technik", "anzeige": "Technik", "farbe": "#6b7280",
     "beschreibung": "Ton, Beamer und Übertragung."},
    {"name": "haus", "anzeige": "Haus", "farbe": "#ef4444",
     "beschreibung": "Gebäude, Räume und Reinigung."},
]

# Gruppentypen (Art der Gruppe, mit den Rollen, die eine Gruppe dieses Typs hat).
GRUPPENTYPEN: list[dict[str, Any]] = [
    {"name": "chor", "anzeige": "Chor", "rollen": ["Chorleitung", "Mitglied"]},
    {"name": "kreis", "anzeige": "Kreis", "rollen": ["Leitung", "Mitglied"]},
    {"name": "team", "anzeige": "Team", "rollen": ["Teamleitung", "Mitglied"]},
    {"name": "dienst", "anzeige": "Dienst", "rollen": ["Einteilung", "Mitglied"]},
]

# Gruppen: Name, Anzeigename, Dienstbereich, Gruppentyp, Leitung, Mitglieder.
GRUPPEN: list[dict[str, Any]] = [
    {
        "name": "Chor", "anzeige": "Chor", "bereich": "musik", "typ": "chor",
        "beschreibung": "Singt im Gottesdienst und probt donnerstags.",
        "treffpunkt": "Gemeindesaal", "treffzeit": "Donnerstag 19:30",
        "leitung": "Rebekka Fink",
        "mitglieder": [
            "Anna Beispiel", "Jonas Beispiel", "Miriam Beispiel", "Elvira Dorn",
            "Hedwig Dorn", "Rebekka Fink", "Clara Imhof", "Franziska Kellner",
            "Ruth Krause", "Esther Moser", "Dorothea Osterloh", "Judith Reuter",
            "Marlene Vogel", "Friederike Wenzel", "Katharina Zimmer", "Sophie Bergmann",
            "Miriam Sonnleitner", "Gregor Sandmann",
        ],
    },
    {
        "name": "jugendkreis", "anzeige": "Jugendkreis", "bereich": "jugend", "typ": "kreis",
        "beschreibung": "Treffen für Jugendliche ab 13 Jahren.",
        "treffpunkt": "Jugendraum", "treffzeit": "Freitag 19:00",
        "leitung": "Samuel Fink",
        "mitglieder": [
            "Miriam Beispiel", "Hedwig Dorn", "Samuel Fink", "Lukas Gerlach",
            "Marta Haas", "Niklas Jäger", "Daniel Lindner", "Johanna Neubauer",
            "Simon Pahl", "Nadine Quandt", "Elias Reuter", "Oskar Theiss",
            "Leonie Uhl", "Benjamin Adler", "Sophie Bergmann",
        ],
    },
    {
        "name": "technik", "anzeige": "Technikteam", "bereich": "technik", "typ": "team",
        "beschreibung": "Ton, Beamer und Übertragung der Gottesdienste.",
        "treffpunkt": "Technikraum", "treffzeit": "nach Absprache",
        "leitung": "Niklas Jäger",
        "mitglieder": [
            "Niklas Jäger", "Tobias Gerlach", "Lukas Gerlach", "Daniel Lindner",
            "Konrad Osterloh", "Valentin Vogel",
        ],
    },
    {
        "name": "kinderdienst", "anzeige": "Kinderdienst", "bereich": "kinder", "typ": "dienst",
        "beschreibung": "Kindergottesdienst während des Hauptgottesdienstes.",
        "treffpunkt": "Kindergruppenraum", "treffzeit": "Sonntag 10:00",
        "leitung": "Susanne Gerlach",
        "mitglieder": [
            "Susanne Gerlach", "Clara Imhof", "Marta Haas", "Franziska Kellner",
            "Johanna Neubauer", "Leonie Uhl", "Alina Winter",
        ],
    },
    {
        "name": "lobpreis", "anzeige": "Lobpreis", "bereich": "musik", "typ": "team",
        "beschreibung": "Band für den Gottesdienst — Gitarre, Klavier, Gesang.",
        "treffpunkt": "Gemeindesaal", "treffzeit": "Samstag 16:00",
        "leitung": "Simon Pahl",
        "mitglieder": [
            "Simon Pahl", "Marta Haas", "Daniel Lindner", "Miriam Beispiel",
            "Alina Winter", "Sophie Bergmann", "Benjamin Adler",
        ],
    },
    {
        "name": "Hauskreis", "anzeige": "Hauskreis", "bereich": "haus", "typ": "kreis",
        "beschreibung": "Hauskreis am Mittwochabend im Süden des Ortes.",
        "treffpunkt": "Lindenweg 3", "treffzeit": "Mittwoch 19:30",
        "leitung": "Philipp Moser",
        "mitglieder": [
            "Philipp Moser", "Esther Moser", "Konrad Osterloh", "Dorothea Osterloh",
            "Bertram Zimmer", "Katharina Zimmer", "Gertrud Sandmann",
            "Miriam Sonnleitner", "Gregor Sandmann",
        ],
    },
    {
        "name": "hauskreis-nord", "anzeige": "Hauskreis Nord", "bereich": "haus", "typ": "kreis",
        "beschreibung": "Hauskreis am Donnerstagabend im Norden des Ortes.",
        "treffpunkt": "Am Kirchberg 12", "treffzeit": "Donnerstag 19:30",
        "leitung": "Matthias Reuter",
        "mitglieder": [
            "Matthias Reuter", "Judith Reuter", "Elias Reuter", "Benedikt Imhof",
            "Clara Imhof", "Ruth Krause", "Valentin Vogel",
        ],
    },
]

#: Musikteams (Kochbuch `musikteams`): Teams sind UNTERgruppen einer Gruppe
#: „Musikteams“ — das Feld `team` waehlt sie über `teams.gruppe_unter`.
#: „Gruppe 3“ heisst so, weil die Kochbuch-Regel `verfuegbarkeit` dieses Team
#: namentlich auf den 1. Sonntag im Monat legt (`"team": "Gruppe 3"`); Namen und
#: Kennung sind hier dasselbe.
MUSIKTEAMS_OBERGRUPPE: str = "Musikteams"
MUSIKTEAMS: list[dict[str, Any]] = [
    {"name": "Team Montag", "anzeige": "Team Montag",
     "mitglieder": ["Anna Beispiel", "Clara Imhof", "Marta Haas", "Sophie Bergmann"]},
    {"name": "Team Dienstag", "anzeige": "Team Dienstag",
     "mitglieder": ["Miriam Beispiel", "Elvira Dorn", "Hedwig Dorn", "Alina Winter"]},
    {"name": "Gruppe 3", "anzeige": "Gruppe 3 (1. Sonntag)",
     "mitglieder": ["Miriam Sonnleitner", "Gregor Sandmann", "Benjamin Adler"]},
]

# Personelle Dienste: Merkmal -> Mitglieder (Quelle fuer den Dienstplan).
MERKMALE_PERSON: dict[str, list[str]] = {
    # Hauskreis (Kochbuch `putzplan`): das Feld „familie“ verlangt ein
    # Auswahl-Merkmal mit genau diesen fuenf Werten. Ohne diese Traeger lehnte
    # die Park-Rahmen-Pruefung jeden Eintrag ab und der Putzplan blieb leer.
    "familie": ["Anna Beispiel", "Bruno Muster", "Clara Clausen",
                "Daniel Dreis", "Elvira Ebert"],
    "prediger": ["Matthias Reuter", "Konrad Osterloh", "Benedikt Imhof"],
    "moderator": ["Anna Beispiel", "Jonas Beispiel", "Elvira Dorn", "Samuel Fink", "Judith Reuter",
                  "Miriam Sonnleitner"],
    "dirigent": ["Rebekka Fink", "Clara Imhof"],
    "klavier": ["Clara Imhof", "Franziska Kellner", "Sophie Bergmann"],
    "einsingen": ["Elvira Dorn", "Hedwig Dorn", "Miriam Sonnleitner"],
    "erfahren_beamer": ["Niklas Jäger", "Daniel Lindner", "Valentin Vogel"],
    "erfahren_ton": ["Tobias Gerlach", "Lukas Gerlach", "Konrad Osterloh"],
    "technik_helfer": ["Benjamin Adler", "Simon Pahl", "Oskar Theiss"],
    # Kindergottesdienst (Kochbuch `kindergottesdienst`): Leiter und Helfer je
    # Altersgruppe. Ohne Traeger bleiben „Leiter“/„Helfer“ leer (Befund B4).
    "leiter": ["Susanne Gerlach", "Clara Imhof", "Marta Haas", "Franziska Kellner",
               "Johanna Neubauer", "Leonie Uhl"],
    "helfer": ["Alina Winter", "Leonie Uhl", "Johanna Neubauer", "Clara Imhof",
               "Marta Haas", "Sophie Bergmann", "Benjamin Adler"],
    # Musikteams (Kochbuch `musikteams`): Sänger der Teams, die freitags proben.
    "saenger": ["Anna Beispiel", "Miriam Beispiel", "Elvira Dorn", "Hedwig Dorn",
                "Clara Imhof", "Sophie Bergmann", "Marta Haas", "Alina Winter",
                "Miriam Sonnleitner", "Gregor Sandmann"],
}

DIENSTROLLEN: list[dict[str, str]] = [
    {"name": "Predigt", "farbe": "#7c3aed"},
    {"name": "Moderation", "farbe": "#0ea5e9"},
    {"name": "Technik Ton", "farbe": "#6b7280"},
    {"name": "Technik Beamer", "farbe": "#6b7280"},
    {"name": "Kinderdienst", "farbe": "#f59e0b"},
    {"name": "Chorleitung", "farbe": "#10b981"},
]

RESSOURCEN: list[dict[str, Any]] = [
    {"name": "Gemeindesaal", "typ": "Raum", "kapazitaet": 180,
     "beschreibung": "Hauptsaal mit Bühne, Beamer und Tonanlage.",
     "tags": "Bühne, Beamer, Ton"},
    {"name": "Jugendraum", "typ": "Raum", "kapazitaet": 30,
     "beschreibung": "Raum mit Sofaecke, Tischtennisplatte und Küche.",
     "tags": "Küche, Sofaecke"},
    {"name": "Kindergruppenraum", "typ": "Raum", "kapazitaet": 25,
     "beschreibung": "Heller Raum für Kinderprogramm, mit Teppich und Regalen.",
     "tags": "Teppich, Spielsachen"},
    {"name": "Technikraum", "typ": "Raum", "kapazitaet": 6,
     "beschreibung": "Mischpult, Verstärker und Kabelbestand.",
     "tags": "Ton, Beamer"},
    {"name": "Gemeindebus", "typ": "Fahrzeug", "kapazitaet": 9,
     "beschreibung": "Kleinbus für Fahrten zu Freizeiten und Besuchen.",
     "tags": "Anhänger, 9 Sitze"},
    {"name": "Beamer mobil", "typ": "Gegenstand", "kapazitaet": None,
     "beschreibung": "Tragbarer Beamer für Veranstaltungen außerhalb des Saals.",
     "tags": "HDMI, Leinwand"},
]

KALENDER: list[dict[str, Any]] = [
    {"name": "gottesdienste", "anzeige": "Gottesdienste", "farbe": "#7c3aed",
     "beschreibung": "Alle Gottesdienste und Andachten."},
    {"name": "gruppen", "anzeige": "Gruppen & Kreise", "farbe": "#10b981",
     "beschreibung": "Proben, Treffen und Kreise."},
    {"name": "veranstaltungen", "anzeige": "Gemeindeleben", "farbe": "#f59e0b",
     "beschreibung": "Feste, Ausflüge und Besondere Termine."},
]

TERMINKATEGORIEN: list[dict[str, Any]] = [
    {"name": "gottesdienst", "anzeige": "Gottesdienst", "farbe": "#7c3aed",
     "terminart": "Gottesdienst", "hat_ablaufplan": True, "betrifft": "Gottesdienst"},
    {"name": "probe", "anzeige": "Probe", "farbe": "#0ea5e9",
     "terminart": "Probe", "betrifft": "Musik"},
    {"name": "jugend", "anzeige": "Jugendtreffen", "farbe": "#10b981",
     "terminart": "Treffen", "betrifft": "Jugend"},
    {"name": "fest", "anzeige": "Gemeindefest", "farbe": "#f59e0b",
     "terminart": "Fest", "betrifft": "Gemeinde"},
    {"name": "sitzung", "anzeige": "Sitzung", "farbe": "#6b7280",
     "terminart": "Sitzung", "betrifft": "Leitung"},
]

# Feste Termine der Demo (Tage nach dem Stichtag): Titel, Kalender, Kategorie,
# Start, Dauer in Minuten, Ort.
TERMINE_FEST: list[dict[str, Any]] = [
    {"tag": 4, "titel": "Chorprobe", "kalender": "gruppen", "kategorie": "probe",
     "start": "19:30", "dauer": 90, "ort": "Gemeindesaal"},
    {"tag": 11, "titel": "Chorprobe", "kalender": "gruppen", "kategorie": "probe",
     "start": "19:30", "dauer": 90, "ort": "Gemeindesaal"},
    {"tag": 18, "titel": "Chorprobe", "kalender": "gruppen", "kategorie": "probe",
     "start": "19:30", "dauer": 90, "ort": "Gemeindesaal"},
    {"tag": 25, "titel": "Chorprobe", "kalender": "gruppen", "kategorie": "probe",
     "start": "19:30", "dauer": 90, "ort": "Gemeindesaal"},
    {"tag": 6, "titel": "Jugendkreis", "kalender": "gruppen", "kategorie": "jugend",
     "start": "19:00", "dauer": 120, "ort": "Jugendraum"},
    {"tag": 13, "titel": "Jugendkreis", "kalender": "gruppen", "kategorie": "jugend",
     "start": "19:00", "dauer": 120, "ort": "Jugendraum"},
    {"tag": 20, "titel": "Jugendkreis", "kalender": "gruppen", "kategorie": "jugend",
     "start": "19:00", "dauer": 120, "ort": "Jugendraum"},
    {"tag": 27, "titel": "Jugendkreis", "kalender": "gruppen", "kategorie": "jugend",
     "start": "19:00", "dauer": 120, "ort": "Jugendraum"},
    {"tag": 9, "titel": "Hauskreis Süd", "kalender": "gruppen", "kategorie": "sitzung",
     "start": "19:30", "dauer": 120, "ort": "Lindenweg 3"},
    {"tag": 16, "titel": "Hauskreis Nord", "kalender": "gruppen", "kategorie": "sitzung",
     "start": "19:30", "dauer": 120, "ort": "Am Kirchberg 12"},
    {"tag": 23, "titel": "Hauskreis Süd", "kalender": "gruppen", "kategorie": "sitzung",
     "start": "19:30", "dauer": 120, "ort": "Lindenweg 3"},
    {"tag": 30, "titel": "Hauskreis Nord", "kalender": "gruppen", "kategorie": "sitzung",
     "start": "19:30", "dauer": 120, "ort": "Am Kirchberg 12"},
    {"tag": 7, "titel": "Lobpreisprobe", "kalender": "gruppen", "kategorie": "probe",
     "start": "16:00", "dauer": 120, "ort": "Gemeindesaal"},
    {"tag": 21, "titel": "Lobpreisprobe", "kalender": "gruppen", "kategorie": "probe",
     "start": "16:00", "dauer": 120, "ort": "Gemeindesaal"},
    {"tag": 35, "titel": "Gemeindefest", "kalender": "veranstaltungen", "kategorie": "fest",
     "start": "14:00", "dauer": 300, "ort": "Gemeindesaal"},
    {"tag": 42, "titel": "Gemeindeversammlung", "kalender": "veranstaltungen",
     "kategorie": "sitzung", "start": "19:00", "dauer": 120, "ort": "Gemeindesaal"},
    {"tag": 49, "titel": "Adventsbasteln", "kalender": "veranstaltungen",
     "kategorie": "fest", "start": "15:00", "dauer": 180, "ort": "Jugendraum"},
]

# Rechte-Status sind AUSSCHLIESSLICH die vier Werte der App
# (``frontend/src/diakonos/pages/Lieder.vue: RECHTS_STATUS`` und
# ``api/psalmos/musik.py``: Ungeklärt, Gemeinfrei, Lizenz vorhanden,
# Lizenz nötig). Jedes Lied traegt seinen eigenen Wert im Feld
# ``rechte_status`` — „Gemeinfrei“ nur, wo Text UND Melodie nachweislich
# gemeinfrei sind (Urheber seit ueber 70 Jahren tot, alte Choraele). Neuere
# Lieder bekommen NICHT pauschal „Gemeinfrei“, sondern den Status, den eine
# Gemeinde dafuer fuehrt; ohne belastbare Angabe steht „Ungeklärt“ (Befund
# PUB-4g / Opus B2: vorher standen alle Lieder auf „Gemeinfrei“).
LIEDER: list[dict[str, Any]] = [
    {"titel": "Der Morgen strahlt in hellem Licht", "nummer": "001", "kategorien": ["Eröffnung"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Groß ist deine Treue", "nummer": "012", "kategorien": ["Vertrauen"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Kommt und lasst uns singen", "nummer": "023", "kategorien": ["Eröffnung"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Du bist der Weg und die Wahrheit", "nummer": "045", "kategorien": ["Nachfolge"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Herr, erbarme dich", "nummer": "052", "kategorien": ["Kyrie"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Nun danket alle Gott", "nummer": "068", "kategorien": ["Dank"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Gemeinfrei"},
    {"titel": "Lobe den Herrn, meine Seele", "nummer": "081", "kategorien": ["Lob"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Am Abend dieser Erde", "nummer": "094", "kategorien": ["Abendmahl"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz nötig"},
    {"titel": "Friede sei mit euch", "nummer": "103", "kategorien": ["Segen"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Wo Menschen sich vergessen", "nummer": "117", "kategorien": ["Friede"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Komm, o komm, du Geist des Lebens", "nummer": "129", "kategorien": ["Pfingsten"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Gemeinfrei"},
    {"titel": "Auf, auf, mein Herz, mit Freuden", "nummer": "134", "kategorien": ["Ostern"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Macht hoch die Tür", "nummer": "145", "kategorien": ["Advent"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Stern über Bethlehem", "nummer": "158", "kategorien": ["Weihnachten"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Ich will dich lieben, meine Stärke", "nummer": "162", "kategorien": ["Vertrauen"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Meine Hoffnung und meine Freude", "nummer": "176", "kategorien": ["Hoffnung"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Ins Wasser fällt ein Stein", "nummer": "183", "kategorien": ["Friede"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Gott hat mir längst einen Engel gesandt", "nummer": "191", "kategorien": ["Vertrauen"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Taufe — du bist gesegnet", "nummer": "202", "kategorien": ["Taufe"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Singet dem Herrn ein neues Lied", "nummer": "214", "kategorien": ["Lob"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Gemeinfrei"},
    {"titel": "In dir ist Freude", "nummer": "225", "kategorien": ["Freude"],
     "anlaesse": ["Gottesdienst"], "aktiv": True, "rechte_status": "Ungeklärt"},
    {"titel": "Wir strecken uns nach dir", "nummer": "238", "kategorien": ["Nachfolge"],
     "anlaesse": ["Jugend"], "aktiv": True, "rechte_status": "Lizenz nötig"},
    {"titel": "Danke für diesen guten Morgen", "nummer": "246", "kategorien": ["Dank"],
     "anlaesse": ["Kindergottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
    {"titel": "Gottes Liebe ist so wunderbar", "nummer": "257", "kategorien": ["Kinder"],
     "anlaesse": ["Kindergottesdienst"], "aktiv": True, "rechte_status": "Lizenz vorhanden"},
]

#: Die vier Werte, die die App kennt (``Lieder.vue: RECHTS_STATUS``). Der Seed
#: schreibt nichts anderes in ``Lied.rechte_status``.
RECHTS_STATUS = ("Ungeklärt", "Gemeinfrei", "Lizenz vorhanden", "Lizenz nötig")

# Predigtreihe (fuellt die Plansammlung `predigtreihe` des Ablaufplans).
PREDIGTREIHE: list[str] = [
    "Unterwegs mit dem Volk Israel — Aufbruch",
    "Unterwegs mit dem Volk Israel — Wüste",
    "Unterwegs mit dem Volk Israel — Manna",
    "Unterwegs mit dem Volk Israel — Wasser aus dem Felsen",
    "Unterwegs mit dem Volk Israel — Kundschafter",
    "Unterwegs mit dem Volk Israel — Grenzen",
    "Unterwegs mit dem Volk Israel — Verheißung",
    "Unterwegs mit dem Volk Israel — Dank",
    "Unterwegs mit dem Volk Israel — Abschied",
]

#: Bausteine der Sammlung „programme“ (Kindergottesdienst): je Altersgruppe ein
#: Programmpunkt, den die Engine „der Reihe nach“ vergibt.
PROGRAMME: list[dict[str, str]] = [
    {"titel": "Bilderbibel: Der gute Hirte", "altersgruppe": "0-3"},
    {"titel": "Lieder zum Mitsingen und Bewegen", "altersgruppe": "0-3"},
    {"titel": "Basteln: Regenbogen aus Papier", "altersgruppe": "3-6"},
    {"titel": "Geschichte: Noah und die Arche", "altersgruppe": "3-6"},
    {"titel": "Rollenspiel: Der barmherzige Samariter", "altersgruppe": "6-10"},
    {"titel": "Bibelentdecker: Psalm 23", "altersgruppe": "6-10"},
    {"titel": "Gemeinsames Frühstück in der Gruppe", "altersgruppe": "0-3"},
    {"titel": "Theaterstück: Zachäus auf dem Baum", "altersgruppe": "3-6"},
]

#: Gruppen, an die ein Plan-Rahmen-Plan gebunden ist und die die Kochbuch-
#: Vorlagen beim Namen nennen (``rolle: {gruppe: …}``, ``teams: {gruppe_unter: …}``).
#: Die Kennung muss deshalb genauso heissen wie im Kochbuch — sonst findet die
#: Engine keine Kandidaten und der Plan bleibt leer.
GRUPPE_HAUSKREIS: str = "Hauskreis"

#: Plan-Parameter je Plantyp (Kochbuch: ``termine.manuell`` liest sie).
PLAN_PARAMETER: dict[str, dict[str, str]] = {
    # Der Programmablauf ist eine EINZELNE Veranstaltung; Datum und Uhrzeit
    # stehen als Parameter, nicht als Wiederholungsregel.
    "programm": {"datum": "2026-12-06", "uhrzeit": "17:00"},
}

# Kochbuch-Plantypen, die die Demo einrichtet (in dieser Reihenfolge).
PLANTYPEN: list[str] = [
    "gottesdienstablauf",
    "chorplan",
    "technik",
    "predigerplan",
    "musikteams",
    "kindergottesdienst",
    "putzplan",
    "programm",
]

#: Plaene, die VEROEFFENTLICHT im Beispielbestand stehen (Befund PUB-2b/B4).
#: Die uebrigen bleiben Entwurf. „Chorplan“ und „Gottesdienste“ sind die beiden,
#: die in der README als besetzte Plaene gezeigt werden.
VEROEFFENTLICHTE_PLAENE: list[str] = ["chorplan", "gottesdienstablauf"]

PLAN_TITEL: dict[str, str] = {
    "gottesdienstablauf": "Gottesdienste {monat}",
    "chorplan": "Chorplan {monat}",
    "technik": "Technikplan {monat}",
    "predigerplan": "Predigerplan {monat}",
    "musikteams": "Musikteams {monat}",
    "kindergottesdienst": "Kindergottesdienst {monat}",
    "putzplan": "Putzplan {monat}",
    "programm": "Programmablauf {monat}",
}

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────


def stichtag_aus_umgebung() -> date:
    """Referenztag des Beispielzeitraums (``DIKRONOS_DEMO_STICHTAG`` optional)."""
    roh = (os.environ.get("DIAKRONOS_DEMO_STICHTAG") or "").strip()
    if not roh:
        return STANDARD_STICHTAG
    return datetime.strptime(roh, "%Y-%m-%d").date()


def person(vorname: str, nachname: str) -> str:
    """Kennung (``name``) eines Mitglieds — dieselbe Regel wie in der App."""
    return f"{vorname} {nachname}".strip()


def email_von(vorname: str, nachname: str) -> str:
    """Erfundene Mailadresse ``vorname.nachname@example.org`` (klein, ohne Umlaute)."""
    def _glatt(text: str) -> str:
        return (
            text.lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            .replace("é", "e").replace("è", "e").replace(" ", ".")
        )

    return f"{_glatt(vorname)}.{_glatt(nachname)}@example.org"


def strasse_fuer(index: int) -> tuple[str, str]:
    """Erfundene Strasse + Hausnummer aus einer festen Liste."""
    strassen = [
        "Lindenweg", "Am Kirchberg", "Gartenstraße", "Mühlenweg", "Bahnhofstraße",
        "Birkenallee", "Schulstraße", "Feldweg", "Ringstraße", "Blumenweg",
    ]
    return strassen[index % len(strassen)], str(1 + (index * 3) % 27)


def telefon_fuer(index: int) -> str:
    return f"{TELEFON_VORWAHL}-{index + 1}"


def monatsname(datum: date) -> str:
    return MONATE[datum.month - 1]


def zeitraum_text(stichtag: date) -> tuple[str, str]:
    """Monatsnamen fuer die Plantitel (``November`` / ``November–Dezember``)."""
    ende = stichtag + timedelta(days=62)
    von, bis = monatsname(stichtag), monatsname(ende)
    return von, bis


# ── Beitraege und Wiki (Befund PUB-2b/B5) ───────────────────────────────────
# Inhalt der Beispieltexte. Alle Namen sind erfunden, alle Links zeigen auf
# example.org (RFC 2606) — die Texte sind fuer eine Vorfuehrung gedacht.

BEITRAEGE: list[dict[str, str]] = [
    {
        "titel": "Gemeindefest am 1. Advent",
        "kategorie": "Gemeindeleben",
        "auszug": "Gottesdienst, Mittagessen und Adventsbasteln für die ganze Gemeinde.",
        "inhalt": (
            "Am 1. Advent feiern wir um 10:00 Uhr einen Familiengottesdienst im "
            "Gemeindesaal. Der Chor singt, die Kinderdienst-Gruppe gestaltet den "
            "Teil für die Kleinen.\n\n"
            "Anschließend gibt es ein gemeinsames Mittagessen (Suppe und Brot) und "
            "am Nachmittag ein Adventsbasteln für Kinder ab vier Jahren. Wer einen "
            "Beitrag zum Büfett beisteuern möchte, meldet sich bitte bei Miriam "
            "Sonnleitner (Gemeindeleitung).\n\n"
            "Für die Vorbereitung treffen wir uns am Samstag ab 9:00 Uhr im "
            "Gemeindesaal. Helferinnen und Helfer sind willkommen — eine kurze "
            "Nachricht an das Technikteam genügt."
        ),
    },
    {
        "titel": "Neue Hauskreis-Saison startet",
        "kategorie": "Kreise",
        "auszug": "Hauskreis Nord und Hauskreis Süd beginnen mit dem Thema „Hoffnung“.",
        "inhalt": (
            "Ab dieser Woche treffen sich beide Hauskreise wieder regelmäßig. "
            "Hauskreis Süd tagt mittwochs um 19:30 Uhr, Hauskreis Nord donnerstags "
            "um 19:30 Uhr.\n\n"
            "Die neue Reihe steht unter dem Thema „Hoffnung“: sechs Abende mit "
            "Bibeltexten, Gespräch und Gebet. Wer neu dazukommen möchte, ist ohne "
            "Anmeldung willkommen — die Adressen stehen im Gemeinde-Kalender.\n\n"
            "Für die Kinderbetreuung während der Treffen suchen wir noch zwei "
            "Freiwillige; bitte bei der Gruppenleitung melden."
        ),
    },
    {
        "titel": "Chorprobe: neues Programm für die Adventszeit",
        "kategorie": "Musik",
        "auszug": "Der Chor studiert vier neue Lieder ein — neue Stimmen sind willkommen.",
        "inhalt": (
            "Der Chor probt donnerstags um 19:30 Uhr im Gemeindesaal und studiert "
            "für die Adventssonntage vier neue Lieder ein. Die Probenpläne stehen "
            "im Chorplan; dort ist auch vermerkt, wer dirigiert und wer am Klavier "
            "sitzt.\n\n"
            "Wir freuen uns über neue Stimmen in allen Lagen — Vorkenntnisse sind "
            "nicht nötig, Freude am Singen genügt. Eine Schnupperprobe ist jederzeit "
            "möglich.\n\n"
            "Die Liedtexte und die Tonaufnahmen zum Üben liegen im internen Wiki "
            "(Bereich Musik)."
        ),
    },
]

WIKI_ARTIKEL: list[dict[str, str]] = [
    {
        "titel": "Ablauf eines Gottesdienstes",
        "kategorie": "Gottesdienst",
        "tags": "Ablauf, Gottesdienst, Dienstplan",
        "auszug": "Die feste Reihenfolge der Elemente und wer für was zuständig ist.",
        "inhalt": (
            "Ein Gottesdienst bei uns folgt einem festen Ablauf: Begrüßung, "
            "Eingangslied, Predigt, Fürbitten, Schlusslied und Segen.\n\n"
            "Die Moderation übernimmt eine Person aus dem Moderationsteam, die "
            "Predigt eine Person aus dem Predigerteam. Der Ablauf wird im "
            "Ablaufplan des jeweiligen Sonntags festgehalten; dort lassen sich "
            "Elemente ergänzen, verschieben und mit Liedern hinterlegen.\n\n"
            "Wichtig für die Technik: Beamer und Ton werden 30 Minuten vor Beginn "
            "eingerichtet. Wer die Rolle „Technik Ton“ oder „Technik Beamer“ "
            "übernimmt, findet die Einweisung im Wiki-Artikel „Technik im "
            "Gemeindesaal“."
        ),
    },
    {
        "titel": "Technik im Gemeindesaal",
        "kategorie": "Technik",
        "tags": "Ton, Beamer, Übertragung",
        "auszug": "Einschalten, Mikrofone, Beamer und was bei Störungen zu tun ist.",
        "inhalt": (
            "Der Technikraum liegt hinter der Bühne. Die Anlage wird über den "
            "Hauptschalter an der linken Wand eingeschaltet; die Reihenfolge "
            "(erst Mischpult, dann Verstärker) steht als Karte am Pult.\n\n"
            "Für die Mikrofone gilt: zwei Handsender liegen im Ladegerät, die "
            "Kabelmikrofone hängen am Ständer links. Der Beamer startet mit der "
            "Fernbedienung in der Schublade; die richtige Quelle heißt „HDMI 2“.\n\n"
            "Bei Störungen zuerst prüfen, ob das Mischpult Strom hat. Wenn das nicht "
            "hilft, die Anlage einmal aus- und wieder einschalten und das Problem "
            "im Dienstplan beim Termin vermerken — so sieht es der nächste Dienst."
        ),
    },
    {
        "titel": "Kinderdienst: Checkliste für Sonntage",
        "kategorie": "Kinder",
        "tags": "Kinderdienst, Checkliste",
        "auszug": "Was vor, während und nach dem Kindergottesdienst zu tun ist.",
        "inhalt": (
            "Vor dem Gottesdienst: Raum lüften, Stühle stellen, Material für die "
            "Geschichte bereitlegen, Teilnehmerliste drucken.\n\n"
            "Während des Gottesdienstes: Begrüßungsrunde, Geschichte mit Bildern, "
            "Kreativteil, gemeinsames Gebet. Zwei Erwachsene sind immer im Raum — "
            "das ist unsere Regel, damit niemand allein mit den Kindern ist.\n\n"
            "Nach dem Gottesdienst: Raum aufräumen, Material zurück in den Schrank, "
            "Teilnehmerliste in die Ablage, Auffälligkeiten an die Kinderdienst-"
            "Leitung melden."
        ),
    },
]

#: Startseiten-Kacheln (Tabelle ``dashboard_widget``). Ohne diese Zeilen ist die
#: Uebersicht LEER — die SPA zeigt nur Kacheln, fuer die es eine Zeile gibt
#: (Befund PUB-2b/B3). ``api_method`` ist derselbe Endpunkt, den die jeweilige
#: Kachel aufruft; ``None`` heisst: die Kachel rechnet selbst.
WIDGETS: list[dict[str, Any]] = [
    {"widget_id": "greeting", "label": "Begrüßung", "category": "personal",
     "widget_type": "info_card", "grid_size": "full", "default_position": 1,
     "default_visible": 1, "refresh_interval": 0, "api_method": None},
    {"widget_id": "upcoming-events", "label": "Anstehende Termine", "category": "calendar",
     "widget_type": "list_card", "grid_size": "medium", "default_position": 2,
     "default_visible": 1, "refresh_interval": 60, "api_method": "get_upcoming_events",
     "required_permission": "Kronos Element,read",
     "empty_state_mode": "show_message", "empty_state_message": "Keine anstehenden Termine."},
    {"widget_id": "my-services", "label": "Meine Dienste", "category": "personal",
     "widget_type": "list_card", "grid_size": "medium", "default_position": 3,
     "default_visible": 1, "refresh_interval": 60, "api_method": None,
     "empty_state_mode": "show_message", "empty_state_message": "Keine Dienste eingetragen."},
    {"widget_id": "mini-calendar", "label": "Kalender", "category": "calendar",
     "widget_type": "calendar_card", "grid_size": "medium", "default_position": 4,
     "default_visible": 1, "refresh_interval": 300, "api_method": "get_events_for_month"},
    {"widget_id": "announcements", "label": "Beiträge", "category": "content",
     "widget_type": "list_card", "grid_size": "medium", "default_position": 5,
     "default_visible": 1, "refresh_interval": 300, "api_method": "get_pinned_beitraege",
     "empty_state_mode": "show_message", "empty_state_message": "Keine Beiträge vorhanden."},
    {"widget_id": "wiki-recent", "label": "Neue Wiki-Einträge", "category": "content",
     "widget_type": "list_card", "grid_size": "medium", "default_position": 6,
     "default_visible": 1, "refresh_interval": 300, "api_method": "get_recent_articles",
     "required_permission": "Wiki Artikel,read",
     "empty_state_mode": "show_message", "empty_state_message": "Keine Wiki-Einträge."},
    {"widget_id": "my-bookings", "label": "Meine Buchungen", "category": "resources",
     "widget_type": "list_card", "grid_size": "medium", "default_position": 7,
     "default_visible": 1, "refresh_interval": 300,
     "api_method": "get_meine_buchungen_widget",
     "empty_state_mode": "show_message", "empty_state_message": "Keine Buchungen."},
    {"widget_id": "quick-links", "label": "Schnellzugriff", "category": "navigation",
     "widget_type": "links_card", "grid_size": "medium", "default_position": 8,
     "default_visible": 1, "refresh_interval": 0, "api_method": None},
    # Die drei Verwaltungs-Kacheln holen ihre Daten NICHT ueber
    # `get_widget_data` (es gibt fuer sie keinen Endpunkt in
    # `api/dashboard.py`) — sie bleiben sichtbar, aber ohne `api_method`.
    {"widget_id": "member-stats", "label": "Mitgliederstatistik", "category": "admin",
     "widget_type": "stats_card", "grid_size": "medium", "default_position": 9,
     "default_visible": 1, "refresh_interval": 600, "api_method": None,
     "required_role": "Mitgliederadministrator"},
    {"widget_id": "manage-registrations", "label": "Anmeldeanfragen", "category": "action",
     "widget_type": "action_card", "grid_size": "medium", "default_position": 10,
     "default_visible": 1, "refresh_interval": 60, "api_method": None,
     "required_role": "Mitgliederadministrator",
     "empty_state_mode": "show_message", "empty_state_message": "Keine offenen Anfragen."},
    {"widget_id": "open-signups", "label": "Offene Registrierungslinks", "category": "action",
     "widget_type": "action_card", "grid_size": "medium", "default_position": 11,
     "default_visible": 0, "refresh_interval": 300, "api_method": None,
     "required_role": "Mitgliederadministrator"},
    {"widget_id": "pending-registrations", "label": "Zu moderierende Termine", "category": "action",
     "widget_type": "action_card", "grid_size": "medium", "default_position": 12,
     "default_visible": 1, "refresh_interval": 30, "api_method": "get_moderation_vorschlaege",
     "required_role": "Kalenderadministrator",
     "empty_state_mode": "show_message", "empty_state_message": "Keine offenen Termine zur Moderation."},
    {"widget_id": "dsgvo-compliance", "label": "Datenschutz-Aufgaben", "category": "admin",
     "widget_type": "stats_card", "grid_size": "medium", "default_position": 13,
     "default_visible": 0, "refresh_interval": 900, "api_method": None,
     "required_role": "System Manager"},
]


def _log(text: str) -> None:
    print(f"[musterhausen] {text}", flush=True)


def _warnung(text: str) -> None:
    print(f"[musterhausen] WARNUNG {text}", file=sys.stderr, flush=True)


__all__ = [
    "ADMIN_EMAIL", "ADMIN_PASSWORT", "ADMIN_PERSON", "BEZIEHUNGEN", "DIENSTBEREICHE", "DIENSTROLLEN",
    "BEITRAEGE", "GEMEINDE", "GRUPPEN", "GRUPPENTYPEN", "KALENDER", "LIEDER", "MERKMALE_PERSON",
    "MITGLIEDER", "MITGLIEDER_AUSGETRETEN", "MITGLIED_EMAIL", "MITGLIED_PASSWORT",
    "MITGLIED_PERSON", "MONATE", "ORT", "PLAN_TITEL",
    "PLANTYPEN", "PLAN_PARAMETER", "PLZ", "PREDIGTREIHE", "PROGRAMME", "RESSOURCEN",
    "STANDARD_STICHTAG", "VEROEFFENTLICHTE_PLAENE", "WIDGETS", "WIKI_ARTIKEL",
    "GRUPPE_HAUSKREIS", "MUSIKTEAMS", "MUSIKTEAMS_OBERGRUPPE",
    "TERMINKATEGORIEN", "TERMINE_FEST", "WOCHENTAGE", "email_von", "monatsname",
    "person", "strasse_fuer", "stichtag_aus_umgebung", "telefon_fuer", "zeitraum_text",
]
