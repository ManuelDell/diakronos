"""ROUTER-ALIAS-d — Waechter: jeder Methodenpfad aus `tools/` ist erreichbar.

Die Probe- und Abnahme-Skripte in `tools/` rufen die API wie die SPA
(`apiCall('…')`, `ruf('…')`, `fetch('/api/method/…')`). Sie laufen nur von
Hand und werden nicht bei jedem Merge ausgefuehrt — ein toter Pfad bleibt
dort am laengsten unbemerkt: `frontend/src` faellt im Betrieb auf, ein
Abnahme-Skript erst Wochen spaeter (`bs1d-abnahme.py` rief monatelang einen
Pfad, den es auf main nie gab).

Geprueft wird deshalb NICHT gegen eine gepflegte Liste, sondern gegen die
Pfade, die im Quelltext stehen — und zwar am ECHTEN Router (`TestClient`,
angemeldet als Administrator, GET und POST). Ein Router-404 („Methode nicht
gefunden“) oder ein „Methode nicht gefunden“ im Koerper ist ein Befund.

Gescannt wird `tools/` — im Repo (`../../tools`) und im Wegwerf-Container
(`/repo/tools`), weil die Tests dort aus `/repo/backend` laufen.
"""

from __future__ import annotations

import os
import re

import pytest

_TOOLS_KANDIDATEN = (
	"/repo/tools",
	"/tools",
	os.path.join(os.path.dirname(__file__), "..", "..", "tools"),
)

#: Aufrufer mit Methodenpfad als LITERAL. Die Tools schreiben vier Formen:
#:
#:   `ruf('diakronos.…', {…})`            (fix4-tabellen-aktionen.mjs)
#:   `apiCall('diakronos.…')`             (wie die SPA)
#:   `fetch('/api/method/diakronos.…')`   (nackter Pfad, u. a. bs1d)
#:   `ruf(API + 'name')`                  (Bauform, Praefix aus der Datei)
_AUFRUF = re.compile(
	r"(?:apiCall|apiGet|apiPost|apiPut|apiDelete|apiUrl|apiFetch|ruf)\("
	r"\s*[`'\"]([A-Za-z0-9_.]+)[`'\"]"
)
_API_METHOD = re.compile(r"api/method/([A-Za-z0-9_.]+)")
#: `method: '<pfad>'` — die Objektform (`frappe.call({method: …})`). Ein
#: HTTP-VERB (`method: 'POST'`) ist kein Pfad und faellt unten heraus.
_OBJEKT = re.compile(r"method\s*:\s*[`'\"]([A-Za-z0-9_.]+)[`'\"]")
#: Die Bahn einer Datei fuer die Bauform `ruf(API + '<fn>')` — benannt
#: (`PRAEFIX`) oder als Frappe-Konstante (`const API = 'diakronos.…api.x.'`).
_PRAEFIX = re.compile(
	r"(?:const|let|var)\s+(PRAEFIX|[A-Z][A-Z0-9_]*)\s*=\s*[`'\"]([A-Za-z0-9_.]+\.)[`'\"]"
)
_PRAEFIX_BAU = re.compile(r"ruf\(\s*(PRAEFIX|[A-Z][A-Z0-9_]*)\s*\+\s*[`'\"]([A-Za-z0-9_]+)[`'\"]")

#: HTTP-Verben — ein `method:` mit diesem Wert beschreibt die Methode, nicht
#: den Pfad.
_VERBEN = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"})

#: Endungen, in denen ein Aufruf stehen kann. TABELLEN-Daten (.tsv, .json,
#: .txt) sind Protokolle/Erwartungswerte, keine Aufrufe — ein `api/method/…`
#: darin ist Vergangenheit, kein lebender Pfad.
_ENDUNGEN = (".js", ".mjs", ".cjs", ".py", ".sh", ".html", ".vue", ".ts")

#: Pfade, die BEWUSST 404 sein MUESSEN — mit Begruendung, damit die Ausnahme
#: nicht stillschweigend waechst.
_ERWARTET_404 = {
	"diakronos.diakronos.api.website.kalender_oeffentlich": (
		"bs1d-abnahme.py prueft den FEHLENDEN oeffentlichen Baustein: A3/A7 "
		"erwarten dort 404 („oeffentlicher Baustein existiert noch nicht“). "
		"Umstellen auf die echte Bahn waere genau das, was das Skript "
		"ausschliessen soll. Der oeffentliche Lesezugriff heisst heute "
		"`website.oeffentlich.kalender` (oeffentlich_api.py, allow_guest) und "
		"liegt NICHT unter dieser Adresse."
	),
	"diakronos.devmodus.api.uebersicht": (
		"Der Dev-Modus ist im Betrieb AUS; `devmodus/api.py` registriert seine "
		"Endpunkte dann nicht, der Router antwortet 404. Drei Abnahme-Skripte "
		"(abnahme_n5_browser.py, abnahme_n5_oidc_browser.py, "
		"p11b_browser_abnahme.py) erwarten diesen 404 AUSDRUECKLICH als "
		"Normalfall und fuehren ihn als bekannten Befund — die SPA faengt ihn "
		"ab (composables/useDevmodus.js)."
	),
}


def _tools_wurzel() -> str:
	for pfad in _TOOLS_KANDIDATEN:
		geprueft = os.path.abspath(pfad)
		if os.path.isdir(geprueft):
			return geprueft
	pytest.skip("tools/ nicht gefunden — geprueft: " + ", ".join(_TOOLS_KANDIDATEN))


def _ist_pfad(wert: str) -> bool:
	"""True, wenn das Literal ein VOLLSTAENDIGER Methodenpfad ist.

	Ausgeschlossen: Module (ohne Punkt, z. B. `firebase`), HTTP-Verben,
	Platzhalter (`dotted.path`) und blosse Modulbahnen ohne Funktionsnamen
	(`diakronos.diakonos.api`, `…api.gruppen.`) — die sind Praefix fuer eine
	Bauform, kein Aufruf. Eine Bahn MIT Funktionsnamen (`…event_crud`) ist
	kein Aufruf entweder — sie wird unten als MODULBAHN ausgeschlossen.
	"""
	if not wert or wert in _VERBEN:
		return False
	if wert == "dotted.path":  # Prosa aus der Doku von tools/inventar.py
		return False
	if "." not in wert:
		return False
	letztes = wert.rsplit(".", 1)[-1]
	# `api.` / `auth.` als LETZTES Segment ist eine Bahn, kein Name.
	return bool(letztes) and letztes not in {"api", "klassisch", "auth", "diakronos", "diakonos"}


#: Literale, die eine MODULBAHN benennen (letztes Segment ist ein bekannte
#: Modulname) — sie werden zur Laufzeit mit `. <fn>` verklebt oder sind der
#: Praefix einer solchen Klebung. `diakronos.kronos.api.event_crud` als GANZER
#: Pfad ist ein 404 (das Modul ist keine Funktion); geprueft wird deshalb der
#: Aufruf, nicht die Bahn. Bewusst GROB gehalten: was hier nicht steht, wird
#: geprueft (lieber ein Pfad zu viel als einer zu wenig).
_MODULNAMEN = frozenset(
	{
		"auth", "admin_hub", "audit", "austritt", "dashboard", "datenschutz",
		"dienstplan", "einrichtung", "gestaltung", "gemeinde", "gruppen",
		"kalender_verwaltung", "kanban_api", "mailversand", "mitglieder",
		"oeffentlich", "planrahmen", "planung", "profile", "registrierung",
		"registrierungslink_api", "ressourcen", "rechte", "session", "sicherung",
		"user", "verantwortliche", "website", "wiki", "zugang",
		# Kronos-Bahn (Altcode-Module, `diakronos.kronos.api.<modul>`).
		"event_crud", "calendar_get", "series", "permissions", "ablaufplan_api",
	}
)


def nicht_bahn(wert: str) -> bool:
	"""False fuer reine MODULBAHNEN (`…api.event_crud`), sonst True."""
	letzte = wert.rstrip(".").rsplit(".", 1)[-1]
	if wert.endswith(".") or letzte in _MODULNAMEN:
		return False
	return True


def tool_pfade() -> list[str]:
	"""Alle vollen Methodenpfade, die `tools/` aufruft (sortiert, ohne Dubletten)."""
	wurzel = _tools_wurzel()
	gefunden: set[str] = set()
	for ordner, _unterordner, dateien in os.walk(wurzel):
		for datei in dateien:
			if not datei.endswith(_ENDUNGEN):
				continue
			with open(os.path.join(ordner, datei), encoding="utf-8", errors="replace") as fh:
				text = fh.read()
			for muster in (_AUFRUF, _API_METHOD, _OBJEKT):
				for treffer in muster.finditer(text):
					wenn = treffer.group(1)
					if _ist_pfad(wenn) and nicht_bahn(wenn):
						gefunden.add(wenn)
			# Bauform `ruf(API + 'name')`: Bahn aus der Datei + Name.
			bahnen = {m.group(1): m.group(2) for m in _PRAEFIX.finditer(text)}
			for treffer in _PRAEFIX_BAU.finditer(text):
				bahn = bahnen.get(treffer.group(1))
				if bahn:
					gefunden.add(f"{bahn}{treffer.group(2)}")
	return sorted(gefunden)

def _register_vollstaendig() -> None:
	from diakronos_app.main import app  # noqa: F401

	try:
		from diakronos_app.devmodus import api as devmodus_api

		devmodus_api.registriere()
	except Exception:  # noqa: BLE001 — ohne Dev-Modus gibt es diese Module nicht
		pass


def _antwortet(client, pfad: str) -> tuple[int, dict]:
	"""GET und POST auf den Pfad — der schlechteste Stand zaehlt."""
	schlecht: tuple[int, dict] = (0, {})
	for methode in ("GET", "POST"):
		antwort = (
			client.get(f"/api/method/{pfad}")
			if methode == "GET"
			else client.post(f"/api/method/{pfad}", json={})
		)
		koerper = antwort.json() if "json" in antwort.headers.get("content-type", "") else {}
		if antwort.status_code == 404 or koerper.get("message") == "Methode nicht gefunden":
			return antwort.status_code, koerper
		schlecht = (antwort.status_code, koerper)
	return schlecht


def test_tools_pfade_werden_gefunden():
	"""Der Scanner findet die Pfade wirklich — sonst ist der Test blind.

	Ohne diese Untergrenze waere ein Regex-Fehler ein gruener Test: genau der
	Befund dieser Karte (ein Waechter, der nie fehlschlagen kann).
	"""
	pfade = tool_pfade()
	assert len(pfade) >= 30, f"zu wenige tools/-Pfade ({len(pfade)}):\n" + "\n".join(pfade)
	# Die zwei Befunde DIESER Karte muessen im Scan auftauchen — sonst scannt
	# der Test die Dateien nicht, um die es geht. (Sie stehen nach der
	# Umstellung unter der Bahn des Frontends; auf dem ROT-Stand dieses
	# Zweigs stehen sie dort mit `diakronos.diakronos.` und der Test ist rot.)
	for erwartet in (
		"diakronos.diakonos.api.admin_hub.get_anmeldeformulare",
		"diakronos.diakonos.api.admin_hub.get_anmeldungen_hub",
		"diakronos.diakonos.api.admin_hub.create_anmeldeformular",
		"diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen",
		"diakronos.diakronos.api.website.kalender_oeffentlich",
	):
		assert erwartet in pfade, f"{erwartet} fehlt im Scan ({len(pfade)} Pfade)"


def test_alle_tools_methodenpfade_antworten(client, patched_db):
	"""Jeder Methodenpfad aus `tools/` erreicht den Router (GET und POST).

	Angemeldet als Administrator: die Fachfunktion darf fachlich ablehnen
	(401/403/417) — geprueft wird NUR, dass der PFAD existiert. „Methode nicht
	gefunden“ heisst: das Abnahme-Skript ruft ins Leere.
	"""
	_register_vollstaendig()
	tot: list[str] = []
	for pfad in tool_pfade():
		if pfad in _ERWARTET_404:
			continue
		status, koerper = _antwortet(client, pfad)
		if status == 404 or (koerper or {}).get("message") == "Methode nicht gefunden":
			tot.append(f"{pfad} -> {status} {koerper}")
	assert tot == [], f"{len(tot)} tools/-Pfad(e) ohne Methode:\n" + "\n".join(tot)


def test_tools_pfad_ruft_die_funktion_des_frontends(client, patched_db):
	"""Die zwei Pfade dieser Karte treffen DIESELBE Funktion wie die SPA.

	Nicht nur „kein 404“: `admin_hub.get_anmeldeformulare` und
	`gemeinde.gemeinde_get_einstellungen` muessen unter der Schreibweise der
	Tools die Funktion aus `Registrierung.vue` / `Wiki.vue` ausfuehren — die
	Bahn muss also die des Frontends sein, nicht eine zweite.
	"""
	_register_vollstaendig()
	from diakronos_app.frappe_compat import router

	for pfad, modul in (
		("diakronos.diakonos.api.admin_hub.get_anmeldeformulare", "diakronos_app.api.admin_hub"),
		("diakronos.diakonos.api.admin_hub.get_anmeldungen_hub", "diakronos_app.api.admin_hub"),
		("diakronos.diakonos.api.admin_hub.create_anmeldeformular", "diakronos_app.api.admin_hub"),
		(
			"diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen",
			"diakronos_app.api.gemeinde",
		),
	):
		fn = router._aufloesen(pfad)  # noqa: SLF001 — Probe am echten Weg
		assert fn is not None, pfad
		assert getattr(fn, "__module__", "") == modul, (pfad, getattr(fn, "__module__", None))


@pytest.mark.parametrize("pfad", sorted(_ERWARTET_404))
def test_bewusste_404_pfade_bleiben_404(client, patched_db, pfad):
	"""Die Ausnahme ist dokumentiert — und sie ist wirklich noch ein 404.

	Verschwindet der 404, ist die Ausnahme falsch geworden: dann gehoert der
	Pfad umgestellt (er ist kein Fehlbefund mehr, sondern ein lebender
	Baustein) und die Ausnahme geloescht.
	"""
	_register_vollstaendig()
	status, koerper = _antwortet(client, pfad)
	assert status == 404, (status, koerper)
	# Zwei 404-Bilder im Spiel: „Methode nicht gefunden“ (Router, kein
	# zulaessiger/gibt-es-nicht-Pfad) und „Nicht gefunden“ (Pfad zulaessig,
	# aber kein Endpunkt registriert — der Dev-Modus bei DEVMODE_ENABLED=0).
	assert koerper.get("message") in {"Methode nicht gefunden", "Nicht gefunden"}, koerper
