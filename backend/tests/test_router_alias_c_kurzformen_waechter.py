"""ROUTER-ALIAS-c — Waechter: niemand benutzt die verbotenen Kurzformen.

SOLL 4 der Karte: Kurzformen sind nur noch erlaubt, wenn sie EINDEUTIG und
ausdruecklich zugesagt sind. Bevor das gilt, muss belegt sein, dass
`frontend/src`, `tools/` und `backend/src` die gestrichenen Schreibweisen
nicht benutzen — sonst faellt die SPA beim naechsten Klick auf 404.

Geprueft wird der QUELLTEXT (wie der SPA-Waechter daneben): jeder Aufruf
`api/method/<pfad>` bzw. `apiCall('…')`/`apiUrl('…')`/`fetch('…')` mit einem
gestrichenen Pfad ist ein Befund. Die Frappe-Schreibweisen (`frappe.client.
insert`, `upload_file`, `logout`, `frappe.sessions.get_csrf_token`) bleiben
zugesagt und sind deshalb nicht betroffen.
"""

from __future__ import annotations

import os
import re

import pytest

_WURZELN = (
    "/frontend/src",
    "/repo/frontend/src",
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src"),
)
_TOOLS = (os.path.join(os.path.dirname(__file__), "..", "..", "tools"),)
_BACKEND = (os.path.join(os.path.dirname(__file__), "..", "src"),)

#: Gestrichene Kurzformen (SOLL 4 der Karte). Getrennt gehalten, weil der
#: stumme Name (`insert`) nur als GANZER Pfad verboten ist, `session.insert`
#: dagegen eine Modulbahn waere.
_VERBOTEN = (
    # Mehrdeutig im Register (mehrere gleichnamige Fassungen).
    "sitzung_status",
    "status",
    "liste",
    # Vorlauf statt Kurzform.
    "api.insert",
    "api.upload_file",
    "api.logout",
    "api.root_uebertragen",
    # Frappe-Kernfunktion: nur ihre zugesagte Schreibweise.
    "insert",
)

#: Ein Methodenpfad, wie ihn Frontend/Tools schreiben. Auch die
#: Konstanten-Bauform `ruf('name')` zaehlt: `PRAEFIX + methode` wird beim
#: Scannen zusammengesetzt (`_praefix_von`).
_MUSTER = re.compile(
    r"(?:api/method/|apiCall\(\s*[`'\"]|apiUrl\(\s*[`'\"]|apiPost\(\s*[`'\"]"
    r"|apiGet\(\s*[`'\"]|ruf\(\s*[`'\"])([A-Za-z0-9_.]+)"
)
#: `const PRAEFIX = 'diakronos.x.api.'` — Bahnen fuer `ruf('<fn>')`.
_PRAEFIX = re.compile(r"const\s+PRAEFIX\s*=\s*[`'\"]([A-Za-z0-9_.]+)[`'\"]")
#: `/api/method/<pfad>` — auch ein NACKTER Name (`/api/method/ping`) ist ein
#: Methodenpfad; genau diese Form hat der alte Test nie gesehen, weil der
#: SPA-Scanner nur Literale MIT Punkt sammelt.
_API_METHOD = re.compile(r"api/method/([A-Za-z0-9_]+(?:[./][A-Za-z0-9_]+)*)")
#: Erste Segmente, die ein MODUL benennen — `/api/method/<modul>` bzw.
#: `<modul>.<fn>` sind keine Kurzform-Aufrufe.
_MODULNAMEN = frozenset(
	{
		"api", "auth", "mitglieder", "gruppen", "kalender", "website", "wiki",
		"zugang", "session", "profile", "planung", "dashboard", "gemeinde",
		"rechte", "user", "sicherung", "mailversand", "registrierung",
		"admin_hub", "austritt", "datenschutz", "einrichtung", "gestaltung",
		"oeffentlich", "planrahmen", "verantwortliche", "dienstplan",
		"kalender_verwaltung", "kanban_api", "event_crud", "calendar_get",
		"permissions", "series", "ablaufplan_api", "diakronos", "diakonos",
		"frappe", "x", "pfad", "dotted",
	}
)
#: Bahn einer Datei fuer die Bauform `apiCall(API + '<fn>')` / `ruf(P + '<fn>')`:
#: der Name muss nicht `PRAEFIX` heissen (`const API = 'diakronos.…api.x.'`).
_Q = "[\"'`]"
#: `const NAME = 'ein.pfad'` (beliebiger Wert, fuer `_bahn_der_datei`).
_KONSTANTE = re.compile(
	r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*" + _Q + r"([A-Za-z0-9_.]+)" + _Q
)
_BAHN = re.compile(
	r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*" + _Q + r"([A-Za-z0-9_.]+\.)" + _Q
)
#: Bauform `apiCall(API + '<fn>')` / `ruf(PRAEFIX + '<fn>')`.
_BAU = re.compile(
	r"(?:apiCall|apiGet|ruf)\(\s*([A-Za-z_$][\w$]*)\s*\+\s*" + _Q + r"([A-Za-z0-9_.]+)" + _Q
)
#: Ein NACKTER Aufruf der SPA-Form: `apiUrl('logout')` (useAbmelden.js:187),
#: `apiUrl('upload_file')` (Profile.vue:526) … Genau diese Form sah der
#: Scanner nie — er kannte nur `api/method/<name>`. ROUTER-ALIAS-e: `apiUrl`
#: baut den Methodenpfad (`/api/method/<präfix><name>`), ein unbekannter
#: nackter Name ist damit ein toter Aufruf wie jeder andere.
#: Zweistellige Signaturen der SPA (`apiCall('POST', '/api/…')`) sind damit
#: KEINE Pfade: `POST` faellt ueber `_NACKT_AUSGENOMMEN` heraus.
_NACKT_AUFRUF = re.compile(
	r"(?:apiCall|apiUrl|apiGet|apiPost|apiPut|apiDelete|apiFetch|ruf)"
	r"\(\s*" + _Q + r"([A-Za-z0-9_]+)" + _Q
)
#: Literale, die kein Name sein koennen (HTTP-Verben, Prosa aus Kommentaren).
_NACKT_AUSGENOMMEN = frozenset(
	{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "GET ", "POST "}
)
#: Die Bauform mit Bahn der Datei: `ruf('<name>')` neben
#: `const PRAEFIX = 'diakronos.x.api.'` (siehe `_kurzformen_in`).
_RUFE = re.compile(r"\bruf\(\s*" + _Q + r"([A-Za-z0-9_]+)" + _Q)
#: Eine Datei, die `ruf`/`apiCall` SELBST definiert UND darin den Pfad
#: zusammenbaut (`async function ruf(fn, p) { … apiCall(`${RECHTS}.${fn}`, p) }`,
#: RollenEinstellungen.vue:426) — dort ist jedes `ruf('<name>')` ein
#: Funktionsargument einer Bahn, kein fertiger Methodenpfad.
#:
#: ROUTER-ALIAS-f: Der Ausdruck war zu breit. Er traf JEDE Datei mit einer
#: eigenen Funktionsdeklaration dieses Namens — auch die reinen DURCHREICHER
#: (`async function apiCall(...argumente) { return modul.apiCall(...argumente) }`
#: in `papierkorb.mjs:21` und `rueckgaengigWeg.mjs:260`, `useApi.js:169`,
#: `useDevmodus.js:50`). Deren `apiCall('<name>')`/`ruf('<name>')` ist der
#: Pfad-Name selbst (die Bahn steckt in `useApi.js`/`shared/basis.js`), kein
#: Suffix — die Dateien wurden komplett uebersprungen (Mutation X1/X6 blieben
#: gruen). Gesucht wird jetzt ein Wrapper mit benanntem Pfad-Parameter; ein
#: Durchreicher deklariert `(...argumente)` ohne Namen. Ein `method`-Kopf
#: allein genuegt NICHT: der Rumpf muss zusammenbauen (`_ZUSAMMENBAU`) —
#: sonst waere `useApi.js`/`rueckgaengigWeg.mjs` wieder ausgenommen.
#:
#: ROUTER-ALIAS-g: Diese Ausnahme gilt je DEFINITION, nicht je Datei —
#: in `_kurzformen_in` ueber `_in_lokalem_ruf` (Zeilenspanne). Datei-Weite
#: bleibt nur dort richtig, wo kein Pfad verloren gehen kann
#: (`_nackte_namen`: `ruf('<name>')` ist auch dort kein nackter Methodenpfad).
_LOKALES_RUF = re.compile(
	r"(?:async\s+)?function\s+"
	r"(?:ruf|apiCall|apiFetch|apiGet|apiPost)\s*\(\s*"
	r"(?:method|methode|fn|name|pfad|path)\b"
)
#: Die Bauformen, an denen ein Wrapper den Pfad zusammensetzt:
#: `` `${RECHTS}.${fn}` `` (RollenEinstellungen.vue:428),
#: `` `${API}.${method}` `` (dashboardConfig.js:13),
#: `` PRAEFIX + methode `` (useDevmodus.js:51).
_ZUSAMMENBAU = re.compile(
	r"`[^`\n]*\$\{[^}`\n]+\}[^`\n]*\.\$\{[^}`\n]+\}[^`\n]*`"
	r"|\b[A-Za-z_$][\w$]*\s*\+\s*(?:method|methode|fn|name)\b"
)
#: Anfang einer Definition auf SPALTENEBENE (`function …`, `const x = … =>`).
#: Grenze fuer die Spanne einer selbstgebauten `ruf`-Definition (ROUTER-ALIAS-g,
#: `_lokale_ruf_definitionen`). `	` zaehlt hier bewusst NICHT als Einrueckung:
#: `frontend/src` ist mit Leerzeichen eingerueckt, `tools/` mit Tabs — was auf
#: Spaltenebene beginnt, beendet die vorige Definition.
_DEFINITION_ANFANG = re.compile(
	r"(?:export\s+)?(?:async\s+)?(?:function\b|(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=)"
)
#: Kurznamen, die in `frontend/src` und `tools/` als KURZFORM zugesagt sind.
#:
#: ROUTER-ALIAS-e: Hier stand vorher zusaetzlich
#: `zugesagt |= {p for p in registry.registered() if "." not in p}` — damit
#: war JEDER registrierte Kurzname zugesagt und der „unbekannt“-Check ein
#: „tot“-Check (der naechste Test prueft die Auflösung ohnehin). Zugesagt ist
#: jetzt eine AUSDRUECKLICHE Menge: die Frappe-Kernpfade, die der Router als
#: `_KERNPFADE` fuehrt (`ping`, `logout`, `upload_file`, `login`, `insert`).
#: Nur mit Kommentar erweitern.
_ERLAUBTE_KURZNAMEN = frozenset({"ping", "logout", "upload_file", "login", "insert"})


def _register_vollstaendig() -> None:
	"""Laedt die App — und den Dev-Modus, wenn er EINGESCHALTET ist.

	ROUTER-ALIAS-e: Hier stand `devmodus_api.registriere()` ohne `app`. Die
	Funktion verlangt `app` (TypeError), der von einem stillen
	`except Exception: pass` verschluckt wurde — die Dev-Modus-Bahn wurde
	also nie registriert. Jetzt gilt die Regel des Betriebs (`main.py:241`):
	`registriere(app)` MIT der App, und ohne stilles `except`.

	Der Dev-Modus ist im Testlauf AUS (`DEVMODE_ENABLED` nicht gesetzt, siehe
	`devmodus/einstellungen.py`); `registriere` meldet das ueber `False` und
	importiert nichts. Genau so verhaelt sich der Betrieb.
	"""
	from diakronos_app.devmodus import api as devmodus_api
	from diakronos_app.main import app

	devmodus_api.registriere(app)


def _baut_pfad(text: str) -> bool:
	"""True, wenn ein Wrapper in `text` den Methodenpfad SELBST zusammensetzt.

	ROUTER-ALIAS-f: Die Ausnahme `_LOKALES_RUF` galt vorher fuer jede Datei mit
	eigener Deklaration — auch fuer die Durchreicher (`papierkorb.mjs`,
	`rueckgaengigWeg.mjs`, `useApi.js`, `useDevmodus.js`). Ein Durchreicher
	baut nichts: er ruft die echte Funktion auf. Geprueft wird deshalb BEIDES —
	ein Wrapper-Kopf mit benanntem Pfad-Parameter (`_LOKALES_RUF`) UND eine
	Zusammenbau-Bauform im Rumpf (`_ZUSAMMENBAU`).

	`RollenEinstellungen.vue` (`apiCall(`${RECHTS}.${fn}`, …)`) und
	`dashboardConfig.js` (`fetch(`${API}.${method}`)`) sind solche Bauer —
	dort ist `ruf('<name>')`/`apiFetch('<name>')` ein Suffix, kein Pfad.
	"""
	# Kommentare fliegen raus: ein Beispiel in einer Doc-Zeile ist kein Wrapper.
	ohne_kommentar = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
	if _LOKALES_RUF.search(ohne_kommentar) is None:
		return False
	return _ZUSAMMENBAU.search(ohne_kommentar) is not None


def _bahn_der_datei(text: str) -> str:
	"""Die Bahn, gegen die `ruf('<name>')` geprueft wird.

	ROUTER-ALIAS-f (SOLL 3): Zwei Formen, beide real im Baum:

	  * `const PRAEFIX = 'diakronos.devmodus.api.'` (useDevmodus.js:23) —
	    direkt die Bahn.
	  * `const RECHTS = 'diakronos_app.api.rechte'` + `ruf`, das
	    `${RECHTS}.${fn}` baut (RollenEinstellungen.vue:278/429). Hier NENNT
	    die Konstante den PFAD DER FUNKTION; gemeint ist das Modul davor.
	    Frueher las der Waechter nur `PRAEFIX`, fand in dieser Datei also
	    gar keine Bahn und meldete `ruf('…')` deshalb nie — Mutation X3
	    blieb gruen.

	Die zweite Form gilt NUR, wenn ein `ruf`-Wrapper die Konstante wirklich
	verwendet (`${KONST}.`); eine Konstante ohne Wrapper ist keine Bahn.
	"""
	bahn = _PRAEFIX.search(text)
	if bahn:
		return bahn.group(1)
	# Wrapper, der `<konstante>.${fn}` baut? Dann ist `<konstante>` der Pfad
	# EINER Funktion, das Modul ist alles davor.
	ruf_treffer = _LOKALES_RUF.search(text)
	if ruf_treffer is None:
		return ""
	# Die Konstante braucht KEINEN Punkt: `_BAHN` verlangt einen
	# (Bahnen enden dort auf `.`), hier ist der Wert der Pfad EINER Funktion.
	for treffer in _KONSTANTE.finditer(text):
		name, wert = treffer.group(1), treffer.group(2).rstrip(".")
		if f"${{{name}}}." in text and "." in wert:
			# `wert` ist `modul.funktion` — die Bahn ist das Modul.
			return wert.rsplit(".", 1)[0] + "."
	return ""


def _kurzformen_in(wurzeln) -> list[tuple[str, int, str]]:
	"""Alle ECHTEN Kurzform-Aufrufe (ohne Modulbahn).

	Rueckgabe: `(datei, zeile, name)`. Drei Formen, alle ohne Punkt:

	  * `/api/method/<name>` — der nackte Pfad (`fetch('/api/method/ping')`).
	  * `apiUrl('<name>')`, `apiCall('<name>')`, `apiGet('<name>')`,
	    `apiPost('<name>')` … — die SPA-Form. `apiUrl` baut daraus den
	    Methodenpfad (`/api/method/<praefix><name>`, shared/basis.js:80);
	    `useAbmelden.js:187` (`apiUrl('logout')`) und `Profile.vue:526`
	    (`apiUrl('upload_file')`) sind solche Aufrufe. ROUTER-ALIAS-e: diese
	    Form hat der Scanner vorher NIE gesehen — `apiUrl('gibtsnicht_xyz')`
	    im Frontend blieb gruen.
	  * `ruf('<name>')` — die Bauform mit der Bahn der Datei:
	    `const PRAEFIX = 'diakronos.x.api.'` + `ruf('logout')`. Der Pfad ist
	    damit `diakronos.x.api.logout`; er ist nur dann eine Kurzform, wenn
	    die Bahn ihn nicht deckt (`ist_originalpfad`) — sonst ist es eine
	    legitime Modulbahn (`ruf('uebersicht')` in `useDevmodus.js`, Bahn
	    `diakronos.devmodus.api.`).

	Die Bauform `apiCall(API + '<name>')` bleibt hier BEWUSST draussen: der
	Name ist ein SUFFIX einer Bahn (`…api.einrichtung.` + `status`), kein
	Kurzform-Aufruf. Er ist immer erreichbar, wenn die Bahn zugesagt ist —
	das prueft `test_router_alias_waechter` und der tools/-Waechter.
	"""
	from diakronos_app.frappe_compat import registry

	funde: list[tuple[str, int, str]] = []
	for datei in _dateien(tuple(wurzeln)):
		with open(datei, encoding="utf-8", errors="replace") as fh:
			text = fh.read()
		praefix = _bahn_der_datei(text)
		# Baut die Datei ihre Aufrufe selbst zusammen (`async function ruf(fn) {
		# … apiCall(`${RECHTS}.${fn}`) }`, RollenEinstellungen.vue:426), ist
		# jedes `ruf('<name>')` ein Funktionsargument einer Bahn, kein Pfad.
		# ROUTER-ALIAS-f + g: Ein Durchreicher baut nichts — er wird gescannt
		# (`papierkorb.mjs` war vorher komplett uebersprungen). Die Ausnahme
		# gilt je DEFINITION (`_lokale_ruf_definitionen`), nicht je Datei:
		# frueher (`lokales_ruf`) fiel mit der Bauform `ruf('<name>')` auch
		# jedes `apiUrl('<name>')` derselben Datei aus der Pruefung.
		lokale_rufe = _lokale_ruf_definitionen(text)
		zeilen = text.splitlines()
		for nr, zeile in enumerate(zeilen, 1):
			# Doku-Beispiele in Kommentaren (`mitBasis('/api/method/x')`) sind
			# keine Aufrufe und wuerden den Test nur mit Rauschen fuellen.
			nackt = zeile.strip()
			if nackt.startswith(("//", "#", "*", "/*", "<!--")):
				continue
			# Nur REQUEST-Pfade: `apiUrl(PRAEFIX + 'bild') + '?pfad='` baut
			# `…/{praefix}api/method/<p>?pfad=<wert>` — das ist eine
			# aufgeloeste Bahn, ein Literal `<pfad>=<wert>` ist kein Aufruf.
			# Ohne diese Grenze meldete der Scanner die Dev-Modus-Bahn
			# (`…/uebersicht?pfad=…`) faelschlich als Kurzform.
			for name in _API_METHOD.findall(zeile):
				name = name.rstrip("/")
				if "=" in name:
					continue
				# Ein MODUL (`mitglieder`, `api`, `x` in Doku-Prosa) ist keine
				# Kurzform — es beschreibt keinen Aufruf.
				if "." not in name and name not in _MODULNAMEN:
					funde.append((datei, nr, name))
			for treffer in _NACKT_AUFRUF.finditer(zeile):
				name = treffer.group(1)
				if name in _MODULNAMEN or name in _NACKT_AUSGENOMMEN:
					continue
				if re.search(r"\bruf\(\s*" + _Q + name + _Q, zeile):
					# `ruf('<name>')` neben einer Bahn = PAAR (unten geprueft).
					continue
				funde.append((datei, nr, name))
			# `ruf('<name>')` in einer Datei mit Bahn: nur eine Kurzform, wenn
			# die Bahn den Pfad nicht selbst deckt (ROUTER-ALIAS-f: hier steht
			# KEIN dateiweites `continue` — der Zweig prueft die Bahn ohnehin
			# gegen `ist_originalpfad`). ROUTER-ALIAS-g: Ausgenommen ist nur die
			# DEFINITION selbst, die den Namen als Argument baut.
			if _in_lokalem_ruf(zeilen, nr, lokale_rufe):
				continue
			for treffer in _RUFE.finditer(zeile):
				name = treffer.group(1)
				if name in _MODULNAMEN or name in _NACKT_AUSGENOMMEN or not praefix:
					continue
				fn = registry.lookup(f"{praefix}{name}")
				if fn is not None and registry.ist_originalpfad(f"{praefix}{name}", fn):
					continue
				funde.append((datei, nr, name))
	return funde


def _lokale_ruf_definitionen(text: str) -> list[tuple[int, int]]:
	"""Zeilenspannen `(anfang, ende)` der `ruf`/`apiCall`-Definitionen einer Datei.

	Spanne bis zur naechsten Definition auf Spaltenebene (`function`, `const x
	= … =>`) oder bis zum Dateiende — bewusst grob: lieber eine Zeile zu weit
	als eine Definition zu frueh beenden. Die Definition selbst bleibt drin
	(sie ist eine Funktion, kein Aufruf).
	"""
	zeilen = text.splitlines()
	definiert = [
		nr for nr, zeile in enumerate(zeilen, 1) if _LOKALES_RUF.search(zeile)
	]
	grenzen = [
		nr for nr, zeile in enumerate(zeilen, 1) if _DEFINITION_ANFANG.match(zeile)
	]
	spannen: list[tuple[int, int]] = []
	for anfang in definiert:
		naechste = [g for g in grenzen if g > anfang]
		spannen.append((anfang, (naechste[0] - 1) if naechste else len(zeilen)))
	return spannen


def _in_lokalem_ruf(zeilen: list[str], nr: int, spannen: list[tuple[int, int]]) -> bool:
	"""True, wenn Zeile `nr` in einer selbstgebauten `ruf`-Definition steht."""
	return any(anfang <= nr <= ende for anfang, ende in spannen)


def _kurzformen_im_quelltext() -> list[tuple[str, int, str]]:
	"""Kurzformen aus `frontend/src` und `tools/` (die zwei Aufrufer)."""
	return _kurzformen_in((_frontend_wurzel(),) + _TOOLS)


def _nackte_namen() -> set[str]:
	"""Namen, die WIRKLICH nackt aufgerufen werden (ohne Bahn der Datei).

	Das sind `/api/method/<name>` und `apiUrl('<name>')`/`apiCall('<name>')`.
	Nicht dabei: `ruf('<name>')` neben einer Bahn — dort baut die Datei den
	Pfad selbst zusammen.
	"""
	namen: set[str] = set()
	for datei in _dateien((_frontend_wurzel(),) + _TOOLS):
		with open(datei, encoding="utf-8", errors="replace") as fh:
			text = fh.read()
		if _baut_pfad(text):
			# Die Datei baut ihren Aufruf selbst zusammen (`apiFetch` in
			# dashboardConfig.js:11 -> `${API}.${method}`); der Name ist dann
			# ein Argument einer Bahn, kein nackter Methodenpfad.
			# ROUTER-ALIAS-f: Ein Durchreicher (`papierkorb.mjs`,
			# `rueckgaengigWeg.mjs`) baut nichts und wird gescannt.
			continue
		for zeile in text.splitlines():
			nackt = zeile.strip()
			if nackt.startswith(("//", "#", "*", "/*", "<!--")):
				continue
			for treffer in _API_METHOD.findall(zeile):
				name = treffer.rstrip("/")
				if "=" not in name and "." not in name and name not in _MODULNAMEN:
					namen.add(name)
			for treffer in _NACKT_AUFRUF.finditer(zeile):
				name = treffer.group(1)
				# `ruf('<name>')` neben einer Bahn ist ein PAAR, kein nackter Aufruf.
				if re.search(r"\bruf\(\s*" + _Q + name + _Q, zeile):
					continue
				if name not in _MODULNAMEN and name not in _NACKT_AUSGENOMMEN:
					namen.add(name)
	return namen


def _dateien(wurzeln: tuple[str, ...]) -> list[str]:
    gefunden: list[str] = []
    for wurzel in wurzeln:
        if not os.path.isdir(wurzel):
            continue
        for ordner, _u, dateien in os.walk(wurzel):
            for name in dateien:
                if name.endswith((".js", ".mjs", ".vue", ".py", ".cjs", ".html")):
                    gefunden.append(os.path.join(ordner, name))
    return gefunden


def _frontend_wurzel() -> str:
    for pfad in _WURZELN:
        if os.path.isdir(pfad):
            return pfad
    pytest.skip("frontend/src nicht gefunden")


@pytest.mark.parametrize("bereich", ["frontend", "tools", "backend"])
def test_keine_gestrichene_kurzform_im_quelltext(bereich):
    """Kein Aufrufer benutzt eine gestrichene Kurzform (sonst 404 im Betrieb)."""
    wurzeln = {
        "frontend": (_frontend_wurzel(),),
        "tools": _TOOLS,
        "backend": _BACKEND,
    }[bereich]
    befund: list[str] = []
    for datei in _dateien(wurzeln):
        with open(datei, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # Bahn der Datei (`const PRAEFIX = 'diakronos.x.api.'`) fuer `ruf('<fn>')`.
        bahn = _PRAEFIX.search(text)
        praefix = bahn.group(1) if bahn else ""
        for nummer, zeile in enumerate(text.splitlines(), 1):
            for treffer in _MUSTER.finditer(zeile):
                ziel = treffer.group(1).rstrip(".")
                # `ruf('sitzung_status')` in einer Datei mit `PRAEFIX` baut den
                # vollen Pfad `diakronos.x.api.sitzung_status`.
                voll = f"{praefix}{ziel}" if praefix and "." not in ziel else ziel
                # Nur der GANZE Pfad zaehlt: `diakronos.x.api.status` ist eine
                # Modulbahn, `status` die gestrichene Kurzform.
                if voll in _VERBOTEN:
                    befund.append(f"{datei}:{nummer}: {voll}")
    assert befund == [], "gestrichene Kurzform im Quelltext:\n" + "\n".join(befund[:20])


def test_frontend_pfade_nutzen_keine_kurzform():
    """Gegenprobe am Scanner des SPA-Waechters: nur volle Modulbahnen.

    ROUTER-ALIAS-d (Befund): Dieser Test konnte NIE fehlschlagen. Er las
    `W._frontend_pfade()` und filterte alles ohne Punkt heraus — und der
    Scanner liefert per Konstruktion nur Literale MIT Punkt. Damit war
    „keine Kurzform" eine Tautologie.

    Geprueft wird jetzt, was wirklich zaehlt:

      * Es gibt ueberhaupt Kurzform-Aufrufe im Quelltext (sonst sieht der
        Test nichts — und ist blind, nicht gruen).
      * Keine der gestrichenen Kurzformen (`_VERBOTEN`) wird aufgerufen.
      * Jeder gefundene Kurzname gehoert zur ZUGESAGTEN Menge
        (`_ERLAUBTE_KURZNAMEN`, dokumentierte Frappe-Kernpfade und `ping`) —
        ein neuer, unbemerkter Kurzname faellt hier auf.
      * Fuer jeden dieser Namen gilt: er loest am Router wirklich auf.

    Der fruehere 8er-Katalog (Z. 31-43) war eine gepflegte Kopie; die Menge
    kommt jetzt aus dem Quelltext von `frontend/src` UND `tools/`.
    """
    import test_router_alias_waechter as W

    _register_vollstaendig()
    kurz = _kurzformen_im_quelltext()
    assert len(kurz) >= 3, f"zu wenige Kurzform-Aufrufe gefunden ({len(kurz)}): {kurz}"
    verboten = [f"{datei}:{nr}: {name}" for datei, nr, name in kurz if name in _VERBOTEN]
    assert verboten == [], "gestrichene Kurzform im Quelltext:\n" + "\n".join(verboten[:20])
    # Zugesagt ist eine Kurzform NUR, wenn sie in `_ERLAUBTE_KURZNAMEN` steht
    # (die Frappe-Kernpfade des Routers und `ping`).
    #
    # ROUTER-ALIAS-e: Hier stand zusaetzlich
    # `zugesagt |= {p for p in registry.registered() if "." not in p}` — damit
    # war jeder registrierte Kurzname zugesagt und dieser Check konnte nie
    # etwas finden (er war eine Kopie des „tot“-Checks darunter). Die
    # Erlaubnis ist jetzt eine AUSDRUECKLICHE Menge.
    #
    # Ein NICHT zugesagter Name ist nur dann Befund, wenn er WIRKLICH ueber die
    # nackte Form laeuft (`fetch('/api/method/x')`, `apiUrl('x')`). `ruf('x')`
    # in einer Datei mit eigener Bahn ist ein PAAR (`bahn + x`) — es steht hier
    # nur, weil das Ergebnis nicht deckt, und faellt schon unter `tot`
    # (Aufloesung) auf; ein zweiter Befund waere Rauschen.
    nackt = _nackte_namen()
    zugesagt = set(_ERLAUBTE_KURZNAMEN)
    unbekannt = sorted(nackt - zugesagt)
    assert unbekannt == [], f"nicht zugesagte Kurzform(en): {unbekannt}"
    # ... und jede benutzte Kurzform muss am Router wirklich loesen.
    tot = sorted({name for _d, _n, name in kurz if not W._loest_auf(name)})
    assert tot == [], f"Kurzform(en) ohne Funktion am Router: {tot}"

def test_lokales_ruf_schaltet_nur_seine_definition_ab(tmp_path):
	"""ROUTER-ALIAS-g: die `ruf`-Ausnahme gilt je DEFINITION, nicht je Datei.

	Befund: `lokales_ruf` war dateiweit und schaltete die Bauform
	`ruf('<name>')` in der GANZEN Datei ab. Belegt wird hier die Grenze:
	`ruf('<name>')` INNERHALB der selbstgebauten Definition ist ein Argument
	(kein Pfad), `ruf('<name>')` AUSSERHALB ist ein Pfad und wird gesehen;
	`apiUrl('<name>')` daneben faellt nie unter die Ausnahme.
	"""
	datei = os.path.join(str(tmp_path), "lokal.mjs")
	with open(datei, "w", encoding="utf-8") as fh:
		fh.write(
			"const PRAEFIX = 'diakronos.x.api.'\n"
			"const RECHTS = 'diakronos_app.api.rechte'\n"
			"export async function laden() { return 1 }\n"
			"async function ruf(fn, params) {\n"
			"  return apiCall(`${RECHTS}.${fn}`, params)\n"
			"}\n"
			"export async function weg() {\n"
			"  return ruf('gibtsnicht_aussen')\n"
			"}\n"
			"export async function weg2() {\n"
			"  return ruf('auch_weg')\n"
			"}\n"
			"export async function weg3() {\n"
			"  return apiUrl('direkt_nackt')\n"
			"}\n"
		)
	namen = [name for _d, _n, name in _kurzformen_in([str(tmp_path)])]
	# Der innere Aufbau der Definition ist ein Argument, kein Pfad.
	assert "fn" not in namen, namen
	# Ausserhalb der Definition wird gesucht — Bahn der Datei ist fremd
	# (`diakronos.x.api.` deckt `gibtsnicht_aussen` nicht), also Befund:
	assert "gibtsnicht_aussen" in namen, namen
	assert "auch_weg" in namen, namen
	# Und der NACKTE Aufruf daneben: mit der alten dateiweiten Ausnahme
	# (`lokales_ruf`) fiel auch er weg — genau der Befund dieser Karte.
	assert "direkt_nackt" in namen, namen

def test_kurzform_waechter_kann_rot_werden(monkeypatch, tmp_path):
	"""Mutationsbeleg: derselbe Test wird mit einer gestrichenen Kurzform ROT.

	Ohne diesen Nachweis waere nicht belegt, dass der Waechter ueberhaupt
	etwas sieht — genau der Befund dieser Karte. Die Mutation ist eine
	ECHTE Datei im gleichen Baum (und derselbe Scanner), kein Mock.
	"""
	with open(os.path.join(str(tmp_path), "mutant.mjs"), "w", encoding="utf-8") as fh:
		fh.write(
			"export async function a() { return fetch('/api/method/liste') }\n"
			"export async function b() { return fetch('/api/method/status') }\n"
		)
	# ROUTER-ALIAS-e (K3/K4): die SPA-Form OHNE `/api/method/` davor, und die
	# Datei-Bahn `ruf('<name>')` — hier `diakronos.diakonos.api.`, eine Bahn,
	# die `logout` NICHT deckt.
	with open(os.path.join(str(tmp_path), "mutant2.mjs"), "w", encoding="utf-8") as fh:
		fh.write(
			"const PRAEFIX = 'diakronos.diakonos.api.'\n"
			"export async function a() { return apiUrl('logout') }\n"
			"export async function b() { return apiCall('upload_file') }\n"
			"export async function c() { return ruf('logout') }\n"
			"export async function d() { return apiUrl('gibtsnicht_xyz') }\n"
		)
	pfade = _kurzformen_in([str(tmp_path)])
	namen = [n for _d, _n, n in pfade]
	assert "liste" in namen, pfade
	assert "status" in namen, pfade
	# Beides sind GESTRICHENE Kurzformen — der Waechter sieht sie also.
	assert [n for n in namen if n in _VERBOTEN], "der Waechter sieht die Mutation nicht"
	# Und die nackten SPA-Aufrufe: gesehene Kurznamen UND ein unbekannter
	# Name, den `_ERLAUBTE_KURZNAMEN` nicht kennt (`unbekannt`-Check des
	# Waechters wird damit rot — vorher blieb K3 gruen).
	assert {"logout", "upload_file"} <= set(namen), pfade
	# Gesehen: `apiUrl('logout')` und `ruf('logout')` (der Name steht in beiden
	# Formen in der Zeile), `apiCall('upload_file')`.
	assert namen.count("logout") == 2, pfade
	assert sorted(set(namen) - set(_ERLAUBTE_KURZNAMEN)) == [
		"gibtsnicht_xyz",
		"liste",
		"status",
	], namen


def test_durchreicher_und_bauer_werden_unterschieden(tmp_path):
	"""ROUTER-ALIAS-f: `_LOKALES_RUF` nimmt nur noch WIRKLICHE Bauer aus.

	Befund der Karte: Die Ausnahme traf jede Datei mit eigener Deklaration
	gleichen Namens. `papierkorb.mjs:21` und `rueckgaengigWeg.mjs:260`
	(`async function apiCall(...argumente) { return modul.apiCall(...argumente) }`)
	geben den Namen unveraendert weiter — ihr `apiCall('delete_lied')` ist ein
	fertiger Kurzname, wurde aber nie gescannt (Mutation X1/X6 blieben gruen).
	"""
	# (a) Durchreicher: kein Pfad wird gebaut -> wird gescannt.
	durchreicher = (
		"async function apiCall(...argumente) {\n"
		"\tconst modul = await import('./useApi.js')\n"
		"\treturn modul.apiCall(...argumente)\n"
		"}\n"
	)
	assert _baut_pfad(durchreicher) is False
	# (b) Baeuer ueber Template-Literal (RollenEinstellungen.vue:426/428) und
	#     ueber `PRAEFIX +` (useDevmodus.js:51) -> Ausnahme gilt.
	assert _baut_pfad(
		"async function ruf(fn, params) {\n"
		"\tconst antwort = await apiCall(`${RECHTS}.${fn}`, params)\n"
		"}\n"
	) is True
	assert _baut_pfad(
		"function ruf(methode, args = {}) {\n"
		"\treturn apiCall(PRAEFIX + methode, args)\n"
		"}\n"
	) is True
	# (c) `fetch(`${API}.${method}`)` (dashboardConfig.js:13) ebenso.
	assert _baut_pfad(
		"async function apiFetch(method, body = {}) {\n"
		"\tconst res = await fetch(`${API}.${method}`, { method: 'POST' })\n"
		"}\n"
	) is True
	# (d) Ein Kopf mit `method` ohne Zusammenbau im Rumpf ist ein Durchreicher
	#     (`useApi.js:169`: `return mitSitzungsdialog(() => apiCallRoh(...))`).
	assert _baut_pfad(
		"export async function apiCall(method, args = {}, options = {}) {\n"
		"\treturn mitSitzungsdialog(() => apiCallRoh(method, args, options))\n"
		"}\n"
	) is False
	# (e) Der Durchreicher wird jetzt gescannt (vorher war die Datei blind).
	with open(os.path.join(str(tmp_path), "durchreicher.mjs"), "w", encoding="utf-8") as fh:
		fh.write(durchreicher + "export const m = () => apiCall('delete_lied')\n")
	namen = [n for _d, _n, n in _kurzformen_in([str(tmp_path)])]
	assert namen == ["delete_lied"], namen
	tote = [n for _d, _n, n in _kurzformen_in([str(tmp_path)]) if n == "gibtsnicht_xyz"]
	assert tote == [], tote


def test_bauer_mit_bahn_meldet_toten_ruf(tmp_path):
	"""ROUTER-ALIAS-f (SOLL 3): `ruf('<name>')` in einem Baeuer wird geprueft.

	`RollenEinstellungen.vue:448` ruft `ruf('ernenne_mv')`; `ruf` baut daraus
	`${RECHTS}.${fn}` (Z. 428). Der Waechter muss einen toten Namen dort sehen
	(Mutation X3), ohne die legitimen Namen der Datei zu melden.
	"""
	# Bahn wie in der echten Datei (`api/rechte.py` sagt sie ueber
	# `praefix_zusagen` zu): `diakronos.api.rechte`. Der Waechter liest sie
	# als `_PRAEFIX` (`const PRAEFIX = 'diakronos.api.rechte.'`).
	with open(os.path.join(str(tmp_path), "bauer.vue"), "w", encoding="utf-8") as fh:
		fh.write(
			"const PRAEFIX = 'diakronos.api.rechte.'\n"
			"async function ruf(fn, params) {\n"
			"\treturn apiCall(`${PRAEFIX}${fn}`, params)\n"
			"}\n"
			"async function a() { return ruf('ernenne_mv', {}) }\n"
			"async function b() { return ruf('gibtsnicht_xyz', {}) }\n"
		)
	namen = [n for _d, _n, n in _kurzformen_in([str(tmp_path)])]
	assert "gibtsnicht_xyz" in namen, namen
