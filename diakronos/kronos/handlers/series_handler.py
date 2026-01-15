# diakronos/kronos/handlers/series_handler.py
"""
Event Hooks für automatische Serie-Generierung
Wird aufgerufen wenn Element (Event) erstellt/aktualisiert wird
"""

import frappe
from frappe import _
from frappe.utils import get_datetime


def before_insert_element(doc, method):
    """
    Hook: Wird VOR Insert (Erstellung) aufgerufen
    Validiert Serie-Einstellungen
    """
    if doc.get("repeat_this_event"):
        start_dt = get_datetime(doc.get("element_start"))
        repeat_till = doc.get("repeat_till")
        if repeat_till:
            repeat_dt = get_datetime(repeat_till)
            if repeat_dt <= start_dt:
                frappe.throw(_("Wiederholungsende muss nach Start-Datum liegen"))


def before_update_element(doc, method):
    """
    Hook: Wird VOR Update aufgerufen
    Validiert Änderungen
    """
    if doc.get("repeat_this_event"):
        start_dt = get_datetime(doc.get("element_start"))
        repeat_till = doc.get("repeat_till")
        if repeat_till:
            repeat_dt = get_datetime(repeat_till)
            if repeat_dt <= start_dt:
                frappe.throw(_("Wiederholungsende muss nach Start-Datum liegen"))


def after_insert_element(doc, method):
    """
    Hook: Wird NACH Insert aufgerufen
    Generiert Serie-Instanzen automatisch
    """
    if doc.get("repeat_this_event"):
        try:
            from diakronos.kronos.api.series_create import create_event_series
            create_event_series(doc.name)
            frappe.msgprint(
                _("Serie-Termine wurden automatisch generiert"),
                title=_("Serie erstellt"),
                indicator="green"
            )
        except Exception as e:
            frappe.log_error(
                f"Fehler bei Serie-Generierung: {str(e)}",
                "Series Handler Error"
            )
