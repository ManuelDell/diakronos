"""BACKUP-1 — Rechte und Endpunkte der Datensicherung.

Die Karte B3 verlangt: die Oberflaeche „Datensicherung“ ist NUR System
Manager. Geprueft wird am ENDPUNKT (der Server entscheidet, nicht die UI):

* System Manager darf lesen, speichern, sichern und loeschen.
* Mitgliederadministrator und Gast bekommen 403.
* Die Antwort enthaelt KEINEN Ablagepfad (B4) und keine Zugangsdaten.
* Loeschen der neuesten erfolgreichen Sicherung ist verweigert.
* Ein Name aus dem Browser ist nie ein Pfadbestandteil.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diakronos_app.sicherung import dump
from diakronos_app.sicherung import einstellungen as einstellungen_modul

API = "diakronos.diakonos.api.sicherung."


@pytest.fixture()
def backup_heim(monkeypatch, tmp_path):
	import diakronos_app.settings as settings_modul

	heim = tmp_path / "data"
	(heim / "files").mkdir(parents=True)
	monkeypatch.setattr(settings_modul.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(settings_modul.settings, "backup_dir", str(heim / "sicherungen"))
	monkeypatch.setattr(dump.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(dump.settings, "backup_dir", str(heim / "sicherungen"))
	return heim


@pytest.fixture()
def rollen(patched_db):
	"""Legt Konten + Rollen an und liefert einen Setzer fuer den Aufrufer."""
	from diakronos_app.models.core import HasRole, User

	sess = patched_db()
	for name, rolle in (
		("admin@example.org", None),
		("mitgliederadmin@example.org", "Mitgliederadministrator"),
		("chefin@example.org", "System Manager"),
	):
		if sess.get(User, name) is None:
			sess.add(User(name=name, email=name, full_name=name, enabled=True))
		if rolle and sess.get(HasRole, f"hr-{name}") is None:
			sess.add(HasRole(name=f"hr-{name}", parent=name, parenttype="User",
			                 parentfield="roles", role=rolle, docstatus=0, idx=1))
	sess.commit()
	sess.close()

	def _setze(name: str):
		from diakronos_app import frappe_compat

		frappe_compat.set_user(name)

	return _setze


@pytest.fixture()
def redis_stub_fuer_sperre(monkeypatch):
	from redis_stub import StubRedis

	stub = StubRedis()
	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: stub)
	return stub


def test_system_manager_darf_lesen(client, rollen, backup_heim):
	rollen("chefin@example.org")
	antwort = client.post(f"/api/method/{API}sicherung_get", json={})
	assert antwort.status_code == 200, antwort.text
	daten = antwort.json()["message"]
	assert daten["einstellungen"]["aufbewahrung_tage"] == 30
	assert daten["einstellungen"]["uhrzeit"] == "03:00"
	assert daten["sicherungen"] == []
	assert daten["ablage"]["benutzbar"] is True
	# B4: kein Pfad im Browser.
	text = antwort.text
	assert str(backup_heim) not in text
	assert "/data/sicherungen" not in text


@pytest.mark.parametrize("konto", ["mitgliederadmin@example.org"])
def test_mitgliederadministrator_wird_abgewiesen(client, rollen, konto, backup_heim):
	rollen(konto)
	antwort = client.post(f"/api/method/{API}sicherung_get", json={})
	assert antwort.status_code == 403


def test_gast_wird_abgewiesen(guest_client, patched_db, backup_heim):
	import diakronos_app.settings as settings_modul

	antwort = guest_client.post(f"/api/method/{API}sicherung_get", json={})
	assert antwort.status_code in (403, 401)


def test_einstellungen_speichern_nur_system_manager(client, rollen, backup_heim):
	rollen("mitgliederadmin@example.org")
	antwort = client.post(f"/api/method/{API}sicherung_einstellungen_speichern",
	                      json={"automatisch": True, "uhrzeit": "05:00",
	                            "aufbewahrung_tage": 14})
	assert antwort.status_code == 403


def test_einstellungen_speichern_prueft_werte(client, rollen, backup_heim):
	rollen("chefin@example.org")
	schlecht = client.post(f"/api/method/{API}sicherung_einstellungen_speichern",
	                       json={"automatisch": True, "uhrzeit": "05:00",
	                             "aufbewahrung_tage": 0})
	assert schlecht.status_code == 417, schlecht.text
	assert "mindestens" in schlecht.text.lower()

	uhrzeit = client.post(f"/api/method/{API}sicherung_einstellungen_speichern",
	                      json={"automatisch": True, "uhrzeit": "25:00",
	                            "aufbewahrung_tage": 14})
	assert uhrzeit.status_code == 417

	gut = client.post(f"/api/method/{API}sicherung_einstellungen_speichern",
	                  json={"automatisch": False, "uhrzeit": "04:30",
	                        "aufbewahrung_tage": 14})
	assert gut.status_code == 200, gut.text
	assert gut.json()["message"]["einstellungen"] == {
		"automatisch": False, "uhrzeit": "04:30", "aufbewahrung_tage": 14,
	}


def test_jetzt_sichern_nur_system_manager(client, rollen, backup_heim,
                                          redis_stub_fuer_sperre):
	rollen("mitgliederadmin@example.org")
	antwort = client.post(f"/api/method/{API}sicherung_jetzt", json={})
	assert antwort.status_code == 403


def test_jetzt_sichern_meldet_den_fehlschlag_ohne_zugangsdaten(
	client, rollen, backup_heim, monkeypatch, redis_stub_fuer_sperre,
):
	"""Der Knopf zeigt einen verstaendlichen Fehler statt 500."""
	rollen("chefin@example.org")

	def _kaputt(ziel: Path, *, timeout: int | None = None) -> None:
		raise dump.SicherungFehler(
			"Der Datenbank-Dump ist fehlgeschlagen (Exit 2): connection refused"
		)

	monkeypatch.setattr(dump, "schreibe_dump", _kaputt)
	monkeypatch.setattr(dump, "schreibe_dateiarchiv",
	                    lambda ziel, quelle=None: ziel.write_bytes(b"x"))
	antwort = client.post(f"/api/method/{API}sicherung_jetzt", json={})
	assert antwort.status_code == 200, antwort.text
	daten = antwort.json()["message"]
	assert daten["ok"] is False
	assert "fehlgeschlagen" in daten["meldung"].lower()
	assert "PGPASSWORD" not in antwort.text
	assert str(backup_heim) not in antwort.text


def test_loeschen_der_neuesten_sicherung_ist_verweigert(client, rollen, backup_heim):
	"""Ein Fehlgriff im Bestaetigungsdialog darf nicht die letzte Kopie kosten."""
	rollen("chefin@example.org")
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	ordner = basis / "2026-10-20_030000"
	ordner.mkdir()
	(ordner / dump.DUMP_NAME).write_bytes(b"dump")
	(ordner / dump.PRUEFSUMMEN_NAME).write_text("x  db.dump\n", encoding="utf-8")
	(ordner / dump.FERTIG_NAME).write_bytes(b"")

	antwort = client.post(f"/api/method/{API}sicherung_loeschen",
	                      json={"name": "2026-10-20_030000"})
	assert antwort.status_code == 417, antwort.text
	assert ordner.exists()
	_ = jetzt


def test_loeschen_einer_aelteren_sicherung_entfernt_ordner_und_zeile(
	client, rollen, backup_heim, patched_db,
):
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	rollen("chefin@example.org")
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	for name in ("2026-10-18_030000", "2026-10-19_030000"):
		ordner = basis / name
		ordner.mkdir()
		(ordner / dump.DUMP_NAME).write_bytes(b"dump")
		(ordner / dump.PRUEFSUMMEN_NAME).write_text("x  db.dump\n", encoding="utf-8")
		(ordner / dump.FERTIG_NAME).write_bytes(b"")
	sess = patched_db()
	sess.add(Sicherungslauf(name="2026-10-18_030000",
	                        begonnen_am=datetime(2026, 10, 18, 3, 0), status=STATUS_OK))
	sess.commit()
	sess.close()

	antwort = client.post(f"/api/method/{API}sicherung_loeschen",
	                      json={"name": "2026-10-18_030000"})
	assert antwort.status_code == 200, antwort.text
	assert not (basis / "2026-10-18_030000").exists()
	assert (basis / "2026-10-19_030000").exists(), "die neueste bleibt"


@pytest.mark.parametrize("name", ["../../etc", "..", "/etc/passwd", "2026-10-20_030000/../x", ""])
def test_name_aus_dem_browser_ist_kein_pfad(client, rollen, backup_heim, name):
	rollen("chefin@example.org")
	antwort = client.post(f"/api/method/{API}sicherung_loeschen", json={"name": name})
	assert antwort.status_code == 404, antwort.text


def test_liste_zeigt_status_und_groesse_ohne_pfad(client, rollen, backup_heim, patched_db):
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	rollen("chefin@example.org")
	sess = patched_db()
	sess.add(Sicherungslauf(name="2026-10-20_030000",
	                        begonnen_am=datetime(2026, 10, 20, 3, 0),
	                        beendet_am=datetime(2026, 10, 20, 3, 1),
	                        status=STATUS_OK, groesse_bytes=1234, ausloeser="automatisch"))
	sess.commit()
	sess.close()

	antwort = client.post(f"/api/method/{API}sicherung_get", json={})
	daten = antwort.json()["message"]
	assert daten["sicherungen"][0]["name"] == "2026-10-20_030000"
	assert daten["sicherungen"][0]["groesse_bytes"] == 1234
	assert daten["sicherungen"][0]["status"] == "ok"
	assert str(backup_heim) not in antwort.text


def test_ablage_hinweis_bei_unbrauchbarem_ziel(client, rollen, monkeypatch, tmp_path):
	"""Ist der Ablageort im Image, sagt die Oberflaeche das — statt zu luegen."""
	import diakronos_app.settings as settings_modul

	rollen("chefin@example.org")
	(Path(tmp_path) / "files").mkdir()
	monkeypatch.setattr(settings_modul.settings, "files_dir", str(Path(tmp_path) / "files"))
	monkeypatch.setattr(dump.settings, "files_dir", str(Path(tmp_path) / "files"))
	monkeypatch.setattr(dump.settings, "backup_dir", "/app/backups")
	antwort = client.post(f"/api/method/{API}sicherung_get", json={})
	daten = antwort.json()["message"]
	assert daten["ablage"]["benutzbar"] is False
	assert daten["ablage"]["hinweis"]
