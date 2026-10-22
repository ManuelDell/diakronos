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

import sys
from typing import Callable

_REGISTRY: dict[str, Callable] = {}
# Optionen je Registrierung (z. B. `allow_guest=False`). Der Router wertet sie
# aus; der Wrapper selbst ist ein No-op, damit die Signatur unveraendert bleibt.
_OPTIONS: dict[int, dict] = {}


def options_for(fn: Callable) -> dict:
	"""Registrierungs-Optionen einer whitelisted Funktion."""
	return _OPTIONS.get(id(fn), {})


def whitelist(*dargs, **dkwargs):
	"""Unterstuetzt `@whitelist()` und `@whitelist`.
	"""
	# direkte Nutzung: @whitelist
	if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
		return _register(dargs[0], {})

	# parametrisierte Nutzung: @whitelist(allow_guest=True)
	def decorator(fn: Callable) -> Callable:
		return _register(fn, dict(dkwargs))

	return decorator


def _register(fn: Callable, options: dict | None = None) -> Callable:
	_OPTIONS[id(fn)] = {"allow_guest": False, **(options or {})}
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


def lookup(path: str) -> Callable | None:
	"""Findet die Funktion zu einem dotted path (z. B. `mitglieder.get_...`)."""
	return _REGISTRY.get(path)


def registriere_originalpfad(path: str) -> bool:
	"""Setzt den Original-Frappe-Pfad `diakronos.diakonos.api.<modul>.<fn>`.

	Deterministische Alternative zu `nachregistrieren()` fuer den konkreten
	angefragten Pfad: aus `diakronos.diakonos.api.admin_hub.get_statistik`
	wird ueber das bereits bekannte Kurzmodul (`admin_hub.get_statistik`) die
	Funktion gefunden und unter ihrem Original-Pfad eingetragen. Greift
	unabhaengig von Importreihenfolge und ohne das Register zu durchlaufen.

	Rueckgabe: True, wenn der Pfad danach aufloest.
	"""
	if path in _REGISTRY:
		return True
	parts = path.split(".")
	if len(parts) < 2:
		return False
	name = parts[-1]
	module = parts[-2]  # z. B. "admin_hub" aus "...api.admin_hub.get_statistik"
	fn = _REGISTRY.get(f"{module}.{name}")
	if fn is None:
		# Modul direkt importieren und die Funktion von dort ziehen.
		try:
			import importlib

			mod = importlib.import_module(f"diakronos_app.api.{module}")
			fn = getattr(mod, name, None)
		except ImportError:
			fn = None
	if fn is None or not callable(fn):
		return False
	if id(fn) not in _OPTIONS:
		# Nicht als Endpunkt (whitelist) bekannt -> nicht erfinden.
		return False
	_REGISTRY[path] = fn
	return True


def register_with_frappe_module(frappe_module: str, name: str, fn: Callable) -> Callable:
	"""Registriert `fn` zusaetzlich unter `<frappe_module>.<name>`.

	Fuer die RE-EXPORTS des Altcodes: `calendar_get.get_accessible_calendars`
	ist im Original nur `from .permissions import get_accessible_calendars`.
	Die Modulkonstante `FRAPPE_MODULE` deckt das nicht ab, weil
	`_register` sie aus `sys.modules[fn.__module__]` liest — die Funktion
	traegt aber das `permissions`-Modul. Diese Funktion ergaenzt den
	Original-Pfad deshalb explizit, ueber DENSELBEN Mechanismus (nur mit dem
	Modul als Parameter). Idempotent: mehrfaches Registrieren ist harmlos.

	Die Optionen (`allow_guest`) bleiben an der Funktion selbst haengen, es
	ist dieselbe Funktion — der Router wertet sie ueber `options_for` aus.
	"""
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

	Diese Nachregistrierung laeuft am Ende von `diakronos_app.api` und traegt
	den Original-Pfad fuer ALLE bereits bekannten Funktionen nach. Idempotent.
	Rueckgabe: Zahl der (neu) gesetzten Eintraege.
	"""
	gesetzt = 0
	for fn in list(_REGISTRY.values()):
		module = getattr(fn, "__module__", None)
		frappe_module = getattr(sys.modules.get(module or ""), "FRAPPE_MODULE", None)
		if not frappe_module or not getattr(fn, "__name__", None):
			continue
		key = f"{frappe_module}.{fn.__name__}"
		if key not in _REGISTRY:
			_REGISTRY[key] = fn
			gesetzt += 1
	return gesetzt


def registered() -> dict[str, Callable]:
	return dict(_REGISTRY)
