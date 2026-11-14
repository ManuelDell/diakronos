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

from datetime import timedelta
from typing import Any

from diakronos_app import papierkorb
from diakronos_app.frappe_compat.api_helpers import (
    _coerce_filters,
    _create,
    _delete_doc,
    _update_doc,
)
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
    throw,
)
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.session import session
from diakronos_app.zeit import zeit_text

# ── Berechtigungen (1:1 aus dem Original) ───────────────────────────────────


def _get_user():
    """Original: `_get_user()` — Guest -> PermissionError (403)."""
    user = session.user
    if user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)
    return user


# ── R-7: EIN Rechtesystem (Lesen/Anlegen/Verwalten ueber den Kern) ─────────


def _darf(aktion: str, objekt: str | None = None, **kw) -> bool:
    from diakronos_app import rechte

    return bool(rechte.darf(session.user, aktion, "wiki", objekt, **kw))


def _pruefe_verwalten(objekt: str) -> None:
    from diakronos_app import rechte

    rechte.pruefe(session.user, rechte.VERWALTEN, "wiki", objekt)


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
        # ZEIT-3: ``modified`` ist ein UTC-Zeitstempel. ``str(...)[:10]`` lieferte
        # zwischen 0 und 2 Uhr Ortszeit den Vortag; geliefert wird jetzt der
        # Kalendertag in der Zeitzone der Gemeinde (gespeichert bleibt UTC).
        # Vertrag bleibt `JJJJ-MM-TT` (Wiki.vue liest ein Datum, ZEIT-2).
        "updatedAt":    (zeit_text(a["modified"]) or "")[:10],
        "isNew":        bool(a["ist_neu"]),
    }
    if with_content:
        d["content"] = get_value("Wiki Artikel", a["name"], "inhalt") or ""
    return d


# ── Endpunkte ───────────────────────────────────────────────────────────────


def _tripel(doctype: str, filters: dict) -> list[list]:
    """`{"feld": wert}` / `{"feld": [op, wert]}` -> `[[feld, op, wert], …]`.

    Fuer das Zusammenfuehren mit `papierkorb.nur_aktive_filter`, das selbst
    Tripel liefert — der Filter-Compiler versteht eine GEMISCHTE Liste aus
    Tripeln und Dict-Eintraegen nicht (UX2b).
    """
    tripel: list[list] = []
    for feld, spec in _coerce_filters(doctype, filters).items():
        if isinstance(spec, (list, tuple)) and len(spec) == 2 and isinstance(spec[0], str):
            tripel.append([feld, spec[0], spec[1]])
        else:
            tripel.append([feld, "=", spec])
    return tripel


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
        # UX2b: ein Artikel im Papierkorb ist in Liste, Detail und Tag-Wolke weg.
        filters=[*_tripel("Wiki Artikel", filters), ["geloescht_am", "is", "not set"]],
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

    # R-7: nur, was der Kern lesen laesst (Gruppe/Freigabe/Gemeinde).
    from diakronos_app import rechte

    ergebnis = []
    for a in artikel:
        if not _darf(rechte.LESEN, a.get("name")):
            continue
        d = _artikel_to_dict(a)
        d["darf_bearbeiten"] = _darf(rechte.VERWALTEN, a.get("name"))
        ergebnis.append(d)
    return ergebnis


@whitelist(allow_guest=False)
def get_wiki_artikel_detail(artikel_id):
    """Gibt einen Wiki-Artikel mit Inhalt zurück."""
    _get_user()

    a = get_value(
        "Wiki Artikel",
        artikel_id,
        ["name", "titel", "kategorie", "auszug", "tags", "autor", "autor_email", "modified",
         "ist_neu", "geloescht_am"],
        as_dict=True,
    )
    if not a or a.get("geloescht_am") is not None:
        throw("Artikel nicht gefunden.", DoesNotExistError)
    # R-7: Leserecht ueber den Kern (Gruppe/Freigabe/Gemeinde).
    from diakronos_app import rechte

    if not (_darf(rechte.LESEN, artikel_id) or _darf(rechte.VERWALTEN, artikel_id)):
        throw("Artikel nicht gefunden.", DoesNotExistError)

    d = _artikel_to_dict(a, with_content=True)
    # R-12l: dieselbe Pruefung wie in der Liste (Leseseite: Aendern-Knoepfe).
    d["darf_bearbeiten"] = _darf(rechte.VERWALTEN, artikel_id)
    return d


@whitelist(methods=["POST"], allow_guest=False)
def create_wiki_artikel(titel, inhalt, kategorie="allgemein", tags="", auszug="",
                        gruppe=None, untergruppe=None):
    """Erstellt einen neuen Wiki-Artikel — R-7: HV/MV (bzw. GL) in ihrer
    Gruppe, gemeindeweit nur der Admin.

    `ist_neu` ist im Original `1` (Check-Feld) — hier derselbe Wert.
    """
    user = _get_user()
    from diakronos_app.rechte import verwaltung as _rv

    gruppe = str(gruppe or "").strip() or None
    untergruppe = str(untergruppe or "").strip() or None
    _rv.pruefe_inhalt_anlegen(user, "wiki", gruppe, untergruppe)

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
    _rv.inhalt_anmelden(user, "wiki", artikel_id, gruppe, untergruppe)

    return {"success": True, "artikel_id": artikel_id}


@whitelist(methods=["POST"], allow_guest=False)
def update_wiki_artikel(artikel_id, titel="", inhalt="", kategorie="", tags="", auszug="", ist_neu=None):
    """Aktualisiert einen Wiki-Artikel (nur Admin).

    Die `if`-Kette des Originals entscheidet, WELCHE Felder geschrieben
    werden. `tags`/`auszug`/`ist_neu` werden (anders als `titel`) schon bei
    Leerstring gesetzt — deshalb wird hier `is not None` geprueft und nicht
    auf Wahrheitswert.
    """
    _get_user()
    _pruefe_verwalten(artikel_id)  # R-7

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


@whitelist(methods=["POST"], allow_guest=False)
def delete_wiki_artikel(artikel_id):
    """Legt einen Wiki-Artikel in den Papierkorb (nur Admin) — UX2b.

    Wie im Original ist die einzige Schranke `_require_admin()` — kein
    gesondertes Verbot fuer fremde Artikel. API-kompatibel (Karte P4): die
    Antwort traegt weiter ``success`` und zusaetzlich die Kennung fuer
    „Rueckgaengig“ (``wiederherstellbar_bis``).
    """
    user = _get_user()
    _pruefe_verwalten(artikel_id)  # R-7

    try:
        zeitpunkt = papierkorb.loeschen("Wiki Artikel", artikel_id, von=user)
    except DoesNotExistError:
        throw("Artikel nicht gefunden.", DoesNotExistError)

    return {
        "success": True,
        "geloescht_am": zeitpunkt.isoformat(sep=" "),
        "wiederherstellbar_bis": (zeitpunkt + timedelta(days=papierkorb.AUFBEWAHRUNG_TAGE)).isoformat(sep=" "),
    }


@whitelist(methods=["POST"], allow_guest=False)
def wiederherstellen_wiki_artikel(artikel_id):
    """Holt einen Wiki-Artikel aus dem Papierkorb (nur Admin) — UX2b P2."""
    _get_user()
    _pruefe_verwalten(artikel_id)  # R-7

    try:
        papierkorb.wiederherstellen("Wiki Artikel", artikel_id)
    except DoesNotExistError:
        throw("Artikel nicht gefunden.", DoesNotExistError)

    return {"success": True, "artikel_id": artikel_id}


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
        filters=[["tags", "!=", ""], ["geloescht_am", "is", "not set"]],
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
    "wiederherstellen_wiki_artikel",
]
