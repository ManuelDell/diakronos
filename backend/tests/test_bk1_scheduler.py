"""BACKUP-1 — die Sicherung laeuft durch den vorhandenen scheduler-Dienst.

Die Karte verlangt die Sicherung „durch den vorhandenen scheduler-Dienst
(diakronos_app.scheduler)“. Geprueft wird hier die Fälligkeit — also die
Entscheidung, ob der Minuten-Job jetzt sichern soll:

* vor der eingestellten Uhrzeit: nein
* danach und heute noch nicht gesichert: ja
* danach und heute schon gesichert: nein (hoechstens EIN Lauf je Tag)
* automatisch aus: nein
* ein Neustart um 04:30 holt eine verpasste 03:00-Sicherung nach
"""

from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.sicherung import einstellungen as einstellungen_modul


@pytest.fixture()
def redis_stub(monkeypatch):
	from redis_stub import StubRedis

	stub = StubRedis()
	monkeypatch.setattr("diakronos_app.scheduler._merker_client", lambda: stub)
	return stub


@pytest.fixture()
def backup_heim(monkeypatch, tmp_path):
	"""Eigener Datenbaum — dieselbe Fixture wie in ``test_bk1_sicherung``.

	``fuehre_aus`` prueft den Ablageort; ohne eigenen Baum liefe der Test
	gegen ``/data/sicherungen`` des Containers.
	"""
	import diakronos_app.settings as settings_modul
	from diakronos_app.sicherung import dump

	heim = tmp_path / "data"
	(heim / "files").mkdir(parents=True)
	monkeypatch.setattr(settings_modul.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(settings_modul.settings, "backup_dir", str(heim / "sicherungen"))
	monkeypatch.setattr(dump.settings, "files_dir", str(heim / "files"))
	monkeypatch.setattr(dump.settings, "backup_dir", str(heim / "sicherungen"))
	return heim


@pytest.fixture()
def einstellungen(patched_db, monkeypatch):
	"""Einstellungszeile im Test-DB; der Job oeffnet seine Sitzung wie im Betrieb."""
	import diakronos_app.db as dbmod
	from sqlalchemy.orm import sessionmaker

	# `sicherung_faellig` holt die Einstellungen ueber `SessionLocal()`; die
	# conftest-Fixture patcht das Modul-Attribut bereits. Nichts weiter noetig.

	def _setze(**werte):
		sess = dbmod.SessionLocal()
		try:
			zeile = einstellungen_modul.holen_oder_anlegen(sess, jetzt=datetime(2026, 10, 19, 3, 0))
			for feld, wert in werte.items():
				setattr(zeile, feld, wert)
			sess.commit()
		finally:
			sess.close()

	return _setze


def test_vor_der_uhrzeit_ist_nichts_faellig(einstellungen, redis_stub):
	from diakronos_app import scheduler

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 2, 59)) is False


def test_nach_der_uhrzeit_ist_es_faellig(einstellungen, redis_stub):
	from diakronos_app import scheduler

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 3, 0)) is True


def test_hoechstens_ein_lauf_je_tag(einstellungen, redis_stub):
	from diakronos_app import scheduler

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 3, 0)) is True
	scheduler.merke_gesichert("2026-10-20", 30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 3, 1)) is False
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 23, 59)) is False
	# Der naechste Tag ist wieder faellig.
	assert scheduler.sicherung_faellig(datetime(2026, 10, 21, 3, 0)) is True


def test_abgeschaltet_sichert_nicht(einstellungen, redis_stub):
	from diakronos_app import scheduler

	einstellungen(uhrzeit="03:00", automatisch=False, aufbewahrung_tage=30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 12, 0)) is False


def test_verpasste_uhrzeit_wird_nachgeholt(einstellungen, redis_stub):
	"""Neustart um 04:30 und die 03:00-Sicherung fehlt -> jetzt nachholen."""
	from diakronos_app import scheduler

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 4, 30)) is True


def test_veraenderte_uhrzeit_wirkt_ohne_neustart(einstellungen, redis_stub):
	from diakronos_app import scheduler

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 2, 30)) is False
	einstellungen(uhrzeit="02:15")
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 2, 30)) is True


def test_job_ruft_den_lauf_mit_dem_ausloeser_automatisch(
	einstellungen, redis_stub, monkeypatch, tmp_path,
):
	"""Der Minuten-Job startet `fuehre_aus(ausloeser='automatisch')`."""
	from diakronos_app import scheduler
	from diakronos_app.sicherung import lauf as lauf_modul

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	aufrufe: list[str] = []

	def _fuehre_aus(*, ausloeser, jetzt=None, sitzung=None, timeout=None,
	                aufraeumen=True, sperre_gesetzt=None):
		aufrufe.append(ausloeser)
		if sperre_gesetzt is not None:
			sperre_gesetzt()
		return lauf_modul.Sicherungsergebnis(name="x", status="ok", meldung="ok")

	monkeypatch.setattr(lauf_modul, "fuehre_aus", _fuehre_aus)
	scheduler.job_datensicherung(datetime(2026, 10, 20, 3, 0))
	assert aufrufe == ["automatisch"]
	# Zweiter Tick am selben Tag: kein zweiter Lauf.
	scheduler.job_datensicherung(datetime(2026, 10, 20, 3, 1))
	assert aufrufe == ["automatisch"]


def test_job_vor_der_uhrzeit_startet_nichts(einstellungen, redis_stub, monkeypatch):
	from diakronos_app import scheduler
	from diakronos_app.sicherung import lauf as lauf_modul

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	aufrufe: list[str] = []
	monkeypatch.setattr(lauf_modul, "fuehre_aus",
	                    lambda **kw: aufrufe.append("x"))
	scheduler.job_datensicherung(datetime(2026, 10, 20, 1, 0))
	assert aufrufe == []


def test_scheduler_registriert_den_sicherungsjob():
	from datetime import timedelta, timezone
	from threading import Thread
	from time import sleep

	from diakronos_app.scheduler import build_scheduler

	scheduler = build_scheduler()
	assert "datensicherung" in {job.id for job in scheduler.get_jobs()}

	# BlockingScheduler.start() blockiert — der Start laeuft im eigenen Faden,
	# damit sich der Laufzeitpunkt des Jobs abfragen laesst.
	faden = Thread(target=scheduler.start, daemon=True)
	faden.start()
	try:
		job = None
		ende = datetime.now(timezone.utc) + timedelta(seconds=10)
		while datetime.now(timezone.utc) < ende:
			job = scheduler.get_job("datensicherung")
			if job is not None and getattr(job, "next_run_time", None) is not None:
				break
			sleep(0.05)
		assert job is not None, "Der Sicherungsjob ist nicht im Scheduler"
		assert job.trigger.__class__.__name__ == "IntervalTrigger", \
			"Minuten-Job, weil die Uhrzeit in der Datenbank steht"
		# APScheduler-Haltepunkt: `next_run_time=None` heisst "angehalten" —
		# ein solcher Job laeuft NIE (am 2026-10-20 im Teststack beobachtet:
		# kein einziger Lauf, obwohl faellig). Der erste Lauf braucht also
		# einen echten Zeitpunkt.
		assert getattr(job, "next_run_time", None) is not None, \
			"Job ohne next_run_time bleibt dauerhaft angehalten"
		# Kein Sofortlauf beim Hochfahren des Stacks: der erste Lauf liegt
		# eine Intervall-Periode (1 Minute) in der Zukunft.
		assert job.next_run_time >= datetime.now(timezone.utc) + timedelta(seconds=30), \
			"erster Lauf sofort statt nach einer Intervall-Periode"
	finally:
		scheduler.shutdown(wait=False)


def test_merker_ohne_redis_sichert_lieber(monkeypatch):
	"""Fällt Redis aus, wird gesichert statt geschwiegen (Merker ist Beiwerk)."""
	from diakronos_app import scheduler

	class _Kaputt:
		def get(self, *_a, **_k):
			raise RuntimeError("redis weg")

	monkeypatch.setattr(scheduler, "_merker_client", lambda: _Kaputt())
	assert scheduler.schon_gesichert("2026-10-20") is False


# ── N3 (BACKUP-1b): stiller Ausfall des automatischen Laufs ────────────────

def test_sperre_nicht_verfuegbar_setzt_den_tagesmerker_nicht(
	einstellungen, redis_stub, monkeypatch,
):
	"""Scheitert der Lauf an der Sperre, bleibt der Tag offen (N3)."""
	from diakronos_app import scheduler
	from diakronos_app.sicherung import lauf as lauf_modul

	einstellungen(uhrzeit="03:00", automatisch=True, aufbewahrung_tage=30)
	zeit = datetime(2026, 10, 20, 3, 0)

	class _OhneRedis:
		def set(self, *_a, **_k):
			raise RuntimeError("redis weg")

		def get(self, *_a, **_k):
			return None

	# Sperre und Merker teilen sich Redis: beide Wege fallen aus.
	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: _OhneRedis())

	scheduler.job_datensicherung(zeit)

	assert scheduler.schon_gesichert("2026-10-20") is False, \
		"ohne Sperre darf der Tag nicht als erledigt gelten"
	assert scheduler.sicherung_faellig(datetime(2026, 10, 20, 3, 5)) is True, \
		"der naechste Tick muss es erneut versuchen"


def test_ausfall_an_der_sperre_benachrichtigt_die_system_manager(
	patched_db, backup_heim, monkeypatch,
):
	"""N3: der Ausfall bleibt nicht unbemerkt — Meldung an die System Manager."""
	from diakronos_app.models.core import HasRole, User
	from diakronos_app.sicherung import lauf as lauf_modul

	sess = patched_db()
	sess.add(User(name="chefin@example.org", email="chefin@example.org",
	              full_name="Chefin", enabled=True))
	sess.add(HasRole(name="hr-2", parent="chefin@example.org", parenttype="User",
	                 parentfield="roles", role="System Manager", docstatus=0, idx=1))
	sess.commit()
	sess.close()

	class _Belegt:
		def set(self, *_a, **_k):
			return False      # SET NX: es laeuft schon eine Sicherung

		def get(self, *_a, **_k):
			return None

	gesehen: list[tuple[str, str]] = []

	def _merke(subject, inhalt, sitzung=None):
		gesehen.append((subject, inhalt))
		return ["chefin@example.org"]

	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: _Belegt())
	monkeypatch.setattr(lauf_modul, "benachrichtige_system_manager", _merke)

	ergebnis = lauf_modul.fuehre_aus(
		ausloeser=lauf_modul.AUSLOESER_AUTOMATISCH,
		jetzt=datetime(2026, 10, 20, 3, 0),
	)
	assert ergebnis.ok is False
	assert len(gesehen) == 1
	assert "nicht gelaufen" in gesehen[0][0].lower()


# ── N6 (BACKUP-1c): Meldungsflut drosseln ──────────────────────────────────
#
# Der Minuten-Job versucht es bei jedem Tick erneut (N3, Absicht). Die MELDUNG
# an die System Manager darf dabei nicht mitwachsen: hoechstens eine Meldung je
# Tag und Ursache — und der Merker haelt auch dann, wenn Redis weg ist (der
# Merker darf nicht von dem Dienst abhaengen, dessen Ausfall er meldet).

class _ZaehlendeMeldungen:
	"""Sammelt die TATSAECHLICH zugestellten Meldungen (siehe ``_beobachte``)."""

	def __init__(self):
		self.gesendet: list[tuple[str, str]] = []


def _system_manager_anlegen(patched_db) -> None:
	from diakronos_app.models.core import HasRole, User

	sess = patched_db()
	sess.add(User(name="chefin@example.org", email="chefin@example.org",
	              full_name="Chefin", enabled=True))
	sess.add(HasRole(name="hr-2", parent="chefin@example.org", parenttype="User",
	                 parentfield="roles", role="System Manager", docstatus=0, idx=1))
	sess.commit()
	sess.close()


def _minuten_ticks(jetzt):
	"""30 Minuten-Ticks am selben Tag ab ``jetzt`` (Sperre/Redis bleibt kaputt)."""
	from datetime import timedelta

	from diakronos_app import scheduler

	for minute in range(30):
		scheduler.job_datensicherung(jetzt + timedelta(minutes=minute))


def _hole_einstellungen(patched_db) -> None:
	"""Einstellungszeile direkt in der DB — ohne Redis (``sicherung_faellig``).

	``einstellungen`` (Fixture oben) ist der Weg ueber ``merke_gesichert``; hier
	wird der Tagesmerker absichtlich NICHT benutzt: ``schon_gesichert`` faellt
	bei kaputtem Redis auf ``False`` zurueck, der Job muss also bei jedem Tick
	neu anlaufen. Gesetzt wird die Zeile ueber dieselbe Funktion wie im Betrieb.
	"""
	from diakronos_app.db import SessionLocal
	from diakronos_app.sicherung.einstellungen import holen_oder_anlegen

	sess = SessionLocal()
	try:
		zeile = holen_oder_anlegen(sess, jetzt=datetime(2026, 10, 20, 3, 0))
		zeile.uhrzeit = "03:00"
		zeile.automatisch = True
		zeile.aufbewahrung_tage = 30
		sess.commit()
	finally:
		sess.close()


def _sperre_belegt(monkeypatch) -> None:
	class _Belegt:
		def set(self, *_a, **_k):
			return False      # SET NX: es laeuft schon eine Sicherung

		def get(self, *_a, **_k):
			return None

	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: _Belegt())


def _redis_weg(monkeypatch) -> None:
	"""Sperre UND Tagesmerker fallen aus — beide teilen sich Redis."""
	class _OhneRedis:
		def set(self, *_a, **_k):
			raise RuntimeError("redis weg")

		def get(self, *_a, **_k):
			raise RuntimeError("redis weg")

	monkeypatch.setattr("diakronos_app.scheduler._merker_client", lambda: _OhneRedis())
	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: _OhneRedis())


def _beobachte(monkeypatch, zaehler: "_ZaehlendeMeldungen") -> None:
	"""Zeichnet die TATSAECHLICH zugestellten Meldungen auf.

	Gezaehlt wird an der Zustellstelle (``benachrichtigungen.schreibe_meldung``)
	statt an ``lauf.benachrichtige_system_manager``: so ist die Zahl unabhaengig
	davon, welcher Weg die Meldung schickt (Sperre, Redis-Ausfall, echter Lauf).
	"""
	from diakronos_app import benachrichtigungen

	echt = benachrichtigungen.schreibe_meldung

	def _zustellen(*, for_user, subject, inhalt, document_type="",
	               document_name="", typ="Alert"):
		zaehler.gesendet.append((subject, inhalt))
		return echt(for_user=for_user, subject=subject, inhalt=inhalt,
		            document_type=document_type, document_name=document_name, typ=typ)

	monkeypatch.setattr(benachrichtigungen, "schreibe_meldung", _zustellen)


def test_belegte_sperre_meldet_nur_einmal_pro_tag(patched_db, backup_heim, monkeypatch):
	"""30 Ticks, Sperre belegt → genau EINE Meldung (N6)."""
	_hole_einstellungen(patched_db)
	_system_manager_anlegen(patched_db)
	_sperre_belegt(monkeypatch)

	meldungen = _ZaehlendeMeldungen()
	_beobachte(monkeypatch, meldungen)

	_minuten_ticks(datetime(2026, 10, 20, 3, 0))

	assert len(meldungen.gesendet) == 1, f"Flut: {len(meldungen.gesendet)} Meldungen"
	assert "nicht gelaufen" in meldungen.gesendet[0][0].lower()


def test_redis_ausfall_meldet_nur_einmal_pro_tag(patched_db, backup_heim, monkeypatch):
	"""30 Ticks, Redis weg → genau EINE Meldung; der Merker haelt ohne Redis."""
	_hole_einstellungen(patched_db)
	_system_manager_anlegen(patched_db)
	_redis_weg(monkeypatch)

	meldungen = _ZaehlendeMeldungen()
	_beobachte(monkeypatch, meldungen)

	_minuten_ticks(datetime(2026, 10, 20, 3, 0))

	assert len(meldungen.gesendet) == 1, f"Flut: {len(meldungen.gesendet)} Meldungen"


def test_am_naechsten_tag_meldet_es_wieder_einmal(patched_db, backup_heim, monkeypatch):
	"""Der Drossel-Merker laeuft um Mitternacht ab — gestern drosselt heute nicht."""
	_hole_einstellungen(patched_db)
	_system_manager_anlegen(patched_db)
	_sperre_belegt(monkeypatch)

	meldungen = _ZaehlendeMeldungen()
	_beobachte(monkeypatch, meldungen)

	_minuten_ticks(datetime(2026, 10, 20, 3, 0))
	assert len(meldungen.gesendet) == 1

	_minuten_ticks(datetime(2026, 10, 21, 3, 0))
	assert len(meldungen.gesendet) == 2, \
		f"am naechsten Tag keine neue Meldung: {len(meldungen.gesendet)}"


def test_zwei_ursachen_werden_getrennt_gedrosselt(patched_db, backup_heim, monkeypatch):
	"""Sperre und Redis-Ausfall sind zwei Ursachen — je eine Meldung."""
	_hole_einstellungen(patched_db)
	_system_manager_anlegen(patched_db)
	meldungen = _ZaehlendeMeldungen()
	_beobachte(monkeypatch, meldungen)

	_sperre_belegt(monkeypatch)
	_minuten_ticks(datetime(2026, 10, 20, 3, 0))

	_redis_weg(monkeypatch)
	_minuten_ticks(datetime(2026, 10, 20, 4, 0))

	assert len(meldungen.gesendet) == 2, f"{len(meldungen.gesendet)} Meldungen"
	assert "Sperre" in meldungen.gesendet[1][1], \
		"die zweite Meldung nennt nicht die neue Ursache (Redis)"


def test_manueller_lauf_bei_belegter_sperre_meldet_nicht(patched_db, backup_heim,
                                                         monkeypatch):
	"""Ein Mensch drueckt den Knopf und sieht die Meldung — keine Mail noetig."""
	from diakronos_app.sicherung import lauf as lauf_modul

	class _Belegt:
		def set(self, *_a, **_k):
			return False

	monkeypatch.setattr("diakronos_app.sicherung.sperre._client", lambda: _Belegt())
	gesehen: list[str] = []
	monkeypatch.setattr(lauf_modul, "benachrichtige_system_manager",
	                    lambda subject, inhalt, sitzung=None: gesehen.append(subject))

	ergebnis = lauf_modul.fuehre_aus(
		ausloeser=lauf_modul.AUSLOESER_MANUELL,
		jetzt=datetime(2026, 10, 20, 3, 0),
	)
	assert ergebnis.ok is False
	assert gesehen == []
