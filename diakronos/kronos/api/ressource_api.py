"""
Ressourcen-API – Räume / Orte verwalten und Konflikte prüfen
"""
import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_ressources():
    """Alle Ressourcen für Dropdown und Resource-Timeline."""
    ressources = frappe.get_all(
        "Ressource",
        fields=["name", "ressource_name", "kapazitaet", "beschreibung", "bild"],
        order_by="ressource_name asc"
    )
    return [
        {
            "id":          r.name,
            "title":       r.ressource_name or r.name,
            "kapazitaet":  r.kapazitaet or None,
            "beschreibung": r.beschreibung or "",
            "bild":        r.bild or None,
        }
        for r in ressources
    ]


@frappe.whitelist(allow_guest=False)
def get_kronos_settings():
    """Gibt Kronos-Einstellungen zurück (ressource_pflichtfeld, standard_ressource)."""
    try:
        s = frappe.get_single("Kronos Einstellungen")
        return {
            "ressource_pflichtfeld": bool(s.ressource_pflichtfeld),
            "standard_ressource":    s.standard_ressource or None,
        }
    except Exception:
        return {"ressource_pflichtfeld": False, "standard_ressource": None}


@frappe.whitelist(allow_guest=False)
def check_resource_conflict(ressource, element_start, element_end, exclude_id=None):
    """
    Prüft ob die Ressource im angegebenen Zeitraum bereits belegt ist.
    Gibt das erste konfliktierende Element zurück (oder None).
    exclude_id: eigene Event-ID beim Bearbeiten ausschließen
    """
    if not ressource or not element_start or not element_end:
        return None

    from diakronos.kronos.api.event_crud import parse_iso_datetime_raw
    start_str = parse_iso_datetime_raw(element_start)
    end_str   = parse_iso_datetime_raw(element_end)

    conditions = """
        ressource = %(ressource)s
        AND status != 'Konflikt'
        AND (ignore_conflict IS NULL OR ignore_conflict = 0)
        AND element_start < %(end)s
        AND element_end   > %(start)s
    """
    params = {"ressource": ressource, "start": start_str, "end": end_str}

    if exclude_id:
        conditions += " AND name != %(exclude_id)s"
        params["exclude_id"] = exclude_id

    conflicts = frappe.db.sql(
        f"SELECT name, element_name, element_start, element_end FROM `tabElement` WHERE {conditions} LIMIT 1",
        params,
        as_dict=True
    )

    if not conflicts:
        return None

    c = conflicts[0]
    return {
        "id":    c.name,
        "title": c.element_name,
        "start": str(c.element_start),
        "end":   str(c.element_end),
    }


@frappe.whitelist(allow_guest=False)
def finalize_pending_events(event_ids, as_final=False):
    """
    Setzt Status von Vorschlag-Events auf 'Festgelegt' (wenn as_final=True)
    oder bestätigt sie als eingereichten Vorschlag (bleibt Vorschlag).
    event_ids: JSON-String oder Liste von Element-Namen
    """
    import json
    from diakronos.kronos.api.event_crud import _assert_write_access

    if isinstance(event_ids, str):
        event_ids = json.loads(event_ids)

    if not event_ids:
        return {"success": True, "updated": 0}

    updated = 0
    errors  = []

    for eid in event_ids:
        try:
            doc = frappe.get_doc("Element", eid)
            _assert_write_access(doc.element_calendar)

            if as_final:
                doc.status = "Festgelegt"
                doc.save(ignore_permissions=True)
                updated += 1
        except Exception as e:
            errors.append({"id": eid, "error": str(e)})

    if updated:
        frappe.db.commit()

    return {"success": True, "updated": updated, "errors": errors}


@frappe.whitelist(allow_guest=False)
def get_conflict_events():
    """Gibt alle Konflikt-Events zurück die der Nutzer als Moderator sehen kann."""
    from diakronos.kronos.api.permissions import get_accessible_calendars
    accessible = get_accessible_calendars()
    mod_cal_names = [c["name"] for c in accessible if c.get("is_moderator")]
    if not mod_cal_names:
        return []

    placeholders = ", ".join(["%s"] * len(mod_cal_names))
    events = frappe.db.sql(f"""
        SELECT
            elem.name,
            elem.element_name  AS title,
            elem.element_start AS start,
            elem.element_end   AS end,
            elem.element_calendar,
            kal.calendar_name  AS calendar_title,
            kal.calendar_color AS calendar_color,
            elem.ressource
        FROM `tabElement` elem
        LEFT JOIN `tabKalender` kal ON kal.name = elem.element_calendar
        WHERE elem.status = 'Konflikt'
          AND elem.element_calendar IN ({placeholders})
        ORDER BY elem.element_start ASC
    """, mod_cal_names, as_dict=True)

    return [
        {
            "id":            e.name,
            "title":         e.title,
            "start":         str(e.start),
            "end":           str(e.end),
            "calendar":      e.element_calendar,
            "calendarTitle": e.calendar_title or e.element_calendar,
            "color":         e.calendar_color or "#ef4444",
            "ressource":     e.ressource or None,
        }
        for e in events
    ]


@frappe.whitelist(allow_guest=False)
def get_calendar_pending_info(calendar_names):
    """
    Gibt für eine Liste von Kalendernamen zurück ob sie selbstverwaltet sind.
    calendar_names: JSON-String oder Liste
    """
    import json
    if isinstance(calendar_names, str):
        calendar_names = json.loads(calendar_names)

    result = {}
    for name in calendar_names:
        try:
            doc = frappe.get_doc("Kalender", name)
            result[name] = {
                "selbstverwaltet": bool(doc.selbstverwaltet),
                "title": doc.calendar_name or name,
            }
        except Exception:
            result[name] = {"selbstverwaltet": False, "title": name}

    return result
