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

	# BEKANNTER BEFUND (hier nur festgehalten, nicht geheilt — diese Karte
	# aendert keinen Produktivcode): bei den Kernpfad-Schreibweisen laufen die
	# zwei Wege auseinander. `registriere_originalpfad` weist ALLES ohne Punkt
	# pauschal ab (`"." not in path -> False`), obwohl der Router `logout`,
	# `login`, `upload_file` ueber `_KERNPFAD_ZIEL` bedient — HTTP-Beleg:
	# `test_kernpfade_bleiben_offen` (POST /api/method/logout -> kein NotFound).
	# `frappe.login` ist der zweite Fall: der Router loest auf, das Register
	# findet keinen Eintrag. Beides gehoert in eine eigene Karte.
	assert router._ist_eigener_pfad("logout") is True
	assert registry.registriere_originalpfad("logout") is False  # <- Befund
	assert router._ist_eigener_pfad("frappe.login") is True
	assert registry.registriere_originalpfad("frappe.login") is False  # <- Befund


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
