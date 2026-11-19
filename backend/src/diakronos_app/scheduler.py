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


def job_papierkorb_aufraeumen() -> None:
	"""Taeglicher Job (UX2b): Papierkorb-Zeilen nach 7 Tagen endgueltig entfernen.

	Die Frist ist die Fachentscheidung aus Karte UX2b (hoechstens 7 Tage,
	``papierkorb.AUFBEWAHRUNG_TAGE``). Der Job ist idempotent: was weg ist,
	ist weg; ein zweiter Lauf findet nichts mehr.
	"""
	from diakronos_app import papierkorb

	try:
		count = papierkorb.aufraeumen()
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		logger.exception("Job papierkorb_aufraeumen fehlgeschlagen")
		return
	logger.info("Job papierkorb_aufraeumen fertig (%s endgueltig entfernt).", count)


def job_gastlinks_aufraeumen() -> None:
	"""Taeglicher Job (R-11f): abgelaufene/widerrufene Gast-Links nach 30 Tagen
	entfernen (``rechte.gastlinks.AUFBEWAHRUNG_TAGE``). Idempotent."""
	from diakronos_app.rechte import gastlinks

	try:
		count = gastlinks.aufraeumen()
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		logger.exception("Job gastlinks_aufraeumen fehlgeschlagen")
		return
	logger.info("Job gastlinks_aufraeumen fertig (%s entfernt).", count)


# ── CHAT-4a: gebuendelte Glocke ─────────────────────────────────────────────

#: Abstand des Glocken-Jobs in Minuten. Bewusst 1 Minute statt 2: die Ruhezeit
#: betraegt 5 Minuten, und ein 2‑Minuten-Takt verspaetete die Glocke im
#: unguenstigsten Fall auf knapp 7 Minuten (Konzept 1/S1 sagt „nach 5 Minuten
#: Ruhe“). Der Job liest je Lauf nur die Gespraechsliste und die
#: faelligen Kandidaten — ein Index-Zugriff.
GLOCKE_INTERVALL_MINUTEN = 1


def job_chat_glocken_buendeln() -> None:
	"""Minuten-Job: EINE gebuendelte Glocke je Gespraech und Person (CHAT-4a).

	Die Fachlogik steht in ``api.chat.chat_glocken_buendeln``; hier steht nur
	der Schutz, dass ein Fehler den Scheduler nicht toetet (Muster der
	uebrigen Jobs).
	"""
	from diakronos_app.api import chat as chat_api

	try:
		count = chat_api.chat_glocken_buendeln()
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		logger.exception("Job chat_glocken_buendeln fehlgeschlagen")
		return
	if count:
		logger.info("Job chat_glocken_buendeln fertig (%s Glocken).", count)
def job_umfragen_schliessen() -> None:
	"""Taeglicher Job (CHAT-5): Umfragen zur Frist schliessen.

	Kein eigener Zeitgeber und keine eigene Tabelle: der Job ruft
	``api.chat.schliesse_faellige``, das ``geschlossen_am`` auf die FRIST
	schreibt (nicht auf "jetzt") und ``geschlossen_von`` leer laesst
	("automatisch heisst automatisch"). Idempotent: der Zustand
	``geschlossen_am IS NULL`` faellt nach dem ersten Lauf weg.
	"""
	from diakronos_app.api.chat import schliesse_faellige

	try:
		count = schliesse_faellige()
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		logger.exception("Job umfragen_schliessen fehlgeschlagen")
		return
	logger.info("Job umfragen_schliessen fertig (%s geschlossen).", count)


# (Job-Funktion, Job-Id) — die Registrierung ist damit an EINER Stelle und
# fuer Tests pruefbar, ohne den BlockingScheduler zu starten.
DAILY_JOBS: list[tuple] = [
	(job_anonymize_expired_audit_logs, "anonymize_expired_audit_logs"),
	(job_delete_alte_anmeldeanfragen, "delete_alte_anmeldeanfragen"),
	(job_delete_alte_zuordnung_ablehnungen, "delete_alte_zuordnung_ablehnungen"),
	(job_papierkorb_aufraeumen, "papierkorb_aufraeumen"),
	(job_gastlinks_aufraeumen, "gastlinks_aufraeumen"),
	(job_umfragen_schliessen, "umfragen_schliessen"),
]

#: MINUTEN-Jobs (Intervall in Minuten, Job-Funktion, Job-Id) — dieselbe eine
#: Stelle wie ``DAILY_JOBS``, gleiche Pruefbarkeit. CHAT-4a ergaenzt die
#: gebuendelte Glocke; die Datensicherung bleibt aus Kompatibilitaetsgruenden
#: in ``build_scheduler`` (eigener Merker, eigene Faelligkeitspruefung).
MINUTEN_JOBS: list[tuple] = [
	(GLOCKE_INTERVALL_MINUTEN, job_chat_glocken_buendeln, "chat_glocken_buendeln"),
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
	# CHAT-4a: die gebuendelte Glocke und weitere Minuten-Jobs aus
	# ``MINUTEN_JOBS`` — Registrierung an EINER Stelle, in Tests pruefbar.
	# Faelligkeit („5 Minuten Ruhe“) steht im Fachcode und wird je Lauf
	# geprueft. `coalesce=True` verhindert nachgeholte Laeufe; doppelt glocken
	# kann der Job ohnehin nicht (`chat_glocke.stand`).
	for minuten, fn, job_id in MINUTEN_JOBS:
		scheduler.add_job(
			fn,
			"interval",
			minutes=minuten,
			id=job_id,
			max_instances=1,
			coalesce=True,
			misfire_grace_time=120,
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
