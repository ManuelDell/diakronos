"""Portierung von `diakonos/api/wiki.py` (P4f) — Wiki, 7 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/wiki.py`

Die SPA ruft ausschliesslich die ORIGINAL-Pfade
`diakronos.diakonos.api.wiki.<fn>` auf (hooks.py:140-146,
`frontend/src/diakonos/pages/Wiki.vue`). Dafuer traegt dieses Modul die
Konstante `FRAPPE_MODULE`.

Schema-Realitaet (geprueft, NICHT angenommen):
`inventar/live_schema_ist.tsv` fuer `tabWiki Artikel`:
  name, creation, modified, modified_by, owner, docstatus, idx, titel,
  kategorie, tags, autor, autor_email, ist_neu, auszug, inhalt

Alle im Original benutzten Felder existieren dort — es gibt aber KEINE Spalte
`gruppe`. Das Original prueft nirgends `has_column("Wiki Artikel", "gruppe")`
und filtert nirgends auf `gruppe`; der in der Karte erwaehnte Zweig kommt in
`wiki.py` nicht vor (er lebte in `gruppen.get_gruppe_detail`, siehe P4a).
Es wird deshalb auch kein solcher Zweig nachgebaut. Belegt durch
`backend/tests/test_p4f_beitraege_wiki.py::test_wiki_artikel_hat_keine_gruppe_spalte`.

Sichtbarkeit (ausdruecklich dokumentiert, weil die Karte danach fragt):
Das Original filtert `get_wiki_artikel_liste` NUR auf die optionale
`kategorie`-Angabe. Eine Pruefung auf Gruppen-/Bereichszugehoerigkeit oder
Rollen gibt es dort NICHT (kein `check_permission`, kein `ancestor_path`).
Diese Karte fuehrt deshalb KEINE zusaetzliche Bereichsfilterung ein — sie
waere eine Neuerfindung und wuerde die SPA-Sicht aendern.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user               -> session.user
    frappe.get_roles()                -> permissions.get_roles()
    frappe.get_all(...)               -> query.get_all(...)   (Zeilen sind dicts)
    frappe.db.get_value(...)          -> query.get_value(...)
    frappe.get_doc({...}).insert()    -> _create(...)
    frappe.get_doc(dt, name)          -> query.get_doc(...) -> Document
    doc.save(ignore_permissions=...)  -> _update_doc(...)
    frappe.delete_doc(dt, name, ...)  -> _delete_doc(...)
    frappe.db.commit()                -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)            -> exceptions.throw(...)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.wiki"

from typing import Any

from diakronos_app.frappe_compat.api_helpers import (
    _coerce_filters,
    _create,
    _delete_doc,
    _update_doc,
)
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
    throw,
)
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.session import session

# ── Berechtigungen (1:1 aus dem Original) ───────────────────────────────────


def _get_user():
    """Original: `_get_user()` — Guest -> PermissionError (403)."""
    user = session.user
    if user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)
    return user


def _require_admin():
    """Original: `_require_admin()` — Mitgliederadministrator ODER System Manager."""
    roles = permissions.get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        throw("Nur für Administratoren.", FrappePermissionError)


def _avatar(name: str | None) -> str:
    """`"".join(w[0].upper() for w in (name or "").split()[:2]) or "?"`."""
    return "".join(w[0].upper() for w in (name or "").split()[:2]) or "?"


def _artikel_to_dict(a, with_content=False):
    """Original: `_artikel_to_dict(a, with_content=False)`.

    `a` ist bei Liste und Detail ein dict (`get_all` bzw.
    `get_value(as_dict=True)`); Werte identisch zum Original.
    """
    tags_list = [t.strip() for t in (a["tags"] or "").split(",") if t.strip()]
    d = {
        "id":           a["name"],
        "title":        a["titel"],
        "excerpt":      a["auszug"] or "",
        "category":     a["kategorie"] or "allgemein",
        "tags":         tags_list,
        "author":       a["autor"] or "",
        "authorAvatar": _avatar(a["autor"]),
        "updatedAt":    str(a["modified"])[:10] if a["modified"] else "",
        "isNew":        bool(a["ist_neu"]),
    }
    if with_content:
        d["content"] = get_value("Wiki Artikel", a["name"], "inhalt") or ""
    return d


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_wiki_artikel_liste(kategorie="", search=""):
    """Gibt alle Wiki-Artikel zurück.

    Filtert NUR auf die optionale `kategorie` — genau wie das Original.
    Keine Bereichs-/Rollenfilterung, siehe Modul-Docstring.
    """
    _get_user()

    filters = {}
    if kategorie:
        filters["kategorie"] = kategorie

    artikel = get_all(
        "Wiki Artikel",
        filters=_coerce_filters("Wiki Artikel", filters),
        fields=["name", "titel", "kategorie", "auszug", "tags", "autor", "modified", "ist_neu"],
        order_by="modified desc",
        limit_page_length=200,
    )

    if search:
        q = search.lower()
        artikel = [
            a for a in artikel
            if q in (a.get("titel") or "").lower()
            or q in (a.get("auszug") or "").lower()
            or q in (a.get("tags") or "").lower()
        ]

    return [_artikel_to_dict(a) for a in artikel]


@whitelist(allow_guest=False)
def get_wiki_artikel_detail(artikel_id):
    """Gibt einen Wiki-Artikel mit Inhalt zurück."""
    _get_user()

    a = get_value(
        "Wiki Artikel",
        artikel_id,
        ["name", "titel", "kategorie", "auszug", "tags", "autor", "autor_email", "modified", "ist_neu"],
        as_dict=True,
    )
    if not a:
        throw("Artikel nicht gefunden.", DoesNotExistError)

    return _artikel_to_dict(a, with_content=True)


@whitelist(allow_guest=False)
def create_wiki_artikel(titel, inhalt, kategorie="allgemein", tags="", auszug=""):
    """Erstellt einen neuen Wiki-Artikel (nur Admin).

    `ist_neu` ist im Original `1` (Check-Feld) — hier derselbe Wert.
    """
    user = _get_user()
    _require_admin()

    user_doc = get_value("User", user, ["full_name"], as_dict=True) or {}

    artikel_id = _create("Wiki Artikel", {
        "titel":       titel.strip(),
        "inhalt":      inhalt,
        "kategorie":   kategorie,
        "tags":        tags.strip() if tags else "",
        "auszug":      auszug.strip(),
        "autor":       user_doc.get("full_name") or user,
        "autor_email": user,
        "ist_neu":     1,
    })

    return {"success": True, "artikel_id": artikel_id}


@whitelist(allow_guest=False)
def update_wiki_artikel(artikel_id, titel="", inhalt="", kategorie="", tags="", auszug="", ist_neu=None):
    """Aktualisiert einen Wiki-Artikel (nur Admin).

    Die `if`-Kette des Originals entscheidet, WELCHE Felder geschrieben
    werden. `tags`/`auszug`/`ist_neu` werden (anders als `titel`) schon bei
    Leerstring gesetzt — deshalb wird hier `is not None` geprueft und nicht
    auf Wahrheitswert.
    """
    _get_user()
    _require_admin()

    doc = get_doc("Wiki Artikel", artikel_id)

    updates: dict[str, Any] = {}
    if titel:
        updates["titel"] = titel.strip()
    if inhalt:
        updates["inhalt"] = inhalt
    if kategorie:
        updates["kategorie"] = kategorie
    if tags is not None:
        updates["tags"] = tags.strip()
    if auszug is not None:
        updates["auszug"] = auszug.strip()
    if ist_neu is not None:
        updates["ist_neu"] = int(ist_neu)

    _update_doc("Wiki Artikel", doc.name, updates)

    return {"success": True}


@whitelist(allow_guest=False)
def delete_wiki_artikel(artikel_id):
    """Löscht einen Wiki-Artikel (nur Admin).

    Wie im Original ist die einzige Schranke `_require_admin()` — kein
    gesondertes Verbot fuer fremde Artikel.
    """
    _get_user()
    _require_admin()

    _delete_doc("Wiki Artikel", artikel_id)

    return {"success": True}


@whitelist(allow_guest=False)
def get_wiki_kategorien():
    """Gibt alle verwendeten Kategorien zurück.

    Statische Liste des Originals (fest verdrahtete 5 Kategorien) — bewusst
    NICHT aus der Datenbank abgeleitet, sonst waere die Antwort eine andere.
    """
    _get_user()

    kategorien_map = {
        "technik":   {"id": "technik",   "name": "Technik",   "icon": "🔧"},
        "ablaeufe":  {"id": "ablaeufe",  "name": "Abläufe",   "icon": "📋"},
        "raeume":    {"id": "raeume",    "name": "Räume",     "icon": "🏢"},
        "kontakte":  {"id": "kontakte",  "name": "Kontakte",  "icon": "📞"},
        "faq":       {"id": "faq",       "name": "FAQ",       "icon": "❓"},
    }
    return list(kategorien_map.values())


@whitelist(allow_guest=False)
def get_wiki_tags():
    """Gibt alle verwendeten Tags zurück.

    Filter des Originals: `{"tags": ["!=", ""]}` — nur Artikel mit
    nicht-leerem Tag-Feld. Sortiert per `sorted()` (case-sensitiv, wie dort).
    """
    _get_user()

    artikel = get_all(
        "Wiki Artikel",
        fields=["tags"],
        filters=_coerce_filters("Wiki Artikel", {"tags": ["!=", ""]}),
    )
    tags_set = set()
    for a in artikel:
        for tag in (a["tags"] or "").split(","):
            t = tag.strip()
            if t:
                tags_set.add(t)
    return sorted(tags_set)


__all__ = [
    "create_wiki_artikel",
    "delete_wiki_artikel",
    "get_wiki_artikel_detail",
    "get_wiki_artikel_liste",
    "get_wiki_kategorien",
    "get_wiki_tags",
    "update_wiki_artikel",
]
