"""APScheduler — taegliche Jobs des Standalone-Backends.

Entspricht den `scheduler_events` des Frappe-Originals
(`referenz/diakronos-frappe/diakronos/hooks.py:47`):

    scheduler_events = {"daily": [
        "diakronos.diakonos.api.audit_policy.anonymize.anonymize_expired_audit_logs",
        "diakronos.diakonos.api.cleanup.delete_alte_anmeldeanfragen",
    ]}

Beide Jobs sind **DSGVO-relevant**:

* `anonymize_expired_audit_logs` pseudonymisiert Audit-Logs nach Ablauf der
  konfigurierten Frist (`Diakronos Einstellungen.audit_log_retention_days`,
  Default 1095 Tage).
* `delete_alte_anmeldeanfragen` loescht Anmeldeanfragen aelter als 14 Tage mit
  den Status 'Anmeldeanfrage' / 'Abgelehnt'.

Kein Job laeuft beim Start sofort: `next_run_time` wird bewusst auf den naechsten
regulaeren Laufzeitpunkt gesetzt (Kartenanforderung "Scheduler NICHT alle Jobs
beim Start sofort ausfuehren lassen"). Frappe verhaelt sich genauso — ein
taeglicher Job wartet bis zum naechsten Cron-Zeitpunkt.

Beide Funktionen sind idempotent: zweimal laufen ist folgenlos (Auswahlkriterien
schliessen bereits bearbeitete Zeilen aus).

BACKUP-1 — Datensicherung
-------------------------
Die Sicherung laeuft ebenfalls hier, aber **nicht wie die uebrigen Jobs um
00:00**: ihre Uhrzeit ist einstellbar (Standard 03:00, Ortszeit aus
`settings.calendar_timezone`) und steht in der Datenbank. Ein Cron-Job mit
fester Stunde koennte das nicht abbilden; deshalb ist `job_datensicherung`
ein **Minuten-Job**, der prueft, ob die eingestellte Uhrzeit erreicht ist, und
sonst sofort zurueckkehrt (zwei Datenbank-Lesungen pro Minute — das ist der
Preis fuer eine Uhrzeit, die man ohne Neustart aendern kann).

Dabei gilt: hoechstens EIN Lauf je Tag. Der Merker liegt in Redis
(`sicherung:zuletzt`), nicht im Prozess — ein Neustart des Schedulers darf
die Sicherung des Tages nicht ein zweites Mal ausloesen, und ein
`docker compose restart` um 03:01 soll sie auch nicht verschlucken.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from diakronos_app.settings import settings

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("diakronos_app.scheduler")

# Uhrzeit des taeglichen Laufs (UTC). Frappe faehrt `daily`-Jobs um 00:00.
DAILY_HOUR = 0
DAILY_MINUTE = 0


def tick() -> None:
	logger.info("scheduler tick — noch keine Jobs registriert")


def job_anonymize_expired_audit_logs() -> None:
	"""Taeglicher DSGVO-Job: abgelaufene Audit-Logs pseudonymisieren."""
	from diakronos_app.api.audit_policy.anonymize import anonymize_expired_audit_logs

	try:
		count = anonymize_expired_audit_logs()
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		logger.exception("Job anonymize_expired_audit_logs fehlgeschlagen")
		return
	logger.info("Job anonymize_expired_audit_logs fertig (%s Eintraege).", count)


def job_delete_alte_anmeldeanfragen() -> None:
	"""Taeglicher Job: alte Anmeldeanfragen (> 14 Tage) loeschen."""
	from diakronos_app.api.cleanup import delete_alte_anmeldeanfragen

	try:
		count = delete_alte_anmeldeanfragen()
	except Exception:  # noqa: BLE001
		logger.exception("Job delete_alte_anmeldeanfragen fehlgeschlagen")
		return
	logger.info("Job delete_alte_anmeldeanfragen fertig (%s geloescht).", count)


def job_delete_alte_zuordnung_ablehnungen() -> None:
	"""Taeglicher Job: abgelehnte Zuordnungen nach Frist entfernen (N-2)."""
	from diakronos_app.api.cleanup import delete_alte_zuordnung_ablehnungen

	try:
		count = delete_alte_zuordnung_ablehnungen()
	except Exception:  # noqa: BLE001
		logger.exception("Job delete_alte_zuordnung_ablehnungen fehlgeschlagen")
		return
	logger.info("Job delete_alte_zuordnung_ablehnungen fertig (%s geloescht).", count)


# (Job-Funktion, Job-Id) — die Registrierung ist damit an EINER Stelle und
# fuer Tests pruefbar, ohne den BlockingScheduler zu starten.
DAILY_JOBS: list[tuple] = [
	(job_anonymize_expired_audit_logs, "anonymize_expired_audit_logs"),
	(job_delete_alte_anmeldeanfragen, "delete_alte_anmeldeanfragen"),
	(job_delete_alte_zuordnung_ablehnungen, "delete_alte_zuordnung_ablehnungen"),
]


# ── BACKUP-1: Datensicherung ────────────────────────────────────────────────

#: Redis-Schluessel des Tagesmerkers: enthaelt das Datum des letzten Laufs.
SICHERUNG_MERKER = "sicherung:zuletzt"


def _jetzt_ortszeit():
	"""Aktuelle Ortszeit — eigentliche Funktion in ``sicherung/einstellungen``.

	Scheduler und Sicherungslauf muessen dieselbe Uhr verwenden, damit alle
	Zeitpunkte (Name, Beginn, Ende) in Ortszeit stehen.
	"""
	from diakronos_app.sicherung.einstellungen import jetzt_ortszeit

	return jetzt_ortszeit()


def _merker_client():
	"""Redis-Client des Tagesmerkers (eigene Funktion — Tests ersetzen sie)."""
	from redis import Redis

	from diakronos_app.settings import settings

	return Redis.from_url(settings.redis_url)


def schon_gesichert(heute: str) -> bool:
	"""Wurde heute (``JJJJ-MM-TT``) bereits automatisch gesichert?"""
	try:
		wert = _merker_client().get(SICHERUNG_MERKER)
	except Exception:  # noqa: BLE001 — ohne Merker lieber sichern als nicht
		logger.warning("Sicherungsmerker nicht lesbar — es wird gesichert.")
		return False
	gespeichert = wert.decode() if isinstance(wert, bytes) else (wert or "")
	return gespeichert == heute


def merke_gesichert(heute: str, tage: int) -> None:
	"""Tagesmerker setzen (Lebensdauer: ``tage``, mindestens 2 Tage)."""
	try:
		_client = _merker_client()
		_client.set(SICHERUNG_MERKER, heute, ex=max(172800, (int(tage) + 2) * 86400))
	except Exception as fehler:  # noqa: BLE001
		logger.warning("Sicherungsmerker nicht setzbar: %s", fehler)


def sicherung_faellig(jetzt=None) -> bool:
	"""Ist die automatische Sicherung jetzt faellig?

	Faellig heisst: automatisch eingeschaltet UND die eingestellte Uhrzeit ist
	erreicht (oder vorbei) UND heute ist noch nicht gesichert. Der
	"Nachtrag"-Fall ist Absicht: startet der Scheduler um 04:30 neu und die
	Sicherung von 03:00 fehlt, holt er sie nach. Er holt sie aber nicht am
	selben Tag zweimal (Tagesmerker).
	"""
	from diakronos_app.db import SessionLocal
	from diakronos_app.sicherung.einstellungen import holen_oder_anlegen, uhrzeit_teile

	zeit = jetzt or _jetzt_ortszeit()
	sess = SessionLocal()
	try:
		zeile = holen_oder_anlegen(sess, jetzt=zeit)
		if not zeile.automatisch:
			return False
		stunde, minute = uhrzeit_teile(zeile.uhrzeit)
	finally:
		sess.close()

	if (zeit.hour, zeit.minute) < (stunde, minute):
		return False
	return not schon_gesichert(zeit.strftime("%Y-%m-%d"))


def job_datensicherung(jetzt=None) -> None:
	"""Minuten-Job: sichert, wenn die eingestellte Uhrzeit erreicht ist."""
	from diakronos_app.sicherung import lauf as sicherungslauf

	try:
		if not sicherung_faellig(jetzt):
			return
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		logger.exception("Pruefung der Datensicherung fehlgeschlagen")
		return

	from diakronos_app.db import SessionLocal
	from diakronos_app.sicherung.einstellungen import holen_oder_anlegen

	zeit = jetzt or _jetzt_ortszeit()
	sess = SessionLocal()
	try:
		zeile = holen_oder_anlegen(sess, jetzt=zeit)
		tage = int(zeile.aufbewahrung_tage)
	finally:
		sess.close()

	# N3 (BACKUP-1b): der Merker wird ERST gesetzt, wenn die Sperre wirklich
	# steht. Scheitert der Lauf an Sperre/Redis (SperreBesteht,
	# SperreNichtVerfuegbar), bleibt der Tag offen — der naechste Tick
	# versucht es erneut, statt den Tag stillschweigend ohne Sicherung zu
	# beenden. Damit der Ausfall nicht unbemerkt bleibt, werden die System
	# Manager benachrichtigt.
	try:
		ergebnis = sicherungslauf.fuehre_aus(
			ausloeser=sicherungslauf.AUSLOESER_AUTOMATISCH, jetzt=zeit,
			sperre_gesetzt=lambda: merke_gesichert(zeit.strftime("%Y-%m-%d"), tage),
		)
	except Exception:  # noqa: BLE001
		logger.exception("Job Datensicherung fehlgeschlagen")
		return
	if ergebnis.ok:
		logger.info(
			"Job Datensicherung fertig (%s, %s Bytes, %s alte entfernt).",
			ergebnis.name, ergebnis.groesse_bytes, len(ergebnis.entfernt),
		)
	else:
		logger.error("Job Datensicherung fehlgeschlagen: %s", ergebnis.meldung)


def build_scheduler() -> BlockingScheduler:
	"""Scheduler mit den taeglichen Jobs (ohne zu starten)."""
	scheduler = BlockingScheduler(timezone="UTC")
	scheduler.add_job(
		tick, "interval", minutes=1, id="tick", max_instances=1,
		# `next_run_time=None` haelt den Platzhalter-Bus JETZT absichtlich an:
		# er protokolliert nur und hat keine Aufgabe. Achtung — dieselbe
		# Angabe beim Datensicherungs-Job waere ein Fehler (der Job liefe nie).
		next_run_time=None,
	)
	for fn, job_id in DAILY_JOBS:
		scheduler.add_job(
			fn,
			"cron",
			hour=DAILY_HOUR,
			minute=DAILY_MINUTE,
			id=job_id,
			max_instances=1,
			coalesce=True,
			misfire_grace_time=3600,
		)
	# BACKUP-1: Minuten-Job statt Cron — die Uhrzeit steht in der Datenbank und
	# ist ohne Neustart aenderbar (Modulkopf).
	#
	# APScheduler: `next_run_time=None` heisst "angehalten" — ein solcher Job
	# laeuft NIE (am 2026-10-20 im Teststack geprueft: kein einziger Lauf,
	# obwohl faellig). Deshalb wird der erste Lauf bewusst NICHT angegeben:
	# der Intervall-Trigger setzt ihn auf jetzt + 1 Minute, und der prueft dann
	# nur die Faelligkeit — ein frisch gestarteter Scheduler holt eine
	# verpasste Sicherung beim naechsten Tick nach, nicht sofort beim
	# Hochfahren des Stacks.
	scheduler.add_job(
		job_datensicherung,
		"interval",
		minutes=1,
		id="datensicherung",
		max_instances=1,
		coalesce=True,
	)
	return scheduler


def main() -> None:
	scheduler = build_scheduler()
	logger.info(
		"scheduler gestartet (interval=1min, %s taegliche Jobs um %02d:%02d UTC)",
		len(DAILY_JOBS),
		DAILY_HOUR,
		DAILY_MINUTE,
	)
	try:
		scheduler.start()
	except (KeyboardInterrupt, SystemExit):
		logger.info("scheduler gestoppt")


if __name__ == "__main__":
	main()
