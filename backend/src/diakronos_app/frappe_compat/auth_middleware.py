"""Sitzungs- und CSRF-Middleware — Karte A1b2 (die Umschaltung).

Vorher war jeder Aufruf Administrator (`session.DEFAULT_USER`). Nach dieser
Karte ist ein Aufruf ohne gueltige Sitzung `Guest` und laeuft in die
fail-closed-Permission-Pruefung.

Drei Aufgaben, in dieser Reihenfolge pro Request:

1. **Sitzung**: `sid`-Cookie lesen -> `sitzungen.lesen()` -> pruefen, dass der
   Benutzer existiert und `enabled` ist (`benutzer_status.ist_aktiv`, Karte
   B1) -> `session.user` setzen und die TTL verlaengern (gleitende Sitzung).
   Kein/unbekanntes Cookie -> `Guest`. Eine Sitzung, die einem nicht mehr
   aktiven Konto gehoert, wird dabei serverseitig geloescht (s. Docstring
   von `SessionMiddleware`).
2. **CSRF**: nur bei schreibenden Methoden (POST/PUT/PATCH/DELETE) und nur,
   wenn eine Sitzung existiert. `X-Frappe-CSRF-Token` wird per
   `hmac.compare_digest` gegen `sitzung.csrf_token` verglichen. Mismatch ->
   `CSRFTokenError` (HTTP 417, eigener `exc_type` — sonst waere die Ablehnung
   nicht von der Argumentpruefung zu unterscheiden, siehe Karten-Kommentar).
   `/api/method/login` ist ausgenommen: dort gibt es noch keine Sitzung.
3. Der Benutzer wird im `finally` wieder auf `Guest` zurueckgesetzt, damit
   kein Zustand zwischen Requests leckt (ContextVar + BaseHTTPMiddleware).

Warum Middleware und kein Dependency: die portierten Fachfunktionen
(`get_accessible_calendars`, `check_permission`, ...) sind synchron und lesen
`frappe_compat.session.session.user` direkt. Sie koennen keinen Request
entgegennehmen — genau wie beim `request_context`. Also dasselbe Muster.
"""

from __future__ import annotations

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from diakronos_app.frappe_compat import benutzer_status, sitzungen
from diakronos_app.frappe_compat.session import GUEST, session, user_uebersteuert

logger = logging.getLogger("diakronos_app.auth")

__all__ = [
    "COOKIE_NAME",
    "CSRF_HEADER",
    "SessionMiddleware",
    "CsrfMiddleware",
    "ist_csrf_ausgenommen",
    "sid_aus_headers",
]

# Frappe nennt das Session-Cookie `sid` (identisch zu api/auth.py).
COOKIE_NAME = "sid"

# Header, den die SPA aus `boot.csrf_token` befuellt (useApi.js:18/28).
CSRF_HEADER = "x-frappe-csrf-token"

# ── WEB-8: Der Login ist in JEDER Schreibweise ausgenommen ────────────────
#
# Bis WEB-8 stand hier eine Menge EXAKTER Pfade. Mit `DIAKRONOS_BASE_PATH`
# heisst der Login aber `/diakronos/api/method/login` — und damit fiel er
# NICHT mehr unter die Ausnahme. Weil jeder Alias (`auth.login`,
# `frappe.login`, `api.login`, `frappe.login.login`, …) ein eigener Pfad ist,
# waere auch eine laengere Liste unvollstaendig gewesen.
#
# Die Folge war der Befund vom 2026-10-30: wer noch angemeldet war und das
# Anmeldeformular erneut absandte, bekam 417 `CSRFTokenError` als rohes JSON
# im Browser — die Middleware verlangte den Kopfzeilen-Token, den ein
# HTML-Formular nie senden kann. Der Login hat seinen EIGENEN CSRF-Schutz
# (SEC-4: eigene Herkunft ODER gueltiger Masken-Token `_csrf`, fremde
# Herkunft immer abgelehnt) — der bleibt unveraendert und ist der alleinige
# Schutz dieses Endpunkts.
#
# Erkannt wird der Login deshalb am LETZTEN Namenssegment und an der erlaubten
# Endung: `…/api/method/<name>`, wobei `<name>` `login` oder auf `x.login`
# endet, dazu die Schreibweise ohne `api/method` (`/login`, `/diakronos/login`).
# Dadurch fallen `/api/method/loginx`, `/api/method/login_und_mehr` und
# `/api/method/logout` NICHT darunter (siehe `test_web8_login_csrf.py`).
_CSRF_METHODEN_PRAEFIX = "/api/method/"
_LOGIN_ENDER = ("login", ".login")

#: Ausser dem Login: die Token-Ausgabe der Sitzung (Vorbestand aus A1b2).
_WEITERE_AUSNAHMEN = frozenset({"/api/method/frappe.sessions.get_csrf_token"})


def _mit_praefix_entfernt(pfad: str) -> str:
    """Entfernt den aktiven Betriebs-Praefix (`/diakronos/api/…` -> `/api/…`)."""
    from diakronos_app import base_path

    praefix = base_path.aktiver_praefix()
    if praefix and (pfad == praefix or pfad.startswith(praefix + "/")):
        return pfad[len(praefix):] or "/"
    return pfad


def ist_csrf_ausgenommen(pfad: str) -> bool:
    """True, wenn dieser Pfad NICHT unter die Sitzungs-CSRF-Pflicht faellt.

    WEB-8: Der Login ist in jeder Schreibweise und mit jedem Praefix
    ausgenommen — er bringt seinen eigenen Schutz mit (SEC-4). Alles andere
    bleibt unter der Pflicht; die Ausnahme ist absichtlich eng und wird im
    Test `test_web8_login_csrf.py` in beide Richtungen belegt.
    """
    pfad = _mit_praefix_entfernt(str(pfad or "").rstrip("/") or "/")
    if pfad in _WEITERE_AUSNAHMEN:
        return True
    if pfad.startswith(_CSRF_METHODEN_PRAEFIX):
        # Nur das LETZTE Segment zaehlt: `auth.login` ist der Login,
        # `login_und_mehr` nicht.
        name = pfad[len(_CSRF_METHODEN_PRAEFIX):]
        # Grenze am Punkt (Review WEB-8): nur "login" selbst oder ein voll
        # qualifizierter Name, der auf ".login" endet — NICHT "irgendwas_login".
        return name == "login" or name.endswith(".login")
    # Formular-Adresse der Anmeldemaske (`/login`, mit Praefix `/diakronos/login`).
    return pfad == "/login"



_SCHREIBENDE_METHODEN = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def sid_aus_headers(headers) -> str | None:
    """Liest `sid` aus dem `Cookie`-Kopfzeilenwert (auch mehrfach belegt)."""
    for header in headers.getlist("cookie") or []:
        for teil in header.split(";"):
            name, _, wert = teil.strip().partition("=")
            if name == COOKIE_NAME and wert:
                return wert
    return None


class SessionMiddleware(BaseHTTPMiddleware):
    """Setzt `session.user` aus dem `sid`-Cookie. Ohne Sitzung: `Guest`.

    Eine per `session.set_user()` explizit gesetzte Identitaet (Test-Naht,
    siehe `frappe_compat/session.py`) wird respektiert und NICHT ueberschrieben.

    B1 — DIE ZWEITE HAELFTE DER SITZUNGSPRUEFUNG
    ------------------------------------------
    Ein `sid` im Cookie beweist nur, dass es einmal einen gab. Er beweist
    **nicht**, dass der Benutzer heute noch existiert und noch `enabled` ist.
    Bis B1 wurde der Name ungeprueft in `session.user` uebernommen: ein
    deaktivierter oder aus der Datenbank geloeschter Benutzer blieb so lange
    angemeldet, wie seine Sitzung im Redis lag — auf jedem Geraet, ohne dass
    irgendetwas davon sichtbar gewesen waere. Die Regel steht jetzt in
    `frappe_compat/benutzer_status.py` und wird **hier** angewandt:

      * `ist_aktiv(name)` == False (deaktiviert, geloescht, DB nicht
        erreichbar) -> `sitzungen.loeschen(sid)`, `session.user = Guest`.
        Die Sitzung wird damit **serverseitig** ungueltig, nicht nur fuer
        diesen Request ignoriert: das Cookie bleibt zwar im Browser, zeigt
        aber beim naechsten Mal ins Leere.
      * `ist_aktiv(name)` == True -> wie bisher, Sitzung normal genutzt.

    Warum hier und nicht in `sitzungen.lesen()`: der Store ist laut eigenem
    Docstring "reine Datenschicht" und darf nicht entscheiden, wer
    eingeloggt ist. Ausserdem braucht `CsrfMiddleware` die Sitzung auch
    fuer eine **verworfene** — sie soll nicht an einem Benutzer scheitern,
    den es nicht mehr gibt, sondern schlicht kein Token mehr pruefen.

    Die Kosten dieser Pruefung stehen in `benutzer_status.py`: sie ist
    ein Redis-`GET` (0,130 ms gemessen) und nur alle
    `settings.benutzerstatus_ttl` Sekunden (Default 30) ein DB-Lookup
    (0,407 ms). Der aktive Widerruf (`delete_my_data`) kommt ohne diese
    Frist aus, weil er den Cache selbst loescht.
    """

    async def dispatch(self, request: Request, call_next):
        if user_uebersteuert():
            # Test-Schalter aktiv: die Identitaet kommt aus dem Prozess, nicht
            # aus dem Cookie. Produktionscode ruft `set_user()` nie auf.
            return await call_next(request)
        sid = sid_aus_headers(request.headers)
        daten = sitzungen.lesen(sid) if sid else None
        from diakronos_app.anmeldung.passwortzugang import wechsel_noetig_gecacht
        if (daten and daten.get("user") and benutzer_status.ist_aktiv(str(daten["user"]))
                and (daten.get("sso") is True or not wechsel_noetig_gecacht(str(daten["user"])))):
            sitzungen.verlaengern(sid)
            session.user = str(daten["user"])
        else:
            if daten and daten.get("user") and sid:
                # B1: Die Sitzung gehoert einem Benutzer, den es nicht (mehr)
                # gibt. Sie wird hier serverseitig geloescht — nicht nur fuer
                # diesen Aufruf ausser Kraft gesetzt. Grund: ein Cookie, das
                # zwar nichts mehr kann, aber liegen bleibt, ist der Grund
                # dafuer, dass die Loeschung in einem spaeteren Lauf wie eine
                # halbe Massnahme aussieht.
                logger.info(
                    "Sitzung eines nicht mehr aktiven Kontos verworfen (Kuerzel %s).",
                    benutzer_status._pseudonym(str(daten["user"])),
                )
                sitzungen.loeschen(sid)
            session.user = GUEST
        try:
            return await call_next(request)
        finally:
            # Kein Leck zwischen Requests (ContextVar in einem Worker).
            session.user = GUEST


class CsrfMiddleware(BaseHTTPMiddleware):
    """Synchronizer-Token-Pruefung fuer schreibende Methoden.

    Die SPA sendet KEIN CSRF-Cookie, nur den Header `X-Frappe-CSRF-Token` aus
    dem Boot-Objekt. Deshalb liegt der Token in der Server-Sitzung (Redis) und
    wird hier verglichen — kein Double-Submit-Cookie.

    Abgelehnt wird mit `CSRFTokenError` (HTTP 417, eigener `exc_type`): eine
    Ablehnung mit nur dem Statuscode 417 waere nicht von einer
    Argumentpruefung (`ValidationError`, ebenfalls 417) zu unterscheiden.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in _SCHREIBENDE_METHODEN:
            pfad = request.url.path.rstrip("/") or "/"
            if not ist_csrf_ausgenommen(pfad):
                sid = sid_aus_headers(request.headers)
                daten = sitzungen.lesen(sid) if sid else None
                if daten is not None:
                    # Nur pruefen, wenn es ueberhaupt eine Sitzung gibt.
                    erwartet = str(daten.get("csrf_token") or "")
                    geliefert = request.headers.get(CSRF_HEADER, "")
                    if not erwartet or not hmac.compare_digest(erwartet, geliefert):
                        return _csrf_ablehnung()
        return await call_next(request)


def _csrf_ablehnung() -> Response:
    """Frappe-konforme CSRF-Ablehnung: 417 + `exc_type=CSRFTokenError`."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=417,
        content={
            "message": "CSRF-Token ungueltig oder fehlend.",
            "exception": "CSRFTokenError",
            "exc_type": "CSRFTokenError",
        },
    )
