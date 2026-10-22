"""P0-1 — `/api/resource` vollstaendig absichern (BLD-R1 Rest, BLD-04/05).

Der Hotfix 52f3be2 sperrt nur Gaeste sowie `User`/`Has Role` fuer Nicht-Admins.
Offen blieb: ein **angemeldeter Nicht-Admin** durfte ueber den generischen
CRUD praktisch jeden DocType lesen, schreiben und loeschen — die SPA nutzt
davon nur `Eventkategorie` (Liste) und `Element` (Einzelabruf/Loeschen).

Diese Datei prueft die Rollenmatrix je Aktion (anonym / mitglied / admin) und
die verstaendliche Fehlermeldung beim Loeschen (BLD-04/05: vorher HTTP 500 mit
rohem SQL bzw. unbehandelte Ausnahme).

Vor dem Fix sind die Nicht-Admin-Faelle rot (200 statt 403) und der
Loesch-Fehlerfall liefert 500 statt 417.
"""

from __future__ import annotations

import pytest


def _set_user(user: str) -> None:
	from diakronos_app.frappe_compat.session import set_user

	set_user(user)


@pytest.fixture()
def mitglied(client, patched_db):
	"""Ein angemeldeter Nicht-Admin ohne jede Admin-Rolle.

	Die `user`-Zeile muss existieren und `enabled` sein, sonst wertet die
	Session-Middleware den Aufruf als `Guest` (Regel B1). Rollen bekommt der
	Nutzer bewusst keine — genau der Fall, den BLD-R1 offen liess.
	"""
	from diakronos_app.models.core import User

	sess = patched_db()
	if sess.get(User, "einfach@example.org") is None:
		sess.add(User(
			name="einfach@example.org",
			email="einfach@example.org",
			full_name="Einfacher Nutzer",
			enabled=True,
		))
		sess.commit()
	sess.close()
	return "einfach@example.org"


# ── BLD-R1 Rest: anonym ─────────────────────────────────────────────────────


def test_anonym_kein_lesen_und_kein_schreiben(client):
	_set_user("Guest")
	assert client.get("/api/resource/Eventkategorie").status_code == 403
	assert client.get("/api/resource/Element/E-1").status_code == 403
	assert client.get("/api/resource/User?fields=[\"name\"]").status_code == 403
	assert client.post("/api/resource/Eventkategorie", json={"name": "X"}).status_code == 403
	assert client.put("/api/resource/Element/E-1", json={"element_name": "X"}).status_code == 403
	assert client.delete("/api/resource/Element/E-1").status_code == 403


# ── BLD-R1 Rest: angemeldeter Nicht-Admin (Rollenmatrix) ────────────────────


@pytest.mark.parametrize("doctype", [
	"Lied", "Anmeldung", "Wiki Artikel", "Kalender", "Gruppe", "Dienstbereich",
	"Audit Log", "Registrierungslink", "Ressource", "Eventkategorie",
])
def test_nicht_admin_kein_schreiben_und_loeschen(client, mitglied, doctype):
	_set_user(mitglied)
	assert client.post(f"/api/resource/{doctype}", json={"name": "P01-X"}).status_code == 403
	assert client.put(f"/api/resource/{doctype}/P01-X", json={}).status_code == 403
	assert client.delete(f"/api/resource/{doctype}/P01-X").status_code == 403


@pytest.mark.parametrize("doctype", [
	"Lied", "Anmeldung", "Wiki Artikel", "Kalender", "Gruppe", "Dienstbereich",
	"Audit Log", "Registrierungslink", "Ressource", "User", "Has Role",
])
def test_nicht_admin_kein_lesen_fremder_doctypes(client, mitglied, doctype):
	_set_user(mitglied)
	assert client.get(f"/api/resource/{doctype}").status_code == 403
	assert client.get(f"/api/resource/{doctype}/egal").status_code == 403


def test_nicht_admin_darf_eventkategorie_lesen(client, mitglied, patched_db):
	# Der einzige Listen-Aufruf der SPA (KronosEventCreate/Edit.vue).
	from diakronos_app.models.kronos import Eventkategorie

	sess = patched_db()
	sess.add(Eventkategorie(name="EK-1", event_category_name="Gottesdienst"))
	sess.commit()
	sess.close()

	_set_user(mitglied)
	r = client.get(
		"/api/resource/Eventkategorie"
		"?fields=[\"name\",\"event_category_name\"]&limit_page_length=500"
	)
	assert r.status_code == 200, r.text
	assert r.json()["data"] == [{"name": "EK-1", "event_category_name": "Gottesdienst"}]


def test_nicht_admin_darf_element_NICHT_lesen(client, mitglied, patched_db):
	"""P0-1-Rest: `Element` ist aus der Leseallowlist entfernt.

	Vorher konnte jedes angemeldete Mitglied alle Termine aller Kalender per
	`fields`/`filters`/`pluck` listen und einzeln lesen — und damit die Filter
	von `get_events`, Dashboard und Konfliktliste umgehen. Der einzige
	Frontend-Treffer ist ein DELETE (fuer Nicht-Admins gesperrt, nirgends
	aufgerufen).
	"""
	from diakronos_app.models.kronos import Element

	sess = patched_db()
	sess.add(Element(name="E-1", element_name="Probe"))
	sess.commit()
	sess.close()

	_set_user(mitglied)
	# Einzelabruf gesperrt ...
	assert client.get("/api/resource/Element/E-1").status_code == 403
	# ... und die Liste erst recht (inkl. Feldprojektion).
	assert client.get("/api/resource/Element").status_code == 403
	assert client.get(
		"/api/resource/Element?fields=[\"name\",\"element_name\"]&limit_page_length=500"
	).status_code == 403
	assert client.get("/api/resource/Element?pluck=element_name").status_code == 403


def test_admin_darf_element_weiter_lesen(client, patched_db):
	"""Gegenprobe: fuer Admins bleibt der generische Weg offen (kein Regress)."""
	from diakronos_app.models.kronos import Element

	sess = patched_db()
	sess.add(Element(name="E-ADM", element_name="Admin-Termin"))
	sess.commit()
	sess.close()

	assert client.get("/api/resource/Element/E-ADM").status_code == 200
	assert client.get("/api/resource/Element").status_code == 200


def test_nicht_admin_darf_mitglied_nur_im_detail_lesen(client, mitglied):
	"""P0-1-Rest (klein): Mitglied-Detail ueber den Sonderweg, Liste gesperrt."""
	_set_user(mitglied)
	assert client.get("/api/resource/Mitglied").status_code == 403


# ── BLD-04/05: keine rohen SQL-Texte in Antworten (P0-1-Rest) ───────────────


def test_schreiben_fehler_ohne_rohen_sql_text(client, patched_db, monkeypatch):
	"""ROT vorher: `_apply_resource_write` gab `str(exc)` aus — Schema-Leck
	(Tabellen-, Spalten-, Constraint-Namen) direkt an den Client."""
	from diakronos_app.models.kronos import Eventkategorie

	sess = patched_db()
	sess.add(Eventkategorie(name="EK-W", event_category_name="Probe"))
	sess.commit()
	sess.close()

	import diakronos_app.db as dbmod

	class _KaputteSitzung:
		def __init__(self, echt):
			self._echt = echt

		def __getattr__(self, name):
			return getattr(self._echt, name)

		def commit(self):
			raise RuntimeError(
				'column "event_category_name" of relation "eventkategorie" does not exist'
			)

	echt = dbmod.SessionLocal
	monkeypatch.setattr(dbmod, "SessionLocal", lambda: _KaputteSitzung(echt()))

	r = client.put("/api/resource/Eventkategorie/EK-W", json={"event_category_name": "Neu"})
	assert r.status_code == 417, r.text
	text = r.text.lower()
	assert "relation" not in text, "Tabellenname leakt"
	assert "column" not in text, "Spaltenname leakt"
	assert "does not exist" not in text, "roher SQL-Text leakt"
	assert "konnte nicht gespeichert werden" in text


# ── BLD-R1 Rest: Admin bleibt voll handlungsfaehig ──────────────────────────


def test_admin_darf_weiter_lesen_und_schreiben(client, patched_db):
	# `client` laeuft als Administrator (siehe conftest).
	from diakronos_app.models.kronos import Eventkategorie

	assert client.post(
		"/api/resource/Eventkategorie", json={"name": "EK-ADMIN", "event_category_name": "Test"}
	).status_code == 200
	assert client.get("/api/resource/Eventkategorie").status_code == 200
	sess = patched_db()
	assert sess.get(Eventkategorie, "EK-ADMIN") is not None
	sess.close()


# ── BLD-04/05: Loeschen scheitert verstaendlich statt mit HTTP 500 ──────────


def test_loeschen_fehler_liefert_417_statt_500(client, patched_db, monkeypatch):
	"""Wurzel: `resource_delete` committet ohne try/except — jede Ausnahme
	(z. B. Fremdschluessel-Verletzung) schlug als roher 500er durch."""
	from diakronos_app.models.kronos import Element

	sess = patched_db()
	sess.add(Element(name="E-DEL", element_name="Waise"))
	sess.commit()
	sess.close()

	class _KaputteSitzung:
		def __init__(self, echt):
			self._echt = echt

		def __getattr__(self, name):
			return getattr(self._echt, name)

		def commit(self):
			# P0-1-Rest: der Loeschpfad unterscheidet jetzt die echte
			# Fremdschluessel-Verletzung (`IntegrityError` -> "wird noch
			# verwendet") von allem anderen. Die Simulation muss deshalb die
			# echte Ausnahme werfen, nicht irgendeinen RuntimeError.
			from sqlalchemy.exc import IntegrityError

			raise IntegrityError(
				"DELETE FROM element",
				{},
				RuntimeError('update or delete on table "element" violates foreign key constraint'),
			)

	# `resource_delete` importiert `SessionLocal` zur Laufzeit aus
	# `diakronos_app.db` — dort greift der Haken (nicht im Router-Modul).
	import diakronos_app.db as dbmod

	einfach = dbmod.SessionLocal
	monkeypatch.setattr(dbmod, "SessionLocal", lambda: _KaputteSitzung(einfach()))

	r = client.delete("/api/resource/Element/E-DEL")
	assert r.status_code == 417, r.text
	body = r.json()
	assert body["exception"] == "ValidationError"
	assert "kann nicht gelöscht werden" in body["message"]
	assert "foreign key constraint" not in body["message"].lower()


def test_loeschen_sonstiger_fehler_bleibt_generisch(client, patched_db, monkeypatch):
	"""P0-1-Rest (klein): nur die FK-Verletzung heisst "wird noch verwendet".

	Ein anderer Fehler (z. B. Verbindungsabbruch) darf diese Ursache nicht
	behaupten — vorher meldete das pauschale `except Exception` sie immer.
	"""
	from diakronos_app.models.kronos import Element

	sess = patched_db()
	sess.add(Element(name="E-CONN", element_name="Verbindung"))
	sess.commit()
	sess.close()

	import diakronos_app.db as dbmod

	class _KaputteSitzung:
		def __init__(self, echt):
			self._echt = echt

		def __getattr__(self, name):
			return getattr(self._echt, name)

		def commit(self):
			raise RuntimeError("connection reset by peer")

	echt = dbmod.SessionLocal
	monkeypatch.setattr(dbmod, "SessionLocal", lambda: _KaputteSitzung(echt()))

	r = client.delete("/api/resource/Element/E-CONN")
	assert r.status_code == 417, r.text
	msg = r.json()["message"]
	assert "wird noch von anderen Einträgen verwendet" not in msg
	assert "konnte nicht gelöscht werden" in msg


def test_loeschen_fehler_laesst_zeile_stehen(client, patched_db, monkeypatch):
	"""Kein halber Loeschvorgang: nach dem Fehler existiert die Zeile weiter."""
	from diakronos_app.models.kronos import Element

	einfach = patched_db()
	einfach.add(Element(name="E-BLEIBT", element_name="Bleibt"))
	einfach.commit()
	einfach.close()

	import diakronos_app.db as dbmod

	class _KaputteSitzung:
		def __init__(self, echt):
			self._echt = echt

		def __getattr__(self, name):
			return getattr(self._echt, name)

		def commit(self):
			from sqlalchemy.exc import IntegrityError

			raise IntegrityError("DELETE FROM element", {}, RuntimeError("foreign key constraint"))

	echter_factory = dbmod.SessionLocal
	monkeypatch.setattr(dbmod, "SessionLocal", lambda: _KaputteSitzung(echter_factory()))

	assert client.delete("/api/resource/Element/E-BLEIBT").status_code == 417

	sess = patched_db()
	assert sess.get(Element, "E-BLEIBT") is not None
	sess.close()
