"""P2b: Tests fuer den portierten Endpunkt `admin_hub.get_statistik`.

Quelle: referenz/diakronos-frappe/diakonos/diakonos/api/admin_hub.py:100-163.
Prueft die Antwortstruktur (nicht nur den HTTP-Status) und die Kennzahlen
gegen geseedete Daten.
"""

from __future__ import annotations

from datetime import date

import pytest

from typing import Any


@pytest.fixture()
def rollen(monkeypatch):
	"""Rollen des Test-Users steuern. Echte Rollenquelle ist P3.

	Patcht die Namen in BEIDEN Modulen: `admin_hub` hat `get_roles` per
	`from ... import` gebunden, dort greift ein Patch auf `permissions`
	allein nicht. `is_guest` wird mitgepatcht, weil es intern wieder
	`get_roles` aufruft.
	"""
	from diakronos_app.api import admin_hub
	from diakronos_app.frappe_compat import permissions

	halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"]}
	hole = lambda user=None: list(halt["roles"])          # noqa: E731
	nur_mitglied = lambda user=None: False                 # noqa: E731
	for mod in (permissions, admin_hub):
		if hasattr(mod, "get_roles"):
			monkeypatch.setattr(mod, "get_roles", hole)
		if hasattr(mod, "is_guest"):
			monkeypatch.setattr(mod, "is_guest", nur_mitglied)
	return halt


@pytest.fixture()
def statistik_daten(patched_db, seed_mitglieder):
	"""Anmeldungen + DSGVO + Links fuer aussagekraeftige Kennzahlen."""
	from diakronos_app.models.diakonos import (
		Anmeldung,
		DSGVOEinwilligung,
		Mitglied,
		Registrierungslink,
	)

	sess = patched_db()
	heute = date.today()
	anmeldungen = [
		Anmeldung(name="ANM-1", status="Anmeldeanfrage", anmeldedatum=heute),
		Anmeldung(name="ANM-2", status="Ausstehend", anmeldedatum=heute),
		Anmeldung(name="ANM-3", status="Bestaetigt", anmeldedatum=heute),
	]
	# UXD-R16: die Statistik zaehlt PERSONEN, deshalb steht der Einwilligungs-
	# stand am Mitglied (`datenschutz_einwilligung`). M-0003 hat widerrufen:
	# Feld False, juengster `datenschutz`-Log-Eintrag ist der Widerruf.
	sess.query(Mitglied).filter(Mitglied.name == "M-0001").update(
		{"datenschutz_einwilligung": True})
	sess.query(Mitglied).filter(Mitglied.name == "M-0002").update(
		{"datenschutz_einwilligung": True})
	sess.query(Mitglied).filter(Mitglied.name == "M-0003").update(
		{"datenschutz_einwilligung": False})
	# Protokoll: Foto/Werbe-Eintraege duerfen die Zaehlung NICHT erhoehen.
	konsens = [
		DSGVOEinwilligung(name="DSG-1", mitglied="M-0001", typ="datenschutz",
		                  aktion="erteilt", widerrufen=0),
		DSGVOEinwilligung(name="DSG-2", mitglied="M-0002", typ="datenschutz",
		                  aktion="erteilt", widerrufen=0),
		DSGVOEinwilligung(name="DSG-3", mitglied="M-0003", typ="datenschutz",
		                  aktion="widerrufen", widerrufen=1),
		# Mehrere Zeilen fuer EINE Person (Foto/Werbung) — zaehlen nicht als Personen.
		DSGVOEinwilligung(name="DSG-4", mitglied="M-0001", typ="foto", aktion="erteilt"),
		DSGVOEinwilligung(name="DSG-5", mitglied="M-0001", typ="werbung", aktion="erteilt"),
	]
	links = [
		Registrierungslink(name="LNK-1", bezeichnung="Sommer", aktiv=1, anmeldungen_count=12),
		Registrierungslink(name="LNK-2", bezeichnung="Winter", aktiv=0, anmeldungen_count=3),
	]
	sess.add_all(anmeldungen + konsens + links)
	sess.commit()
	yield sess
	sess.close()


def test_statistik_braucht_adminrolle(client, seed_mitglieder, statistik_daten, rollen):
	rollen["roles"] = []
	r = client.get("/api/method/admin_hub.get_statistik")
	assert r.status_code == 403
	assert r.json()["exception"] == "PermissionError"


def test_statistik_antwortstruktur(client, seed_mitglieder, statistik_daten, rollen):
	r = client.get("/api/method/admin_hub.get_statistik")
	assert r.status_code == 200, r.text
	stats = r.json()["message"]
	# Struktur wie admin_hub.py:148-163
	assert set(stats) == {"mitglieder", "dsgvo", "anmeldungen", "links"}
	assert set(stats["mitglieder"]) == {
		"gesamt", "mitglied", "gast", "passives_mitglied", "passiver_gast"}
	assert set(stats["dsgvo"]) == {"ok", "widerrufen", "fehlt"}
	assert set(stats["anmeldungen"]) == {"gesamt", "diesen_monat", "offen", "nach_status"}
	assert set(stats["links"]) == {"aktiv", "inaktiv", "gesamt_anmeldungen", "top"}


def test_statistik_mitglieder_zaehlt_nach_status(client, seed_mitglieder, statistik_daten, rollen):
	stats = client.get("/api/method/admin_hub.get_statistik").json()["message"]
	m = stats["mitglieder"]
	assert m["gesamt"] == 3
	assert m["mitglied"] == 2      # M-0001 'Mitglied', M-0002 'Mitglied'
	assert m["gast"] == 0
	assert m["passives_mitglied"] == 0
	assert m["passiver_gast"] == 0


def test_statistik_dsgvo_zaehlt(client, seed_mitglieder, statistik_daten, rollen):
	stats = client.get("/api/method/admin_hub.get_statistik").json()["message"]
	# PERSONEN zaehlen (UXD-R16): M-0001/M-0002 haben eingewilligt (ok=2),
	# M-0003 hat widerrufen (fehlt=1, widerrufen=1). Die zusaetzlichen
	# Foto-/Werbe-Eintraege fuer M-0001 duerfen die Zahl NICHT erhoehen.
	assert stats["dsgvo"] == {"ok": 2, "widerrufen": 1, "fehlt": 1}


def test_statistik_anmeldungen(client, seed_mitglieder, statistik_daten, rollen):
	stats = client.get("/api/method/admin_hub.get_statistik").json()["message"]
	a = stats["anmeldungen"]
	assert a["gesamt"] == 3
	assert a["offen"] == 2          # Anmeldeanfrage + Ausstehend
	assert a["diesen_monat"] == 3   # alle heute angelegt
	assert a["nach_status"] == {"Anmeldeanfrage": 1, "Ausstehend": 1, "Bestaetigt": 1}


def test_statistik_links(client, seed_mitglieder, statistik_daten, rollen):
	stats = client.get("/api/method/admin_hub.get_statistik").json()["message"]
	links = stats["links"]
	assert links["aktiv"] == 1
	assert links["inaktiv"] == 1
	assert links["gesamt_anmeldungen"] == 15   # 12 + 3
	# order_by anmeldungen_count desc -> LNK-1 zuerst, max 5
	assert [l["name"] for l in links["top"]] == ["LNK-1", "LNK-2"]


def test_statistik_leere_datenbank_ist_nullen(client, rollen):
	"""Ohne Daten sind alle Kennzahlen 0, kein Fehler."""
	r = client.get("/api/method/admin_hub.get_statistik")
	assert r.status_code == 200, r.text
	stats = r.json()["message"]
	assert stats["mitglieder"]["gesamt"] == 0
	assert stats["dsgvo"] == {"ok": 0, "widerrufen": 0, "fehlt": 0}
	assert stats["anmeldungen"]["gesamt"] == 0
	assert stats["links"]["top"] == []


def test_statistik_ist_nicht_guest(client):
	from diakronos_app.api import admin_hub
	from diakronos_app.frappe_compat.registry import lookup, options_for

	fn = lookup("admin_hub.get_statistik")
	assert fn is admin_hub.get_statistik
	assert options_for(fn)["allow_guest"] is False
