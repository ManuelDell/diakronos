"""A1c2 — Brute-Force-Sperre fuer CalDAV (`PROPFIND /dav/`).

A1c1 hat die Sperre fuer den interaktiven Login gebaut. Hier geht es um den
**zweiten** Zugang zu denselben Konten: CalDAV war bis A1c2 unbegrenzt
durchprobierbar, ein Angreifer brauchte kein Browser-Fenster, nur `curl -u`.

Die fuenf Saetze, die diese Datei zusammenhalten:

  1. Die Sperre ist **nicht erkennbar** — gesperrt, falsches Passwort und
    unbekannter Benutzer liefern Status, Kopfzeilen, Body und Groessenordnung
    der Antwortzeit identisch.
  2. Die Sperre ist **wirksam** — auch das richtige Passwort hilft nicht,
    erst nach Ablauf wieder.
  3. Erfolg **entlastet** den CalDAV-Zaehler (sonst sperrt ein Benutzer mit
    zwei Vertippern sich selbst aus dem Kalender aus).
  4. **Zaehler getrennt, Sperre gemeinsam** — drei Vertipper im Browser
    sperren den Kalender nicht; wer aber per CalDAV brute-forcet, kommt am
    Login nicht vorbei.
  5. Die IP laesst sich **nicht per Kopfzeile** umgehen (`X-Forwarded-For` nur
    mit aktiviertem `BEHIND_PROXY`).
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from diakronos_app.frappe_compat import loginversuche
from diakronos_app.models.core import User

SCHWELLE = 5

# A1c12: ein echter TCP-Peer, kein unparsebarer TestClient-Hostname.
TEST_CLIENT_IP = "203.0.113.90"


# ── Helfer ──────────────────────────────────────────────────────────────────


def _basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


def _frappe_hash(passwort: str, salt: bytes = b"caldavbremsebrem", runden: int = 29000) -> str:
    """Echter Frappe-`pbkdf2-sha256`-Hash eines BEKANNTEN Klartexts.

    Ein Argon2-Hash wuerde den Test um ~90 ms pro Aufruf kosten (dutzende
    Aufrufe = Sekunden). Der Frappe-Hash ist derselbe Code-Pfad, den ein
    importiertes Konto hat — und genau der soll hier geprueft werden.
    """
    digest = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, runden, dklen=32)

    def ab64(roh: bytes) -> str:
        return base64.b64encode(roh).decode().rstrip("=").replace("+", ".")

    return f"$pbkdf2-sha256${runden}${ab64(salt)}{ab64(digest)}".replace(
        ab64(salt) + ab64(digest), ab64(salt) + "$" + ab64(digest)
    )


def _lege_benutzer(session_factory, name: str, passwort: str = "geheim-123", **felder) -> None:
    sess = session_factory()
    try:
        sess.add(User(
            name=name,
            email=felder.pop("email", name),
            full_name=felder.pop("full_name", name),
            enabled=felder.pop("enabled", True),
            password_hash=_frappe_hash(passwort),
        ))
        sess.commit()
    finally:
        sess.close()


def _dav(client, user: str, pw: str, **kwargs):
    """PROPFIND /dav/ mit Basic Auth und gueltiger Peer-IP (A1c12)."""
    client._transport.client = (TEST_CLIENT_IP, 50000)
    return client.request("PROPFIND", "/dav/", headers=_basic(user, pw), **kwargs)


def _serie(client, user: str, pw: str, anzahl: int = SCHWELLE) -> None:
    """`anzahl` Fehlversuche — jede Antwort 401, keine davon gesperrt."""
    for nummer in range(anzahl):
        r = _dav(client, user, pw)
        assert r.status_code == 401, f"Fehlversuch {nummer}: {r.status_code}"


def _sperre(client, user: str, pw: str = "falsch") -> None:
    """Fehlserie bis die Sperre steht — und BESTAETIGT, dass sie steht.

    Wer sich nur darauf verlaesst, dass 5 Fehlversuche gesperrt haetten,
    schreibt einen Test, der die Sperre nicht wirklich belegt.
    """
    _serie(client, user, pw)
    assert _dav(client, user, pw).status_code == 401
    assert loginversuche.ist_gesperrt(user, TEST_CLIENT_IP), "Sperre nicht aktiv"


def _aufloesen(user: str, ip: str = TEST_CLIENT_IP) -> None:
    """Simuliert das Ablaufen der Sperre (im Betrieb der Redis-TTL).

    Wichtig: **beide** Bereiche zuruecksetzen, nicht nur den CalDAV- oder den
    Login-Bereich. Die Sperre ist bereichsuebergreifend, und der Fehlversuchs-
    zaehler des jeweils anderen Bereichs steht nach einer Serie weiterhin auf
    der Schwelle — beim naechsten Versuch wuerde er sonst sofort wieder
    sperren. Genau das ist gewolltes Verhalten (der Zaehler laeuft ja mit
    eigener TTL ab), im Test aber ein Stolperstein.
    """
    for bereich in ("login", "caldav"):
        loginversuche.zuruecksetzen(user, ip, bereich=bereich)


def _stand(user: str, bereich: str, ip: str = TEST_CLIENT_IP) -> dict:
    return loginversuche.zaehler_stand(user, ip, bereich=bereich)


# ── 1. Die Sperre ist nicht erkennbar ───────────────────────────────────────


def test_gesperrt_antwortet_wie_falsches_passwort(client, patched_db, fake_redis):
    """Status, Body und Kopfzeilen des gesperrten Versuchs == falsches Passwort."""
    _lege_benutzer(patched_db, "anna@example.org")

    falsch = _dav(client, "anna@example.org", "falsch")
    _sperre(client, "anna@example.org")
    gesperrt = _dav(client, "anna@example.org", "falsch")

    assert gesperrt.status_code == falsch.status_code == 401
    assert gesperrt.text == falsch.text
    # KEIN Hinweis auf "gesperrt": kein 429, kein Retry-After, keine
    # Zusatzkopfzeile. Sichtbarkeit kostet die Sperre ihren Nutzen.
    assert gesperrt.headers.get("retry-after") is None
    assert set(gesperrt.headers) == set(falsch.headers)
    assert gesperrt.headers["www-authenticate"] == falsch.headers["www-authenticate"]
    assert gesperrt.headers["www-authenticate"] == 'Basic realm="Diakronos CalDAV"'


def test_gesperrt_ist_auch_fuer_unbekannten_benutzer_401(client, patched_db, fake_redis):
    """Ein gesperrter Versuch sieht nicht aus wie "unbekannter Benutzer"."""
    unbekannt = _dav(client, "niemand@example.org", "egal")
    _sperre(client, "niemand@example.org")
    gesperrt = _dav(client, "niemand@example.org", "egal")

    assert gesperrt.status_code == unbekannt.status_code == 401
    assert gesperrt.text == unbekannt.text
    assert set(gesperrt.headers) == set(unbekannt.headers)


def test_gesperrt_antwortzeit_ist_nicht_erkennbar(client, patched_db, fake_redis):
    """Die Sperre darf nicht daran erkennbar sein, dass sie schneller ist.

    Der gesperrte Zweig verbraucht denselben Dummy-Hash wie ein Benutzer
    ohne Pruefmöglichkeit — sonst waere die Sperre per Zeitmessung sichtbar
    und ein Angreifer wuesste sofort, dass er den richtigen Namen hat.
    """
    import time

    _lege_benutzer(patched_db, "anna@example.org")

    def median(aufrufe: int = 7) -> float:
        dauer = []
        for _ in range(aufrufe):
            start = time.perf_counter()
            _dav(client, "anna@example.org", "falsch")
            dauer.append(time.perf_counter() - start)
        dauer.sort()
        return dauer[len(dauer) // 2]

    # Aufwaermen: der erste Aufruf enthaelt den Argon2-Dummy-Aufbau.
    median(2)
    falsch = median()

    _sperre(client, "anna@example.org")
    gesperrt = median()

    verhaeltnis = max(gesperrt, falsch) / max(min(gesperrt, falsch), 1e-6)
    # Faktor 2: CI-Jitter laesst keinen engeren Wert zu. Ein Sonderfall
    # "gesperrt antwortet in 2 ms" waere Faktor 50+.
    assert verhaeltnis < 2.0, f"Sperre an der Zeit erkennbar: {gesperrt=} {falsch=}"


# ── 2. Die Sperre ist wirksam ───────────────────────────────────────────────


def test_richtiges_passwort_waehrend_der_sperre_auch_401(client, patched_db, fake_redis):
    """Der Kern der Karte: richtig eingeloggt und trotzdem abgewiesen."""
    _lege_benutzer(patched_db, "anna@example.org")

    _sperre(client, "anna@example.org")

    r = _dav(client, "anna@example.org", "geheim-123")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == 'Basic realm="Diakronos CalDAV"'


def test_nach_ablauf_der_sperre_wieder_207(client, patched_db, fake_redis):
    """Nach Ablauf der Sperre funktioniert derselbe Zugang wieder."""
    _lege_benutzer(patched_db, "anna@example.org")
    _sperre(client, "anna@example.org")
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 401

    _aufloesen("anna@example.org")

    r = _dav(client, "anna@example.org", "geheim-123")
    assert r.status_code == 207
    assert "current-user-principal" in r.text


def test_sperre_greift_auch_fuer_einen_anderen_benutzer(client, patched_db, fake_redis):
    """IP-Sperre: ein Benutzer sperrt die ganze IP — auch Unbeteiligte.

    **A1c10:** das sind jetzt **fuenfundzwanzig** Fehlversuche mit
    verschiedenen (unbekannten) Namen, nicht fuenf. Fuenf sperren weiterhin
    das **Konto**; die Adresse erst ab 25 — das ist der ganze Unterschied,
    und dieser Test ist der Beweis dafuer, dass CalDAV beide Regeln
    automatisch mitbekommt (derselbe Store, dieselbe Funktion).
    """
    from diakronos_app.frappe_compat import loginversuche as lv

    adressschwelle = lv._max_versuche("ip")

    # ── Zwischen den Schwellen ist die Adresse noch frei ──────────────────
    # **Adressschwelle MINUS EIN**, und das ist der Punkt, den man leicht
    # falsch erwischt: `pruefe_und_merke` sperrt bei `zaehler > schwelle`
    # (A1c1-Frappes-Zaehlweise), sperrt also mit dem **26.** Versuch dieser
    # Adresse. Nach 25 Fehlversuchen steht der Zaehler auf 25, und der
    # naechste Versuch — der mit dem guten Passwort — waere bereits der
    # sperrende. Der gewuenschte Aussagepunkt ist "24 Fehlversuche, dann
    # kommt ein Unbeteiligter noch durch".
    for nummer in range(adressschwelle - 1):
        assert _dav(client, f"opfer{nummer}@example.org", "egal").status_code == 401

    _lege_benutzer(patched_db, "anna@example.org")
    r = _dav(client, "anna@example.org", "geheim-123")
    assert r.status_code == 207, (
        f"bei {adressschwelle - 1} Fehlversuchen darf die Adresse noch nicht "
        f"gesperrt sein (war {r.status_code})"
    )

    # Der Erfolg hat den Adresszaehler **geleert** (`entlaste`) — das ist
    # Absicht und keine Nebenwirkung dieser Karte. Wer hier einfach zwei
    # Fehlversuche anhaengte, wuerde die Sperre der Serie davor zerstoeren,
    # ohne es zu merken: der naechste Versuch stuende bei 3, nicht bei 26.
    assert lv.zaehler_stand("anna@example.org", TEST_CLIENT_IP, bereich="caldav")["ip"] == 0

    # ── Und jetzt: die volle Serie ueber viele Konten sperrt die Adresse ──
    for nummer in range(adressschwelle + 1):
        assert _dav(client, f"attacke{nummer}@example.org", "egal").status_code == 401

    assert lv.ist_gesperrt(None, TEST_CLIENT_IP) is True, "die Adresssperre greift nicht"

    # Und jetzt ist auch der Benutzer mit dem richtigen Passwort draussen —
    # das ist der eigentliche Zweck der Sammelsperre.
    r = _dav(client, "anna@example.org", "geheim-123")

    assert r.status_code == 401, "ein Unbeteiligter kam trotz Adresssperre herein"


# ── 3. Zuruecknehmen nach Erfolg ────────────────────────────────────────────


def test_erfolg_setzt_den_caldav_zaehler_zurueck(client, patched_db, fake_redis):
    """Abnahme: Fehlversuch, Fehlversuch, Erfolg, dann wieder die volle Serie."""
    _lege_benutzer(patched_db, "anna@example.org")

    assert _dav(client, "anna@example.org", "falsch").status_code == 401
    assert _dav(client, "anna@example.org", "falsch").status_code == 401
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207

    stand = _stand("anna@example.org", "caldav")
    assert stand["benutzer"] == 0, "Erfolg muss den CalDAV-Zaehler leeren"

    # Und die volle Serie ist danach wieder moeglich.
    _sperre(client, "anna@example.org")
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 401


def test_erfolg_setzt_auch_den_ip_zaehler_zurueck(client, patched_db, fake_redis):
    _lege_benutzer(patched_db, "anna@example.org")

    _dav(client, "anna@example.org", "falsch")
    _dav(client, "anna@example.org", "geheim-123")

    assert _stand("anna@example.org", "caldav")["ip"] == 0


def test_zwei_vertipper_und_caldav_sperren_nicht(client, patched_db, fake_redis):
    """Der Alltagsfall: zweimal danebengetippt und gut drauf."""
    _lege_benutzer(patched_db, "anna@example.org")

    assert _dav(client, "anna@example.org", "gehesim").status_code == 401
    assert _dav(client, "anna@example.org", "gehem-123").status_code == 401
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207

    for _ in range(3):
        assert _dav(client, "anna@example.org", "falsch").status_code == 401
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207


# ── 4. Zaehler getrennt, Sperre gemeinsam ───────────────────────────────────


def test_browser_vertipper_sperren_den_kalender_nicht(client, patched_db, fake_redis):
    """Abnahme: die Zaehler sind GETRENNT.

    Wer sich viermal im Browser anmeldet (SCHWELLE-1 Versuche, also noch
    keine Sperre), hat seinen Kalender damit nicht blockiert — und umgekehrt.
    """
    from diakronos_app.models.core import User  # noqa: F401 — Import prueft die Tabelle

    _lege_benutzer(patched_db, "anna@example.org")

    for _ in range(SCHWELLE - 1):
        assert client.post("/api/method/login",
                           json={"usr": "anna@example.org", "pwd": "falsch"}).status_code == 401

    login_stand = _stand("anna@example.org", "login")
    caldav_stand = _stand("anna@example.org", "caldav")
    assert login_stand["benutzer"] == SCHWELLE - 1
    assert caldav_stand["benutzer"] == 0, "CalDAV darf nicht mitzaehlen"

    # Und der Kalender ist noch offen.
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207


def test_caldav_vertipper_sperren_den_browser_nicht(client, patched_db, fake_redis):
    """Die Umgekehrte Richtung: derselbe Nutzer, derselbe Vorgang."""
    _lege_benutzer(patched_db, "anna@example.org")

    for _ in range(SCHWELLE - 1):
        assert _dav(client, "anna@example.org", "falsch").status_code == 401

    assert _stand("anna@example.org", "caldav")["benutzer"] == SCHWELLE - 1
    assert _stand("anna@example.org", "login")["benutzer"] == 0

    assert client.post("/api/method/login",
                       json={"usr": "anna@example.org", "pwd": "geheim-123"}).status_code == 200


def test_caldav_sperre_greift_auch_im_login(client, patched_db, fake_redis):
    """Abnahme: wer per CalDAV brute-forcet, kommt am Login nicht vorbei.

    Die Sperre ist die Sanktion, nicht der Zaehler. Sie liegt in einem
    eigenen Namensraum und gilt fuer beide Benutzeroberflaechen.
    """
    _lege_benutzer(patched_db, "anna@example.org")
    _sperre(client, "anna@example.org")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    assert r.status_code == 401
    assert r.json()["message"] == "Ungueltige Anmeldedaten"


def test_login_sperre_greift_auch_im_caldav(client, patched_db, fake_redis):
    """Und die Umgekehrte: eine Login-Sperre sperrt auch den Kalender."""
    _lege_benutzer(patched_db, "anna@example.org")

    for nummer in range(SCHWELLE):
        assert client.post("/api/method/login",
                           json={"usr": "anna@example.org", "pwd": "falsch"}).status_code == 401
    assert client.post("/api/method/login",
                       json={"usr": "anna@example.org", "pwd": "falsch"}).status_code == 401
    assert loginversuche.ist_gesperrt("anna@example.org", TEST_CLIENT_IP)

    assert _dav(client, "anna@example.org", "geheim-123").status_code == 401


def test_die_bereiche_benutzen_getrennte_zaehler_keys(client, patched_db, fake_redis):
    """Beleg auf Keyebene: zwei Zaehler-Keys, EIN Sperr-Key."""
    _lege_benutzer(patched_db, "anna@example.org")
    _dav(client, "anna@example.org", "falsch")

    zaehler = [k for k in fake_redis._values if loginversuche._hash("anna@example.org") in k]
    assert any(k.startswith("diakronos:caldavversuche:") for k in zaehler), zaehler
    assert not any(k.startswith(loginversuche.SCHLUESSEL_PRAEFIX) for k in zaehler), zaehler


def test_erfolg_im_caldav_leert_den_login_zaehler_nicht(client, patched_db, fake_redis):
    """Ein CalDAV-Erfolg raeumt nur den CalDAV-Zaehler weg — nicht den des Logins.

    Wichtig, weil es zwei moegliche Fehlrichtungen gibt: Der Zaehler des
    anderen Bereichs **darf nicht** mitgeloescht werden (sonst kaennte ein
    Angreifer mit EINEM gueltigen Passwort die Fehlversuchszaehler des
    Logins wegraeumen), und die Sperre **darf nur durch Ablauf** fallen
    (sie wird VOR der Passwortpruefung geprueft — unter einer Sperre kommt
    es gar nicht erst zum Erfolg).
    """
    _lege_benutzer(patched_db, "anna@example.org")

    # Der Login-Bereich sammelt vier Fehlversuche.
    for _ in range(SCHWELLE - 1):
        assert client.post("/api/method/login",
                           json={"usr": "anna@example.org", "pwd": "falsch"}).status_code == 401
    assert _stand("anna@example.org", "login")["benutzer"] == SCHWELLE - 1

    # Erfolg am Kalender.
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207

    # Der CalDAV-Zaehler ist frei ...
    assert _stand("anna@example.org", "caldav")["benutzer"] == 0
    # ... der Login-Zaehler unberuehrt: der naechste Login-Fehlversuch
    # waere der fuenfte und wuerde den Benutzer sperren.
    assert _stand("anna@example.org", "login")["benutzer"] == SCHWELLE - 1


def test_eine_sperre_faellt_nur_durch_ablauf_und_nicht_durch_erfolg(client, patched_db, fake_redis):
    """Unter einer Sperre gibt es keinen Erfolg — sie endet nur mit der Zeit.

    Das ist die bewusst gewaehlte Eigenschaft: die Sperre wird VOR der
    Passwortpruefung geprueft, also kann auch das richtige Passwort sie
    nicht kaufen. Wer sie aufheben will, wartet (oder der Backoff macht sie
    unbequem lang).
    """
    _lege_benutzer(patched_db, "anna@example.org")
    _sperre(client, "anna@example.org")

    # Auch nicht ueber den ANDEREN Zugang: die Sperre ist bereichsuebergreifend.
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 401
    assert client.post("/api/method/login",
                       json={"usr": "anna@example.org", "pwd": "geheim-123"}).status_code == 401
    assert loginversuche.ist_gesperrt("anna@example.org", TEST_CLIENT_IP)

    # Erst der Ablauf macht wieder Platz.
    _aufloesen("anna@example.org")
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207


# ── 5. X-Forwarded-For hebt die IP-Sperre nicht auf ─────────────────────────


def test_xff_umgeht_die_ip_sperre_nicht(client, patched_db, fake_redis):
    """Abnahme-Kernfall: IP-Sperre laesst sich nicht durch einen Header heben.

    `X-Forwarded-For` setzt der Client. Ohne aktivierten Proxy-Schalter
    zaehlt der IP-Zaehler weiter nach `request.client.host` — jeder neue
    gefaelschte Header waere sonst ein neues Leben.
    """
    _lege_benutzer(patched_db, "anna@example.org")
    for nummer in range(SCHWELLE):
        r = client.request("PROPFIND", "/dav/", headers={
            **_basic("anna@example.org", "falsch"),
            "X-Forwarded-For": f"203.0.113.{nummer}",
        })
        assert r.status_code == 401

    r = client.request("PROPFIND", "/dav/", headers={
        **_basic("anna@example.org", "geheim-123"),
        "X-Forwarded-For": "198.51.100.7",
    })

    assert r.status_code == 401, "Gegengipfel: XFF ohne Schalter hebt die Sperre auf"


def test_xff_wird_ohne_proxy_schalter_ignoriert():
    """Die reine IP-Regel, ohne HTTP: fail closed."""
    from diakronos_app import request_context, settings as settingsmod

    request_context.clear_request()
    try:
        with_proxy = settingsmod.settings.behind_proxy
        settingsmod.settings.behind_proxy = False
        # Kontext so setzen, als kaeme der Header an (wie im echten Request).
        _client = request_context._client_ip
        _headers = request_context._headers
        _client.set("198.51.100.1")
        _headers.set({"x-forwarded-for": "203.0.113.9"})
        assert request_context.zaehler_client_ip() == "198.51.100.1"
    finally:
        settingsmod.settings.behind_proxy = with_proxy
        request_context.clear_request()


def test_xff_greift_mit_proxy_schalter():
    """MIT Schalter zaehlt der Header — sonst waere er hinter Proxy tot."""
    from diakronos_app import request_context, settings as settingsmod

    request_context.clear_request()
    with_proxy = settingsmod.settings.behind_proxy
    try:
        settingsmod.settings.behind_proxy = True
        _client = request_context._client_ip
        _headers = request_context._headers
        _client.set("198.51.100.1")            # der Proxy
        _headers.set({"x-forwarded-for": "203.0.113.9, 198.51.100.2"})
        # Der ERSTE Wert ist der Absender; die folgenden sind Stationen.
        assert request_context.zaehler_client_ip() == "203.0.113.9"
        # Ohne Header bleibt die Direktadresse (kein Proxy-Fall).
        _headers.set({})
        assert request_context.zaehler_client_ip() == "198.51.100.1"
    finally:
        settingsmod.settings.behind_proxy = with_proxy
        request_context.clear_request()


# ── Ein Kaputter Client zaehlt nicht ────────────────────────────────────────


@pytest.mark.parametrize("bad", [
    "Bearer abc",
    "Basic !!!kein-base64",
    "Basic " + base64.b64encode(b"ohnedoppelpunkt").decode(),
])
def test_kaputter_authorization_header_zaehlt_nicht(client, patched_db, fake_redis, bad):
    """Muell ist kein Versuch.

    Zaehlte er, koennte ein Angreifer jeden Benutzer sperren, indem er
    Muell schickt — die Sperre waere dann ein DoS-Werkzeug.
    """
    for _ in range(SCHWELLE + 3):
        r = client.request("PROPFIND", "/dav/", headers={"Authorization": bad})
        assert r.status_code == 401

    assert _stand("anna@example.org", "caldav")["benutzer"] == 0
    assert not any(loginversuche.SPERRE_PRAEFIX in k for k in fake_redis._values)


def test_ohne_authorization_header_zaehlt_nicht(client, patched_db, fake_redis):
    """Auch ein fehlender Header ist kein Versuch (Browser-Vorabanfrage)."""
    for _ in range(SCHWELLE + 3):
        assert client.request("PROPFIND", "/dav/").status_code == 401

    assert _stand("anna@example.org", "caldav")["ip"] == 0
    assert not any(loginversuche.SPERRE_PRAEFIX in k for k in fake_redis._values)


def test_options_zaehlt_nicht(client, patched_db, fake_redis):
    """OPTIONS ist eine Faehigkeitsabfrage ohne Credentials — kein Versuch."""
    for _ in range(SCHWELLE + 3):
        assert client.request("OPTIONS", "/dav/").status_code == 200

    assert not any(loginversuche.SPERRE_PRAEFIX in k for k in fake_redis._values)


# ── Kein Informationsleck ───────────────────────────────────────────────────


def test_redis_key_enthaelt_keine_email_und_kein_passwort(client, patched_db, fake_redis):
    """Abnahme: kein Schluessel nennt die E-Mail, kein Wert das Passwort."""
    _lege_benutzer(patched_db, "anna@example.org")
    _dav(client, "anna@example.org", "falsch")

    rohdaten = repr(fake_redis._values) + repr(fake_redis._sets)

    assert "anna" not in rohdaten
    assert "example.org" not in rohdaten
    assert "geheim" not in rohdaten
    assert any(k.startswith("diakronos:caldavversuche:") for k in fake_redis._values)


def test_audit_eintrag_ohne_klartext(client, patched_db, fake_redis):
    """Der abgewiesene Versuch wird protokolliert — pseudonym."""
    from diakronos_app.models.diakonos import AuditLog

    _lege_benutzer(patched_db, "anna@example.org")
    _sperre(client, "anna@example.org")
    _dav(client, "anna@example.org", "geheim-123")  # auch der wird abgewiesen

    sess = patched_db()
    try:
        zeilen = [z for z in sess.query(AuditLog).all()
                  if "Brute-Force" in (z.begruendung or "")]
    finally:
        sess.close()

    assert zeilen, "ein abgewiesener Versuch muss protokolliert werden"
    volltext = " ".join(
        str(getattr(z, feld) or "")
        for z in zeilen
        for feld in ("begruendung", "target_name", "ip_address", "old_value", "new_value")
    )
    assert "anna" not in volltext.lower()
    assert "example.org" not in volltext.lower()
    assert "geheim" not in volltext
    assert "CalDAV" in zeilen[0].begruendung  # der Zugang ist benannt
    assert zeilen[0].target_name.startswith("sha256:")


def test_erfolgreicher_zugriff_erzeugt_keinen_sperr_eintrag(client, patched_db, fake_redis):
    from diakronos_app.models.diakonos import AuditLog

    _lege_benutzer(patched_db, "anna@example.org")
    _dav(client, "anna@example.org", "falsch")
    assert _dav(client, "anna@example.org", "geheim-123").status_code == 207

    sess = patched_db()
    try:
        zeilen = [z for z in sess.query(AuditLog).all()
                  if "Brute-Force" in (z.begruendung or "")]
    finally:
        sess.close()
    assert zeilen == [], "ein normaler Fehlversuch ist keine Sperre"


def test_audit_fehlschlag_haelt_die_sperre_nicht_auf(client, patched_db, fake_redis, monkeypatch):
    """Faellt der Audit-Eintrag aus, bleibt der Zugang trotzdem gesperrt.

    Sonst wuerde ein Angreifer die Sperre durch Ueberlasten der
    Logbuchhaltung abschalten — ein DoS als Ausfallschalter.
    """
    import diakronos_app.frappe_compat.api_helpers as helpers

    _lege_benutzer(patched_db, "anna@example.org")
    _sperre(client, "anna@example.org")

    def _kaputt(*_a, **_kw):
        raise RuntimeError("Audit-DB weg")

    monkeypatch.setattr(helpers, "_create", _kaputt)
    r = _dav(client, "anna@example.org", "geheim-123")

    assert r.status_code == 401
    assert loginversuche.ist_gesperrt("anna@example.org", TEST_CLIENT_IP)


# ── Konfiguration ───────────────────────────────────────────────────────────


def test_defaults_sind_gesetzt():
    """Ohne ENV startet die App und sperrt trotzdem — Pflicht der Karte."""
    from diakronos_app.settings import settings

    assert settings.login_max_versuche >= 1
    assert settings.login_sperre_sekunden >= 30
    assert settings.login_sperre_max_faktor >= 1
    # **fail closed**: ohne den Schalter wird X-Forwarded-For nicht geglaubt.
    assert settings.behind_proxy is False


def test_caldav_zaehlt_in_seinem_eigenen_bereich():
    """Der Bereich ist ein Modul-Bezeichner, kein Geheimnis — aber ein fester."""
    assert loginversuche.BEREICH_CALDAV == "caldav"
    assert loginversuche.BEREICH_LOGIN == "login"
    assert loginversuche.BEREICH_CALDAV != loginversuche.BEREICH_LOGIN


def test_bereichsname_kann_den_namensraum_nicht_verlassen():
    """Auch ein verdächtiger Bereichsname baut keinen Key ausserhalb."""
    kriegsliste = loginversuche._zaehler_praefix("../../evil")
    assert kriegsliste.startswith("diakronos:")
    assert ".." not in kriegsliste
    assert "/" not in kriegsliste


# ── 8. Aufraehrweg fuer die Folgekarte A1c6 ──────────────────────────────────
#
# Gesperrte Konten kommen sonst nur ueber die Zeit wieder herein. Ist der
# einzige Administrator selbst gesperrt, gibt es niemanden, der warten kann
# — und einen Passwort-Reset gibt es bewusst nicht. Die Folgekarte baut die
# Oberflaeche dafuer; hier steht nur der Store, an dem sie andockt.
#
# Die Anforderung des Betreibers war ausdruecklich EINE oeffentliche Funktion
# fuer ALLE Bereiche, damit A1c6 weder `BEREICH_LOGIN`/`BEREICH_CALDAV`
# kennen noch eine Bereichsliste pflegen muss.


def test_zuruecksetzen_alles_leert_zaehler_und_sperre_in_beiden_bereichen(fake_redis):
    """Der Aufraehrweg raeumt Login UND CalDAV ab — mit EINEM Aufruf."""
    user = "anna@example.org"
    ip = TEST_CLIENT_IP

    # Beide Bereiche mit einer halben Serie daneben, CalDAV bis zur Sperre.
    loginversuche.pruefe_und_merke(user, ip, bereich=loginversuche.BEREICH_LOGIN)
    loginversuche.pruefe_und_merke(user, ip, bereich=loginversuche.BEREICH_LOGIN)
    loginversuche.pruefe_und_merke(user, ip, bereich=loginversuche.BEREICH_CALDAV)
    for _ in range(SCHWELLE + 1):
        loginversuche.pruefe_und_merke(user, ip, bereich=loginversuche.BEREICH_CALDAV)
    assert loginversuche.ist_gesperrt(user, ip)

    loginversuche.zuruecksetzen_alles(user)

    assert not loginversuche.ist_gesperrt(user, ip), "Sperre steht noch"
    # Auch die Zaehler sind weg, nicht nur die Sperre — sonst sperrt der
    # naechste Versuch sofort wieder, und der Admin wundert sich.
    for bereich in loginversuche.BEREICHE:
        stand = loginversuche.zaehler_stand(user, None, bereich=bereich)
        assert stand["benutzer"] == 0, f"Bereich {bereich} hat noch Fehlversuche"


def test_zuruecksetzen_alles_wirkt_auf_jeden_bereich_in_der_liste(fake_redis):
    """Der Aufraehrweg laeuft ueber `BEREICHE` — nicht ueber zwei Aufrufe.

    Wer die Liste um einen dritten Zugang erweitert, bekommt die Freigabe
    dort automatisch; wer stattdessen zwei Bereichsnamen hart kodiert,
    vergisst sie beim dritten.
    """
    user = "anna@example.org"
    ip = TEST_CLIENT_IP
    for bereich in loginversuche.BEREICHE:
        for _ in range(SCHWELLE + 1):
            loginversuche.pruefe_und_merke(user, ip, bereich=bereich)
    assert loginversuche.ist_gesperrt(user, ip)

    loginversuche.zuruecksetzen_alles(user)

    assert not loginversuche.ist_gesperrt(user, ip)


def test_zuruecksetzen_alles_ignoriert_die_gross_klein_schreibung(fake_redis):
    """Der Admin tippt die Adresse ein — Gross/Klein darf nicht entscheiden.

    Die Schluessel entstehen ueber `user.strip().lower()`. Waere die
    Normalisierung hier anders als im Anmeldepfad, wuerde die Freigabe
    ins Leere laufen und der einzige Admin bliebe ausgesperrt.
    """
    user = "anna@example.org"
    ip = TEST_CLIENT_IP
    for _ in range(SCHWELLE + 1):
        loginversuche.pruefe_und_merke(user, ip, bereich=loginversuche.BEREICH_CALDAV)
    assert loginversuche.ist_gesperrt(user, ip)

    loginversuche.zuruecksetzen_alles("  ANNA@Example.ORG  ")

    assert not loginversuche.ist_gesperrt(user, ip)


def test_zuruecksetzen_alles_laesst_andere_konten_gesperrt(fake_redis):
    """Freigeben heisst freigeben — nicht "alle Schluessel leeren"."""
    a, b = "anna@example.org", "berta@example.org"
    for _ in range(SCHWELLE + 1):
        loginversuche.pruefe_und_merke(a, None, bereich=loginversuche.BEREICH_CALDAV)
        loginversuche.pruefe_und_merke(b, None, bereich=loginversuche.BEREICH_CALDAV)
    assert loginversuche.ist_gesperrt(a, None)
    assert loginversuche.ist_gesperrt(b, None)

    loginversuche.zuruecksetzen_alles(a)

    assert not loginversuche.ist_gesperrt(a, None), "a ist nicht freigegeben"
    assert loginversuche.ist_gesperrt(b, None), "b wurde mitfreigegeben"


def test_zuruecksetzen_alles_gibt_nichts_zurueck_was_klartext_waere(fake_redis):
    """Die Freigabe braucht die Zuordnung, nicht den Keyspace-Inhalt.

    A1c6 entsperrt ueber die vom Admin getippte Adresse, nicht durch
    Scannen. Deshalb gibt die Funktion nichts zurueck, was eine E-Mail
    preisgeben wuerde — und der Keyspace selbst traegt sie nirgends.
    """
    user = "anna@example.org"
    for _ in range(SCHWELLE + 1):
        loginversuche.pruefe_und_merke(user, None, bereich=loginversuche.BEREICH_CALDAV)

    ergebnis = loginversuche.zuruecksetzen_alles(user)

    assert ergebnis is None, "kein Rueckgabewert mit Adressen"
    alle = " ".join(fake_redis._values)
    assert user not in alle
    assert "anna" not in alle
