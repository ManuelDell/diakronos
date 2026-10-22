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

FRISTENLOGIK — 1:1 aus dem Original uebernommen (nicht geraten):
* Frist aus `Diakronos Einstellungen.audit_log_retention_days`.
* Ist das Feld leer/`None`/nicht lesbar -> Default **1095 Tage (3 Jahre)**.
* Ist der Wert `<= 0` -> **Fruehaustieg, gar nichts wird anonymisiert**
  (so dokumentiert das Original den expliziten Opt-out).
* Sonst: Cutoff = `jetzt - retention_days`; anonymisiert werden Eintraege mit
  `anonymized_at is NULL` UND `zeitstempel < cutoff` — **strikt kleiner**, also
  ein Eintrag GENAU auf der Grenze bleibt unangetastet.

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
# Der Single (Ein-Zeilen-DocType) mit der Frist-Konfiguration.
_EINSTELLUNGEN = "Diakronos Einstellungen"
DEFAULT_RETENTION_DAYS = 1095  # 3 Jahre — Original-Default
BATCH_LIMIT = 1000  # Original `limit=1000`

# Site-Salt des Originals (`frappe.local.site or "diakronos"`). Im Standalone
# gibt es genau EINE Instanz; der Wert ist damit konstant und deterministisch.
_SITE_SALT = "diakronos"


def _cint(value: Any, default: int = 0) -> int:
	"""`frappe.utils.cint` — tolerante Ganzzahl."""
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def _site_now() -> datetime:
	"""`frappe.utils.now_datetime()` — naiver UTC-Zeitstempel."""
	return _now()


def _single_field(feld: str):
	"""Ein Feld des Singles `Diakronos Einstellungen` lesen (oder `None`).

	`frappe.db.get_single_value("Diakronos Einstellungen", feld)` -> die
	Einstellungszeile ist wie bei `api/orgchart_api.py` und
	`api/kronos/permissions.py` ein Ein-Zeilen-Datensatz mit
	`name == DocType-Name`; gelesen wird ueber `query.get_value`. Kein rohes SQL.
	Fehlt der Wert, liefert die Funktion `None` — das Original faengt denselben
	Fall per `try/except`.
	"""
	from diakronos_app.frappe_compat.query import get_value

	try:
		return get_value(_EINSTELLUNGEN, _EINSTELLUNGEN, feld)
	except Exception:  # noqa: BLE001 — Original faengt hier ebenfalls alles ab
		return None


def _retention_days() -> int:
	"""Frist in Tagen: gesetzter Wert, sonst Default 1095. 1:1 wie im Original.

	Reihenfolge exakt nach Original:
	* Wert lesen (`_cint` -> `0` bei `None`/unparsebar)
	* `retention_days or DEFAULT` — ABER der Original-Vergleich auf `<= 0`
	  (Fruehaustieg) steht in `anonymize_expired_audit_logs` NACH diesem
	  Default-Schritt. Damit ist der Default nur fuer "nicht gesetzt" wirksam
	  und ein expliziter Opt-out kann NUR ueber das Vorzeichen entschieden
	  werden. Deshalb hier NICHT `or`, sondern der Default nur bei
	  fehlendem/ungueltigem Wert.
	"""
	raw = _single_field("audit_log_retention_days")
	if raw is None or raw == "":
		return DEFAULT_RETENTION_DAYS
	try:
		return int(raw)
	except (TypeError, ValueError):
		return DEFAULT_RETENTION_DAYS


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

	if retention_days <= 0:
		# Expliziter Opt-out: nichts tun (Original-Zeile 18/19).
		return 0

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
	"DEFAULT_RETENTION_DAYS",
	"anonymize_expired_audit_logs",
]
