"""Portierung von `diakronos.diakonos.api.veranstaltungsanmeldung` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/veranstaltungsanmeldung.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    register_mitglied    check_anmeldestatus

**NUR FUER EINGELOGGTE MITGLIEDER.** Beide tragen im Original
`@frappe.whitelist(allow_guest=False)` und behandeln `Guest` gesondert:
`register_mitglied` wirft einen `PermissionError`, `check_anmeldestatus`
antwortet bewusst `{"angemeldet": False}` (kein Fehler) — das ist 1:1
uebernommen.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user            -> session.user
    frappe.db.get_value(dt, id, [..], as_dict=True) -> get_value(..., as_dict=True)
    frappe.db.exists(dt, {f: [..]})  -> _exists(...) (Operator "!=" unterstuetzt)
    frappe.get_doc({...}).insert() -> _create(...)
    frappe.db.set_value(..., update_modified=False) -> _update_doc(..., skip_modified=True)
    frappe.db.commit()             -> no-op (die Helfer committen je Operation)
    frappe.throw(msg, exc)         -> throw(msg, exc)
    now_datetime()                 -> _now()
    getdate(nowdate())             -> date.today()

Profil-Hinweis: Das Original liest `first_name`/`last_name` aus `tabUser`.
Die Live-DB hat beide Spalten (s. `inventar/live_schema_ist.tsv`), das
Standalone-Modell `models/core.User` bildet sie aber (noch) nicht ab.
Deshalb wird der Name bevorzugt aus `full_name` abgeleitet und nur dann
getrennt, wenn das Modell die Einzelspalten liefert — es wird nie ein Feld
erfunden, das die Tabelle nicht hat.
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.veranstaltungsanmeldung"

from typing import Any

from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.query import get_all, get_value
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session as compat_session

from diakronos_app.frappe_compat.api_helpers import (
    _create,
    _now,
    _today,
    _update_doc,
    throw,
)

# Einwilligungstext der Veranstaltungsanmeldung (Original: `_DSGVO_TEXT`).
_DSGVO_TEXT = (
    "Ich willige ein, dass meine personenbezogenen Daten (Name, Kontaktdaten) "
    "zum Zweck der Veranstaltungsanmeldung gemäß Art. 6 Abs. 1 lit. a DSGVO "
    "gespeichert und verarbeitet werden."
)

# Felder des Registrierungslink, die `register_mitglied` liest (Original: get_value-Liste).
_LINK_FIELDS = (
    "name",
    "typ",
    "gueltig_bis",
    "max_anmeldungen",
    "anmeldungen_count",
    "aktiv",
)


def _exists(doctype: str, filters: dict[str, Any]) -> bool:
    """`frappe.db.exists(doctype, {..})` — gibt es mindestens eine Zeile?"""
    return bool(
        get_all(doctype, filters=filters, fields=["name"], limit_page_length=1)
    )


def _ist_angemeldet(registrierungslink_id: str, user: str) -> bool:
    """Anmeldung des Nutzers an diesem Link, die nicht abgelehnt wurde.

    Original: `{"registrierungslink": .., "email": user, "status": ["!=", "Abgelehnt"]}`
    """
    return _exists(
        "Anmeldung",
        {
            "registrierungslink": registrierungslink_id,
            "email": user,
            "status": ["!=", "Abgelehnt"],
        },
    )


def _get_dict(doctype: str, name, fields: list[str]) -> dict[str, Any]:
    """`frappe.db.get_value(dt, name, [..], as_dict=True)` — als dict.

    `get_value` liefert je nach Aufrufform `list|dict|None`; der Port
    normalisiert auf ein dict (leeres dict, wenn nichts gefunden wurde).
    """
    row = get_value(doctype, name, fields, as_dict=True)
    return row if isinstance(row, dict) else {}


def _profil_name(user: str) -> tuple[str, str]:
    """Vor-/Nachname des Nutzers aus `tabUser`.

    Bevorzugt `first_name`/`last_name` (wie das Original), faellt auf eine
    Aufteilung von `full_name` zurueck, wenn das Modell die Einzelspalten
    nicht abbildet. Die Live-DB hat beide Spalten
    (`inventar/live_schema_ist.tsv`), das Standalone-Modell
    `models/core.User` aber (noch) nicht — deshalb wird die Feldliste aus den
    tatsaechlich gemappten Spalten gebildet und NIE ein Feld abgefragt, das
    die Tabelle nicht hat (sonst `KeyError` in `query.get_value`).
    """
    from diakronos_app.frappe_compat.registry_gen import column_names

    bekannt = column_names("User")
    gewuenscht = [f for f in ("first_name", "last_name", "full_name", "email") if f in bekannt]
    row = _get_dict("User", user, gewuenscht)

    vorname = row.get("first_name")
    nachname = row.get("last_name")
    if vorname is not None or nachname is not None:
        return (vorname or ""), (nachname or "")

    voll = (row.get("full_name") or "").strip()
    if not voll:
        return "", ""
    teile = voll.split(" ", 1)
    if len(teile) == 1:
        return teile[0], ""
    return teile[0], teile[1]


@whitelist(allow_guest=False)
def register_mitglied(registrierungslink_id):
    """One-Click-Anmeldung eines eingeloggten Mitglieds zu einer Veranstaltung."""
    user = compat_session.user
    if user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)

    link = _get_dict("Registrierungslink", registrierungslink_id, list(_LINK_FIELDS))

    if not link or not link.get("aktiv"):
        throw(
            "Registrierungslink nicht gefunden oder deaktiviert.",
            DoesNotExistError,
        )

    if link.get("typ") != "Veranstaltung":
        throw(
            "Dieser Link ist nicht für Veranstaltungs-Anmeldungen.",
            FrappePermissionError,
        )

    if link.get("gueltig_bis") and str(link["gueltig_bis"])[:10] < _today():
        throw("Dieser Registrierungslink ist abgelaufen.", FrappePermissionError)

    max_anmeldungen = link.get("max_anmeldungen") or 0
    count = link.get("anmeldungen_count") or 0
    if max_anmeldungen > 0 and count >= max_anmeldungen:
        throw(
            "Die maximale Anzahl an Anmeldungen wurde erreicht.",
            FrappePermissionError,
        )

    if _ist_angemeldet(link["name"], user):
        throw(
            "Du bist bereits für diese Veranstaltung angemeldet.",
            ValidationError,
        )

    vorname, nachname = _profil_name(user)

    name = _create(
        "Anmeldung",
        {
            "anmeldungstyp": "Veranstaltung",
            "vorname": vorname,
            "nachname": nachname,
            "email": user,
            "dsgvo_zustimmung": 1,
            "dsgvo_text_snapshot": _DSGVO_TEXT,
            "anmeldedatum": _now(),
            "status": "Anmeldeanfrage",
            "registrierungslink": link["name"],
        },
    )

    _update_doc(
        "Registrierungslink",
        link["name"],
        {"anmeldungen_count": count + 1},
        skip_modified=True,
    )

    return {"success": True, "anmeldung": name}


@whitelist(allow_guest=False)
def check_anmeldestatus(registrierungslink_id):
    """Prueft, ob der aktuelle Nutzer bereits angemeldet ist."""
    user = compat_session.user
    if user == "Guest":
        return {"angemeldet": False}

    return {"angemeldet": _ist_angemeldet(registrierungslink_id, user)}
