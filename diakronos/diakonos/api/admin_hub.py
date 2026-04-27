import frappe
from frappe.utils import nowdate, get_first_day, get_last_day


def _require_admin():
    if frappe.session.user == "Guest":
        frappe.throw("Zugriff verweigert.", frappe.PermissionError)
    roles = frappe.get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        frappe.throw("Nur für Mitgliederadministratoren.", frappe.PermissionError)


@frappe.whitelist()
def get_dsgvo_uebersicht():
    _require_admin()

    mitglieder = frappe.get_all(
        "Mitglied",
        fields=["name", "vorname", "nachname", "status", "email",
                "datenschutz_einwilligung", "datenschutz_datum"],
        order_by="nachname asc",
    )

    # Enrich with DSGVO Einwilligung status
    for m in mitglieder:
        if not m.datenschutz_einwilligung:
            m["dsgvo_status"] = "fehlt"
            m["dsgvo_datum"] = None
        else:
            # Check if there's an active (non-revoked) consent
            active = frappe.db.exists(
                "DSGVO Einwilligung",
                {"mitglied": m.name, "widerrufen": 0},
            )
            if active:
                m["dsgvo_status"] = "ok"
                m["dsgvo_datum"] = m.datenschutz_datum
            else:
                m["dsgvo_status"] = "widerrufen"
                m["dsgvo_datum"] = m.datenschutz_datum

    ok = sum(1 for m in mitglieder if m["dsgvo_status"] == "ok")
    widerrufen = sum(1 for m in mitglieder if m["dsgvo_status"] == "widerrufen")
    fehlt = sum(1 for m in mitglieder if m["dsgvo_status"] == "fehlt")

    return {
        "mitglieder": mitglieder,
        "stats": {
            "gesamt": len(mitglieder),
            "ok": ok,
            "widerrufen": widerrufen,
            "fehlt": fehlt,
        },
    }


@frappe.whitelist()
def get_anmeldungen_hub():
    _require_admin()

    anmeldungen = frappe.get_all(
        "Anmeldung",
        fields=["name", "vorname", "nachname", "status", "anmeldungstyp",
                "anmeldedatum", "email"],
        order_by="anmeldedatum desc",
        limit=500,
    )

    links = frappe.get_all(
        "Registrierungslink",
        fields=["name", "bezeichnung", "typ", "aktiv", "slug",
                "gueltig_bis", "max_anmeldungen", "anmeldungen_count", "link_anzeige"],
        order_by="creation desc",
    )

    return {"anmeldungen": anmeldungen, "links": links}


@frappe.whitelist()
def get_statistik():
    _require_admin()

    # Mitglieder
    alle_mitglieder = frappe.get_all("Mitglied", fields=["name", "status", "datenschutz_einwilligung"])
    m_stats = {"gesamt": len(alle_mitglieder), "mitglied": 0, "gast": 0, "kind": 0, "inaktiv": 0, "archiviert": 0}
    for m in alle_mitglieder:
        key = (m.status or "").lower()
        if key in m_stats:
            m_stats[key] += 1

    # DSGVO
    dsgvo_ok = frappe.db.count("DSGVO Einwilligung", {"widerrufen": 0})
    dsgvo_wr = frappe.db.count("DSGVO Einwilligung", {"widerrufen": 1})
    dsgvo_fehlt = max(0, len(alle_mitglieder) - frappe.db.count("DSGVO Einwilligung"))

    # Anmeldungen
    alle_anm = frappe.get_all("Anmeldung", fields=["name", "status", "anmeldedatum"])
    monat_start = get_first_day(nowdate()).strftime("%Y-%m-%d")
    diesen_monat = sum(1 for a in alle_anm if a.anmeldedatum and str(a.anmeldedatum) >= monat_start)
    offen = sum(1 for a in alle_anm if a.status in ("Anmeldeanfrage", "Ausstehend"))

    nach_status = {}
    for a in alle_anm:
        nach_status[a.status] = nach_status.get(a.status, 0) + 1

    # Links
    alle_links = frappe.get_all(
        "Registrierungslink",
        fields=["name", "bezeichnung", "aktiv", "anmeldungen_count"],
        order_by="anmeldungen_count desc",
    )
    aktiv = sum(1 for l in alle_links if l.aktiv)
    top_links = alle_links[:5]

    return {
        "mitglieder": m_stats,
        "dsgvo": {"ok": dsgvo_ok, "widerrufen": dsgvo_wr, "fehlt": dsgvo_fehlt},
        "anmeldungen": {
            "gesamt": len(alle_anm),
            "diesen_monat": diesen_monat,
            "offen": offen,
            "nach_status": nach_status,
        },
        "links": {
            "aktiv": aktiv,
            "inaktiv": len(alle_links) - aktiv,
            "gesamt_anmeldungen": sum(l.anmeldungen_count or 0 for l in alle_links),
            "top": top_links,
        },
    }
