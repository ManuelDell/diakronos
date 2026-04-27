import frappe
from frappe.utils import getdate, nowdate


def get_context(context):
    context.no_cache = 1
    context.title = "Gast-Anmeldung"

    token = frappe.request.args.get("token", "")
    context.token = token
    context.link_fehler = None
    context.link_typ = None

    if not token:
        context.link_fehler = "Kein Anmeldelink angegeben. Bitte nutze den dir mitgeteilten Link."
        return

    link = frappe.db.get_value(
        "Registrierungslink",
        {"slug": token, "aktiv": 1},
        ["name", "typ", "gueltig_bis", "max_anmeldungen", "anmeldungen_count"],
        as_dict=True,
    )

    if not link:
        context.link_fehler = "Dieser Link ist ungültig oder wurde deaktiviert."
        return

    if link.gueltig_bis and getdate(link.gueltig_bis) < getdate(nowdate()):
        context.link_fehler = "Dieser Anmeldelink ist abgelaufen."
        return

    if link.max_anmeldungen > 0 and link.anmeldungen_count >= link.max_anmeldungen:
        context.link_fehler = "Die maximale Anzahl an Anmeldungen wurde erreicht."
        return

    if link.typ != "Gast-Anmeldung":
        context.link_fehler = "Dieser Link ist für die Mitglied-Registrierung vorgesehen. Bitte nutze den richtigen Link."
        return

    context.link_typ = link.typ
