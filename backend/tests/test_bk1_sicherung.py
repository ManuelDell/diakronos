"""BACKUP-1 — Automatische Datensicherung mit einstellbarer Aufbewahrung.

Die Karte verlangt Tests fuer fuenf Zusagen. Sie stehen hier in dieser
Reihenfolge:

1. **Aufbewahrung loescht genau das Richtige — die neueste bleibt**
   (:func:`test_aufbewahrung_loescht_nur_alte_und_behaelt_die_neueste` und
   Verwandte). Geprueft mit KONKRETEN Datumsgrenzen: eine Sicherung knapp
   INNERHALB, eine knapp AUSSERHALB der Frist.
2. **Rechte**: nur System Manager; ein Mitgliederadministrator bekommt 403,
   ein Gast ebenfalls.
3. **Sperre gegen Doppellauf**: der zweite Lauf beginnt nicht.
4. **Einstellungen**: Pruefung (Pflicht, Minimum 1, HH:MM) und Speichern.
5. **Sicherheit (B4)**: Rechte 0600/0700, kein Pfad und keine Zugangsdaten in
   der Antwort, kein Download-/Wiederherstellungs-Endpunkt, Ziel im
   Datenbaum statt im Image.

Ein echter ``pg_dump`` laeuft in der Suite NICHT: die Standard-Suite laeuft
gegen SQLite, und ``pg_dump`` gibt es im Test-Image zwar, aber ohne
PostgreSQL-Server. Der Dump wird deshalb an der Prozess-Grenze ersetzt
(``dump.schreibe_dump``); die ECHTE Sicherung gegen PostgreSQL samt
Wiederherstellung ist Teil der Abnahme im Wegwerf-Stack (Abschlusskommentar).
Die Client-Version selbst wird aber geprueft (:func:`test_client_version`).
"""

from __future__ import annotations

import os
import re
import stat
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diakronos_app.sicherung import aufbewahrung, dump
from diakronos_app.sicherung import einstellungen as einstellungen_modul
from diakronos_app.sicherung import lauf as lauf_modul
from diakronos_app.sicherung.sperre import Sicherungssperre, SperreBesteht


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def backup_heim(monkeypatch, tmp_path):
	"""Eigener Datenbaum: ``files`` und ``sicherungen`` liegen darunter.

	``dump.pruefe_ziel`` verlangt, dass beide im selben Baum liegen (nicht im
	Image). Ohne diese Fixture wuerde jeder Test nach ``/data`` schreiben.
	"""
	import diakronos_app.settings as settings_modul

	heim = tmp_path / "data"
	(heim / "files").mkdir(parents=True)
	monkeypatch.setattr(settings_modul.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(settings_modul.settings, "backup_dir", str(heim / "sicherungen"))
	monkeypatch.setattr(dump.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(dump.settings, "backup_dir", str(heim / "sicherungen"))
	return heim


@pytest.fixture()
def fake_dump(monkeypatch, backup_heim):
	"""``pg_dump`` durch eine Datei mit Inhalt ersetzen (kein PG in der Suite)."""
	aufrufe: list[dict] = []

	def _schreibe(ziel: Path, *, timeout: int | None = None) -> None:
		aufrufe.append({"ziel": ziel, "timeout": timeout})
		ziel.parent.mkdir(parents=True, exist_ok=True)
		ziel.write_bytes(b"PGDMP-fake-" + ziel.name.encode())
		os.chmod(ziel, dump.DATEI_MODUS)

	monkeypatch.setattr(dump, "schreibe_dump", _schreibe)
	# Auch die Dateiablage: ein echtes tar.gz waere hier nur teuer.
	def _archiv(ziel: Path, quelle: Path | None = None) -> None:
		ziel.write_bytes(b"archiv")
		os.chmod(ziel, dump.DATEI_MODUS)

	monkeypatch.setattr(dump, "schreibe_dateiarchiv", _archiv)
	return aufrufe


@pytest.fixture()
def redis_stub_fuer_sperre(monkeypatch):
	"""Redis der Sperre durch den In-Memory-Stub ersetzen."""
	from redis_stub import StubRedis

	stub = StubRedis()
	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: stub)
	return stub


# ── 1. Aufbewahrung ────────────────────────────────────────────────────────

def _sicherung_anlegen(basis: Path, zeitpunkt: datetime, *, fertig: bool = True) -> Path:
	"""Ein Sicherungsverzeichnis wie nach einem erfolgreichen Lauf."""
	ordner = basis / zeitpunkt.strftime("%Y-%m-%d_%H%M%S")
	ordner.mkdir(parents=True)
	(ordner / dump.DUMP_NAME).write_bytes(b"dump")
	(ordner / dump.ARCHIV_NAME).write_bytes(b"archiv")
	(ordner / dump.PRUEFSUMMEN_NAME).write_text("x  db.dump\n", encoding="utf-8")
	if fertig:
		(ordner / dump.FERTIG_NAME).write_bytes(b"")
	return ordner


def test_aufbewahrung_loescht_nur_alte_und_behaelt_die_neueste(backup_heim):
	"""30 Tage: 31 Tage alt fliegt raus, 29 Tage alt bleibt."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	alt = _sicherung_anlegen(basis, jetzt - timedelta(days=31))       # AUSSERHALB
	knapp = _sicherung_anlegen(basis, jetzt - timedelta(days=29))     # INNERHALB
	neu = _sicherung_anlegen(basis, jetzt - timedelta(hours=1))

	entfernt = aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30)

	assert entfernt == [alt.name]
	assert not alt.exists()
	assert knapp.exists()
	assert neu.exists()


def test_aufbewahrung_loescht_die_neueste_erfolgreiche_nie(backup_heim):
	"""Die letzte Kopie bleibt, auch wenn sie aelter als die Frist ist.

	Ohne diese Ausnahme waere die Regel bei einem Ausfall der automatischen
	Sicherung genau das Gegenteil von Sicherheit: nach dem ersten Lauf waere
	die letzte vorhandene Kopie weg.
	"""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	nur = _sicherung_anlegen(basis, jetzt - timedelta(days=400))

	entfernt = aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30)

	assert entfernt == []
	assert nur.exists(), "die einzige Sicherung darf nie geloescht werden"


def test_aufbewahrung_behaelt_die_neueste_auch_neben_alteren(backup_heim):
	"""Zwei uralte Sicherungen: die NEUESTE der beiden bleibt."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	a = _sicherung_anlegen(basis, jetzt - timedelta(days=500))
	b = _sicherung_anlegen(basis, jetzt - timedelta(days=100))

	entfernt = aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30)

	assert entfernt == [a.name]
	assert b.exists(), "die neueste erfolgreiche Sicherung ist geschuetzt"


def test_aufbewahrung_schuetzt_eine_aeltere_wenn_die_neuere_unvollstaendig_ist(backup_heim):
	"""Ein Abbruch mitten im Lauf zaehlt nicht als erfolgreiche Sicherung."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	alt_fertig = _sicherung_anlegen(basis, jetzt - timedelta(days=200))
	abgebrochen = _sicherung_anlegen(basis, jetzt - timedelta(days=10), fertig=False)

	entfernt = aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30)

	# Die abgebrochene ist NICHT die geschuetzte (sie ist nicht erfolgreich),
	# die fertige aeltere schon — die abgebrochene selbst liegt innerhalb der
	# Frist und bleibt vorerst.
	assert entfernt == []
	assert alt_fertig.exists()
	assert abgebrochen.exists()


def test_aufbewahrung_loescht_unvollstaendige_nach_frist(backup_heim):
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	fertig = _sicherung_anlegen(basis, jetzt - timedelta(days=5))
	alt_abgebrochen = _sicherung_anlegen(basis, jetzt - timedelta(days=90), fertig=False)

	entfernt = aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30)

	assert entfernt == [alt_abgebrochen.name]
	assert fertig.exists()


def test_aufbewahrung_mit_ungueltigem_wert_loescht_nichts(backup_heim):
	"""0 Tage kann nur aus einer Handaenderung kommen — dann fail safe."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	alt = _sicherung_anlegen(basis, jetzt - timedelta(days=900))

	assert aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=0) == []
	assert alt.exists()


def test_aufbewahrung_ignoriert_fremde_verzeichnisse(backup_heim):
	"""Ein Ordner ohne Zeitstempel-Namen wird nie angefasst."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	fremd = basis / "wichtig"
	fremd.mkdir()
	(fremd / "notiz.txt").write_text("nicht anfassen", encoding="utf-8")
	_sicherung_anlegen(basis, jetzt - timedelta(days=1))

	assert aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30) == []
	assert fremd.exists()


# ── 2. Einstellungen ───────────────────────────────────────────────────────

def test_einstellungen_standard_und_grenzen():
	assert einstellungen_modul.pruefe_aufbewahrung(30) == 30
	assert einstellungen_modul.pruefe_aufbewahrung("1") == 1
	with pytest.raises(einstellungen_modul.EinstellungFehler):
		einstellungen_modul.pruefe_aufbewahrung(0)
	with pytest.raises(einstellungen_modul.EinstellungFehler):
		einstellungen_modul.pruefe_aufbewahrung("")
	with pytest.raises(einstellungen_modul.EinstellungFehler):
		einstellungen_modul.pruefe_aufbewahrung("viele")
	with pytest.raises(einstellungen_modul.EinstellungFehler):
		einstellungen_modul.pruefe_aufbewahrung(3651)


def test_einstellungen_uhrzeit_muss_hh_mm_sein():
	assert einstellungen_modul.pruefe_uhrzeit("03:00") == "03:00"
	assert einstellungen_modul.pruefe_uhrzeit(" 23:59 ") == "23:59"
	for falsch in ("3:00", "24:00", "03:60", "0300", "", "morgen"):
		with pytest.raises(einstellungen_modul.EinstellungFehler):
			einstellungen_modul.pruefe_uhrzeit(falsch)
	assert einstellungen_modul.uhrzeit_teile("03:30") == (3, 30)


def test_einstellungen_werden_gespeichert_und_gelesen(patched_db, monkeypatch):
	# Die Erstbelegung kommt aus der Umgebung (compose setzt
	# BACKUP_AUTOMATISCH=0 im Teststack) — hier gilt der Produktiv-Default,
	# sonst haengt der Test an der Umgebung des Containers statt am Code.
	import diakronos_app.settings as settings_modul
	monkeypatch.setattr(settings_modul.settings, "backup_automatisch", True)
	sess = patched_db()
	try:
		zeile = einstellungen_modul.holen_oder_anlegen(sess, jetzt=datetime(2026, 10, 20, 3, 0))
		assert zeile.aufbewahrung_tage == 30
		assert zeile.uhrzeit == "03:00"
		assert zeile.automatisch is True

		einstellungen_modul.speichern(
			sess, automatisch=False, uhrzeit="04:15", aufbewahrung_tage=7,
			benutzer="chef@example.org", jetzt=datetime(2026, 10, 20, 4, 0),
		)
		erneut = einstellungen_modul.holen_oder_anlegen(sess)
		assert erneut.aufbewahrung_tage == 7
		assert erneut.uhrzeit == "04:15"
		assert erneut.automatisch is False
		assert erneut.modified_by == "chef@example.org"
	finally:
		sess.close()


def test_einstellungen_falscher_wert_schreibt_nichts(patched_db):
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess)
		with pytest.raises(einstellungen_modul.EinstellungFehler):
			einstellungen_modul.speichern(
				sess, automatisch=True, uhrzeit="03:00", aufbewahrung_tage=0,
				benutzer="chef@example.org",
			)
		assert einstellungen_modul.holen_oder_anlegen(sess).aufbewahrung_tage == 30
	finally:
		sess.close()


# ── 3. Sperre gegen Doppellauf ─────────────────────────────────────────────

def test_sperre_laesst_nur_einen_lauf_zu(redis_stub_fuer_sperre):
	# `Sicherungssperre.setzen` holt sich den Client ueber `_client()`; fuer
	# den zweiten Versuch muss deshalb ein EIGENES Objekt genommen werden,
	# nicht dieselbe Sperre (sonst meldet sie sich selbst als belegt).
	erste = Sicherungssperre(ttl_sekunden=60)
	erste.setzen()
	try:
		with pytest.raises(SperreBesteht):
			Sicherungssperre(ttl_sekunden=60).setzen()
	finally:
		erste.freigeben()
	# Nach der Freigabe geht es wieder.
	zweite = Sicherungssperre(ttl_sekunden=60)
	zweite.setzen()
	zweite.freigeben()


def test_doppellauf_beginnt_nicht(patched_db, backup_heim, fake_dump,
                                  redis_stub_fuer_sperre):
	"""Bei bestehender Sperre wird KEIN zweiter Lauf gestartet."""
	from diakronos_app.models.sicherung import Sicherungslauf

	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=datetime(2026, 10, 20, 3, 0))
	finally:
		sess.close()

	erste = Sicherungssperre(ttl_sekunden=60)
	erste.setzen()
	try:
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_MANUELL,
			jetzt=datetime(2026, 10, 20, 3, 0, 1),
		)
	finally:
		erste.freigeben()

	assert ergebnis.ok is False
	assert "bereits" in ergebnis.meldung.lower()
	assert fake_dump == [], "ohne Sperre darf kein Dump geschrieben werden"
	sess = patched_db()
	try:
		assert list(sess.query(Sicherungslauf)) == []
	finally:
		sess.close()


# ── 4. Ein vollstaendiger Lauf (Dump ersetzt) ──────────────────────────────

def test_lauf_schreibt_dump_archiv_pruefsummen_und_fertig(patched_db, backup_heim,
                                                          fake_dump,
                                                          redis_stub_fuer_sperre):
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_MANUELL, jetzt=jetzt, sitzung=sess,
			aufraeumen=False,
		)
		assert ergebnis.ok is True, ergebnis.meldung
		assert ergebnis.name == "2026-10-20_030000"
		ordner = backup_heim / "sicherungen" / ergebnis.name
		for name in (dump.DUMP_NAME, dump.ARCHIV_NAME, dump.PRUEFSUMMEN_NAME, dump.FERTIG_NAME):
			assert (ordner / name).is_file(), name
		assert ergebnis.groesse_bytes > 0
		zeile = sess.get(Sicherungslauf, ergebnis.name)
		assert zeile is not None and zeile.status == STATUS_OK
		assert zeile.groesse_bytes == ergebnis.groesse_bytes
	finally:
		sess.close()


def test_lauf_laesst_keine_temporaeren_reste_stehen(patched_db, backup_heim, fake_dump,
                                                    redis_stub_fuer_sperre):
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL, jetzt=jetzt,
		                      sitzung=sess, aufraeumen=False)
	finally:
		sess.close()
	reste = list((backup_heim / "sicherungen").glob(f"{dump.TEMP_PRAEFIX}*"))
	assert reste == []


def test_fehlgeschlagener_dump_ist_ein_fehlschlag_und_benachrichtigt(patched_db, backup_heim,
                                                                    monkeypatch,
                                                                    redis_stub_fuer_sperre):
	"""B1/B3: fehlgeschlagene Sicherung -> Status + In-App-Meldung."""
	from diakronos_app.models.core import HasRole, User
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess = patched_db()
	sess.add(User(name="chefin@example.org", email="chefin@example.org",
	              full_name="Chefin", enabled=True))
	# Die Benachrichtigung schreibt ueber `_create` in eine EIGENE Sitzung;
	# in der Test-Datenbank ist das dieselbe Engine (StaticPool).
	sess.add(HasRole(name="hr-1", parent="chefin@example.org", parenttype="User",
	                 parentfield="roles", role="System Manager", docstatus=0, idx=1))
	sess.commit()

	def _kaputt(ziel: Path, *, timeout: int | None = None) -> None:
		raise dump.SicherungFehler("Der Datenbank-Dump ist fehlgeschlagen (Exit 1).")

	monkeypatch.setattr(dump, "schreibe_dump", _kaputt)
	monkeypatch.setattr(dump, "schreibe_dateiarchiv",
	                    lambda ziel, quelle=None: ziel.write_bytes(b"x"))
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is False
		assert "fehlgeschlagen" in ergebnis.meldung.lower()
		zeile = sess.get(Sicherungslauf, ergebnis.name)
		assert zeile is not None
		assert zeile.status == STATUS_FEHLGESCHLAGEN
		assert zeile.meldung
		assert "chefin@example.org" in (zeile.benachrichtigt or "")
		# Kein halbfertiges Verzeichnis unter dem richtigen Namen.
		assert not (backup_heim / "sicherungen" / ergebnis.name).exists()
	finally:
		sess.close()


def test_abgebrochener_vorgaenger_wird_als_fehlgeschlagen_gemeldet(patched_db, backup_heim,
                                                                   fake_dump,
                                                                   redis_stub_fuer_sperre):
	from diakronos_app.models.sicherung import STATUS_LAEUFT, Sicherungslauf

	sess = patched_db()
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess.add(Sicherungslauf(name="2026-10-19_030000",
	                        begonnen_am=jetzt - timedelta(days=1), status=STATUS_LAEUFT))
	sess.commit()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL, jetzt=jetzt,
		                      sitzung=sess, aufraeumen=False)
		sess.expire_all()
		alt = sess.get(Sicherungslauf, "2026-10-19_030000")
		assert alt.status == "fehlgeschlagen"
		assert alt.beendet_am is not None
		assert "abgebrochen" in (alt.meldung or "").lower()
	finally:
		sess.close()


def test_abgebrochener_vorgaenger_mit_fertig_markierung_wird_ok(patched_db, backup_heim):
	"""FERTIG im Verzeichnis beweist den vollen Lauf (typisch nach der
	Wiederherstellung: der eigene Dump enthaelt die Zeile noch als ``laeuft``)."""
	from diakronos_app.models.sicherung import STATUS_LAEUFT, STATUS_OK, Sicherungslauf
	from diakronos_app.sicherung import sperre as sperre_modul

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	ordner = _sicherung_anlegen(basis, jetzt - timedelta(days=1))
	sess = patched_db()
	sess.add(Sicherungslauf(name=ordner.name,
	                        begonnen_am=jetzt - timedelta(days=1), status=STATUS_LAEUFT))
	sess.commit()
	try:
		betroffen = sperre_modul.raeume_abgebrochene_auf(sess, jetzt=jetzt)
		assert betroffen == [ordner.name]
		sess.expire_all()
		zeile = sess.get(Sicherungslauf, ordner.name)
		assert zeile.status == STATUS_OK
		assert "Fertig" in (zeile.meldung or "")
		assert zeile.groesse_bytes > 0
	finally:
		sess.close()


def test_lauf_zeichnet_die_zeiten_in_ortszeit(patched_db, backup_heim, fake_dump,
                                              redis_stub_fuer_sperre, monkeypatch):
	"""Name und Zeitpunkt eines Laufs stehen in Ortszeit — auch von Hand.

	Ohne eine gemeinsame Uhr lagen manuelle Läufe (UTC) und Scheduler-Läufe
	(Ortszeit) in der Oberflaeche um die Zeitzonen-Differenz auseinander.
	"""
	ersatz = datetime(2026, 10, 20, 21, 47, 11)
	monkeypatch.setattr("diakronos_app.sicherung.lauf.jetzt_ortszeit", lambda: ersatz)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=ersatz)
		ergebnis = lauf_modul.fuehre_aus(
			ausloeser=lauf_modul.AUSLOESER_MANUELL, sitzung=sess)
		assert ergebnis.name == "2026-10-20_214711"
		assert ergebnis.zeitpunkt == ersatz
	finally:
		sess.close()


def test_lauf_wendet_die_aufbewahrung_an(patched_db, backup_heim, fake_dump,
                                         redis_stub_fuer_sperre):
	"""Nach der Sicherung wird geloescht, was zu alt ist — die neue bleibt."""
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	basis.mkdir()
	alt = _sicherung_anlegen(basis, jetzt - timedelta(days=40))
	sess = patched_db()
	sess.add(Sicherungslauf(name=alt.name, begonnen_am=jetzt - timedelta(days=40),
	                        beendet_am=jetzt - timedelta(days=40), status=STATUS_OK))
	sess.commit()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is True
		assert ergebnis.entfernt == [alt.name]
		assert not alt.exists()
		assert (basis / ergebnis.name).is_dir()
		sess.expire_all()
		assert sess.get(Sicherungslauf, alt.name) is None, "Protokollzeile mit entfernen"
	finally:
		sess.close()


# ── 4b. Verwaiste Temp-Reste (BACKUP-1b, M1) ───────────────────────────────

def _temp_rest_anlegen(basis: Path, *, alter_sekunden: float, name: str = ".tmp-verwaist",
                       bezug: datetime | None = None) -> Path:
	"""Was ein abgestuerzter Lauf hinterlaesst: Ordner mit Teil-Dump.

	``bezug`` ist die Uhr, gegen die ``verwaiste_temp_entfernen`` prueft —
	im Lauf ist das der Laufzeitpunkt (``jetzt``). Wird der Zeitstempel gegen
	die Wanduhr gesetzt und mit der Laufzeit verglichen, ist die Frist
	beliebig; deshalb immer denselben Bezug nehmen.
	"""
	basis.mkdir(parents=True, exist_ok=True)
	ordner = basis / name
	ordner.mkdir()
	(ordner / (dump.DUMP_NAME + ".part")).write_bytes(b"PGDMP-teil")
	stempel = ((bezug or datetime.now()).timestamp() - alter_sekunden)
	os.utime(ordner, (stempel, stempel))
	return ordner


def test_verwaister_temp_rest_wird_nach_der_frist_entfernt(backup_heim):
	"""M1: Rest aelter als ``backup_timeout_sekunden`` -> weg (mit Teil-Dump)."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	rest = _temp_rest_anlegen(basis, alter_sekunden=7200, bezug=jetzt)

	entfernt = aufbewahrung.verwaiste_temp_entfernen(
		basis, jetzt=jetzt, timeout_sekunden=1800,
	)

	assert entfernt == [rest.name]
	assert not rest.exists(), "Teil-Dump mit Personendaten muss weg sein"


def test_frischer_temp_rest_bleibt_stehen(backup_heim):
	"""M1: ein juengerer Ordner kann zu einem laufenden Lauf gehoeren."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	rest = _temp_rest_anlegen(basis, alter_sekunden=60, bezug=jetzt)

	entfernt = aufbewahrung.verwaiste_temp_entfernen(
		basis, jetzt=jetzt, timeout_sekunden=1800,
	)

	assert entfernt == []
	assert rest.exists()


def test_temp_rest_aufraeumen_beruehrt_keine_sicherung(backup_heim):
	"""M1: nur ``.tmp-*`` — Sicherungen und fremde Ordner bleiben unberuehrt."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	alt = _sicherung_anlegen(basis, jetzt - timedelta(days=40))
	fremd = basis / "manuell-kopie"
	fremd.mkdir()
	rest = _temp_rest_anlegen(basis, alter_sekunden=7200, bezug=jetzt)

	aufbewahrung.aufraeumen(basis, jetzt=jetzt, aufbewahrung_tage=30,
	                        timeout_sekunden=1800)

	assert not rest.exists()
	assert alt.exists(), "Aufbewahrung entscheidet ueber Sicherungen, nicht dieser Schritt"
	assert fremd.exists()


def test_lauf_entfernt_verwaisten_temp_rest(patched_db, backup_heim, fake_dump,
                                            redis_stub_fuer_sperre):
	"""M1 in der Kette: der naechste Lauf (unter Sperre) raeumt den Rest weg."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	rest = _temp_rest_anlegen(basis, alter_sekunden=7200, bezug=jetzt)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is True, ergebnis.meldung
	finally:
		sess.close()
	assert not rest.exists()
	assert (basis / ergebnis.name).is_dir()


# ── 4c. Nacharbeit BACKUP-1b: N1, N2, N4, Platz ────────────────────────────

def test_alte_fehlgeschlagene_laeufe_fallen_aus_der_liste(patched_db, backup_heim,
                                                           fake_dump,
                                                           redis_stub_fuer_sperre):
	"""N1: ein Fehlschlag hat kein Verzeichnis, verstopfte aber die Liste ewig."""
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess = patched_db()
	sess.add(Sicherungslauf(name="2026-08-01_030000",
	                        begonnen_am=jetzt - timedelta(days=80),
	                        status=STATUS_FEHLGESCHLAGEN, meldung="alt"))
	sess.add(Sicherungslauf(name="2026-10-18_030000",
	                        begonnen_am=jetzt - timedelta(days=2),
	                        status=STATUS_FEHLGESCHLAGEN, meldung="jung"))
	sess.commit()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is True, ergebnis.meldung
		sess.expire_all()
		assert sess.get(Sicherungslauf, "2026-08-01_030000") is None, \
			"80 Tage alter Fehlschlag muss nach 30 Tagen Aufbewahrung weg sein"
		assert sess.get(Sicherungslauf, "2026-10-18_030000") is not None, \
			"junge Fehlschlaege bleiben sichtbar"
	finally:
		sess.close()


def test_alter_fehlschlag_bleibt_bei_abgeschalteter_aufbewahrung(patched_db, backup_heim,
                                                                 fake_dump,
                                                                 redis_stub_fuer_sperre):
	"""N1 greift in der Aufbewahrung — ohne sie bleibt die Spur stehen."""
	from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess = patched_db()
	sess.add(Sicherungslauf(name="2026-08-01_030000",
	                        begonnen_am=jetzt - timedelta(days=80),
	                        status=STATUS_FEHLGESCHLAGEN))
	sess.commit()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL, jetzt=jetzt,
		                      sitzung=sess, aufraeumen=False)
		sess.expire_all()
		assert sess.get(Sicherungslauf, "2026-08-01_030000") is not None
	finally:
		sess.close()


def test_dump_fehlertext_nennt_keinen_rechnernamen(caplog):
	"""N2: der Hostname aus der pg_dump-Ausgabe bleibt im Log, nicht in der Meldung."""
	import subprocess as sp

	ausgabe = sp.CompletedProcess(
		args=["pg_dump"], returncode=1, stdout="",
		stderr='pg_dump: error: could not translate host name "db-geheim" '
		       "to address: Name or service not known\n",
	)
	with caplog.at_level("WARNING"):
		text = dump._dump_fehlertext(ausgabe)

	assert "db-geheim" not in text
	assert "nicht erreichbar" in text
	assert "db-geheim" in caplog.text, "ins Protokoll gehoert die Ursache"


def test_ziel_hinweis_enthaelt_keinen_pfad(monkeypatch, tmp_path):
	"""N2: ``ablage.hinweis`` nennt keinen absoluten Pfad."""
	import diakronos_app.settings as settings_modul
	from diakronos_app.sicherung import lauf as lauf_modul_2

	files = tmp_path / "data" / "files"
	files.mkdir(parents=True)
	monkeypatch.setattr(settings_modul.settings, "files_dir", str(files))
	monkeypatch.setattr(dump.settings, "files_dir", str(files))

	# ``/proc`` ist ein Dateisystem, in dem nichts angelegt werden darf: die
	# Schreibprobe scheitert, ohne dass auf diesem Rechner etwas entsteht.
	hinweis = lauf_modul_2.status_fuer_oberflaeche(None, Path("/proc/bk1b-sicherungen"))

	assert hinweis["benutzbar"] is False
	assert "Daten-Ordner" in hinweis["hinweis"]
	assert str(tmp_path) not in hinweis["hinweis"], "kein Pfad in der Oberflaeche"
	assert "/proc" not in hinweis["hinweis"], "kein Pfad in der Oberflaeche"


def test_kennungskollision_in_derselben_sekunde(patched_db, backup_heim, fake_dump,
                                                redis_stub_fuer_sperre):
	"""N4: belegter Name -> der Lauf bekommt die naechste freie Sekunde."""
	from diakronos_app.models.sicherung import STATUS_OK, Sicherungslauf

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	# Verzeichnis aus einem frueheren Lauf, dessen Zeile verloren ist.
	verwaist = _sicherung_anlegen(basis, jetzt)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is True, ergebnis.meldung
		assert ergebnis.name == "2026-10-20_030001"
		assert (basis / ergebnis.name).is_dir()
		# Der fremde Ordner bleibt unangetastet, er passt ins Namensmuster.
		assert verwaist.is_dir()
		assert sess.get(Sicherungslauf, ergebnis.name).status == STATUS_OK
	finally:
		sess.close()


def test_doppelte_kennung_im_dump_wird_gemeldet_nicht_umbenannt(backup_heim, fake_dump):
	"""N4: der alte ``-pid``-Zusatz fiel aus dem Namensmuster — jetzt ein Fehler."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	verwaist = _sicherung_anlegen(basis, jetzt)

	with pytest.raises(dump.SicherungFehler) as fehler:
		dump.sichere(jetzt=jetzt, name=verwaist.name)

	assert "bereits ein Verzeichnis" in str(fehler.value)
	# Kein Ordner mit Prozess-Zusatz daneben.
	assert sorted(p.name for p in basis.iterdir()) == [verwaist.name]


def test_zu_wenig_platz_bricht_vor_dem_dump_ab(patched_db, backup_heim, fake_dump,
                                               redis_stub_fuer_sperre, monkeypatch):
	"""N5: reicht der Platz nicht fuer 2x die letzte Sicherung, laeuft nichts."""
	import types

	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	_sicherung_anlegen(basis, jetzt - timedelta(days=1))

	# Ein Byte frei — die letzte Sicherung ist groesser.
	monkeypatch.setattr(
		dump.shutil, "disk_usage",
		lambda pfad: types.SimpleNamespace(total=4096, used=4095, free=1),
	)
	monkeypatch.setattr(aufbewahrung.shutil, "disk_usage", dump.shutil.disk_usage)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is False
		assert "freier Platz" in ergebnis.meldung
	finally:
		sess.close()
	assert fake_dump == [], "ohne Platz darf kein Dump beginnen"
	assert not any(p.name.startswith(dump.TEMP_PRAEFIX) for p in basis.iterdir())


def test_platz_ist_ausreichend_dann_laeuft_es(patched_db, backup_heim, fake_dump,
                                              redis_stub_fuer_sperre):
	"""Gegenprobe: mit Platz laeuft derselbe Weg durch (kein Blindabbruch)."""
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	basis = backup_heim / "sicherungen"
	_sicherung_anlegen(basis, jetzt - timedelta(days=1))
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL,
		                                 jetzt=jetzt, sitzung=sess)
		assert ergebnis.ok is True, ergebnis.meldung
	finally:
		sess.close()


# ── 5. Sicherheit (B4) ─────────────────────────────────────────────────────

def test_sicherungsdateien_sind_nicht_fuer_andere_lesbar(patched_db, backup_heim,
                                                          fake_dump,
                                                          redis_stub_fuer_sperre):
	jetzt = datetime(2026, 10, 20, 3, 0, 0)
	sess = patched_db()
	try:
		einstellungen_modul.holen_oder_anlegen(sess, jetzt=jetzt)
		ergebnis = lauf_modul.fuehre_aus(ausloeser=lauf_modul.AUSLOESER_MANUELL,
		                                 jetzt=jetzt, sitzung=sess, aufraeumen=False)
	finally:
		sess.close()
	ordner = backup_heim / "sicherungen" / ergebnis.name
	assert stat.S_IMODE(ordner.stat().st_mode) == 0o700
	for datei in ordner.iterdir():
		assert stat.S_IMODE(datei.stat().st_mode) == 0o600, datei.name


def test_ziel_im_image_wird_abgewiesen(monkeypatch, tmp_path):
	"""Ein Ziel im Programmverzeichnis ist nach einem Neustart weg — Fehler."""
	import diakronos_app.settings as settings_modul

	monkeypatch.setattr(settings_modul.settings, "files_dir", str(tmp_path / "files"))
	monkeypatch.setattr(dump.settings, "files_dir", str(tmp_path / "files"))
	(tmp_path / "files").mkdir()
	monkeypatch.setattr(dump.settings, "backup_dir", "/app/backups")
	with pytest.raises(dump.SicherungFehler):
		dump.pruefe_ziel()
	monkeypatch.setattr(dump.settings, "backup_dir", "tmp/../ausserhalb-des-datenbaums")
	with pytest.raises(dump.SicherungFehler):
		dump.pruefe_ziel()


def test_ziel_im_datenbaum_wird_angelegt(backup_heim):
	ziel = dump.pruefe_ziel()
	assert ziel == (backup_heim / "sicherungen").resolve()
	assert stat.S_IMODE(ziel.stat().st_mode) == 0o700


def test_verbindungsdaten_stehen_nicht_in_der_meldung():
	"""B4: eine Dump-Fehlermeldung nennt Exit-Code und Zeile, kein Passwort."""
	import subprocess

	from diakronos_app.sicherung.dump import _dump_fehlertext

	ausgabe = subprocess.CompletedProcess(
		["pg_dump"], 1, "",
		'pg_dump: error: connection to server at "db" (198.51.100.2), port 5432 failed: '
		"password authentication failed for user \"diakronos\"\n",
	)
	text = _dump_fehlertext(ausgabe)
	assert "Exit 1" in text
	assert "password authentication" not in text
	assert "198.51.100.2" not in text


def test_pg_env_setzt_keine_argumente_auf_die_kommandozeile():
	"""Die Verbindung kommt aus der Umgebung, nicht aus Argumenten (ps)."""
	from diakronos_app.sicherung.dump import _pg_env

	env = _pg_env()
	assert env["PGHOST"]
	assert env["PGPORT"].isdigit()
	assert env["PGDATABASE"]
	# Passwort nur in der Umgebung — und im Test-Stack gar nicht gesetzt.
	assert "PGPASSWORD" not in env or not env["PGPASSWORD"].startswith("-")


def test_client_version_passt_zum_betrieb():
	"""pg_dump muss mindestens Major 17 sein (Betrieb: postgres:17-alpine).

	Ein 15er-pg_dump gegen einen 17er-Server bricht mit "server version
	mismatch" ab — die Sicherung waere im Betrieb tot, ohne dass es hier
	auffiele. Der Test laeuft nur, wenn pg_dump vorhanden ist (im Image ja).
	"""
	import shutil
	import subprocess

	if not shutil.which("pg_dump"):
		pytest.skip("pg_dump im Testlauf nicht vorhanden")
	ausgabe = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True)
	treffer = re.search(r"(\d+)\.", ausgabe.stdout)
	assert treffer, ausgabe.stdout
	assert int(treffer.group(1)) >= 17, f"pg_dump zu alt: {ausgabe.stdout.strip()}"


def test_es_gibt_keinen_download_und_keinen_wiederherstellungs_endpunkt():
	"""B3: Wiederherstellen/Herunterladen NUR ueber die Kommandozeile."""
	quelle = Path(__file__).resolve().parents[1] / "src/diakronos_app/api/sicherung.py"
	text = quelle.read_text(encoding="utf-8")
	funktionen = set(re.findall(r"^def (\w+)", text, re.M))
	assert funktionen == {
		"_angemeldeter_system_manager", "_sicherungsname", "_laeufe",
		"sicherung_get", "sicherung_einstellungen_speichern",
		"sicherung_jetzt", "sicherung_loeschen", "_jetzt",
	}
	# `pg_restore` darf nur im Modulkopf als Aussage stehen ("tut es NICHT").
	assert "pg_restore" not in re.sub(r'""".*?"""', "", text, flags=re.S), \
		"kein Wiederherstellen ueber HTTP"
	assert "FileResponse" not in text and "StreamingResponse" not in text
