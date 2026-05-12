"""Dashboard-API — Widget-Konfiguration und Datenabruf"""
import json
import frappe
from frappe import _


def _user_can_see_widget(user, widget):
    """Prüft ob der Nutzer das Widget sehen darf."""
    required_role = widget.get("required_role") if isinstance(widget, dict) else widget.required_role
    required_permission = widget.get("required_permission") if isinstance(widget, dict) else widget.required_permission

    if required_role:
        if not frappe.db.exists("Has Role", {"parent": user, "role": required_role}):
            return False

    if required_permission:
        try:
            parts = [p.strip() for p in required_permission.split(",")]
            doctype = parts[0]
            perm = parts[1] if len(parts) > 1 else "read"
            if not frappe.has_permission(doctype, perm, user=user):
                return False
        except Exception:
            pass

    return True


@frappe.whitelist(allow_guest=False)
def get_available_widgets():
    """Gibt alle für den aktuellen Nutzer sichtbaren Widgets zurück (nur Metadaten)."""
    user = frappe.session.user
    widgets = frappe.get_all(
        "Dashboard Widget",
        filters={"enabled": 1},
        fields=[
            "widget_id", "label", "category", "icon", "widget_type",
            "grid_size", "empty_state_mode", "empty_state_message",
            "refresh_interval", "default_position", "default_visible",
            "required_role", "required_permission", "api_method"
        ],
        order_by="default_position asc"
    )
    return [w for w in widgets if _user_can_see_widget(user, w)]


@frappe.whitelist(allow_guest=False)
def get_user_config():
    """Gibt das personalisierte Dashboard-Layout des aktuellen Nutzers zurück."""
    user = frappe.session.user
    available = get_available_widgets()

    configs = frappe.get_all(
        "Dashboard Widget User Config",
        filters={"user": user},
        fields=["widget", "position", "visible", "size", "collapsed"]
    )
    config_map = {c.widget: c for c in configs}

    result = []
    for w in available:
        cfg = config_map.get(w["widget_id"])
        result.append({
            "widget_id":           w["widget_id"],
            "label":               w["label"],
            "category":            w["category"],
            "icon":                w.get("icon") or "",
            "widget_type":         w.get("widget_type") or "info_card",
            "api_method":          w.get("api_method") or "",
            "grid_size":           (cfg.size if cfg and cfg.size != "default" else None) or w["grid_size"],
            "position":            cfg.position if cfg else w["default_position"],
            "visible":             bool(cfg.visible if cfg else w["default_visible"]),
            "collapsed":           bool(cfg.collapsed if cfg else False),
            "empty_state_mode":    w["empty_state_mode"],
            "empty_state_message": w["empty_state_message"] or "Keine Daten.",
            "refresh_interval":    w["refresh_interval"] or 0,
        })

    result.sort(key=lambda x: x["position"])
    return result


@frappe.whitelist(allow_guest=False)
def set_user_config(layout_json):
    """Speichert das personalisierte Layout für den aktuellen Nutzer."""
    if isinstance(layout_json, str):
        layout = json.loads(layout_json)
    else:
        layout = layout_json

    user = frappe.session.user
    available_ids = {w["widget_id"] for w in get_available_widgets()}

    for item in layout:
        widget_id = item.get("widget_id")
        if widget_id not in available_ids:
            continue

        existing = frappe.db.get_value(
            "Dashboard Widget User Config",
            {"user": user, "widget": widget_id},
            "name"
        )
        if existing:
            doc = frappe.get_doc("Dashboard Widget User Config", existing)
        else:
            doc = frappe.new_doc("Dashboard Widget User Config")
            doc.user = user
            doc.widget = widget_id

        doc.position = int(item.get("position", 0))
        doc.visible = 1 if item.get("visible", True) else 0
        doc.size = item.get("size", "default") or "default"
        doc.collapsed = 1 if item.get("collapsed", False) else 0
        doc.save(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "ok"}


@frappe.whitelist(allow_guest=False)
def reset_user_config():
    """Setzt das Layout auf die Standardwerte zurück."""
    user = frappe.session.user
    frappe.db.delete("Dashboard Widget User Config", {"user": user})
    frappe.db.commit()
    return {"status": "ok"}


@frappe.whitelist(allow_guest=False)
def get_widget_data(widget_id, extra_args=None):
    """Lädt die Daten für ein einzelnes Widget (dynamischer API-Aufruf)."""
    user = frappe.session.user
    widget = frappe.db.get_value(
        "Dashboard Widget",
        {"widget_id": widget_id, "enabled": 1},
        ["api_method", "required_role", "required_permission", "api_args"],
        as_dict=True
    )
    if not widget:
        frappe.throw(_("Widget nicht gefunden."))
    if not _user_can_see_widget(user, widget):
        frappe.throw(_("Zugriff verweigert."), frappe.PermissionError)
    if not widget.api_method:
        return {"widget_id": widget_id, "data": None}

    try:
        method = frappe.get_attr(widget.api_method)
        args = json.loads(widget.api_args or "{}")
        if extra_args:
            if isinstance(extra_args, str):
                extra_args = json.loads(extra_args)
            args.update(extra_args)
        data = method(**args)
    except Exception as e:
        frappe.log_error(str(e), f"get_widget_data:{widget_id}")
        return {"widget_id": widget_id, "data": None, "error": str(e)}

    return {"widget_id": widget_id, "data": data}
"""
Dashboard Widget — Daten-APIs (Phase 2)
Anhängen an diakronos/diakonos/api/dashboard.py
"""
import datetime
import frappe


@frappe.whitelist(allow_guest=False)
def get_upcoming_events(limit=5):
    """Nächste Termine ab heute für das Dashboard-Widget."""
    user = frappe.session.user
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    events = frappe.get_all(
        "Element",
        filters=[
            ["element_start", ">=", now],
            ["docstatus", "!=", 2],
        ],
        fields=["name", "element_name", "element_start", "element_end", "element_calendar"],
        order_by="element_start asc",
        limit=int(limit),
        ignore_permissions=True,
    )
    return [
        {
            "id":       e.name,
            "title":    e.element_name or "(Kein Titel)",
            "start":    str(e.element_start) if e.element_start else "",
            "end":      str(e.element_end) if e.element_end else "",
            "calendar": e.element_calendar or "",
        }
        for e in events
    ]


@frappe.whitelist(allow_guest=False)
def get_events_for_month(year=None, month=None):
    """Gibt Termine-Tage für den Mini-Kalender zurück."""
    today = datetime.date.today()
    year = int(year or today.year)
    month = int(month or today.month)
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year+1}-01-01"
    else:
        end = f"{year}-{month+1:02d}-01"

    rows = frappe.db.sql(
        """SELECT DATE(element_start) AS day
           FROM `tabElement`
           WHERE element_start >= %s AND element_start < %s
             AND docstatus != 2
           GROUP BY DATE(element_start)""",
        (start, end),
        as_dict=True,
    )
    return {"year": year, "month": month, "event_days": [str(r.day) for r in rows]}


@frappe.whitelist(allow_guest=False)
def get_pinned_beitraege(limit=3):
    """Neueste veröffentlichte Beiträge für das Dashboard."""
    rows = frappe.get_all(
        "Beitrag",
        filters=[["veroeffentlicht", "=", 1]],
        fields=["name", "titel", "auszug", "datum", "autor", "bild"],
        order_by="datum desc",
        limit=int(limit),
        ignore_permissions=True,
    )
    return [
        {
            "id":      r.name,
            "title":   r.titel or "",
            "excerpt": r.auszug or "",
            "date":    str(r.datum) if r.datum else "",
            "author":  r.autor or "",
            "image":   r.bild or "",
        }
        for r in rows
    ]


@frappe.whitelist(allow_guest=False)
def get_recent_articles(limit=3):
    """Zuletzt geänderte Wiki-Artikel für das Dashboard."""
    rows = frappe.get_all(
        "Wiki Artikel",
        fields=["name", "titel", "modified", "kategorie"],
        order_by="modified desc",
        limit=int(limit),
        ignore_permissions=True,
    )
    return [
        {
            "id":       r.name,
            "title":    r.titel or r.name,
            "modified": str(r.modified) if r.modified else "",
            "category": r.kategorie or "",
        }
        for r in rows
    ]


@frappe.whitelist(allow_guest=False)
def get_meine_buchungen_widget(upcoming_only=1, limit=3):
    """Kommende Ressourcen-Buchungen des aktuellen Nutzers."""
    user = frappe.session.user
    filters = {"nutzer": user}
    if int(upcoming_only):
        filters["start_date"] = [">=", datetime.date.today().strftime("%Y-%m-%d")]
    rows = frappe.get_all(
        "Ressourcen Buchung",
        filters=filters,
        fields=["name", "ressource", "start_date", "end_date", "zweck", "status"],
        order_by="start_date asc",
        limit=int(limit),
        ignore_permissions=True,
    )
    # Ressource-Name auflösen
    result = []
    for r in rows:
        ressource_name = frappe.db.get_value("Ressource", r.ressource, "ressource_name") or r.ressource
        result.append({
            "id":             r.name,
            "ressource":      r.ressource,
            "ressource_name": ressource_name,
            "start":          str(r.start_date) if r.start_date else "",
            "end":            str(r.end_date) if r.end_date else "",
            "zweck":          r.zweck or "",
            "status":         r.status or "",
        })
    return result
"""
Dashboard Phase 4 — Badge-Counts für Action-Widgets
Anhängen an diakronos/diakonos/api/dashboard.py
"""


@frappe.whitelist(allow_guest=False)
def get_widget_badge_counts():
    """
    Gibt Anzahl-Badges für Action-Widgets zurück.
    Nur die Counts, keine Daten — schnell gecacht.
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    result = {}

    # pending-registrations: Termine zur Moderation (Kalenderadmin)
    if "Kalenderadministrator" in roles or "System Manager" in roles:
        count = frappe.db.sql("""
            SELECT COUNT(DISTINCT a.name)
            FROM `tabElement` a
            JOIN `tabElement` b
              ON a.ressource = b.ressource
             AND a.name != b.name
             AND a.element_start < b.element_end
             AND a.element_end > b.element_start
             AND a.docstatus != 2
             AND b.docstatus != 2
            WHERE a.ressource IS NOT NULL AND a.ressource != ''
        """)[0][0]
        result["pending-registrations"] = int(count or 0)

    # manage-registrations: Offene Anmeldungen (Admin)
    if "Mitgliederadministrator" in roles or "System Manager" in roles:
        count = frappe.db.count("Anmeldung", {"status": "Ausstehend"})
        result["manage-registrations"] = int(count or 0)

        # open-signups: Aktive Registrierungslinks
        count = frappe.db.count("Registrierungslink", {"aktiv": 1})
        result["open-signups"] = int(count or 0)

    return result
