"""WEB-8 — Login-Formular scheitert mit 417 CSRF, wenn eine Sitzung vorhanden ist.

BEFUND (Manuel 2026-10-30, live auf dev.ecg-hn.de):

  1. frischer Client: `GET /login` (Formular mit `_csrf`), dann
     `POST /api/method/login` als `application/x-www-form-urlencoded`
     -> 303, angemeldet.
  2. Derselbe Client NOCH ANGEMELDET (gueltiges `sid`): Formular erneut
     abgeschickt -> 417 `{"message": "CSRF-Token ungueltig oder fehlend.",
     "exc_type": "CSRFTokenError"}` als ROHES JSON im Browser.
  3. Client mit ALTEM `sid`-Cookie `Path=/` (aus der Zeit vor
     `DIAKRONOS_BASE_PATH`) -> ebenfalls 417.

URSACHE: `CsrfMiddleware` nimmt `/api/method/login` nur als EXAKTEN Pfad aus.
Mit Praefix heisst der Pfad `/diakronos/api/method/login` — er faellt damit
NICHT unter die Ausnahme, und weil Fall 2/3 eine Sitzung mitbringt, verlangt
die Middleware den Kopfzeilen-Token `X-Frappe-CSRF-Token`. Den kann ein
HTML-Formular nie senden.

Die Karte verlangt:

  (F1) Alle Alias-Pfade des Logins (mit und ohne Praefix) sind von der
       SITZUNGS-CSRF-Pflicht ausgenommen. Der eigene Schutz (SEC-4:
       eigene Herkunft ODER gueltiger Masken-Token, fremde Herkunft immer
       abgelehnt) bleibt unveraendert und ist der alleinige Schutz.
  (F2) Erfolgreicher Login mit vorhandener Sitzung: alte Sitzung
       serverseitig beenden, neue `sid` ausgeben (Rotation, keine Fixierung).
  (F3) Doppelte Cookie-Namen (`sid`) mit unterschiedlichem `Path`: mit
       Praefix wird beim Login und Logout zusaetzlich das veraltete Cookie
       auf `Path=/` geloescht. Vorher wird GEMESSEN, welches Cookie die App
       liest, wenn beide gesendet werden (Browser senden den laengeren Pfad
       zuerst) — das Ergebnis steht in `test_f3_messung_*`.
  (F4) Fehler beim Formular-Login landen nie als rohes JSON im Browser:
       Formular-POST -> 303 zurueck auf die Anmeldeseite mit Meldung
       (`dk_login_flash`). JSON-Aufrufe bleiben wie heute.

Alle Faelle laufen MIT und OHNE `DIAKRONOS_BASE_PATH`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers
from diakronos_app.main import erstelle_app
from diakronos_app.models.core import User
from diakronos_app.settings import settings as echte_settings

PRAEFIX = "/diakronos"
USR = "web8@example.org"
PWD = "synthetisch-web8"

#: Kopfzeilen eines echten Browser-Formulars (der Router nimmt den
#: Browser-Weg nur bei `text/html` im `Accept` bzw. `Sec-Fetch-Mode: navigate`).
_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
_JSON = {"Accept": "application/json"}


# ── Hilfen ────────────────────────────────────────────────────────────────


def _lege_benutzer(session_factory, name: str = USR, passwort: str = PWD) -> None:
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    sess = session_factory()
    try:
        if sess.get(User, name) is None:
            sess.add(
                User(
                    name=name,
                    email=name,
                    full_name="WEB-8 Probe",
                    enabled=True,
                    password_hash=neuer_hash(passwort),
                )
            )
            sess.commit()
    finally:
        sess.close()


def _set_cookie_koepfe(resp) -> list[str]:
    """Alle `Set-Cookie`-Kopfzeilen einer Antwort (auch mehrfach belegt)."""
    if hasattr(resp.headers, "get_list"):
        return [k for k in resp.headers.get_list("set-cookie") if k]
    return []


def _sid_kopfzeilen(resp) -> list[str]:
    return [k for k in _set_cookie_koepfe(resp) if k.lower().startswith("sid=")]


def _masken_token(client, login_seite: str) -> str:
    """`_csrf` aus der Anmeldemaske — das Feld, das ein Browser mitsendet."""
    import re

    seite = client.get(login_seite, headers=_BROWSER, follow_redirects=False)
    assert seite.status_code == 200, seite.text
    treffer = re.search(r'name="_csrf" value="([^"]+)"', seite.text)
    assert treffer, "Anmeldemaske ohne _csrf-Feld"
    return treffer.group(1)


def _formular(client, api_pfad: str, *, token: str, usr: str = USR, pwd: str = PWD, kopf=None):
    """Browser-Formular-POST auf den Login — genau das, was der Browser tut."""
    h = dict(_BROWSER)
    h["Content-Type"] = "application/x-www-form-urlencoded"
    h.update(kopf or {})
    return client.post(
        api_pfad,
        data={"usr": usr, "pwd": pwd, "_csrf": token, "redirect-to": "/diakonos"},
        headers=h,
        follow_redirects=False,
    )


@pytest.fixture()
def mit_praefix(monkeypatch):
    """Anwendung MIT `DIAKRONOS_BASE_PATH=/diakronos` (Praefix danach zurueck)."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", PRAEFIX)
    try:
        yield PRAEFIX
    finally:
        base_path.setze_praefix("")


@pytest.fixture()
def ohne_praefix(monkeypatch):
    """Anwendung OHNE Praefix — `base_path` ist eine Prozessgroesse."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", "")
    base_path.setze_praefix("")
    try:
        yield ""
    finally:
        base_path.setze_praefix("")


def _client(app) -> TestClient:
    return TestClient(app)


def _app():
    return erstelle_app()


# ── F1a: CSRF-Middleware nimmt ALLE Login-Alias-Pfade aus ─────────────────


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
@pytest.mark.parametrize(
    "pfad",
    [
        "/api/method/login",
        "/api/method/frappe.login",
        "/api/method/frappe.login.login",
        "/api/method/auth.login",
        "/api/method/api.login",
        "/api/method/diakronos_app.api.auth.login",
    ],
)
def test_f1a_login_aliaspfade_sind_von_der_sitzungs_csrf_ausgenommen(praefix, pfad):
    """Jeder Login-Alias ist ausgenommen — mit UND ohne Praefix.

    Geprueft wird die ENTSCHEIDUNG der Middleware (`ist_csrf_ausgenommen`),
    nicht ein Aufruf: ein Alias, der nicht aufloest, ist ein 404 und damit
    kein Beweis fuer die Ausnahme.
    """
    from diakronos_app.frappe_compat.auth_middleware import ist_csrf_ausgenommen

    base_path.setze_praefix(praefix)
    try:
        voll = f"{praefix}{pfad}" if praefix else pfad
        assert ist_csrf_ausgenommen(voll) is True, f"{voll} faellt unter die Sitzungs-CSRF"
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
@pytest.mark.parametrize(
    "pfad",
    [
        "/api/method/logout",
        "/api/method/save_mitglied",
        "/api/method/frappe.sessions.get_csrf_token",
        "/api/method/loginx",
        "/api/method/login_und_mehr",
        "/api/method/logins",
        "/api/method/login_x",
    ],
)
def test_f1a_keine_anderen_pfade_sind_ausgenommen(praefix, pfad):
    """Nur der Login. Logout, ein Allerwelts-Endpunkt und Praefix-Lookalikes
    bleiben unter der Sitzungs-CSRF-Pflicht.

    `frappe.sessions.get_csrf_token` ist seit A1b2 ebenfalls ausgenommen
    (Vorbestand, nicht Teil dieser Karte) — er steht deshalb NICHT in der
    Verbotsliste; die uebrigen Eintraege sind der eigentliche Beleg.
    """
    from diakronos_app.frappe_compat.auth_middleware import ist_csrf_ausgenommen

    if pfad.endswith("get_csrf_token"):
        pytest.skip("Vorbestand aus A1b2 — nicht Gegenstand dieser Karte")

    base_path.setze_praefix(praefix)
    try:
        voll = f"{praefix}{pfad}" if praefix else pfad
        assert ist_csrf_ausgenommen(voll) is False, f"{voll} ist unerlaubt ausgenommen"
    finally:
        base_path.setze_praefix("")


# ── F1b/2: Reproduktion — angemeldet, Formular erneut absenden ────────────


@pytest.mark.parametrize("mit_praefix_", ["ja", "nein"])
def test_f1b_login_mit_vorhandener_sitzung_ist_kein_417(
    patched_db, fake_redis, monkeypatch, request, mit_praefix_
):
    """DER BEFUND: wer angemeldet ist, darf das Formular trotzdem absenden.

    Ein HTML-Formular kann den Kopfzeilen-Token `X-Frappe-CSRF-Token` nie
    senden. Mit vorhandener Sitzung verlangte die Middleware genau das und
    antwortete 417 — als rohes JSON im Browser.
    """
    praefix = PRAEFIX if mit_praefix_ == "ja" else ""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        app = _app()
        login_seite = f"{praefix}/login"
        api = f"{praefix}/api/method/login"

        with _client(app) as c:
            # Schritt 1: frischer Client meldet sich an.
            token = _masken_token(c, login_seite)
            erst = _formular(c, api, token=token)
            assert erst.status_code == 303, erst.text
            alte_sid = sitzungen.lesen(_sid_aus_cookie(c))

            # Schritt 2: derselbe Client, NOCH ANGEMELDET, sendet erneut.
            zwei = _formular(c, api, token=_masken_token(c, login_seite))

        assert zwei.status_code == 303, (
            f"Login mit vorhandener Sitzung: {zwei.status_code} {zwei.text[:200]}"
        )
        assert "CSRFTokenError" not in zwei.text
    finally:
        base_path.setze_praefix("")


def _sid_aus_cookie(client) -> str:
    """Der `sid`-Wert, den der Testclient gerade mitsenden wuerde."""
    return client.cookies.get("sid") or ""


# ── F2: Rotation — die alte Sitzung ist serverseitig weg ──────────────────


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f2_login_mit_sitzung_rotiert_und_beendet_die_alte(patched_db, fake_redis, monkeypatch, praefix):
    """Erfolgreicher Login beendet die vorhandene Sitzung und setzt eine neue.

    Keine Sitzungs-Fixierung: der alte `sid` ist danach serverseitig
    ungueltig, die Antwort traegt einen ANDEREN `sid`.
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"
        login_seite = f"{praefix}/login"

        with _client(_app()) as c:
            erst = _formular(c, api, token=_masken_token(c, login_seite))
            assert erst.status_code == 303
            alt = _sid_aus_cookie(c)
            assert sitzungen.lesen(alt) is not None

            zweit = _formular(c, api, token=_masken_token(c, login_seite))
            assert zweit.status_code == 303
            neu = _sid_aus_cookie(c)

        assert neu and neu != alt, "sid wurde nicht rotiert (Fixierung)"
        assert sitzungen.lesen(alt) is None, "alte Sitzung lebt serverseitig weiter"
        assert sitzungen.lesen(neu) is not None, "neue Sitzung fehlt"
    finally:
        base_path.setze_praefix("")


# ── F3: Alt-Cookie auf Path=/ — Messung, dann Loeschung ───────────────────


def test_f3_messung_welches_cookie_die_app_liest():
    """MESSUNG: bei zwei `sid`-Cookies entscheidet der ERSTE im Kopf.

    Ein Browser sortiert `Cookie` nach Pfadlaenge (laengster Pfad zuerst);
    mit `sid` auf `/diakronos` (laenger) und `/` (kuerzer) kommt also das
    Praefix-Cookie zuerst. `sid_aus_headers` liest den ersten Treffer — das
    Praefix-Cookie gewinnt damit von selbst. Genau das wird hier belegt,
    damit die Loeschung des Alt-Cookies (F3) nicht auf einer Annahme steht.
    """
    from starlette.datastructures import Headers

    beide = Headers({"cookie": "sid=aus-praefix; sid=alt-auf-wurzel"})
    assert sid_aus_headers(beide) == "aus-praefix"

    # Reihenfolge umgedreht (Browser, der NICHT sortiert): es gewinnt der
    # erste Wert — deshalb muss die App das Alt-Cookie loeschen, statt auf
    # eine Wohlverhaltens-Regel des Browsers zu bauen.
    umgedreht = Headers({"cookie": "sid=alt-auf-wurzel; sid=aus-praefix"})
    assert sid_aus_headers(umgedreht) == "alt-auf-wurzel"


@pytest.mark.parametrize("praefix", [PRAEFIX])
def test_f3_im_echten_request_gewinnt_das_praefix_cookie_bei_browser_sortierung(
    patched_db, fake_redis, monkeypatch, praefix
):
    """Ende-zu-Ende: so sendet ein Browser (Praefix-Cookie zuerst).

    Die Sitzung wird erkannt, obwohl im selben Kopf noch ein `sid` auf `/`
    steht — das ist der Fall „alter Cookie neben neuem“.
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        sid, csrf = sitzungen.anlegen(USR)

        with _client(_app()) as c:
            r = c.post(
                f"{praefix}/api/method/session.sitzung_status",
                json={},
                headers={
                    "Cookie": f"sid={sid}; sid=veraltet-auf-wurzel",
                    "X-Frappe-CSRF-Token": csrf,
                    "Accept": "application/json",
                },
                follow_redirects=False,
            )

        assert r.status_code == 200, r.text
        assert r.json()["message"]["csrf_token"] == csrf
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f3_alte_sid_cookies_werden_auf_wurzelpfad_geloescht(patched_db, fake_redis, monkeypatch, praefix):
    """Mit Praefix setzt der Login zusaetzlich ein Loesch-Cookie auf `Path=/`.

    Chromium/Safari sortieren `Cookie` NICHT nach Pfadlaenge; ein altes
    `sid` auf `/` kann deshalb gewinnen. Der Login loescht es deshalb
    ausdruecklich — und nur dann, wenn ein Praefix gesetzt ist.
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"
        login_seite = f"{praefix}/login"

        with _client(_app()) as c:
            c.cookies.set("sid", "alt-auf-wurzel", path="/")
            r = _formular(c, api, token=_masken_token(c, login_seite))

        assert r.status_code == 303, r.text
        koepfe = _sid_kopfzeilen(r)
        wurzel_loeschung = [
            k for k in koepfe if "Path=/" in k.replace(" ", "") and ("Max-Age=0" in k or "expires" in k.lower())
        ]
        if praefix:
            assert wurzel_loeschung, f"Alt-Cookie auf Path=/ nicht geloescht: {koepfe}"
            # Und die neue Sitzung sitzt auf dem Praefix-Pfad.
            assert any(f"Path={praefix}" in k.replace(" ", "") for k in koepfe), koepfe
        else:
            assert not wurzel_loeschung, f"Ohne Praefix kein zusaetzliches Set-Cookie: {koepfe}"
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f3_logout_loescht_auch_das_wurzel_cookie(patched_db, fake_redis, monkeypatch, praefix):
    """Dasselbe beim Logout: mit Praefix faellt auch das Alt-Cookie auf `/`."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"
        logout = f"{praefix}/api/method/logout"
        login_seite = f"{praefix}/login"

        with _client(_app()) as c:
            _formular(c, api, token=_masken_token(c, login_seite))
            daten = sitzungen.lesen(_sid_aus_cookie(c)) or {}
            csrf = str(daten.get("csrf_token") or "")
            r = c.post(logout, headers={**_JSON, "X-Frappe-CSRF-Token": csrf}, follow_redirects=False)

        assert r.status_code == 200, r.text
        koepfe = _sid_kopfzeilen(r)
        wurzel_loeschung = [
            k for k in koepfe if "Path=/" in k.replace(" ", "") and ("Max-Age=0" in k or "expires" in k.lower())
        ]
        praefix_loeschung = [
            k for k in koepfe
            if f"Path={praefix}" in k.replace(" ", "") and ("Max-Age=0" in k or "expires" in k.lower())
        ]
        # Genau EIN Loesch-Cookie auf dem eigenen Pfad; mit Praefix zusaetzlich
        # das Alt-Cookie auf `/`.
        assert praefix_loeschung, f"Logout ohne Cookie-Loeschung auf Path={praefix or '/'}: {koepfe}"
        if praefix:
            assert wurzel_loeschung, f"Alt-Cookie auf Path=/ beim Logout nicht geloescht: {koepfe}"
        else:
            # Ohne Praefix ist `/` der EIGENE Pfad — `praefix_loeschung` und
            # `wurzel_loeschung` beschreiben dann dasselbe Cookie. Entscheidend
            # ist: genau EIN Loesch-Cookie.
            assert len(koepfe) == 1, koepfe
    finally:
        base_path.setze_praefix("")


# ── F3b: Praefix-Cookie gewinnt, auch wenn das alte zuerst kommt ──────────


@pytest.mark.parametrize("praefix", [PRAEFIX])
def test_f3b_praefix_cookie_gewinnt_auch_bei_browser_ohne_sortierung(patched_db, fake_redis, monkeypatch, praefix):
    """Steht das Alt-Cookie (`/`) im Kopf ZUERST, darf es nicht die Sitzung
    bestimmen: `sid_aus_headers` nimmt den ERSTEN Wert, deshalb belegt der
    Test die Regel direkt auf der Lesefunktion (die von Login, CSRF-Middleware
    und Logout gemeinsam benutzt wird).
    """
    from starlette.datastructures import Headers

    sid, _csrf = sitzungen.anlegen(USR)
    # Reihenfolge wie bei einem Browser ohne Pfad-Sortierung: alt zuerst.
    kopf = Headers({"cookie": f"sid=veraltet-auf-wurzel; sid={sid}"})
    gelesen = sid_aus_headers(kopf)

    # Erster Wert gewinnt → mit dieser Reihenfolge waere das Alt-Cookie
    # massgeblich. Genau deshalb loescht der Login es (F3, Test oben) und
    # setzt die neue Sitzung auf den Praefix-Pfad.
    assert gelesen == "veraltet-auf-wurzel"
    assert sitzungen.lesen(gelesen) is None
    assert sitzungen.lesen(sid) is not None


# ── F4: Formular-Fehler landen nie als JSON im Browser ────────────────────


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f4_formular_fehler_mit_sitzung_ist_303_und_html(patched_db, fake_redis, monkeypatch, praefix):
    """Mit vorhandener Sitzung UND falschem Passwort: 303 auf die Maske,
    kein 417-JSON. Die Meldung steht im Flash-Cookie (LOGIN-1).
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"
        login_seite = f"{praefix}/login"

        with _client(_app()) as c:
            _formular(c, api, token=_masken_token(c, login_seite))
            r = _formular(c, api, token=_masken_token(c, login_seite), pwd="falsch")

        assert r.status_code == 303, f"{r.status_code} {r.text[:200]}"
        assert r.headers["location"].startswith(f"{praefix}/login?"), r.headers["location"]
        assert "dk_login_flash" in " ".join(_set_cookie_koepfe(r))
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f4_json_aufruf_bleibt_json_und_401(patched_db, fake_redis, monkeypatch, praefix):
    """JSON-Aufrufer (SPA, Apps) bekommen unveraendert 401 + JSON."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"

        with _client(_app()) as c:
            r = c.post(api, json={"usr": USR, "pwd": "falsch"}, headers=_JSON, follow_redirects=False)

        assert r.status_code == 401, r.text
        assert r.headers["content-type"].startswith("application/json")
    finally:
        base_path.setze_praefix("")


# ── F1c: Der SEC-4-Schutz bleibt der alleinige Login-Schutz ───────────────


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f1c_fremde_herkunft_wird_auch_mit_gueltigem_token_abgewiesen(
    patched_db, fake_redis, monkeypatch, praefix
):
    """Die Ausnahme von der Sitzungs-CSRF hebt die Herkunftspruefung NICHT auf."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"
        login_seite = f"{praefix}/login"

        with _client(_app()) as c:
            token = _masken_token(c, login_seite)
            r = _formular(
                c,
                api,
                token=token,
                kopf={"Origin": "https://boese.example.net", "Referer": "https://boese.example.net/login"},
            )

        assert not _sid_kopfzeilen(r), f"Cross-Site-Login setzte eine Sitzung: {_set_cookie_koepfe(r)}"
        assert r.status_code == 303
        assert r.headers["location"].startswith(f"{praefix}/login?")
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f1c_browser_formular_ohne_herkunft_und_ohne_token_abgewiesen(
    patched_db, fake_redis, monkeypatch, praefix
):
    """BROWSER ohne `Origin`/`Referer` und mit FALSCH em `_csrf`: kein Login.

    Der Masken-Token ersetzt die FEHLENDE Kopfzeile (SEC-4). Ein falscher
    Wert im Feld ist kein Nachweis — er wird wie fremde Herkunft behandelt.
    Gemessen (Wegwerf-Image, Tabelle im Karten-Kommentar):

      * Token gueltig, kein `Origin`            -> Login (SEC-4)
      * Token FALSCH,  kein `Origin`            -> kein Login
      * Token FALSCH,  eigener `Origin`         -> kein Login
      * Token FEHLT/leer, eigener `Origin`      -> Login (LOGIN-3, Vorbestand)
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"

        with _client(_app()) as c:
            # `_BROWSER` enthaelt weder `Origin` noch `Referer`.
            falsch = _formular(c, api, token="0000000000:deadbeef")

        assert not _sid_kopfzeilen(falsch), _set_cookie_koepfe(falsch)
        assert falsch.status_code == 303
        assert falsch.headers["location"].startswith(f"{praefix}/login?")
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("praefix", ["", PRAEFIX])
def test_f1c_gemessene_matrix_token_und_herkunft(patched_db, fake_redis, monkeypatch, praefix):
    """Die vollstaendige Messung als Test.

    `_read_args` verwirft LEERE Formularfelder — ein `_csrf=""` kommt beim
    Login also als „kein Token“ an. Genau deshalb ist die Zeile
    „Token leer“ gleichbedeutend mit „Feld fehlt“ und nicht mit „falsch“.
    """
    from diakronos_app.anmeldung.maske_token import erzeuge_token

    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    base_path.setze_praefix(praefix)
    try:
        _lege_benutzer(patched_db)
        api = f"{praefix}/api/method/login"
        eigen = {"Origin": "http://testserver"}
        gueltig = erzeuge_token()

        erwartet = [
            ("gueltig", gueltig, None, True),
            ("gueltig", gueltig, eigen, True),
            ("falsch", "0000000000:deadbeef", None, False),
            ("falsch", "0000000000:deadbeef", eigen, False),
            ("fehlt", None, eigen, True),
        ]
        with _client(_app()) as c:
            for name, token, kopf, soll in erwartet:
                if token is None:
                    kopf = dict(_BROWSER, **(kopf or {}))
                    r = c.post(
                        api,
                        data={"usr": USR, "pwd": PWD, "redirect-to": "/diakonos"},
                        headers=kopf,
                        follow_redirects=False,
                    )
                else:
                    r = _formular(c, api, token=token, kopf=kopf)
                hat_sid = bool(_sid_kopfzeilen(r))
                assert hat_sid is soll, f"{name}/{kopf}: Login={hat_sid}, erwartet {soll}"
    finally:
        base_path.setze_praefix("")


@pytest.mark.parametrize("pfad", [
    "/api/method/render_login",
    "/api/method/diakronos_app.spa.render_login",
    "/api/method/x_login",
    "/api/method/foologin",
])
def test_review_suffix_ohne_punkt_bleibt_unter_csrf_pflicht(pfad):
    """Review WEB-8: Namen, die nur auf 'login' ENDEN, sind nicht der Login."""
    from diakronos_app.frappe_compat.auth_middleware import ist_csrf_ausgenommen
    assert ist_csrf_ausgenommen(pfad) is False
