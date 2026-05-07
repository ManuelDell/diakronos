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

    # Lade Antworten + Kinder für jede Anmeldung
    anmeldung_names = [a.name for a in anmeldungen]

    antworten_map = {}
    for a in frappe.get_all("Anmeldung Antwort",
                             filters={"parent": ["in", anmeldung_names]},
                             fields=["parent", "feldlabel", "antwort"]):
        antworten_map.setdefault(a.parent, []).append({"label": a.feldlabel, "wert": a.antwort})

    kinder_map = {}
    for k in frappe.get_all("Anmeldung Kind",
                              filters={"parent": ["in", anmeldung_names]},
                              fields=["parent", "vorname", "nachname", "geburtstag"]):
        kinder_map.setdefault(k.parent, []).append(
            {"vorname": k.vorname, "nachname": k.nachname, "geburtstag": str(k.geburtstag or "")}
        )

    for a in anmeldungen:
        a["antworten"] = antworten_map.get(a.name, [])
        a["kinder"] = kinder_map.get(a.name, [])

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
    m_stats = {
        "gesamt": len(alle_mitglieder),
        "mitglied": 0,
        "gast": 0,
        "passives_mitglied": 0,
        "passiver_gast": 0,
    }
    STATUS_KEY_MAP = {
        "Mitglied": "mitglied",
        "Gast": "gast",
        "Passives Mitglied": "passives_mitglied",
        "Passiver Gast": "passiver_gast",
    }
    for m in alle_mitglieder:
        key = STATUS_KEY_MAP.get(m.status or "")
        if key:
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


@frappe.whitelist()
def genehmige_anmeldung(anmeldung_id):
    """Setzt Anmeldung auf 'Best\u00e4tigt' → on_update() erstellt Mitglied + DSGVO."""
    _require_admin()

    doc = frappe.get_doc("Anmeldung", anmeldung_id)
    doc.status = "Best\u00e4tigt"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "mitglied": doc.mitglied}


@frappe.whitelist()
def lehne_anmeldung_ab(anmeldung_id, grund=""):
    """Setzt Anmeldung auf 'Abgelehnt'."""
    _require_admin()

    doc = frappe.get_doc("Anmeldung", anmeldung_id)
    doc.status = "Abgelehnt"
    if grund:
        doc.kommentar = (doc.kommentar or "") + f"\n[Abgelehnt: {grund}]"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def get_anmeldeformulare():
    """Liste aller Anmeldeformulare f\u00fcr Dropdowns."""
    _require_admin()

    formulare = frappe.get_all(
        "Anmeldeformular",
        fields=["name", "bezeichnung", "mit_gaesten", "mit_kinder"],
        order_by="bezeichnung asc",
    )
    return {"formulare": formulare}


@frappe.whitelist()
def create_anmeldeformular(bezeichnung, mit_gaesten=0, mit_kinder=0):
    """Schnellanlage eines Anmeldeformulars aus dem Hub."""
    _require_admin()

    doc = frappe.get_doc({
        "doctype": "Anmeldeformular",
        "bezeichnung": bezeichnung,
        "mit_gaesten": int(mit_gaesten or 0),
        "mit_kinder": int(mit_kinder or 0),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "id": doc.name}


@frappe.whitelist()
def update_anmeldeformular_felder(formular_id, felder_json):
    """Ersetzt alle Felder eines Anmeldeformulars."""
    _require_admin()
    import json as _json

    form = frappe.get_doc("Anmeldeformular", formular_id)
    felder = _json.loads(felder_json) if isinstance(felder_json, str) else felder_json

    form.felder = []
    for f in felder:
        form.append("felder", {
            "label":      f.get("label", ""),
            "feldtyp":    f.get("feldtyp", "Text"),
            "optionen":   f.get("optionen", ""),
            "pflichtfeld": int(f.get("pflichtfeld", 0)),
            "fuer_gaeste": int(f.get("fuer_gaeste", 0)),
            "fuer_kinder": int(f.get("fuer_kinder", 0)),
        })
    form.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}
