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
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.responses import Response

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


def _error_response(msg: str, exc_name: str, status: int) -> JSONResponse:
	return JSONResponse(status_code=status, content={"message": str(msg), "exception": exc_name, "exc_type": exc_name})


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
	"""False, wenn dieser Aufruf die HTTP-Methode nicht annimmt."""
	if not _ist_login_zugang(path, fn):
		return True
	return str(getattr(request, "method", "") or "").upper() in _LOGIN_METHODEN



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


@router.api_route("/method/{path:path}", methods=["GET", "POST", "PUT", "PATCH"], operation_id="call_method")
async def call_method(path: str, request: Request):
	fn = lookup(path)
	if fn is None:
		# Fallback: Modul importieren (registriert die Funktionen).
		_maybe_import(path)
		fn = lookup(path)
	if fn is None:
		return _error_response(f"Methode {path!r} nicht gefunden", "NotFound", 404)

	# LOGIN-3/H1(a): Der Login nimmt NUR POST an. Eine GET-Anmeldung ist der
	# klassische CSRF-Weg ohne Formular (`<img src="/api/method/login?usr=…&pwd=…">`,
	# geteilter Link): sie traegt keinen `Origin` und faellt nicht unter die
	# CSRF-Middleware. Ein Browser, der navigiert, landet auf der Anmeldemaske;
	# ein Skript bekommt 405. In beiden Faellen wird KEINE Sitzung gesetzt.
	if not _methode_erlaubt(path, fn, request):
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
			logger.info("Login per %s abgewiesen; zur Anmeldemaske.", request.method)
			return antwort
		return JSONResponse(
			status_code=405,
			content={
				"message": "Diese Methode ist fuer diesen Endpunkt nicht erlaubt.",
				"exception": "MethodNotAllowed",
				"exc_type": "MethodNotAllowed",
			},
			headers={"Allow": "POST"},
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
		return _error_response(str(exc), exc.exc_name, exc.http_status)
	except TypeError as exc:
		return _error_response(f"Falsche Argumente fuer {path}: {exc}", "ValidationError", 417)
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


def _serialize_payload(value: Any) -> Any:
	"""Antwortwert JSON-faehig machen (Datetime/Decimal/Document/ORM-Objekte)."""
	from datetime import date, datetime, time
	from decimal import Decimal

	if value is None or isinstance(value, (str, int, float, bool)):
		return value
	if isinstance(value, (datetime, date, time)):
		return str(value)
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, dict):
		return {k: _serialize_payload(v) for k, v in value.items()}
	if isinstance(value, (list, tuple, set)):
		return [_serialize_payload(v) for v in value]
	if hasattr(value, "as_dict"):
		return _serialize_payload(value.as_dict())
	if hasattr(value, "__table__"):
		return {c.name: _serialize_payload(getattr(value, c.name)) for c in value.__table__.columns}
	return value


# ── /api/resource/<doctype>[/<name>] ────────────────────────────────────────


def _private_resource_denied(doctype: str) -> bool:
	# Hotfix 2026-10-16 (Nachtpruefung BLD-R1): ohne Anmeldung nie; Konten/Rollen nur Admins.
	if frappe_session.user == "Guest":
		return True
	if doctype in {"User", "Has Role"}:
		from diakronos_app.frappe_compat.permissions import get_roles
		return "System Manager" not in set(get_roles())
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
	"""Admin-Kurzschluss (dieselben Rollen wie `permissions.ADMIN_ROLES`)."""
	from diakronos_app.frappe_compat.permissions import ADMIN_ROLES, get_roles

	user = frappe_session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	return bool(set(ADMIN_ROLES) & set(get_roles(user)))


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
		from diakronos_app.frappe_compat.permissions import get_roles
		if "System Manager" not in set(get_roles()):
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
		return {c.name: _serialize_payload(getattr(obj, c.name)) for c in model.__table__.columns}
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
