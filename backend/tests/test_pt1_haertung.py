"""PT1 — Haertung der SEC1-Anmeldung: Befunde mit Gegenprobe-Test.

Die Karte PT1 hat die SEC1-Anmeldung (OIDC + Forward-Auth) autorisiert
geprueft. Zwei Befunde sind hier mit einem Test belegt, der den ANGRIFF
abwehrt — faellt der Code auf den alten Stand zurueck, wird dieser Test rot:

1. **Atomare `state`-Entnahme** (`anmeldung/transaktionen.py`). Vorher las
   `entnehmen()` mit `GET` und loeschte danach mit `DELETE`. Unter Nebenlauf
   lasen zwei Anfragen denselben `state` als vorhanden und loesten denselben
   Autorisierungscode theoretisch zweimal ein (Authorization-Code-Replay).
   Jetzt passiert das Entnehmen in einem Schritt (`GETDEL`).
2. **Logout ohne CSRF-Schutz** (`anmeldung/routen.py`, `CSRF_EXEMPT_PATHS`).
   Ein fremdes `<img src="/logout">` konnte die Sitzung eines angemeldeten
   Nutzers beenden (Forced Logout). Der Logout verlangt jetzt denselben
   CSRF-Token wie jeder andere schreibende Aufruf.
"""

from __future__ import annotations

import threading

# ── 1. Atomare state-Entnahme ───────────────────────────────────────────────


def test_entnehmen_ist_atomar_unter_nebenlauf(monkeypatch):
    """Zwei nebenlaeufige `entnehmen()` sehen den `state` nur EINMAL.

    Nebenlauf wird echt erzeugt: zwei Threads treffen gleichzeitig auf
    denselben Schluessel. Waere das Lesen und Loeschen getrennt (alter
    Stand), lieferten beide den Wert.
    """
    from diakronos_app.anmeldung import transaktionen
    from redis_stub import StubRedis

    stub = StubRedis()
    monkeypatch.setattr(transaktionen, "_client", lambda: stub)
    stub.set(transaktionen._key("state-1"), '{"nonce": "n", "code_verifier": "v"}')

    ergebnisse: list[dict | None] = []
    schranke = threading.Barrier(2)

    def _entnehmen() -> None:
        schranke.wait()
        ergebnisse.append(transaktionen.entnehmen("state-1"))

    threads = [threading.Thread(target=_entnehmen) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for e in ergebnisse if e is not None) == 1, ergebnisse
    assert sum(1 for e in ergebnisse if e is None) == 1, ergebnisse
    # Beim zweiten Mal ist der Schluessel wirklich weg.
    assert transaktionen.entnehmen("state-1") is None


def test_entnehmen_nutzt_getdel_und_nicht_get_plus_delete(monkeypatch):
    """Der Produktivweg benutzt `GETDEL` (ein Kommando), nicht `GET`+`DELETE`.

    Sonst waere die Atomaritaet nur eine Annahme ueber die Reihenfolge.
    """
    ausgerufen: list[str] = []

    class ZaehlClient:
        def getdel(self, key):
            ausgerufen.append("getdel")
            return None

        def get(self, key):
            ausgerufen.append("get")
            return None

        def delete(self, key):
            ausgerufen.append("delete")

    from diakronos_app.anmeldung import transaktionen

    monkeypatch.setattr(transaktionen, "_client", lambda: ZaehlClient())
    assert transaktionen.entnehmen("egal") is None
    assert ausgerufen == ["getdel"]


def test_entnehmen_rueckfall_ohne_getdel_liest_und_loescht():
    """Ohne `GETDEL` (alter Redis, fremder Stub) bleibt Einmalverwendung.

    Der Rueckfall ueber die Pipeline liest UND loescht ebenfalls.
    """
    from diakronos_app.anmeldung import transaktionen

    class OhneGetdel:
        def __init__(self):
            self._werte = {"k": '{"nonce": "n", "code_verifier": "v"}'}

        def pipeline(self, transaction: bool = True):
            return _Pipe(self)

    class _Pipe:
        def __init__(self, store):
            self._store = store
            self._ops = []

        def get(self, key):
            self._ops.append(("get", key))
            return self

        def delete(self, key):
            self._ops.append(("delete", key))
            return self

        def execute(self):
            ergebnis = []
            for op, key in self._ops:
                if op == "get":
                    ergebnis.append(self._store._werte.get(key))
                else:
                    self._store._werte.pop(key, None)
                    ergebnis.append(1)
            return ergebnis

    client = OhneGetdel()
    from diakronos_app.anmeldung import transaktionen as t

    # Direkter Aufruf des Rueckfalls: `_getdel` ohne `getdel`-Attribut.
    wert = t._getdel(client, "k")
    assert wert is not None
    assert "k" not in client._werte


def test_entnehmen_mit_falschem_oder_leerem_state(monkeypatch):
    """Leerer/fehlender `state` und bereits entnommener `state` -> None."""
    from diakronos_app.anmeldung import transaktionen
    from redis_stub import StubRedis

    stub = StubRedis()
    monkeypatch.setattr(transaktionen, "_client", lambda: stub)
    assert transaktionen.entnehmen("") is None
    assert transaktionen.entnehmen("nie-abgelegt") is None


# ── 2. Logout ist CSRF-geschuetzt ───────────────────────────────────────────


def test_logout_ist_nicht_von_csrf_ausgenommen():
    """Weder `/api/method/logout` noch `/logout` stehen in der Ausnahmeliste."""
    from diakronos_app.frappe_compat.auth_middleware import CSRF_EXEMPT_PATHS

    assert "/api/method/logout" not in CSRF_EXEMPT_PATHS
    assert "/logout" not in CSRF_EXEMPT_PATHS


def test_logout_ohne_csrf_token_abgewiesen(client):
    """Ein Logout-Aufruf MIT Sitzung, aber OHNE CSRF-Token wird abgelehnt.

    Genau der Angriff: eine fremde Seite kann den `X-Frappe-CSRF-Token`-Header
    nicht setzen, `sid` geht als Cookie aber automatisch mit.
    """
    from diakronos_app.frappe_compat import sitzungen

    # Eigener Client ohne CSRF-Header, mit gueltiger Sitzung.
    sid, _csrf = sitzungen.anlegen("Administrator")
    client.headers.pop("x-frappe-csrf-token", None)
    client.cookies.set("sid", sid)

    r = client.post("/api/method/logout")
    assert r.status_code == 417
    assert r.json().get("exc_type") == "CSRFTokenError"
    # Die Sitzung lebt noch — der Zwangs-Logout hat NICHT gewirkt.
    assert sitzungen.lesen(sid) is not None


def test_logout_mit_csrf_token_erlaubt(client):
    """Der regulaere, CSRF-geschuetzte Logout funktioniert weiter."""
    from diakronos_app.frappe_compat import sitzungen

    sid, csrf = sitzungen.anlegen("Administrator")
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf

    r = client.post("/api/method/logout")
    assert r.status_code == 200
    assert sitzungen.lesen(sid) is None


def test_logout_ohne_sitzung_bleibt_noop(guest_client):
    """Ohne Sitzung ist ein Logout ein wirkungsloser No-op (kein 417).

    Der Schutz darf den Fall „niemand ist angemeldet" nicht bestrafen.
    """
    r = guest_client.post("/api/method/logout")
    assert r.status_code == 200


def test_lege_logout_route_verlangt_csrf(client):
    """Auch die neue OIDC-Logout-Route `/logout` verlangt den CSRF-Token."""
    from diakronos_app.frappe_compat import sitzungen

    sid, _csrf = sitzungen.anlegen("Administrator")
    client.headers.pop("x-frappe-csrf-token", None)
    client.cookies.set("sid", sid)

    r = client.post("/logout")
    assert r.status_code == 417
    assert sitzungen.lesen(sid) is not None


def test_get_logout_existiert_nicht_mehr(client):
    """`GET /logout` ist entfernt — der Forced-Logout-per-Bild-Vektor.

    Ein GET darf die Sitzung nicht beenden, weil ihn jede fremde Seite per
    `<img src="/logout">` ausloesen kann.
    """
    from diakronos_app.frappe_compat import sitzungen

    sid, _csrf = sitzungen.anlegen("Administrator")
    client.cookies.set("sid", sid)
    r = client.get("/logout")
    # 405 (Methode nicht erlaubt) oder 404 (Route weg) — NICHT 303/200.
    assert r.status_code in (404, 405)
    # Die Sitzung lebt.
    assert sitzungen.lesen(sid) is not None


# ── 3. azp bei Mehrfach-aud ─────────────────────────────────────────────────


def test_azp_bei_mehrfach_aud_wird_geprueft():
    """Ein Token mit mehreren `aud`-Werten verlangt `azp == client_id`.

    Ohne diese Pruefung koennte ein Token, das fuer einen anderen Client mit
    demselben Publikumskreis ausgestellt wurde, durchgehen. Getestet wird die
    `pruefe_id_token`-Logik isoliert: das JWKS liefert den echten
    Anbieter-Schluessel, das Token traegt eine `aud`-Liste.
    """
    import time

    import pytest
    from authlib.jose import JsonWebKey, jwt as jose_jwt

    from diakronos_app.anmeldung import oidc
    from diakronos_app.anmeldung.konfiguration import OidcKonfiguration

    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    cfg = OidcKonfiguration(
        issuer="https://anbieter.test", client_id="diakronos-test",
        client_secret="x", scopes=("openid",), redirect_url="https://app/cb",
        logout=False, anbietername="T", metadata_ttl=0, leeway=30,
        local_login="an",
    )
    meta = oidc.OidcMetadaten(
        issuer="https://anbieter.test",
        authorization_endpoint="https://anbieter.test/auth",
        token_endpoint="https://anbieter.test/token",
        jwks_uri="https://anbieter.test/jwks",
        end_session_endpoint=None,
        id_token_signing_alg_values_supported=("RS256",),
    )

    def _token(azp):
        claims = {
            "iss": "https://anbieter.test",
            "aud": ["diakronos-test", "fremder-client"],
            "azp": azp,
            "sub": "s", "exp": int(time.time()) + 300, "nonce": "n",
        }
        return jose_jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key).decode()

    import pytest

    # JWKS des Anbieters durch den Test-Schluessel ersetzen.
    original = oidc._hole_jwks
    oidc._hole_jwks = lambda _meta: {"keys": [key.as_dict(is_private=False)]}
    try:
        # Falscher azp -> Ablehnung.
        with pytest.raises(oidc.OidcFehler):
            oidc.pruefe_id_token(cfg, meta, _token("fremder-client"), nonce="n")
        # Korrekter azp -> akzeptiert.
        claims = oidc.pruefe_id_token(cfg, meta, _token("diakronos-test"), nonce="n")
        assert claims["sub"] == "s"
    finally:
        oidc._hole_jwks = original
