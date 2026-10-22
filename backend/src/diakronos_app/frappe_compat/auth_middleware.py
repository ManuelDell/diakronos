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
    "CSRF_EXEMPT_PATHS",
    "SessionMiddleware",
    "CsrfMiddleware",
    "sid_aus_headers",
]

# Frappe nennt das Session-Cookie `sid` (identisch zu api/auth.py).
COOKIE_NAME = "sid"

# Header, den die SPA aus `boot.csrf_token` befuellt (useApi.js:18/28).
CSRF_HEADER = "x-frappe-csrf-token"

# Pfade ohne CSRF-Pruefung: nur der Login (dort gibt es noch keine Sitzung).
# `/api/method/logout` ist NICHT mehr ausgenommen: sonst koennte jede fremde
# Seite mit `<img src="/api/method/logout">` oder einem Cross-Site-Formular
# die Sitzung eines angemeldeten Nutzers beenden (Forced Logout). Die
# Ablehnung trifft nur Aufrufe, die tatsaechlich eine Sitzung mitbringen —
# ein Logout ohne Sitzung bleibt ein wirkungsloser No-op.
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/method/login",
        "/api/method/frappe.sessions.get_csrf_token",
    }
)

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
            if pfad not in CSRF_EXEMPT_PATHS:
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
