"""
Ressourcen-API – Räume / Orte verwalten und Konflikte prüfen
"""
import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def get_ressources():
    """Alle Ressourcen für Dropdown und Resource-Timeline."""
    try:
        meta = frappe.get_meta("Ressource")
        typ_field = next((f for f in meta.fields if f.fieldname == "typ"), None)
        type_options = [t.strip() for t in (typ_field.options or "").split("\n") if t.strip()] if typ_field else []
    except Exception:
        rows_opt = frappe.db.sql(
            "SELECT options FROM `tabDocField` WHERE parent='Ressource' AND fieldname='typ'",
            as_dict=True
        )
        type_options = [t.strip() for t in (rows_opt[0].options if rows_opt else "").split("\n") if t.strip()]

    rows = frappe.db.sql("""
        SELECT name, ressource_name, typ, kapazitaet, beschreibung, bild
        FROM `tabRessource`
        ORDER BY COALESCE(typ, '') ASC, COALESCE(ressource_name, name) ASC
    """, as_dict=True)

    return {
        "types": type_options,
        "resources": [
            {
                "id":           r.name,
                "title":        r.ressource_name or r.name,
                "typ":          r.typ or "Sonstiges",
                "kapazitaet":   r.kapazitaet,
                "beschreibung": r.beschreibung or "",
                "bild":         r.bild,
            }
            for r in rows
        ]
    }


@frappe.whitelist(allow_guest=False)
def get_kronos_settings():
    """Kronos-Einstellungen für die Ressourcen-Pflichtfeld-Konfiguration."""
    settings = frappe.get_single("Kronos Einstellungen")
    return {
        "ressource_pflichtfeld": settings.get("ressource_pflichtfeld") or 0,
        "standard_ressource":   settings.get("standard_ressource") or "",
    }


@frappe.whitelist(allow_guest=False)
def check_resource_conflict(ressource, element_start, element_end, exclude_id=None):
    """Prüft ob eine Ressource im Zeitraum bereits belegt ist."""
    if not ressource or not element_start or not element_end:
        return {"conflict": False, "events": []}

    filters = [
        ["Kronos Element", "ressource", "=", ressource],
        ["Kronos Element", "element_start", "<", element_end],
        ["Kronos Element", "element_end", ">", element_start],
        ["Kronos Element", "docstatus", "!=", 2],
    ]
    if exclude_id:
        filters.append(["Kronos Element", "name", "!=", exclude_id])

    events = frappe.get_all(
        "Kronos Element",
        filters=filters,
        fields=["name", "element_name", "element_start", "element_end", "element_calendar"],
        ignore_permissions=True
    )
    return {"conflict": len(events) > 0, "events": events}


@frappe.whitelist(allow_guest=False)
def finalize_pending_events(event_ids, as_final=True):
    """Setzt Vorschlag-Events auf Festgelegt oder zurück."""
    if isinstance(event_ids, str):
        import json
        event_ids = json.loads(event_ids)
    if isinstance(as_final, str):
        as_final = as_final.lower() in ("true", "1", "yes")

    updated = []
    for eid in event_ids:
        try:
            doc = frappe.get_doc("Kronos Element", eid)
            doc.vorschlag = 0 if as_final else 1
            doc.save(ignore_permissions=True)
            updated.append(eid)
        except Exception as e:
            frappe.log_error(str(e), "finalize_pending_events")
    return {"updated": updated}


@frappe.whitelist(allow_guest=False)
def get_conflict_events():
    """Gibt Konflikt-Events zurück (nur für Moderatoren)."""
    if not frappe.has_permission("Kronos Element", "read"):
        frappe.throw(_("Keine Berechtigung"), frappe.PermissionError)

    events = frappe.db.sql("""
        SELECT a.name, a.element_name, a.element_start, a.element_end,
               a.ressource, a.element_calendar
        FROM `tabKronos Element` a
        JOIN `tabKronos Element` b
          ON a.ressource = b.ressource
         AND a.name != b.name
         AND a.element_start < b.element_end
         AND a.element_end > b.element_start
         AND a.docstatus != 2
         AND b.docstatus != 2
        WHERE a.ressource IS NOT NULL AND a.ressource != ''
        ORDER BY a.ressource, a.element_start
    """, as_dict=True)
    return events


@frappe.whitelist(allow_guest=False)
def get_calendar_pending_info(calendar_names):
    """Gibt zurück ob Kalender selbstverwaltet sind."""
    if isinstance(calendar_names, str):
        import json
        calendar_names = json.loads(calendar_names)

    result = {}
    for name in calendar_names:
        try:
            doc = frappe.get_doc("Kronos Kalender", name)
            result[name] = {
                "selbstverwaltet": doc.get("selbstverwaltet") or 0,
                "pending_count": frappe.db.count(
                    "Kronos Element",
                    filters={"element_calendar": name, "vorschlag": 1, "docstatus": ["!=", 2]}
                )
            }
        except Exception:
            result[name] = {"selbstverwaltet": 0, "pending_count": 0}
    return result
