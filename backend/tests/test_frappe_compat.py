"""Tests fuer die Frappe-Compat-Schicht (P2a).

Deckt Envelopes, Filter-Compiler, get_all/get_doc/get_value, /api/method und
/api/resource ab. Laufen auf In-Memory-SQLite (siehe conftest).
"""

from __future__ import annotations

from typing import Any

import pytest


# ── /api/method ─────────────────────────────────────────────────────────────


def test_method_envelope_post(client):
	r = client.post("/api/method/ping")
	assert r.status_code == 200
	assert r.json() == {"message": "pong"}


def test_method_envelope_get(client):
	r = client.get("/api/method/ping")
	assert r.status_code == 200
	assert r.json()["message"] == "pong"


def test_method_unknown_404(client):
	r = client.post("/api/method/gibt.es.nicht")
	assert r.status_code == 404
	assert r.json()["exception"] == "NotFound"


def test_method_validation_error_is_417(client):
	r = client.post("/api/method/fail_validation", json={"msg": "zu jung"})
	assert r.status_code == 417
	body = r.json()
	assert body["message"] == "zu jung"
	assert body["exception"] == "ValidationError"


def _als_admin(monkeypatch):
	"""Rollen auf Admin setzen — die echten Mitglieder-Endpunkte sind
	rollengebunden (fail closed). Gleiches Muster wie in test_admin_hub.py."""
	from diakronos_app.frappe_compat import permissions

	monkeypatch.setattr(
		permissions, "get_roles", lambda user=None: ["Mitgliederadministrator"]
	)
	monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)


def test_method_args_are_kwargs(client, seed_mitglieder, monkeypatch):
	# Realistisch: die Portierung exportiert die Funktion im Paket `api`.
	# Seit P1d liegt hier die echte Portierung (api/mitglieder.py), nicht mehr
	# der P2a-Platzhalter — sie ist rollengebunden, daher Admin simulieren.
	_als_admin(monkeypatch)
	r = client.post("/api/method/mitglieder.get_mitglieder_liste", json={"status": "Mitglied"})
	assert r.status_code == 200, r.text
	msg = r.json()["message"]
	assert msg["total"] == 2
	assert {m["name"] for m in msg["data"]} == {"M-0001", "M-0002"}


def test_method_bare_name_resolves(client, seed_mitglieder, monkeypatch):
	# Kurzpfad ohne Modul soll ebenfalls aufloesen.
	_als_admin(monkeypatch)
	r = client.get("/api/method/get_mitglieder_liste")
	assert r.status_code == 200, r.text
	# AUSTRITT A5/b (B3): Die Grundliste nennt nur die, die noch dabei sind —
	# die Ausgetretene (M-0003) steht hinter dem Statusfilter „Ausgetreten“.
	# Geprueft wird hier der Kurzpfad, nicht die Sichtbarkeit selbst.
	assert r.json()["message"]["total"] == 2


def test_method_ignores_unknown_args(client):
	# ping() nimmt keine Argumente -> extra Argument darf nicht crashen
	r = client.post("/api/method/ping", json={"unbekannt": 1})
	assert r.status_code == 200
	assert r.json()["message"] == "pong"


# ── Filter-Compiler ueber die oeffentliche get_all-API ──────────────────────


@pytest.fixture()
def qa(patched_db):
	from diakronos_app.frappe_compat import get_all

	return get_all


def test_get_all_dict_equality(qa, seed_mitglieder):
	rows = qa("Mitglied", filters={"status": "Mitglied"}, fields=["name"])
	assert len(rows) == 2


def test_get_all_list_of_triples(qa, seed_mitglieder):
	rows = qa("Mitglied", filters=[["status", "=", "Ausgetreten"]], fields=["name"])
	assert [r["name"] for r in rows] == ["M-0003"]


def test_get_all_like(qa, seed_mitglieder):
	rows = qa("Mitglied", filters={"vorname": ["like", "A%"]}, fields=["name"])
	assert [r["name"] for r in rows] == ["M-0001"]


def test_get_all_in_and_notin(qa, seed_mitglieder):
	rows = qa("Mitglied", filters={"status": ["in", ["Mitglied", "Ausgetreten"]]}, fields=["name"])
	assert len(rows) == 3
	rows = qa("Mitglied", filters={"status": ["not in", ["Ausgetreten"]]}, fields=["name"])
	assert len(rows) == 2


def test_get_all_is_set(qa, seed_mitglieder):
	rows = qa("Mitglied", filters={"status": ["is", "set"]}, fields=["name"])
	assert len(rows) == 3


def test_get_all_pluck(qa, seed_mitglieder):
	assert qa("Mitglied", pluck="name", order_by="name asc") == ["M-0001", "M-0002", "M-0003"]


def test_get_all_as_list(qa, seed_mitglieder):
	rows = qa("Mitglied", fields=["name"], as_list=True, order_by="name asc")
	assert rows == [["M-0001"], ["M-0002"], ["M-0003"]]


def test_get_all_limit_offset(qa, seed_mitglieder):
	rows = qa("Mitglied", fields=["name"], order_by="name asc", limit_start=1, limit_page_length=1)
	assert [r["name"] for r in rows] == ["M-0002"]


def test_get_all_field_alias(qa, seed_mitglieder):
	rows = qa("Mitglied", fields=["name as n"], order_by="name asc", limit_page_length=1)
	assert rows == [{"n": "M-0001"}]


def test_get_all_unknown_doctype_raises(qa):
	# Frappe antwortet auf einen unbekannten DocType mit DoesNotExistError
	# (HTTP 404), nicht mit einem nackten KeyError (HTTP 500).
	from diakronos_app.frappe_compat import DoesNotExistError

	with pytest.raises(DoesNotExistError):
		qa("GibtEsNicht")


# ── get_doc / get_value ─────────────────────────────────────────────────────


def test_get_doc_roundtrip(patched_db, seed_mitglieder):
	from diakronos_app.frappe_compat import get_doc

	doc = get_doc("Mitglied", "M-0001")
	assert doc.vorname == "Anna"


def test_get_doc_missing_raises(patched_db, seed_mitglieder):
	from diakronos_app.frappe_compat import get_doc
	from diakronos_app.frappe_compat.exceptions import DoesNotExistError

	with pytest.raises(DoesNotExistError):
		get_doc("Mitglied", "M-9999")


def test_get_value_scalar(patched_db, seed_mitglieder):
	from diakronos_app.frappe_compat import get_value

	assert get_value("Mitglied", {"name": "M-0002"}, "vorname") == "Bruno"


def test_get_value_by_name_string(patched_db, seed_mitglieder):
	from diakronos_app.frappe_compat import get_value

	assert get_value("Mitglied", "M-0003", "nachname") == "Clausen"


def test_get_value_list(patched_db, seed_mitglieder):
	from diakronos_app.frappe_compat import get_value

	assert get_value("Mitglied", "M-0001", ["vorname", "nachname"]) == ["Anna", "Beispiel"]


# ── /api/resource ───────────────────────────────────────────────────────────


def test_resource_list_envelope_data(client, seed_mitglieder, monkeypatch):
	_als_admin(monkeypatch)
	# SPA liest `.data` -> bewusste Abweichung von Frappes nacktem Array.
	r = client.get("/api/resource/Mitglied?fields=[\"name\"]&order_by=name%20asc")
	assert r.status_code == 200
	assert r.json()["data"] == [{"name": "M-0001"}, {"name": "M-0002"}, {"name": "M-0003"}]


def test_resource_list_limit(client, seed_mitglieder, monkeypatch):
	_als_admin(monkeypatch)
	r = client.get("/api/resource/Mitglied?fields=[\"name\"]&limit_page_length=1")
	assert len(r.json()["data"]) == 1


def test_resource_get_single(client, seed_mitglieder, monkeypatch):
	_als_admin(monkeypatch)
	r = client.get("/api/resource/Mitglied/M-0001")
	assert r.status_code == 200
	assert r.json()["data"]["vorname"] == "Anna"


def test_resource_get_missing_404(client, seed_mitglieder, monkeypatch):
	_als_admin(monkeypatch)
	r = client.get("/api/resource/Mitglied/M-9999")
	assert r.status_code == 404
	assert r.json()["exception"] == "DoesNotExistError"


def test_resource_unknown_doctype_404(client):
	r = client.get("/api/resource/GibtEsNicht")
	assert r.status_code == 404


def test_resource_create_update_delete(client, monkeypatch):
	_als_admin(monkeypatch)
	# create — ID-1d: die Kennung vergibt der Server, ein mitgeschickter
	# `name` wird verworfen (frueher wurde er als Primaerschluessel uebernommen).
	r = client.post("/api/resource/Mitglied", json={"name": "M-0100", "vorname": "Neu", "nachname": "Person"})
	assert r.status_code == 200, r.text
	assert r.json()["data"]["vorname"] == "Neu"
	kennung = r.json()["data"]["name"]
	assert kennung != "M-0100"
	# update
	r = client.put(f"/api/resource/Mitglied/{kennung}", json={"vorname": "Geaendert"})
	assert r.status_code == 200
	assert r.json()["data"]["vorname"] == "Geaendert"
	# delete
	r = client.delete(f"/api/resource/Mitglied/{kennung}")
	assert r.status_code == 202
	# weg
	r = client.get(f"/api/resource/Mitglied/{kennung}")
	assert r.status_code == 404


# ── healthz bleibt unberuehrt ───────────────────────────────────────────────


def test_healthz_still_served(client):
	r = client.get("/healthz")
	assert r.status_code == 200
	assert set(r.json()) >= {"status", "db", "redis"}


# ── P2b: portierte Endpunkte api/mitglieder.py ──────────────────────────────


@pytest.fixture()
def rollen(monkeypatch):
	"""Rollen des Test-Users steuern. Echte Rollenquelle ist P3."""
	from diakronos_app.frappe_compat import permissions

	halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"]}
	monkeypatch.setattr(permissions, "get_roles", lambda user=None: list(halt["roles"]))
	return halt


def test_mitglieder_liste_admin_sieht_alles(client, seed_mitglieder, rollen):
	r = client.get("/api/method/mitglieder.get_mitglieder_liste")
	assert r.status_code == 200, r.text
	body = r.json()["message"]
	assert body["success"] is True
	# AUSTRITT A5/b (B3): Ausgetretene sind in der Grundliste standardmaessig
	# ausgeblendet und ueber den Statusfilter „Ausgetreten“ zu sehen; ein
	# AUSSCHLUSS (Passiver Gast) bleibt dagegen in der Liste. Beides steht in
	# tests/test_austritt_b.py — hier bleibt nur die Sichtbarkeit der Aktiven.
	assert [m["name"] for m in body["data"]] == ["M-0001", "M-0002"]
	assert body["total"] == 2
	# Vertrag: Envelope-Schluessel wie im Referenz-Endpunkt.
	assert set(body) >= {"success", "data", "total", "start", "limit"}


def test_mitglieder_liste_felder(client, seed_mitglieder, rollen):
	m = client.get("/api/method/mitglieder.get_mitglieder_liste").json()["message"]["data"][0]
	assert set(m) >= {"name", "vorname", "nachname", "full_name", "email", "status",
	                  "wohnort", "postleitzahl", "geburtstag", "ancestor_path"}
	assert m["full_name"] == "Anna Beispiel"


def test_mitglieder_liste_ohne_rolle_ist_leer(client, seed_mitglieder, rollen):
	# Fail closed: ohne Rolle keine Sichtbarkeit -> leere Liste, kein 500.
	rollen["roles"] = []
	body = client.get("/api/method/mitglieder.get_mitglieder_liste").json()["message"]
	assert body["data"] == []
	assert body["total"] == 0


def test_mitglieder_liste_suche(client, seed_mitglieder, rollen):
	r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"suche": "Brandner"})
	assert [m["name"] for m in r.json()["message"]["data"]] == ["M-0002"]


def test_mitglieder_liste_status_filter_zaehlt_gleich(client, seed_mitglieder, rollen):
	body = client.get("/api/method/mitglieder.get_mitglieder_liste",
	                  params={"status": "Ausgetreten"}).json()["message"]
	assert [m["name"] for m in body["data"]] == ["M-0003"]
	assert body["total"] == 1


def test_mitglieder_liste_pagination(client, seed_mitglieder, rollen):
	body = client.get("/api/method/mitglieder.get_mitglieder_liste",
	                  params={"limit": 1, "offset": 1}).json()["message"]
	assert len(body["data"]) == 1
	assert body["total"] == 2      # total bleibt die Gesamtzahl (ohne Ausgetretene)
	assert body["limit"] == 1


def test_mitglieder_liste_boeses_sort_by_wird_ignoriert(client, seed_mitglieder, rollen):
	# Sort-Whitelist: Injection darf nicht durchkommen und nicht 500en.
	r = client.get("/api/method/mitglieder.get_mitglieder_liste",
	               params={"sort_by": "name; DROP TABLE mitglied"})
	assert r.status_code == 200
	assert len(r.json()["message"]["data"]) == 2


def test_mitglied_detail_braucht_rolle(client, seed_mitglieder, rollen):
	rollen["roles"] = []
	r = client.get("/api/method/mitglieder.get_mitglied_detail",
	               params={"mitglied_id": "M-0001"})
	assert r.status_code == 403
	assert r.json()["exception"] == "PermissionError"


def test_mitglied_detail_liefert_dsgvo_und_permissions(client, seed_mitglieder, rollen):
	body = client.get("/api/method/mitglieder.get_mitglied_detail",
	                  params={"mitglied_id": "M-0001"}).json()["message"]
	assert body["success"] is True
	d = body["data"]
	assert d["name"] == "M-0001" and d["vorname"] == "Anna"
	assert set(d["dsgvo"]) >= {"datenschutz", "datenschutz_datum", "foto",
	                           "foto_datum", "werbung", "werbung_datum"}
	assert isinstance(d["gruppenmitgliedschaften"], list)
	# Referenz mitglieder.py:230-234 — `permissions` liegt NEBEN `data`,
	# nicht darin (die SPA liest message.permissions).
	assert set(body) >= {"success", "data", "permissions"}
	perms = body["permissions"]
	assert perms["can_view"] is True
	assert perms["can_view_sensitive"] is True
	assert perms["can_delete"] is False   # wie im Original


def test_mitglied_detail_unbekannt_ist_404(client, seed_mitglieder, rollen):
	r = client.get("/api/method/mitglieder.get_mitglied_detail",
	               params={"mitglied_id": "M-9999"})
	assert r.status_code == 404
	assert r.json()["exception"] == "DoesNotExistError"


def test_mitglied_detail_guest_wird_abgewiesen(client, seed_mitglieder):
	r = client.get("/api/method/mitglieder.get_mitglied_detail",
	               params={"mitglied_id": "M-0001", "_as_guest": 1})
	assert r.status_code == 403


def test_mitglieder_endpunkte_sind_nicht_guest(client):
	# allow_guest=False: der Router darf diese Methoden nicht oeffentlich machen.
	from diakronos_app.api import mitglieder
	from diakronos_app.frappe_compat.registry import lookup, options_for

	for name in ("get_mitglieder_liste", "get_mitglied_detail"):
		fn = lookup(f"mitglieder.{name}")
		assert fn is not None, f"{name} nicht registriert"
		assert fn is getattr(mitglieder, name)
		assert options_for(fn)["allow_guest"] is False



# ── Router: `**kwargs`-Sammler (Frappe-Whitelist-Semantik) ──────────────────
#
# P4e: `registrierungslink_api.update_link(link_id, **kwargs)` erwartet ALLE
# Request-Parameter (Frappe reicht sie ungefiltert an `**kwargs` weiter).
# Vor dem Fix filterte `_accepted_params` sie weg -> kwargs war immer leer.


def test_accepted_params_bei_kwargs_sammler():
	from diakronos_app.frappe_compat.router import _accepted_params

	def mit_kwargs(link_id, **kwargs):
		return None

	def ohne_kwargs(link_id, bezeichnung=None):
		return None

	assert _accepted_params(mit_kwargs) is None
	assert _accepted_params(ohne_kwargs) == {"link_id", "bezeichnung"}


def test_kwargs_endpunkt_bekommt_alle_parameter(client):
	"""Ein `**kwargs`-Endpunkt sieht alle uebergebenen Formularfelder."""
	from diakronos_app.frappe_compat import registry

	gesehen: dict[str, Any] = {}

	def probe(link_id, **kwargs):
		gesehen["link_id"] = link_id
		gesehen.update(kwargs)
		return {"ok": True}

	# Ueber `api.registrierungslink_api.update_link` (echter Port-Endpunkt)
	# pruefen — der ist bereits registriert und hat die `**kwargs`-Signatur.
	assert registry.lookup("registrierungslink_api.update_link") is not None

	registry.register_with_frappe_module("testkw", "probe", probe)
	try:
		r = client.post(
			"/api/method/testkw.probe",
			data={"link_id": "RL-1", "bezeichnung": "Sommerfest", "typ": "Veranstaltung"},
		)
		assert r.status_code == 200, r.text
		assert gesehen["link_id"] == "RL-1"
		assert gesehen["bezeichnung"] == "Sommerfest"
		assert gesehen["typ"] == "Veranstaltung"
	finally:
		registry.registered()  # Snapshot bleibt unveraendert (kein Unregister noetig)
