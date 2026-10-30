"""SEC-4 — Anmeldung bleibt moeglich, obwohl `Referer` fehlt.

Abnahme im echten Browser (Wegwerf-Stack, 2026-10-29): die Kopfzeile
`Referrer-Policy: no-referrer` (SEC-4) entfernt den `Referer` aus JEDER
Anfrage — auch aus dem eigenen Anmeldeformular. Die Herkunftspruefung
(`api/auth._herkunft_ist_eigen`) verlangte aber `Origin` ODER `Referer`;
nach einer Umleitung (303 auf `/login` nach einem Tippfehler) kam keins von
beiden an. Ergebnis: die RICHTIGE Anmeldung wurde als „fremde Herkunft“
abgewiesen.

Der Fix schreibt einen SIGNIERTEN Token in die Maske
(`anmeldung/maske_token.py`) und laesst ihn als zweiten Nachweis gelten.

Warum signiert und nicht sitzungsgebunden: eine eigens fuer die Maske
angelegte Sitzung verwirft die `SessionMiddleware` sofort wieder, weil sie
zu einem Konto gehoert, das es nicht gibt bzw. das deaktiviert ist
(`benutzer_status.ist_aktiv`) — im Wegwerf-Stack nachgewiesen. Ein Token
ohne Sitzung ist der einzige Weg, der nicht an dieser Regel vorbei muss.

Die Tests sichern beide Richtungen und die Grenzen:

* das eigene Formular kommt durch (Token gueltig, kein `Origin`/`Referer`),
* ein Browser ohne Token kommt NICHT durch,
* ein fremder `Origin` wird weiterhin abgewiesen (auch MIT Token),
* ein gefaelschter oder abgelaufener Token oeffnet nichts,
* ein Client ohne jedes Browser-Merkmal (curl, Apps, Abnahme-Tools) bleibt
  erlaubt — die Regel aus LOGIN-3.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from diakronos_app.main import app

EMAIL = "sec4@example.org"
PASSWORT = "geheim-genug-123"


@pytest.fixture()
def client(patched_db, fake_redis):
    patched_db()
    with TestClient(app) as c:
        yield c


def _konto_anlegen() -> None:
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    s = SessionLocal()
    try:
        if s.get(User, EMAIL) is None:
            s.add(User(name=EMAIL, email=EMAIL, full_name="SEC-4 Probe", enabled=True,
                       password_hash=neuer_hash(PASSWORT)))
            s.commit()
    finally:
        s.close()


def _token_aus_maske(client) -> str:
    """Holt die Maske und liest den Token aus dem Formular."""
    antwort = client.get("/login?noredirect=1")
    assert antwort.status_code == 200
    treffer = re.search(r'name="_csrf" value="([^"]+)"', antwort.text)
    assert treffer, "Anmeldemaske ohne Token-Feld"
    return treffer.group(1)


# ── Der Token selbst ──────────────────────────────────────────────────────


def test_token_ist_signiert_und_begrenzt():
    """Form, Ablauf und Faelschungssicherheit des Masken-Tokens."""
    from diakronos_app.anmeldung import maske_token as mt

    jetzt = 1_800_000_000
    tok = mt.erzeuge_token(jetzt)
    assert re.fullmatch(r"\d+:[0-9a-f]{64}", tok), tok
    assert mt.token_ist_gueltig(tok, jetzt + 10)
    # faelschen: andere Zeit, gleiche Signatur
    _, _, sig = tok.partition(":")
    assert not mt.token_ist_gueltig(f"{jetzt + 1}:{sig}", jetzt + 10)
    # abgelaufen
    assert not mt.token_ist_gueltig(tok, jetzt + mt.FELD_GUELTIG_SEKUNDEN + 1)
    # Unsinn
    for mist in ("", "abc", "123", "123:", ":abc", "123:zz"):
        assert not mt.token_ist_gueltig(mist, jetzt), mist


# ── Der Anmeldeweg ────────────────────────────────────────────────────────


def test_eigenes_formular_ohne_referer_kommt_durch(client):
    """Kein `Origin`, kein `Referer` — dafuer der Token der Maske: erlaubt."""
    _konto_anlegen()
    token = _token_aus_maske(client)

    antwort = client.post(
        "/api/method/login",
        data={"usr": EMAIL, "pwd": PASSWORT, "_csrf": token},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303, antwort.text
    assert antwort.headers.get("location", "").startswith("/diakonos"), antwort.headers
    assert client.cookies.get("sid")


def test_ohne_token_und_ohne_herkunft_bleibt_erlaubt(client):
    """Kein Browser-Merkmal, kein Token: wie bisher erlaubt (Apps, curl, Tests).

    Ausdrueckliche Regel aus LOGIN-2/LOGIN-3 (`test_login2_csrf.py::
    test_formular_ohne_origin_und_referer_bleibt_erlaubt`,
    `test_login3_csrf_rest.py::test_client_ohne_browserkopf_bleibt_erlaubt`).
    Der Token aendert daran nichts — er ist der Gegenbeweis fuer den Fall
    „Browser, aber `Referer` fehlt“, kein allgemeiner Zwang.
    """
    _konto_anlegen()
    _token_aus_maske(client)
    antwort = client.post(
        "/api/method/login",
        data={"usr": EMAIL, "pwd": PASSWORT},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303
    assert antwort.headers.get("location", "").startswith("/diakonos")


def test_fremder_origin_wird_auch_mit_token_abgewiesen(client):
    """Ein fremder `Origin` gewinnt gegen einen (gestohlenen) Token."""
    _konto_anlegen()
    token = _token_aus_maske(client)
    antwort = client.post(
        "/api/method/login",
        data={"usr": EMAIL, "pwd": PASSWORT, "_csrf": token},
        headers={"Accept": "text/html", "Origin": "https://boese.example"},
        follow_redirects=True,
    )
    assert "falsch" in antwort.text
    assert "dk-login" in antwort.text


def test_gefaelschter_token_oeffnet_keine_fremde_herkunft(client):
    """Selbstgebauter Token (ohne Server-Schluessel) + fremder `Origin`: nichts.

    Der Token ist nur ein Ersatz fuer den fehlenden `Referer`; er hebt die
    `Origin`-Pruefung nicht auf.
    """
    _konto_anlegen()
    _token_aus_maske(client)
    antwort = client.post(
        "/api/method/login",
        data={"usr": EMAIL, "pwd": PASSWORT, "_csrf": "1800000000:" + "a" * 64},
        headers={"Accept": "text/html", "Origin": "https://boese.example"},
        follow_redirects=True,
    )
    assert "falsch" in antwort.text


def test_origin_null_mit_token_kommt_durch(client):
    """Chromium schickt nach einer Umleitung `Origin: null` (Abnahme im Browser).

    Beobachtet am 2026-10-29 im Wegwerf-Stack: `Origin: null`, kein
    `Referer` (unser `no-referrer`) — die Anmeldung scheiterte, obwohl das
    Formular von uns kam. `Origin: null` ist keine Herkunft; der Token
    entscheidet. Ein ECHTER fremder `Origin` bleibt abgewiesen
    (`test_fremder_origin_wird_auch_mit_token_abgewiesen`).
    """
    _konto_anlegen()
    token = _token_aus_maske(client)
    antwort = client.post(
        "/api/method/login",
        data={"usr": EMAIL, "pwd": PASSWORT, "_csrf": token},
        headers={"Accept": "text/html", "Origin": "null"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303, antwort.text
    assert antwort.headers.get("location", "").startswith("/diakonos"), antwort.headers


def test_maske_legt_keine_sitzung_an(client):
    """Die Maske braucht weder Redis noch eine Sitzung (SEC-4).

    Kein `sid`-Cookie aus der Maske: der Token ist signiert und zustandslos.
    (Ein leeres `dk_login_flash`-Cookie zum Aufraeumen ist erlaubt — das ist
    die Flash-Spur, kein Sitzungs-Cookie.)
    """
    antwort = client.get("/login?noredirect=1")
    kopf = [w.lower() for w in antwort.headers.get_list("set-cookie")]
    assert not any(k.startswith("sid=") for k in kopf), kopf
