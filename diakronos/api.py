import frappe
from frappe import _
from frappe.utils import get_datetime, cint, cstr

@frappe.whitelist(allow_guest=True)
def element_get_calendar_events(start=None, end=None):
    filters = {}
    if start:
        filters["elementlink_start"] = [">=", f"{start} 00:00:00"]
    if end:
        filters["elementlink_start"] = ["<=", f"{end} 23:59:59"]

    data = frappe.get_all(
        "Elementlink",
        filters=filters,
        fields=["name", "parent", "elementlink_title", "elementlink_start", "elementlink_end", "elementlink_color"],
        limit_page_length=2000
    )

    events = []
    for d in data:
        if not d.elementlink_start:
            continue

        # Farbe
        kalender_color = frappe.db.get_value("Kalender", d.parent, "calendar_color") or "#4367b8"
        color = d.elementlink_color or kalender_color

        # SICHER umwandeln: String → datetime → ISO-String
        start_dt = get_datetime(d.elementlink_start)
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S")

        end_iso = None
        if d.elementlink_end:
            end_dt = get_datetime(d.elementlink_end)
            end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

        events.append({
            "id": d.name,
            "title": d.elementlink_title or "Termin",
            "start": start_iso,
            "end": end_iso,
            "backgroundColor": color,
            "borderColor": color,
            "allDay": False
        })

    return events