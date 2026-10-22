"""P6a Teil 1 — Scheduler-Jobs: `anonymize_expired_audit_logs`, `delete_alte_anmeldeanfragen`.

Originale (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/audit_policy/anonymize.py`
`referenz/diakronos-frappe/diakronos/diakonos/api/cleanup.py`
registriert in `referenz/diakronos-frappe/diakronos/hooks.py:47` (`daily`).

Fristen werden mit KONKRETEN Datumsgrenzen geprueft: ein Eintrag knapp INNERHALB,
einer knapp AUSSERHALB der Frist.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from diakronos_app.api.audit_policy.anonymize import (
	DEFAULT_RETENTION_DAYS,
	anonymize_expired_audit_logs,
)
from diakronos_app.api.cleanup import AUFBEWAHRUNG_TAGE, delete_alte_anmeldeanfragen

# ── Helpers ─────────────────────────────────────────────────────────────────


def _now() -> datetime:
	from diakronos_app.frappe_compat.api_helpers import _now as shared_now

	return shared_now()


def _audit(sess, name: str, zeitstempel, **felder):
	from diakronos_app.models.diakonos import AuditLog

	werte = {
		"name": name,
		"zeitstempel": zeitstempel,
		"action_typ": "Datenzugriff",
		"actor": "anna@example.org",
		"target_user": "bruno@example.org",
		"old_value": "alt",
		"new_value": "neu",
		"confirm_reason": "weil",
		"ip_address": "203.0.113.1",
		"user_agent": "Mozilla/5.0",
		"docstatus": 0,
		"idx": 0,
	}
	werte.update(felder)
	row = AuditLog(**{k: v for k, v in werte.items() if hasattr(AuditLog, k)})
	sess.add(row)
	sess.commit()
	return row


def _anmeldung(sess, name: str, creation, status: str):
	from diakronos_app.models.diakonos import Anmeldung

	row = Anmeldung(
		name=name,
		creation=creation,
		modified=creation,
		owner="Administrator",
		modified_by="Administrator",
		docstatus=0,
		idx=0,
		status=status,
		anmeldungstyp="Mitglied",
	)
	sess.add(row)
	sess.commit()
	return row


def _set_retention(monkeypatch, days):
	"""`Diakronos Einstellungen.audit_log_retention_days` liefern.

	SCHEMA-REALITAET (geprueft, NICHT angenommen):
	* `Spaltenabzug der Betriebs-DB` fuehrt **keine** Tabelle
	  `Diakronos Einstellungen` — das DocType ist `issingle: 1` (s.
	  `referenz/.../doctype/diakronos_einstellungen/diakronos_einstellungen.json`)
	  und hat dort **kein** Feld `audit_log_retention_days`.
	* Das Feld existiert nur in `anonymize.py` selbst.

	Deshalb wird die Einstellung — wie in der Realitaet — ueber die
	Lesefunktion des Singles nachgebildet (`_single_field`), nicht ueber eine
	Spalte. Das entspricht exakt dem Originalpfad
	`frappe.db.get_single_value("Diakronos Einstellungen", ...)`.
	"""
	from diakronos_app.api.audit_policy import anonymize

	monkeypatch.setattr(
		anonymize,
		"_single_field",
		lambda feld: days if feld == "audit_log_retention_days" else None,
	)


def _clear_retention(monkeypatch):
	"""Kein Wert gesetzt (Single leer) -> Original faellt auf Default 1095."""
	from diakronos_app.api.audit_policy import anonymize

	monkeypatch.setattr(anonymize, "_single_field", lambda feld: None)


# ── anonymize_expired_audit_logs ────────────────────────────────────────────


def test_anonymize_default_frist_ist_1095_tage():
	"""Ohne gesetzten Wert greift der Original-Default: 3 Jahre."""
	assert DEFAULT_RETENTION_DAYS == 1095


def test_anonymize_nichts_zu_tun_ohne_daten(patched_db):
	assert anonymize_expired_audit_logs() == 0


def test_anonymize_frist_grenze_knapp_innerhalb_und_ausserhalb(patched_db, monkeypatch):
	"""Kernpruefung der Frist: 1095 Tage.

	Eintrag A: 1095 Tage + 1 Stunde alt  -> AUSSERHALB der Frist -> anonymisiert.
	Eintrag B: 1095 Tage - 1 Stunde alt  -> INNERHALB der Frist -> bleibt.
	"""
	_set_retention(monkeypatch, 1095)
	sess = patched_db()
	jetzt = _now()
	_audit(sess, "AL-ALT", jetzt - timedelta(days=1095, hours=1))
	_audit(sess, "AL-JUNG", jetzt - timedelta(days=1095, hours=-1))
	sess.close()

	assert anonymize_expired_audit_logs() == 1

	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	alt = sess.get(AuditLog, "AL-ALT")
	jung = sess.get(AuditLog, "AL-JUNG")
	sess.close()

	# Der alte Eintrag ist pseudonymisiert.
	assert alt.anonymized_at is not None
	assert alt.actor.startswith("sha256:")
	assert alt.target_user.startswith("sha256:")
	assert alt.old_value == "***"
	assert alt.new_value == "***"
	assert alt.confirm_reason == "***"
	assert alt.ip_address is None
	assert alt.user_agent is None

	# Der junge Eintrag ist UNBERUEHRT.
	assert jung.anonymized_at is None
	assert jung.actor == "anna@example.org"
	assert jung.ip_address == "203.0.113.1"


def test_anonymize_ist_idempotent(patched_db, monkeypatch):
	"""Zweimal laufen darf nichts kaputtmachen (Kartenanforderung)."""
	_set_retention(monkeypatch, 30)
	sess = patched_db()
	_audit(sess, "AL-1", _now() - timedelta(days=40))
	sess.close()

	assert anonymize_expired_audit_logs() == 1
	# Der zweite Lauf findet nichts mehr.
	assert anonymize_expired_audit_logs() == 0

	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	row = sess.get(AuditLog, "AL-1")
	sess.close()
	# Hash bleibt stabil (nicht doppelt gehasht), Stempel unveraendert gesetzt.
	assert row.actor.startswith("sha256:")
	assert row.actor.count("sha256:") == 1
	assert row.anonymized_at is not None


def test_anonymize_stempelt_anonymized_at(patched_db, monkeypatch):
	_set_retention(monkeypatch, 7)
	sess = patched_db()
	_audit(sess, "AL-S", _now() - timedelta(days=10))
	sess.close()
	anonymize_expired_audit_logs()
	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	row = sess.get(AuditLog, "AL-S")
	sess.close()
	assert isinstance(row.anonymized_at, datetime)


def test_anonymize_frist_null_ist_opt_out(patched_db, monkeypatch):
	"""`retention_days <= 0` -> gar nichts anonymisieren (Original-Zeile 18)."""
	_set_retention(monkeypatch, 0)
	sess = patched_db()
	_audit(sess, "AL-NULL", _now() - timedelta(days=9999))
	sess.close()

	assert anonymize_expired_audit_logs() == 0

	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	row = sess.get(AuditLog, "AL-NULL")
	sess.close()
	assert row.anonymized_at is None
	assert row.actor == "anna@example.org"


def test_anonymize_ohne_einstellungen_nutzt_default(patched_db, monkeypatch):
	"""Kein Single vorhanden -> Default 1095 Tage, nicht 0 (nicht alles loeschen).

	Originalpfad: `get_single_value` wirft/leer -> `cint(None) == 0` -> `or 1095`.
	"""
	_clear_retention(monkeypatch)
	sess = patched_db()
	_audit(sess, "AL-1200", _now() - timedelta(days=1200))
	_audit(sess, "AL-100", _now() - timedelta(days=100))
	sess.close()

	assert anonymize_expired_audit_logs() == 1

	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	assert sess.get(AuditLog, "AL-1200").anonymized_at is not None
	assert sess.get(AuditLog, "AL-100").anonymized_at is None
	sess.close()


def test_anonymize_bereits_anonymisierte_zeile_bleibt_unberuehrt(patched_db, monkeypatch):
	"""Eine Zeile mit gesetztem `anonymized_at` wird nie erneut angefasst."""
	_set_retention(monkeypatch, 30)
	stempel = _now() - timedelta(days=1)
	sess = patched_db()
	_audit(
		sess, "AL-ALREADY", _now() - timedelta(days=400),
		anonymized_at=stempel, actor="sha256:abc",
	)
	sess.close()

	assert anonymize_expired_audit_logs() == 0

	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	row = sess.get(AuditLog, "AL-ALREADY")
	sess.close()
	assert row.anonymized_at == stempel
	assert row.actor == "sha256:abc"


def test_anonymize_hash_ist_deterministisch_und_mit_site_salt(patched_db):
	import hashlib

	from diakronos_app.api.audit_policy.anonymize import _hash_identifier

	erwartet = hashlib.sha256(("anna@example.org" + "diakronos").encode()).hexdigest()
	assert _hash_identifier("anna@example.org") == f"sha256:{erwartet}"
	# Leerwert -> None (Original).
	assert _hash_identifier(None) is None
	assert _hash_identifier("") is None


def test_anonymize_leere_felder_bleiben_none(patched_db, monkeypatch):
	_set_retention(monkeypatch, 1)
	sess = patched_db()
	_audit(
		sess, "AL-LEER", _now() - timedelta(days=5),
		old_value=None, new_value=None, confirm_reason=None,
		actor=None, target_user=None,
	)
	sess.close()
	anonymize_expired_audit_logs()
	sess = patched_db()
	from diakronos_app.models.diakonos import AuditLog

	row = sess.get(AuditLog, "AL-LEER")
	sess.close()
	# Original: "***" nur wenn vorher ein Wert da war, sonst None.
	assert row.old_value is None
	assert row.new_value is None
	assert row.confirm_reason is None
	assert row.anonymized_at is not None


# ── delete_alte_anmeldeanfragen ─────────────────────────────────────────────


def test_cleanup_frist_ist_14_tage():
	assert AUFBEWAHRUNG_TAGE == 14


def test_cleanup_nichts_zu_tun_ohne_daten(patched_db):
	assert delete_alte_anmeldeanfragen() == 0


def test_cleanup_grenze_knapp_innerhalb_und_ausserhalb(patched_db):
	"""15 Tage alte 'Anmeldeanfrage' weg, 13 Tage alte bleibt."""
	sess = patched_db()
	heute = date.today()
	_anmeldung(sess, "AN-ALT", datetime.combine(heute - timedelta(days=15), datetime.min.time()), "Anmeldeanfrage")
	_anmeldung(sess, "AN-JUNG", datetime.combine(heute - timedelta(days=13), datetime.min.time()), "Anmeldeanfrage")
	sess.close()

	assert delete_alte_anmeldeanfragen() == 1

	from diakronos_app.models.diakonos import Anmeldung

	sess = patched_db()
	assert sess.get(Anmeldung, "AN-ALT") is None
	assert sess.get(Anmeldung, "AN-JUNG") is not None
	sess.close()


def test_cleanup_loescht_nur_die_beiden_alten_status(patched_db):
	"""Status-Filter: 'Angenommen'/'Abgelehnt genug' bleiben, 'Abgelehnt' geht."""
	sess = patched_db()
	alt = datetime.combine(date.today() - timedelta(days=30), datetime.min.time())
	_anmeldung(sess, "AN-ANFRAGE", alt, "Anmeldeanfrage")
	_anmeldung(sess, "AN-ABGELEHNT", alt, "Abgelehnt")
	_anmeldung(sess, "AN-ANGENOMMEN", alt, "Angenommen")
	_anmeldung(sess, "AN-ANDERER", alt, "Sonstiges")
	sess.close()

	assert delete_alte_anmeldeanfragen() == 2

	from diakronos_app.models.diakonos import Anmeldung

	sess = patched_db()
	assert sess.get(Anmeldung, "AN-ANFRAGE") is None
	assert sess.get(Anmeldung, "AN-ABGELEHNT") is None
	assert sess.get(Anmeldung, "AN-ANGENOMMEN") is not None
	assert sess.get(Anmeldung, "AN-ANDERER") is not None
	sess.close()


def test_cleanup_ist_idempotent(patched_db):
	sess = patched_db()
	alt = datetime.combine(date.today() - timedelta(days=20), datetime.min.time())
	_anmeldung(sess, "AN-1", alt, "Anmeldeanfrage")
	sess.close()

	assert delete_alte_anmeldeanfragen() == 1
	assert delete_alte_anmeldeanfragen() == 0


def test_cleanup_loescht_kindzeilen_mit(patched_db):
	"""Ohne FK-Kaskade muessen `Anmeldung Kind`/`Antwort` mitgeloescht werden."""
	sess = patched_db()
	alt = datetime.combine(date.today() - timedelta(days=20), datetime.min.time())
	_anmeldung(sess, "AN-KIND", alt, "Anmeldeanfrage")

	from diakronos_app.models.diakonos import AnmeldungAntwort, AnmeldungKind

	sess.add(AnmeldungKind(
		name="AK-1", parent="AN-KIND", parenttype="Anmeldung", parentfield="kinder",
		docstatus=0, idx=0, vorname="Lena", nachname="Lang",
	))
	sess.add(AnmeldungAntwort(
		name="AA-1", parent="AN-KIND", parenttype="Anmeldung", parentfield="antworten",
		docstatus=0, idx=0, feldlabel="Essen", antwort="Ja",
	))
	sess.commit()
	sess.close()

	assert delete_alte_anmeldeanfragen() == 1

	sess = patched_db()
	assert sess.get(AnmeldungKind, "AK-1") is None
	assert sess.get(AnmeldungAntwort, "AA-1") is None
	sess.close()


def test_cleanup_ueberspringt_fehlende_zeile_still(patched_db, monkeypatch):
	"""Ein Loeschfehler stoppt den Lauf nicht (Original try/except in der Schleife)."""
	from diakronos_app.api import cleanup

	sess = patched_db()
	alt = datetime.combine(date.today() - timedelta(days=20), datetime.min.time())
	_anmeldung(sess, "AN-A", alt, "Anmeldeanfrage")
	_anmeldung(sess, "AN-B", alt, "Anmeldeanfrage")
	sess.close()

	echt = cleanup._delete_anmeldung
	gesehen = []

	def halb_kaputt(name: str) -> None:
		gesehen.append(name)
		if name == "AN-A":
			raise RuntimeError("kaputt")
		echt(name)

	monkeypatch.setattr(cleanup, "_delete_anmeldung", halb_kaputt)

	# AN-A scheitert, AN-B wird trotzdem geloescht.
	assert cleanup.delete_alte_anmeldeanfragen() == 1
	assert set(gesehen) == {"AN-A", "AN-B"}

	from diakronos_app.models.diakonos import Anmeldung

	sess = patched_db()
	assert sess.get(Anmeldung, "AN-A") is not None
	assert sess.get(Anmeldung, "AN-B") is None
	sess.close()


# ── Scheduler-Registrierung ────────────────────────────────────────────────


def test_scheduler_registriert_beide_daily_jobs():
	from diakronos_app.scheduler import DAILY_JOBS

	ids = {job_id for _, job_id in DAILY_JOBS}
	assert ids == {
		"anonymize_expired_audit_logs",
		"delete_alte_anmeldeanfragen",
		# N-2: Aufbewahrungsfrist abgelehnter Anbieter-Zuordnungen.
		"delete_alte_zuordnung_ablehnungen",
	}


def test_scheduler_jobs_sind_daily_und_laufen_nicht_sofort():
	"""Kartenanforderung: kein Job darf beim Start sofort ausgefuehrt werden.

	APScheduler liefert `next_run_time` erst ab `start()` (das Feld wird beim
	Einplanen gesetzt). Statt den Scheduler zu starten (blockierend!) pruefen
	wir den Cron-Trigger selbst gegen 'jetzt': der naechste Feürzeitpunkt muss
	echt in der Zukunft liegen. Das ist genau die Zusicherung 'nicht sofort'.
	"""
	from apscheduler.triggers.cron import CronTrigger

	from diakronos_app.scheduler import DAILY_HOUR, DAILY_MINUTE, build_scheduler

	scheduler = build_scheduler()
	try:
		jobs = {job.id: job for job in scheduler.get_jobs()}
		for job_id in (
			"anonymize_expired_audit_logs",
			"delete_alte_anmeldeanfragen",
			"delete_alte_zuordnung_ablehnungen",
		):
			assert job_id in jobs
			job = jobs[job_id]
			assert job.trigger.__class__.__name__ == "CronTrigger"
			# Cron-Trigger gegen den Einplan-Zeitpunkt auswerten.
			fire_at = job.trigger.get_next_fire_time(None, _now().replace(tzinfo=timezone.utc))
			assert fire_at is not None
			# 00:00 UTC ist der naechste Lauf -> strikt in der Zukunft.
			assert fire_at > _now().replace(tzinfo=timezone.utc)
			assert (fire_at.hour, fire_at.minute) == (DAILY_HOUR, DAILY_MINUTE)
	finally:
		if scheduler.running:
			scheduler.shutdown(wait=False)


def test_scheduler_job_wrapper_ruft_die_portierte_funktion(patched_db, monkeypatch):
	"""Der Scheduler-Wrapper muss die portierte Funktion aufrufen (nicht raten)."""
	from diakronos_app import scheduler

	aufgerufen: list[str] = []

	monkeypatch.setattr(
		"diakronos_app.api.audit_policy.anonymize.anonymize_expired_audit_logs",
		lambda: aufgerufen.append("anonymize") or 0,
	)
	monkeypatch.setattr(
		"diakronos_app.api.cleanup.delete_alte_anmeldeanfragen",
		lambda: aufgerufen.append("cleanup") or 0,
	)

	scheduler.job_anonymize_expired_audit_logs()
	scheduler.job_delete_alte_anmeldeanfragen()

	assert aufgerufen == ["anonymize", "cleanup"]


def test_scheduler_wrapper_schluckt_fehler(patched_db, monkeypatch):
	"""Ein Job-Fehler darf den Scheduler-Prozess nicht toeten."""
	from diakronos_app import scheduler

	def kaputt():
		raise RuntimeError("boom")

	monkeypatch.setattr(
		"diakronos_app.api.audit_policy.anonymize.anonymize_expired_audit_logs", kaputt
	)
	# Darf nicht werfen.
	scheduler.job_anonymize_expired_audit_logs()


def test_anonymize_ist_kein_http_endpunkt():
	"""Der Job hat kein `@whitelist` — wie im Original (kein SPA-Pfad)."""
	from diakronos_app.frappe_compat.registry import lookup

	assert lookup("diakronos.diakonos.api.audit_policy.anonymize.anonymize_expired_audit_logs") is None
	assert lookup("diakronos.diakonos.api.cleanup.delete_alte_anmeldeanfragen") is None


@pytest.mark.parametrize("frist,alter_tage,erwartet", [
	(1095, 1095.5, 1),
	(1095, 1094.5, 0),
	(365, 366, 1),
	(365, 364, 0),
	(1, 2, 1),
	(1, 1, 0),
])
def test_anonymize_fristen_matrix(patched_db, monkeypatch, frist, alter_tage, erwartet):
	"""Fristenmatrix mit konkreten Alterswerten.

	Die Uhr wird im Modul unter Test auf EINEN Zeitpunkt gepinnt. Sonst liegen
	Zeilen-Anlage und Cutoff-Berechnung Mikrosekunden auseinander und der
	exakte Grenzfall `alter_tage == frist` wuerde mal so, mal so ausgehen —
	die Grenze ist strikt `<`, das soll deterministisch geprueft werden.
	"""
	from diakronos_app.api.audit_policy import anonymize

	fest = _now()
	# `_site_now` ist die einzige "Jetzt"-Quelle des Moduls (Z.103/179).
	monkeypatch.setattr(anonymize, "_site_now", lambda: fest)
	_set_retention(monkeypatch, frist)

	sess = patched_db()
	_audit(sess, "AL-M", fest - timedelta(days=alter_tage))
	sess.close()
	assert anonymize_expired_audit_logs() == erwartet
