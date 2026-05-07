import frappe
from frappe.utils import today


def _get_user():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Anmeldung erforderlich.", frappe.PermissionError)
    return user


def _require_admin():
    roles = frappe.get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        frappe.throw("Nur für Administratoren.", frappe.PermissionError)


def _beitrag_to_dict(b, with_kommentare=False):
    d = {
        "id":       b.name,
        "title":    b.titel,
        "excerpt":  b.auszug or "",
        "category": b.kategorie or "allgemein",
        "image":    b.bild or "",
        "author":   b.autor or "",
        "date":     str(b.datum) if b.datum else "",
        "comments": 0,
    }
    if with_kommentare:
        kommentare = frappe.get_all(
            "Beitrag Kommentar",
            filters={"parent": b.name},
            fields=["name", "autor", "autor_email", "text", "datum"],
            order_by="datum asc",
        )
        d["comments"] = len(kommentare)
        d["commentList"] = [
            {
                "id":     k.name,
                "author": k.autor or "",
                "avatar": "".join(w[0].upper() for w in (k.autor or "").split()[:2]) or "?",
                "text":   k.text or "",
                "date":   str(k.datum) if k.datum else "",
            }
            for k in kommentare
        ]
        d["content"] = frappe.db.get_value("Beitrag", b.name, "inhalt") or ""
    return d


@frappe.whitelist()
def get_beitraege_liste(kategorie="", search=""):
    """Gibt alle veröffentlichten Beiträge zurück."""
    _get_user()

    filters = {"veroeffentlicht": 1}
    if kategorie:
        filters["kategorie"] = kategorie

    beitraege = frappe.get_all(
        "Beitrag",
        filters=filters,
        fields=["name", "titel", "kategorie", "auszug", "bild", "autor", "datum"],
        order_by="datum desc",
        limit=100,
    )

    if search:
        q = search.lower()
        beitraege = [
            b for b in beitraege
            if q in (b.titel or "").lower() or q in (b.auszug or "").lower() or q in (b.autor or "").lower()
        ]

    result = []
    for b in beitraege:
        d = _beitrag_to_dict(b)
        count = frappe.db.count("Beitrag Kommentar", {"parent": b.name})
        d["comments"] = count
        result.append(d)

    return result


@frappe.whitelist()
def get_beitrag_detail(beitrag_id):
    """Gibt einen Beitrag mit Inhalt und Kommentaren zurück."""
    _get_user()

    b = frappe.db.get_value(
        "Beitrag",
        beitrag_id,
        ["name", "titel", "kategorie", "auszug", "bild", "autor", "autor_email", "datum", "veroeffentlicht"],
        as_dict=True,
    )
    if not b:
        frappe.throw("Beitrag nicht gefunden.", frappe.DoesNotExistError)

    return _beitrag_to_dict(b, with_kommentare=True)


@frappe.whitelist()
def create_beitrag(titel, inhalt, kategorie="allgemein", auszug="", bild=""):
    """Erstellt einen neuen Beitrag (nur Admin)."""
    user = _get_user()
    _require_admin()

    user_doc = frappe.db.get_value("User", user, ["full_name"], as_dict=True) or {}

    doc = frappe.get_doc({
        "doctype":       "Beitrag",
        "titel":         titel.strip(),
        "inhalt":        inhalt,
        "kategorie":     kategorie,
        "auszug":        auszug.strip(),
        "bild":          bild or None,
        "autor":         user_doc.get("full_name") or user,
        "autor_email":   user,
        "datum":         today(),
        "veroeffentlicht": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "beitrag_id": doc.name}


@frappe.whitelist()
def update_beitrag(beitrag_id, titel="", inhalt="", kategorie="", auszug="", bild=""):
    """Aktualisiert einen Beitrag (nur Admin)."""
    _get_user()
    _require_admin()

    doc = frappe.get_doc("Beitrag", beitrag_id)
    if titel:
        doc.titel = titel.strip()
    if inhalt:
        doc.inhalt = inhalt
    if kategorie:
        doc.kategorie = kategorie
    if auszug is not None:
        doc.auszug = auszug.strip()
    if bild is not None:
        doc.bild = bild or None
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def delete_beitrag(beitrag_id):
    """Löscht einen Beitrag (nur Admin)."""
    _get_user()
    _require_admin()

    frappe.delete_doc("Beitrag", beitrag_id, ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def create_kommentar(beitrag_id, text):
    """Fügt einen Kommentar hinzu."""
    user = _get_user()

    if not text or not text.strip():
        frappe.throw("Kommentar darf nicht leer sein.", frappe.ValidationError)

    user_doc = frappe.db.get_value("User", user, ["full_name"], as_dict=True) or {}

    doc = frappe.get_doc("Beitrag", beitrag_id)
    doc.append("kommentare", {
        "autor":       user_doc.get("full_name") or user,
        "autor_email": user,
        "text":        text.strip(),
        "datum":       today(),
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    kommentar = doc.kommentare[-1]
    return {
        "success": True,
        "kommentar": {
            "id":     kommentar.name,
            "author": kommentar.autor,
            "avatar": "".join(w[0].upper() for w in (kommentar.autor or "").split()[:2]) or "?",
            "text":   kommentar.text,
            "date":   str(kommentar.datum),
        },
    }
