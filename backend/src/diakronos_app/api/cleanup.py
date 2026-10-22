"""Portierung von `diakonos/api/cleanup.py` (P6a) — Aufraeum-Nachtjob.

Quelle (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/cleanup.py`

Der Altcode registriert die Funktion in `hooks.py` als taeglichen Job:

    scheduler_events = {"daily": [
        ...,
        "diakronos.diakonos.api.cleanup.delete_alte_anmeldeanfragen",
    ]}

Kein HTTP-Endpunkt (`@whitelist` fehlt — wie im Original).

FRISTENLOGIK 1:1 aus dem Original:
* Cutoff = **heutiges Datum minus 14 Tage** (`add_days(nowdate(), -14)`), also
  ein DATUM, kein Zeitstempel.
* Geloescht werden `Anmeldung`-Zeilen mit `creation < cutoff` UND
  `status in ("Anmeldeanfrage", "Abgelehnt")`. Verglichen wird auf
  `creation` (Anlagedatum), NICHT auf `anmeldedatum`.
* Fehler beim Loeschen EINER Zeile brechen den Lauf nicht ab: die Zeile wird
  geloggt, der Rest laeuft weiter (Original `try/except` in der Schleife).

IDEMPOTENZ: geloeschte Zeilen sind weg — ein zweiter Lauf findet dieselben Namen
nicht mehr (`_delete_doc` kehrt bei fehlender Zeile still zurueck).

Frappe-Aufruf -> Compat-Schicht:

    frappe.get_all("Anmeldung", filters=[...], pluck="name") -> get_all(..., pluck="name")
    frappe.delete_doc("Anmeldung", name, ignore_permissions=True)
                                                             -> _delete_doc(...)
    frappe.db.commit()                                       -> (SQLAlchemy je Satz)
    frappe.log_error(...)                                    -> log_error(...)
    frappe.logger().info(...)                                -> stdlib-logging
    frappe.utils.add_days / nowdate()                        -> _cutoff_date()
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.cleanup"

import logging
from datetime import date, timedelta

from diakronos_app.frappe_compat.api_helpers import _delete_doc, log_error
from diakronos_app.frappe_compat.query import get_all

logger = logging.getLogger("diakronos_app.cleanup")

DOCTYPE_ANMELDUNG = "Anmeldung"
AUFBEWAHRUNG_TAGE = 14  # Original: `add_days(nowdate(), -14)`
ALTE_STATUS = ["Anmeldeanfrage", "Abgelehnt"]  # Original-Filter

# Kind-Tabellen von `Anmeldung` (Frappe `on_trash` raeumt sie mit ab; das
# Standalone-Backend hat keine FK-Kaskade). Quelle: `models/_mapping.json` —
# beide Kind-DocTypes tragen `parentfield` und haengen an `Anmeldung`.
_ANMELDUNG_KIND_TABELLEN: dict[str, str] = {
	"Anmeldung Kind": "kinder",
	"Anmeldung Antwort": "antworten",
}


def _cutoff_date() -> date:
	"""`add_days(nowdate(), -14)` — heutiges Datum minus Aufbewahrungsfrist."""
	return date.today() - timedelta(days=AUFBEWAHRUNG_TAGE)


def _delete_anmeldung(name: str) -> None:
	"""`frappe.delete_doc("Anmeldung", name, ignore_permissions=True)`.

	Raeumt die Kind-Zeilen vorher weg: `frappe_compat.api_helpers._delete_doc` kennt nur die
	Kind-Tabellen von `Element`, nicht die von `Anmeldung`. Ohne das blieben
	`Anmeldung Kind` / `Anmeldung Antwort` als Waisen zurueck (im Live-Schema
	existiert KEIN Fremdschluessel, s. `inventar/live_schema_ist.tsv`).
	"""
	from diakronos_app.db import SessionLocal
	from diakronos_app.frappe_compat.registry_gen import model_for

	sess = SessionLocal()
	try:
		for child_doctype, parentfield in _ANMELDUNG_KIND_TABELLEN.items():
			kind = model_for(child_doctype)
			sess.execute(
				kind.__table__.delete().where(
					kind.parent == name,
					kind.parentfield == parentfield,
				)
			)
		sess.commit()
	finally:
		sess.close()

	_delete_doc(DOCTYPE_ANMELDUNG, name)


def delete_alte_anmeldeanfragen() -> int:
	"""Taeglicher Job: Anmeldeanfragen > 14 Tage mit Status 'Anmeldeanfrage'
	oder 'Abgelehnt' loeschen.

	Gibt die Anzahl der geloeschten Zeilen zurueck (der Scheduler loggt sie) —
	das Original loggt dieselbe Zahl, hatte aber keinen Rueckgabewert.
	"""
	cutoff = _cutoff_date()

	# `creation < cutoff` + `status in [...]` — beides in der Abfrage, damit ein
	# zweiter Lauf die bereits geloeschten Zeilen nicht mehr findet.
	anmeldungen = get_all(
		DOCTYPE_ANMELDUNG,
		filters=[
			["creation", "<", cutoff],
			["status", "in", ALTE_STATUS],
		],
		pluck="name",
	)

	deleted = 0
	for name in anmeldungen:
		try:
			_delete_anmeldung(str(name))
			deleted += 1
		except Exception:  # noqa: BLE001 — eine kaputte Zeile stoppt den Lauf nicht
			log_error(f"Fehler beim Loeschen von Anmeldung {name}")

	if deleted:
		logger.info("Cleanup: %s alte Anmeldeanfragen geloescht.", deleted)

	return deleted


def delete_alte_zuordnung_ablehnungen() -> int:
	"""Taeglicher Job: abgelehnte Anbieter-Zuordnungen nach Frist entfernen (N-2).

	`auth_zuordnung_ablehnung` macht abgelehnte OIDC-Zuordnungen fuer die
	Verwaltung sichtbar (R-N8). Die Zeilen sind kein Einwilligungs-Nachweis,
	sondern ein Arbeitshinweis — sie brauchen eine Aufbewahrungsfrist. Frist aus
	`settings.auth_zuordnung_ablehnung_tage` (Default 90 Tage); `0` schaltet sie
	ausdruecklich ab (keine Loeschung).

	Geloescht wird auf `zuletzt` (dem letzten Versuch) — faellt dieses Feld aus,
	auf `created`. Der Vergleich ist ein Datum (`< cutoff`) wie in
	`delete_alte_anmeldeanfragen`; idempotent, weil geloeschte Zeilen weg sind.

	Rueckgabe: Zahl der geloeschten Zeilen (der Scheduler loggt sie).
	"""
	from diakronos_app.settings import settings

	tage = int(getattr(settings, "auth_zuordnung_ablehnung_tage", 90) or 0)
	if tage <= 0:
		return 0
	cutoff = date.today() - timedelta(days=tage)

	from diakronos_app.db import SessionLocal
	from diakronos_app.models.auth_oidc import ZuordnungsAblehnung
	from sqlalchemy import delete, or_

	sess = SessionLocal()
	try:
		ergebnis = sess.execute(
			delete(ZuordnungsAblehnung).where(
				or_(
					ZuordnungsAblehnung.zuletzt < cutoff,
					ZuordnungsAblehnung.zuletzt.is_(None)
					& (ZuordnungsAblehnung.created < cutoff),
				)
			)
		)
		sess.commit()
		geloescht = int(ergebnis.rowcount or 0)
	except Exception:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht toeten
		sess.rollback()
		log_error("Cleanup abgelehnter Zuordnungen fehlgeschlagen")
		raise
	finally:
		sess.close()

	if geloescht:
		logger.info("Cleanup: %s abgelehnte Zuordnungen geloescht.", geloescht)
	return geloescht


__all__ = [
	"FRAPPE_MODULE",
	"AUFBEWAHRUNG_TAGE",
	"ALTE_STATUS",
	"delete_alte_anmeldeanfragen",
	"delete_alte_zuordnung_ablehnungen",
]
