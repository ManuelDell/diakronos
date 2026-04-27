import frappe
from frappe import _
from diakronos.diakonos.api.audit import log


@frappe.whitelist()
def export_mitglied_data(mitglied_name):
    """
    DSGVO-Export: Alle personenbezogenen Daten eines Mitglieds als dict.
    Schreibt einen Audit-Log-Eintrag.
    """
    frappe.only_for("System Manager")

    m = frappe.get_doc("Mitglied", mitglied_name)

    data = {
        "stammdaten": {
            "name": m.name,
            "vorname": m.vorname,
            "nachname": m.nachname,
            "email": m.email,
            "geburtstag": str(m.geburtstag) if m.geburtstag else None,
            "telefonnummer": m.telefonnummer,
            "geschlecht": m.geschlecht,
            "familienstand": m.familienstand,
            "status": m.status,
            "mitglied_seit": str(m.mitglied_seit) if m.mitglied_seit else None,
            "adresse": {
                "straße": getattr(m, "straße", None),
                "nummer": m.nummer,
                "postleitzahl": m.postleitzahl,
                "wohnort": m.wohnort,
            },
        },
        "datenschutz": {
            "einwilligung_erteilt": bool(m.datenschutz_einwilligung),
            "einwilligung_datum": str(m.datenschutz_datum) if m.datenschutz_datum else None,
            "einwilligungen": [
                {
                    "name": e.name,
                    "zeitstempel": str(e.zeitstempel),
                    "widerrufen": bool(e.widerrufen),
                    "widerruf_datum": str(e.widerruf_datum) if e.widerruf_datum else None,
                }
                for e in frappe.get_all(
                    "DSGVO Einwilligung",
                    filters={"mitglied": mitglied_name},
                    fields=["name", "zeitstempel", "widerrufen", "widerruf_datum"],
                    order_by="zeitstempel asc",
                )
            ],
        },
        "beziehungen": [
            {"beziehung_zu": r.beziehung_zu, "typ": r.beziehungstyp}
            for r in m.get("beziehungen") or []
            if not r.ist_spiegel
        ],
        "gruppen": frappe.db.sql(
            """
            SELECT g.gruppenname, gm.rolle, gm.status, gm.beitrittsdatum
            FROM `tabGruppenmitgliedschaft` gm
            JOIN `tabGruppe` g ON g.name = gm.parent
            WHERE gm.mitglied = %(name)s
            """,
            {"name": mitglied_name},
            as_dict=True,
        ),
        "anhaenge": frappe.get_all(
            "Sicherer Anhang",
            filters={"mitglied": mitglied_name},
            fields=["dateiname", "dateityp", "loeschfrist", "sichtbarkeits_ebene"],
        ),
    }

    log("DSGVO-Export", "Mitglied", mitglied_name,
        f"DSGVO-Datenexport durch {frappe.session.user}")

    return data
