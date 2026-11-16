"""ROUTER-ALIAS-d — Umleitungsziele loesen nur unter IHREM Pfad auf.

Befund: `_ist_kernfunktion` zaehlte die Ziele aus `_KERNPFAD_UMLEITUNG` als
Kernfunktionen. Damit bekam `sitzung_status` (Ziel von
`frappe.sessions.get_csrf_token`) JEDE Schreibweise aus `_KERNPFADE` —
insbesondere `logout`:

    ist_originalpfad("logout", sitzung_status)  ->  True

Die Zusage eines Umleitungsziels ist aber genau EIN Pfad („diese Frappe-Adresse
gehoert dieser Funktion“), nicht „jede Kernpfad-Schreibweise“. Geprueft wird
hier beides: die Zusage selbst UND ihr Fehlen fuer fremde Schreibweisen, am
echten Router.
"""

from __future__ import annotations

from diakronos_app.frappe_compat import registry, router

UMLEITUNG = "frappe.sessions.get_csrf_token"


def _register_vollstaendig() -> None:
	"""Laedt die App — und den Dev-Modus, wenn er EINGESCHALTET ist.

	ROUTER-ALIAS-e: Hier stand `devmodus_api.registriere()` OHNE `app`. Die
	Funktion verlangt `app` (TypeError), der von einem stillen
	`except Exception: pass` verschluckt wurde — die Dev-Modus-Bahn wurde
	also nie registriert. Jetzt gilt die Regel des Betriebs
	(`main.py:241`): `registriere(app)` MIT der App, ohne stilles `except`.

	Der Dev-Modus ist im Testlauf AUS (`DEVMODE_ENABLED` nicht gesetzt,
	siehe `devmodus/einstellungen.py`); `registriere` meldet das ueber
	`False` und importiert nichts — genau wie im Betrieb.
	"""
	from diakronos_app.devmodus import api as devmodus_api
	from diakronos_app.main import app

	devmodus_api.registriere(app)


def test_umleitungsziel_loest_nur_unter_seinem_pfad_auf():
	"""`sitzung_status` gehoert `frappe.sessions.get_csrf_token` — und nur dort."""
	_register_vollstaendig()
	from diakronos_app.api.session import sitzung_status

	assert registry.ist_originalpfad(UMLEITUNG, sitzung_status) is True
	# Der Befund dieser Karte: diese fuenf waren vorher ALLE True.
	for fremd in ("logout", "login", "frappe.login", "upload_file", "frappe.client.insert"):
		assert registry.ist_originalpfad(fremd, sitzung_status) is False, fremd
		# ROUTER-ALIAS-e: Hier stand
		# `assert registriere_originalpfad(fremd) is False or fremd != "logout"` —
		# fuer `logout` eine Tautologie (`X or False` == `X`), fuer die anderen
		# vier durch das `or` abgeschwaecht. Die echte Aussage ist: unter KEINER
		# dieser Schreibweisen kommt das UMLEITUNGSZIEL.
		ziel = registry._KERNPFAD_ZIEL(fremd)  # noqa: SLF001 — Kernpfad-Tabelle
		assert ziel is not sitzung_status, (fremd, getattr(ziel, "__name__", None))
		# Und der Router sieht dieselbe Antwort wie das Register — die zwei
		# Wege duerfen nicht auseinanderlaufen. Fuer Pfade FREMDE Schreibweisen
		# gilt das ausnahmslos: beide sagen `False`.
		if fremd not in registry._KERNPFADE:  # noqa: SLF001 — Kernpfad-Tabelle
			assert router._ist_eigener_pfad(fremd) is False, fremd
			assert registry.registriere_originalpfad(fremd) is False, fremd

	# ROUTER-ALIAS-f (Befund geschlossen): Die Kernpfad-Schreibweisen laufen
	# NICHT mehr auseinander. `registriere_originalpfad` fragt die Kernpfade
	# VOR der Punkt-Pruefung und antwortet mit derselben Regel wie der Router
	# (`_kernfunktion_unter_kernpfad`): der Pfad muss in `_KERNPFADE` stehen
	# UND diese Funktion bedienen — also nicht nur "ist eine Kernfunktion".
	# Vorher standen hier die zwei Befund-Zeilen
	# (`registriere_originalpfad("logout") is False`,
	# `registriere_originalpfad("frappe.login") is False`), obwohl der Router
	# beide bediente.
	for kernpfad in ("logout", "login", "frappe.login", "upload_file", "frappe.client.insert"):
		assert router._ist_eigener_pfad(kernpfad) is True, kernpfad
		assert registry.registriere_originalpfad(kernpfad) is True, kernpfad
		ziel_kern = registry._KERNPFAD_ZIEL(kernpfad)  # noqa: SLF001 — Kernpfad-Tabelle
		assert ziel_kern is not None, kernpfad
		# Und das Umleitungsziel bleibt unter KEINER dieser Schreibweisen.
		assert ziel_kern is not sitzung_status, kernpfad


def test_registriere_originalpfad_gleicht_router_und_docstring():
	"""ROUTER-ALIAS-f: Register-Antwort == Router-Antwort, auch ohne Punkt.

	Der Docstring von `registriere_originalpfad` sagt "loest der Pfad danach
	auf". Vorher war `registriere_originalpfad("logout")` `False`, obwohl
	`POST /api/method/logout` bedient wird — die Punkt-Pruefung stand vor der
	Kernpfad-Tabelle. Geprueft wird die Uebereinstimmung an beiden Enden:
	"""
	_register_vollstaendig()
	# (a) Kernpfade: Register sagt True, der Router bedient sie.
	for pfad in (
		"logout",
		"login",
		"frappe.login",
		"frappe.login.login",
		"upload_file",
		"frappe.client.insert",
		UMLEITUNG,
	):
		assert registry.registriere_originalpfad(pfad) is True, pfad
		assert router._aufloesen(pfad) is not None, pfad
	# (b) Fremd/erfunden: beide sagen False — die Kernpfad-Tabelle ist kein
	#     Freibrief (`api.logout`, `x.auth.login` ist die LOGIN-Ausnahme,
	#     nicht diese Regel).
	for pfad in ("gibtsnicht", "api.logout", "frappe.client.gibtsnicht", "x.y.z"):
		assert registry.registriere_originalpfad(pfad) is False, pfad
		assert router._ist_eigener_pfad(pfad) is False, pfad
	# (c) Die Regel, die BEIDE Funktionen benutzen, ist EINE:
	#     `_kernfunktion_unter_kernpfad` verlangt, dass der Pfad im Register
	#     steht UND in `_KERNPFADE`, UND dass `_KERNPFAD_ZIEL(path)` GENAU
	#     diese Funktion liefert — „ist eine Kernfunktion" allein genuegt
	#     fuer keinen zweiten Pfad.
	from diakronos_app.api.frappe_core import logout as kern_logout

	# ROUTER-ALIAS-g: Die Regel ist PFADGEBUNDEN — `path` ist Argument. Sie
	# prueft `path in _KERNPFADE` UND `_KERNPFAD_ZIEL(path) is fn`; die frueher
	# zusaetzlich oeffentliche `path_in_kernpfaden(fn)` (Parameter war `fn`,
	# kein Pfad) ist darin aufgegangen.
	assert registry._kernfunktion_unter_kernpfad(kern_logout, "logout") is True  # noqa: SLF001
	# ... aber NUR unter seinem eigenen Kernpfad (`upload_file` bedient eine
	# andere Funktion).
	assert registry._kernfunktion_unter_kernpfad(kern_logout, "upload_file") is False  # noqa: SLF001
	assert registry._kernfunktion_unter_kernpfad(kern_logout, "api.logout") is False  # noqa: SLF001
	# Eine App-Funktion (der Login) ist ueber diese Regel NICHT zugesagt —
	# ihre Schreibweisen kommen aus der LOGIN-Ausnahme.
	from diakronos_app.api.auth import login

	assert registry._kernfunktion_unter_kernpfad(login, "login") is False  # noqa: SLF001


def test_ist_kernfunktion_docstring_sagt_was_der_code_tut():
	"""ROUTER-ALIAS-f: `_ist_kernfunktion(login)` ist False — wie im Docstring.

	Der alte Docstring fuehrte `diakronos_app.api.auth.login` als
	Kernfunktion; der Code weist sie ab (`_original_modul` ist gesetzt). Der
	Login bekommt seine Schreibweisen ueber die LOGIN-Ausnahme
	(`ist_originalpfad`), nicht ueber diese Eigenschaft.
	"""
	_register_vollstaendig()
	from diakronos_app.api.auth import login

	from diakronos_app.api.frappe_core import logout as kern_logout

	assert registry._ist_kernfunktion(login) is False  # noqa: SLF001
	assert registry._ist_kernfunktion(kern_logout) is True  # noqa: SLF001
	# Trotzdem zugesagt: `login` und `frappe.login` bedient der Login.
	for pfad in ("login", "frappe.login"):
		assert registry.ist_originalpfad(pfad, login) is True, pfad
		assert registry.registriere_originalpfad(pfad) is True, pfad


def test_umleitungsziel_ist_keine_kernfunktion():
	"""Die Tabelle oeffnet EINEN Pfad — sie macht aus dem Ziel keine Kernfunktion."""
	_register_vollstaendig()
	from diakronos_app.api.session import sitzung_status

	assert registry._ist_kernfunktion(sitzung_status) is False  # noqa: SLF001
	# Die echten Kernfunktionen bleiben, was sie sind: `logout` steht in
	# `_KERNPFADE` und loest dort auf — unter `logout` steht jetzt `logout`.
	assert registry.lookup("logout") is not None
	assert registry.ist_originalpfad("logout", registry.lookup("logout")) is True


def test_umleitungspfad_bleibt_erreichbar(client, patched_db):
	"""HTTP-Gegenprobe: der zugesagte Pfad antwortet (kein Router-404)."""
	_register_vollstaendig()
	antwort = client.post(f"/api/method/{UMLEITUNG}", json={})
	assert antwort.json().get("message") != "Methode nicht gefunden", antwort.text
	# Ohne Sitzung ist die ehrliche Antwort 401 — der PFAD loest aber auf.
	assert antwort.json().get("exc_type") != "NotFound", antwort.text


def test_umleitungsziel_nicht_unter_kernpfad_schreibweise(client, patched_db):
	"""`sitzung_status` ist unter `logout` NICHT erreichbar (HTTP).

	Ohne die Korrektur haette dieser Aufruf die Sitzungsabfrage ausgefuehrt,
	statt den Logout — ein Endpunkt unter fremdem Namen.
	"""
	_register_vollstaendig()
	ziel = router._aufloesen("logout")  # noqa: SLF001
	assert ziel is not None
	assert getattr(ziel, "__name__", "") == "logout", getattr(ziel, "__name__", None)
	from diakronos_app.api.session import sitzung_status

	assert ziel is not sitzung_status
