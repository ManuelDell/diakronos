"""Portierung von `diakronos.kronos.api.ablaufplan_api` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/ablaufplan_api.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    get_ablaufplan        save_ablaufplan        get_termine_am_tag

Zustaendigkeitspruefungen (Original -> Port), alle 1:1 erhalten:

    _get_element_or_throw  -> _get_element_or_throw (Guest -> 403, Element fehlt -> 417)
    _assert_read_access    -> _assert_read_access   (kein Leserecht -> 403)
    _assert_write_access   -> _assert_write_access  (kein Schreibrecht -> 403)
    get_termine_am_tag    -> Login-Guard + Kalender-Whitelist (Guest -> 403)

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user          -> session.user
    frappe.get_doc("Element", x) -> _shared.get_doc(...) -> Document
    frappe.db.get_value(...)     -> _shared.get_value(...)
    frappe.db.exists(...)        -> db.exists(...)
    frappe.get_all(...)          -> _shared.get_all(...)  (Zeilen sind dicts)
    frappe.new_doc(..).insert()  -> _shared._create(...)
    doc.ablaufplan = x; doc.save() -> _shared._update_doc(...)
    ablaufplan.append("positionen", row) -> _child_replace(...)
    frappe.db.commit()           -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)       -> _shared.throw(msg, exc)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.ablaufplan_api"

import json

from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _child_replace,
    _child_rows,
    _create,
    _update_doc,
    get_all,
    get_doc,
    get_value,
    log_error,
    session,
    throw,
)
from diakronos_app.frappe_compat import db
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
)

# Positionen-Felder des Originals (`ablaufplan.append("positionen", {...})`).
_POSITION_FIELDS = (
    "reihenfolge",
    "bezeichnung",
    "dauer_minuten",
    "verantwortlicher",
    "notiz",
    "referenz_doctype",
    "referenz_name",
    "funktion",
    "gruppe",
    "detail",
)


# ── Berechtigungen (1:1 aus dem Original) ───────────────────────────────────


def _assert_read_access(calendar_name: str) -> None:
    """Wirft PermissionError, wenn der User kein Leserecht auf den Kalender hat."""
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet", FrappePermissionError)
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    calendars = get_accessible_calendars()
    readable = {c["name"] for c in calendars}
    if calendar_name not in readable:
        throw(f"Kein Lesezugriff auf Kalender: {calendar_name}", FrappePermissionError)


def _assert_write_access(calendar_name: str) -> None:
    """Wirft PermissionError, wenn der User kein Schreibrecht auf den Kalender hat."""
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet", FrappePermissionError)
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    calendars = get_accessible_calendars()
    writable = {c["name"] for c in calendars if c.get("write")}
    if calendar_name not in writable:
        throw(f"Kein Schreibzugriff auf Kalender: {calendar_name}", FrappePermissionError)


def _get_element_or_throw(element):
    """Laedt ein Element und wirft PermissionError bei fehlendem Lesezugriff.

    P0-3 Befund 3: Zusaetzlich zur Kalender-Sichtbarkeit wird geprueft, ob der
    Nutzer diesen TERMIN ueberhaupt sehen darf. Ein Vorschlag im lesbaren
    Kalender ist fuer Nicht-Moderatoren unsichtbar (genau wie in
    `calendar_get.get_calendar_events` im Lesemodus); ohne diese zweite
    Schranke liess sich ein fremder Vorschlag ueber die Ablaufplan-Wege
    trotzdem lesen und beschreiben.
    """
    if not element or element in ("undefined", "null", ""):
        throw("Element fehlt", ValidationError)
    doc = get_doc("Element", element)
    _assert_read_access(doc.element_calendar)
    if not _darf_termin_sehen(doc):
        throw(
            f"Kein Lesezugriff auf Termin: {element}",
            FrappePermissionError,
        )
    return doc


def _darf_termin_sehen(doc) -> bool:
    """Sieht der aktuelle Nutzer diesen Termin?

    Regel (deckungsgleich mit `calendar_get`): Moderatoren sehen alles in
    ihren Kalendern AUSSER `Abgelehnt`, alle anderen nur "Festgelegt". Die
    eigene Sicht auf den Kalender ist bereits durch `_assert_read_access` belegt.

    W-A (R-P1-8): `Abgelehnt` ist erledigt — der Termin erscheint nur noch in
    der Moderations-Historie, nicht im Kalender (dieselbe Regel wie in
    `calendar_get.get_calendar_events` und `api/kronos/series.py`). Vorher
    lieferten die Ablaufplan-Wege einen abgelehnten Termin weiter aus.
    """
    from diakronos_app.api.kronos.event_crud import _ist_moderator

    if (doc.get("status") or "") == "Abgelehnt":
        return False
    if _ist_moderator(doc.element_calendar):
        return True
    return (doc.get("status") or "") == "Festgelegt"


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_ablaufplan(element):
    """Liefert {ablaufplan, positionen:[...]} fuer ein Element oder None."""
    doc = _get_element_or_throw(element)

    ablaufplan_name = doc.get("ablaufplan")
    if not ablaufplan_name:
        return None

    try:
        ablaufplan = get_doc("Ablaufplan", ablaufplan_name)
    except Exception as e:  # noqa: BLE001 — Original loggt und liefert None
        log_error(f"Ablaufplan {ablaufplan_name} nicht ladbar", "get_ablaufplan")
        return None

    # Kind-Zeilen ueber die Child-Tabelle lesen (Original: ablaufplan.get("positionen")).
    positionen = []
    for row in _child_rows(
        "Ablaufplan Position", ablaufplan_name, "positionen", list(_POSITION_FIELDS)
    ):
        positionen.append({
            "reihenfolge": row.get("reihenfolge"),
            "bezeichnung": row.get("bezeichnung") or "",
            "dauer_minuten": row.get("dauer_minuten"),
            "verantwortlicher": row.get("verantwortlicher") or "",
            "notiz": row.get("notiz") or "",
            "referenz_doctype": row.get("referenz_doctype") or "",
            "referenz_name": row.get("referenz_name") or "",
            "funktion": row.get("funktion") or "",
            "gruppe": row.get("gruppe") or "",
            "detail": row.get("detail") or "",
        })

    return {
        "ablaufplan": ablaufplan_name,
        "titel": ablaufplan.get("titel") or "",
        "datum": str(ablaufplan.get("datum") or ""),
        "notizen": ablaufplan.get("notizen") or "",
        "positionen": positionen,
    }


@whitelist(allow_guest=False)
def save_ablaufplan(element, positionen):
    """Legt den Ablaufplan LAZY an (wenn Kategorie hat_ablaufplan=1) und
    ueberschreibt danach die Positionen. Verknuepft Element.ablaufplan."""
    doc = _get_element_or_throw(element)
    _assert_write_access(doc.element_calendar)

    if isinstance(positionen, str):
        try:
            positionen = json.loads(positionen)
        except Exception:  # noqa: BLE001 — Original faellt auf [] zurueck
            positionen = []

    if not isinstance(positionen, list):
        positionen = []

    # LAZY anlegen wenn noch kein Ablaufplan existiert
    ablaufplan_name = doc.get("ablaufplan")
    if not ablaufplan_name:
        hat_ablaufplan = 0
        if doc.get("element_category"):
            hat_ablaufplan = get_value(
                "Eventkategorie", doc.element_category, "hat_ablaufplan") or 0
        if not int(hat_ablaufplan):
            throw(
                "Die Eventkategorie erlaubt keinen Ablaufplan.", ValidationError)

        werte = {
            "titel": doc.get("element_name") or element,
            "element": doc.name,
        }
        if doc.get("element_start"):
            werte["datum"] = str(doc.element_start)[:10]
        ablaufplan_name = _create("Ablaufplan", werte)

        _update_doc("Element", doc.name, {"ablaufplan": ablaufplan_name})
    else:
        # Existiert der verknuepfte Ablaufplan noch? (defensive)
        if not db.exists("Ablaufplan", {"name": ablaufplan_name}):
            throw(f"Ablaufplan {ablaufplan_name} existiert nicht.")

    # Positionen ueberschreiben (Original: ablaufplan.positionen = [] + append je Zeile)
    rows = []
    for i, row in enumerate(positionen, start=1):
        if not isinstance(row, dict):
            continue
        bezeichnung = (row.get("bezeichnung") or "").strip()
        if not bezeichnung:
            continue
        rows.append({
            "reihenfolge": row.get("reihenfolge") or i,
            "bezeichnung": bezeichnung,
            "dauer_minuten": row.get("dauer_minuten"),
            "verantwortlicher": (row.get("verantwortlicher") or "").strip(),
            "notiz": (row.get("notiz") or "").strip(),
            "referenz_doctype": (row.get("referenz_doctype") or "").strip(),
            "referenz_name": (row.get("referenz_name") or "").strip(),
            "funktion": (row.get("funktion") or "").strip(),
            "gruppe": (row.get("gruppe") or "").strip(),
            "detail": (row.get("detail") or "").strip(),
        })

    _child_replace("Ablaufplan Position", ablaufplan_name, "positionen", rows)

    return {"success": True, "ablaufplan": ablaufplan_name, "element": doc.name}


@whitelist(allow_guest=False)
def get_termine_am_tag(datum, kalender=None):
    """Kandidaten zum Andocken eines Ablaufplans an einem Tag.

    Liefert nur Elemente zu Kalendern, auf die der User Leserecht hat.
    """
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet", FrappePermissionError)

    if not datum:
        throw("Datum fehlt", ValidationError)

    # Erlaubte Kalender. Ohne Zugriff gibt es nichts zu sehen — frueh raus,
    # sonst liefert get_all (umgeht Permissions) ALLE Termine.
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    allowed = [c["name"] for c in get_accessible_calendars()]
    if not allowed:
        return []

    filters = {
        "element_start": ["between", [f"{datum} 00:00:00", f"{datum} 23:59:59"]],
    }

    # kalender akzeptiert einen Namen, eine Liste oder eine JSON-Liste
    if kalender:
        if isinstance(kalender, str):
            try:
                parsed = json.loads(kalender)
                kalender = parsed if isinstance(parsed, list) else [kalender]
            except Exception:  # noqa: BLE001 — Original faellt auf [kalender] zurueck
                kalender = [kalender]
        if isinstance(kalender, list):
            gewuenscht = [k for k in kalender if k in allowed]
            # Nur nicht-erlaubte Kalender angefragt -> leeres Ergebnis,
            # NICHT stillschweigend auf alle erlaubten ausweiten
            if not gewuenscht:
                return []
            filters["element_calendar"] = ["in", gewuenscht]

    if "element_calendar" not in filters:
        filters["element_calendar"] = ["in", allowed]

    # P0-3 Befund 3: Nicht-Moderatoren sehen am Tag nur festgelegte Termine.
    # Ohne diesen Filter lieferte der Endpunkt Titel, Zeit und Raum fremder
    # Vorschlaege und Konflikte aus lesbaren Kalendern — genau die Daten, die
    # `get_calendar_events` im Lesemodus zurueckhaelt. Moderatoren der eigenen
    # Kalender sehen dort weiterhin alles (Vorschlag und Konflikt).
    from diakronos_app.api.kronos.event_crud import _ist_moderator

    moderierte = {
        c["name"] for c in get_accessible_calendars() if c.get("is_moderator")
    }

    elements = get_all(
        "Element",
        filters=filters,
        fields=["name", "element_name", "element_start", "element_end",
                "ressource", "element_category", "element_calendar", "status"],
        order_by="element_start asc",
    )

    # Ein Durchlauf, eine Regel: "Festgelegt" immer, alles andere nur in
    # Kalendern, die der Nutzer moderiert — `Abgelehnt` NIRGENDS (W-A: ein
    # abgelehnter Termin ist erledigt und erscheint nur in der Historie).
    elements = [
        e for e in elements
        if (e.get("status") or "") != "Abgelehnt"
        and ((e.get("status") or "") == "Festgelegt"
             or e.get("element_calendar") in moderierte)
    ]

    result = []
    for e in elements:
        ressource_name = ""
        if e.get("ressource"):
            ressource_name = get_value("Ressource", e["ressource"], "ressource_name") or ""
        result.append({
            "name": e.get("name"),
            "element_name": e.get("element_name") or "",
            "element_start": str(e.get("element_start")),
            "element_end": str(e.get("element_end")) if e.get("element_end") else None,
            "ressource_name": ressource_name,
            "element_category": e.get("element_category") or "",
        })

    return result


__all__ = [
    "get_ablaufplan",
    "get_termine_am_tag",
    "save_ablaufplan",
]
