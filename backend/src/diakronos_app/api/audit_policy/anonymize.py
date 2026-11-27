"""Portierung von `diakonos/api/audit_policy/anonymize.py` (P6a) — DSGVO-Nachtjob.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/audit_policy/anonymize.py`

Der Altcode registriert die Funktion in `hooks.py` als taeglichen
Scheduler-Job:

    scheduler_events = {"daily": [
        "diakronos.diakonos.api.audit_policy.anonymize.anonymize_expired_audit_logs",
        ...
    ]}

Im Standalone-Backend ruft `diakronos_app/scheduler.py` dieselbe Funktion
taeglich auf; es gibt KEINEN HTTP-Endpunkt (`@whitelist` fehlt — wie im
Original, das ist ein Job, keine API).

FRISTENLOGIK — **feste Frist, nicht einstellbar** (ABN-5/W3, Entscheidung des
Operators):
* Das Original las `Diakronos Einstellungen.audit_log_retention_days`. Dieses
  Feld existiert im Standalone weder im Modell (`models/diakronos.py`,
  `DiakronosEinstellungen`) noch in einer Alembic-Migration. Der alte Code hat
  es trotzdem gelesen und fiel deshalb immer auf den Default zurueck — die
  zugesagte "Einstellbarkeit" war eine Fiktion.
* Deshalb wird das Feld **nicht mehr gelesen**: die Frist steht als benannte
  Konstante `AUDIT_LOG_AUFBEWAHRUNG_TAGE = 1095` (3 Jahre). Wer sie aendert,
  aendert eine Zahl im Code und die Doku dazu — nicht eine Einstellung.
* Cutoff = `jetzt - AUDIT_LOG_AUFBEWAHRUNG_TAGE`; anonymisiert werden Eintraege
  mit `anonymized_at is NULL` UND `zeitstempel < cutoff` — **strikt kleiner**,
  also ein Eintrag GENAU auf der Grenze bleibt unangetastet.
* Der fruehere Opt-out (`Wert <= 0` -> gar nichts tun) entfaellt mit dem Feld.
  Abschalten geht nur noch ueber den Scheduler (Job nicht registrieren).

SCHEMA-REALITAET (geprueft, NICHT angenommen):
`inventar/live_schema_ist.tsv` fuehrt `tabAudit Log` mit den hier benutzten
Spalten `zeitstempel, actor, target_user, old_value, new_value, confirm_reason,
ip_address, user_agent, anonymized_at`. Das DocType-JSON ist nicht die Wahrheit,
das live-Schema schon — beide stimmen hier ueberein.

IDEMPOTENZ (Kartenanforderung): die Auswahl filtert hart auf
`anonymized_at IS NULL`. Ein zweiter Lauf findet dieselben Zeilen deshalb nicht
mehr und schreibt nichts. Zusaetzlich ueberspringt `_hash_identifier` einen
Wert, der bereits die Form `sha256:<hex>` hat — so bleibt die Pseudonymisierung
stabil, falls ein Eintrag wider Erwarten erneut durchlaeuft.

Frappe-Aufruf -> Compat-Schicht:

    frappe.db.get_single_value("Diakronos Einstellungen", feld) -> _single_field(...)
    frappe.get_all("Audit Log", filters=..., fields=..., limit=1000)
                                                                -> query.get_all(...)
    frappe.db.set_value(dt, name, {feld: wert}, update_modified=False)
                                                                -> _set_fields(...)
    frappe.db.commit()                                          -> (SQLAlchemy je Satz)
    frappe.logger().info(...)                                   -> stdlib-logging
    frappe.local.site                                           -> "diakronos" (fest)
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.audit_policy.anonymize"

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from diakronos_app.frappe_compat.api_helpers import _now
from diakronos_app.frappe_compat.query import get_all
from diakronos_app.frappe_compat.registry_gen import column_names, model_for

logger = logging.getLogger("diakronos_app.audit_policy")

DOCTYPE_AUDIT_LOG = "Audit Log"

# Aufbewahrungsfrist der Audit-Logs in Tagen — **feste Konstante, keine
# Einstellung** (ABN-5/W3). Das fruehere Feld
# `Diakronos Einstellungen.audit_log_retention_days` ist im Standalone nicht
# vorhanden (weder Modell noch Migration) und wird hier bewusst nicht mehr
# gelesen. 1095 Tage = 3 Jahre. Geaendert wird hier im Code, nicht in der DB.
AUDIT_LOG_AUFBEWAHRUNG_TAGE = 1095

# Alter Name (Original-Sprache); bleibt als Alias, damit bestehende Importe und
# Tests nicht brechen. Neue Stellen nutzen AUDIT_LOG_AUFBEWAHRUNG_TAGE.
DEFAULT_RETENTION_DAYS = AUDIT_LOG_AUFBEWAHRUNG_TAGE
BATCH_LIMIT = 1000  # Original `limit=1000`

# Site-Salt des Originals (`frappe.local.site or "diakronos"`). Im Standalone
# gibt es genau EINE Instanz; der Wert ist damit konstant und deterministisch.
_SITE_SALT = "diakronos"


def _site_now() -> datetime:
	"""`frappe.utils.now_datetime()` — naiver UTC-Zeitstempel."""
	return _now()


def _retention_days() -> int:
	"""Aufbewahrungsfrist der Audit-Logs in Tagen — fest 1095 (3 Jahre).

	ABN-5/W3: Es gibt **kein** Einstellungsfeld. Das fruehere Lesen ueber
	`Diakronos Einstellungen.audit_log_retention_days` ist entfernt, weil das
	Feld weder im Modell noch in einer Migration existiert — der Wert war
	damit ohnehin immer der Default. Die Frist ist die Konstante
	`AUDIT_LOG_AUFBEWAHRUNG_TAGE`.

	Die Funktion bleibt als eine benannte Stelle: ein Test prueft, dass sie
	1095 liefert und dass dabei KEIN Feld gelesen wird (Mutationsprobe).
	"""
	return AUDIT_LOG_AUFBEWAHRUNG_TAGE


def _hash_identifier(value):
	"""Deterministischer SHA-256-Hash eines Identifiers mit Site-Salt.

	`sha256:<hex>` ist die exakte Ausgabeform des Originals. Ein bereits
	gehashter Wert wird unveraendert zurueckgegeben (Idempotenz, s. Modul-Doc).
	"""
	if not value:
		return None
	text_value = str(value)
	if text_value.startswith("sha256:"):
		return text_value
	return f"sha256:{hashlib.sha256((text_value + _SITE_SALT).encode()).hexdigest()}"


def _set_fields(name: str, values: dict[str, Any]) -> None:
	"""`frappe.db.set_value(dt, name, {feld: wert}, update_modified=False)`."""
	from diakronos_app.db import SessionLocal

	model = model_for(DOCTYPE_AUDIT_LOG)
	cols = column_names(DOCTYPE_AUDIT_LOG)
	data = {k: v for k, v in values.items() if k in cols}

	sess = SessionLocal()
	try:
		obj = sess.get(model, name)
		if obj is None:
			return
		for key, value in data.items():
			setattr(obj, key, value)
		sess.commit()
	finally:
		sess.close()


def anonymize_expired_audit_logs() -> int:
	"""Taeglicher DSGVO-Job: Audit-Logs aelter als die Frist pseudonymisieren.

	Kein physisches Loeschen (Nachweispflicht), sondern Pseudonymisierung:
	`actor`/`target_user` werden gehasht, Freitextinhalte auf `***` gesetzt,
	IP und User-Agent geloescht, `anonymized_at` gestempelt.

	Gibt die Anzahl der anonymisierten Eintraege zurueck (der Scheduler loggt
	sie) — das Original loggt dieselbe Zahl, hatte aber keinen Rueckgabewert.
	"""
	retention_days = _retention_days()

	# Kein Opt-out mehr: die Frist ist fest (ABN-5/W3). Ein Abschalten waere
	# eine Aenderung hier im Code, nicht ein Wert in der Datenbank.
	cutoff_date = _site_now() - timedelta(days=retention_days)

	# `anonymized_at is not set` + `zeitstempel < cutoff` — beides hart in der
	# Abfrage, damit ein zweiter Lauf nichts mehr findet (Idempotenz).
	logs = get_all(
		DOCTYPE_AUDIT_LOG,
		filters={
			"anonymized_at": ["is", "not set"],
			"zeitstempel": ["<", cutoff_date],
		},
		fields=[
			"name", "actor", "target_user", "old_value", "new_value",
			"confirm_reason", "ip_address", "user_agent",
		],
		limit_page_length=BATCH_LIMIT,
	)

	anonymized = 0
	for log in logs:
		_set_fields(
			log["name"],
			{
				"actor": _hash_identifier(log["actor"]),
				"target_user": _hash_identifier(log["target_user"]),
				"old_value": "***" if log["old_value"] else None,
				"new_value": "***" if log["new_value"] else None,
				"confirm_reason": "***" if log["confirm_reason"] else None,
				"ip_address": None,
				"user_agent": None,
				"anonymized_at": _site_now(),
			},
		)
		anonymized += 1

	if anonymized:
		logger.info(
			"Anonymisiert %s Audit-Log-Eintraege (alter als %s Tage).",
			anonymized,
			retention_days,
		)

	return anonymized


__all__ = [
	"FRAPPE_MODULE",
	"AUDIT_LOG_AUFBEWAHRUNG_TAGE",
	"DEFAULT_RETENTION_DAYS",
	"anonymize_expired_audit_logs",
]
