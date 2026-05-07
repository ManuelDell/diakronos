import frappe
from frappe.utils import nowdate, getdate


def _require_admin():
    if frappe.session.user == "Guest":
        frappe.throw("Zugriff verweigert.", frappe.PermissionError)
    roles = frappe.get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        frappe.throw("Nur f\u00fcr Mitgliederadministratoren.", frappe.PermissionError)


@frappe.whitelist()
def create_link(bezeichnung, typ, gueltig_bis="", max_anmeldungen=0,
                anmeldeformular_id="", element_id=""):
    """Erstellt einen neuen Registrierungslink."""
    _require_admin()

    doc = frappe.get_doc({
        "doctype": "Registrierungslink",
        "bezeichnung": bezeichnung,
        "typ": typ,
        "gueltig_bis": gueltig_bis or None,
        "max_anmeldungen": int(max_anmeldungen or 0),
        "anmeldeformular": anmeldeformular_id or None,
        "element": element_id or None,
        "aktiv": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "link": {
            "name": doc.name,
            "bezeichnung": doc.bezeichnung,
            "typ": doc.typ,
            "slug": doc.slug,
            "aktiv": doc.aktiv,
            "link_anzeige": doc.link_anzeige,
            "gueltig_bis": str(doc.gueltig_bis) if doc.gueltig_bis else None,
            "max_anmeldungen": doc.max_anmeldungen,
            "anmeldungen_count": doc.anmeldungen_count,
            "anmeldeformular": doc.anmeldeformular,
            "element": doc.element,
        }
    }


@frappe.whitelist()
def update_link(link_id, **kwargs):
    """Aktualisiert einen Registrierungslink."""
    _require_admin()

    doc = frappe.get_doc("Registrierungslink", link_id)
    allowed = {"bezeichnung", "gueltig_bis", "max_anmeldungen",
               "anmeldeformular", "element", "aktiv"}

    for key, value in kwargs.items():
        if key in allowed:
            setattr(doc, key, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "link_id": doc.name}


@frappe.whitelist()
def delete_link(link_id):
    """L\u00f6scht einen Link nur wenn keine best\u00e4tigten Anmeldungen existieren."""
    _require_admin()

    # Pr\u00fcfe ob Best\u00e4tigte Anmeldungen existieren
    bestaetigt = frappe.db.exists(
        "Anmeldung",
        {"registrierungslink": link_id, "status": "Best\u00e4tigt"}
    )
    if bestaetigt:
        frappe.throw(
            "Link kann nicht gel\u00f6scht werden: Es existieren best\u00e4tigte Anmeldungen.",
            frappe.ValidationError
        )

    # L\u00f6sche ausstehende Anmeldungen
    ausstehend = frappe.get_all(
        "Anmeldung",
        filters={"registrierungslink": link_id},
        pluck="name"
    )
    for anm_id in ausstehend:
        frappe.delete_doc("Anmeldung", anm_id, ignore_permissions=True)

    frappe.delete_doc("Registrierungslink", link_id, ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def toggle_link(link_id):
    """Schaltet einen Link aktiv / inaktiv um."""
    _require_admin()

    doc = frappe.get_doc("Registrierungslink", link_id)
    doc.aktiv = 0 if doc.aktiv else 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "aktiv": bool(doc.aktiv)}
