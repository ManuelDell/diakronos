# diakronos/kronos/api/kanban_api.py
import json
import frappe
from frappe import _
from .permissions import get_accessible_calendars


def _fmt_event(e, cal_info):
    cal = cal_info.get(e.element_calendar, {})
    return {
        "type":           "event",
        "id":             e.name,
        "title":          e.element_name or "Termin",
        "start":          str(e.element_start),
        "end":            str(e.element_end) if e.element_end else None,
        "all_day":        bool(e.all_day),
        "calendar":       e.element_calendar,
        "calendar_title": cal.get("title", e.element_calendar),
        "calendar_color": cal.get("color", "#3b82f6"),
        "status":         e.status,
        "series_id":      e.series_id or "",
        "ressource":      e.ressource or "",
        "description":    e.description or "",
        "modified":       str(e.modified),
        "modified_by":    e.modified_by or "",
    }


@frappe.whitelist(allow_guest=False)
def get_kanban_board_data():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Nicht angemeldet"))

    allowed = get_accessible_calendars()
    mod_cals = [c["name"] for c in allowed if c.get("is_moderator")]
    if not mod_cals:
        return {"vorschlaege": [], "konflikte": [], "staging": [], "notifications": {}}

    # Calendar info cache
    cal_info = {}
    for cn in mod_cals:
        row = frappe.db.get_value("Kalender", cn, ["calendar_name", "calendar_color"], as_dict=True) or {}
        cal_info[cn] = {
            "title": row.get("calendar_name") or cn,
            "color": row.get("calendar_color") or "#3b82f6",
        }

    _fields = [
        "name", "element_name", "element_start", "element_end", "all_day",
        "element_calendar", "element_category", "status", "ressource",
        "ignore_conflict", "description", "modified", "modified_by", "series_id",
    ]

    raw_v = frappe.get_all("Element",
        filters={"element_calendar": ["in", mod_cals], "status": "Vorschlag"}, fields=_fields)
    raw_k = frappe.get_all("Element",
        filters={"element_calendar": ["in", mod_cals], "status": "Konflikt"}, fields=_fields)

    all_formatted = {e.name: _fmt_event(e, cal_info) for e in raw_v + raw_k}
    vorschlaege = [_fmt_event(e, cal_info) for e in raw_v]
    konflikte   = [_fmt_event(e, cal_info) for e in raw_k]

    # Load user staging state
    staging      = []
    notifications = {}
    try:
        states = frappe.get_all("Kronos Kanban Zustand",
            filters={"user": user}, fields=["staging_events", "event_snapshots"], limit=1,
            ignore_permissions=True)
        if states:
            staging_ids = json.loads(states[0].staging_events or "[]")
            snapshots   = json.loads(states[0].event_snapshots or "{}")
            for eid in staging_ids:
                if eid in all_formatted:
                    ev = all_formatted[eid]
                    staging.append(ev)
                    snap = snapshots.get(eid, {})
                    if snap.get("modified") and snap["modified"] != ev["modified"]:
                        notifications[eid] = {"by": ev["modified_by"], "at": ev["modified"]}
    except Exception as ex:
        frappe.log_error(str(ex), "get_kanban_board_data")

    # Remove staging items from their source columns
    staging_set  = {e["id"] for e in staging}
    vorschlaege  = [e for e in vorschlaege if e["id"] not in staging_set]
    konflikte    = [e for e in konflikte   if e["id"] not in staging_set]

    return {
        "vorschlaege":  vorschlaege,
        "konflikte":    konflikte,
        "staging":      staging,
        "notifications": notifications,
    }


@frappe.whitelist(allow_guest=False)
def save_staging_state(staging_ids):
    user = frappe.session.user
    if user == "Guest":
        return
    ids_list = json.loads(staging_ids) if isinstance(staging_ids, str) else (staging_ids or [])

    snaps = {}
    for eid in ids_list:
        row = frappe.db.get_value("Element", eid, ["modified", "modified_by"], as_dict=True)
        if row:
            snaps[eid] = {"modified": str(row.modified), "modified_by": row.modified_by or ""}

    try:
        states = frappe.get_all("Kronos Kanban Zustand",
            filters={"user": user}, pluck="name", limit=1, ignore_permissions=True)
        if states:
            frappe.db.set_value("Kronos Kanban Zustand", states[0], {
                "staging_events":  json.dumps(ids_list),
                "event_snapshots": json.dumps(snaps),
            }, update_modified=False)
        else:
            doc = frappe.new_doc("Kronos Kanban Zustand")
            doc.user            = user
            doc.staging_events  = json.dumps(ids_list)
            doc.event_snapshots = json.dumps(snaps)
            doc.insert(ignore_permissions=True)
    except Exception as ex:
        frappe.log_error(str(ex), "save_staging_state")
    return {"ok": True}


@frappe.whitelist(allow_guest=False)
def finalize_staged_events(event_ids):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Nicht angemeldet"))
    ids_list = json.loads(event_ids) if isinstance(event_ids, str) else (event_ids or [])
    count = 0
    for eid in ids_list:
        try:
            frappe.db.set_value("Element", eid, "status", "Festgelegt")
            count += 1
        except Exception as ex:
            frappe.log_error(str(ex), f"finalize_event {eid}")

    # Clear staging state
    try:
        states = frappe.get_all("Kronos Kanban Zustand",
            filters={"user": user}, pluck="name", limit=1, ignore_permissions=True)
        if states:
            frappe.db.set_value("Kronos Kanban Zustand", states[0], {
                "staging_events": "[]", "event_snapshots": "{}",
            }, update_modified=False)
    except Exception:
        pass
    return {"finalized": count}


@frappe.whitelist(allow_guest=False)
def get_conflict_partner(element_id):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Nicht angemeldet"))
    try:
        doc = frappe.get_doc("Element", element_id)
    except Exception:
        return None
    if not doc.ressource:
        return None

    conflicts = frappe.db.sql("""
        SELECT name, element_name, element_start, element_end, all_day,
               element_calendar, ressource
        FROM   `tabElement`
        WHERE  ressource    = %(res)s
          AND  name         != %(name)s
          AND  element_start < %(end)s
          AND  element_end   > %(start)s
        ORDER  BY element_start
        LIMIT  1
    """, {"res": doc.ressource, "name": element_id,
          "start": str(doc.element_start), "end": str(doc.element_end)},
    as_dict=True)

    if not conflicts:
        return None
    c = conflicts[0]
    cal_title = frappe.db.get_value("Kalender", c.element_calendar, "calendar_name") or c.element_calendar
    return {
        "id":       c.name,
        "title":    c.element_name or "Termin",
        "start":    str(c.element_start),
        "end":      str(c.element_end) if c.element_end else None,
        "all_day":  bool(c.all_day),
        "calendar": cal_title,
        "ressource": c.ressource or "",
    }


@frappe.whitelist(allow_guest=False)
def resolve_conflict(element_id, action, title=None, element_start=None,
                     element_end=None, all_day=None, ressource=None, description=None):
    """
    action: 'ignore'     → ignore_conflict=1, status=Vorschlag → to staging
            'vorschlag'  → status=Vorschlag, ignore_conflict=0 → to vorschlaege col
            'festlegen'  → save edits, status=Konflikt stays   → to staging
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Nicht angemeldet"))
    try:
        doc = frappe.get_doc("Element", element_id)
    except Exception:
        frappe.throw(_("Termin nicht gefunden"))

    if title is not None:
        doc.element_name = title
    if element_start:
        doc.element_start = element_start
    if element_end:
        doc.element_end = element_end
    if all_day is not None:
        doc.all_day = int(all_day)
    if ressource is not None:
        doc.ressource = ressource or None
    if description is not None:
        doc.description = description

    if action == "ignore":
        doc.ignore_conflict = 1
        doc.status = "Vorschlag"
    elif action == "vorschlag":
        doc.status = "Vorschlag"
        doc.ignore_conflict = 0

    doc.save(ignore_permissions=True)
    return {"id": doc.name, "new_status": doc.status, "action": action}
