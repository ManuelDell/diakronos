# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _

from diakronos.diakonos.api.session import check_permission


def _check_dienstplan_permission():
    """Hilfsfunktion: Prüft Leseberechtigung für den Dienstplan via check_permission."""
    referenz = frappe.db.get_value("Dienstbereich", {}, "name")
    if referenz:
        perm = check_permission("Dienstbereich", referenz, "read")
        if not perm.get("allowed"):
            frappe.throw(
                _("Keine Berechtigung zum Anzeigen des Dienstplans."),
                frappe.PermissionError,
            )
    else:
        if not frappe.has_permission("Dienstbereich", "read"):
            frappe.throw(
                _("Keine Berechtigung zum Anzeigen des Dienstplans."),
                frappe.PermissionError,
            )


@frappe.whitelist()
def get_dienstplan(start_date=None, end_date=None):
    """Gibt Dienstplan-Einträge für einen Zeitraum zurück."""
    _check_dienstplan_permission()

    if not start_date or not end_date:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        sunday = monday + datetime.timedelta(days=6)
        start_date = str(monday)
        end_date = str(sunday)

    eintraege = frappe.get_all(
        "Anmeldung",
        filters=[
            ["anmeldedatum", ">=", start_date],
            ["anmeldedatum", "<=", end_date],
        ],
        fields=[
            "name",
            "anmeldedatum",
            "anmeldungstyp",
            "status",
            "vorname",
            "nachname",
            "email",
            "mitglied",
            "element",
            "gruppe",
        ],
        order_by="anmeldedatum asc",
    ) or []

    return {
        "start_date": start_date,
        "end_date": end_date,
        "eintraege": eintraege,
    }


@frappe.whitelist()
def get_meine_dienste():
    """Gibt alle Dienste des aktuellen Users zurück."""
    _check_dienstplan_permission()

    user = frappe.session.user
    user_email = frappe.db.get_value("User", user, "email") or user

    eintraege = frappe.get_all(
        "Anmeldung",
        filters={"email": user_email},
        fields=[
            "name",
            "anmeldedatum",
            "anmeldungstyp",
            "status",
            "vorname",
            "nachname",
            "email",
            "mitglied",
            "element",
            "gruppe",
        ],
        order_by="anmeldedatum desc",
    ) or []

    return {
        "user": user,
        "eintraege": eintraege,
    }
