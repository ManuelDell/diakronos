import frappe
from frappe.utils import now_datetime, getdate, nowdate


_DSGVO_TEXT = (
    "Ich willige ein, dass meine personenbezogenen Daten (Name, Kontaktdaten) "
    "zum Zweck der Veranstaltungsanmeldung gemäß Art. 6 Abs. 1 lit. a DSGVO "
    "gespeichert und verarbeitet werden."
)


@frappe.whitelist()
def register_mitglied(registrierungslink_id):
    """
    One-Click-Anmeldung eines eingeloggten Mitglieds zu einer Veranstaltung.
    Legt eine Anmeldung mit den Profildaten des angemeldeten Nutzers an.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Anmeldung erforderlich.", frappe.PermissionError)

    link = frappe.db.get_value(
        "Registrierungslink",
        registrierungslink_id,
        ["name", "typ", "gueltig_bis", "max_anmeldungen", "anmeldungen_count", "aktiv"],
        as_dict=True,
    )

    if not link or not link.aktiv:
        frappe.throw("Registrierungslink nicht gefunden oder deaktiviert.", frappe.DoesNotExistError)

    if link.typ != "Veranstaltung":
        frappe.throw("Dieser Link ist nicht für Veranstaltungs-Anmeldungen.", frappe.PermissionError)

    if link.gueltig_bis and getdate(link.gueltig_bis) < getdate(nowdate()):
        frappe.throw("Dieser Registrierungslink ist abgelaufen.", frappe.PermissionError)

    if link.max_anmeldungen > 0 and link.anmeldungen_count >= link.max_anmeldungen:
        frappe.throw("Die maximale Anzahl an Anmeldungen wurde erreicht.", frappe.PermissionError)

    existing = frappe.db.exists(
        "Anmeldung",
        {"registrierungslink": link.name, "email": user, "status": ["!=", "Abgelehnt"]},
    )
    if existing:
        frappe.throw("Du bist bereits für diese Veranstaltung angemeldet.", frappe.ValidationError)

    user_doc = frappe.db.get_value("User", user, ["first_name", "last_name", "email"], as_dict=True) or {}

    doc = frappe.get_doc({
        "doctype":             "Anmeldung",
        "anmeldungstyp":       "Veranstaltung",
        "vorname":             user_doc.get("first_name") or "",
        "nachname":            user_doc.get("last_name") or "",
        "email":               user,
        "dsgvo_zustimmung":    1,
        "dsgvo_text_snapshot": _DSGVO_TEXT,
        "anmeldedatum":        now_datetime(),
        "status":              "Anmeldeanfrage",
        "registrierungslink":  link.name,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.set_value(
        "Registrierungslink", link.name,
        "anmeldungen_count", link.anmeldungen_count + 1,
        update_modified=False,
    )
    frappe.db.commit()

    return {"success": True, "anmeldung": doc.name}


@frappe.whitelist()
def check_anmeldestatus(registrierungslink_id):
    """Prüft ob der aktuelle Nutzer bereits angemeldet ist."""
    user = frappe.session.user
    if user == "Guest":
        return {"angemeldet": False}

    existing = frappe.db.exists(
        "Anmeldung",
        {"registrierungslink": registrierungslink_id, "email": user, "status": ["!=", "Abgelehnt"]},
    )
    return {"angemeldet": bool(existing)}
