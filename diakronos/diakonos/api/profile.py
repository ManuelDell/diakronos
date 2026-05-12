import frappe
import json


def _get_my_mitglied():
    name = frappe.db.get_value("Mitglied", {"user": frappe.session.user}, "name")
    if not name:
        frappe.throw("Kein Mitglied-Datensatz für diesen Nutzer gefunden.")
    return name


@frappe.whitelist()
def get_my_profile():
    mid = _get_my_mitglied()
    doc = frappe.get_doc("Mitglied", mid)

    sichtbarkeit = doc.adressbuch_sichtbarkeit
    if isinstance(sichtbarkeit, str):
        try:
            sichtbarkeit = json.loads(sichtbarkeit)
        except Exception:
            sichtbarkeit = {}
    if not sichtbarkeit:
        sichtbarkeit = {"email": True, "telefonnummer": True, "adresse": False, "geburtstag": False}

    return {
        "name": doc.name,
        "vorname": doc.vorname or "",
        "nachname": doc.nachname or "",
        "email": doc.email or "",
        "geburtstag": str(doc.geburtstag) if doc.geburtstag else None,
        "telefonnummer": doc.telefonnummer or "",
        "postleitzahl": doc.postleitzahl or "",
        "wohnort": doc.wohnort or "",
        "strasse": doc.get("straße") or "",
        "nummer": doc.nummer or "",
        "foto": doc.foto or "",
        "geschlecht": doc.geschlecht or "",
        "familienstand": doc.familienstand or "",
        "datenschutz_einwilligung": bool(doc.datenschutz_einwilligung),
        "datenschutz_datum": str(doc.datenschutz_datum) if doc.datenschutz_datum else None,
        "adressbuch_sichtbarkeit": sichtbarkeit,
    }


@frappe.whitelist()
def update_my_profile(vorname=None, nachname=None, telefonnummer=None,
                       postleitzahl=None, wohnort=None, strasse=None,
                       nummer=None, geburtstag=None, geschlecht=None, familienstand=None):
    mid = _get_my_mitglied()
    doc = frappe.get_doc("Mitglied", mid)
    if vorname is not None:      doc.vorname = vorname
    if nachname is not None:     doc.nachname = nachname
    if telefonnummer is not None: doc.telefonnummer = telefonnummer
    if postleitzahl is not None: doc.postleitzahl = postleitzahl
    if wohnort is not None:      doc.wohnort = wohnort
    if strasse is not None:
        try: doc.set("straße", strasse)
        except Exception: pass
    if nummer is not None:       doc.nummer = nummer
    if geburtstag is not None:   doc.geburtstag = geburtstag or None
    if geschlecht is not None:   doc.geschlecht = geschlecht
    if familienstand is not None: doc.familienstand = familienstand
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def update_adressbuch_sichtbarkeit(settings=None):
    mid = _get_my_mitglied()
    if isinstance(settings, str):
        settings = json.loads(settings)
    allowed = {"email", "telefonnummer", "adresse", "geburtstag"}
    clean = {k: bool(v) for k, v in (settings or {}).items() if k in allowed}
    frappe.db.set_value("Mitglied", mid, "adressbuch_sichtbarkeit", json.dumps(clean))
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def update_profile_picture(file_url=None):
    mid = _get_my_mitglied()
    frappe.db.set_value("Mitglied", mid, "foto", file_url)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def delete_my_data():
    """DSGVO-Widerruf: Anonymisiert alle Daten und deaktiviert den Account."""
    user = frappe.session.user
    mid = _get_my_mitglied()
    doc = frappe.get_doc("Mitglied", mid)

    doc.vorname = "Gelöscht"
    doc.nachname = doc.name
    doc.email = f"deleted-{doc.name}@deleted.invalid"
    doc.telefonnummer = ""
    doc.postleitzahl = ""
    doc.wohnort = ""
    try: doc.set("straße", "")
    except Exception: pass
    doc.nummer = ""
    doc.geburtstag = None
    doc.foto = None
    doc.datenschutz_einwilligung = 0
    doc.adressbuch_sichtbarkeit = json.dumps(
        {"email": False, "telefonnummer": False, "adresse": False, "geburtstag": False}
    )
    doc.save(ignore_permissions=True)

    frappe.db.set_value("User", user, "enabled", 0)
    frappe.db.commit()
    frappe.local.login_manager.logout()
    return {"ok": True}
