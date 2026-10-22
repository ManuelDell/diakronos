"""N1: Original-Frappe-Pfade sind auch nach ungewoehnlicher Importreihenfolge da.

Befund aus der N1-Abnahme: die SPA ruft die Endpunkte unter ihrem
Original-Pfad auf (`diakronos.diakonos.api.admin_hub.get_statistik`). Wird ein
API-Untermodul zuerst geladen (z. B. weil `main.py` es zieht), fehlte dieser
Pfad im Register und die Seite zeigte „Methode nicht gefunden“ — obwohl die
Kurzform `admin_hub.get_statistik` aufloeste.

Dieser Test erzwingt die Reihenfolge „Untermodul zuerst“ und prueft, dass der
Original-Pfad danach trotzdem registriert ist (Nachregistrierung).
"""

from __future__ import annotations

import subprocess
import sys


def test_original_pfad_nach_untermodul_zuerst():
	"""Erst `api.admin_hub` laden, dann muss der Original-Pfad aufloesen."""
	programm = (
		"import importlib, sys;"
		# Untermodul ZUERST — der Fall, in dem die Registrierung frueher fehlte.
		"importlib.import_module('diakronos_app.api.admin_hub');"
		"importlib.import_module('diakronos_app.api');"
		"from diakronos_app.frappe_compat.registry import lookup, nachregistrieren;"
		"nachregistrieren();"
		"p='diakronos.diakonos.api.admin_hub.get_statistik';"
		"sys.exit(0 if lookup(p) else 1)"
	)
	ergebnis = subprocess.run([sys.executable, "-c", programm], capture_output=True)
	assert ergebnis.returncode == 0, (
		"Original-Pfad fehlt nach Nachregistrierung: "
		+ ergebnis.stderr.decode()[-500:]
	)


def test_nachregistrierung_ist_idempotent():
	"""Zweimal nachregistrieren darf nichts kaputt machen und nichts doppeln."""
	from diakronos_app.api import admin_hub  # noqa: F401
	from diakronos_app.frappe_compat.registry import lookup, nachregistrieren

	nachregistrieren()
	vorher = lookup("diakronos.diakonos.api.admin_hub.get_statistik")
	assert vorher is admin_hub.get_statistik, "Original-Pfad zeigt auf dieselbe Funktion"
	# Nach vollstaendiger Registrierung traegt ein weiterer Lauf nichts mehr ein.
	assert nachregistrieren() == 0, "keine Doppelarbeit erwartet"
	assert lookup("diakronos.diakonos.api.admin_hub.get_statistik") is admin_hub.get_statistik
