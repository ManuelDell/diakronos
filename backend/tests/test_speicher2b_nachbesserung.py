"""SPEICHER-2b — die sechs Befunde aus der dritten Review-Runde.

Die Karte nennt sechs Punkte; jeder hat hier seinen Test:

1. **Doppelte Zeile** in ``_laeufe_aus_der_nextcloud``: ein fehlgeschlagener
   Lauf mit TEILORDNER in der Nextcloud erschien zweimal. Jetzt genau einmal,
   die Fehlerzeile gewinnt.
2. **Verbindungsleck** im Streaming-PUT: ``strom=True`` liess jede Antwort
   offen, bis der Pool erschoepft war.
3. **Sperre verlaengern**: die TTL ist eine Schaetzung; waehrend Upload und
   Gegenprobe wird sie nachgefasst (Herzschlag).
4. **Nur lokale Kopie bleibt**: ohne vollstaendige Sicherung in der Nextcloud
   lehnt die API das Loeschen ab (nicht nur die Oberflaeche).
5. **Ordner selbst loeschen**: ``_leere_ordner_entfernen`` griff nie, weil
   ``auflisten`` nur Dateien nennt — jetzt WebDAV-DELETE auf die Ordner-Adresse.
6. **Nextcloud nicht erreichbar**: ``benutzbar=False`` hat einen Text, keinen
   leeren roten Kasten.

KEIN Netz: die Ablage ist ein ``httpx.MockTransport`` (``FakeWebDAV`` aus
``test_speicher1_vertrag``) oder ein Doppel im Prozess.
"""

from __future__ import annotations

import io
import time
from datetime import datetime

import httpx
import pytest

from diakronos_app.sicherung import cloud, dump, lauf as lauf_modul
from diakronos_app.sicherung import sperre as sperre_modul
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

from test_speicher1_vertrag import URL
from test_speicher2_sicherung import (  # noqa: F401 — Fixtures
	BLOCK,
	ZUGANG,
	_nextcloud,
	_prepare_db,
	_sicherung_anlegen,
	_system_manager,
	backup_heim,
	fake,
	fake_dump,
	nextcloud_aktiv,
	redis_stub_fuer_sperre,
)


# ── 1. Jeder Name genau eine Zeile ─────────────────────────────────────────

def test_fehlgeschlagener_lauf_mit_teilordner_steht_genau_einmal(
	client, set_user, backup_heim, nextcloud_aktiv,
):
	"""Der Kern von Punkt 1: Ordnerschleife UND Fehlerzeile zeigten denselben Namen."""
	from diakronos_app import db
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	with db.SessionLocal() as sess:
		_system_manager(sess)
		# Ein halber Upload: Ordner liegt in der Nextcloud, aber ohne FERTIG.
		nextcloud_aktiv.schreiben("sicherungen/2026-11-18_030000/db.dump", b"halb")
		sess.add(Sicherungslauf(
			name="2026-11-18_030000",
			begonnen_am=datetime(2026, 11, 18, 3, 0, 0),
			status=STATUS_FEHLGESCHLAGEN,
			meldung="Die Sicherung liegt nur lokal — die Uebertragung in die "
			        "Nextcloud ist nicht vollstaendig.",
			groesse_bytes=4,
		))
		sess.commit()

	set_user("chef")
	antwort = client.get("/api/method/sicherung_get")
	assert antwort.status_code == 200, antwort.text
	inhalt = antwort.json().get("message", antwort.json())
	namen = [eintrag["name"] for eintrag in inhalt["sicherungen"]]
	assert namen == ["2026-11-18_030000"], f"doppelte Zeile: {namen}"
	eintrag = inhalt["sicherungen"][0]
	# Die Fehlerzeile gewinnt: Status und Grund stehen da, der Rest ist
	# trotzdem als unvollstaendig erkennbar.
	assert eintrag["status"] == STATUS_FEHLGESCHLAGEN
	assert "Nextcloud" in eintrag["meldung"]
	assert eintrag["vollstaendig"] is False


def test_vollstaendige_sicherung_bleibt_bei_ihrem_ordner_eintrag(
	client, set_user, backup_heim, nextcloud_aktiv,
):
	"""Der Gegenfall: eine VOLLSTAENDIGE Sicherung wird nicht durch das
	Protokoll „ersetzt“ — dort steht ``vollstaendig: True``."""
	from diakronos_app import db
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	with db.SessionLocal() as sess:
		_system_manager(sess)
		ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000")
		cloud.hochladen(ordner, ablage=nextcloud_aktiv)
		sess.add(Sicherungslauf(
			name="2026-11-18_030000",
			begonnen_am=datetime(2026, 11, 18, 3, 0, 0),
			status=STATUS_OK,
		))
		sess.commit()

	set_user("chef")
	inhalt = client.get("/api/method/sicherung_get").json()
	inhalt = inhalt.get("message", inhalt)
	assert [e["name"] for e in inhalt["sicherungen"]] == ["2026-11-18_030000"]
	assert inhalt["sicherungen"][0]["vollstaendig"] is True


# ── 2. Kein Verbindungsleck beim Streaming-PUT ─────────────────────────────

def test_streaming_put_laesst_keine_antwort_offen(fake):
	"""Punkt 2: der PUT fordert KEINEN offenen Strom (``strom=True``) an.

	Mit ``strom=True`` schickt ``_anfrage`` ``client.send(..., stream=True)``
	— und der Aufrufer (``_schreibe_strom``) schliesst die Antwort nie: die
	Verbindung bleibt im Pool haengen, bis keiner mehr frei ist. Der Test
	belegt beides: der PUT geht ueber den normalen Weg (kein
	``send(..., stream=True)``), und die Antwort ist danach geschlossen.

	Ein Zaehler am Transport misst hier nichts (``MockTransport`` liefert gar
	keine ``BoundSyncStream``, deren ``close()`` man beobachten koennte) —
	deshalb wird der Weg selbst geprueft: ``send`` mit ``stream=True`` ist
	genau das Muster, das die Antwort offen laesst.
	"""
	wege: list[str] = []

	def handler(anfrage: httpx.Request) -> httpx.Response:
		anfrage.read()  # wie MockTransport — der Koerper wird eingelesen
		wege.append(anfrage.method)
		return fake(anfrage)

	client = httpx.Client(transport=httpx.MockTransport(handler), auth=ZUGANG,
	                      trust_env=False)
	gesendet_mit_strom: list[bool] = []
	echtes_send = client.send

	def send(anfrage, **kwargs):
		if anfrage.method == "PUT":
			gesendet_mit_strom.append(bool(kwargs.get("stream", False)))
		return echtes_send(anfrage, **kwargs)

	client.send = send  # type: ignore[method-assign]
	zugang = NextcloudZugang(URL, *ZUGANG, "/Diakronos", timeout=5.0,
	                         transfer_timeout=5.0, versuche=1)
	ablage = Nextcloud(zugang, client=client)
	try:
		for nummer in range(4):
			ablage.schreiben(f"probe-{nummer}.bin", io.BytesIO(b"x" * (300 * 1024)))
			assert ablage.groesse(f"probe-{nummer}.bin") == 300 * 1024
	finally:
		client.close()
	assert wege.count("PUT") == 4, wege
	assert gesendet_mit_strom == [False] * 4, (
		"der PUT fordert weiter einen offenen Strom an — die Antwort wird "
		"nirgends geschlossen (Verbindungsleck)"
	)


def test_streaming_put_bleibt_ein_echter_strom(fake):
	"""Gegenprobe zu Punkt 2: der Koerper geht weiter blockweise hinaus.

	Die Antwort des PUT wird eingelesen (kein ``strom=True``) — der
	ANFRAGEKOERPER bleibt trotzdem ein Strom: er wird waehrend des Sendens aus
	der Datei gelesen, nie ganz in den Speicher geholt.
	"""
	from diakronos_app.speicher import nextcloud as modul

	gelesen: list[int] = []

	class ZaehlendeDatei:
		def __init__(self) -> None:
			self._datei = io.BytesIO(b"y" * (2 * BLOCK + 3))

		def read(self, anzahl: int = -1) -> bytes:
			gelesen.append(anzahl)
			return self._datei.read(anzahl)

		def seek(self, *args) -> int:
			return self._datei.seek(*args)

		def tell(self) -> int:
			return self._datei.tell()

		def fileno(self) -> int:
			return -1

	quelle = ZaehlendeDatei()
	ablage = _nextcloud(fake)
	ablage.schreiben("probe.bin", quelle)
	assert len(gelesen) >= 2, gelesen
	assert max(gelesen) <= modul.BLOCKGROESSE, gelesen


# ── 3. Sperre wird waehrend des Laufs verlaengert ──────────────────────────

class RekordSperre:
	"""Sperre-Doppel: setzt, zaehlt Verlaengerungen, gibt frei."""

	gesetzt = 0
	verlaengert = 0

	def __init__(self, ttl_sekunden: int = 3600) -> None:
		self.ttl = ttl_sekunden
		self._token = "tok"

	def setzen(self) -> None:
		RekordSperre.gesetzt += 1

	def verlaengern(self, ttl_sekunden=None) -> bool:
		RekordSperre.verlaengert += 1
		return True

	def freigeben(self) -> None:
		self._token = None


def test_sperre_wird_waehrend_upload_und_gegenprobe_verlaengert(
	monkeypatch, patched_db, backup_heim, fake_dump, nextcloud_aktiv,
):
	"""Punkt 3: die TTL ist eine Schaetzung — der Lauf fasst sie nach.

	Der Takt wird auf 0,02 s gesetzt, damit auch ein winziger Testlauf mehrere
	Herzschlaege sieht (im Betrieb sind es 60 s).
	"""
	import threading

	RekordSperre.gesetzt = RekordSperre.verlaengert = 0
	monkeypatch.setattr(lauf_modul, "Sicherungssperre", RekordSperre)
	monkeypatch.setattr(lauf_modul, "HERZSCHLAG_SEKUNDEN", 0.02)

	waehrend_upload: list[int] = []
	echt_hochladen = cloud.hochladen

	def langsam_hochladen(verzeichnis, *, ablage=None):
		# Waehrend der Upload laeuft, muss der Herzschlag schon geklopft haben.
		time.sleep(0.15)
		waehrend_upload.append(RekordSperre.verlaengert)
		return echt_hochladen(verzeichnis, ablage=ablage)

	monkeypatch.setattr(cloud, "hochladen", langsam_hochladen)

	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	sess = _prepare_db(patched_db, jetzt)
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_MANUELL, jetzt=jetzt, sitzung=sess,
			aufraeumen=False,
		)
	finally:
		sess.close()
	# Der Herzschlag-Faeden darf den Lauf nicht ueberleben.
	assert not [t for t in threading.enumerate() if t.name == "sicherung-herzschlag"]
	assert ergebnis.ok, ergebnis.meldung
	assert RekordSperre.gesetzt == 1
	assert waehrend_upload and waehrend_upload[0] >= 1, (
		"die Sperre wurde waehrend des Uploads nicht nachgefasst"
	)
	assert RekordSperre.verlaengert >= 1


def test_mit_herzschlag_verlaengert_und_stellt_fehler_durch(monkeypatch):
	"""Der Herzschlag ist Beiwerk: er verlaengert, wirft aber nie selbst."""
	import threading

	class Sperre:
		hier = 0

		def verlaengern(self, ttl_sekunden=None):
			Sperre.hier += 1
			return True

	vorher = threading.active_count()
	ergebnis = lauf_modul._mit_herzschlag(
		Sperre(), lambda: (time.sleep(0.2), "fertig")[1], takt=0.01,
	)
	assert ergebnis == "fertig"
	assert Sperre.hier >= 1, "die Sperre wurde nicht nachgefasst"
	assert threading.active_count() <= vorher + 1

	# Eine Ausnahme kommt durch — der Faeden wird trotzdem gestoppt.
	def platzt():
		raise RuntimeError("kaputt")

	with pytest.raises(RuntimeError):
		lauf_modul._mit_herzschlag(Sperre(), platzt, takt=0.01)
	assert not [t for t in threading.enumerate() if t.name == "sicherung-herzschlag"]


def test_verlaengern_nur_mit_eigener_sperre(monkeypatch):
	"""``verlaengern`` gibt ``False``, wenn die Sperre nicht (mehr) uns gehoert."""

	class Stub:
		def __init__(self):
			self.values: dict = {}

		def set(self, key, wert, nx=False, px=None):
			if nx and key in self.values:
				return False
			self.values[key] = wert
			return True

		def get(self, key):
			return self.values.get(key)

		def delete(self, key):
			self.values.pop(key, None)

		def eval(self, skript, anzahl, key, token, ms):
			# Vergleich-und-Setzen wie im Lua-Skript: nur die eigene Sperre.
			return 1 if self.values.get(key) == token else 0

	stub = Stub()
	monkeypatch.setattr(sperre_modul, "_client", lambda: stub)

	sperre = sperre_modul.Sicherungssperre(ttl_sekunden=60)
	sperre.setzen()
	assert sperre.verlaengern() is True
	assert sperre.verlaengern(120) is True
	# Ein anderer haelt die Sperre jetzt.
	stub.values[sperre_modul.SPERRE_SCHLUESSEL] = "fremd"
	assert sperre.verlaengern() is False
	# Ohne Sperre (nach ``freigeben``) gibt es nichts zu verlaengern.
	sperre._token = None
	assert sperre.verlaengern() is False


# ── 4. Die einzige lokale Kopie bleibt ─────────────────────────────────────

def test_loeschen_der_einzigen_lokalen_kopie_wird_abgelehnt(
	client, set_user, backup_heim, nextcloud_aktiv,
):
	"""Punkt 4: keine vollstaendige Sicherung in der Nextcloud -> Ablehnung."""
	from diakronos_app import db
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	with db.SessionLocal() as sess:
		_system_manager(sess)
		ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000")
		assert ordner.is_dir()
		sess.add(Sicherungslauf(
			name="2026-11-18_030000",
			begonnen_am=datetime(2026, 11, 18, 3, 0, 0),
			status=STATUS_FEHLGESCHLAGEN,
			meldung="Die Sicherung liegt nur lokal.",
		))
		sess.commit()

	set_user("chef")
	antwort = client.post("/api/method/sicherung_loeschen",
	                      json={"name": "2026-11-18_030000"})
	assert antwort.status_code >= 400, "die letzte Kopie wurde geloescht!"
	assert "einzige" in antwort.text
	assert (backup_heim / "sicherungen" / "2026-11-18_030000").is_dir()


def test_loeschen_mit_vollstaendiger_kopie_in_der_nextcloud_geht(
	client, set_user, backup_heim, nextcloud_aktiv,
):
	"""Der Gegenfall: die Nextcloud hat eine vollstaendige Kopie — lokal weg."""
	from diakronos_app import db
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	with db.SessionLocal() as sess:
		_system_manager(sess)
		for name in ("2026-11-17_030000", "2026-11-18_030000"):
			ordner = _sicherung_anlegen(backup_heim / "sicherungen", name)
			cloud.hochladen(ordner, ablage=nextcloud_aktiv)
			sess.add(Sicherungslauf(
				name=name,
				begonnen_am=datetime.strptime(
					name, "%Y-%m-%d_%H%M%S"),
				status=STATUS_OK,
			))
		sess.commit()

	set_user("chef")
	antwort = client.post("/api/method/sicherung_loeschen",
	                      json={"name": "2026-11-17_030000"})
	assert antwort.status_code == 200, antwort.text
	assert not (backup_heim / "sicherungen" / "2026-11-17_030000").exists()


# ── 5. Der Ordner selbst wird per WebDAV geloescht ─────────────────────────

def test_loeschen_entfernt_den_ordner_auch_mit_resten(backup_heim, nextcloud_aktiv, fake):
	"""Punkt 5: ein unvollstaendiger Rest wird ueber die ORDNER-Adresse geloescht.

	Vorher lief ``_leere_ordner_entfernen`` ins Leere (``auflisten`` nennt nur
	Dateien) und ein Rest ohne ``FERTIG`` blieb fuer immer stehen.
	"""
	ablage = nextcloud_aktiv
	ablage.schreiben("sicherungen/2026-11-18_030000/db.dump", b"halb")
	ablage.schreiben("sicherungen/2026-11-18_030000/files.tar.gz", b"halb")
	assert ablage.auflisten("sicherungen/2026-11-18_030000")

	assert cloud.loeschen("2026-11-18_030000", ablage=ablage) is True
	assert ablage.auflisten("sicherungen/2026-11-18_030000") == []
	# Und der Ordner selbst ist auch weg — ueber die Ordner-Adresse (nicht
	# Datei fuer Datei).
	ordner_del = [eintrag for eintrag in fake.anfragen
	              if eintrag[0] == "DELETE"
	              and eintrag[1].endswith("/sicherungen/2026-11-18_030000")]
	assert ordner_del, f"kein DELETE auf die Ordner-Adresse: {fake.anfragen[-4:]}"


def test_leere_ordner_werden_ueber_die_ordner_adresse_entfernt():
	"""Punkt 5, zweiter Weg: ``_leere_ordner_entfernen`` loescht den ORDNER.

	``auflisten`` nennt nur Dateien — genau deshalb griff die alte Fassung
	nie. Hier steht ein Doppel bereit, das (wie ``Nextcloud``) seine Ordner
	kennt und einen Ordner ohne Dateien als Rest ausweist. Geloescht werden
	muss er ueber ``ordner_loeschen`` (Ordner-Adresse), NICHT ueber
	``loeschen`` (Datei).
	"""
	class Doppel:
		def __init__(self) -> None:
			# Eine Datei in einem Ordner und ein Ordner OHNE Dateien (Rest).
			self.dateien = {"sicherungen/2026-11-18_030000/db.dump": 9}
			self.rest = {"sicherungen/2020-01-01_030000"}
			self.ordner_geloescht: list[str] = []
			self.datei_geloescht: list[str] = []

		def auflisten(self, praefix=""):
			# ``Nextcloud.auflisten`` nennt NUR Dateien und liefert den
			# abgefragten Ordner selbst mit (so tut es auch dieser Doppel fuer
			# ``sicherungen``).
			treffer = sorted(k for k in self.dateien if k.startswith(praefix))
			if praefix.rstrip("/") == "sicherungen":
				treffer = sorted(set(treffer) | self.rest)
			return treffer

		def groesse(self, schluessel):
			return self.dateien.get(schluessel)

		def ordner_loeschen(self, schluessel):
			if schluessel not in self.rest:
				return False
			self.rest.discard(schluessel)
			self.ordner_geloescht.append(schluessel)
			return True

		def loeschen(self, schluessel):
			self.datei_geloescht.append(schluessel)
			return self.dateien.pop(schluessel, None) is not None

	ablage = Doppel()
	cloud._leere_ordner_entfernen(ablage)
	assert ablage.ordner_geloescht == ["sicherungen/2020-01-01_030000"]
	# Der gefuellte Ordner bleibt unberuehrt, keine Datei wird geloescht.
	assert ablage.datei_geloescht == []
	assert "sicherungen/2026-11-18_030000/db.dump" in ablage.dateien


def test_leere_ordner_entfernen_laesst_gefuellte_ordner_stehen(backup_heim,
                                                               nextcloud_aktiv, fake):
	"""Keine Verwechslung: ein Ordner MIT Dateien bleibt unberuehrt."""
	ablage = nextcloud_aktiv
	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000")
	cloud.hochladen(ordner, ablage=ablage)

	cloud._leere_ordner_entfernen(ablage)
	assert len(ablage.auflisten("sicherungen/2026-11-18_030000")) == 4


# ── 6. Kein leerer roter Hinweis ───────────────────────────────────────────

def test_nicht_erreichbare_nextcloud_hat_immer_einen_hinweis(
	client, set_user, backup_heim, nextcloud_aktiv, fake,
):
	"""Punkt 6: ``benutzbar=False`` bedeutet in der Oberflaeche einen ROTEN Kasten."""
	from diakronos_app import db

	with db.SessionLocal() as sess:
		_system_manager(sess)
	fake.zeitueberschreitung = True

	set_user("chef")
	inhalt = client.get("/api/method/sicherung_get").json()
	inhalt = inhalt.get("message", inhalt)
	ablage = inhalt["ablage"]
	assert ablage["benutzbar"] is False
	assert ablage["hinweis"].strip(), "leerer roter Hinweis"
	assert "nicht erreichbar" in ablage["hinweis"]
	assert "lokal" in ablage["hinweis"].lower()


def test_unbrauchbares_ziel_behaelt_seinen_eigenen_hinweis(backup_heim, monkeypatch,
                                                           nextcloud_aktiv, fake):
	"""Steht schon ein Satz da (Ziel unbrauchbar), wird er NICHT ersetzt."""
	from diakronos_app.sicherung import lauf as modul

	def platzt(*_args, **_kwargs):
		raise dump.SicherungFehler("Der Ablageort der Sicherungen liegt im "
		                           "Programmverzeichnis.")

	monkeypatch.setattr(dump, "pruefe_ziel", platzt)
	fake.zeitueberschreitung = True
	status = modul.status_fuer_oberflaeche(None)
	assert status["benutzbar"] is False
	assert "Programmverzeichnis" in status["hinweis"]
	assert "nicht erreichbar" not in status["hinweis"]
