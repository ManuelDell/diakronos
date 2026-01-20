# diakronos/diakronos/page/kronos_calendar_page/kronos_calendar_page.py
# page_header_remove_apply: Entfernt Page-Header, lässt Awesome-Bar

import frappe

def get_context(context):
    context.no_cache = 1
    context.no_head = 1  # page_header_remove_apply: Entfernt "Kronos Kalender"
    context.title = "Kronos Kalender"

    context.add_css = [
        "/assets/diakronos/css/kronos_calendar_custom.css",
        "/assets/diakronos/css/kronos_modal.css"
    ]

    if not frappe.has_permission("Element", "read"):
        frappe.throw("Keine Berechtigung für den Kronos Kalender")

    return context