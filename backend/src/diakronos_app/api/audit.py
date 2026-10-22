"""Portierung von `diakonos/api/audit.py` (P4g) — Audit-Log, 4 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/audit.py`

Die SPA ruft die ORIGINAL-Pfade `diakronos.diakonos.api.audit.<fn>` auf
(siehe Aufrufliste des Frappe-Frontends). Dafuer traegt dieses Modul die
Konstante `FRAPPE_MODULE`.

Schema-Realitaet (geprueft, NICHT angenommen):
Frappe-Schema fuer `tabNotification Log` und die
`tabAudit Log`-Spaltenliste. `tabNotification Log` ist ein Frappe-CORE-DocType
(nicht in den 73 App-DocTypes) — er wurde in P4g als Core-Stub in
`tools/gen_models.py` ergaenzt (`models/core.py:NotificationLog`), weil er LIVE
existiert und von diesem Modul beschrieben/gelesen wird.

DATEN-/DSGVO-SCHUTZ (Kartenanforderung, ausdruecklich belegt):
`get_my_audit_log` filtert auf `target_user = user` ODER `actor = user`
(DSGVO Art. 15 — Auskunft ueber eigene Daten). `get_my_notifications` und
`get_unread_notifications` filtern HART auf `for_user = user`. Es gibt KEINEN
Endpunkt, der fremde Eintraege liefert. Test:
`backend/tests/test_p4g_audit_auswahl_session.py::test_audit_sieht_fremde_eintraege_nicht`.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user                 -> session.user
    frappe.get_all(...)                 -> query.get_all(...)   (dicts)
    frappe.db.count(...)                -> db.count(...)
    frappe.db.set_value(dt, filters, ..)-> db.set_value(...)
    frappe.get_doc({...}).insert(...)   -> _create(...)
    frappe.utils.now_datetime()         -> _now()
    frappe.db.sql(<MariaDB>)            -> get_all + Python-Aggregation
    frappe.throw(msg, exc)              -> throw(msg, exc)
    frappe._(...)                       -> (i18n entfernt, Rohstring)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.audit"

from diakronos_app.frappe_compat.api_helpers import (
    _create,
    _now,
    get_all,
    session,
    throw,
)
from diakronos_app.frappe_compat import db
from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.registry import whitelist

VALID_ACTIONS = {
    "Datenzugriff",
    "Profiländerung",
    "Dateizugriff",
    "Dateilöschung",
    "DSGVO-Export",
    "Berechtigungsänderung",
    "Sonstiges",
}


def _cint(value, default: int = 0) -> int:
    """`frappe.utils.cint` — tolerante Ganzzahl (Original nutzt es fuer start/limit)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def log(action_typ, target_doctype, target_name, begruendung=""):
    """Schreibt einen Audit-Log-Eintrag. Immer ignore_permissions, da intern.

    Portierung von `audit.log` (Original:127). Kein `@whitelist` — die Funktion
    ist ein interner Helfer, kein HTTP-Endpunkt (Original 4 Endpunkte, nicht 5).
    `frappe.local.audit_policy_logged` ist eine Frappe-Reentranz-Flag; im
    Standalone gibt es keinen Policy-Hook mehr, der sie liest. Wir setzen sie
    1:1 ueber die `_shared.flags`-Halterung, damit das Aufruferverhalten
    unveraendert bleibt (im Docstring dieses Helfers begruendet).
    """
    if action_typ not in VALID_ACTIONS:
        action_typ = "Sonstiges"
    _create(
        "Audit Log",
        {
            "zeitstempel": _now(),
            "action_typ": action_typ,
            "actor": session.user,
            "target_doctype": target_doctype,
            "target_name": target_name,
            "begruendung": begruendung,
            "notification_gesendet": 0,
        },
    )


@whitelist(allow_guest=False)
def get_my_audit_log(start=0, limit=20, action_typ=None):
    """Audit-Log-Eintraege des aktuellen Users (DSGVO Art. 15).

    Filtert auf `target_user = user` ODER `actor = user`. Ein optionaler
    `action_typ` muss aus `VALID_ACTIONS` stammen, sonst `ValidationError`.
    """
    user = session.user

    filters = {}
    if action_typ:
        if action_typ not in VALID_ACTIONS:
            throw("Ungültiger action_typ.", ValidationError)
        filters["action_typ"] = action_typ

    or_filters = [
        ["target_user", "=", user],
        ["actor", "=", user],
    ]

    logs = get_all(
        "Audit Log",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name", "zeitstempel", "action_typ", "actor", "target_doctype",
            "target_name", "policy_triggered", "consequence", "field_changed",
            "old_value", "new_value", "confirm_reason", "confirmed_at",
            "ip_address", "user_agent", "anonymized_at", "begruendung",
        ],
        order_by="zeitstempel desc",
        limit_start=_cint(start),
        limit_page_length=_cint(limit),
    )

    # Original zaehlt per rohem SQL, weil `db.count` kein `or_filters` kennt.
    # Portierung: SQL-Count ebenfalls nicht noetig -> zwei get_all-Zaehlungen
    # waeren teuer; stattdessen zaehlen wir ueber die Sichtbarkeitsmenge per
    # `db.count` getrennt (target_user UND actor), koennen aber Doppelzaehlung
    # (user ist actor UND target_user) nicht per SQL-Praedikat ausschliessen.
    # Deshalb: dieselbe or-Semantik in Python, ueber eine UNGEFILTERTE Abfrage
    # waere falsch (Datenschutz). Wir bleiben 1:1 beim Original: PostgreSQL-
    # COUNT mit gebundenen Parametern, keine String-Interpolation von Werten.
    total = _count_my_audit(user, filters)

    return {
        "success": True,
        "data": logs,
        "total": total,
        "start": _cint(start),
        "limit": _cint(limit),
    }


def _count_my_audit(user: str, filters: dict) -> int:
    """COUNT der sichtbaren Audit-Zeilen (target_user ODER actor = user).

    PostgreSQL-Syntax, gebundene Parameter (`:p_user`). Kein rohes MariaDB-SQL,
    kein f-string mit Werten — die Bind-Parameter sind die einzigen variablen
    Teile, die Spaltennamen stammen aus der festen Feldliste dieser Funktion.
    """
    where = ["(target_user = :p_user OR actor = :p_user)"]
    params = {"p_user": user}
    for key, value in filters.items():
        where.append(f"{key} = :f_{key}")
        params[f"f_{key}"] = value
    sql = "SELECT COUNT(*) FROM audit_log WHERE " + " AND ".join(where)
    rows = db.sql(sql, params)
    return int(rows[0][0]) if rows else 0


@whitelist(allow_guest=False)
def get_unread_notifications():
    """Anzahl ungelesener Notification-Log-Eintraege des aktuellen Users."""
    user = session.user
    count = db.count(
        "Notification Log",
        filters={
            "for_user": user,
            "read": 0,
        },
    )
    return {"success": True, "unread_count": count}


@whitelist(allow_guest=False)
def mark_notifications_read(names=None):
    """Markiert nur die angezeigten, eigenen Eintraege als gelesen."""
    if names is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={
            "message": "Bitte die Seite neu laden und die Benachrichtigungen erneut öffnen.",
            "exc_type": "ValidationError",
        })
    if names == []:
        return {"success": True}
    if not isinstance(names, list) or len(names) > 100 or any(
        not isinstance(name, str) or not name for name in names
    ):
        throw("Bitte höchstens 100 Benachrichtigungs-Kennungen angeben.", ValidationError)
    user = session.user
    db.set_value(
        "Notification Log",
        {"for_user": user, "read": 0, "name": ["in", names]},
        "read",
        1,
        update_modified=False,
    )
    return {"success": True}


@whitelist(allow_guest=False)
def get_my_notifications(start=0, limit=20):
    """Notification-Log-Eintraege des aktuellen Users."""
    user = session.user
    notifications = get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=[
            "name", "subject", "email_content", "document_type",
            "document_name", "creation", "read",
        ],
        order_by="creation desc",
        limit_start=int(start),
        limit_page_length=int(limit),
    )
    return {"success": True, "data": notifications}


__all__ = [
    "FRAPPE_MODULE",
    "VALID_ACTIONS",
    "get_my_audit_log",
    "get_my_notifications",
    "get_unread_notifications",
    "log",
    "mark_notifications_read",
]
