"""SEC-1 — kein Passwort-/Token-Hash-Abfluss ueber die generische Resource-API.

Befund (Pentest dev.ecg-hn.de, HOCH, ``.hermes/scratch/diakronos-pentest/
bericht-deepseek.md`` Abschnitt 1): ``GET /api/resource/User/{email}`` und
``GET /api/resource/User`` lieferten das Feld ``password_hash`` (argon2id) im
JSON. Damit war Offline-Cracking gegen JEDEN Hash moeglich, sobald ein Konto
die User-Ressource lesen durfte.

Die Sperre sitzt zentral im Resource-Serializer
(``frappe_compat/query.py``) und gilt fuer ALLE Doctypes, fuer Liste wie
Einzelabruf, auch bei expliziter ``fields``-Projektion und ``pluck``.
Zusaetzlich ist der Lesezugriff auf ``User``/``Has Role`` auf
``System Manager`` beschraenkt.

Was hier NICHT kaputtgehen darf: Nicht-Geheim-Spalten bleiben vollstaendig
sichtbar (sonst waere die Sperre eine Funktionsverschlechterung), und
``File.content_hash`` (Integritaetsnachweis einer Datei, kein Geheimnis)
bleibt erhalten.
"""

from __future__ import annotations

import pytest

# Der Wert, der im Pentest ausgeliefert wurde — nur als Testmarke, kein echter
# Hash eines echten Kontos.
HASH_MARKE = "$argon2id$v=19$m=65536,t=3,p=4$5Hya2LccVHuRiTRxgl58Cw$b9UtP3biMM6yKaiA6VdkUS8T6qOHUbUaWRbb0Y6hD8g"
TOKEN_MARKE = "f" * 64


def _set_user(user: str) -> None:
	from diakronos_app.frappe_compat.session import set_user

	set_user(user)


def _konto_anlegen(patched_db, name: str, *, rolle: str | None = None) -> None:
	"""Ein Konto (plus optional eine Rolle) in der Test-DB anlegen.

	Rollen stehen in `Has Role` (Kind von `User`) — das ist die Quelle von
	`permissions.get_roles`; `UserRole` ist der Link-Ziel-Stub fuer Kalender.
	"""
	from diakronos_app.models.core import HasRole, Role, User

	sess = patched_db()
	if sess.get(User, name) is None:
		sess.add(User(
			name=name,
			email=name,
			full_name=f"Konto {name}",
			enabled=True,
			user_type="System User",
			password_hash=HASH_MARKE,
		))
	if rolle:
		if sess.get(Role, rolle) is None:
			sess.add(Role(name=rolle))
		sess.flush()
		sess.add(HasRole(name=f"HR-{name}", parent=name, parenttype="User",
		                 role=rolle, docstatus=0, idx=0))
	sess.commit()
	sess.close()


@pytest.fixture()
def zwei_konten(patched_db):
	"""Zwei konten mit Hash in der DB — der Bestand aus dem Pentest-Bericht."""
	_konto_anlegen(patched_db, "sec1-admin@example.org", rolle="System Manager")
	_konto_anlegen(patched_db, "sec1-anna@example.org")
	return patched_db


@pytest.fixture()
def mitglied(patched_db):
	"""Ein angemeldeter Nicht-Admin ohne Admin-Rolle (Regel B1: Zeile noetig)."""
	from diakronos_app.models.core import User

	sess = patched_db()
	if sess.get(User, "sec1-einfach@example.org") is None:
		sess.add(User(
			name="sec1-einfach@example.org",
			email="sec1-einfach@example.org",
			full_name="Einfacher Nutzer",
			enabled=True,
		))
		sess.commit()
	sess.close()
	return "sec1-einfach@example.org"


# ── S1: Einzelabruf als Administrator ───────────────────────────────────────


def test_admin_einzelabruf_user_ohne_password_hash(client, zwei_konten):
	"""ROT vorher: 200 mit ``password_hash`` in der Antwort."""
	r = client.get("/api/resource/User/sec1-anna@example.org")
	assert r.status_code == 200, r.text
	daten = r.json()["data"]
	assert "password_hash" not in daten, "Passwort-Hash wurde ausgeliefert"
	assert HASH_MARKE not in r.text
	# Kein Regress: die harmlosen Kontofelder bleiben da.
	assert daten["name"] == "sec1-anna@example.org"
	assert daten["email"] == "sec1-anna@example.org"
	assert "enabled" in daten


def test_admin_einzelabruf_user_mit_feldfilter_ohne_password_hash(client, zwei_konten):
	"""Auch eine ausdrueckliche Projektion darf den Hash nicht zurueckholen."""
	r = client.get('/api/resource/User/sec1-anna@example.org?fields=["name","password_hash"]')
	assert r.status_code == 200, r.text
	assert HASH_MARKE not in r.text
	assert "password_hash" not in r.json()["data"]


# ── S1: Liste als Administrator ─────────────────────────────────────────────


def test_admin_liste_user_ohne_password_hash(client, zwei_konten):
	"""ROT vorher: die Liste enthielt ``password_hash`` fuer beide Konten."""
	r = client.get("/api/resource/User")
	assert r.status_code == 200, r.text
	zeilen = r.json()["data"]
	assert zeilen, "Testbestand fehlt"
	assert all("password_hash" not in z for z in zeilen), "Passwort-Hash wurde ausgeliefert"
	assert HASH_MARKE not in r.text
	assert any(z["name"] == "sec1-anna@example.org" for z in zeilen)


def test_admin_liste_user_mit_feldfilter_ohne_password_hash(client, zwei_konten):
	"""Fail closed: eine Projektion auf ein Geheimnis wird abgewiesen (404,
	wie ein unbekanntes Feld) — statt den Hash zu liefern."""
	r = client.get('/api/resource/User?fields=["name","password_hash"]')
	assert r.status_code == 404, r.text
	assert HASH_MARKE not in r.text


def test_admin_liste_user_mit_alias_auf_password_hash(client, zwei_konten):
	"""Auch ein Alias darf das Geheimnis nicht zurueckholen."""
	r = client.get('/api/resource/User?fields=["password_hash as x"]')
	assert r.status_code == 404, r.text
	assert HASH_MARKE not in r.text


def test_admin_liste_user_pluck_password_hash_leer(client, zwei_konten):
	"""``pluck=password_hash`` liefert nichts Verwertbares (kein Hash im Text).

	Fail closed: das Feld ist "unbekannt" (404) — es wird kein nackter
	Skalar-Hash ausgeliefert.
	"""
	r = client.get("/api/resource/User?pluck=password_hash")
	assert r.status_code == 404, r.text
	assert HASH_MARKE not in r.text


def test_admin_liste_user_as_list_ohne_password_hash(client, zwei_konten):
	"""``as_list=1`` (nackte Zeilen) darf die Sperre ebenfalls nicht umgehen."""
	r = client.get("/api/resource/User?as_list=1")
	assert r.status_code == 200, r.text
	assert HASH_MARKE not in r.text


# ── S1: Sperre fuer ALLE Doctypes, nicht nur User ───────────────────────────


def test_sperrliste_gilt_fuer_jeden_doctype(client, patched_db):
	"""Auch ein unauffaelliger DocType mit ``_hash``-Spalte bleibt sauber.

	``File.content_hash`` ist bewusst NICHT gesperrt (Integritaetsnachweis,
	kein Geheimnis) — die Sperre greift gezielt auf ``password_hash``,
	``token_hash``, ``*_secret`` und ``api_key``.
	"""
	from diakronos_app.models.core import FileModel

	sess = patched_db()
	sess.add(FileModel(
		name="SEC1F1",
		file_name="beleg.pdf",
		file_url="/files/beleg.pdf",
		content_hash="schluesselwert-1234",
		is_private=True,
	))
	sess.commit()
	sess.close()

	r = client.get("/api/resource/File/SEC1F1")
	assert r.status_code == 200, r.text
	assert r.json()["data"]["content_hash"] == "schluesselwert-1234", (
		"content_hash ist ein Integritaetswert und darf sichtbar bleiben"
	)


def test_zentrale_sperrliste_ist_vollstaendig():
	"""Die Liste deckt die Pflichtfelder aus der Karte ab."""
	from diakronos_app.frappe_compat.query import ist_gesperrtes_feld

	for feld in ("password_hash", "token_hash", "api_key", "secret",
	             "client_secret", "auth_proxy_shared_secret", "irgendwas_secret",
	             "neuer_token_hash"):
		assert ist_gesperrtes_feld(feld), f"{feld} fehlt in der Sperrliste"
	# Schluessel und Hashes, die KEINE Geheimnisse sind, bleiben sichtbar.
	for feld in ("content_hash", "name", "email", "full_name", "enabled",
	             "has_role", "schluessel"):
		assert not ist_gesperrtes_feld(feld), f"{feld} faelschlich gesperrt"


# ── S2: User-Ressource nur fuer System Manager ─────────────────────────────


def test_mitglied_darf_user_weder_einzeln_noch_als_liste_lesen(client, mitglied, zwei_konten):
	"""ROT vorher: jedes angemeldete Konto konnte die Hash-Liste lesen.

	Der Identitaetswechsel laeuft ueber die Naht (`set_user`) — die
	`SessionMiddleware` respektiert ihn pro Request.
	"""
	_set_user(mitglied)
	assert client.get("/api/resource/User").status_code == 403
	assert client.get("/api/resource/User/sec1-anna@example.org").status_code == 403
	assert client.get("/api/resource/User?fields=[\"name\"]").status_code == 403
	assert client.get("/api/resource/User?pluck=password_hash").status_code == 403
	# Kein Hash im Fehlertext (auch 403-Antworten nicht auswerten — sicher ist sicher).
	assert HASH_MARKE not in client.get("/api/resource/User").text


def test_mitgliederadministrator_darf_user_nicht_lesen(client, patched_db):
	"""Auch die Mitglieder-Verwaltungsrolle gibt Konten NICHT frei."""
	_konto_anlegen(patched_db, "sec1-verwaltung@example.org",
	                rolle="Mitgliederadministrator")
	_set_user("sec1-verwaltung@example.org")
	assert client.get("/api/resource/User").status_code == 403
	assert client.get("/api/resource/User/sec1-anna@example.org").status_code == 403


def test_system_manager_darf_user_weiter_lesen(patched_db, fake_redis):
	"""Gegenprobe: die Kontenverwaltung bleibt fuer `System Manager` offen.

	Geprueft wird die Zugriffsentscheidung UND die Antwort selbst (ohne
	``password_hash``). Der Aufruf geht direkt durch den Router-Handler, weil
	`set_user()` die Response-Middleware nicht uebersteht (sie setzt die
	Identitaet nach dem Handler zurueck) — das ist die dokumentierte Grenze der
	Test-Naht, kein Sonderweg des Produktivcodes.
	"""
	import asyncio

	from diakronos_app.frappe_compat.router import _resource_denied, resource_list
	from diakronos_app.frappe_compat.session import set_user

	_konto_anlegen(patched_db, "sec1-sm@example.org", rolle="System Manager")
	set_user("sec1-sm@example.org")
	assert _resource_denied("User", "list") is None
	assert _resource_denied("User", "read") is None

	antwort = asyncio.run(resource_list("User", _Anfrage()))
	assert antwort.status_code == 200, antwort.body
	assert HASH_MARKE not in antwort.body.decode()
	assert b"password_hash" not in antwort.body


class _Anfrage:
	"""Minimal-`Request` fuer den direkten Handler-Aufruf (nur Query-Parameter)."""

	query_params: dict = {}



# ── S1: Schreib-Antwort (POST/PUT) — Review-Nachtrag ─────────────────────────


def test_admin_put_user_antwort_ohne_password_hash(client, zwei_konten):
	"""PUT /api/resource/User darf den Hash nicht in der Antwort spiegeln.

	Review SEC-1: `_apply_resource_write` serialisierte frueher nur die WERTE,
	nicht die KEYS -> password_hash kam in der Schreib-Antwort zurueck, obwohl
	alle Lesewege ihn filtern. Dieser Test nagelt den geschlossenen Pfad fest.
	"""
	r = client.put(
		"/api/resource/User/sec1-anna@example.org",
		json={"full_name": "Anna Geaendert"},
	)
	assert r.status_code == 200, r.text
	assert HASH_MARKE not in r.text
	assert "password_hash" not in r.json().get("data", {})
