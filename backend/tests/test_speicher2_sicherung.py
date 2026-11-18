"""SPEICHER-2 — Datensicherungen im Nextcloud-Betrieb auf der Nextcloud.

Die Karte verlangt fuenf Zusagen; sie stehen hier in dieser Reihenfolge:

1. **Der Upload ist erst fertig, wenn er wirklich fertig ist.**
   Groesse im Ziel wird geprueft, Pruefsumme im Ziel nachgerechnet; ein
   abgeschnittenerUpload ist ein Fehlschlag des Laufs (``fehlgeschlagen``,
   lokale Kopie bleibt, System Manager werden benachrichtigt).
2. **Blockweise, nicht im Speicher.** Der Nachweis zaehlt die Bytes, die beim
   ersten Schreibblock schon uebertragen sind — und dass ein Dump deutlich
   groesser als ``MAX_ZWISCHENPUFFER`` NICHT abgelehnt wird (vorher haette
   ``schreiben(IO)`` ab 200 MB abgebrochen).
3. **Lokal bleibt nur die juengste Kopie**; die Aufbewahrung (Frist +
   „neueste nie loeschen“) gilt fuer die Nextcloud-Seite.
4. **``sicherung_get`` listet aus der Nextcloud, ``sicherung_loeschen``
   wirkt dort**; kein Pfad, keine Adresse, kein Download in der Antwort.
5. **Wiederherstellung**: die Sicherung laesst sich aus der Nextcloud zuerst
   lokal holen (``sicherung.wiederherstellen``), mit Pruefsummen-Gegenprobe.

KEIN Netz, kein echter Nextcloud-Server: die Ablage ist entweder die echte
``Nextcloud``-Klasse an einem ``httpx.MockTransport`` (``FakeWebDAV`` aus
``test_speicher1_vertrag``) oder eine ``GedaechtnisAblage`` mit denselben
Eigenschaften wie ``Nextcloud`` (kein ``pfad()``).
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from diakronos_app.sicherung import aufbewahrung, cloud, dump
from diakronos_app.sicherung import einstellungen as einstellungen_modul
from diakronos_app.sicherung import lauf as lauf_modul
from diakronos_app.speicher import setze_speicher, vergiss_speicher
from diakronos_app.speicher.basis import Basis, Quelle
from diakronos_app.speicher.nextcloud import MAX_ZWISCHENPUFFER, Nextcloud, NextcloudZugang

from test_speicher1_vertrag import FakeWebDAV, URL

ZUGANG = ("diakronos", "geheim-app-passwort")
BLOCK = 256 * 1024  # ``basis.BLOCKGROESSE``


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture()
def backup_heim(monkeypatch, tmp_path):
	"""Eigener Datenbaum: ``files`` und ``sicherungen`` liegen darunter."""
	import diakronos_app.settings as settings_modul

	heim = tmp_path / "data"
	(heim / "files").mkdir(parents=True)
	# ``dump.settings`` IST ``settings_modul.settings`` (dasselbe Objekt) —
	# ein zweites ``setattr`` auf ``dump.settings`` wuerde beim Zuruecksetzen
	# die gerade gesetzten Werte ueberschreiben. Deshalb genau einmal.
	monkeypatch.setattr(settings_modul.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(settings_modul.settings, "backup_dir", str(heim / "sicherungen"))
	return heim


@pytest.fixture()
def fake_dump(monkeypatch, backup_heim):
	"""``pg_dump``/Archiv durch kleine Dateien ersetzen (kein PG in der Suite)."""
	monkeypatch.setattr(dump, "schreibe_dump", _fake_dump)
	monkeypatch.setattr(dump, "schreibe_dateiarchiv", _fake_archiv)


def _fake_dump(ziel: Path, *, timeout: int | None = None) -> None:
	ziel.parent.mkdir(parents=True, exist_ok=True)
	ziel.write_bytes(b"PGDMP-fake-" + ziel.name.encode())
	os.chmod(ziel, dump.DATEI_MODUS)


def _fake_archiv(ziel: Path, quelle: Path | None = None) -> None:
	ziel.write_bytes(b"archiv")
	os.chmod(ziel, dump.DATEI_MODUS)


@pytest.fixture()
def redis_stub_fuer_sperre(monkeypatch):
	from redis_stub import StubRedis

	stub = StubRedis()
	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: stub)
	return stub


@pytest.fixture()
def fake() -> FakeWebDAV:
	return FakeWebDAV()


def _nextcloud(fake: FakeWebDAV, *, versuche: int = 1) -> Nextcloud:
	zugang = NextcloudZugang(URL, *ZUGANG, "/Diakronos",
	                         timeout=5.0, transfer_timeout=5.0, versuche=versuche)
	client = httpx.Client(transport=httpx.MockTransport(fake), auth=ZUGANG,
	                      trust_env=False)
	ablage = Nextcloud(zugang, client=client)
	ablage.wartezeiten = tuple(0.0 for _ in range(5))
	return ablage


@pytest.fixture()
def nextcloud_aktiv(fake):
	"""Die Ablage fest auf den Fake-Nextcloud stellen (kein Netz!)."""
	ablage = _nextcloud(fake)
	setze_speicher(ablage)
	try:
		yield ablage
	finally:
		vergiss_speicher()


def test_nextcloud_ablage_benutzt_denselben_fake(fake):
	"""Der Fake ist der aus SPEICHER-1 (eine Wahrheit fuer WebDAV)."""
	ablage = _nextcloud(fake)
	ablage.schreiben("probe.txt", b"hallo")
	assert ablage.lesen("probe.txt") == b"hallo"
	assert ("PUT", "/remote.php/dav/files/diakronos/Diakronos/probe.txt") in fake.anfragen


# ── 1. Upload: erst fertig, wenn fertig ────────────────────────────────────

def _sicherung_anlegen(basis: Path, name: str, *, inhalt: bytes = b"dump") -> Path:
	ordner = basis / name
	ordner.mkdir(parents=True)
	(ordner / dump.DUMP_NAME).write_bytes(inhalt)
	(ordner / dump.ARCHIV_NAME).write_bytes(b"archiv")
	dump.schreibe_pruefsummen(ordner)
	(ordner / dump.FERTIG_NAME).write_bytes(b"")
	return ordner


def test_hochladen_legt_alle_dateien_in_den_eigenen_ordner(tmp_path, fake):
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000")
	ergebnis = cloud.hochladen(ordner, ablage=ablage)

	assert ergebnis.ok, ergebnis.meldung
	assert ergebnis.dateien == 4, "db.dump, files.tar.gz, SHA256SUMS, FERTIG"
	assert ergebnis.bytes == dump.verzeichnisgroesse(ordner)
	assert sorted(ablage.auflisten("sicherungen")) == [
		"sicherungen/2026-11-18_030000/FERTIG",
		"sicherungen/2026-11-18_030000/SHA256SUMS",
		"sicherungen/2026-11-18_030000/db.dump",
		"sicherungen/2026-11-18_030000/files.tar.gz",
	]
	# Byte-gleich: derselbe Dump, keine Umkodierung.
	assert ablage.lesen("sicherungen/2026-11-18_030000/db.dump") == b"dump"


def test_fertig_markierung_wird_zulettzt_hochgeladen(tmp_path, fake):
	"""Bricht der Upload ab, liegt in der Nextcloud KEINE vollstaendige Sicherung."""
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000")
	# Der PUT auf eine Datei scheitert — der letzte Eintrag ist ``FERTIG``.
	fake.antworten.extend(("PUT", 403) for _ in range(4))
	ergebnis = cloud.hochladen(ordner, ablage=ablage)

	assert ergebnis.ok is False
	assert ergebnis.fehler
	vorhanden = ablage.auflisten("sicherungen")
	assert "sicherungen/2026-11-18_030000/FERTIG" not in vorhanden
	assert "sicherungen/2026-11-18_030000/db.dump" not in vorhanden


def test_unvollstaendiger_upload_wird_erkannt(tmp_path, fake):
	"""Groesse im Ziel stimmt nicht -> Fehlschlag, auch wenn der PUT „ok“ war."""
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000")

	class Kurz(Nextcloud):
		def groesse(self, schluessel):  # noqa: D401 — Test-Doppel
			ist = super().groesse(schluessel)
			return None if ist is None else max(0, ist - 1)

	setze_speicher(Kurz(ablage.zugang, client=ablage._client))
	try:
		ergebnis = cloud.hochladen(ordner)
	finally:
		vergiss_speicher()
	assert ergebnis.ok is False
	assert any("unvollstaendig" in text for text in ergebnis.fehler), ergebnis.fehler


def test_verfaelschter_dump_wird_an_der_pruefsumme_erkannt(tmp_path, fake):
	"""Gleiche Groesse, anderer Inhalt: nur die Pruefsumme im Ziel faellt auf."""
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000")

	class Verdreher(Nextcloud):
		def schreiben(self, schluessel, daten):
			geschrieben = super().schreiben(schluessel, daten)
			if str(schluessel).endswith("db.dump"):
				# Gleich viele Bytes, ein Zeichen anders — Groesse bleibt gleich.
				echt = self.lesen(schluessel)
				super().schreiben(schluessel, b"X" + echt[1:])
			return geschrieben

	ergebnis = cloud.hochladen(ordner, ablage=Verdreher(
		ablage.zugang, client=ablage._client))
	assert ergebnis.ok is False
	assert any("Pruefsumme" in text for text in ergebnis.fehler), ergebnis.fehler


def test_lokal_modus_schickt_nichts_weg(backup_heim):
	"""Ohne Nextcloud ist der Upload still — kein Fehler, nichts zu tun."""
	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000")
	ergebnis = cloud.hochladen(ordner)
	assert ergebnis.aktiv is False
	assert ergebnis.ok is False, "nicht aktiv ist kein Erfolg"
	assert ergebnis.fehlgeschlagen is False, "…aber auch kein Fehlschlag"


# ── 2. Blockweise uebertragen, nicht im Speicher ────────────────────────────

class ZaehlStrom(httpx.SyncByteStream):
	"""Antwortkoerper, der mitzaehlt, wie viel der Abnehmer geholt hat."""

	def __init__(self, daten: bytes, block: int = BLOCK) -> None:
		self.daten = daten
		self.block = block
		self.geholt = 0

	def __iter__(self):
		for anfang in range(0, len(self.daten), self.block):
			stueck = self.daten[anfang:anfang + self.block]
			self.geholt += len(stueck)
			yield stueck


def test_pruefsumme_im_ziel_wird_blockweise_gelesen(tmp_path, fake):
	"""Die Gegenprobe liest stroemend — kein ``ganz()`` auf einem grossen Dump."""
	gross = b"x" * (BLOCK * 3 + 17)
	ablage = _nextcloud(fake)
	ablage.schreiben("sicherungen/2026-11-18_030000/db.dump", gross)
	summe = cloud._summe_in_der_ablage(ablage, "sicherungen/2026-11-18_030000/db.dump")
	assert summe == hashlib.sha256(gross).hexdigest()


def test_grosser_dump_wird_gestreamt_nicht_abgelehnt(tmp_path, fake):
	"""Ueber ``MAX_ZWISCHENPUFFER``: die Datei geht als Strom zum Transport.

	Review-Befund 2: der alte Test war ein Quelltext-Grep. Hier wird eine
	sparse Datei von ``MAX_ZWISCHENPUFFER + 1 Byte`` geschrieben (auf der
	Platte kostet sie nichts) und der Weg der Bytes beobachtet:

	* ``Content-Length`` steht (sonst chunked, das manche Server ablehnen),
	* die Quelle wird in ``BLOCKGROESSE``-Stuecken gelesen — nie am Stueck
	  (kein ``read()`` ohne Groesse, kein ``bytes(…)`` des Ganzen),
	* gelesen wird erst WAEHREND des Sendens: vor dem ersten Zugriff auf die
	  Quelle ist noch nichts von ihr abgeholt,
	* am Ziel kommt die volle Laenge an.

	``MockTransport`` liest den Anfragekoerper vor dem Handler komplett ein
	(``request.read()``) — deshalb wird hier die QUELLE gemessen und nicht
	der Transport; das ist genau die Stelle, an der frueher der ``bytearray``
	gefuellt wurde.
	"""
	from diakronos_app.speicher import nextcloud as modul

	assert MAX_ZWISCHENPUFFER == 200 * 1024 * 1024
	ablage = _nextcloud(fake)
	ordner = tmp_path / "2026-11-18_030000"
	ordner.mkdir()
	dump_datei = ordner / dump.DUMP_NAME
	# Sparse: 200 MB + 1 Byte, ohne sie zu materialisieren.
	with open(dump_datei, "wb") as datei:
		datei.truncate(MAX_ZWISCHENPUFFER + 1)
	kopf_gesehen: dict[str, str] = {}

	class ZaehlendeDatei:
		"""Eine Datei, die jede Leseanforderung mitschreibt."""

		def __init__(self, pfad: Path) -> None:
			self._datei = open(pfad, "rb")
			self.angefordert: list[int] = []

		def read(self, anzahl: int = -1) -> bytes:
			self.angefordert.append(anzahl)
			return self._datei.read(anzahl)

		def seek(self, *args) -> int:
			return self._datei.seek(*args)

		def tell(self) -> int:
			return self._datei.tell()

		def fileno(self) -> int:
			return self._datei.fileno()

		def close(self) -> None:
			self._datei.close()

	quelle = ZaehlendeDatei(dump_datei)

	class MerkenderFake(FakeWebDAV):
		def __call__(self, request: httpx.Request) -> httpx.Response:
			if request.method == "PUT":
				kopf_gesehen.update(dict(request.headers))
				# Beim Senden ist noch NICHTS (oder nur ein Block) gelesen.
				gesehen.append(len(quelle.angefordert))
			return super().__call__(request)

	gesehen: list[int] = []
	gross = MerkenderFake()
	ablage = _nextcloud(gross)
	try:
		geschrieben = ablage.schreiben(
			"sicherungen/2026-11-18_030000/db.dump", quelle,
		)
	finally:
		quelle.close()

	assert geschrieben == MAX_ZWISCHENPUFFER + 1
	assert ablage.groesse("sicherungen/2026-11-18_030000/db.dump") == MAX_ZWISCHENPUFFER + 1
	assert kopf_gesehen.get("content-length") == str(MAX_ZWISCHENPUFFER + 1)
	# Kein ``read()`` ohne Groesse: die Datei wurde nie am Stueck eingelesen.
	assert quelle.angefordert, "die Quelle wurde nicht gelesen"
	assert all(anzahl and anzahl > 0 for anzahl in quelle.angefordert)
	assert max(quelle.angefordert) <= modul.BLOCKGROESSE
	# 200 MB / 256 KiB sind 800 Lesevorgaenge — also wirklich blockweise.
	assert len(quelle.angefordert) >= 800, len(quelle.angefordert)
	# Der Speicherbedarf bleibt EIN Block: das groesste gelesene Stueck.
	assert max(quelle.angefordert) < MAX_ZWISCHENPUFFER


def test_schreiben_einer_datei_streamt_durch(tmp_path, fake):
	"""Eine Datei (IO) geht als Strom zum Transport, nicht als ein Riesenbytes."""
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000",
	                           inhalt=b"d" * (BLOCK * 2 + 5))
	ergebnis = cloud.hochladen(ordner, ablage=ablage)
	assert ergebnis.ok, ergebnis.meldung
	assert ablage.groesse("sicherungen/2026-11-18_030000/db.dump") == BLOCK * 2 + 5


def test_wiederholung_nach_500_setzt_den_strom_zurueck(tmp_path, fake):
	"""Ein 5xx mitten im Upload: der zweite Versuch beginnt am DATEIANFANG.

	Ohne ``seek(0)`` schickte die Wiederholung nur die Reste — die Datei im
	Ziel waere kuerzer (oder leer) und die Groessenpruefung schluege zu.
	"""
	ablage = _nextcloud(fake, versuche=2)
	inhalt = b"r" * (BLOCK + 7)
	datei = tmp_path / "gross.dump"
	datei.write_bytes(inhalt)
	fake.antworten.append(("PUT", 500))
	geschrieben = ablage.schreiben("sicherungen/2026-11-18_030000/db.dump",
	                               open(datei, "rb"))
	assert geschrieben == len(inhalt)
	assert ablage.lesen("sicherungen/2026-11-18_030000/db.dump") == inhalt


# ── 3. Lauf: Upload, Status, Aufbewahrung ──────────────────────────────────

def _prepare_db(patched_db, jetzt: datetime, *, tage: int | None = None):
	sess = patched_db()
	zeile = einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
	if tage is not None:
		zeile.aufbewahrung_tage = tage
		sess.commit()
	return sess


def test_lauf_legt_die_sicherung_in_die_nextcloud(patched_db, backup_heim, fake_dump,
                                                  redis_stub_fuer_sperre,
                                                  nextcloud_aktiv):
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	sess = _prepare_db(patched_db, jetzt)
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
			aufraeumen=False,
		)
		assert ergebnis.ok is True, ergebnis.meldung
		assert "Nextcloud" in ergebnis.meldung
		dateien = nextcloud_aktiv.auflisten("sicherungen")
		assert f"sicherungen/{ergebnis.name}/{dump.DUMP_NAME}" in dateien
		assert f"sicherungen/{ergebnis.name}/{dump.FERTIG_NAME}" in dateien
		# Lokal liegt die juengste Kopie weiterhin (schnelle Wiederherstellung).
		assert (backup_heim / "sicherungen" / ergebnis.name / dump.FERTIG_NAME).is_file()
		zeile = sess.get(Sicherungslauf, ergebnis.name)
		assert zeile.status == STATUS_OK
	finally:
		sess.close()


def test_fehlgeschlagener_upload_ist_fehlschlag_und_meldet(patched_db, backup_heim,
                                                           fake_dump,
                                                           redis_stub_fuer_sperre,
                                                           nextcloud_aktiv, fake):
	from diakronos_app.models.core import HasRole, User
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	sess = _prepare_db(patched_db, jetzt)
	sess.add(User(name="chef", email="chef@example.org", full_name="Chef", enabled=True))
	sess.add(HasRole(name="HR-chef", parent="chef", role="System Manager",
	                 parenttype="User", parentfield="roles", docstatus=0, idx=0))
	sess.commit()
	# „Speicher voll“ (507): endgueltig, keine Wiederholung.
	fake.speicher_voll = True
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
			aufraeumen=False,
		)
		assert ergebnis.ok is False
		assert "nur lokal" in ergebnis.meldung
		zeile = sess.get(Sicherungslauf, ergebnis.name)
		assert zeile.status == STATUS_FEHLGESCHLAGEN
		assert "Nextcloud" in (zeile.meldung or "")
		# Die lokale Kopie BLEIBT (sonst waere die Sicherung weg).
		lokal = backup_heim / "sicherungen" / ergebnis.name
		assert (lokal / dump.FERTIG_NAME).is_file()
		assert sess.get(Sicherungslauf, ergebnis.name).benachrichtigt == "chef"
	finally:
		sess.close()


@pytest.mark.parametrize("tage,alter,bleibt", [(30, 40, False), (30, 29, True)])
def test_aufbewahrung_gilt_fuer_die_nextcloud_seite(patched_db, backup_heim, fake_dump,
                                                    redis_stub_fuer_sperre,
                                                    nextcloud_aktiv, tage, alter, bleibt):
	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	alt = jetzt - timedelta(days=alter)
	alt_name = alt.strftime("%Y-%m-%d_%H%M%S")
	ordner = _sicherung_anlegen(backup_heim / "sicherungen", alt_name)
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)

	sess = _prepare_db(patched_db, jetzt, tage=tage)
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
		)
		assert ergebnis.ok is True, ergebnis.meldung
		vorhanden = [name for name, _, _, _ in cloud.sicherungen_auflisten(nextcloud_aktiv)]
		assert ergebnis.name in vorhanden, "die neue Sicherung ist immer da"
		assert (alt_name in vorhanden) is bleibt
		if not bleibt:
			assert alt_name in ergebnis.entfernt
	finally:
		sess.close()


def test_lokal_bleibt_nur_die_juengste_kopie(patched_db, backup_heim, fake_dump,
                                             redis_stub_fuer_sperre, nextcloud_aktiv):
	"""Nach dem Upload werden die aelteren LOKALEN Kopien entfernt.

	Die aeltere Kopie liegt AUCH in der Nextcloud (sie wurde dort erfolgreich
	hochgeladen) — nur dann ist ihr Loeschen vertretbar. Eine lokale Kopie,
	deren Upload nie verifiziert wurde, bleibt stehen (Review-Befund 6, siehe
	``test_fehlgeschlagener_upload_loescht_keine_alte_lokale_kopie``).
	"""
	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	alt = _sicherung_anlegen(basis, "2026-11-18_020000")
	assert cloud.hochladen(alt, ablage=nextcloud_aktiv).ok

	sess = _prepare_db(patched_db, jetzt, tage=365)
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
		)
		assert ergebnis.ok is True, ergebnis.meldung
		assert not alt.exists(), "aeltere lokale Kopie muss weg sein"
		assert (basis / ergebnis.name).is_dir(), "die juengste bleibt lokal"
		# …und ist in der Nextcloud vorhanden.
		vorhanden = [name for name, _, _, _ in cloud.sicherungen_auflisten(nextcloud_aktiv)]
		assert set(vorhanden) == {ergebnis.name, "2026-11-18_020000"}
	finally:
		sess.close()


def test_fehlgeschlagener_upload_loescht_keine_alte_lokale_kopie(patched_db,
                                                                 backup_heim,
                                                                 fake_dump,
                                                                 redis_stub_fuer_sperre,
                                                                 nextcloud_aktiv, fake):
	"""Review-Befund 6: lokal wird NICHTS geloescht, was nicht verifiziert ist.

	Ein frueherer Lauf konnte nicht hochladen — seine lokale Kopie ist die
	einzige. Ein spaeterer erfolgreicher Lauf darf sie deshalb nicht
	mitnehmen, auch wenn sie nicht die juengste ist.
	"""
	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	# Diese Kopie kam nie in die Nextcloud (Upload verweigert).
	unhochgeladen = _sicherung_anlegen(basis, "2026-11-18_010000")
	fake.speicher_voll = True
	assert cloud.hochladen(unhochgeladen, ablage=nextcloud_aktiv).ok is False
	fake.speicher_voll = False

	sess = _prepare_db(patched_db, jetzt, tage=365)
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
		)
		assert ergebnis.ok is True, ergebnis.meldung
	finally:
		sess.close()
	assert unhochgeladen.is_dir(), (
		"die lokale Kopie ohne Upload in der Nextcloud ist die einzige — "
		"sie darf nicht geloescht werden"
	)


def test_aufbewahrung_schuetzt_die_neueste_auch_wenn_sie_alt_ist(patched_db,
                                                                 backup_heim,
                                                                 nextcloud_aktiv):
	"""Nach langer Pause: die LETZTE Kopie darf die Frist nicht wegloeschen."""
	ablage = nextcloud_aktiv
	alt = _sicherung_anlegen(backup_heim / "sicherungen", "2026-01-01_030000")
	cloud.hochladen(alt, ablage=ablage)
	entfernt = cloud.aufraeumen(
		jetzt=datetime(2026, 11, 18, 3, 0, 0), aufbewahrung_tage=30, ablage=ablage,
	)
	assert entfernt == []
	assert [name for name, _, _, _ in cloud.sicherungen_auflisten(ablage)] == [
		"2026-01-01_030000"
	]


def test_aufbewahrung_mit_ungueltigem_wert_loescht_nichts(backup_heim, nextcloud_aktiv):
	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2020-01-01_030000")
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)
	assert cloud.aufraeumen(
		jetzt=datetime(2026, 11, 18), aufbewahrung_tage=0, ablage=nextcloud_aktiv,
	) == []


def test_nextcloud_lauf_raeumt_lokale_temporaere_reste(patched_db, backup_heim,
                                                       fake_dump,
                                                       redis_stub_fuer_sperre,
                                                       nextcloud_aktiv):
	"""Teil-Dumps abgestuerzter Laeufe bleiben lokal — auch bei Nextcloud."""
	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	rest = basis / f"{dump.TEMP_PRAEFIX}verwaist"
	rest.mkdir(parents=True)
	(rest / dump.DUMP_NAME).write_bytes(b"teil-dump")
	alt = (jetzt - timedelta(hours=2)).timestamp()
	os.utime(rest, (alt, alt))

	sess = _prepare_db(patched_db, jetzt)
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
		)
		assert ergebnis.ok is True, ergebnis.meldung
	finally:
		sess.close()
	assert not rest.exists(), "verwaister Teil-Dump muss auch hier weg sein"


def test_zu_alt_haelt_die_neueste_und_ignoriert_fremde_namen():
	# Nur fremde Namen: nichts zu loeschen.
	assert cloud.zu_alt(["keine-sicherung"], jetzt=datetime(2026, 11, 18),
	                    aufbewahrung_tage=30) == []
	# Die juengste bleibt IMMER (auch wenn sie alt ist); aeltere fallen weg.
	namen = ["2026-01-01_030000", "2020-01-01_030000", "keine-sicherung"]
	assert cloud.zu_alt(namen, jetzt=datetime(2026, 11, 18),
	                    aufbewahrung_tage=30) == ["2020-01-01_030000"]
	# Kommt eine frische Sicherung dazu, faellt die alte weg — die neue bleibt.
	namen.append("2026-11-17_030000")
	assert cloud.zu_alt(namen, jetzt=datetime(2026, 11, 18),
	                    aufbewahrung_tage=30) == [
		"2020-01-01_030000", "2026-01-01_030000"
	]


# ── 3b. Nachbesserungen aus dem Review ─────────────────────────────────────

def test_fertig_wird_nach_einem_fehler_nicht_hochgeladen(tmp_path, fake):
	"""Review-Befund 3: beim ersten Fehler ist Schluss — auch ohne ``FERTIG``.

	Vorher lief die Schleife mit ``continue`` weiter und lud am Ende die
	``FERTIG``-Markierung. In der Nextcloud stand dann eine „vollstaendige“
	Sicherung, in der eine Datei (oder eine Pruefsumme) fehlte.
	"""
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000")
	# Der zweite PUT scheitert (nach ``db.dump``) — ``FERTIG`` ist der letzte.
	fake.antworten.append(("PUT", 403))
	ergebnis = cloud.hochladen(ordner, ablage=ablage)

	assert ergebnis.ok is False
	vorhanden = ablage.auflisten("sicherungen/2026-11-18_030000")
	assert "sicherungen/2026-11-18_030000/FERTIG" not in vorhanden
	assert ablage.auflisten("sicherungen/2026-11-18_030000/SHA256SUMS") == [], (
		"nach dem Fehler wurde weiter hochgeladen"
	)
	# Der Ordner dort gilt als unvollstaendig (keine "neueste Sicherung").
	assert cloud.ist_vollstaendig(ablage, "2026-11-18_030000") is False


def test_pruefsummen_lesefehler_ist_ein_fehlschlag(tmp_path, fake):
	"""Review-Befund 7: unlesbare Pruefsumme heisst NICHT „alles in Ordnung“."""
	ablage = _nextcloud(fake)
	ordner = _sicherung_anlegen(tmp_path, "2026-11-18_030000")

	class NichtLesbar(Nextcloud):
		def oeffnen(self, schluessel):
			if str(schluessel).endswith("db.dump"):
				raise RuntimeError("kaputt")
			return super().oeffnen(schluessel)

	ergebnis = cloud.hochladen(ordner, ablage=NichtLesbar(
		ablage.zugang, client=ablage._client))
	assert ergebnis.ok is False
	assert any("Pruefsumme nicht pruefbar" in text for text in ergebnis.fehler), ergebnis.fehler


def test_unvollstaendige_sicherung_ist_nicht_die_neueste(backup_heim, nextcloud_aktiv):
	"""Review-Befund 5: ein Rest ohne ``FERTIG`` schuetzt die letzte Kopie nicht.

	Aufbau: eine uralte ECHTE Sicherung (vollstaendig) und ein juengerer Rest
	aus einem abgebrochenen Upload. Ueberfristig sind beide. Frueher galt der
	Rest als „neueste“ — dann waere die letzte echte Kopie geloescht worden
	und nur der Rest geblieben.
	"""
	ablage = nextcloud_aktiv
	echt = _sicherung_anlegen(backup_heim / "sicherungen", "2020-01-01_030000")
	assert cloud.hochladen(echt, ablage=ablage).ok
	# Juengerer Ordner aus einem abgebrochenen Upload: eine Datei, kein FERTIG.
	ablage.schreiben("sicherungen/2020-06-01_030000/db.dump", b"halb")

	assert cloud.ist_vollstaendig(ablage, "2020-06-01_030000") is False
	assert cloud.ist_vollstaendig(ablage, "2020-01-01_030000") is True
	entfernt = cloud.aufraeumen(
		jetzt=datetime(2026, 11, 18, 3, 0, 0), aufbewahrung_tage=30, ablage=ablage,
	)
	# Der Rest faellt weg, die uralte ECHTE bleibt (neueste vollstaendige).
	assert "2020-06-01_030000" in entfernt
	assert "2020-01-01_030000" not in entfernt
	assert [name for name, _, _, _ in cloud.sicherungen_auflisten(ablage)] == [
		"2020-01-01_030000"
	]


def test_aufraeumen_entfernt_leere_ordner(backup_heim, nextcloud_aktiv):
	"""Review-Befund 7: nach halbem Loeschen bleibt kein leerer Ordner stehen."""
	ablage = nextcloud_aktiv
	ablage._ordner_anlegen("sicherungen/2020-01-01_030000")
	cloud.aufraeumen(jetzt=datetime(2026, 11, 18), aufbewahrung_tage=30, ablage=ablage)
	assert ablage.auflisten("sicherungen/2020-01-01_030000") == []


def test_loeschen_eines_unbekannten_namens_ist_kein_fehler(nextcloud_aktiv):
	"""Review-Befund 7: Zeile ohne Ordner -> Loeschen ist trotzdem erfolgreich."""
	assert cloud.loeschen("2020-01-01_000000", ablage=nextcloud_aktiv) is True


def test_sperre_haelt_ueber_die_uebertragung(patched_db, backup_heim, fake_dump,
                                             redis_stub_fuer_sperre, nextcloud_aktiv):
	"""Review-Befund 6: die Sperre deckt Dump UND Uebertragung ab."""
	from diakronos_app.sicherung import sperre as sperre_modul

	# Eine 1-GB-Sicherung als Bestand: der naechste Upload braucht Zeit.
	gross = backup_heim / "sicherungen" / "2026-11-17_030000"
	gross.mkdir(parents=True)
	with open(gross / dump.DUMP_NAME, "wb") as datei:
		datei.truncate(1024 * 1024 * 1024)
	(gross / dump.PRUEFSUMMEN_NAME).write_text("", encoding="utf-8")
	(gross / dump.FERTIG_NAME).write_bytes(b"")

	gesehen: list[int] = []
	echte_klasse = sperre_modul.Sicherungssperre

	class Mitschreibend(echte_klasse):  # type: ignore[misc,valid-type]
		def __init__(self, *, ttl_sekunden: int) -> None:
			gesehen.append(int(ttl_sekunden))
			super().__init__(ttl_sekunden=ttl_sekunden)

	import diakronos_app.sicherung.lauf as lauf_modul

	original = lauf_modul.Sicherungssperre
	lauf_modul.Sicherungssperre = Mitschreibend
	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	sess = _prepare_db(patched_db, jetzt)
	try:
		lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH, jetzt=jetzt, sitzung=sess,
			aufraeumen=False,
		)
	finally:
		lauf_modul.Sicherungssperre = original
		sess.close()
	# Timeout (1800) + 300 waren das alte Mass (2100). 1 GB bei 10 Mbit/s
	# sind rund 859 s — die Sperre muss deutlich darueber liegen.
	assert gesehen and gesehen[0] >= 1800 + 800, gesehen


# ── 4. Oberflaeche: Liste aus der Nextcloud, Loeschen wirkt dort ───────────

def _system_manager(sess, name: str = "chef") -> None:
	from diakronos_app.models.core import HasRole, User

	if sess.get(User, name) is None:
		sess.add(User(name=name, email=f"{name}@example.org", full_name=name,
		              enabled=True))
		sess.add(HasRole(name=f"HR-{name}", parent=name, role="System Manager",
		                 parenttype="User", parentfield="roles", docstatus=0, idx=0))
		sess.commit()


def test_sicherung_get_listet_aus_der_nextcloud(client, set_user, backup_heim,
                                                nextcloud_aktiv):
	from diakronos_app import db

	with db.SessionLocal() as sess:
		_system_manager(sess)
	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000",
	                            inhalt=b"d" * 100)
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)

	set_user("chef")
	antwort = client.get("/api/method/sicherung_get")
	assert antwort.status_code == 200, antwort.text
	daten = antwort.json()
	inhalt = daten.get("message", daten)
	namen = [eintrag["name"] for eintrag in inhalt["sicherungen"]]
	assert namen == ["2026-11-18_030000"]
	eintrag = inhalt["sicherungen"][0]
	assert eintrag["ort"] == "nextcloud"
	assert eintrag["groesse_bytes"] == dump.verzeichnisgroesse(ordner)
	assert eintrag["zeitpunkt"].startswith("2026-11-18T03:00")
	assert inhalt["ablage"]["ort"] == "nextcloud"
	assert inhalt["ablage"]["vorhanden"] == 1
	# Kartenvorgabe 4: kein Pfad, keine Adresse, kein Download.
	text = antwort.text
	for verboten in ("remote.php", "cloud.example.org", str(backup_heim),
	                 "/Diakronos"):
		assert verboten not in text, verboten


def test_sicherung_loeschen_wirkt_in_der_nextcloud(client, set_user, backup_heim,
                                                    nextcloud_aktiv):
	from diakronos_app import db
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	with db.SessionLocal() as sess:
		_system_manager(sess)
		for name in ("2026-11-17_030000", "2026-11-18_030000"):
			ordner = _sicherung_anlegen(backup_heim / "sicherungen", name)
			cloud.hochladen(ordner, ablage=nextcloud_aktiv)
			sess.add(Sicherungslauf(name=name, begonnen_am=datetime.strptime(
				name, "%Y-%m-%d_%H%M%S"), status=STATUS_OK))
		sess.commit()

	set_user("chef")
	antwort = client.post("/api/method/sicherung_loeschen",
	                      json={"name": "2026-11-17_030000"})
	assert antwort.status_code == 200, antwort.text
	assert nextcloud_aktiv.auflisten("sicherungen/2026-11-17_030000") == []
	assert nextcloud_aktiv.auflisten("sicherungen/2026-11-18_030000")
	# Die juengste bleibt geschuetzt.
	antwort = client.post("/api/method/sicherung_loeschen",
	                      json={"name": "2026-11-18_030000"})
	assert antwort.status_code >= 400
	assert nextcloud_aktiv.auflisten("sicherungen/2026-11-18_030000")


def test_fehlgeschlagener_lauf_erscheint_in_der_liste(client, set_user, backup_heim,
                                                      nextcloud_aktiv):
	"""Review-Befund 4: ein gescheiterter Upload bleibt in der Liste sichtbar.

	Sonst zeigte die Oberflaeche bei Nextcloud-Betrieb nur, was dort liegt —
	und ein Lauf, dessen Upload gescheitert ist, waere unsichtbar, samt der
	Meldung, warum die Sicherung fehlt.
	"""
	from diakronos_app import db
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	with db.SessionLocal() as sess:
		_system_manager(sess)
		sess.add(Sicherungslauf(
			name="2026-11-18_030000",
			begonnen_am=datetime(2026, 11, 18, 3, 0, 0),
			status=STATUS_FEHLGESCHLAGEN,
			meldung="Die Sicherung liegt nur lokal — die Uebertragung in die "
			        "Nextcloud ist nicht vollstaendig.",
		))
		sess.commit()

	set_user("chef")
	antwort = client.get("/api/method/sicherung_get")
	assert antwort.status_code == 200, antwort.text
	inhalt = antwort.json().get("message", antwort.json())
	eintraege = {eintrag["name"]: eintrag for eintrag in inhalt["sicherungen"]}
	assert "2026-11-18_030000" in eintraege, "der Fehlschlag ist unsichtbar"
	assert eintraege["2026-11-18_030000"]["status"] == STATUS_FEHLGESCHLAGEN
	assert "Nextcloud" in eintraege["2026-11-18_030000"]["meldung"]
	assert eintraege["2026-11-18_030000"]["vollstaendig"] is False


def test_nicht_erreichbare_nextcloud_sagt_das(client, set_user, backup_heim,
                                              nextcloud_aktiv, fake):
	"""Review-Befund 4: „nicht erreichbar“ ist NICHT „keine Sicherungen“."""
	from diakronos_app import db

	with db.SessionLocal() as sess:
		_system_manager(sess)
	# Jede Anfrage scheitert (Zeitueberschreitung wirkt fuer alle Methoden).
	fake.zeitueberschreitung = True

	set_user("chef")
	antwort = client.get("/api/method/sicherung_get")
	assert antwort.status_code == 200, antwort.text
	inhalt = antwort.json().get("message", antwort.json())
	assert inhalt["ablage"]["benutzbar"] is False
	assert "nicht erreichbar" in inhalt["ablage"]["hinweis_ort"]


def test_lokal_modus_listet_wie_bisher(client, set_user, backup_heim, fake_dump,
                                       redis_stub_fuer_sperre, patched_db):
	"""Ohne Nextcloud: Liste aus der Protokolltabelle, kein ``ort``-Feld."""
	from diakronos_app import db

	with db.SessionLocal() as sess:
		_system_manager(sess)
	jetzt = datetime(2026, 11, 18, 3, 0, 0)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_MANUELL, jetzt=jetzt, sitzung=sess,
			aufraeumen=False,
		)
		assert ergebnis.ok, ergebnis.meldung
	finally:
		sess.close()

	set_user("chef")
	antwort = client.get("/api/method/sicherung_get")
	inhalt = antwort.json().get("message", antwort.json())
	assert [e["name"] for e in inhalt["sicherungen"]] == [ergebnis.name]
	assert "ort" not in inhalt["sicherungen"][0]
	assert inhalt["ablage"]["ort"] == "lokal"
	# Lokal-Modus ist UNVERAENDERT (Review-Befund 1): die Sicherung liegt
	# direkt unter ``BACKUP_DIR`` — kein zusaetzlicher Unterordner.
	assert dump.ziel_basis() == backup_heim / "sicherungen"
	assert os.path.isdir(str(dump.ziel_basis() / ergebnis.name))
	assert not (backup_heim / "sicherungen" / "sicherungen").exists()


# ── 5. Wiederherstellung holt zuerst lokal ─────────────────────────────────

def test_wiederherstellen_holt_und_prueft(backup_heim, nextcloud_aktiv, monkeypatch):
	from diakronos_app.sicherung import wiederherstellen

	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000",
	                            inhalt=b"dump-inhalt")
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)
	# Lokal „vergessen“: so sieht es aus, wenn nur die Nextcloud die Kopie hat.
	aufbewahrung.entferne(ordner)
	assert not ordner.exists()

	ziel = wiederherstellen.hole_lokal("2026-11-18_030000")
	assert ziel == backup_heim / "sicherungen" / "2026-11-18_030000"
	assert (ziel / dump.DUMP_NAME).read_bytes() == b"dump-inhalt"
	assert (ziel / dump.FERTIG_NAME).is_file()
	assert dump.lese_pruefsummen(ziel)[dump.DUMP_NAME]


def test_wiederherstellen_bricht_bei_beschaedigter_datei_ab(backup_heim,
                                                            nextcloud_aktiv):
	from diakronos_app.sicherung import wiederherstellen

	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000",
	                            inhalt=b"dump-inhalt")
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)
	aufbewahrung.entferne(ordner)
	# In der Ablage ist der Dump unterwegs kaputtgegangen (gleiche Groesse).
	nextcloud_aktiv.schreiben("sicherungen/2026-11-18_030000/db.dump", b"XXXXXXXXXXX")

	with pytest.raises(wiederherstellen.WiederherstellungsFehler) as fehler:
		wiederherstellen.hole_lokal("2026-11-18_030000")
	assert "beschaedigt" in str(fehler.value)


def test_wiederherstellen_listet_und_meldet_unbekanntes(backup_heim, nextcloud_aktiv,
                                                        capsys):
	import pytest as _pytest

	from diakronos_app.sicherung import wiederherstellen

	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000")
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)
	assert wiederherstellen.main(["--liste"]) == 0
	assert "2026-11-18_030000" in capsys.readouterr().out
	assert wiederherstellen.main(["2026-11-18_030000"]) == 0
	with _pytest.raises(wiederherstellen.WiederherstellungsFehler):
		wiederherstellen.hole_lokal("2020-01-01_000000")


def test_wiederherstellen_holt_fertig_zuletzt(backup_heim, nextcloud_aktiv):
	"""Review-Befund 7: ``FERTIG`` wird ZULETZT geholt.

	Bricht das Holen ab, darf lokal kein Ordner stehen, der wie eine
	vollstaendige Sicherung aussieht.
	"""
	from diakronos_app.sicherung import wiederherstellen

	ordner = _sicherung_anlegen(backup_heim / "sicherungen", "2026-11-18_030000")
	cloud.hochladen(ordner, ablage=nextcloud_aktiv)
	aufbewahrung.entferne(ordner)

	reihenfolge: list[str] = []
	echt = wiederherstellen._hole_datei

	def mitschreiben(ablage, schluessel, ziel, summen_text):
		reihenfolge.append(ziel.name)
		return echt(ablage, schluessel, ziel, summen_text)

	original = wiederherstellen._hole_datei
	wiederherstellen._hole_datei = mitschreiben
	try:
		wiederherstellen.hole_lokal("2026-11-18_030000")
	finally:
		wiederherstellen._hole_datei = original
	assert reihenfolge[-1] == dump.FERTIG_NAME, reihenfolge


def test_wiederherstellen_im_lokal_modus_ist_ein_aufruffehler(backup_heim):
	from diakronos_app.sicherung import wiederherstellen

	with pytest.raises(wiederherstellen.WiederherstellungsFehler) as fehler:
		wiederherstellen.hole_lokal("2026-11-18_030000")
	assert "lokal" in str(fehler.value)
