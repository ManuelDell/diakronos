"""PLAN-W1-Nachweis: reines Betrachter-Konto an die Demo anbinden.

Die Demo bringt nur zwei Konten mit — admin@example.org (Administrator) und
anna.beispiel@example.org. Anna leitet in Musterhausen eine Gruppe und ist
damit SELBST Planerin: sie sieht die Pruef-Warnungen zu Recht
(darf_bearbeiten=True). Fuer den Nachweis „Betrachter sieht keine Warnungen“
braucht es ein Konto OHNE jede Verantwortung.

Dieses Skript legt es ueber die regulaeren Modelle/Wege an (Konto, Rolle
„Mitglied“, Bindung an ein BESTEHENDES Mitglied ohne Leitungsfunktion) und
ist idempotent. Es schreibt nur in die Wegwerf-Datenbank des Stacks.

    docker compose -p plan-w1 ... exec -T app python /app/tools/demo/plan-w1-betrachter.py
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import select

from diakronos_app.db import SessionLocal
from diakronos_app.frappe_compat import api_helpers
from diakronos_app.frappe_compat.session import set_user, testnaht
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    DienstbereichVerantwortlicher, GruppeVerantwortlicher, Mitglied,
)

# SEC-DEF2: KEIN eingebauter Standard-Zugang. Der oeffentliche
# Musterhausen-Demo-Standard (tools/demo/TESTKONTEN.md) ist hier der Wert des
# ANGELEGTEN Kontos — ein Skript soll das aber nicht stillschweigend benutzen.
# SEC-DEF2: KEIN eingebauter Standard-Zugang. Fehlt die Variable (oder ist sie
# leer), bricht das Skript mit erklaerender Meldung und Exit-Code 2 ab. Der
# oeffentliche Musterhausen-Demo-Standard steht in ``tools/demo/TESTKONTEN.md``,
# wird aber nicht stillschweigend eingesetzt: ein Skript, das versehentlich auf
# einer ECHTEN Instanz laeuft, soll nicht mit bekannten Zugangsdaten weiterlaufen.
# Absichtlich INLINE (kein Import aus ``tools/demo/zugang.py``): viele dieser
# Skripte laufen als EINZELNE Datei in einen Container eingehaengt, andere
# liegen ausserhalb von ``tools/demo`` — ein Nachbarmodul waere dort nicht da.
def wert_oder_abbruch(name: str, hinweis: str = "") -> str:
    wert = os.environ.get(name, "")
    if str(wert).strip():
        return wert
    zusatz = f" {hinweis.strip()}" if hinweis.strip() else ""
    print(
        f"[abbruch] Umgebungsvariable {name} ist nicht gesetzt.{zusatz} "
        "Die Demo-Skripte haben absichtlich KEINEN eingebauten Standard-Zugang "
        "(SEC-DEF2): der oeffentliche Musterhausen-Demo-Standard steht in "
        "tools/demo/TESTKONTEN.md, muss aber ausdruecklich uebergeben werden.",
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(2)


EMAIL = wert_oder_abbruch("BETRACHTER_EMAIL")
PASSWORT = wert_oder_abbruch("BETRACHTER_PASS")
NAME = "Betrachter Test"
#: Kandidaten in der Demo (Mitglieder ohne Leitung). Genommen wird das erste
#: Mitglied, das in KEINER Verantwortungs-Tabelle steht.
VORNAME, NACHNAME = "Betrachter", "Test"


def freies_mitglied(s) -> Mitglied | None:
    verantwortlich = set()
    verantwortlich |= set(s.scalars(select(DienstbereichVerantwortlicher.user)).all())
    verantwortlich |= set(s.scalars(select(GruppeVerantwortlicher.user)).all())
    for m in s.scalars(select(Mitglied).order_by(Mitglied.name)).all():
        if m.user and m.user in verantwortlich:
            continue
        if m.user in ("admin@example.org", "anna.beispiel@example.org"):
            continue
        if m.user is None or m.user == "":
            return m
    return None


def main() -> int:
    # Zwei eigene Transaktionen: das Konto muss COMMITTET sein, bevor ein
    # Mitglied darauf verweisen darf (FK mitglied.user -> user.name).
    with SessionLocal.begin() as s:
        with testnaht():
            set_user("Administrator")
            if s.get(User, EMAIL) is None:
                from diakronos_app.frappe_compat.passwoerter import neuer_hash

                # Wie `musterhausen.py::_benutzer_anlegen`: enabled=1 (sonst
                # hat das Konto auch mit Rolle keine Planrechte) und
                # user_type="System User" — der Hash kommt aus demselben Weg,
                # den die Anmeldung prueft (`new_password` kennt der
                # Compat-Schreibweg nicht).
                api_helpers._create("User", {
                    "name": EMAIL, "email": EMAIL, "full_name": NAME,
                    "enabled": 1, "user_type": "System User",
                    "password_hash": neuer_hash(PASSWORT),
                })
                print("Konto angelegt:", EMAIL)
            else:
                print("Konto vorhanden:", EMAIL)
    with SessionLocal.begin() as s:
        with testnaht():
            set_user("Administrator")
            if s.get(HasRole, f"{EMAIL}-Mitglied") is None:
                api_helpers._create("Has Role", {
                    "name": f"{EMAIL}-Mitglied", "parent": EMAIL,
                    "parenttype": "User", "parentfield": "roles",
                    "role": "Mitglied",
                })
                print("Rolle Mitglied gesetzt")
            m = freies_mitglied(s)
            if m is None:
                print("Kein freies Mitglied gefunden", file=sys.stderr)
                return 2
            if m.user != EMAIL:
                m.user, m.email = EMAIL, EMAIL
                s.flush()
                print("Betrachter-Konto an Mitglied gebunden:", m.name)
            else:
                print("Bindung vorhanden:", m.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
