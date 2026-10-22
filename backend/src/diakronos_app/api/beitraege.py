"""Portierung von `diakonos/api/beitraege.py` (P4f) — Gemeinde-Feed, 6 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/beitraege.py`

Die SPA ruft ausschliesslich die ORIGINAL-Pfade
`diakronos.diakonos.api.beitraege.<fn>` auf (hooks.py:133-138,
`frontend/src/diakonos/pages/Beitraege.vue`). Dafuer traegt dieses Modul die
Konstante `FRAPPE_MODULE`.

Schema-Realitaet (geprueft, NICHT angenommen):
`inventar/live_schema_ist.tsv` fuer `tabBeitrag` und
`inventar/live_schema_ist.tsv` fuer `tabBeitrag Kommentar`.
Alle im Original benutzten Felder existieren dort:
  Beitrag:          name, titel, kategorie, datum, autor, autor_email,
                    veroeffentlicht, auszug, inhalt, bild
  Beitrag Kommentar: name, autor, autor_email, datum, text, parent,
                     parentfield, parenttype
`tabBeitrag Kommentar` hat `parent`/`parentfield`/`parenttype` und `idx` —
es ist die Frappe-Kindtabelle von `Beitrag` zum Feld `kommentare`
(`Beitrag.kommentare` in `models/diakonos.py:260`). Das Original benutzt
`frappe.get_all("Beitrag Kommentar", filters={"parent": b.name})` und
`doc.append("kommentare", {...})`; beides wird 1:1 uebernommen.

Sichtbarkeit (ausdruecklich dokumentiert, weil die Karte danach fragt):
Das Original filtert `get_beitraege_liste` NUR auf `veroeffentlicht = 1`.
Eine Pruefung auf Gruppen-/Bereichszugehoerigkeit oder Rollen gibt es dort
NICHT (kein `check_permission`, kein `ancestor_path`). Diese Karte fuehrt
deshalb KEINE zusaetzliche Bereichsfilterung ein — sie wuerde die SPA-Sicht
aendern und waere eine Neuerfindung. Belegt durch
`backend/tests/test_p4f_beitraege_wiki.py::test_liste_hat_keine_bereichsfilterung_belegt`.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user               -> session.user
    frappe.get_roles()                -> permissions.get_roles()
    frappe.get_all(...)               -> query.get_all(...)   (Zeilen sind dicts)
    frappe.db.count(...)              -> db.count(...)
    frappe.db.get_value(...)          -> query.get_value(...)
    frappe.get_doc({...}).insert()    -> _create(...)
    frappe.get_doc(dt, name)          -> query.get_doc(...) -> Document
    doc.append("kommentare", {...})   -> _child_insert(...)
    doc.save(ignore_permissions=...)  -> _update_doc(...)
    frappe.delete_doc(dt, name, ...)  -> _delete_doc(...)
    frappe.db.commit()                -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)            -> exceptions.throw(...)
    frappe.utils.today()              -> _today() (ISO-Datum)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.beitraege"

from typing import Any

from diakronos_app.frappe_compat.api_helpers import (
    _child_insert,
    _coerce,
    _coerce_filters,
    _create,
    _delete_doc,
    _today,
    _update_doc,
)
from diakronos_app.frappe_compat import db
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
    ValidationError,
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
    """Original: `_require_admin()` — Mitgliederadministrator ODER System Manager.

    Die Rollenliste ist exakt die des Originals (`frappe.get_roles()`); die
    Compat-Umsetzung ist `permissions.get_roles()` (`tabHas Role`).
    """
    roles = permissions.get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        throw("Nur für Administratoren.", FrappePermissionError)


def _avatar(name: str | None) -> str:
    """`"".join(w[0].upper() for w in (name or "").split()[:2]) or "?"`."""
    return "".join(w[0].upper() for w in (name or "").split()[:2]) or "?"


def _beitrag_to_dict(b, with_kommentare=False):
    """Original: `_beitrag_to_dict(b, with_kommentare=False)`.

    `b` ist beim Detail-Aufruf ein dict (aus `db.get_value(as_dict=True)`), bei
    der Liste ein dict (aus `get_all`). Beide Zugriffe laufen daher ueber
    `dict.get`, nicht ueber Attribute — Frappe liefert in beiden Faellen
    attribute-basierte Objekte, deren Werte identisch sind.
    """
    d = {
        "id":       b.get("name"),
        "title":    b.get("titel"),
        "excerpt":  b.get("auszug") or "",
        "category": b.get("kategorie") or "allgemein",
        "image":    b.get("bild") or "",
        "author":   b.get("autor") or "",
        "date":     str(b.get("datum")) if b.get("datum") else "",
        "comments": 0,
    }
    if with_kommentare:
        kommentare = get_all(
            "Beitrag Kommentar",
            filters={"parent": b.get("name")},
            fields=["name", "autor", "autor_email", "text", "datum"],
            order_by="datum asc",
        )
        d["comments"] = len(kommentare)
        d["commentList"] = [
            {
                "id":     k.get("name"),
                "author": k.get("autor") or "",
                "avatar": _avatar(k.get("autor")),
                "text":   k.get("text") or "",
                "date":   str(k.get("datum")) if k.get("datum") else "",
            }
            for k in kommentare
        ]
        d["content"] = get_value("Beitrag", b.get("name"), "inhalt") or ""
    return d


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_beitraege_liste(kategorie="", search=""):
    """Gibt alle veröffentlichten Beiträge zurück.

    Filtert NUR auf `veroeffentlicht = 1` (und optional `kategorie`) — genau
    wie das Original. Keine Bereichs-/Rollenfilterung, siehe Modul-Docstring.
    """
    _get_user()

    filters = {"veroeffentlicht": 1}
    if kategorie:
        filters["kategorie"] = kategorie

    beitraege = get_all(
        "Beitrag",
        filters=_coerce_filters("Beitrag", filters),
        fields=["name", "titel", "kategorie", "auszug", "bild", "autor", "datum"],
        order_by="datum desc",
        limit_page_length=100,
    )

    if search:
        q = search.lower()
        beitraege = [
            b for b in beitraege
            if q in (b.get("titel") or "").lower()
            or q in (b.get("auszug") or "").lower()
            or q in (b.get("autor") or "").lower()
        ]

    result = []
    for b in beitraege:
        d = _beitrag_to_dict(b)
        d["comments"] = db.count("Beitrag Kommentar", {"parent": b.get("name")})
        result.append(d)

    return result


def _require_beitrag_view(b, user):
    # Nicht vorhandene und verborgene Beitraege sind von aussen identisch.
    if not b or (
        b.get("veroeffentlicht") != 1
        and b.get("autor_email") != user
        and not any(role in permissions.get_roles(user) for role in permissions.ADMIN_ROLES)
    ):
        throw("Beitrag nicht gefunden.", DoesNotExistError)


@whitelist(allow_guest=False)
def get_beitrag_detail(beitrag_id):
    """Gibt sichtbare Beitraege mit Inhalt und Kommentaren zurueck."""
    user = _get_user()

    b = get_value(
        "Beitrag",
        beitrag_id,
        ["name", "titel", "kategorie", "auszug", "bild", "autor", "autor_email", "datum", "veroeffentlicht"],
        as_dict=True,
    )
    _require_beitrag_view(b, user)
    return _beitrag_to_dict(b, with_kommentare=True)


@whitelist(allow_guest=False)
def create_beitrag(titel, inhalt, kategorie="allgemein", auszug="", bild=""):
    """Erstellt einen neuen Beitrag (nur Admin).

    Das Original baut ein `frappe.get_doc({...})`-Dict; hier geht derselbe
    Wertsatz durch `_create()` (kein Dict-Insert am `Document`).
    """
    user = _get_user()
    _require_admin()

    user_doc = get_value("User", user, ["full_name"], as_dict=True) or {}

    beitrag_id = _create("Beitrag", {
        "titel":           titel.strip(),
        "inhalt":          inhalt,
        "kategorie":       kategorie,
        "auszug":          auszug.strip(),
        "bild":            bild or None,
        "autor":           user_doc.get("full_name") or user,
        "autor_email":     user,
        "datum":           _today(),
        "veroeffentlicht": 1,
    })

    return {"success": True, "beitrag_id": beitrag_id}


@whitelist(allow_guest=False)
def update_beitrag(beitrag_id, titel="", inhalt="", kategorie="", auszug="", bild=""):
    """Aktualisiert einen Beitrag (nur Admin).

    Die `if`-Kette des Originals entscheidet, WELCHE Felder geschrieben
    werden (`bild or None` setzt ein leeres Bild ausdruecklich auf NULL).
    `_update_doc` schreibt nur nicht-None-Werte — dieselbe Wirkung.
    """
    _get_user()
    _require_admin()

    doc = get_doc("Beitrag", beitrag_id)

    updates: dict[str, Any] = {}
    if titel:
        updates["titel"] = titel.strip()
    if inhalt:
        updates["inhalt"] = inhalt
    if kategorie:
        updates["kategorie"] = kategorie
    if auszug is not None:
        updates["auszug"] = auszug.strip()
    if bild is not None:
        updates["bild"] = bild or None

    _update_doc("Beitrag", doc.name, updates)

    return {"success": True}


@whitelist(allow_guest=False)
def delete_beitrag(beitrag_id):
    """Löscht einen Beitrag (nur Admin).

    Auch das Original verbietet das Loeschen eines FREMDEN Beitrags nicht
    gesondert — die einzige Schranke ist `_require_admin()`. Genau so bleibt
    es hier (keine Verschaerfung, keine Lockerung).
    """
    _get_user()
    _require_admin()

    _delete_doc("Beitrag", beitrag_id)

    return {"success": True}


@whitelist(allow_guest=False)
def create_kommentar(beitrag_id, text):
    """Fügt einen Kommentar hinzu.

    `Beitrag Kommentar` ist eine Kindtabelle von `Beitrag` (Feld
    `kommentare`, `tabBeitrag Kommentar` mit parent/parentfield/parenttype).
    Das Original haengt eine Zeile an und liest sie danach aus
    `doc.kommentare[-1]` zurueck; hier liefert `_child_insert` direkt den
    `name` der neuen Zeile.
    """
    user = _get_user()

    if not text or not text.strip():
        throw("Kommentar darf nicht leer sein.", ValidationError)

    b = get_value("Beitrag", beitrag_id, ["veroeffentlicht", "autor_email"], as_dict=True)
    _require_beitrag_view(b, user)

    user_doc = get_value("User", user, ["full_name"], as_dict=True) or {}
    autor = user_doc.get("full_name") or user
    datum = _today()

    kommentar_name = _child_insert(
        "Beitrag Kommentar",
        beitrag_id,
        "kommentare",
        {
            "autor":       autor,
            "autor_email": user,
            "text":        text.strip(),
            "datum":       datum,
        },
        parenttype="Beitrag",
    )

    # Antwortform des Originals: `str(kommentar.datum)` des frisch gelesenen
    # Feldes (Frappe liefert dort "YYYY-MM-DD").
    datum_str = _coerce("Beitrag Kommentar", {"datum": datum}).get("datum")
    return {
        "success": True,
        "kommentar": {
            "id":     kommentar_name,
            "author": autor,
            "avatar": _avatar(autor),
            "text":   text.strip(),
            "date":   str(datum_str),
        },
    }


__all__ = [
    "create_beitrag",
    "create_kommentar",
    "delete_beitrag",
    "get_beitraege_liste",
    "get_beitrag_detail",
    "update_beitrag",
]
