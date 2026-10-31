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
    "fremde_herkunft_abgewiesen",
    "ist_oeffentlicher_website_endpunkt",
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
# WEB-10: Kontaktformular der Website — öffentlich, ohne Sitzung gedacht, mit
# eigener strenger Herkunftsprüfung (Origin/Referer = Host). Ohne Ausnahme
# bekäme ein gleichzeitig in Diakronos angemeldeter Besucher 417, weil die
# statische Website keinen Sitzungs-CSRF-Token senden kann. NUR exakte Namen.
_WEITERE_AUSNAHMEN = frozenset({
    "/api/method/frappe.sessions.get_csrf_token",
    "/api/method/website.kontakt_senden",
    "/api/method/kontakt.kontakt_senden",
    "/api/method/diakronos.diakronos.api.website.kontakt_senden",
})


def _mit_praefix_entfernt(pfad: str) -> str:
	"""Entfernt den aktiven Betriebs-Praefix (`/diakronos/api/…` -> `/api/…`).

	SEC-11: Ein Pfad, der schon `/{Praefix}/api/…` enthaelt, wird AUCH dann
	befreit, wenn `aktiver_praefix()` in diesem Prozess leer ist. Grund: in
	einem ASGI-Mount (`root_path`) steht der Praefix im `request.url.path`,
	waehrend die Prozessgroesse nur beim Setzen des Praefixes gefuellt ist —
	dann liefe eine Praefix-Pruefung wie `ist_oeffentlicher_website_endpunkt`
	ins Leere und liesse z. B. `website.kontakt_senden` unter die
	Herkunftsschranke fallen (die oeffentliche Website kann sie dann nicht
	mehr aufrufen). Deshalb werden Prozess-Praefix UND `settings.diakronos_base_path`
	geprueft — der Pfad selbst nennt den Praefix bereits.
	"""
	from diakronos_app import base_path
	from diakronos_app.settings import settings

	roh = str(pfad or "") or "/"
	# Zwei Quellen: der Prozess-Praefix UND die Einstellung. Der Prozesswert
	# ist der gueltige, die Einstellung ist der Rueckfall fuer Faelle, in denen
	# der Praefix (noch) nicht gesetzt ist — falsch negativ waere hier
	# gleichbedeutend mit „die Ausnahme greift nicht".
	kandidaten = {
		base_path.aktiver_praefix(),
		str(getattr(settings, "diakronos_base_path", "") or ""),
	}
	for praefix in kandidaten:
		praefix = "/" + praefix.strip("/") if praefix.strip("/") else ""
		if praefix and (roh == praefix or roh.startswith(praefix + "/")):
			return roh[len(praefix):] or "/"
	return roh


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


# ── SEC-11 (C4): Herkunft als zweite, methodenunabhaengige Schranke ─────────
#
# Die Methoden-Sperre (C1/C2) haengt daran, dass ein Endpunkt als schreibend
# erkannt und deklariert wurde. Diese Schranke haengt an gar nichts: sie gilt
# fuer JEDEN Aufruf unter `/api/method/*` und `/api/resource/*`, gleich welche
# Methode. `Sec-Fetch-Site` setzt der Browser selbst — ein Skript kann den Kopf
# setzen, aber ein Skript braucht kein CSRF (es hat keine Sitzung des Opfers).
# Fehlt der Kopf (aeltere Browser, curl, Apps, CalDAV), wird NICHT abgewiesen:
# eine Sperre auf „fehlt" wuerde jeden Nicht-Browser-Aufruf treffen, und die
# Luecke, um die es geht — ein fremder Link im Browser — traegt ihn immer.
#
# Ausgenommen sind die OEFFENTLICHEN Website-Endpunkte: die statische Website
# ruft sie von einer anderen Herkunft aus auf (eigener Host), und sie bringen
# ihre eigene, strengere Herkunftspruefung mit (Origin/Referer = Host).
_API_PRAEFIXE = ("/api/method/", "/api/resource/")
_FREMDE_HERKUNFT = frozenset({"cross-site", "same-site"})
_OEFFENTLICHE_WEBSITE_ENDUNGEN = frozenset({"kontakt_senden"})


def ist_oeffentlicher_website_endpunkt(pfad: str) -> bool:
    """True fuer die Website-Endpunkte mit eigener CORS-/Herkunftspruefung."""
    pfad = _mit_praefix_entfernt(str(pfad or "").rstrip("/") or "/")
    if not pfad.startswith(_API_PRAEFIXE[0]):
        return False
    name = pfad[len(_API_PRAEFIXE[0]):]
    if name.startswith("website.") or name.startswith("website.oeffentlich."):
        return True
    # `kontakt_senden` in jeder Schreibweise (`website.kontakt_senden`,
    # `diakronos.diakronos.api.website.kontakt_senden`).
    return name.rsplit(".", 1)[-1] in _OEFFENTLICHE_WEBSITE_ENDUNGEN


def fremde_herkunft_abgewiesen(request) -> bool:
    """True, wenn ein BROWSER aus fremder Herkunft eine API anfasst (SEC-11/C4).

    Geprueft wird ausschliesslich `Sec-Fetch-Site` — `Origin`/`Referer` fehlen
    bei Navigationen und GET-Aufrufen, sind also hier kein Ersatz.

    Der Betriebs-Praefix wird VOR der Praefix-Pruefung entfernt: unter
    `/diakronos` heisst der Pfad `/diakronos/api/method/…` und beginnt nicht
    mit `/api/method/` (Befund Wegwerf-Stack 2026-10-31).
    """
    pfad = str(getattr(getattr(request, "url", None), "path", "") or "")
    if not _mit_praefix_entfernt(pfad).startswith(_API_PRAEFIXE):
        return False
    if ist_oeffentlicher_website_endpunkt(pfad):
        return False
    herkunft = (request.headers.get("sec-fetch-site") or "").strip().lower()
    return herkunft in _FREMDE_HERKUNFT


def _herkunft_ablehnung() -> Response:
    """403 fuer fremde Herkunft — Frappe-Konvention (`PermissionError`)."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=403,
        content={
            "message": "Die Anfrage kam nicht von dieser Anwendung.",
            "exception": "PermissionError",
            "exc_type": "PermissionError",
        },
    )


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
        # SEC-11/C4: Ein Browser aus fremder Herkunft kommt an KEINE API —
        # unabhaengig von der Methode. Die Methoden-Sperre (C1/C2) kann diese
        # Luecke nur schliessen, wenn der Endpunkt als schreibend deklariert
        # ist; hier haengt nichts an einer Einstufung.
        if fremde_herkunft_abgewiesen(request):
            logger.warning(
                "API-Aufruf aus fremder Herkunft abgewiesen (Sec-Fetch-Site=%s).",
                request.headers.get("sec-fetch-site"),
            )
            return _herkunft_ablehnung()
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
