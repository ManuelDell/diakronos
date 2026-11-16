"""ROUTER-ALIAS — Waechter: kein SPA-Pfad bricht, kein fremdes Praefix loest auf.

Zwei Zusagen dieser Karte, beide am ECHTEN Router-Weg gemessen
(`registry.registriere_originalpfad` und `router._ist_eigener_pfad`):

  1. Jeder Methodenpfad, den die SPA aufruft, loest auf. Die Liste kommt per
     Regex aus `frontend/src` — nicht aus einer gepflegten Kopie. Damit faellt
     ein Bruch wie `diakronos.diakronos.api.mailversand.*` (Nachbesserung
     Punkt 1: die SPA war tot, die angepassten Tests hatten es verdeckt)
     sofort auf, statt erst beim Klick in der Oberflaeche.
  2. Fuer ALLE registrierten Funktionen gilt: ein fremdes Modulpraefix loest
     nicht auf — ohne Ausnahme fuer Module ohne `FRAPPE_MODULE`
     (Nachbesserung Punkt 2: `…planrahmen.api.root_uebertragen` -> root,
     `…setze_rollen` -> zugang, `…set_verantwortliche` -> verantwortliche).
"""

from __future__ import annotations

import os
import re

import pytest

#: Wurzel des Frontends — im Repo UND im Image (wie `test_sec11_methoden._werkzeug`).
_FRONTEND_KANDIDATEN = (
	"/frontend/src",
	"/repo/frontend/src",
	os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src"),
)

#: Aufrufe, die einen Methodenpfad als Literal tragen.
_AUFRUF = re.compile(
	r"(?:apiCall|apiGet|apiPost|apiPut|apiDelete|apiUrl|apiFetch)\(\s*(['\"`])([^'\"`$]+?)\1"
)
#: Ein `diakronos.*`/`frappe.*`-Literal mit mindestens einer FUNKTION am Ende
#: (`a.b.api.mod.fn`) oder ein Modul PRAEFIX (endet auf den Punkt, wird zur
#: Laufzeit mit dem Funktionsnamen verklebt: `const API = '…mailversand.'`).
#: Reine Modulbahnen ohne Funktion (`diakronos.diakonos.api.zugang`) und
#: Kommentarbeispiele (`diakronos.x.y`) sind keine Pfade und werden nicht
#: geprueft — sie sind aufloesbar, sobald ein Aufruf daraus wird.
_LITERAL = re.compile(
	r"['\"`]((?:diakronos|frappe)(?:\.[A-Za-z0-9_]+)+\.?)['\"`]"
)
#: Dateiendungen, in denen die SPA ihre Aufrufe schreibt.
_ENDUNGEN = (".js", ".mjs", ".vue")

#: Letzte Segmente, die ein MODUL/Paket benennen — ein Literal, das damit
#: endet, ist ein Praefix, an das die SPA den Funktionsnamen haengt
#: (auch per Template-String, den der Scanner nicht sieht).
_MODULNAMEN = frozenset(
	{
		"api",
		"auth",
		"admin_hub",
		"audit",
		"austritt",
		"dashboard",
		"datenschutz",
		"dienstplan",
		"einrichtung",
		"gestaltung",
		"gruppen",
		"kalender_verwaltung",
		"kanban_api",
		"mailversand",
		"mitglieder",
		"planrahmen",
		"registrierung",
		"ressourcen",
		"session",
		"sicherung",
		"user",
		"verantwortliche",
		"website",
		"wiki",
		"zugang",
	}
)


def _frontend_src() -> str:
	for pfad in _FRONTEND_KANDIDATEN:
		geprueft = os.path.abspath(pfad)
		if os.path.isdir(geprueft):
			return geprueft
	pytest.skip("frontend/src nicht gefunden — geprueft: " + ", ".join(_FRONTEND_KANDIDATEN))


def _frontend_pfade() -> list[str]:
	"""Alle Methodenpfade, die die SPA aufruft (sortiert, ohne Dubletten).

	Gesammelt werden die Formen, die zur Laufzeit WIRKLICH einen Request
	ausloesen: das Argument eines `apiCall('…')`/`apiUrl('…')` und jedes
	`diakronos.*`-Literal, an das die SPA einen Funktionsnamen haengt
	(Constants wie `const API = 'diakronos.diakonos.api.austritt'` oder
	`const API = 'diakronos.diakronos.api.mailversand.'` — genau ein solches
	Konstantenpraefix war in der Nachbesserung der Bruch).

	Was NICHT in die Liste gehoert: erfundene Beispielpfade in Kommentaren
	(`apiUrl('diakronos.x.y')` in der Doku von `shared/basis.js`) und
	Modulbahnen ohne Funktion. Beide wuerden den Test nur mit Rauschen fuellen.
	"""
	wurzel = _frontend_src()
	gefunden: set[str] = set()
	for ordner, _unterordner, dateien in os.walk(wurzel):
		for datei in dateien:
			if not datei.endswith(_ENDUNGEN):
				continue
			with open(os.path.join(ordner, datei), encoding="utf-8") as fh:
				text = fh.read()
			for treffer in _AUFRUF.finditer(text):
				gefunden.add(treffer.group(2))
			for treffer in _LITERAL.finditer(text):
				# Ein Literal ist ein REQUEST-Pfad, wenn ein Funktionsname folgt:
				# die Datei haengt ihn per +`'/'+name` oder per Template-String
				# direkt an (`mos.lesen` als Literal, `mailversand.` als Praefix).
				# Beispielpfade in Kommentaren (`diakronos.x.y`) und Modulbahnen
				# ohne Funktion fuellen den Test nur mit Rauschen.
				wert = treffer.group(1)
				segmente = wert.rstrip(".").split(".")
				if wert.endswith(".") or (len(segmente) >= 3 and "api" in segmente):
					gefunden.add(wert)
	# Platzhalter (`${…}`) sind keine Pfade; `POST` ist ein HTTP-Verb, kein Pfad.
	return sorted(p for p in gefunden if "${" not in p and "." in p)


def _ist_modulebene(path: str) -> bool:
	"""True, wenn der Pfad MEHRERE Modulebenen hat, aber keine Funktion.

	`diakronos.devmodus.api` und `diakronos.diakonos.api.zugang` enden auf
	einem Paket/Praefix, an das die SPA den Funktionsnamen haengt (auch ueber
	einen Template-String, der dem Scanner nicht sichtbar ist). Solche Bahnen
	sind keine Aufrufe und werden hier nicht geprueft. `diakronos.x.y` ist
	Doku-Prosa und ebenso wenig ein Aufruf.
	"""
	letztes = path.rstrip(".").rsplit(".", 1)[-1]
	if path.endswith("."):
		return True
	return letztes in _MODULNAMEN


def _register_vollstaendig() -> None:
	from diakronos_app.main import app  # noqa: F401

	# Der Dev-Modus registriert seine Endpunkte erst auf Anforderung
	# (`registriere()`), wie im Betrieb auch.
	try:
		from diakronos_app.devmodus import api as devmodus_api

		devmodus_api.registriere()
	except Exception:  # noqa: BLE001 — ohne Dev-Modus gibt es diese Module nicht
		pass


def _loest_auf(path: str) -> bool:
	from diakronos_app.frappe_compat.registry import lookup, registriere_originalpfad
	from diakronos_app.frappe_compat.router import _ist_eigener_pfad

	registriere_originalpfad(path)  # ergaenzt nichts, beantwortet nur
	return _ist_eigener_pfad(path) or lookup(path) is not None


# ── (1) Waechter: die SPA darf keinen Pfad verlieren ──────────────────────


def test_alle_frontend_methodenpfade_loesen_auf():
	"""Jeder in `frontend/src` aufgerufene Methodenpfad ist erreichbar.

	Der Test liest die Pfade aus dem Quellbaum. Findet er zu wenige, ist der
	Scanner kaputt — das ist ein Fehlschlag, kein Grund zum Ueberspringen.
	"""
	_register_vollstaendig()
	pfade = _frontend_pfade()
	assert len(pfade) >= 100, f"zu wenige Frontend-Pfade gefunden ({len(pfade)}) — Scanner pruefen"
	tot = [p for p in pfade if p != "diakronos.x.y" and not _ist_modulebene(p) and not _loest_auf(p)]
	assert tot == [], f"{len(tot)} SPA-Pfad(e) geben 404:\n" + "\n".join(tot)


@pytest.mark.parametrize(
	"pfad",
	[
		# Nachbesserung Punkt 1: genau diese vier Aufrufe waren tot, weil die
		# Tests die Pfade auf die FRAPPE_MODULE-Bahn „korrigiert“ hatten.
		"diakronos.diakronos.api.mailversand.mailversand_get",
		"diakronos.diakronos.api.mailversand.mailversand_speichern",
		"diakronos.diakronos.api.mailversand.mailversand_testmail",
		"diakronos.diakronos.api.mailversand.mailversand_status",
		"diakronos.diakronos.api.gestaltung.lesen",
		"diakronos.diakronos.api.gestaltung.speichern",
		"diakronos.diakronos.api.gestaltung.zuruecksetzen",
		"diakronos.diakronos.api.admin_hub.get_dsgvo_uebersicht",
		# ... und die dokumentierte Bahn derselben Funktionen bleibt offen.
		"diakronos.diakonos.api.mailversand.mailversand_status",
		"diakronos.diakonos.api.admin_hub.get_dsgvo_uebersicht",
	],
)
def test_spa_aliase_loesen_auf(pfad):
	"""Die Aliase der SPA sind AUSDRUECKLICH eingetragen, nicht zufaellig."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat.registry import lookup

	assert lookup(pfad) is not None, f"{pfad} fehlt im Register"
	assert _loest_auf(pfad) is True, pfad


def test_spa_alias_per_http_antwortet(client, patched_db):
	"""HTTP-Gegenprobe: der SPA-Pfad erreicht die Fachfunktion (kein 404)."""
	_register_vollstaendig()
	antwort = client.get("/api/method/diakronos.diakronos.api.mailversand.mailversand_status")
	assert antwort.status_code != 404, antwort.text
	assert antwort.json().get("exc_type") != "NotFound", antwort.text


# ── (2) Flaechendeckend: kein fremdes Modulpraefix, keine Ausnahme ────────


def test_flaeche_ohne_ausnahme_kein_fremdes_praefix():
	"""Fuer JEDE registrierte Funktion bleibt ein fremdes Praefix 404.

	Kein `continue` fuer Module ohne `FRAPPE_MODULE`: der Freibrief
	(`frappe_module is None -> True`) ist der Kernbefund, nicht der Randfall.
	Geprueft werden die Bahnen, die der alte Weg verwechselt haette:

	  * `diakronos.planrahmen.api.<name>` (vorletztes Segment `api`),
	  * `<fremdes Kurzmodul>.api.<name>`,
	  * `<eigenes Kurzmodul>.fremd.<name>`.
	"""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import registry

	register = registry.registered()
	vorher = dict(register)
	gesehen: set[int] = set()
	fremd_aufgeloest: list[str] = []
	geprueft = 0
	for pfad, fn in sorted(register.items()):
		if id(fn) in gesehen:
			continue  # eine Funktion je Runde — der Rest sind Aliasse
		gesehen.add(id(fn))
		if registry._ist_login(fn):  # noqa: SLF001
			# LOGIN-4/A: der Login loest absichtlich unter jedem Praefix auf
			# (Sperren haengen am Funktionsobjekt). Eigener Test unten.
			continue
		name = getattr(fn, "__name__", "")
		module = getattr(fn, "__module__", "") or ""
		if not name or not module.startswith("diakronos_app."):
			continue
		# Pfade, die dieser Funktion GEHOEREN, sind keine Verwechslung.
		eigen = registry._original_pfade(fn)  # noqa: SLF001 — Gegenprobe im Test
		kurz = module.split(".")[-1]
		for fremd in (
			f"diakronos.planrahmen.api.{name}",
			f"{kurz}.api.{name}",
			f"{kurz}.fremd.{name}",
		):
			if fremd in eigen or fremd in register:
				continue
			geprueft += 1
			if registry.registriere_originalpfad(fremd):
				fremd_aufgeloest.append(f"{fremd} -> {module}.{name}")
			from diakronos_app.frappe_compat.router import _ist_eigener_pfad

			if _ist_eigener_pfad(fremd):
				fremd_aufgeloest.append(f"{fremd} (Router) -> {module}.{name}")
	assert geprueft >= 300, f"zu wenige Pruefungen ({geprueft}) — Testaufbau pruefen"
	assert fremd_aufgeloest == [], (
		f"{len(fremd_aufgeloest)} fremde(s) Praefix loest auf:\n"
		+ "\n".join(fremd_aufgeloest[:20])
	)
	# Und die Pruefung selbst hat das Register nicht veraendert.
	neu = {p for p in registry.registered() if p not in vorher}
	assert neu == set(), f"Register durch Anfragen gewachsen: {sorted(neu)[:10]}"


@pytest.mark.parametrize(
	"name",
	# Nachbesserung Punkt 2: diese Namen loesten aus ihren fremden Modulen auf,
	# weil ihr Modul kein `FRAPPE_MODULE` trug (Freibrief).
	["root_uebertragen", "setze_rollen", "set_verantwortliche", "liste", "status", "schritt_setzen"],
)
def test_kein_freibrief_ohne_frappe_module(name):
	"""Module ohne `FRAPPE_MODULE` bekommen keinen Freibrief mehr."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import registry
	from diakronos_app.frappe_compat.router import _ist_eigener_pfad

	for fremd in (f"diakronos.planrahmen.api.{name}", f"x.y.api.{name}", f"fremd.{name}"):
		assert registry.registriere_originalpfad(fremd) is False, fremd
		assert _ist_eigener_pfad(fremd) is False, fremd
		assert registry.lookup(fremd) is None, fremd


@pytest.mark.parametrize(
	"pfad",
	# Punkt 3 der Nachbesserung: Kernnamen loesten unter jedem Praefix auf.
	# AUSNAHME `login`: LOGIN-4/A verlangt ausdruecklich, dass der Login unter
	# JEDEM Praefix dieselben Sperren traegt (erkannt am Funktionsobjekt) —
	# deshalb geprueft mit `logout`, das diese Ausnahme NICHT hat.
	["x.y.auth.logout", "diakronos.planrahmen.api.logout", "a.b.c.logout",
	 "x.y.api.insert", "x.y.frappe.client.insert"],
)
def test_kernnamen_nur_unter_ihrer_schreibweise(pfad):
	"""`logout`/`insert` gibt es nur unter den Pfaden aus `_KERNPFADE`."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import registry
	from diakronos_app.frappe_compat.router import _ist_eigener_pfad

	vorher = len(registry.registered())
	assert registry.registriere_originalpfad(pfad) is False, pfad
	assert _ist_eigener_pfad(pfad) is False, pfad
	# Punkt 3: die Anfrage darf NICHTS dauerhaft eintragen.
	assert registry.lookup(pfad) is None, pfad
	assert len(registry.registered()) == vorher, "Register durch eine Anfrage gewachsen"


@pytest.mark.parametrize("pfad", ["x.auth.login", "beliebig.tief.auth.login", "api.login"])
def test_login_bleibt_unter_jedem_praefix_erreichbar(pfad):
	"""LOGIN-4/A: Login-Aliase bleiben offen — die Sperren haengen am Objekt.

	Dokumentierte SICHERHEITS-Ausnahme dieser Karte, nicht der Befund: der
	Router behandelt jeden `login`-Alias wie `login` (Nur-POST, `usr`/`pwd`
	nur aus dem Body, Herkunft). `test_login4_aliaspfade.py` prueft das
	Verhalten; hier steht nur, dass die Ausnahme NICHT stillschweigend
	verschwindet.
	"""
	_register_vollstaendig()
	from diakronos_app.api.auth import login
	from diakronos_app.frappe_compat import registry

	assert registry.ist_originalpfad(pfad, login) is True, pfad
	assert registry.registriere_originalpfad(pfad) is True, pfad


def test_kernpfade_bleiben_offen(client, patched_db):
	"""Die benutzten Schreibweisen der Kernpfade loesen weiter auf (kein 404)."""
	_register_vollstaendig()
	for pfad in ("logout", "frappe.login", "frappe.login.login"):
		antwort = client.post(f"/api/method/{pfad}")
		assert antwort.json().get("exc_type") != "NotFound", (pfad, antwort.text)


# ── (3) Nachtrag R-7 (2026-11): Zusagen, die der Vorlauf nicht kannte ─────
#
# Zwei Wege sind SEIT dem Merge mit main dazugekommen und standen unter einer
# Bahn, die weder `FRAPPE_MODULE` noch der Python-Pfad ergibt:
#
#   * `diakronos.api.rechte.*` — das Rechte-Frontend (`ModerationAntraege.vue`,
#     `freigabeStufen.mjs`). Zugesagt ueber `praefix_zusagen` IM API-Modul.
#   * `frappe.sessions.get_csrf_token` — die Gastseite holt dort den Token nach
#     (`gastinhalt/App.vue`); die Funktion ist `api.session.sitzung_status`.
#
# Beide bleiben AUSDRUECKLICHE Zusagen: ein fremdes Praefix auf denselben
# Namen loest weiterhin nicht auf.


@pytest.mark.parametrize(
	"pfad",
	[
		"diakronos.api.rechte.get_rollen_erklaerung",
		"diakronos.api.rechte.get_offene_sichtbarkeits_antraege",
		"diakronos.api.rechte.entscheide_sichtbarkeit",
		"frappe.sessions.get_csrf_token",
	],
)
def test_nachtrag_r7_pfade_loesen_auf(pfad):
	"""Die zwei Nachzuegler aus dem main-Merge sind erreichbar (kein 404)."""
	_register_vollstaendig()
	assert _loest_auf(pfad) is True, pfad


@pytest.mark.parametrize(
	"fremd",
	[
		# `praefix_zusagen` gilt fuer EINE Bahn, nicht fuer „irgendein Praefix“.
		"diakronos.planrahmen.api.get_rollen_erklaerung",
		"x.y.api.get_rollen_erklaerung",
		"diakronos.diakronos.api.rechte.get_rollen_erklaerung",
		# Die CSRF-Adresse ist ein Kernpfad, keine Bahn fuer andere Namen.
		"x.y.sessions.get_csrf_token",
		"diakronos.api.session.get_csrf_token",
	],
)
def test_nachtrag_r7_fremdes_praefix_bleibt_404(fremd):
	"""Die Zusagen oeffnen genau ihre Bahn — kein Freibrief fuer andere."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import registry
	from diakronos_app.frappe_compat.router import _ist_eigener_pfad

	vorher = len(registry.registered())
	assert registry.registriere_originalpfad(fremd) is False, fremd
	assert _ist_eigener_pfad(fremd) is False, fremd
	assert registry.lookup(fremd) is None, fremd
	assert len(registry.registered()) == vorher, "Register durch eine Anfrage gewachsen"


def test_nachtrag_r7_csrf_token_per_http(client, patched_db):
	"""HTTP-Gegenprobe: die Gastseite bekommt ihre Antwort, keinen 404.

	Ohne Sitzung ist die ehrliche Antwort 401 `SessionExpired` (kein Token
	erfinden) — geprueft wird hier nur, dass der PFAD aufloest.
	"""
	_register_vollstaendig()
	antwort = client.post("/api/method/frappe.sessions.get_csrf_token", json={})
	assert antwort.json().get("exc_type") != "NotFound", antwort.text
