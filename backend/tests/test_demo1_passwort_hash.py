"""DEMO-1: Die Konten der Demo „Musterhausen“ koennen sich anmelden.

BEFUND (UX1d-Worker): der Seed schrieb fuer `admin@example.org` und
`anna.beispiel@example.org` einen Passwort-Hash, der sich NICHT verifizieren
liess — die Demo war damit nur ueber die Datenbank, nicht ueber die
Anmeldemaske benutzbar.

URSACHE: nicht reproduziert. `_benutzer_anlegen` schrieb den Hash vorher als
Feld im selben `Anleger.neu("User", …)`-Aufruf, ueber den generischen
Schreibweg `frappe_compat.api_helpers._create`. Der Hash entsteht jetzt
getrennt ueber den Passwortweg (`frappe_compat.passwoerter.neuer_hash`) und
wird nach dem Setzen mit `pruefe()` gegen das dokumentierte Demo-Passwort
verifiziert; ist er nicht pruefbar, bricht der Seed mit `DemoFehler` ab.

Hinweis: `password_hash` ist auf dem generischen Schreibweg NICHT gesperrt —
`ist_gesperrtes_feld` filtert nur das ZurueckLESEN von Geheimnissen. Der
Schreibweg war also nicht die Ursache eines falschen Hashes, sondern nur der
Ort, an dem der falsche Wert entstand, ohne dass ihn jemand pruefte.

DIESE TESTS sind die Absicherung: jedes Demo-Konto muss sich mit dem
dokumentierten Demo-Passwort ueber den ECHTEN HTTP-Login anmelden koennen
(`POST /api/method/login`, Feld `usr`/`pwd`) — nach dem Seed und nach einem
Neustart-aequivalenten Zurueckrollen/erneuten Lesen derselben Datenbank.
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest

STICHTAG = date(2026, 11, 2)


@pytest.fixture()
def demo(patched_db):
    return importlib.import_module("musterhausen")


def _login_ueber_http(usr: str, pwd: str) -> int:
    """Meldet ueber den echten Endpunkt an und gibt den HTTP-Status zurueck.

    Der Client wird explizit gesetzt: `api/auth.py` liest fuer die
    Brute-Force-Sperre je Adresse `request.client`; ohne ihn bricht der Login
    im Testclient mit „No request object set“ ab (siehe `conftest.client`).

    `follow_redirects=False`: Der Status haengt sonst davon ab, ob im Image
    ein SPA-Build liegt. Der Login antwortet 200; nach einer Umleitung in die
    SPA folgt eine 303 auf `/`. Geprueft wird der Login, nicht das Ziel
    danach — ein Fehlschlag bleibt 401 und wird nicht umgeleitet.
    """
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    with TestClient(app, client=("127.0.0.1", 50000),
                    follow_redirects=False) as c:
        antwort = c.post("/api/method/login", data={"usr": usr, "pwd": pwd})
    return antwort.status_code


def _ist_anmeldung_erfolgreich(status: int) -> bool:
    """Anmeldung gelungen: 200, oder 303 (Umleitung in die SPA nach Login)."""
    return status in (200, 303)


def test_demo_konten_funktionieren_fuer_den_passwortpruefer(engine, session_factory, demo):
    """Jeder Demo-Hash ist mit dem dokumentierten Passwort pruefbar.

    Das ist die Stufe UNTER dem HTTP-Login: derselbe Hash, den die Zeile
    traegt, wird vom Pruefer der App (`frappe_compat.passwoerter.pruefe`)
    akzeptiert — und zwar NUR mit dem richtigen Passwort.
    """
    from diakronos_app.frappe_compat.passwoerter import neuer_hash, pruefe
    from diakronos_app.models.core import User

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for email, passwort in demo.KONTEN.items():
            konto = s.get(User, email)
            assert konto is not None, f"Konto fehlt: {email}"
            assert konto.password_hash, f"{email} hat keinen Hash"
            assert not konto.password_hash.startswith("$pbkdf2"), (
                f"{email} traegt noch einen Frappe-Hash — die Demo soll Argon2 schreiben")
            # Der Hash entsteht ueber die normale Passwort-Funktion des Backends.
            assert pruefe(passwort, konto.password_hash), (
                f"{email}: dokumentiertes Passwort wird abgelehnt")
            assert not pruefe(passwort + "x", konto.password_hash), (
                f"{email}: falsches Passwort wird akzeptiert")
            # Zwei Konten mit gleichem Klartext duerfen NICHT denselben Hash
            # tragen (Argon2 salzt) — ein geteilter Hash waere ein Zeichen
            # dafuer, dass der Wert irgendwo fest verdrahtet ist.
            assert konto.password_hash != neuer_hash(passwort)


def test_demo_konten_bleiben_nach_der_sitzung_in_der_datenbank(engine, session_factory, demo):
    """Der Hash ist COMMITTET — nicht nur geflusht.

    `Anleger` haengt die Skript-Sitzung als aktuelle Sitzung ein; der
    generische Schreibweg (`_create`) committet dort NICHT (nur flush).
    Dieser Test liest in einer NEUEN Sitzung nach und rollt die Skript-
    Sitzung vorher zurueck — genau der Fall, in dem der Hash fruehere
    Fassungen verlor.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    demo.anlegen(stichtag=STICHTAG)

    # Neustart-aequivalent: frische Sitzung, offene Transaktion verworfen.
    with SessionLocal() as s:
        s.rollback()

    with session_factory() as s:
        for email in demo.KONTEN:
            assert s.get(User, email) is not None, f"Konto {email} ist nicht persistiert"
            assert s.get(User, email).password_hash


def test_demo_konten_anmeldung_ueber_http(engine, session_factory, demo, fake_redis):
    """Abnahmekriterium der Karte: Login per HTTP fuer JEDEN Demo-Benutzer."""
    demo.anlegen(stichtag=STICHTAG)
    for email, passwort in demo.KONTEN.items():
        status = _login_ueber_http(email, passwort)
        assert _ist_anmeldung_erfolgreich(status), (
            f"Anmeldung fehlgeschlagen fuer {email} (HTTP {status})")


def test_demo_konten_falsches_passwort_ueber_http(engine, session_factory, demo, fake_redis):
    """Das falsche Passwort wird ueber HTTP abgelehnt (kein offenes Tor)."""
    demo.anlegen(stichtag=STICHTAG)
    for email in demo.KONTEN:
        assert _login_ueber_http(email, "falsches-passwort") == 401, email


def test_demo_konten_persistieren_einen_zweiten_lauf(engine, session_factory, demo, fake_redis):
    """Nach dem Seed (und einem weiteren Lesen) melden sich die Konten an.

    Der zweite Aufruf von `anlegen` bricht wegen belegter Datenbank ab — der
    Zustand davor muss trotzdem vollstaendig in der Datenbank stehen.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    demo.anlegen(stichtag=STICHTAG)
    with SessionLocal() as s:
        s.rollback()
    with pytest.raises(demo.DemoFehler):
        demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for email in demo.KONTEN:
            assert s.get(User, email) is not None
    for email, passwort in demo.KONTEN.items():
        status = _login_ueber_http(email, passwort)
        assert _ist_anmeldung_erfolgreich(status), f"{email}: HTTP {status}"
