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


def _artikel_to_dict(a, with_content=False):
    tags_list = [t.strip() for t in (a.tags or "").split(",") if t.strip()]
    d = {
        "id":          a.name,
        "title":       a.titel,
        "excerpt":     a.auszug or "",
        "category":    a.kategorie or "allgemein",
        "tags":        tags_list,
        "author":      a.autor or "",
        "authorAvatar": "".join(w[0].upper() for w in (a.autor or "").split()[:2]) or "?",
        "updatedAt":   str(a.modified)[:10] if a.modified else "",
        "isNew":       bool(a.ist_neu),
    }
    if with_content:
        d["content"] = frappe.db.get_value("Wiki Artikel", a.name, "inhalt") or ""
    return d


@frappe.whitelist()
def get_wiki_artikel_liste(kategorie="", search=""):
    """Gibt alle Wiki-Artikel zurück."""
    _get_user()

    filters = {}
    if kategorie:
        filters["kategorie"] = kategorie

    artikel = frappe.get_all(
        "Wiki Artikel",
        filters=filters,
        fields=["name", "titel", "kategorie", "auszug", "tags", "autor", "modified", "ist_neu"],
        order_by="modified desc",
        limit=200,
    )

    if search:
        q = search.lower()
        artikel = [
            a for a in artikel
            if q in (a.titel or "").lower()
            or q in (a.auszug or "").lower()
            or q in (a.tags or "").lower()
        ]

    return [_artikel_to_dict(a) for a in artikel]


@frappe.whitelist()
def get_wiki_artikel_detail(artikel_id):
    """Gibt einen Wiki-Artikel mit Inhalt zurück."""
    _get_user()

    a = frappe.db.get_value(
        "Wiki Artikel",
        artikel_id,
        ["name", "titel", "kategorie", "auszug", "tags", "autor", "autor_email", "modified", "ist_neu"],
        as_dict=True,
    )
    if not a:
        frappe.throw("Artikel nicht gefunden.", frappe.DoesNotExistError)

    return _artikel_to_dict(a, with_content=True)


@frappe.whitelist()
def create_wiki_artikel(titel, inhalt, kategorie="allgemein", tags="", auszug=""):
    """Erstellt einen neuen Wiki-Artikel (nur Admin)."""
    user = _get_user()
    _require_admin()

    user_doc = frappe.db.get_value("User", user, ["full_name"], as_dict=True) or {}

    doc = frappe.get_doc({
        "doctype":     "Wiki Artikel",
        "titel":       titel.strip(),
        "inhalt":      inhalt,
        "kategorie":   kategorie,
        "tags":        tags.strip() if tags else "",
        "auszug":      auszug.strip(),
        "autor":       user_doc.get("full_name") or user,
        "autor_email": user,
        "ist_neu":     1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "artikel_id": doc.name}


@frappe.whitelist()
def update_wiki_artikel(artikel_id, titel="", inhalt="", kategorie="", tags="", auszug="", ist_neu=None):
    """Aktualisiert einen Wiki-Artikel (nur Admin)."""
    _get_user()
    _require_admin()

    doc = frappe.get_doc("Wiki Artikel", artikel_id)
    if titel:
        doc.titel = titel.strip()
    if inhalt:
        doc.inhalt = inhalt
    if kategorie:
        doc.kategorie = kategorie
    if tags is not None:
        doc.tags = tags.strip()
    if auszug is not None:
        doc.auszug = auszug.strip()
    if ist_neu is not None:
        doc.ist_neu = int(ist_neu)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def delete_wiki_artikel(artikel_id):
    """Löscht einen Wiki-Artikel (nur Admin)."""
    _get_user()
    _require_admin()

    frappe.delete_doc("Wiki Artikel", artikel_id, ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def get_wiki_kategorien():
    """Gibt alle verwendeten Kategorien zurück."""
    _get_user()

    kategorien_map = {
        "technik":   {"id": "technik",   "name": "Technik",   "icon": "🔧"},
        "ablaeufe":  {"id": "ablaeufe",  "name": "Abläufe",   "icon": "📋"},
        "raeume":    {"id": "raeume",    "name": "Räume",     "icon": "🏢"},
        "kontakte":  {"id": "kontakte",  "name": "Kontakte",  "icon": "📞"},
        "faq":       {"id": "faq",       "name": "FAQ",       "icon": "❓"},
    }
    return list(kategorien_map.values())


@frappe.whitelist()
def get_wiki_tags():
    """Gibt alle verwendeten Tags zurück."""
    _get_user()

    artikel = frappe.get_all("Wiki Artikel", fields=["tags"], filters={"tags": ["!=", ""]})
    tags_set = set()
    for a in artikel:
        for tag in (a.tags or "").split(","):
            t = tag.strip()
            if t:
                tags_set.add(t)
    return sorted(tags_set)
