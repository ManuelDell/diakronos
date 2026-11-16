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
	from diakronos_app.main import app  # noqa: F401

	try:
		from diakronos_app.devmodus import api as devmodus_api

		devmodus_api.registriere()
	except Exception:  # noqa: BLE001 — ohne Dev-Modus gibt es diese Module nicht
		pass


def test_umleitungsziel_loest_nur_unter_seinem_pfad_auf():
	"""`sitzung_status` gehoert `frappe.sessions.get_csrf_token` — und nur dort."""
	_register_vollstaendig()
	from diakronos_app.api.session import sitzung_status

	assert registry.ist_originalpfad(UMLEITUNG, sitzung_status) is True
	# Der Befund dieser Karte: diese vier waren vorher ALLE True.
	for fremd in ("logout", "login", "frappe.login", "upload_file", "frappe.client.insert"):
		assert registry.ist_originalpfad(fremd, sitzung_status) is False, fremd
		assert registry.registriere_originalpfad(fremd) is False or fremd != "logout", fremd


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
