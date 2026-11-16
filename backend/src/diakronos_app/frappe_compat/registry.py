"""`@frappe.whitelist()` — registriert portierte API-Funktionen.

Im Altcode werden `whitelisted`-Funktionen ueber `/api/method/<dotted_path>`
erreichbar. Wir registrieren sie per Namenskonvention: wird das Modul
`diakronos_app.api.<modul>` importiert, kennt der Router `<modul>.<funktion>`
(bzw. den vollen dotted path) — genau die Pfade, die die SPA aufruft.

Der Dekorator ist absichtlich ein No-op bis auf die Registrierung: die
Funktionssignatur bleibt unveraendert, damit die Funktionen sich verhalten wie
in Frappe (Keyword-Argumente aus dem Request).
"""

from __future__ import annotations

import importlib
import sys
from typing import Callable

_REGISTRY: dict[str, Callable] = {}
# Optionen je Registrierung (z. B. `allow_guest=False`). Der Router wertet sie
# aus; der Wrapper selbst ist ein No-op, damit die Signatur unveraendert bleibt.
_OPTIONS: dict[int, dict] = {}
# ROUTER-ALIAS: ausdrueckliche Re-Export-/Alias-Zusagen
# (`register_with_frappe_module`) als `(modul, name)` -> Funktion. Nur diese
# duerfen einen Pfad beanspruchen, der NICHT der Original-Pfad der Funktion ist
# (Altcode-Alias wie `diakronos.diakronos.api.website.…`).
_REEXPORTE: dict[tuple[str, str], Callable] = {}
#: Ausdrueckliche PRAEFIX-Zusagen eines Moduls: `modul` -> Praefixe, unter
#: denen JEDE seiner registrierten Funktionen stehen darf. Dieselbe Zusage wie
#: `register_with_frappe_module`, nur fuer eine ganze Modulbahn statt einen
#: Namen — fuer Bahnen, die der Altcode/das Frontend benutzt und die aus dem
#: Python-Paketpfad NICHT ableitbar sind (`diakronos.api.rechte` fuer
#: `diakronos_app.api.rechte`, R-7-Nachzug 2026-11). Ein FREMDES Praefix bleibt
#: 404: zugesagt wird genau die genannte Bahn, nicht „irgendein Praefix“.
_PRAEFIXE: dict[str, tuple[str, ...]] = {}


def praefix_zusagen(modul: str, praefixe: str | tuple[str, ...]) -> None:
	"""Sagt zu: Funktionen aus `modul` duerfen unter diesen Praefixen stehen.

	Aufruf im API-Modul selbst (Importzeit), neben `FRAPPE_MODULE`:

	    praefix_zusagen(__name__, "diakronos.api.rechte")
	    -> `diakronos.api.rechte.get_rollen_erklaerung` loest auf
	    -> `diakronos.planrahmen.api.get_rollen_erklaerung` NICHT (fremd)

	Idempotent; mehrfaches Zusagen ist harmlos.
	"""
	if isinstance(praefixe, str):
		praefixe = (praefixe,)
	neu = [p.strip(".") for p in praefixe if str(p).strip(".")]
	alt = set(_PRAEFIXE.get(modul, ()))
	_PRAEFIXE[modul] = tuple(sorted(alt | set(neu)))

#: Frappe-Kernpfade ohne Modulbahn: der Altcode hat sie als `login`, `logout`,
#: `frappe.login`, `frappe.client.insert`, `upload_file` aufgerufen. Diese
#: Schreibweisen bleiben — jede ANDERE Bahn auf einen Kernnamen waere
#: Pfadverwirrung (ROUTER-ALIAS, Punkt 3 der Nachbesserung).
#:
#: `frappe.sessions.get_csrf_token` (R-7-Nachzug 2026-11) gehoert dazu: die
#: Gastseite (`frontend/src/gastinhalt/App.vue`) holt den Token unter genau
#: dieser Adresse nach, und `auth_middleware._WEITERE_AUSNAHMEN` nimmt sie vom
#: CSRF-Zwang aus. Die Funktion ist `api/session.sitzung_status`; ihre eigene
#: Bahn bleibt daneben (`…api.session.sitzung_status`).
#:
#: AUSNAHME `login`: LOGIN-4/A verlangt ausdruecklich, dass der Login unter
#: JEDEM Praefix (`x.auth.login`, `a.b.c.login`) DIESELBEN Sperren traegt —
#: ein beliebiger Vorlauf darf eine Login-Anmeldung nicht an CSRF-Methoden-
#: und Body-Regeln vorbeifuehren. `is_login` erkennt ihn am Funktionsobjekt,
#: damit ist jeder Alias so streng wie `login` selbst. Diese eine Ausnahme ist
#: gewollt und getestet (`test_login4_aliaspfade.py`).
_KERNPFADE = frozenset(
	{
		"login",
		"logout",
		"frappe.login",
		"frappe.login.login",
		"frappe.client.insert",
		"frappe.sessions.get_csrf_token",
		"upload_file",
	}
)

#: Kernpfad-Schreibweisen, die auf ein ANDERES Ziel zeigen als ihr Name sagt:
#: `pfad` -> `(python_modul, funktion)`. Die Zuordnung steht als Tabelle hier,
#: weil sie NICHT aus dem Namen folgt (siehe `_KERNPFAD_ZIEL`).
#:
#: ROUTER-ALIAS-c: Frueher las `_KERNPFAD_ZIEL` das Ziel IM REGISTER. Es steht
#: dort aber nicht — `_register` legt nur die Bahn
#: `diakronos.diakonos.api.session.sitzung_status` an, und ein Eintrag unter
#: dem Frappe-Pfad entsteht nie. Ergebnis: `frappe.sessions.get_csrf_token` war
#: im Router ein 404, waehrend der Waechter „loest auf“ meldete, weil er
#: `_ist_eigener_pfad` ODER `lookup` fragte. Deshalb steht das Ziel jetzt als
#: (Modul, Funktion) hier — KEIN Register-Schreibzugriff, keine zweite Wahrheit
#: ueber die Funktion selbst.
_KERNPFAD_UMLEITUNG: dict[str, tuple[str, str]] = {
	"frappe.sessions.get_csrf_token": ("diakronos_app.api.session", "sitzung_status"),
}

#: Python-Paket der portierten API und das Altcode-Praefix davor. Aus
#: `diakronos_app.api.zugang.setze_rollen` wird so
#: `diakronos.diakonos.api.zugang.setze_rollen` (die Bahn des Altcodes
#: `diakronos/diakonos/api/zugang.py`) — Modulbahnen, die der Altcode benutzt
#: hat, gehen damit NICHT verloren, ohne dass ein fremdes Praefix auf einen
#: beliebigen Namen aufloesen darf.
_API_PAKET = "diakronos_app.api."
_ALTCODE_PRAEFIX = "diakronos.diakonos.api"

#: Module, deren Funktionen Frappe-KERNPFADE sind (keine App-Modulbahn).
_KERN_MODULE = frozenset({"diakronos_app.api.auth"})


def options_for(fn: Callable) -> dict:
	"""Registrierungs-Optionen einer whitelisted Funktion."""
	return _OPTIONS.get(id(fn), {})


def whitelist(*dargs, **dkwargs):
	"""Unterstuetzt `@whitelist()` und `@whitelist`.

	SEC-11 (CRIT-1): zusaetzlich `methods=[...]` wie in Frappe:

	    @whitelist(methods=["POST"])     # schreibender Endpunkt
	    @whitelist(allow_guest=True, methods=["POST"])

	Der Wert ist eine Liste von HTTP-Methoden (oder ein einzelner String). Der
	Router laesst fuer die Funktion NUR diese Methoden zu; jede andere endet mit
	405 und fuehrt nichts aus (`router._erlaubte_methoden`). Ohne Angabe bleibt
	alles wie bisher (GET/POST/PUT/PATCH) — deshalb ist die Umstellung je
	Endpunkt eine sichtbare, pruefbare Entscheidung und keine stille.

	BS-1c2 (F3): zusaetzlich `preflight="self"` — NUR der so angemeldete
	Endpunkt bekommt den OPTIONS-Preflight hereingereicht und beantwortet ihn
	selbst (Herkunft/CORS, Kontaktformular BS-1c/K4). Ohne diese Anmeldung
	antwortet der Router auf OPTIONS mit einer leeren 204 und fuehrt nichts
	aus (`router._beantwortet_preflight_selbst`).
	"""
	# direkte Nutzung: @whitelist
	if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
		return _register(dargs[0], {})

	# parametrisierte Nutzung: @whitelist(allow_guest=True, methods=["POST"])
	def decorator(fn: Callable) -> Callable:
		return _register(fn, dict(dkwargs))

	return decorator


def _normalisiere_methoden(wert) -> tuple[str, ...] | None:
	"""`methods` aus dem Dekorator in eine aufsteigend sortierte Tupelform."""
	if wert is None:
		return None
	if isinstance(wert, str):
		wert = [wert]
	methoden = {str(m).strip().upper() for m in wert if str(m).strip()}
	if not methoden:
		return None
	unbekannt = methoden - _BEKANNTE_METHODEN
	if unbekannt:
		raise ValueError(f"Unbekannte HTTP-Methode(n) in @whitelist(methods=…): {sorted(unbekannt)}")
	return tuple(sorted(methoden))


#: Was der Router ueberhaupt annimmt (er routet GET/POST/PUT/PATCH).
_BEKANNTE_METHODEN = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"})


def methoden_fuer(fn: Callable) -> tuple[str, ...] | None:
	"""Erlaubte HTTP-Methoden dieser Registrierung — `None` = keine Einschraenkung."""
	return options_for(fn).get("methods")


def _register(fn: Callable, options: dict | None = None) -> Callable:
	options = dict(options or {})
	if "methods" in options:
		options["methods"] = _normalisiere_methoden(options["methods"])
	_OPTIONS[id(fn)] = {"allow_guest": False, **options}
	module = fn.__module__
	# `diakronos_app.api.mitglieder.get_mitglieder_liste` -> `mitglieder.get_...`
	short_module = module.split(".")[-1] if module else ""
	flavours = {fn.__name__, f"{short_module}.{fn.__name__}"}
	if module.startswith("diakronos_app.api."):
		rel = module[len("diakronos_app.api."):]
		flavours.add(f"{rel}.{fn.__name__}")
		# Erstes Segment der relativen Modulbahn (z. B. `mitglieder` aus
		# `mitglieder.list`), damit auch Kurzpfade aufloesen.
		flavours.add(f"{rel.split('.')[0]}.{fn.__name__}")
	if module.startswith("diakronos_app.api"):
		flavours.add(f"api.{fn.__name__}")
	# Der ORIGINAL-Frappe-Pfad. Die SPA ruft ausschliesslich diese Form auf,
	# z. B. `diakronos.diakonos.api.gruppen.get_gruppe_detail` oder
	# `diakronos.kronos.api.calendar_get.get_calendar_events`. Ohne diesen
	# Eintrag ist ein portierter Endpunkt fuer das Frontend nicht erreichbar —
	# und keine Testsuite merkt das, weil Tests die Kurzform benutzen.
	# Jedes portierte API-Modul deklariert dafuer eine Modulkonstante, direkt
	# NACH `from __future__ import annotations` (davor -> SyntaxError):
	#     FRAPPE_MODULE = "diakronos.diakonos.api.gruppen"
	frappe_module = getattr(sys.modules.get(module), "FRAPPE_MODULE", None)
	if frappe_module:
		flavours.add(f"{frappe_module}.{fn.__name__}")
	for key in flavours:
		_REGISTRY[key] = fn
	# Vollstaendiger dotted path als Fallback.
	_REGISTRY[f"{module}.{fn.__name__}"] = fn
	return fn


def _original_modul(fn: Callable) -> str | None:
	"""`FRAPPE_MODULE` des Moduls, in dem `fn` definiert ist (sonst `None`)."""
	module = getattr(fn, "__module__", None)
	frappe_module = getattr(sys.modules.get(module or ""), "FRAPPE_MODULE", None)
	return frappe_module if frappe_module else None


def _ist_kernfunktion(fn: Callable) -> bool:
	"""True, wenn `fn` zu den Frappe-KERNPFADEN gehoert (login, logout, …).

	Erkannt wird das am MODUL, nicht am Namen: `diakronos_app.api.auth.login`
	und `diakronos_app.api.frappe_core.logout`/`insert`/`upload_file` tragen
	keine App-Modulbahn. Gleichnamige Fachfunktionen (`root.status`,
	`verantwortliche.setze_rollen`) sind KEINE Kernfunktionen — sonst haetten
	sie wieder einen Freibrief unter jedem Praefix.

	ROUTER-ALIAS-d: Ein UMLEITUNGSZIEL ist hier NICHT dabei. Frueher zaehlte
	`_KERNPFAD_UMLEITUNG`-Ziele (`frappe.sessions.get_csrf_token` ->
	`sitzung_status`) als Kernfunktion — und bekam damit ueber
	`ist_originalpfad` JEDE Schreibweise aus `_KERNPFADE`: `logout` zeigte
	auf `sitzung_status`. Die Zusage eines Umleitungsziels ist genau EIN
	Pfad; sie wird in `ist_originalpfad`/`_ist_umleitungsziel` geprueft.
	"""
	if _original_modul(fn) is not None:
		return False
	module = getattr(fn, "__module__", "") or ""
	if module in _KERN_MODULE:
		return True
	return getattr(sys.modules.get(module or ""), "__name__", "").endswith(".frappe_core")


def _kernpfad_ziele() -> dict[str, Callable]:
	"""Aufgeloeste `_KERNPFAD_UMLEITUNG` (Pfad -> Funktion), ohne zu importieren."""
	ziele: dict[str, Callable] = {}
	for pfad, (modul, name) in _KERNPFAD_UMLEITUNG.items():
		geladen = sys.modules.get(modul)
		ziel = getattr(geladen, name, None) if geladen is not None else None
		if callable(ziel):
			ziele[pfad] = ziel
	return ziele


def _ist_login(fn: Callable) -> bool:
	"""True, wenn `fn` DAS Login-Funktionsobjekt der App ist (`api.auth.login`)."""
	try:
		from diakronos_app.api.auth import login as _login_fn
	except Exception:  # noqa: BLE001 — ohne api-Modul gibt es keinen Login
		return False
	return fn is _login_fn


def _ist_eigene_definition(fn: Callable) -> bool:
	"""True, wenn `fn` in seinem `__module__` definiert ist (nicht nur importiert).

	`__module__` traegt bei einer importierten Funktion den Ursprungsort, das
	Modulobjekt kennt sie aber als fremden Namen — genau daran unterscheiden
	wir „gehoert hier hin“ von „wird hier nur weitergereicht“.
	"""
	module = getattr(fn, "__module__", None)
	modulobjekt = sys.modules.get(module or "")
	if modulobjekt is None:
		return False
	return getattr(modulobjekt, getattr(fn, "__name__", ""), None) is fn


def _original_pfade(fn: Callable) -> set[str]:
	"""Alle Pfade, unter denen `fn` von RECHTS wegen steht.

	Das ist ihr `FRAPPE_MODULE`-Pfad (so ruft der Altcode und die SPA sie auf),
	ihr voller Python-Pfad und jede ausdrueckliche Re-Export-/Alias-Zusage
	(`register_with_frappe_module`).

	`FRAPPE_MODULE` zaehlt NUR, wenn die Funktion in genau diesem Modul steht
	(`_ist_eigene_definition`): sonst wuerde die Konstante eines
	Weiterreich-Moduls fuer jede mitgenommene fremde Funktion gelten — genau
	die Pfadverwirrung aus dem Befund. Fuer Funktionen aus einem Modul OHNE
	Konstante gilt der volle Python-Pfad: `diakronos_app.api.zugang.setze_rollen`
	-> `diakronos.diakonos.api.zugang.setze_rollen` (Altcode-Bahn `api/zugang.py`).
	"""
	zulaessig: set[str] = set()
	name = getattr(fn, "__name__", None)
	module = getattr(fn, "__module__", None)
	if name and module:
		zulaessig.add(f"{module}.{name}")
	frappe_module = _original_modul(fn)
	if name and frappe_module and _ist_eigene_definition(fn):
		zulaessig.add(f"{frappe_module}.{name}")
	# Modulbahnen mit Altcode-Praefix (`diakronos_app.api.<pfad>` ->
	# `diakronos.diakonos.api.<pfad>`), fuer Module ohne `FRAPPE_MODULE`.
	if name and module and module.startswith(_API_PAKET):
		zulaessig.add(f"{_ALTCODE_PRAEFIX}.{module[len(_API_PAKET):]}.{name}")
	for (modul, kurzname), ziel in _REEXPORTE.items():
		if ziel is fn:
			zulaessig.add(f"{modul}.{kurzname}")
	# Praefix-Zusagen des EIGENEN Moduls (`praefix_zusagen`): genau diese
	# Bahnen, nicht „irgendein Praefix“.
	if name and module:
		for praefix in _PRAEFIXE.get(module, ()):
			zulaessig.add(f"{praefix}.{name}")
	return zulaessig


def ist_originalpfad(path: str, fn: Callable) -> bool:
	"""True, wenn `path` ein Pfad ist, der `fn` WIRKLICH gehoert.

	ROUTER-ALIAS: Der Router darf unter einem Pfad nur ausfuehren, was dort
	auch hingehoert — der `FRAPPE_MODULE`-Pfad der Funktion, ihr voller
	Python-Pfad, ein ausdruecklich ueber `register_with_frappe_module`
	eingetragener Re-Export oder (nur fuer Frappe-Kernfunktionen) eine der
	Schreibweisen aus `_KERNPFADE`.

	EINE Ausnahme, sicherheitsbegruendet (LOGIN-4/A): der LOGIN loest unter
	jedem Praefix auf, solange der Name `login` stimmt. Das ist keine
	Pfadverwirrung, sondern die Abwehr einer Umgehung: alle Login-Sperren
	(Nur-POST, `usr`/`pwd` nur aus dem Body, Herkunft) haengen am
	FUNKTIONSOBJEKT (`router.is_login`), sodass ein Alias wie `x.auth.login`
	genauso streng behandelt wird wie `login`. Wuerde der Alias 404en, waere
	das Verhalten nur schwerer nachvollziehbar — die Sperre bliebe gleich.
	`logout`, `insert`, `upload_file` haben diese Ausnahme NICHT.

	Alles andere ist Pfadverwirrung (ein Endpunkt erscheint unter einem fremden
	Modul) und endet mit 404. Es gibt KEINEN Freibrief fuer Module ohne
	`FRAPPE_MODULE`: auch der Kernname `root_uebertragen` ist unter
	`diakronos.planrahmen.api.root_uebertragen` nicht erreichbar.

	ROUTER-ALIAS-d (Befund): Ein UMLEITUNGSZIEL (`frappe.sessions.
	get_csrf_token` -> `sitzung_status`) ist ueber seine Frappe-Adresse
	erreichbar — aber NUR ueber die eine Adresse aus `_KERNPFAD_UMLEITUNG`.
	Frueher zaehlte es ueber `_ist_kernfunktion` als Kernfunktion und bekam
	damit JEDE Kernpfad-Schreibweise: `ist_originalpfad("logout",
	sitzung_status)` war `True`. Jetzt wird ein Umleitungsziel ausschliesslich
	gegen seinen EIGENEN Umleitungspfad geprueft.
	"""
	if not path or fn is None:
		return False
	if path in _original_pfade(fn):
		return True
	# ROUTER-ALIAS-d: Ein Umleitungsziel gehoert GENAU SEINEN Umleitungspfad —
	# und keinen weiteren Kernpfad (frueher: `ist_originalpfad("logout",
	# sitzung_status)` war True). Die Zusage steht NACH der eigenen Bahn,
	# damit `…session.sitzung_status` unberuehrt bleibt.
	if _ist_umleitungsziel(fn):
		return _KERNPFAD_UMLEITUNG.get(path) == (
			getattr(fn, "__module__", ""),
			getattr(fn, "__name__", ""),
		)
	# LOGIN-4/A (SICHERHEITS-Ausnahme, ausdruecklich): der Login loest unter
	# jedem Praefix auf, solange der Name `login` stimmt — ohne Bedingung an
	# den Vorlauf, wie `test_login4_aliaspfade` und der Waechter es verlangen.
	# Alle Login-Sperren (Nur-POST, `usr`/`pwd` nur aus dem Body, Herkunft)
	# haengen am FUNKTIONSOBJEKT (`router.is_login`), ein Alias wie
	# `x.auth.login` ist damit genauso streng wie `login` selbst.
	if _ist_login(fn) and path.rsplit(".", 1)[-1] == "login":
		return True
	if _ist_kernfunktion(fn):
		return path in _KERNPFADE
	return False


def _ist_umleitungsziel(fn: Callable) -> bool:
	"""True, wenn `fn` das ZIEL einer `_KERNPFAD_UMLEITUNG` ist.

	Der Vergleich laeuft ueber das FUNKTIONSOBJEKT (`is`), nicht ueber den
	Namen — eine gleichnamige Funktion eines anderen Moduls ist kein Ziel.
	"""
	return any(fn is ziel for ziel in _kernpfad_ziele().values())


def lookup(path: str) -> Callable | None:
	"""Findet die Funktion zu einem dotted path (z. B. `mitglieder.get_...`)."""
	return _REGISTRY.get(path)


def registriere_originalpfad(path: str) -> bool:
	"""Sagt, ob der angefragte Pfad danach aufloest — und traegt NICHTS ein.

	ROUTER-ALIAS (Befund R-7): Frueher wurde das VORLETZTE Pfadsegment als
	Kurzmodul genommen (`…planrahmen.api.delete_lied` -> Modul `api`, Funktion
	`delete_lied`) — damit loeste ein beliebiges Praefix auf eine fremde
	Funktion auf und der Endpunkt erschien unter einem Modul, zu dem er nicht
	gehoert.

	Jetzt gilt: nur was der Funktion WIRKLICH gehoert, loest auf — ihr
	`FRAPPE_MODULE`-Pfad, ihr voller Python-Pfad, ihre Altcode-Modulbahn
	(`diakronos.diakonos.api.<modul>.<fn>`), eine ausdrueckliche
	Re-Export-Zusage (`register_with_frappe_module`) oder (nur fuer
	Frappe-Kernfunktionen) eine Schreibweise aus `_KERNPFADE`. Alles andere:
	`False` (404).

	Wichtig seit der Nachbesserung: Die Funktion LIEST nur noch. Frueher
	trug jeder angenommene Pfad sich selbst ins Register ein (`_REGISTRY[path]
	= fn`) — damit wuchs das Register mit jeder Anfrage, und ein Kernname
	(`login`) war unter jedem Praefix dauerhaft erreichbar. Solche Pfade legt
	ausschliesslich `register_with_frappe_module` an, und zwar im Code.

	ROUTER-ALIAS-c: Das gilt auch fuer den LOGIN-Alias. LOGIN-4/A verlangt
	nur, dass ein Alias WIE der Login behandelt wird (erkannt am
	Funktionsobjekt), nicht dass er im Register steht. Frueher setzte diese
	Funktion ihn (`_REGISTRY[path] = fn`): 300 Anfragen `z<i>.login` = 300
	Registereintraege, und jeder Eintrag war danach ein Pfad, der auch ohne
	diese Funktion aufloeste. Der Alias wird jetzt nur noch BEANTWORTET.
	"""
	if not path or "." not in path:
		return False
	if path in _KERNPFADE:
		fn = _KERNPFAD_ZIEL(path)
		return fn is not None and _ist_kernfunktion(fn)
	fn = _REGISTRY.get(path)
	if fn is not None:
		return ist_originalpfad(path, fn)
	# Kein Eintrag: Die Frage „gehoert der Pfad einer registrierten Funktion?“
	# wird direkt beantwortet — gesucht werden ALLE Funktionen, die unter
	# diesem Namen bekannt sind (Kurzpfade, volle Python-Pfade, Kernnamen).
	# Frueher wurde das vorletzte Segment als Modul interpretiert und die
	# Funktion von dort gezogen; das war die Verwechslung aus R-7
	# (`…planrahmen.api.delete_lied` -> Modul `api` -> `musik.delete_lied`).
	name = path.rsplit(".", 1)[-1]
	gesehen: set[int] = set()
	for kurzpfad, fn in list(_REGISTRY.items()):
		if kurzpfad.rsplit(".", 1)[-1] != name or id(fn) in gesehen:
			continue
		gesehen.add(id(fn))
		if id(fn) not in _OPTIONS:
			# Nicht als Endpunkt (whitelist) bekannt -> nicht erfinden.
			continue
		if not ist_originalpfad(path, fn):
			continue
		# LOGIN-4/A: Der Login-Alias wird ANGENOMMEN (die Sperren gelten fuer
		# ihn, weil der Router `ist_login(fn)` fragt) — aber NICHT ins Register
		# geschrieben (ROUTER-ALIAS-c: sonst waechst es mit jeder Anfrage).
		return True
	return False


def _KERNPFAD_ZIEL(path: str) -> Callable | None:  # noqa: N802 — Kernpfad-Tabelle
	"""Funktion hinter einer Kernpfad-Schreibweise (`login`, `frappe.client.insert`).

	Die Umleitung (`frappe.sessions.get_csrf_token`) zeigt auf ein PYTHON-Modul
	und wird ueber `importlib` geladen — das Ziel registriert sich beim Import
	selbst, ein Eingriff ins Register ist dafuer nicht noetig und nicht
	gewuenscht (`registered()` bleibt die Liste der Registrierungen, nicht der
	Anfragen). Der Name der Funktion ist der letzte Pfadteil.

	Der Import ist idempotent und harmlos: er laedt ein Modul des EIGENEN
	Pakets, nie einen Namen aus der Anfrage (siehe `router._vorbedingung`).
	"""
	umleitung = _KERNPFAD_UMLEITUNG.get(path)
	if umleitung is not None:
		modul_name, funktion = umleitung
		try:
			modul = sys.modules.get(modul_name) or importlib.import_module(modul_name)
		except ImportError:
			return None
		ziel = getattr(modul, funktion, None)
		return ziel if callable(ziel) else None
	# Registry-Eintrag, sonst `frappe.login` -> `frappe.login.login`.
	# (`login`, `logout`, `upload_file` liegen NICHT im Register: sie sind
	# Kernpfade, keine App-Endpunkte — ein leerer Rueckgabewert ist dort richtig.)
	return _REGISTRY.get(path) or _REGISTRY.get(f"{path}.{path.rsplit('.', 1)[-1]}")


def register_with_frappe_module(frappe_module: str, name: str, fn: Callable) -> Callable:
	"""Registriert `fn` zusaetzlich unter `<frappe_module>.<name>`.

	Fuer die RE-EXPORTS des Altcodes: `calendar_get.get_accessible_calendars`
	ist im Original nur `from .permissions import get_accessible_calendars`.
	Die Modulkonstante `FRAPPE_MODULE` deckt das nicht ab, weil
	`_register` sie aus `sys.modules[fn.__module__]` liest — die Funktion
	traegt aber das `permissions`-Modul. Diese Funktion ergaenzt den
	Original-Pfad deshalb explizit, ueber DENSELBEN Mechanismus (nur mit dem
	Modul als Parameter). Idempotent: mehrfaches Registrieren ist harmlos.

	ROUTER-ALIAS: Das ist die EINZIGE Stelle, an der ein Pfad entstehen darf,
	der nicht der Original-Pfad der Funktion ist (Altcode-Alias wie
	`gestaltung.lesen` oder `website.oeffentlich.kalender`). Der Pfad wird
	deshalb als Zusage in `_REEXPORTE` vermerkt; `ist_originalpfad` liest sie.

	Die Optionen (`allow_guest`) bleiben an der Funktion selbst haengen, es
	ist dieselbe Funktion — der Router wertet sie ueber `options_for` aus.
	"""
	_REEXPORTE[(frappe_module, name)] = fn
	_REGISTRY[f"{frappe_module}.{name}"] = fn
	return fn


def nachregistrieren() -> int:
	"""Ergaenzt fuer jede registrierte Funktion ihren `FRAPPE_MODULE`-Pfad.

	Warum: `_register` liest `FRAPPE_MODULE` beim Auswerten des Dekorators aus
	`sys.modules[fn.__module__]`. Erfolgt der Import eines API-Moduls ueber
	einen anderen Einstieg als `diakronos_app.api` (z. B. wenn `main.py` zuerst
	ein Untermodul zieht) und ist das Paket dabei noch nicht fertig, fehlt der
	Original-Pfad `diakronos.diakonos.api.<modul>.<funktion>` — die SPA
	erreicht den Endpunkt dann mit 404, obwohl die Kurzform aufloest.

	ROUTER-ALIAS-c: Diese Nachregistrierung laeuft EINMAL beim Start — am Ende
	von `diakronos_app.api` (`_nachregistrieren()`), und NIRGENDS sonst.
	Frueher lief sie zusaetzlich bei JEDEM Fehlgriff einer Anfrage ueber das
	ganze Register (CPU-Verstaerker ohne Anmeldung).

	ROUTER-ALIAS-d: Es gibt KEIN Flag, das sie einschaltete — der frueher
	hier genannte `nachregistrieren(frei=True)` existierte nie (weder als
	Parameter noch als Aufruf), und der Router ruft diese Funktion
	ueberhaupt nicht mehr auf. Idempotent: laeuft sie erneut, findet sie
	jeden Bahn-Eintrag bereits und setzt nichts.

	Rueckgabe: Zahl der (neu) gesetzten Eintraege.
	"""
	gesetzt = 0
	for kurzpfad, fn in list(_REGISTRY.items()):
		# Nur die EIGENE Definition zaehlt: eine Konstante eines
		# Weiterreich-Moduls (`api/auth.py` traegt `FRAPPE_MODULE` fuer `login`,
		# nicht fuer das mitgenommene `logout`) darf keine fremden Funktionen
		# in die Bahn ziehen. Fuer Module OHNE Konstante (`api/zugang.py`, …)
		# traegt `_original_pfade` die Altcode-Bahn nach — dort muesste sonst
		# eine Konstante erfunden werden, nur damit die SPA-Bahn existiert.
		#
		# ROUTER-ALIAS-c: Iteriert wird ueber `list(_REGISTRY.items())`, weil
		# der Schleifenkoerper das Register erweitert (`_REGISTRY[key] = fn`) —
		# ueber die lebende Sicht war das ein `RuntimeError: dictionary changed
		# size` genau dann, wenn wirklich etwas fehlte.
		if getattr(fn, "__name__", None) is None:
			continue
		for key in sorted(_original_pfade(fn)):
			if key in _REGISTRY:
				continue
			# Nur Bahnen, die der Router auch als Methodenpfad annimmt:
			# `diakronos.diakonos.api.…`/`FRAPPE_MODULE`, nicht der volle
			# Python-Pfad `diakronos_app.…` (der ist im Register schon gesetzt).
			if key.startswith("diakronos_app."):
				continue
			_REGISTRY[key] = fn
			gesetzt += 1
	return gesetzt


def registered() -> dict[str, Callable]:
	return dict(_REGISTRY)


def nackte_namen_entfernen(funktionen) -> list[str]:
	"""Entfernt die NACKTEN Registernamen dieser Funktionen (BS-1b2/F7).

	`@whitelist` legt jede Funktion unter ihrem blossen `__name__` ab
	(`kalender`, `termine`, `gruppe`, …). Fuer die oeffentliche Lese-API sind
	diese Namen eine Kollisionsflaeche mit den gleichnamigen
	Verwaltungsfunktionen (`api/kronos/calendar_get.termine`,
	`api/gruppen.gruppen`) — je nach Importreihenfolge gewinnt eine der
	beiden Fassungen, und niemand merkt es.

	Entfernt werden nur Eintraege, die GENAU auf eine der uebergebenen
	Funktionen zeigen; alle anderen Namen (Kurzpfade, Frappe-Originalpfade,
	Fremdfunktionen) bleiben. Idempotent. Rueckgabe: die entfernten Namen.
	"""
	ziele = {id(fn) for fn in (funktionen or {}).values() if callable(fn)}
	entfernt = [
		key
		for key, fn in list(_REGISTRY.items())
		if "." not in key and id(fn) in ziele
	]
	for key in entfernt:
		_REGISTRY.pop(key, None)
	return entfernt
