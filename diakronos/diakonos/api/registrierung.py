import frappe
from frappe.utils import now_datetime, getdate, nowdate


_DSGVO_TEXT = (
    "Ich willige ein, dass meine personenbezogenen Daten (Name, Kontaktdaten) "
    "zum Zweck der Mitgliederverwaltung gemäß Art. 6 Abs. 1 lit. a DSGVO "
    "gespeichert und verarbeitet werden. Die Einwilligung kann jederzeit "
    "widerrufen werden."
)


def _get_client_ip():
    return (
        frappe.request.environ.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or frappe.request.environ.get("REMOTE_ADDR", "")
    )


def _validate_token(token):
    """
    Prüft Token und gibt Registrierungslink-Doc zurück.
    Wirft ValidationError bei ungültigem/abgelaufenem/vollem Link.
    """
    if not token:
        frappe.throw("Kein Registrierungstoken angegeben.", frappe.PermissionError)

    link = frappe.db.get_value(
        "Registrierungslink",
        {"slug": token, "aktiv": 1},
        ["name", "typ", "gueltig_bis", "max_anmeldungen", "anmeldungen_count"],
        as_dict=True,
    )

    if not link:
        frappe.throw("Ungültiger oder deaktivierter Registrierungslink.", frappe.PermissionError)

    if link.gueltig_bis and getdate(link.gueltig_bis) < getdate(nowdate()):
        frappe.throw("Dieser Registrierungslink ist abgelaufen.", frappe.PermissionError)

    if link.max_anmeldungen > 0 and link.anmeldungen_count >= link.max_anmeldungen:
        frappe.throw("Die maximale Anzahl an Anmeldungen für diesen Link wurde erreicht.", frappe.PermissionError)

    return link


@frappe.whitelist(allow_guest=True)
def validate_token(token):
    """Gibt Typ des Links zurück (für Frontend-Initialisierung)."""
    link = _validate_token(token)
    return {"typ": link.typ}


@frappe.whitelist(allow_guest=True)
def submit_registrierung(token, vorname, nachname, email="", telefon="", geburtstag="", kommentar=""):
    """Mitglied-Registrierung via Token-Link."""
    link = _validate_token(token)

    if link.typ != "Mitglied-Registrierung":
        frappe.throw("Dieser Link ist nicht für die Mitglied-Registrierung freigegeben.", frappe.PermissionError)

    _validate_name(vorname, nachname)

    doc = frappe.get_doc({
        "doctype":             "Anmeldung",
        "anmeldungstyp":       "Mitglied-Registrierung",
        "vorname":             vorname.strip(),
        "nachname":            nachname.strip(),
        "email":               email.strip(),
        "telefon":             telefon.strip(),
        "geburtstag":          geburtstag or None,
        "kommentar":           kommentar.strip(),
        "dsgvo_zustimmung":    1,
        "dsgvo_text_snapshot": _DSGVO_TEXT,
        "ip_adresse":          _get_client_ip(),
        "anmeldedatum":        now_datetime(),
        "status":              "Anmeldeanfrage",
        "registrierungslink":  link.name,
    })
    doc.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Registrierungslink", link.name, "anmeldungen_count",
        link.anmeldungen_count + 1, update_modified=False,
    )
    frappe.db.commit()

    return {"success": True, "anmeldung": doc.name}


@frappe.whitelist(allow_guest=True)
def submit_gast(token, vorname, nachname):
    """Gast-Anmeldung via Token-Link."""
    link = _validate_token(token)

    if link.typ != "Gast-Anmeldung":
        frappe.throw("Dieser Link ist nicht für die Gast-Anmeldung freigegeben.", frappe.PermissionError)

    _validate_name(vorname, nachname)

    doc = frappe.get_doc({
        "doctype":             "Anmeldung",
        "anmeldungstyp":       "Gast-Anmeldung",
        "vorname":             vorname.strip(),
        "nachname":            nachname.strip(),
        "dsgvo_zustimmung":    1,
        "dsgvo_text_snapshot": _DSGVO_TEXT,
        "ip_adresse":          _get_client_ip(),
        "anmeldedatum":        now_datetime(),
        "status":              "Anmeldeanfrage",
        "registrierungslink":  link.name,
    })
    doc.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Registrierungslink", link.name, "anmeldungen_count",
        link.anmeldungen_count + 1, update_modified=False,
    )
    frappe.db.commit()

    return {"success": True, "anmeldung": doc.name}


def _validate_name(vorname, nachname):
    if not (vorname and vorname.strip()):
        frappe.throw("Vorname ist erforderlich.", frappe.ValidationError)
    if not (nachname and nachname.strip()):
        frappe.throw("Nachname ist erforderlich.", frappe.ValidationError)
