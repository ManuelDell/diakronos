import frappe
from frappe.utils import getdate, nowdate


def get_context(context):
    context.no_cache = 1
    context.title = "Mitglied werden"

    token = frappe.request.args.get("token", "")
    context.token = token
    context.link_fehler = None
    context.link_typ = None

    if not token:
        context.link_fehler = "Kein Registrierungslink angegeben. Bitte nutze den dir mitgeteilten Link."
        return

    link = frappe.db.get_value(
        "Registrierungslink",
        {"slug": token, "aktiv": 1},
        ["name", "typ", "gueltig_bis", "max_anmeldungen", "anmeldungen_count"],
        as_dict=True,
    )

    if not link:
        context.link_fehler = "Dieser Registrierungslink ist ungültig oder wurde deaktiviert."
        return

    if link.gueltig_bis and getdate(link.gueltig_bis) < getdate(nowdate()):
        context.link_fehler = "Dieser Registrierungslink ist abgelaufen."
        return

    if link.max_anmeldungen > 0 and link.anmeldungen_count >= link.max_anmeldungen:
        context.link_fehler = "Die maximale Anzahl an Anmeldungen für diesen Link wurde erreicht."
        return

    if link.typ != "Mitglied-Registrierung":
        context.link_fehler = "Dieser Link ist für die Gast-Anmeldung vorgesehen. Bitte nutze den richtigen Link."
        return

    context.link_typ = link.typ
