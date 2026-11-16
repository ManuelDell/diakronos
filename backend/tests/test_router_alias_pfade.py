"""ROUTER-ALIAS — ein Methodenpfad loest nur auf, was ihm gehoert.

Befund (Claude, beim Rechte-Umbau R-7): Der Router loeste Methodenpfade
moduluebergreifend auf. `registriere_originalpfad` nahm das VORLETZTE
Pfadsegment als Kurzmodul; `diakronos.planrahmen.api.delete_lied` wurde so zu
„Modul `api`, Funktion `delete_lied`“ und fuehrte die gleichnamige Funktion
aus einem fremden Modul aus (`diakronos_app.api.psalmos.musik.delete_lied`).
Keine Rechte-Umgehung — die Funktion prueft selbst —, aber Pfadverwirrung:
der Endpunkt erschien unter einem Modul, zu dem er nicht gehoert (Audit,
Inventar, Methoden-/CSRF-Regeln je Pfad).

Die Zusagen dieses Tests:

  1. `diakronos.planrahmen.api.delete_lied` ist 404 (und loescht nichts).
  2. Bekannte Original-Pfade loesen weiter auf (auch per HTTP).
  3. Fuer JEDE registrierte Funktion gilt: kein fremdes Modulpraefix loest
     auf — so geprueft, wie der Router es wirklich fragt
     (`registriere_originalpfad` und `router._ist_eigener_pfad`).
"""

from __future__ import annotations

import pytest

PLANRAHMEN_PFAD = "diakronos.planrahmen.api"
FREMDER_NAME = "delete_lied"

#: Bekannte Original-Pfade, die aufloesen MUESSEN (Frappe-Bahn der Funktion).
BEKANNT = [
	"diakronos.diakonos.api.admin_hub.get_statistik",
	"diakronos.kronos.api.calendar_get.get_accessible_calendars",
]


def _register_vollstaendig() -> None:
	"""Importiert die App, damit das Register vollstaendig gefuellt ist."""
	from diakronos_app.main import app  # noqa: F401


def _eigener_pfad(path: str) -> bool:
	"""Der Weg, den der Router vor jeder Aufloesung fragt."""
	from diakronos_app.frappe_compat.router import _ist_eigener_pfad

	return _ist_eigener_pfad(path)


def _kernfunktion(fn) -> bool:
	"""Frappe-Kernfunktion (`login`, `logout`, `insert` …)?

	Ihr Modul traegt keine `FRAPPE_MODULE`-Konstante oder eine ohne
	Modulumfang (z. B. `frappe.login`). Der Router erreicht sie absichtlich
	unter jedem Praefix, solange der Name exakt stimmt (LOGIN-4/A) — sie sind
	nicht der Befund dieser Karte.
	"""
	from diakronos_app.frappe_compat import registry

	modul = registry._original_modul(fn)
	return modul is None or "." not in modul


def _kernname(name: str) -> bool:
	"""Heisst eine Frappe-KERNfunktion so? (dann gilt fuer den Namen LOGIN-4/A)

	Die Kernnamen stehen fest: der Router behandelt sie unabhaengig von der
	Registrierung als Kernpfade (`router._LOGIN_PFADE`, `api.auth.login`).
	"""
	from diakronos_app.frappe_compat import registry

	if not name:
		return False
	# Die Kernnamen stehen fest (der Router behandelt sie unabhaengig von der
	# Registrierung als Kernpfade).
	if name in {"login", "logout", "insert", "get_list", "get_value", "set_value"}:
		return True
	return any(
		getattr(fn, "__name__", None) == name and _kernfunktion(fn)
		for fn in registry.registered().values()
	)


# ── (1) Der Befund: das fremde Praefix loest nicht mehr auf ────────────────


def test_planrahmen_praefix_loest_nicht_mehr_auf():
	"""Genau der nachgestellte Befund — jetzt False und kein Register-Eintrag."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat.registry import lookup, registriere_originalpfad

	pfad = f"{PLANRAHMEN_PFAD}.{FREMDER_NAME}"
	# Vorbedingung: die Funktion EXISTIERT (in einem fremden Modul) — sonst
	# waere der Test trivial gruen.
	assert lookup(f"musik.{FREMDER_NAME}") is not None, "Vorbedingung: musik.delete_lied fehlt"
	assert lookup(pfad) is None, "Pfad steht schon im Register — Testaufbau pruefen"
	assert registriere_originalpfad(pfad) is False, (
		f"{pfad} loest auf eine fremde Funktion auf"
	)
	assert lookup(pfad) is None, f"{pfad} wurde trotzdem eingetragen"
	assert _eigener_pfad(pfad) is False


def test_planrahmen_pfad_per_http_ist_404(client, patched_db):
	"""Ueber HTTP: 404 fuer den fremden Pfad, ohne Anmeldung.

	Das ist die Stelle aus `test_li1_lied_anlegen_bearbeiten`: „unter dem
	Planrahmen-Pfad gibt es kein delete_lied“. Nach dem Fix antwortet sie 404
	(frueher lief sie in die Rechtepruefung des fremden Endpunkts, 403).
	"""
	_register_vollstaendig()
	antwort = client.post(
		f"/api/method/{PLANRAHMEN_PFAD}.{FREMDER_NAME}",
		json={"plantyp": "chorplan", "lied": "LIED-1"},
	)
	assert antwort.status_code == 404, antwort.text


# ── (2) Die echten Original-Pfade bleiben erreichbar ──────────────────────


@pytest.mark.parametrize("pfad", BEKANNT)
def test_bekannte_originalpfade_loesen_weiter_auf(pfad):
	from diakronos_app.frappe_compat.registry import lookup, registriere_originalpfad

	_register_vollstaendig()
	ziel = lookup(pfad)
	assert ziel is not None, f"{pfad} fehlt im Register"
	assert registriere_originalpfad(pfad) is True, pfad
	assert lookup(pfad) is ziel


def test_originalpfad_per_http_antwortet(client, patched_db):
	"""Der Weg der SPA bleibt offen (kein 404 durch die neue Pruefung)."""
	_register_vollstaendig()
	antwort = client.get("/api/method/diakronos.diakonos.api.admin_hub.get_statistik")
	# Die Fachfunktion laeuft (die Fachpruefung antwortet 403 fuer einen
	# Nicht-Administrator) — entscheidend: KEIN 404 durch die Pfadpruefung.
	assert antwort.status_code != 404, antwort.text
	assert antwort.json().get("exc_type") != "NotFound", antwort.text


# ── (3) Flaechendeckend: kein fremdes Modulpraefix ────────────────────────


def test_kein_fremdes_modulpraefix_loest_auf():
	"""Fuer JEDE registrierte Funktion: ein fremdes Praefix bleibt 404.

	Gefragt wird zweimal, so wie der Router es tut:

	  * `registriere_originalpfad(<fremdes Praefix>)` darf NICHTS eintragen,
	  * `router._ist_eigener_pfad(<fremdes Praefix>)` darf nicht True werden,
	    solange der Pfad nicht im Register steht.

	Geprueft gegen die Pfade, die das fruehere Verfahren verwechselt haette:
	`diakronos.planrahmen.api.<name>` (vorletztes Segment `api` — dort suchte
	der Fallback `api.<name>`) und `<kurzmodul>.fremd.<name>`.

	Ausgenommen sind Frappe-Kernfunktionen (`login`, `logout`, `insert` …):
	der Router erreicht sie absichtlich unter jedem Praefix, solange der Name
	exakt stimmt (LOGIN-4/A).
	"""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import registry

	register = registry.registered()
	vorher = dict(register)
	ist_original = registry.ist_originalpfad
	verwechslungen: list[str] = []
	geprueft = 0
	for pfad, fn in sorted(register.items()):
		if pfad != f"{getattr(fn, '__module__', '')}.{getattr(fn, '__name__', '')}":
			continue  # nur eine Funktion je (Modul, Name) — der Rest sind Aliasse
		if _kernfunktion(fn):
			continue
		name = getattr(fn, "__name__", "")
		if _kernname(name):
			continue
		modul = getattr(fn, "__module__", "")
		if not modul.startswith("diakronos_app.api."):
			continue
		kurz = modul[len("diakronos_app.api."):].split(".")[0]
		# Die Funktion, die das ALTE Verfahren gefunden haette (`api.<name>`).
		alt = register.get(f"api.{name}") or fn
		geprueft += 1
		# (a) Das frueher verwechselte Praefix (`api` als Kurzmodul).
		fremd = f"{PLANRAHMEN_PFAD}.{name}"
		ziel = register.get(fremd)
		if ziel is not None:
			# Wer dort steht, MUSS dorthin gehoeren — sonst ist es genau die
			# Pfadverwirrung aus dem Befund.
			if not ist_original(fremd, ziel):
				verwechslungen.append(f"{fremd} -> {getattr(ziel, '__module__', '?')}")
			assert _eigener_pfad(fremd) is True, fremd
		else:
			if registry.registriere_originalpfad(fremd):
				verwechslungen.append(fremd)
			# `registriere_originalpfad` setzt fuer Kernnamen (`login`, `logout`)
			# bewusst `<praefix>.<name>` (LOGIN-4/A) — das ist KEINE Verwechslung
			# dieser Karte, deshalb bleibt der Aufruf hier aussen vor.
			pass
		# (b) Ein Praefix, das diese Funktion nie belegen kann. `_eigener_pfad`
		#     fragt das REGISTER (jeder dort eingetragene Pfad ist erlaubt) —
		#     hier zaehlt die Zuordnung selbst: `ist_originalpfad`.
		fremd2 = f"{kurz}.fremd.{name}"
		if not _kernfunktion(fn) and not _kernfunktion(alt):
			assert ist_original(fremd2, fn) is False, fremd2
			assert ist_original(fremd2, alt) is False, fremd2
			assert registry.registriere_originalpfad(fremd2) is False, fremd2
	assert geprueft >= 100, f"zu wenige Pruefungen ({geprueft}) — Testaufbau pruefen"
	assert verwechslungen == [], f"fremdes Praefix loest auf: {verwechslungen[:10]}"
	# Und das Register ist durch die Pruefung nicht gewachsen.
	neu = {p for p in registry.registered() if p not in vorher}
	assert not any(p.startswith(f"{PLANRAHMEN_PFAD}.") for p in neu), sorted(neu)[:10]


def test_kein_fremdes_praefix_fuer_musiknamen():
	"""Alle Namen der Musikdatenbank unter dem Planrahmen-Praefix: 404."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import registry

	musik = [
		pfad
		for pfad, fn in registry.registered().items()
		if getattr(fn, "__module__", "") == "diakronos_app.api.psalmos.musik"
	]
	assert musik, "Vorbedingung: Musikdatenbank nicht registriert"
	loesten_auf = []
	for pfad in sorted(musik):
		name = pfad.split(".")[-1]
		fremd = f"{PLANRAHMEN_PFAD}.{name}"
		if registry.registriere_originalpfad(fremd):
			loesten_auf.append(fremd)
		assert _eigener_pfad(fremd) is False, fremd
		assert registry.lookup(fremd) is None, fremd
	assert loesten_auf == [], f"Musikendpunkte unter dem Planrahmen-Pfad: {loesten_auf}"


def test_ist_originalpfad_lehnt_fremde_praefixe_ab():
	"""Die Pruefung selbst: eigene Pfade ja, fremde nein."""
	_register_vollstaendig()
	from diakronos_app.frappe_compat.registry import ist_originalpfad, lookup

	fn = lookup("diakronos.diakonos.api.admin_hub.get_statistik")
	assert fn is not None
	assert ist_originalpfad("diakronos.diakonos.api.admin_hub.get_statistik", fn) is True
	assert ist_originalpfad("diakronos_app.api.admin_hub.get_statistik", fn) is True
	assert ist_originalpfad("diakronos.planrahmen.api.get_statistik", fn) is False
	assert ist_originalpfad("x.y.api.get_statistik", fn) is False
	assert ist_originalpfad("admin_hub.get_statistik", fn) is False
	assert ist_originalpfad("", fn) is False
	assert ist_originalpfad("diakronos.diakonos.api.admin_hub.get_statistik", None) is False


def test_ausdruecklicher_reexport_bleibt_erlaubt():
	"""Ein ueber `register_with_frappe_module` eingetragener Alias ist erlaubt.

	Das ist der EINZIGE Weg, auf dem ein Pfad entstehen darf, der nicht der
	Original-Pfad der Funktion ist (Altcode-Re-Export, z. B.
	`diakronos.kronos.api.calendar_get.get_accessible_calendars`).
	"""
	_register_vollstaendig()
	from diakronos_app.frappe_compat.registry import ist_originalpfad, lookup

	fn = lookup("diakronos.kronos.api.permissions.get_accessible_calendars")
	assert fn is not None
	assert ist_originalpfad("diakronos.kronos.api.calendar_get.get_accessible_calendars", fn) is True
	# Die Zusage deckt NUR den eingetragenen Namen, nicht das ganze Modul.
	assert ist_originalpfad("diakronos.kronos.api.calendar_get.get_calendar_events", fn) is False
