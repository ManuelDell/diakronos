import frappe

@frappe.whitelist()
def get_events(start_date, end_date):
    """
    Stub: Gibt Events für einen Zeitraum zurück.
    Später: Integration mit Kronos / CalDAV.
    """
    # TODO: Replace with real event query (Kronos / CalDAV)
    dummy_events = [
        {
            "title": "Beispiel-Event",
            "start": start_date,
            "end": end_date,
            "all_day": True,
        }
    ]
    return dummy_events
