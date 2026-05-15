import frappe
import json
from diakronos.diakonos.api.dsgvo_log import log_einwilligung


def _get_my_mitglied():
    user = frappe.session.user
    name = frappe.db.get_value("Mitglied", {"user": user}, "name")
    if not name:
        email = frappe.db.get_value("User", user, "email") or user
        name = frappe.db.get_value("Mitglied", {"email": email}, "name")
    if not name:
        frappe.throw("Kein Mitglied-Datensatz für diesen Nutzer gefunden.")
    return name


@frappe.whitelist()
def get_my_profile():
    mid = _get_my_mitglied()
    doc = frappe.get_doc("Mitglied", mid)

    sichtbarkeit = doc.get("adressbuch_sichtbarkeit")
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
        "foto_einwilligung": bool(doc.get("foto_einwilligung")),
        "foto_datum": str(doc.get("foto_datum")) if doc.get("foto_datum") else None,
        "werbeeinwilligung": bool(doc.get("werbeeinwilligung")),
        "werbung_datum": str(doc.get("werbung_datum")) if doc.get("werbung_datum") else None,
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
    if not hasattr(frappe.local, "audit_skip"):
        frappe.local.audit_skip = set()
    frappe.local.audit_skip.add(doc.name)
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
def update_einwilligung(typ, erteilt):
    """Setzt Foto- oder Werbeeinwilligung (nur eigenes Profil)."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Nicht angemeldet", frappe.PermissionError)
    mid = _get_my_mitglied()
    erteilt = frappe.utils.cint(erteilt)
    heute = frappe.utils.nowdate() if erteilt else None
    if typ == "foto":
        frappe.db.set_value("Mitglied", mid, {
            "foto_einwilligung": erteilt,
            "foto_datum": heute,
        })
    elif typ == "werbung":
        frappe.db.set_value("Mitglied", mid, {
            "werbeeinwilligung": erteilt,
            "werbung_datum": heute,
        })
    else:
        frappe.throw("Ungueltiger Einwilligungstyp")
    frappe.db.commit()
    log_einwilligung(mid, typ, "erteilt" if erteilt else "widerrufen")
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
    hatte_datenschutz = bool(doc.datenschutz_einwilligung)
    hatte_foto = bool(doc.get("foto_einwilligung"))
    hatte_werbung = bool(doc.get("werbeeinwilligung"))
    doc.datenschutz_einwilligung = 0
    doc.foto_einwilligung = 0
    doc.foto_datum = None
    doc.werbeeinwilligung = 0
    doc.werbung_datum = None
    doc.adressbuch_sichtbarkeit = json.dumps(
        {"email": False, "telefonnummer": False, "adresse": False, "geburtstag": False}
    )
    doc.save(ignore_permissions=True)

    frappe.db.set_value("User", user, "enabled", 0)
    frappe.db.commit()
    if hatte_datenschutz:
        log_einwilligung(mid, "datenschutz", "widerrufen")
    if hatte_foto:
        log_einwilligung(mid, "foto", "widerrufen")
    if hatte_werbung:
        log_einwilligung(mid, "werbung", "widerrufen")
    frappe.local.login_manager.logout()
    return {"ok": True}
