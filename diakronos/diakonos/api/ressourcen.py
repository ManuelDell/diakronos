import frappe
from frappe.utils import now_datetime, get_datetime


def _get_user():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Anmeldung erforderlich.", frappe.PermissionError)
    return user


def _typ_key(typ):
    return {"Raum": "room", "Fahrzeug": "vehicle", "Gegenstand": "item"}.get(typ, "item")


@frappe.whitelist()
def get_ressourcen_liste(typ="", search=""):
    """Gibt alle Ressourcen zurück, mit berechnetem Echtzeit-Status."""
    _get_user()

    filters = {}
    if typ:
        typ_de = {"room": "Raum", "vehicle": "Fahrzeug", "item": "Gegenstand"}.get(typ, typ)
        filters["typ"] = typ_de

    ressourcen = frappe.get_all(
        "Ressource",
        filters=filters,
        fields=["name", "ressource_name", "typ", "kapazitaet", "beschreibung", "bild", "tags", "wartung"],
        order_by="ressource_name asc",
    )

    now = str(now_datetime())

    result = []
    for r in ressourcen:
        if search:
            q = search.lower()
            haystack = (r.ressource_name or "").lower() + " " + (r.beschreibung or "").lower() + " " + (r.tags or "").lower()
            if q not in haystack:
                continue

        if r.wartung:
            status = "maintenance"
        else:
            aktiv = frappe.db.exists(
                "Ressourcen Buchung",
                {"ressource": r.name, "status": "Aktiv", "datum_von": ["<=", now], "datum_bis": [">=", now]},
            )
            status = "booked" if aktiv else "available"

        tags_list = [t.strip() for t in (r.tags or "").split(",") if t.strip()]
        result.append({
            "id":          r.name,
            "name":        r.ressource_name,
            "type":        _typ_key(r.typ),
            "description": r.beschreibung or "",
            "capacity":    r.kapazitaet or None,
            "status":      status,
            "tags":        tags_list,
            "image":       r.bild or None,
        })

    return result


@frappe.whitelist()
def get_ressource_buchungen(ressource_id, date_from="", date_to=""):
    """Gibt Buchungen für eine Ressource zurück."""
    _get_user()

    filters = {"ressource": ressource_id, "status": "Aktiv"}
    if date_from:
        filters["datum_bis"] = [">=", date_from]
    if date_to:
        filters["datum_von"] = ["<=", date_to]

    buchungen = frappe.get_all(
        "Ressourcen Buchung",
        filters=filters,
        fields=["name", "zweck", "datum_von", "datum_bis", "gebucht_von_name"],
        order_by="datum_von asc",
        limit=50,
    )

    result = []
    for b in buchungen:
        dv = get_datetime(b.datum_von)
        db_ = get_datetime(b.datum_bis)
        result.append({
            "id":    b.name,
            "title": b.zweck,
            "date":  dv.strftime("%Y-%m-%d"),
            "day":   dv.strftime("%d"),
            "month": dv.strftime("%b"),
            "time":  f"{dv.strftime('%H:%M')} – {db_.strftime('%H:%M')}",
            "user":  b.gebucht_von_name or "",
        })
    return result


@frappe.whitelist()
def get_meine_buchungen():
    """Gibt aktive Buchungen des aktuellen Nutzers zurück."""
    user = _get_user()

    buchungen = frappe.get_all(
        "Ressourcen Buchung",
        filters={"gebucht_von": user, "status": "Aktiv"},
        fields=["name", "ressource", "zweck", "datum_von", "datum_bis"],
        order_by="datum_von asc",
        limit=50,
    )

    result = []
    for b in buchungen:
        ressource_name = frappe.db.get_value("Ressource", b.ressource, "ressource_name") or b.ressource
        ressource_typ = frappe.db.get_value("Ressource", b.ressource, "typ") or ""
        dv = get_datetime(b.datum_von)
        db_ = get_datetime(b.datum_bis)
        result.append({
            "id":           b.name,
            "resourceId":   b.ressource,
            "resourceName": ressource_name,
            "resourceType": _typ_key(ressource_typ),
            "date":         dv.strftime("%a, %d. %b %Y"),
            "time":         f"{dv.strftime('%H:%M')} – {db_.strftime('%H:%M')}",
            "purpose":      b.zweck,
        })
    return result


@frappe.whitelist()
def check_verfuegbarkeit(ressource_id, datum_von, datum_bis, exclude_id=""):
    """Prüft ob die Ressource im Zeitraum verfügbar ist."""
    _get_user()

    filters = {
        "ressource": ressource_id,
        "status":    "Aktiv",
        "datum_von": ["<", datum_bis],
        "datum_bis": [">", datum_von],
    }
    if exclude_id:
        filters["name"] = ["!=", exclude_id]

    konflikt = frappe.get_all(
        "Ressourcen Buchung",
        filters=filters,
        fields=["name", "zweck", "datum_von", "datum_bis", "gebucht_von_name"],
        limit=1,
    )

    if not konflikt:
        return {"verfuegbar": True}

    k = konflikt[0]
    dv = get_datetime(k.datum_von)
    db_ = get_datetime(k.datum_bis)
    return {
        "verfuegbar": False,
        "konflikt": {
            "id":    k.name,
            "titel": k.zweck,
            "time":  f"{dv.strftime('%H:%M')} – {db_.strftime('%H:%M')} ({dv.strftime('%d.%m.%Y')})",
            "user":  k.gebucht_von_name or "",
        },
    }


@frappe.whitelist()
def create_buchung(ressource_id, datum_von, datum_bis, zweck, notizen=""):
    """Erstellt eine Buchung nach Konfliktprüfung."""
    user = _get_user()

    verf = check_verfuegbarkeit(ressource_id, datum_von, datum_bis)
    if not verf.get("verfuegbar"):
        k = verf["konflikt"]
        frappe.throw(
            f"Ressource bereits gebucht: {k['titel']} ({k['time']} von {k['user']})",
            frappe.ValidationError,
        )

    user_doc = frappe.db.get_value("User", user, ["full_name"], as_dict=True) or {}

    doc = frappe.get_doc({
        "doctype":          "Ressourcen Buchung",
        "ressource":        ressource_id,
        "zweck":            zweck.strip(),
        "datum_von":        datum_von,
        "datum_bis":        datum_bis,
        "notizen":          notizen.strip() if notizen else "",
        "gebucht_von":      user,
        "gebucht_von_name": user_doc.get("full_name") or user,
        "status":           "Aktiv",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "buchung_id": doc.name}


@frappe.whitelist()
def update_buchung(buchung_id, datum_von, datum_bis, zweck, notizen=""):
    """Aktualisiert eine eigene Buchung."""
    user = _get_user()

    doc = frappe.get_doc("Ressourcen Buchung", buchung_id)
    roles = frappe.get_roles()
    is_admin = "Mitgliederadministrator" in roles or "System Manager" in roles

    if doc.gebucht_von != user and not is_admin:
        frappe.throw("Keine Berechtigung.", frappe.PermissionError)

    verf = check_verfuegbarkeit(doc.ressource, datum_von, datum_bis, exclude_id=buchung_id)
    if not verf.get("verfuegbar"):
        k = verf["konflikt"]
        frappe.throw(
            f"Zeitraum bereits belegt: {k['titel']} ({k['time']})",
            frappe.ValidationError,
        )

    doc.datum_von = datum_von
    doc.datum_bis = datum_bis
    doc.zweck = zweck.strip()
    doc.notizen = notizen.strip() if notizen else ""
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def delete_buchung(buchung_id):
    """Storniert eine Buchung (setzt Status auf Storniert)."""
    user = _get_user()

    doc = frappe.get_doc("Ressourcen Buchung", buchung_id)
    roles = frappe.get_roles()
    is_admin = "Mitgliederadministrator" in roles or "System Manager" in roles

    if doc.gebucht_von != user and not is_admin:
        frappe.throw("Keine Berechtigung.", frappe.PermissionError)

    doc.status = "Storniert"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}
