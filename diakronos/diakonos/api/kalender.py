import frappe


@frappe.whitelist()
def get_events(start_date, end_date):
    """Gibt bestätigte Termine aus dem Kronos-Kalender zurück."""
    user = frappe.session.user
    if user == "Guest":
        return []

    events = frappe.get_all(
        "Element",
        filters=[
            ["element_start", "<=", end_date + " 23:59:59"],
            ["element_end", ">=", start_date],
            ["status", "=", "Festgelegt"],
        ],
        fields=["name", "element_name", "element_start", "element_end", "all_day",
                "anmeldung_aktiv", "registrierungslink"],
        order_by="element_start asc",
        limit=500,
    )

    result = []
    for e in events:
        slug = None
        if e.registrierungslink:
            slug = frappe.db.get_value("Registrierungslink", e.registrierungslink, "slug")

        result.append({
            "id":                   e.name,
            "title":                e.element_name or "(Kein Titel)",
            "start":                str(e.element_start)[:10] if e.element_start else "",
            "end":                  str(e.element_end)[:10] if e.element_end else "",
            "startDatetime":        str(e.element_start) if e.element_start else "",
            "endDatetime":          str(e.element_end) if e.element_end else "",
            "allDay":               bool(e.all_day),
            "anmeldungAktiv":       bool(e.anmeldung_aktiv),
            "registrierungslinkId": e.registrierungslink or "",
            "registrierungslinkSlug": slug or "",
        })
    return result
