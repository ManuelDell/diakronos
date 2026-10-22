"""A1b1 — `/api/method/login` und `/api/method/logout`.

Kern der Karte: anmelden mit einem selbst gesetzten `$pbkdf2-sha256$29000$`-Hash
BEKANNTEN Klartexts (kein geratenes Echtpasswort!), Hebung auf Argon2, und
401 bei falschem Passwort/unbekanntem Benutzer.
"""

from __future__ import annotations

import base64
import hashlib
import time

from diakronos_app.frappe_compat import sitzungen
from diakronos_app.models.core import User


def _frappe_hash(passwort: str, salt: bytes = b"testsalztestsalt", runden: int = 29000) -> str:
    """Baut einen echten Frappe-`$pbkdf2-sha256$`-Hash im passlib-"adapted base64"."""
    digest = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, runden, dklen=32)

    def ab64(roh: bytes) -> str:
        return base64.b64encode(roh).decode().rstrip("=").replace("+", ".")

    return f"$pbkdf2-sha256${runden}${ab64(salt)}${ab64(digest)}"


def _lege_benutzer(session_factory, name: str, passwort: str, **felder) -> None:
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


def _hash_von(session_factory, name: str) -> str:
    sess = session_factory()
    try:
        return sess.get(User, name).password_hash
    finally:
        sess.close()


# ── Erfolgsfall ─────────────────────────────────────────────────────────────


def test_login_mit_frappe_hash_erfolg(client, patched_db):
    """Abnahme: Login mit selbst gesetztem pbkdf2-Hash bekannten Klartexts."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    assert r.status_code == 200
    assert r.json()["message"] == "Logged In"
    assert r.json()["user"] == "anna@example.org"
    # Cookie `sid` gesetzt.
    assert "sid" in r.cookies
    assert len(r.cookies["sid"]) == 56


def test_login_hebt_hash_auf_argon2(client, patched_db):
    """Abnahme: nach dem Login steht ein `$argon2`-Hash in der DB."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    assert _hash_von(patched_db, "anna@example.org").startswith("$pbkdf2-sha256$")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    assert r.status_code == 200
    neuer = _hash_von(patched_db, "anna@example.org")
    assert neuer.startswith("$argon2")
    # Und das Passwort prueft danach immer noch.
    from diakronos_app.frappe_compat.passwoerter import pruefe

    assert pruefe("geheim-123", neuer) is True


def test_zweiter_login_mit_argon2_hash(client, patched_db):
    """Nach der Hebung funktioniert der Login mit demselben Passwort weiter."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    assert client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"}).status_code == 200
    assert _hash_von(patched_db, "anna@example.org").startswith("$argon2")
    assert client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"}).status_code == 200


def test_login_ueber_email_feld(client, patched_db):
    """Frappe akzeptiert neben dem Docname auch die E-Mail als Login-Namen."""
    _lege_benutzer(patched_db, "ANNA-0001", "geheim-123", email="anna@example.org")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    assert r.status_code == 200
    assert r.json()["user"] == "ANNA-0001"


def test_login_setzt_sitzung_in_redis(client, patched_db, fake_redis):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    sid = r.cookies["sid"]
    assert sitzungen.lesen(sid)["user"] == "anna@example.org"


def test_cookie_ist_httponly(client, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie.replace("samesite", "SameSite") or "samesite=lax" in set_cookie.lower()
    assert "Path=/" in set_cookie


# ── Fehlerfaelle ────────────────────────────────────────────────────────────


def test_falsches_passwort_401(client, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "falsch"})

    assert r.status_code == 401
    assert "sid" not in r.cookies
    # Kein Hash/Passwort in der Antwort.
    assert "geheim" not in r.text and "$" not in r.text


def test_unbekannter_benutzer_401(client, patched_db):
    r = client.post("/api/method/login", json={"usr": "niemand@example.org", "pwd": "egal"})

    assert r.status_code == 401
    assert "sid" not in r.cookies


def test_fehlermeldung_ist_bei_beiden_gleich(client, patched_db):
    """Ob der Benutzer existiert, darf die Antwort nicht verraten."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    falsch = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "nope"})
    unbekannt = client.post("/api/method/login", json={"usr": "niemand@example.org", "pwd": "nope"})

    assert falsch.status_code == unbekannt.status_code == 401
    assert falsch.json()["message"] == unbekannt.json()["message"]


def test_antwortzeiten_in_derselben_groessenordnung(client, patched_db):
    """Grob gemessen (Abnahme) — kein Benchmark, nur kein offensichtlicher Leak."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    start = time.perf_counter()
    client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "nope"})
    dauer_falsch = time.perf_counter() - start

    start = time.perf_counter()
    client.post("/api/method/login", json={"usr": "niemand@example.org", "pwd": "nope"})
    dauer_unbekannt = time.perf_counter() - start

    # Faktor 20 ist grosszuegig genug fuer CI-Jitter und schliesst ein
    # "unbekannter Benutzer antwortet sofort" trotzdem aus.
    verhaeltnis = max(dauer_falsch, dauer_unbekannt) / max(min(dauer_falsch, dauer_unbekannt), 1e-6)
    assert verhaeltnis < 20, f"Zeitunterschied zu gross: {dauer_falsch=} {dauer_unbekannt=}"


def test_deaktivierter_benutzer_401(client, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123", enabled=False)

    r = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})

    assert r.status_code == 401


def test_benutzer_ohne_hash_401(client, patched_db):
    sess = patched_db()
    try:
        sess.add(User(name="ohne@example.org", email="ohne@example.org", enabled=True))
        sess.commit()
    finally:
        sess.close()

    r = client.post("/api/method/login", json={"usr": "ohne@example.org", "pwd": "egal"})

    assert r.status_code == 401


def test_leere_anmeldedaten_401(client, patched_db):
    assert client.post("/api/method/login", json={}).status_code == 401
    assert client.post("/api/method/login", json={"usr": "", "pwd": ""}).status_code == 401


# ── Logout ──────────────────────────────────────────────────────────────────


def test_logout_macht_sid_ungueltig(client, patched_db, fake_redis):
    """Abnahme: logout mit dem Cookie macht die sid ungueltig.

    PT1: `/api/method/logout` verlangt jetzt den CSRF-Token (Forced-Logout
    per eingebettetem Bild wird so verhindert). Der Token der Sitzung kommt
    aus der Login-Antwort.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    login = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})
    sid = login.cookies["sid"]
    csrf = login.json()["csrf_token"]
    assert sitzungen.lesen(sid) is not None

    # Cookie explizit mitschicken: der TestClient haelt hier keinen Cookie-Jar
    # ueber Requests hinweg, und genau so verhaelt sich auch der Browser
    # (er sendet `sid` bei jedem Aufruf mit). Der CSRF-Token der Sitzung
    # gehoert dazu (PT1).
    r = client.post("/api/method/logout",
                    cookies={"sid": sid},
                    headers={"X-Frappe-CSRF-Token": csrf})

    assert r.status_code == 200
    assert sitzungen.lesen(sid) is None


def test_logout_ohne_sitzung_ist_200(client, fake_redis):
    assert client.post("/api/method/logout").status_code == 200


def test_logout_ist_idempotent(client, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    login = client.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "geheim-123"})
    sid = login.cookies["sid"]
    csrf = login.json()["csrf_token"]

    assert client.post("/api/method/logout", cookies={"sid": sid},
                       headers={"X-Frappe-CSRF-Token": csrf}).status_code == 200
    # Zweiter Aufruf: die Sitzung ist weg -> kein CSRF-Schutz mehr noetig,
    # der Logout bleibt idempotent 200.
    assert client.post("/api/method/logout", cookies={"sid": sid}).status_code == 200


def test_logout_entfernt_cookie(client, fake_redis):
    """Der `Set-Cookie`-Header beim Logout setzt `sid` auf leer/Max-Age=0."""
    r = client.post("/api/method/logout", cookies={"sid": "x" * 56})

    set_cookie = r.headers["set-cookie"].lower()
    assert "sid=" in set_cookie
    assert "max-age=0" in set_cookie
