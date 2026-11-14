"""FastAPI-Router fuer die Frappe-kompatiblen Endpunkte.

Deckt ab:
- `/api/method/<dotted_path>` (GET + POST) -> `{"message": <rueckgabe>}`
- `/api/resource/<doctype>[/<name>]` (GET/POST/PUT/DELETE) -> `{"data": ...}`

Envelope- und Fehlerform siehe `backend/API_VERTRAG.md`.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.responses import Response

from diakronos_app.frappe_compat import registry
from diakronos_app.frappe_compat.exceptions import FrappeCompatError
from diakronos_app.frappe_compat.registry import lookup, options_for
from diakronos_app.frappe_compat.session import session as frappe_session
from diakronos_app.frappe_compat.registry_gen import column_names, is_known, model_for

router = APIRouter(prefix="/api", tags=["frappe-compat"])

logger = logging.getLogger("diakronos_app.frappe_compat.router")

_MISSING = object()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _ist_login_formular(fn, request: Request, exc: FrappeCompatError) -> bool:
	"""True, wenn die Fehlerantwort als Anmeldeseite statt als JSON kommen muss.

	Drei Bedingungen, alle noetig — die Pruefung ist absichtlich eng, damit
	der JSON-Weg fuer SPA, Apps und CalDAV-Clients **unveraendert** bleibt:

	  1. Es ist der Login-Endpunkt — erkannt am FUNKTIONSOBJEKT
	     (`ist_login`), nicht am Pfadnamen (LOGIN-4/A). Die namensbasierte
	     Pruefung liess jeden Alias (`auth.login`, `api.login`,
	     `<x>.auth.login`) als „kein Login\" durch, sodass ein Browser dort
	     bei falschem Passwort rohes JSON zu sehen bekam.
	  2. Die Anfrage kam als Formular-POST (`application/x-www-form-urlencoded`
	     oder `multipart/form-data`) — genau das, was ein `<form method="post">`
	     schickt.
	  3. Der Aufrufer IST ein Browser: `text/html` im `Accept` ODER
	     `Sec-Fetch-Mode: navigate`. LOGIN-2/M2: Vorher genuegte das FEHLEN von
	     `application/json`, dann bekam ein form-kodierendes Skript mit
	     `Accept: */*` (curl, `requests`, Playwright `ctx.request.post(data=…)`)
	     eine 303 auf die Maske statt der 401+JSON aus main — und mit
	     Redirect-Folgen am Ende HTML statt JSON. Jeder Browser schickt bei
	     einer Formular-Navigation `text/html`; XHR/fetch schickt
	     `application/json` oder `*/*`.

	Fehlerart: nur `AuthenticationError` (401). Andere Compat-Fehler behalten
	ihre JSON-Antwort.
	"""
	from diakronos_app.frappe_compat.exceptions import AuthenticationError

	if not ist_login(fn):
		return False
	if not isinstance(exc, AuthenticationError):
		return False
	if str(getattr(request, "method", "")).upper() != "POST":
		return False
	ctype = (request.headers.get("content-type") or "").lower()
	if "application/x-www-form-urlencoded" not in ctype and "multipart/form-data" not in ctype:
		return False
	if "application/json" in (request.headers.get("accept") or "").lower():
		return False
	if (request.headers.get("x-requested-with") or "").lower() == "xmlhttprequest":
		return False
	# LOGIN-2/M2: nur ein echter Browser bekommt die Maske. `Sec-Fetch-Mode`
	# setzt der Browser selbst (nicht faelschbar aus JavaScript); der
	# `Accept`-Kopf ist der klassische Weg fuer aeltere Browser ohne
	# Fetch-Metadaten.
	if "text/html" in (request.headers.get("accept") or "").lower():
		return True
	return (request.headers.get("sec-fetch-mode") or "").lower() == "navigate"


async def _read_args(request: Request, *, query: bool = True) -> dict[str, Any]:
	"""Argumente aus JSON-Body, Form-Body oder Query-String (Prioritaet so).

	`query=False` (nur Login, siehe `_QUERY_GESPERRT`) laesst den Query-String
	aussen vor: dann zaehlen ausschliesslich die Felder aus dem Body.
	"""
	args: dict[str, Any] = {}
	ctype = (request.headers.get("content-type") or "").lower()

	if request.method in ("POST", "PUT", "PATCH"):
		if "application/json" in ctype:
			try:
				body = await request.json()
				if isinstance(body, dict):
					args.update(body)
			except Exception:
				pass
		elif "form" in ctype or "multipart" in ctype:
			try:
				form = await request.form()
				args.update({k: v for k, v in form.items()})
			except Exception:
				pass

	if query:
		for k, v in request.query_params.items():
			args.setdefault(k, _coerce_query(v))
	return args


def _coerce_query(value: str) -> Any:
	"""Query-Strings wie Frappe auslegen: JSON, sonst String."""
	if value in ("true", "false"):
		return value == "true"
	if value == "null":
		return None
	try:
		return json.loads(value)
	except (ValueError, TypeError):
		return value


# ── SEC-8 (Pentest R3-A): Exception-Klassennamen nur nach Allowlist ─────────
#
# Pentest Runde 3 (R3-A, NIEDRIG) fand `exception`/`exc_type` mit internen
# Python-Klassennamen in JEDER Fehlerantwort: `DoesNotExistError`,
# `ValidationError`, `NotFound`, `MethodNotAllowed`, `InternalError`, …
# Zusammen mit dem Status ergab das eine Landkarte der Fehlerarten (welcher
# Endpunkt existiert, welcher nicht, welcher Argumente verlangt).
#
# Wegnehmen darf man das Feld aber NICHT: Die SPA wertet es aus (verifiziert
# per grep ueber `frontend/src`, SEC-8/S1):
#
#   * `CSRFTokenError` + 417 → `shared/sitzung-pruefen.js:34`
#     (`istSitzungsAbbruch`) → Sitzung neu aufbauen statt Fachfehler zeigen.
#     Genau daran haengen `useApi.apiCall/apiGet` (Sitzungsablauf,
#     Schreibwiederholung) und die eigenstaendigen Bundles gast/registrierung/
#     organigramm.
#   * `SessionExpired` → 401 an denselben Stellen; die Meldung ist zwar
#     Klartext, aber Tests und Bundles unterscheiden 401/419 als Sitzung.
#   * `PermissionError` → 403 bleibt Rechtefehler; `useApi` und die
#     Mitgliedsseite zeigen ihn als „darf ich nicht“ und versuchen NICHT, die
#     Sitzung zu erneuern (`MitgliedDetail.vue`, Abschnitt P1-9b).
#
# Diese drei sind damit ein STABILER VERTRAG (Allowlist) und werden
# unveraendert ausgeliefert. Alles andere — auch jeder kuenftig neu
# eingefuehrte Fehlertyp — geht als `Error` nach aussen; der echte Name
# landet im Log (Diagnose bleibt moeglich, der Client sieht ihn nicht).
EXC_TYPEN_ALLOWLIST = frozenset({"CSRFTokenError", "SessionExpired", "PermissionError"})

#: Was der Client fuer alle uebrigen Fehler sieht.
GENERISCHER_EXC_TYP = "Error"


def _oeffentlicher_exc_name(exc_name: str, msg: str, status: int) -> str:
	"""Klassenname fuer den Client — Allowlist oder generisch (SEC-8/S2)."""
	if exc_name in EXC_TYPEN_ALLOWLIST:
		return exc_name
	_buche_exc_intern(exc_name, msg, status)
	return GENERISCHER_EXC_TYP


def _buche_exc_intern(exc_name: str, msg: str, status: int) -> None:
	"""Echten Klassennamen ins Log — nur wenn er nicht ohnehin nach aussen geht."""
	logger.info(
		"Fehlerantwort bleibt generisch (status=%s, exc=%s): %s",
		status,
		exc_name,
		str(msg)[:200],
	)


def _fehler_koerper(msg: str, exc_name: str, status: int) -> dict[str, Any]:
	"""Vertragskoerper einer Fehlerantwort (eine Wahrheit fuer alle Wege)."""
	oeffentlich = _oeffentlicher_exc_name(exc_name, msg, status)
	return {"message": str(msg), "exception": oeffentlich, "exc_type": oeffentlich}


def _error_response(msg: str, exc_name: str, status: int) -> JSONResponse:
	return JSONResponse(status_code=status, content=_fehler_koerper(msg, exc_name, status))


# ── SEC-7 (N4): generische Fehlerantworten ──────────────────────────────────
#
# Pentest R2 fand 417-Antworten mit der Python-Signatur im Klartext
# („submit_registrierung() missing 3 required positional arguments: token,
# vorname, nachname"). Damit liess sich die Methodenflaeche aufzaehlen: 404
# heisst „gibt es nicht", 417 verriet den Endpunkt UND seine Parameter.
#
# Ab hier gilt: Diagnosetexte gehen ins Log, der Client bekommt EINE Meldung
# fuer alle Argumentfehler. Der Status bleibt 417 — Frappes Konvention, auf
# die sich die SPA verlaesst (`!res.ok`); ein zweiter Status waere selbst
# wieder ein Unterscheidungsmerkmal.
_ARGUMENTFEHLER_MELDUNG = "Ungueltige Anfrage"
_ARGUMENTFEHLER_TYP = "ValidationError"


def _argumentfehler(path: str, exc: BaseException, request: Request) -> JSONResponse:
	"""417 mit generischer Meldung; Ursache und Signatur nur ins Log (SEC-7/S1)."""
	logger.warning(
		"Methodenaufruf %s (%s) mit unbrauchbaren Argumenten: %s: %s",
		path,
		request.method,
		type(exc).__name__,
		exc,
	)
	return _error_response(_ARGUMENTFEHLER_MELDUNG, _ARGUMENTFEHLER_TYP, 417)


def _nicht_gefunden(request: Request) -> JSONResponse:
	"""404 fuer unbekannte UND fuer unzulaessige Methodenpfade (SEC-7/S2).

	Bewusst ohne den angefragten Pfad in der Meldung: ein gespiegelter Pfad
	ist eine Reflektion, und fuer die Unterscheidung „ungueltig" vs. „gibt es
	nicht" soll es kein zweites Fehlerbild geben.
	"""
	logger.info("Methodenpfad %r (%s) abgewiesen.", request.url.path, request.method)
	return _error_response("Methode nicht gefunden", "NotFound", 404)


# SEC-7/S2: Whitelist fuer den Methodenpfad. Erlaubt ist genau ein
# dotted name aus ASCII-Buchstaben, Ziffern und `_`, getrennt durch EINEN
# Punkt. Alles andere — `..`, `/`, `\`, `%`, Leerraum, Nullbytes, fuehrender
# oder doppelter Punkt — erreicht weder das Register noch `importlib`.
# Begruendung fuer die Enge: jeder der 37 Methodenpfade im Repo (Frontend,
# Backend, Tests, Skripte) passt in dieses Muster; Frappe-Methoden sind
# Python-Namen und koennen nichts anderes enthalten.
_METHODENPFAD = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\Z")

# Laengengrenze: kein echter Methodenpfad ist laenger; schuetzt davor, dass
# ein ueberlanger Pfad erst im Import teuer wird.
_METHODENPFAD_MAX = 255


def _gueltiger_methodenpfad(path: str) -> bool:
	"""True, wenn `path` ein zulaessiger dotted name ist (SEC-7/S2)."""
	if not path or len(path) > _METHODENPFAD_MAX:
		return False
	return _METHODENPFAD.match(path) is not None



def _json(payload: Any, status: int = 200) -> JSONResponse:
	return JSONResponse(status_code=status, content=payload)


def _coerce_json_arg(value: Any) -> Any:
	"""`filters`/`fields`/`order_by` kommen als JSON-String aus dem Query-String."""
	if isinstance(value, str):
		stripped = value.strip()
		if stripped[:1] in "[{":
			try:
				return json.loads(stripped)
			except ValueError:
				return value
		if stripped == "*":
			return "*"
		if "," in stripped:
			return [x.strip() for x in stripped.split(",")]
	return value


# ── /api/method/<dotted_path> ───────────────────────────────────────────────

# LOGIN-3/H1(b) + LOGIN-4/A: Der Login liest `usr`/`pwd` NUR aus dem Body und
# nimmt NUR POST an. Frappe erlaubt Argumente grundsaetzlich auch im
# Query-String; fuer den Login ist das ein Umgehungsweg:
# `POST /api/method/<alias>?usr=…&pwd=…` mit leerem Body meldet an, ohne dass
# ein Formular oder ein Body im Spiel ist — und `GET` erst recht (kein
# `Origin`, keine CSRF-Middleware).
#
# LOGIN-4/A: Erkannt wird der Login am FUNKTIONSOBJEKT (`ist_login`), nicht an
# einer Liste von Pfadnamen. Die Positivliste aus LOGIN-3 (`login`,
# `frappe.login`, `frappe.login.login`) liess jeden Alias offen — `auth.login`,
# `api.login`, `diakronos_app.api.auth.login` und jeder von
# `registry.registriere_originalpfad` erzeugte Pfad `<x>.auth.login` meldeten
# per GET mit `usr`/`pwd` aus dem Query-String an. Dieselbe Luecke traf die
# Formular-Fehlerantwort (`_ist_login_formular`).
#
# Die Namen bleiben als Rueckfallebene: `frappe.login` steht so im Modulkopf
# von `api/auth.py` (`FRAPPE_MODULE`) und loest im Register NICHT auf (dort
# heisst der Kernpfad `frappe.login.login`). Ein 404 ist harmlos, eine
# Anmeldung darueber waere es nicht.
_LOGIN_PFADE = frozenset({"login", "frappe.login", "frappe.login.login"})

# Methoden, die auf dem Login-Pfad angenommen werden (LOGIN-3/H1a). GET/PUT/
# PATCH bleiben fuer ALLE anderen Endpunkte erlaubt (Frappe-Verhalten).
_LOGIN_METHODEN = frozenset({"POST"})


def ist_login(fn) -> bool:
	"""True, wenn `fn` DAS Login-Funktionsobjekt ist (`api.auth.login`).

	Verglichen wird das Objekt, nicht der Name: der Router bekommt nur die aus
	dem Register aufgeloeste Funktion, und jede Umbenennung/Umregistrierung
	(auch `registry.registriere_originalpfad`) zeigt danach auf dasselbe
	Objekt. Eine zufaellig gleichnamige Funktion ist KEIN Login.
	"""
	if fn is None:
		return False
	try:
		from diakronos_app.api.auth import login as _login
	except Exception:  # noqa: BLE001 — ohne api-Modul gibt es keinen Login
		return False
	return fn is _login


def _ist_login_zugang(path: str, fn) -> bool:
	"""True, wenn dieser Aufruf den Login trifft — am Objekt ODER am Namen.

	Das Objekt entscheidet (LOGIN-4/A). Der Pfadname ist nur die
	Rueckfallebene fuer Schreibweisen, die nicht aufloesen (`frappe.login`,
	siehe `_LOGIN_PFADE`).
	"""
	return ist_login(fn) or path in _LOGIN_PFADE


def _query_erlaubt(path: str, fn) -> bool:
	"""False, wenn der Query-String fuer diesen Aufruf NICHT gelesen wird."""
	return not _ist_login_zugang(path, fn)


def _methode_erlaubt(path: str, fn, request: Request) -> bool:
	"""False, wenn dieser Aufruf die HTTP-Methode nicht annimmt.

	Zwei Quellen, in dieser Reihenfolge:

	  1. SEC-11 (CRIT-1): `@whitelist(methods=[...])`. Schreibende Endpunkte
	     deklarieren `["POST"]`; dann ist JEDE andere Methode hier zu Ende —
	     auch fuer den Login, der denselben Weg nimmt.
	  2. Ohne Deklaration gilt weiter die Login-Regel (LOGIN-3/H1(a)): der Login
	     nimmt ausschliesslich POST an, alle anderen alles.
	"""
	methode = str(getattr(request, "method", "") or "").upper()
	deklariert = registry.methoden_fuer(fn)
	if deklariert is not None:
		return methode in deklariert
	if not _ist_login_zugang(path, fn):
		return True
	return methode in _LOGIN_METHODEN


def _erlaubte_methoden(fn) -> tuple[str, ...]:
	"""Methoden, die der Router fuer diesen Endpunkt zulaesst (fuer den `Allow`-Kopf)."""
	deklariert = registry.methoden_fuer(fn)
	if deklariert is not None:
		return deklariert
	return tuple(sorted(_LOGIN_METHODEN))



def _ist_browser_navigation(request: Request) -> bool:
	"""True, wenn ein BROWSER diese Adresse als Seite aufruft (nicht `fetch`).

	Ein Browser zeigt nach einer Navigation HTML an; `Accept: text/html` bzw.
	`Sec-Fetch-Mode: navigate` sind die beiden Merkmale dafuer (dieselbe
	Unterscheidung wie in `_ist_login_formular`, LOGIN-2/M2). Nur dann ist eine
	Weiterleitung auf die Anmeldemaske sinnvoll — ein Skript bekommt 405.
	"""
	return (
		"text/html" in (request.headers.get("accept") or "").lower()
		or (request.headers.get("sec-fetch-mode") or "").lower() == "navigate"
	)


#: BS-1c2 (F3): Endpunkte, die den CORS-PREFLIGHT selbst beantworten, werden
#: hier ausdruecklich angemeldet (`preflight=self` im `@whitelist`-Aufruf).
#: Bis BS-1c entschied die FUNKTIONSGESTALT (`async def` + Parameter
#: `request`) — damit haette jeder kuenftige asynchrone Endpunkt mit
#: `request` stillschweigend den Preflight geerbt und wuerde bei OPTIONS
#: AUSGEFUEHRT. Jetzt gilt nur noch eine sichtbare Anmeldung.
_PREFLIGHT_SELBST = "self"


async def _preflight(path: str, request: Request):
	"""BS-1c/K4, praezisiert in BS-1c2 (F3): OPTIONS auf `/api/method/…`.

	Zwei Faelle, EIN Grundsatz — ein Preflight fuehrt NICHTS aus, was nicht
	ausdruecklich als Preflight-Behandler angemeldet ist:

	  * Der Endpunkt traegt `preflight="self"` in seiner `@whitelist`-
	    Deklaration (das Kontaktformular, BS-1c/K4). NUR er bekommt den
	    Request; er entscheidet selbst ueber Herkunft und CORS-Kopfzeilen
	    (eigene Herkunft, `PRIMO_PUBLIC_URL`, sonst 403).
	  * Alles andere — auch ein `async def`-Endpunkt mit `request`-Parameter:
	    204 ohne Inhalt und ohne CORS-Freigabe. Kein Register-Orakel
	    (unbekannter Pfad antwortet gleich), keine Sitzung, keine
	    Fachfunktion.

	`@whitelist(methods=[...])` bleibt unberuehrt: OPTIONS steht in keiner
	Deklaration, und ein Endpunkt ohne CORS-Bedarf wird durch den Preflight
	auch nicht erreichbar — der Browser bricht ohne Freigabe ab.
	"""
	from starlette.responses import Response

	fn = lookup(path)
	if fn is None:
		_maybe_import(path)
		fn = lookup(path)
	if fn is not None and _beantwortet_preflight_selbst(fn):
		ergebnis = fn(request=request)
		if inspect.iscoroutine(ergebnis):
			ergebnis = await ergebnis
		return ergebnis
	antwort = Response(status_code=204)
	antwort.headers["Cache-Control"] = "no-store"
	antwort.headers["Allow"] = ", ".join(_erlaubte_methoden(fn)) if fn is not None else "GET, POST, PUT, PATCH"
	return antwort


@router.api_route(
	"/method/{path:path}",
	methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
	operation_id="call_method",
)
async def call_method(path: str, request: Request):
	# BS-1c/K4: OPTIONS ist der CORS-PREFLIGHT des Browsers. Er darf NICHTS
	# ausfuehren und NICHTS verraten — die Antwort ist immer leer, fuehrt keine
	# Fachfunktion aus und unterscheidet sich fuer unbekannte Pfade nicht von
	# bekannten (kein Orakel ueber das Register). Ein Endpunkt, der CORS
	# braucht (das Kontaktformular von der Primo-Herkunft), antwortet selbst;
	# er bekommt VOR jeder anderen Pruefung den Request. SEC-11/C1 („nur die
	# deklarierten Methoden") bleibt unberuehrt: OPTIONS fuehrt nie etwas aus.
	if str(getattr(request, "method", "") or "").upper() == "OPTIONS":
		return await _preflight(path, request)
	# SEC-7/S2 (N5): Der Pfad wird VOR jeder Aufloesung geprueft. Vorher lief
	# `..%2F..%2Fetc%2Fpasswd` bis in `_maybe_import` und endete in einem
	# unbehandelten 500 (TypeError aus dem relativen Import) — ein Fehlerbild,
	# das einen Programmfehler vortaeuschte und die Verzeichnisstruktur
	# sondierbar machte (Ja/Nein je Pfad).
	if not _gueltiger_methodenpfad(path):
		return _nicht_gefunden(request)
	fn = lookup(path)
	if fn is None:
		# Fallback: Modul importieren (registriert die Funktionen).
		_maybe_import(path)
		fn = lookup(path)
	if fn is None:
		return _nicht_gefunden(request)

	# LOGIN-3/H1(a): Der Login nimmt NUR POST an. Eine GET-Anmeldung ist der
	# klassische CSRF-Weg ohne Formular (`<img src="/api/method/login?usr=…&pwd=…">`,
	# geteilter Link): sie traegt keinen `Origin` und faellt nicht unter die
	# CSRF-Middleware. Ein Browser, der navigiert, landet auf der Anmeldemaske;
	# ein Skript bekommt 405. In beiden Faellen wird KEINE Sitzung gesetzt.
	#
	# SEC-11 (CRIT-1) erweitert genau diesen Weg auf ALLE Endpunkte, die
	# `@whitelist(methods=[...])` deklarieren: ein Link
	# `GET /api/method/<schreibende_funktion>?…` aus einer fremden Seite ist
	# damit derselbe Fall — der Browser-Nutzer landet auf der Anmeldemaske,
	# ein Skript bekommt 405, und KEINE Fachfunktion wird aufgerufen.
	if not _methode_erlaubt(path, fn, request):
		erlaubt = ", ".join(_erlaubte_methoden(fn))
		if _ist_browser_navigation(request):
			from urllib.parse import quote

			from diakronos_app.api.auth import SPA_ZIEL
			from starlette.responses import RedirectResponse

			# Zurueck auf die Anmeldemaske — dasselbe Ziel wie ein
			# fehlgeschlagenes Formular (`login_formular_fehler`).
			antwort = RedirectResponse(
				f"/login?noredirect=1&redirect-to={quote(SPA_ZIEL, safe='')}",
				status_code=303,
			)
			antwort.headers["Cache-Control"] = "no-store"
			logger.info("Aufruf per %s abgewiesen (erlaubt: %s).", request.method, erlaubt)
			return antwort
		logger.info("Aufruf per %s abgewiesen (erlaubt: %s).", request.method, erlaubt)
		return JSONResponse(
			status_code=405,
			content=_fehler_koerper(
				"Diese Methode ist fuer diesen Endpunkt nicht erlaubt.",
				"MethodNotAllowed",
				405,
			),
			headers={"Allow": erlaubt},
		)
	if _guest_denied(fn):
		return _error_response("Deine Anmeldung ist abgelaufen. Bitte melde dich neu an.", "SessionExpired", 401)
	args = await _read_args(request, query=_query_erlaubt(path, fn))
	accepted = _accepted_params(fn)
	# `accepted is None` -> Funktion hat `**kwargs`, alle Argumente durchreichen.
	kwargs = args if accepted is None else {k: v for k, v in args.items() if k in accepted}
	# A1b1: Endpunkte, die den HTTP-Request selbst brauchen (Logout liest das
	# `sid`-Cookie), deklarieren einen Parameter `request`. Der Kontext-Middleware
	# laesst sich das wegen `BaseHTTPMiddleware` + Sync-Endpunkt nicht verlaesslich
	# entnehmen, deshalb wird er hier explizit durchgereicht.
	# A1b2-rest: `login(usr, pwd, request=None, **kwargs)` hat BEIDES einen
	# `**kwargs` (Frappe-Semantik: alle Formularfelder durchreichen) UND ein
	# `request`. `_accepted_params` liefert fuer eine solche Funktion `None`,
	# deshalb wird die Namensliste hier eigens ermittelt — sonst bekommt
	# `login` den Request nicht und kann Formular-POST nicht von fetch/JSON
	# unterscheiden.
	if _hat_namenparameter(fn, "request"):
		kwargs["request"] = request
	# Positionale Argumente aus kwargs (Frappe-Parameter sind Keyword-faehig).
	try:
		result = fn(**kwargs)
		# WEB-10: ein `async def`-Endpunkt (das Kontaktformular) liefert eine
		# Coroutine — der Router laeuft selbst in einer Coroutine und kann sie
		# hier abwarten. Ohne diesen Schritt stuende die Coroutine als
		# `message` in der Antwort. Der Rumpf dieses Endpunkts wird dadurch
		# EHESTENS so lange blockiert wie der Endpunkt selbst (Lesen mit
		# Zeitlimit, Mailversand im eigenen Faden) — es gibt keine weiteren
		# `async def`-Endpunkte; ein Test haelt das fest.
		if inspect.iscoroutine(result):
			result = await result
	except FrappeCompatError as exc:
		# LOGIN-1: Ein BROWSER-Formular (Anmeldemaske) darf niemals rohes JSON
		# zu sehen bekommen — der Browser zeigt es als Seite an. Kam der Aufruf
		# als Formular-POST, geht es zurueck auf die Anmeldeseite mit einer
		# verstaendlichen Meldung; die zuletzt eingegebene E-Mail reist in einem
		# kurzlebigen, signierten Flash-Cookie (NIE in der URL, NIE das Passwort).
		# JSON/XHR-Aufrufer (SPA, Apps, CalDAV, Tests) bekommen unveraendert
		# 401 + JSON — die Bedingung ist deshalb bewusst eng (nur der
		# Login-Endpunkt, nur ein Formular-POST, nur wenn der Aufrufer kein
		# JSON erwartet).
		from_formular = _ist_login_formular(fn, request, exc)
		if from_formular:
			try:
				from diakronos_app.api.auth import login_formular_fehler

				return login_formular_fehler(request, kwargs)
			except Exception:  # noqa: BLE001 — die Fehlerantwort darf nicht scheitern
				logger.exception("Login-Fehlerantwort (Formular) nicht baubar.")
		# A1b2-rest-Vertrag: `exc_type`/`exception` an der Exception-Klasse
		# bleiben (`SessionExpired`, `CSRFTokenError`, …) — die SPA und die
		# Tests werten sie aus. Die MELDUNG ist Fachinhalt (`frappe.throw`),
		# kein Diagnosetext; SEC-7/S1 betrifft nur Python-Signaturen und
		# interne Namen aus unerwarteten Ausnahmen.
		return _error_response(str(exc), exc.exc_name, exc.http_status)
	# SEC-8/S3: alle Argumentfehler — fehlende wie ueberzaehlige oder falsch
	# typisierte — enden hier in DEMSELBEN Bild (417, generische Meldung).
	# Vorher lief ein falscher Typ (z. B. `geburtsdatum: 123`) in den
	# `except Exception`-Zweig und wurde 500 „Interner Fehler" — ein 500 fuer
	# eine Eingabe, die der Aufrufer selbst verursacht hat (und ein weiteres
	# Unterscheidungsmerkmal mehr). `FrappeCompatError` bleibt davon
	# unberuehrt (Block darueber).
	except (TypeError, ValueError, KeyError) as exc:
		# SEC-7/S1 (N4): hier stand die Python-Signatur im Klartext
		# („submit_registrierung() missing 3 required positional arguments …").
		# Fehlende, falsche und unerwartete Argumente — auch der Aufruf mit
		# `*args`/`**fehlt` — enden jetzt in EINER generischen 417-Antwort.
		# `ValueError`/`KeyError` gehoeren dazu: sie tragen Schluessel- und
		# Feldnamen nach aussen („unbekanntes Feld 'bezeichnung'").
		# `FrappeCompatError` bleibt davon unberuehrt (Block darueber).
		return _argumentfehler(path, exc, request)
	except Exception as exc:  # noqa: BLE001 — SEC-7/S1: nie 500 mit Interna
		# SEC-7/S1: Bisher lief ein unerwarteter Fehler aus einer Fachfunktion
		# als roher 500 mit Traceback nach aussen. Der Client bekommt jetzt
		# eine generische 500 ohne Details.
		#
		# NICHT geschluckt wird `RuntimeError` — und zwar aus einem gemessenen
		# Grund: die DSGVO-/Datenschutz-Tests stellen ihre Falle als
		# `event.listen(engine, "before_cursor_execute", ...)` mit einem
		# `RuntimeError` und erwarten, dass der Fehler den Aufruf erreicht
		# (`pytest.raises(RuntimeError)`), damit sie den Rollback pruefen
		# koennen. Ein pauschaler Fänger machte diese Zusagen unsichtbar
		# (3 Tests rot, `test_dsgvo1_anonymisierung`,
		# `test_dsgvo1b_review`, `test_n7_profil_datenschutz`). Der Import
		# laesst den Traceback ebenfalls bis zum Server durch — genau wie
		# vorher; nur die Antwort an den Client ist jetzt generisch.
		logger.exception("Methodenaufruf %s (%s) fehlgeschlagen.", path, request.method)
		if isinstance(exc, RuntimeError):
			raise
		return _error_response("Interner Fehler", "InternalError", 500)
	# A1b1: Endpunkte, die den Response selbst bauen muessen (Set-Cookie beim
	# Login/Logout), geben direkt eine `Response` zurueck. Alles andere bleibt
	# im Frappe-Envelope `{"message": ...}`.
	if isinstance(result, Response):
		return result
	return _json({"message": _serialize_payload(result)})


def _accepted_params(fn) -> set[str] | None:
	"""Namen der Parameter, die der Router an `fn` weiterreichen darf.

	Rueckgabe `None` bedeutet „alle uebergebenen Argumente durchreichen"
	(Frappe-Semantik): hat die Funktion einen `**kwargs`-Sammler
	(z. B. `registrierungslink_api.update_link(link_id, **kwargs)`), leitet
	Frappe ALLE Request-Parameter dorthin weiter — nicht nur die benannten.
	Die Fachfunktion filtert selbst.

	Alle uebrigen Argumente (`*args`) bleiben wie bisher ausgeschlossen.
	"""
	try:
		sig = inspect.signature(fn)
	except (TypeError, ValueError):  # pragma: no cover
		return set()
	names = set()
	for name, param in sig.parameters.items():
		if param.kind == param.VAR_KEYWORD:
			return None
		if param.kind == param.VAR_POSITIONAL:
			continue
		names.add(name)
	return names


def _beantwortet_preflight_selbst(fn) -> bool:
	"""True, wenn `fn` den CORS-Preflight AUSDRUECKLICH selbst beantwortet (F3).

	Die Anmeldung ist `@whitelist(..., preflight="self")` — eine sichtbare
	Zeile am Endpunkt, die man beim Lesen der Deklaration sieht. Die
	Funktionsgestalt (`async def` + `request`) entscheidet NICHT: sonst
	erbte jeder neue asynchrone Endpunkt mit `request` den Preflight und
	wuerde bei OPTIONS ausgefuehrt, ohne dass jemand das je beschlossen hat.
	`request` muss trotzdem deklariert sein — ohne ihn kann der Endpunkt
	Herkunft und CORS nicht pruefen.
	"""
	if options_for(fn).get("preflight") != _PREFLIGHT_SELBST:
		return False
	return _hat_namenparameter(fn, "request")


def _hat_namenparameter(fn, name: str) -> bool:
	"""True, wenn `fn` den Parameter `name` ausdruecklich deklariert.

	`_accepted_params` liefert `None`, sobald die Funktion einen `**kwargs`
	hat (Frappe-Semantik). Fuer diese Funktionen muss trotzdem erkannt werden
	bar bleiben, ob sie ZUSAETZLICH einen benannten Parameter wie `request`
	erwarten — sonst bekaemen sie ihn nie.
	"""
	try:
		sig = inspect.signature(fn)
	except (TypeError, ValueError):  # pragma: no cover
		return False
	param = sig.parameters.get(name)
	return param is not None and param.kind is not param.VAR_KEYWORD


def _guest_denied(fn) -> bool:
	"""Guest access requires an explicit boolean `allow_guest=True`.

	Missing options and registrations without a flag are fail-closed, as in
	Frappe. Authentication is separate from the endpoint's role/object ACL.
	"""
	if options_for(fn).get("allow_guest", False) is True:
		return False
	return frappe_session.user == "Guest"


def _maybe_import(path: str) -> None:
	"""Importiert das Modul einer dotted path, um `whitelist`-Eintraege zu laden."""
	import importlib

	# Basis-Paket immer laden: registriert alle Funktionen der Portierungen.
	try:
		importlib.import_module("diakronos_app.api")
	except ImportError:  # pragma: no cover — Paket fehlt nur vor P2b
		pass

	# Original-Pfade nachtragen (idempotent): deckt den Fall ab, dass das
	# Paket beim Serverstart nur halb geladen wurde und die SPA deshalb
	# 404 auf `diakronos.diakonos.api.<modul>.<funktion>` sieht.
	from diakronos_app.frappe_compat.registry import (
		nachregistrieren,
		registriere_originalpfad,
	)

	# (1) Direkt fuer den angefragten Pfad: aus `diakronos.diakonos.api.mod.fn`
	#     wird das Kurzmodul `mod`; ist dessen Funktion bekannt, wird der
	#     Original-Pfad gesetzt. Das greift unabhaengig von Importreihenfolge
	#     und Register-Rennen.
	registriere_originalpfad(path)
	# (2) Flaechendeckend fuer alles, was bereits registriert ist.
	nachregistrieren()

	parts = path.split(".")
	for cut in range(len(parts) - 1, 0, -1):
		candidates = [
			".".join(["diakronos_app", "api", *parts[:cut]]),
			".".join([*parts[:cut]]),
		]
		for module_name in candidates:
			try:
				importlib.import_module(module_name)
				return
			except ImportError:
				continue


def _praefixierte_datei_urls(wert: Any) -> Any:
	"""WEB-5a: `file_url`-Werte in einer Antwort mit Betriebs-Praefix.

	In der Datenbank stehen `/files/…` und `/private/files/…` (Frappe-Erbe,
	Karte: DB NICHT migrieren). Bei der AUSGABE muessen die Adressen unter dem
	Praefix stimmen. Angefasst wird ausschliesslich der SCHLUESSEL `file_url` —
	ein beliebiger Text mit `/files/` am Anfang bleibt unberuehrt.

	Ohne Praefix (`DIAKRONOS_BASE_PATH` leer) gibt die Funktion den Wert
	unveraendert zurueck und laesst sich deshalb gefahrlos auf jedem Leseweg
	einsetzen.
	"""
	from diakronos_app.base_path import aktiver_praefix, datei_url

	if not aktiver_praefix():
		return wert
	if isinstance(wert, dict):
		return {
			k: (datei_url(v) if k == "file_url" and isinstance(v, str) else _praefixierte_datei_urls(v))
			for k, v in wert.items()
		}
	if isinstance(wert, (list, tuple, set)):
		return [_praefixierte_datei_urls(v) for v in wert]
	return wert


def _serialize_payload(value: Any) -> Any:
	"""Antwortwert JSON-faehig machen (Datetime/Decimal/Document/ORM-Objekte).

	SEC-1: Dict-Schluessel, die ein Geheimnis benennen (`password_hash`,
	`*_hash`, `*_secret`, `api_key` …), werden verworfen. Das ist die zweite,
	von der Spaltenauswahl unabhaengige Verteidigungslinie — sie greift auch
	fuer Pfade, die ein Modell direkt serialisieren (z.B. die Antwort nach
	einem POST/PUT). Siehe `query.ist_gesperrtes_feld`.

	WEB-5a: `file_url`-Werte bekommen den Betriebs-Praefix (DB bleibt
	unveraendert). Das geschieht NACH dem Verwerfen der gesperrten Felder und
	nur auf dem fertigen Ergebnis, damit die Feld-Sperre unberuehrt bleibt.
	"""
	return _praefixierte_datei_urls(_serialize_roh(value))


def _serialize_roh(value: Any) -> Any:
	"""Teil von `_serialize_payload` OHNE die Praefix-Behandlung."""
	from datetime import date, datetime, time
	from decimal import Decimal

	from .query import ist_gesperrtes_feld

	if value is None or isinstance(value, (str, int, float, bool)):
		return value
	if isinstance(value, (datetime, date, time)):
		return str(value)
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, dict):
		return {
			k: _serialize_roh(v) for k, v in value.items()
			if not ist_gesperrtes_feld(k)
		}
	if isinstance(value, (list, tuple, set)):
		return [_serialize_roh(v) for v in value]
	if hasattr(value, "as_dict"):
		return _serialize_roh(value.as_dict())
	if hasattr(value, "__table__"):
		return {
			c.name: _serialize_roh(getattr(value, c.name))
			for c in value.__table__.columns
			if not ist_gesperrtes_feld(c.name)
		}
	return value


# ── /api/resource/<doctype>[/<name>] ────────────────────────────────────────


def _private_resource_denied(doctype: str) -> bool:
	# Hotfix 2026-10-16 (Nachtpruefung BLD-R1): ohne Anmeldung nie; Konten/Rollen nur Admins.
	if frappe_session.user == "Guest":
		return True
	if doctype in {"User", "Has Role"}:
		# SEC-1 (S2): dieselbe Regel wie `_resource_denied` — sonst liefe die
		# zweite Verteidigungslinie fuer den Sondernutzer `Administrator`
		# wieder in ein 403.
		from diakronos_app.frappe_compat.permissions import get_roles
		return ("System Manager" not in set(get_roles())
		        and frappe_session.user != "Administrator")
	# G1a: neither ciphertext nor credentials writes belong in generic CRUD.
	if doctype == "Google Kalender Einstellungen":
		return True
	# Plan-Rahmen (PR3): die pr_*-Tabellen sind handgepflegt (NICHT generiert)
	# und duerfen niemals ueber den generischen Frappe-Resource-CRUD
	# (/api/resource/<doctype>) erreichbar sein. Sie tauchen bewusst nicht in
	# models/_mapping.json auf (is_known -> False), aber die Sperre hier ist
	# die zweite, ausdrueckliche Verteidigungslinie: selbst wenn eine dieser
	# Tabellen je ins Mapping geriete, bleibt der generische Weg zu.
	if doctype in _PLANRAHMEN_DOCTYPES:
		return True
	# B2: freie Projektionen/Filter/pluck koennen Maskierung umgehen.
	# Die SPA liest Mitglied-Daten ueber die kontrollierten Methoden, nicht
	# ueber diese generische Listen-API. Logs sind ausschliesslich Admin-Daten.
	if doctype not in {"Mitglied", "DSGVO Einwilligung"}:
		return False
	from diakronos_app.frappe_compat.permissions import get_roles
	return not bool({"System Manager", "Mitgliederadministrator"} & set(get_roles()))


# DocType-Namen der Plan-Rahmen-Tabellen (PR3) — siehe `_private_resource_denied`.
_PLANRAHMEN_DOCTYPES = {
	"Plantyp",
	"Plantyp Version",
	"Plan",
	"Termin",
	"Eintrag",
	"Verlauf",
	"Merkmal",
	"Merkmal Wert",
	"Sammlung",
	"Sammlung Eintrag",
	"Abwesenheit",
}

# ── Rollenmatrix fuer den generischen CRUD (BLD-R1 Rest) ────────────────────
#
# Der Hotfix vom 16.10. schloss nur Gaeste und `User`/`Has Role` aus. Danach
# durfte JEDER angemeldete Nutzer weiter jeden DocType ueber
# `/api/resource/<doctype>` lesen, schreiben und loeschen — auch
# personenbezogene (Anmeldung, Gruppenmitgliedschaft) und Audit-Daten.
#
# Deshalb gilt hier ab jetzt eine **Allowlist** statt einer Sperrliste:
# angemeldete Nicht-Admins duerfen genau die DocTypes lesen, die die SPA
# nachweislich ueber diesen Weg abruft, und **nichts** schreiben oder loeschen.
#
# Belegte SPA-Aufrufe (einzige Fundstellen von `/api/resource` im Frontend):
#   * `Eventkategorie` — Liste, KronosEventCreate.vue:296 / KronosEventEdit.vue:276
#   * `Mitglied`       — maskierter Einzelabruf ueber den Sonderweg unten
#                        (get_mitglied_detail); Listen bleibt Admin-Sache.
#
# P0-1-Rest (Befund P0-1): `Element` war HIER ebenfalls in der
# Leseallowlist. Der einzige Frontend-Treffer ist ein DELETE
# (useEventsApi.js:103 -> `deleteEvent`), das fuer Nicht-Admins ohnehin
# gesperrt ist und nirgends aufgerufen wird — ein toter Pfad. Als LESEweg war
# die Allowlist dagegen ein Datenabfluss ohne Funktion: jedes angemeldete
# Mitglied konnte damit ueber `fields`/`filters`/`pluck` ALLE Termine ALLER
# Kalender listen und einzeln lesen (Titel, Beschreibung, Status, Kalender) —
# und damit die Filter von `get_events`, Dashboard und Konfliktliste umgehen.
# Termine gehoeren ueber die kalendergeprueften Methoden (`get_calendar_events`,
# `get_events`) gelesen, nicht ueber den generischen CRUD.
_RESOURCE_LESEN_NICHT_ADMIN = frozenset({"Eventkategorie"})

# Nur der Einzelabruf (Detail): `Mitglied` laeuft in den maskierten Sonderweg,
# die Liste bleibt bewusst Admin-only (B2: Filter/pluck koennen die Maskierung
# umgehen).
_RESOURCE_DETAIL_NICHT_ADMIN = frozenset({"Mitglied"})

# Aktionen der Rollenmatrix. `list` und `read` sind bewusst getrennt: `Element`
# ist als Liste UND Einzelabruf erlaubt, `Mitglied` dagegen nur im Detail.
_RESOURCE_AKTIONEN = frozenset({"list", "read", "write", "delete"})


def _ist_resource_admin() -> bool:
	"""Admin-Kurzschluss der generischen REST-Schnittstelle.

	R-11a: NUR der Administrator des EINEN Rechtesystems. Vorher zaehlte jede
	Rolle aus `ADMIN_ROLES` — damit hatte die Mitgliederverwaltung Lese- und
	Schreibzugriff auf jede Tabelle an allen fachlichen Pruefungen vorbei.
	"""
	from diakronos_app import rechte

	user = frappe_session.user
	if not user or user == "Guest":
		return False
	return rechte.ist_admin(user)


def _ist_benutzer_admin() -> bool:
	"""Darf dieser Aufruf Konten und Rollen (`User`/`Has Role`) sehen? (SEC-1)

	Enger als `_ist_resource_admin`: nur die Systemverwaltung. `ADMIN_ROLES`
	enthaelt auch `Mitgliederadministrator` — der verwaltet Mitglieder und
	darf die Konten mit Passwort-Hashes NICHT lesen.
	"""
	from diakronos_app.frappe_compat.permissions import ADMIN_ROLES, get_roles

	user = frappe_session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	# Nur die Rolle `System Manager` zaehlt. `Mitgliederadministrator` steht
	# ebenfalls in `ADMIN_ROLES`, verwaltet aber Mitglieder, nicht Konten —
	# er darf die Passwort-Hashes nicht lesen.
	return "System Manager" in set(get_roles(user)) & set(ADMIN_ROLES)


def _resource_denied(doctype: str, aktion: str) -> str | None:
	"""Rollenmatrix fuer `/api/resource` — fail closed (BLD-R1 Rest).

	Rueckgabe: Meldung fuer 403 — oder `None`, wenn der Zugriff erlaubt ist.

	Reihenfolge:
	  1. Ohne Anmeldung nie (Hotfix 16.10. bleibt in Kraft).
	  2. Ausdrueckliche Sperren (`Google Kalender Einstellungen` — Chiffrat und
	     Zugangsdaten; Plan-Rahmen-Tabellen) gelten auch fuer Admins.
	  3. `User`/`Has Role` nur fuer `System Manager` (Konten und Rollen).
	  4. Admin-Rollen: Vollzugriff auf das Uebrige.
	  5. Angemeldete Nicht-Admins: ausschliesslich die Leseallowlist oben,
	     kein Schreiben, kein Loeschen.
	"""
	if aktion not in _RESOURCE_AKTIONEN:  # pragma: no cover — Programmierfehler
		return "Unbekannte Aktion."
	if frappe_session.user == "Guest":
		return "Zugriff verweigert."
	if doctype == "Google Kalender Einstellungen":
		return "Auf diese Daten ist der generische Zugriff gesperrt."
	if doctype in _PLANRAHMEN_DOCTYPES:
		return "Auf diese Daten ist der generische Zugriff gesperrt."
	if doctype in {"User", "Has Role"}:
		# SEC-1 (S2): Konten und Rollen nur fuer die Systemverwaltung. Es gilt
		# dieselbe Menge wie `permissions.is_admin` — `System Manager`, die
		# Rollen aus `ADMIN_ROLES` und der Sondernutzer `Administrator`
		# (die Erstinstallation legt ihn ohne `Has Role`-Zeile an; ohne diese
		# Ausnahme waere die Kontenverwaltung fuer ihn gesperrt).
		# `Mitgliederadministrator` bleibt ausdruecklich draussen: er verwaltet
		# Mitglieder, nicht Konten mit Passwort-Hashes.
		if not _ist_benutzer_admin():
			return "Benutzerkonten und Rollen nur fuer System Manager."
		return None
	if _ist_resource_admin():
		return None
	if aktion == "list" and doctype in _RESOURCE_LESEN_NICHT_ADMIN:
		return None
	if aktion == "read" and doctype in _RESOURCE_LESEN_NICHT_ADMIN | _RESOURCE_DETAIL_NICHT_ADMIN:
		return None
	return "Für diese Daten fehlt die Berechtigung."


def _resolve_doctype(value: str) -> str:
	"""`/api/resource/Mitglied` -> DocType `Mitglied` (URL-Deko identisch)."""
	return value


@router.get("/resource/{doctype}")
async def resource_list(doctype: str, request: Request):
	meldung = _resource_denied(doctype, "list")
	if meldung:
		return _error_response(meldung, "PermissionError", 403)
	if _private_resource_denied(doctype):
		return _error_response("Private Resource-Liste nur fuer Admins.", "PermissionError", 403)
	if not is_known(doctype):
		return _error_response(f"DocType {doctype!r} nicht gefunden", "DoesNotExistError", 404)
	from diakronos_app.frappe_compat.query import get_all

	qp = dict(request.query_params)
	filters = _coerce_json_arg(qp.get("filters"))
	fields = _coerce_json_arg(qp.get("fields"))
	or_filters = _coerce_json_arg(qp.get("or_filters"))
	order_by = qp.get("order_by")
	limit_start = int(qp.get("limit_start", 0) or 0)
	limit_page_length = qp.get("limit_page_length")
	limit_page_length = int(limit_page_length) if limit_page_length not in (None, "") else None
	as_list = qp.get("as_list") in ("1", "true")
	pluck = qp.get("pluck")

	# UX2b2 (F3): die generische Liste verhaelt sich wie jede Lese-Ausgabe —
	# Zeilen im Papierkorb erscheinen nicht. Der Zusatzfilter haengt HINTEN an
	# die uebergebene Filterliste (gleichheit, keine ODER-Verknuepfung), damit
	# ein Aufrufer ihn nicht ueberschreiben kann.
	from diakronos_app.papierkorb import BEREICHE as _PAPIERKORB_BEREICHE
	from diakronos_app.papierkorb import nur_aktive_filter as _nur_aktive

	if doctype in _PAPIERKORB_BEREICHE:
		if isinstance(filters, dict):
			filters = {**filters}
			filters["geloescht_am"] = ["is", "not set"]
		else:
			filters = list(filters or []) + _nur_aktive(doctype)

	try:
		rows = get_all(
			doctype,
			filters=filters,
			or_filters=or_filters,
			fields=fields,
			order_by=order_by,
			limit_start=limit_start,
			limit_page_length=limit_page_length,
			as_list=as_list,
			pluck=pluck,
		)
	except FrappeCompatError as exc:
		return _error_response(str(exc), exc.exc_name, exc.http_status)
	except KeyError as exc:
		return _error_response(str(exc), "ValidationError", 417)
	# SPA liest catRes.data -> bewusste Abweichung von Frappes nacktem Array.
	return _json({"data": _serialize_payload(rows)})


@router.get("/resource/{doctype}/{name}")
async def resource_get(doctype: str, name: str):
	meldung = _resource_denied(doctype, "read")
	if meldung:
		return _error_response(meldung, "PermissionError", 403)
	if _private_resource_denied(doctype):
		if doctype in {"DSGVO Einwilligung", "Google Kalender Einstellungen"}:
			return _error_response("Einwilligungs-Logs nur fuer Admins.", "PermissionError", 403)
		if doctype in _PLANRAHMEN_DOCTYPES:
			# Plan-Rahmen-Tabellen sind handgepflegt und haben KEINEN
			# generischen Einzelabruf. Der Abruf hier darf nicht in den
			# Mitglied-Sonderweg (get_mitglied_detail) rutschen.
			return _error_response("Private Resource nur fuer Admins.", "PermissionError", 403)
		from diakronos_app.api.mitglieder import get_mitglied_detail
		try:
			return _json({"data": _serialize_payload(get_mitglied_detail(name)["data"])})
		except FrappeCompatError as exc:
			return _error_response(str(exc), exc.exc_name, exc.http_status)
	if not is_known(doctype):
		return _error_response(f"DocType {doctype!r} nicht gefunden", "DoesNotExistError", 404)
	from diakronos_app.frappe_compat.query import get_doc

	try:
		doc = get_doc(doctype, name)
	except FrappeCompatError as exc:
		return _error_response(str(exc), exc.exc_name, exc.http_status)
	# UX2b2 (F3): ein Einzelabruf auf eine Zeile im Papierkorb antwortet wie
	# auf eine nicht vorhandene Zeile — sonst liesse sich der Papierkorb ueber
	# den generischen CRUD doch wieder auslesen.
	from diakronos_app.papierkorb import BEREICHE as _PAPIERKORB_BEREICHE
	from diakronos_app.papierkorb import ist_geloescht as _ist_geloescht

	if doctype in _PAPIERKORB_BEREICHE and _ist_geloescht(doctype, name):
		return _error_response(
			f"{doctype} {name!r} nicht gefunden", "DoesNotExistError", 404
		)
	return _json({"data": _serialize_payload(doc)})


@router.post("/resource/{doctype}")
async def resource_create(doctype: str, request: Request):
	meldung = _resource_denied(doctype, "write")
	if meldung:
		return _error_response(meldung, "PermissionError", 403)
	if _private_resource_denied(doctype):
		return _error_response("Private Resource nur fuer Admins.", "PermissionError", 403)
	if not is_known(doctype):
		return _error_response(f"DocType {doctype!r} nicht gefunden", "DoesNotExistError", 404)
	body = await _read_args(request)
	doc = _apply_resource_write(doctype, None, body)
	if isinstance(doc, JSONResponse):
		return doc
	return _json({"data": doc})


@router.put("/resource/{doctype}/{name}")
async def resource_update(doctype: str, name: str, request: Request):
	meldung = _resource_denied(doctype, "write")
	if meldung:
		return _error_response(meldung, "PermissionError", 403)
	if _private_resource_denied(doctype):
		return _error_response("Private Resource nur fuer Admins.", "PermissionError", 403)
	if not is_known(doctype):
		return _error_response(f"DocType {doctype!r} nicht gefunden", "DoesNotExistError", 404)
	body = await _read_args(request)
	doc = _apply_resource_write(doctype, name, body)
	if isinstance(doc, JSONResponse):
		return doc
	return _json({"data": doc})


@router.delete("/resource/{doctype}/{name}")
async def resource_delete(doctype: str, name: str):
	meldung = _resource_denied(doctype, "delete")
	if meldung:
		return _error_response(meldung, "PermissionError", 403)
	if _private_resource_denied(doctype):
		return _error_response("Private Resource nur fuer Admins.", "PermissionError", 403)
	if not is_known(doctype):
		return _error_response(f"DocType {doctype!r} nicht gefunden", "DoesNotExistError", 404)
	from diakronos_app.frappe_compat.query import get_doc
	from diakronos_app.db import SessionLocal

	# UX2b2 (F3): Ein DELETE ueber den generischen CRUD auf einen der fuenf
	# Papierkorb-DocTypes loescht NICHT mehr endgueltig — es legt die Zeile in
	# den Papierkorb, wie jeder andere Loeschweg der Verwaltung. Sonst waere
	# dieser Pfad ein stilles Hintertuerchen an der 7-Tage-Frist vorbei.
	# Die Rechtefrage beantwortet `_resource_denied` oben (nur Admin-Rollen
	# duerfen hier loeschen) — dieselbe Schranke wie in den Endpunkten.
	from diakronos_app.papierkorb import BEREICHE as _PAPIERKORB_BEREICHE
	from diakronos_app.papierkorb import loeschen as _in_papierkorb

	if doctype in _PAPIERKORB_BEREICHE:
		try:
			get_doc(doctype, name)
			zeitpunkt = _in_papierkorb(doctype, name, von=str(frappe_session.user or ""))
		except FrappeCompatError as exc:
			return _error_response(str(exc), exc.exc_name, exc.http_status)
		return _json({
			"data": {
				"success": True,
				"name": name,
				"geloescht_am": zeitpunkt.isoformat(sep=" "),
			}
		}, status=202)

	try:
		doc = get_doc(doctype, name)
		if doctype == "Mitglied":
			from diakronos_app.frappe_compat.api_helpers import _pruefe_mitglied_schreibzugriff

			_pruefe_mitglied_schreibzugriff({}, name, loeschen=True)
		elif doctype in ("User", "Has Role"):
			# W1 (R-P1-8e): Loeschen eines Kontos oder einer Rolle darf den
			# letzten aktiven System Manager nicht aussperren.
			from diakronos_app.frappe_compat.api_helpers import _pruefe_konto_schreibzugriff

			_pruefe_konto_schreibzugriff(doctype, name, {}, loeschen=True)
	except FrappeCompatError as exc:
		return _error_response(str(exc), exc.exc_name, exc.http_status)
	sess = SessionLocal()
	try:
		obj = sess.get(model_for(doctype), name)
		if obj is None:
			return _error_response(f"{doctype} {name!r} existiert nicht", "DoesNotExistError", 404)
		if doctype == "Beitrag":
			from diakronos_app.frappe_compat.api_helpers import _beitrag_kommentare_loeschen
			_beitrag_kommentare_loeschen(sess, name)
		sess.delete(obj)
		sess.commit()
	except IntegrityError:  # BLD-04/05: 417 mit Klartext statt 500 mit rohem SQL
		# P0-1-Rest (klein): nur die Fremdschluessel-Verletzung bedeutet "wird
		# noch verwendet". Ein pauschales `except Exception` meldete auch bei
		# Verbindungs-/Programmierfehlern diese Ursache — irrefuehrend, und es
		# verschluckte den echten Fehler. Alles andere bleibt ein Fehler.
		sess.rollback()
		return _error_response(
			f"{doctype} {name!r} kann nicht gelöscht werden — der Datensatz wird "
			"noch von anderen Einträgen verwendet.",
			"ValidationError",
			417,
		)
	except Exception:  # noqa: BLE001 — unerwarteter Fehler: 417, aber generisch
		sess.rollback()
		import logging

		logging.getLogger(__name__).exception(
			"resource_delete %s %r fehlgeschlagen", doctype, name
		)
		return _error_response(
			f"{doctype} {name!r} konnte nicht gelöscht werden.",
			"ValidationError",
			417,
		)
	finally:
		sess.close()
	return _json({"data": {}}, status=202)


def _apply_resource_write(doctype: str, name: str | None, body: dict):
	"""Create/Update ueber das SQLAlchemy-Modell. Gibt dict oder Fehlerresponse."""
	from diakronos_app.db import SessionLocal

	model = model_for(doctype)
	cols = column_names(doctype)
	# SEC-5 (Pentest R2, N1): Credential-Felder gehoeren NICHT auf den
	# generischen Schreibweg. Vorher landete jeder Payload-Schluessel per
	# `setattr`/Konstruktor in der Zeile — damit war `password_hash` ueber
	# POST/PUT /api/resource/User setzbar (Mass-Assignment: Konto uebernehmen,
	# ohne das alte Passwort zu kennen). Geheimnisse setzt ausschliesslich der
	# dedizierte Weg (`api/zugang.py`, `set-password`, `passwoerter.neuer_hash`).
	# Abgelehnt wird der ganze Request (400) statt still verworfen: der Aufrufer
	# soll wissen, dass sein Schreibversuch nicht stattgefunden hat. `content_hash`
	# bleibt erlaubt (Integritaetswert, konsistent zu SEC-1).
	from diakronos_app.frappe_compat.query import ist_gesperrtes_feld

	if any(ist_gesperrtes_feld(k) for k in body):
		# Generische Meldung — der Feldname selbst wird nicht gespiegelt.
		return _error_response(
			f"{doctype} konnte nicht gespeichert werden — bitte die Eingaben "
			"prüfen.",
			"ValidationError",
			400,
		)
	payload = {k: v for k, v in body.items() if k in cols}
	from diakronos_app.frappe_compat.api_helpers import _coerce, _new_name, _normalisiere_leere_links
	payload = _coerce(doctype, _normalisiere_leere_links(doctype, payload))
	if doctype == "Mitglied" and name is None:
		# ID-1d: Die Kennung einer Person vergibt IMMER der Server. Der
		# Schnitt steht VOR der Schranke darunter, damit diese den geplanten
		# Zustand der NEUEN Zeile bewertet — mit einem Client-`name` waere das
		# ein Bestandsname, den es nicht gibt.
		payload.pop("name", None)
		payload["name"] = _new_name()
	if doctype == "Registrierungslink" and name is None:
		# SEC-3: der Token eines NEUEN Links entsteht IMMER serverseitig
		# (43 Zeichen, ~256 Bit). Der Pentest setzte hier `slug: "pt-mitglied"`
		# durch; der Wert wird jetzt verworfen. BESTEHENDE Links bleiben
		# unberuehrt — eine AENDERUNG (`name` im Pfad) fasst den Slug nicht an.
		from diakronos_app.frappe_compat.api_helpers import _registrierungslink_token

		payload = _registrierungslink_token(payload)
	if doctype == "Mitglied":
		# P1-8c (Pflicht 1): derselbe generische Weg wie `PUT /api/resource/...`
		# — der Schutz gegen Aussperren eines Verwaltungskontos und gegen das
		# Umbiegen von `Mitglied.user` gehoert hierhin.
		from diakronos_app.frappe_compat.api_helpers import (
			_normalisiere_mitglied_email,
			_pruefe_mitglied_schreibzugriff,
		)

		try:
			# SEC-c: E-Mail normalisieren + Eindeutigkeit, BEVOR die Schranke
			# den geplanten Zustand bewertet.
			payload = _normalisiere_mitglied_email(payload, name)
			_pruefe_mitglied_schreibzugriff(payload, name)
		except FrappeCompatError as exc:
			return _error_response(str(exc), exc.exc_name, exc.http_status)
	elif doctype in ("User", "Has Role"):
		# W1 (R-P1-8e): der generische Weg darf den letzten aktiven System
		# Manager nicht aussperren (Rolle weg / Konto gesperrt).
		from diakronos_app.frappe_compat.api_helpers import (
			_pruefe_konto_schreibzugriff,
		)

		try:
			_pruefe_konto_schreibzugriff(doctype, name, payload)
		except FrappeCompatError as exc:
			return _error_response(str(exc), exc.exc_name, exc.http_status)
	sess = SessionLocal()
	try:
		if name is None:
			if not payload.get("name"):
				payload["name"] = _new_name()
			obj = model(**payload)
			sess.add(obj)
		else:
			# Ein `name` im Rumpf einer AENDERUNG ist kein Umbenennen — die
			# Kennung der Zeile steht im Pfad und bleibt. Ohne diesen Schnitt
			# landete `name` als Spaltenwert in `setattr` (harmlos, aber
			# irrefuehrend) und die Zusage „Kennung nie vom Client“ waere
			# nicht an einer Stelle nachlesbar.
			payload.pop("name", None)
			obj = sess.get(model, name)
			if obj is None:
				return _error_response(f"{doctype} {name!r} existiert nicht", "DoesNotExistError", 404)
			for k, v in payload.items():
				setattr(obj, k, v)
		sess.commit()
		sess.refresh(obj)
		# SEC-1: das ganze Dict durch _serialize_payload, damit auch die KEYS
		# gegen die Sperrliste laufen — sonst leakt die POST/PUT-Antwort
		# password_hash, obwohl die Lesewege ihn filtern.
		return _serialize_payload({c.name: getattr(obj, c.name) for c in model.__table__.columns})
	except Exception as exc:
		sess.rollback()
		# BLD-04/05 (P0-1-Rest): NIE die rohe SQLAlchemy-/SQL-Meldung ausliefern.
		# `str(exc)` enthielt Tabellen-, Spalten- und Constraint-Namen (Schema-
		# Leck) und ging 1:1 an den Client. Die Ursache gehoert ins Log, der
		# Client bekommt eine verstaendliche deutsche Meldung.
		import logging

		logging.getLogger(__name__).warning(
			"resource_write %s %r fehlgeschlagen: %s", doctype, name, exc
		)
		return _error_response(
			f"{doctype} konnte nicht gespeichert werden — bitte die Eingaben "
			"prüfen.",
			"ValidationError",
			417,
		)
	finally:
		sess.close()


def mount(app) -> None:
	# API-Module laden, damit `@whitelist()`-Funktionen registriert sind.
	import importlib

	try:
		importlib.import_module("diakronos_app.api")
	except ImportError:  # pragma: no cover — vor P2b evtl. leer
		pass
	app.include_router(router)
