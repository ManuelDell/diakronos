"""SEC-5 — Credential-Felder auch auf dem SCHREIBWEG sperren (Pentest R2, N1).

Befund (``/root/.hermes/scratch/diakronos-pentest/bericht-deepseek-runde2.md``,
N1, MITTEL): SEC-1 filterte nur die ANTWORT. ``_apply_resource_write`` in
``frappe_compat/router.py`` schrieb jeden Payload-Schluessel per ``setattr``
(Update) bzw. als Konstruktor-Argument (Create). Damit war ``password_hash``
ueber ``POST``/``PUT /api/resource/User`` setzbar (Mass-Assignment): der
Angreifer uebernahm ein Konto, ohne das alte Passwort zu kennen — die
Antwort war danach sauber, der Schaden aber schon in der DB.

S1: Die vorhandene Sperrliste (``query.ist_gesperrtes_feld``) gilt jetzt auch
    fuer die EINGABE — Create UND Update. Steht ein solcher Schluessel im
    Payload, wird der Request mit 400 abgewiesen (generische Meldung ohne
    Feldnamen-Leak), statt den Schluessel still zu verwerfen.
S2: Passwoerter setzt weiterhin nur der dedizierte Weg
    (``api/zugang.py`` / ``set-password``, ``passwoerter.neuer_hash``).

Was hier NICHT kaputtgehen darf: normale Felder bleiben schreibbar, und
``content_hash`` bei ``File`` ist ein Integritaetswert (kein Geheimnis,
konsistent zu SEC-1) — er bleibt setzbar.
"""

from __future__ import annotations

import pytest

# Marken — keine echten Hashes eines echten Kontos.
HASH_ALT = "$argon2id$v=19$m=65536,t=3,p=4$ALTaltaltaltaltaltalt$altaltaltaltaltaltaltaltaltaltaltalt"
HASH_NEU = "$argon2id$v=19$m=65536,t=3,p=4$NEUneuneuneuneuneun$neuneuneuneuneuneuneuneuneuneuneuneuneu"

OPFER = "sec5-opfer@example.org"


def _konto_anlegen(patched_db, name: str, *, passwort: str | None = None) -> None:
	"""Konto in der Test-DB anlegen — optional mit echtem Passwort-Hash."""
	from diakronos_app.frappe_compat.passwoerter import neuer_hash
	from diakronos_app.models.core import User

	sess = patched_db()
	if sess.get(User, name) is None:
		sess.add(User(
			name=name,
			email=name,
			full_name=f"Konto {name}",
			enabled=True,
			user_type="System User",
			password_hash=neuer_hash(passwort) if passwort else HASH_ALT,
		))
		sess.commit()
	sess.close()


def _hash_in_db(patched_db, name: str) -> str | None:
	from diakronos_app.models.core import User

	sess = patched_db()
	try:
		konto = sess.get(User, name)
		return None if konto is None else konto.password_hash
	finally:
		sess.close()


def _anmeldung_moeglich(patched_db, name: str, passwort: str) -> bool:
	"""Prueft das Passwort ueber denselben Weg wie der Login."""
	from diakronos_app.frappe_compat.passwoerter import neuer_hash, pruefe

	hash_wert = _hash_in_db(patched_db, name)
	if hash_wert and hash_wert.startswith(("$argon2", "$pbkdf2-sha256$")):
		return pruefe(passwort, hash_wert)
	return neuer_hash(passwort) == hash_wert


@pytest.fixture()
def opfer(patched_db):
	"""Ein Konto mit bekanntem Passwort — das Ziel des Mass-Assignments."""
	_konto_anlegen(patched_db, OPFER, passwort="Original-Passwort-2026")
	return patched_db


# ── S1: Update (PUT) ────────────────────────────────────────────────────────


def test_put_user_mit_password_hash_wird_abgelehnt(client, opfer):
	"""ROT vorher: 200 — der Hash in der DB war danach ueberschrieben."""
	vorher = _hash_in_db(opfer, OPFER)
	assert vorher and vorher != HASH_NEU

	r = client.put("/api/resource/User/" + OPFER, json={"password_hash": HASH_NEU})

	assert r.status_code == 400, r.text
	# Generische Meldung: der Feldname darf nicht gespiegelt werden.
	assert "password_hash" not in r.text
	assert HASH_NEU not in r.text
	# Und der bestehende Hash ist unveraendert — Login mit Originalpasswort geht.
	assert _hash_in_db(opfer, OPFER) == vorher
	assert _anmeldung_moeglich(opfer, OPFER, "Original-Passwort-2026")


def test_put_user_mit_password_hash_und_harmlosem_feld_bleibt_ganz_aus(client, opfer):
	"""Atomar: ein gesperrter Schluessel im Rumpf blockt den ganzen Request.

	Sonst koennte ein Angreifer den abgelehnten Teil als 'bestaetigt' werten
	und den harmlosen Rest trotzdem schreiben — hier bleibt alles unveraendert.
	"""
	vorher = _hash_in_db(opfer, OPFER)

	r = client.put(
		"/api/resource/User/" + OPFER,
		json={"full_name": "Uebernommen", "password_hash": HASH_NEU},
	)

	assert r.status_code == 400, r.text
	assert _hash_in_db(opfer, OPFER) == vorher
	from diakronos_app.models.core import User

	sess = opfer()
	try:
		assert sess.get(User, OPFER).full_name != "Uebernommen"
	finally:
		sess.close()


@pytest.mark.parametrize("feld", [
	"password",
	"passwort",
	"token_hash",
	"api_key",
	"client_secret",
	"auth_proxy_shared_secret",
])
def test_put_user_mit_jedem_gesperrten_feldnamen_wird_abgelehnt(client, opfer, feld):
	"""Die ganze Sperrliste gilt auf dem Schreibweg, nicht nur ``password_hash``."""
	r = client.put("/api/resource/User/" + OPFER, json={feld: "boese"})
	assert r.status_code == 400, r.text
	assert feld not in r.text


# ── S1: Create (POST) ───────────────────────────────────────────────────────


def test_post_user_mit_password_hash_wird_abgelehnt(client, patched_db):
	"""ROT vorher: das neue Konto entstand direkt mit fremdem Hash."""
	neu = "sec5-neu@example.org"
	from diakronos_app.models.core import User

	r = client.post(
		"/api/resource/User",
		json={"name": neu, "email": neu, "full_name": "Neu", "password_hash": HASH_NEU},
	)

	assert r.status_code == 400, r.text
	assert "password_hash" not in r.text
	assert HASH_NEU not in r.text
	sess = patched_db()
	try:
		assert sess.get(User, neu) is None, "abgelehnter Request hat trotzdem geschrieben"
	finally:
		sess.close()


# ── Kein Regress: normale Felder bleiben schreibbar ─────────────────────────


def test_put_user_normales_feld_bleibt_schreibbar(client, opfer):
	r = client.put("/api/resource/User/" + OPFER, json={"full_name": "Neuer Name"})
	assert r.status_code == 200, r.text
	assert r.json()["data"]["full_name"] == "Neuer Name"
	# Und die Schreib-Antwort leakt nichts (SEC-1 bleibt wirksam).
	assert HASH_ALT not in r.text
	assert "password_hash" not in r.text


def test_post_user_ohne_geheimfeld_bleibt_erlaubt(client, patched_db):
	neu = "sec5-frisch@example.org"
	r = client.post(
		"/api/resource/User",
		json={"name": neu, "email": neu, "full_name": "Frisch"},
	)
	assert r.status_code == 200, r.text
	assert r.json()["data"]["name"] == neu


def test_file_content_hash_bleibt_schreibbar(client, patched_db):
	"""``content_hash`` ist ein Integritaetswert — SEC-1 sperrt ihn bewusst nicht."""
	from diakronos_app.models.core import FileModel

	sess = patched_db()
	sess.add(FileModel(
		name="SEC5F1",
		file_name="beleg.pdf",
		file_url="/files/beleg.pdf",
		content_hash="alt",
		is_private=True,
	))
	sess.commit()
	sess.close()

	r = client.put("/api/resource/File/SEC5F1", json={"content_hash": "neu-1234"})
	assert r.status_code == 200, r.text
	assert r.json()["data"]["content_hash"] == "neu-1234"


def test_post_file_mit_content_hash_bleibt_erlaubt(client, patched_db):
	r = client.post(
		"/api/resource/File",
		json={"name": "SEC5F2", "file_name": "x.pdf", "file_url": "/files/x.pdf",
		      "content_hash": "abc-999"},
	)
	assert r.status_code == 200, r.text
	assert r.json()["data"]["content_hash"] == "abc-999"


# ── S2: Der dedizierte Weg bleibt der einzige, der Passwoerter setzt ────────


def test_dedizierter_weg_setzt_passwort_weiter(client, patched_db):
	"""Gegenprobe: ``passwoerter.neuer_hash`` ist die erlaubte Stelle.

	Der generische CRUD bleibt fuer Geheimfelder zu (oben), der dedizierte
	Weg erzeugt weiterhin einen gueltigen Hash fuer das Klartextpasswort.
	"""
	from diakronos_app.frappe_compat.passwoerter import neuer_hash, pruefe

	wert = neuer_hash("Frisches-Passwort-2026")
	assert wert and wert != HASH_ALT
	assert pruefe("Frisches-Passwort-2026", wert) is True
	assert pruefe("falsch", wert) is False
