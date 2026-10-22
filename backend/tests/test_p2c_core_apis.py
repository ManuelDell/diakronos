"""Tests fuer die P2c-Frappe-Core-Endpunkte.

Deckt ab:
  * `/api/method/logout`
  * `/api/method/frappe.client.insert` (+ Kurzform `client.insert`)
  * `/api/method/upload_file` (multipart) inkl. File-Dokument
  * `/api/resource/Eventkategorie` mit `fields` + `limit_page_length` (Beweis #4)
  * `File` ist als DocType registriert und im Mapping (P2c-Erweiterung)

Laufen auf In-Memory-SQLite (siehe conftest).
"""

from __future__ import annotations

import io
from typing import Any

import pytest


@pytest.fixture()
def rollen(monkeypatch):
	"""Rollen des Test-Users steuern (analog test_frappe_compat.py)."""
	from diakronos_app.frappe_compat import permissions

	halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"]}
	monkeypatch.setattr(permissions, "get_roles", lambda user=None: list(halt["roles"]))
	return halt


# ── Hilfs-Fixture: Dateiablage in ein tmp-Verzeichnis umleiten ───────────────


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
	"""`settings.files_dir` auf ein tmp-Verzeichnis zeigen.

	Ohne das schreiben die Upload-Tests in die echte Ablage.
	"""
	from diakronos_app import settings as settings_mod

	target = tmp_path / "files"
	monkeypatch.setattr(settings_mod.settings, "files_dir", str(target))
	return target


# ── logout ──────────────────────────────────────────────────────────────────
#
# A1b1: `logout` ist kein Platzhalter mehr. Frueher setzte er nur
# `session.user` auf `Guest`; jetzt loescht er die echte Sitzung in Redis
# (`frappe_compat/sitzungen.py`) und raeumt das `sid`-Cookie weg. Die
# Antwort ist darum schlicht `{"message": "Logged Out"}` — ohne `user`,
# denn ohne Sitzung gibt es keinen Benutzer zu melden.


def test_logout_post_ok(client):
	r = client.post("/api/method/logout")
	assert r.status_code == 200, r.text
	assert r.json()["message"] == "Logged Out"


def test_logout_ignoriert_csrf_header(client):
	# PT1: Der Logout verlangt jetzt den CSRF-TOKEN DER SITZUNG. Der `client`-
	# Fixture haengt `sid` und den passenden Token an; ein Platzhalter-Token
	# wuerde abgelehnt. Hier belegt der Test, dass der korrekte Token genuegt
	# und der Logout 200 liefert.
	from diakronos_app.frappe_compat import sitzungen

	sid, csrf = sitzungen.anlegen("Administrator")
	r = client.post("/api/method/logout", cookies={"sid": sid},
	                headers={"X-Frappe-CSRF-Token": csrf})
	assert r.status_code == 200
	assert r.json()["message"] == "Logged Out"


def test_logout_ohne_csrf_token_abgewiesen(client):
	"""PT1: Ohne (oder mit falschem) CSRF-Token wird der Logout abgewiesen.

	Das schliesst den Zwangs-Logout per eingebettetem Bild
	(`<img src="/api/method/logout">`): der Angreifer kann den Header nicht
	setzen, `sid` geht als Cookie aber automatisch mit.
	"""
	from diakronos_app.frappe_compat import sitzungen

	sid, _csrf = sitzungen.anlegen("Administrator")
	r = client.post("/api/method/logout", cookies={"sid": sid},
	                headers={"X-Frappe-CSRF-Token": "dummy"})
	assert r.status_code == 417
	# Die Sitzung lebt weiter.
	assert sitzungen.lesen(sid) is not None


def test_logout_auch_per_get(client):
	# PT1: Ein GET-Logout MIT gueltiger Sitzung wird abgewiesen (Forced
	# Logout per <img src="/api/method/logout">). Der `client`-Fixture bringt
	# eine Sitzung mit, deshalb hier 417.
	r = client.get("/api/method/logout")
	assert r.status_code == 417


def test_get_logout_ohne_sitzung_bleibt_noop():
	"""Ohne Sitzung ist GET /api/method/logout ein harmloser No-op.

	Auch der Frappe-Endpunkt darf GET nicht grundsaetzlich verbieten — nur
	mit Sitzung ist es der Zwangs-Logout-Vektor.
	"""
	from fastapi.testclient import TestClient

	from diakronos_app.main import app

	with TestClient(app) as c:
		r = c.get("/api/method/logout")
	assert r.status_code == 200
	assert r.json()["message"] == "Logged Out"


def test_logout_ist_guest_erlaubt(client):
	# Logout muss auch mit abgelaufener Session funktionieren.
	r = client.post("/api/method/logout", params={"_as_guest": 1})
	assert r.status_code == 200


# ── frappe.client.insert ────────────────────────────────────────────────────


def test_insert_legt_dokument_an(client, rollen):
	r = client.post(
		"/api/method/frappe.client.insert",
		json={"doc": {"doctype": "Eventkategorie", "name": "EK-9001",
		              "event_category_name": "Testkategorie", "hat_ablaufplan": 0}},
	)
	assert r.status_code == 200, r.text
	msg = r.json()["message"]
	assert msg["name"] == "EK-9001"
	assert msg["event_category_name"] == "Testkategorie"

	# Wirklich persistiert?
	r2 = client.get("/api/resource/Eventkategorie/EK-9001")
	assert r2.status_code == 200
	assert r2.json()["data"]["event_category_name"] == "Testkategorie"


def test_insert_generiert_name_wenn_fehlt(client, rollen):
	r = client.post(
		"/api/method/frappe.client.insert",
		json={"doc": {"doctype": "Eventkategorie", "event_category_name": "Ohne Namen"}},
	)
	assert r.status_code == 200, r.text
	assert r.json()["message"]["name"]


def test_insert_doc_als_json_string(client, rollen):
	# Form-Post der SPA: `doc` kommt als JSON-String an.
	r = client.post(
		"/api/method/frappe.client.insert",
		data={"doc": '{"doctype": "Eventkategorie", "name": "EK-9002", "event_category_name": "AusString"}'},
	)
	assert r.status_code == 200, r.text
	assert r.json()["message"]["name"] == "EK-9002"


def test_insert_unbekannter_doctype_ist_417(client):
	r = client.post(
		"/api/method/frappe.client.insert",
		json={"doc": {"doctype": "GibtEsNicht", "name": "X-1"}},
	)
	assert r.status_code == 417
	assert r.json()["exception"] == "ValidationError"


def test_insert_ohne_doctype_ist_417(client):
	r = client.post("/api/method/frappe.client.insert", json={"doc": {"name": "X-1"}})
	assert r.status_code == 417


def test_insert_kaputtes_json_ist_417(client):
	r = client.post("/api/method/frappe.client.insert", data={"doc": "{kein json"})
	assert r.status_code == 417


def test_insert_ohne_admin_ist_403(client, rollen):
	rollen["roles"] = []
	r = client.post(
		"/api/method/frappe.client.insert",
		json={"doc": {"doctype": "Eventkategorie", "name": "EK-9004"}},
	)
	assert r.status_code == 403
	assert r.json()["exception"] == "PermissionError"


# ── upload_file ─────────────────────────────────────────────────────────────


def test_upload_file_multipart(client, files_dir):
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("gruesse.txt", io.BytesIO(b"hallo welt"), "text/plain")},
		data={"is_private": "0", "folder": "Home"},
	)
	assert r.status_code == 200, r.text
	msg = r.json()["message"]
	assert msg["file_name"] == "gruesse.txt"
	assert msg["file_url"].startswith("/files/")
	assert msg["file_url"].endswith("gruesse.txt")
	assert msg["is_private"] in (0, False)
	assert msg["file_size"] == len(b"hallo welt")
	assert msg["name"]

	# Datei liegt physisch unter files_dir — und NUR dort (kein Pfad-Escape).
	written = list(files_dir.iterdir())
	assert len(written) == 1
	assert written[0].read_bytes() == b"hallo welt"
	assert written[0].name.endswith("gruesse.txt")


def test_upload_file_privat(client, files_dir):
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("ausweis.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
		data={"is_private": "1"},
	)
	assert r.status_code == 200, r.text
	msg = r.json()["message"]
	assert msg["is_private"] in (1, True)
	# Ablage-URL zeigt auf die Datei; Datei liegt physisch unter files_dir.
	assert msg["file_url"].startswith("/files/")
	assert len(list(files_dir.iterdir())) == 1


def test_upload_file_legt_file_dokument_an(client, files_dir):
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("anhang.txt", io.BytesIO(b"inhalt"), "text/plain")},
	)
	assert r.status_code == 200, r.text
	name = r.json()["message"]["name"]

	# Das angelegte `File`-Dokument ist ueber /api/resource abrufbar.
	r2 = client.get(f"/api/resource/File/{name}")
	assert r2.status_code == 200, r2.text
	d = r2.json()["data"]
	assert d["file_name"] == "anhang.txt"
	assert d["file_url"].endswith("anhang.txt")


def test_upload_file_ohne_datei_ist_417(client, files_dir):
	r = client.post("/api/method/upload_file", data={"is_private": "0"})
	assert r.status_code == 417
	assert r.json()["exception"] == "ValidationError"


def test_upload_file_leere_datei_ist_417(client, files_dir):
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("leer.txt", io.BytesIO(b""), "text/plain")},
	)
	assert r.status_code == 417


def test_upload_file_pfad_traversal_wird_entschaerft(client, files_dir):
	# Der Client-Name darf NIE als Pfad uebernommen werden.
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("../../etc/boese.txt", io.BytesIO(b"x"), "text/plain")},
	)
	assert r.status_code == 200, r.text
	msg = r.json()["message"]
	assert "/" not in msg["file_name"]
	assert ".." not in msg["file_name"]
	# Nur innerhalb von files_dir geschrieben.
	written = list(files_dir.rglob("*"))
	assert all(files_dir in p.parents or p.parent == files_dir for p in written if p.is_file())


def test_upload_file_verbotener_typ_ist_417(client, files_dir):
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("boese.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
	)
	assert r.status_code == 417
	assert r.json()["exception"] == "ValidationError"


def test_upload_file_zu_gross_ist_417(client, files_dir, monkeypatch):
	from diakronos_app import settings as settings_mod

	monkeypatch.setattr(settings_mod.settings, "max_upload_bytes", 4)
	r = client.post(
		"/api/method/upload_file",
		files={"file": ("gross.txt", io.BytesIO(b"0123456789"), "text/plain")},
	)
	assert r.status_code == 417
	# Keine Waise in der Ablage.
	assert not files_dir.exists() or list(files_dir.iterdir()) == []


# ── /api/resource/Eventkategorie mit fields + limit_page_length (Beweis #4) ──


def test_eventkategorie_resource_mit_fields_und_limit(client, rollen):
	client.post(
		"/api/method/frappe.client.insert",
		json={"doc": {"doctype": "Eventkategorie", "name": "EK-8001",
		              "event_category_name": "Gottesdienst", "hat_ablaufplan": 1}},
	)
	client.post(
		"/api/method/frappe.client.insert",
		json={"doc": {"doctype": "Eventkategorie", "name": "EK-8002",
		              "event_category_name": "Konzert", "hat_ablaufplan": 0}},
	)
	r = client.get(
		'/api/resource/Eventkategorie?fields=["name","event_category_name","hat_ablaufplan"]'
		"&limit_page_length=500"
	)
	assert r.status_code == 200, r.text
	data = r.json()["data"]
	assert isinstance(data, list) and len(data) == 2
	row = next(d for d in data if d["name"] == "EK-8001")
	assert row["event_category_name"] == "Gottesdienst"
	assert row["hat_ablaufplan"] in (1, True)


def test_eventkategorie_resource_limit_page_length_greift(client, rollen):
	for i in range(3):
		client.post(
			"/api/method/frappe.client.insert",
			json={"doc": {"doctype": "Eventkategorie", "name": f"EK-70{i:02d}"}},
		)
	r = client.get('/api/resource/Eventkategorie?fields=["name"]&limit_page_length=2')
	assert r.status_code == 200
	assert len(r.json()["data"]) == 2


# ── Registry: File ist bekannt (P2c) ────────────────────────────────────────


def test_file_ist_bekannter_doctype():
	from diakronos_app.frappe_compat.registry_gen import column_names, is_known, model_for

	assert is_known("File")
	model = model_for("File")
	assert model.__tablename__ == "file"
	cols = set(column_names("File"))
	assert {"name", "file_name", "file_url", "is_private", "file_size",
	        "attached_to_doctype", "attached_to_name"} <= cols


def test_upload_file_ist_guest_erlaubt():
	# Frappe laesst upload_file grundsaetzlich zu; die Autorisierung passiert
	# ueber die Session, nicht ueber allow_guest.
	from diakronos_app.frappe_compat.registry import lookup

	assert lookup("upload_file") is not None
	assert lookup("logout") is not None
	assert lookup("frappe.client.insert") is not None