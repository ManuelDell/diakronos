"""Portierung von `diakonos/api/dienstplan.py` (P4h) — Mitglieder-Sicht, 3 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/dienstplan.py`

NICHT zu verwechseln mit `api/planung.py` (Plan-ERSTELLUNG, bereits gemergt).
Dieses Modul ist die MITGLIEDER-Sicht:

    get_dienstrollen      Rollen-Stammdaten (fuer das Kronos-Modal)
    get_dienstplan        Dienstplan-Eintraege eines Zeitraums (bereichsgefiltert)
    get_meine_dienste     die eigenen kommenden Dienste des aktuellen Users

`api/planung.py` wird von dieser Karte NICHT angefasst.

Die SPA ruft die ORIGINAL-Pfade `diakronos.diakonos.api.dienstplan.<fn>` auf
(hooks.py; `MeineDienste.vue`, Kronos-Rollenauswahl). Dafuer traegt dieses
Modul die Konstante `FRAPPE_MODULE`.

Schema-Realitaet (geprueft gegen `Spaltenabzug der Betriebs-DB`):

  Dienstplan (Z. 30): ist_entwurf, dienstbereich, gruppe vorhanden.
  Dienstrolle (Z. 31): rollenname, farbe vorhanden.
  Element Mitarbeiter: parent, parentfield, mitglied, dienstrolle, bestaetigt, idx
  Gruppe: dienstbereich, ancestor_path vorhanden.
  Eventkategorie: terminart vorhanden.
  Ablaufplan Position: reihenfolge, bezeichnung, dauer_minuten,
      verantwortlicher, notiz, referenz_doctype, referenz_name, funktion,
      gruppe, detail — alle vorhanden.

Sichtbarkeit (ausdruecklich dokumentiert, weil die Karte danach fragt):

  `get_meine_dienste` liefert die Dienste des AKTUELLEN Users. Die Schranke
  ist doppelt: (1) `Element Mitarbeiter.mitglied = <eigenes Mitglied>` waehlt
  die Kandidaten, (2) `entry["mitglied"] != current_mitglied -> continue`
  wirft danach die Mitarbeiter-Zeilen ANDERER Personen desselben Elements
  heraus. Beides 1:1 uebernommen und per Test belegt.

  `get_dienstplan` filtert je Eintrag den Dienstbereich der Gruppe des
  Elements (ueber `has_bereichs_zugriff`, P3-Spec) UND — die eigentlich
  wirksame Schranke — nach Kalender-Sichtbarkeit
  (`get_accessible_calendars`, dieselbe Regel wie im Kalender und in
  `ablaufplan_api.get_termine_am_tag`). Der Dienstbereich der Gruppe reicht
  NICHT, weil `Element.gruppe` auf Bestandsterminen leer ist.

Entwurfs-Schranke: `_filter_entwurf_elements` entfernt Elemente, deren
Dienstplan ein Entwurf ist (`ist_entwurf = 1`) — ein zurueckgezogener Plan
darf in keinem Endpunkt als Dienst auftauchen.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user            -> session.user
    frappe.get_roles(user)         -> permissions.get_roles(user)
    frappe.get_all(...)            -> query.get_all(...)   (Zeilen sind dicts)
    frappe.db.get_value(...)       -> query.get_value(...)
    frappe.db.exists(...)          -> _exists(...)  (count > 0)
    frappe.get_doc(dt, name)       -> query.get_doc(...) -> Document
    frappe.throw(msg, exc)         -> throw(msg, exc)
    frappe.db.sql(...)             -> get_all(...) + Python-Aggregation
    `_permissions.has_bereichs_zugriff` -> permissions.has_bereichs_zugriff
    `kronos.api.permissions.get_accessible_calendars` -> api.kronos.permissions
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.dienstplan"

import datetime

from diakronos_app.frappe_compat.api_helpers import (
    _child_rows,
    _coerce_filters,
    get_all,
    get_doc,
    get_value,
    throw,
)
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session

from diakronos_app.api.kronos.permissions import get_accessible_calendars

__all__ = ["get_dienstplan", "get_dienstrollen", "get_meine_dienste"]


ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


# ── Compat-Helfer ───────────────────────────────────────────────────────────


def _exists(doctype: str, filters) -> bool:
    """`frappe.db.exists(doctype, filters)` — String-Name -> `{"name": ...}`."""
    from diakronos_app.frappe_compat import db as _db

    if isinstance(filters, str):
        filters = {"name": filters}
    try:
        return bool(_db.exists(doctype, filters))
    except Exception:  # noqa: BLE001 — unbekannter DocType -> nicht vorhanden
        return False


def _throw_if_guest() -> None:
    """`frappe.session.user == "Guest"` -> PermissionError (403).

    Entspricht den drei identischen Guards des Originals
    (dienstplan.py:231, 247, 312).
    """
    if session.user == "Guest":
        throw("Nicht angemeldet", FrappePermissionError)


def _now_str() -> str:
    """`datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")`.

    Hinweis: nur fuer die Ausgabe. Vergleiche gegen die `timestamp`-Spalte
    `Element.element_start` MUESSEN `datetime`-Objekte sein — die Compat-Schicht
    bindet Strings als VARCHAR und Postgres lehnt
    `timestamp >= varchar` ab (verifiziert).
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _day_start(day) -> datetime.datetime:
    """Tagesbeginn als `datetime` (fuer `element_start >= ...`)."""
    if isinstance(day, datetime.datetime):
        return day
    if isinstance(day, datetime.date):
        return datetime.datetime(day.year, day.month, day.day)
    year, month, dom = (int(p) for p in str(day)[:10].split("-"))
    return datetime.datetime(year, month, dom)


def _day_end(day) -> datetime.datetime:
    """Tagesende 23:59:59 als `datetime` (fuer `element_start <= ...`)."""
    return _day_start(day).replace(hour=23, minute=59, second=59)


def _first_of_next_month(year: int, month: int) -> datetime.datetime:
    """Erster Tag des Folgemonats, 00:00:00 (exklusive Obergrenze)."""
    return datetime.datetime(year + 1, 1, 1) if month == 12 else datetime.datetime(year, month + 1, 1)


# ── Berechtigungs-Helfer (1:1 aus dem Original) ─────────────────────────────


def _is_admin() -> bool:
    """True wenn der aktuelle User Admin-Rollen hat (Vollzugriff).

    Quelle: dienstplan.py:15-20. Nutzt die Rollen des angemeldeten Users
    (inkl. `Administrator`-Sonderfall vor der Rollenpruefung).
    """
    user = session.user
    if user == "Administrator":
        return True
    return any(r in permissions.get_roles(user) for r in ADMIN_ROLES)


def _current_user_mitglied_name():
    """Holt den Mitglied-Namen des aktuellen Users (ueber user-Link, Fallback email).

    Quelle: dienstplan.py:23-32. Das ist die zentrale Sichtbarkeits-Bindung:
    ohne eigenen Mitgliedssatz gibt es keine eigenen Dienste.
    """
    user = session.user
    if user in ("Guest", "Administrator"):
        return None
    name = get_value("Mitglied", {"user": user}, "name")
    if not name:
        email = get_value("User", user, "email") or user
        name = get_value("Mitglied", {"email": email}, "name")
    return name


def _element_dienstbereich(element):
    """Dienstbereich-Name der Gruppe eines Elements (None wenn nicht zuordenbar).

    Quelle: dienstplan.py:35-40.
    """
    gruppe = element.get("gruppe")
    if not gruppe:
        return None
    return get_value("Gruppe", gruppe, "dienstbereich")


def _can_see_dienstbereich(dienstbereich, gruppe=None):
    """Prueft Lesezugriff auf einen konkreten Dienstbereich.

    Quelle: dienstplan.py:43-56 — ein duenner Alias auf
    `_permissions.has_bereichs_zugriff`. Die Logik (Admin → Verantwortlichkeit
    → check_permission) existiert nur an EINER Stelle (P3) und wird hier NICHT
    nachgebaut.
    """
    return permissions.has_bereichs_zugriff(dienstbereich, gruppe)


# ── Datenaufbau ─────────────────────────────────────────────────────────────


def _resolve_mitarbeiter(element_names):
    """Laedt alle Element-Mitarbeiter-Zeilen zu einer Elementliste in einem Query.

    Quelle: dienstplan.py:59-116.

    Original-SQL:
        SELECT parent, mitglied, dienstrolle, bestaetigt
        FROM `tabElement Mitarbeiter` WHERE parent IN (...) ORDER BY idx ASC

    Umgestellt auf `get_all` (das Kind-Tabellen ohnehin nach `idx` sortiert):
    die Kind-Zeilen eines Elements werden je Elternteil abgefragt und in
    Reihenfolge aneinandergehaengt — Ergebnis identisch, ohne rohes SQL.
    Ausserdem werden die Mitglied- und Dienstrolle-Namen in je EINEM
    Lesevorgang aufgeloest (Original: zwei `IN`-Queries).

    Returns:
        map: {element_name: [{mitglied, mitglied_name, dienstrolle,
                              dienstrolle_name, bestaetigt}, ...]}
    """
    if not element_names:
        return {}

    rows: list[dict] = []
    for element_name in element_names:
        rows.extend(
            get_all(
                "Element Mitarbeiter",
                filters={"parent": element_name},
                fields=["parent", "mitglied", "dienstrolle", "bestaetigt"],
                order_by="idx asc",
            ) or []
        )

    mitglied_ids = {r["mitglied"] for r in rows if r.get("mitglied")}
    dienstrolle_ids = {r["dienstrolle"] for r in rows if r.get("dienstrolle")}

    # AUSTRITT-b (B1): Anzeigenamen ueber die eine Regel (Klarname einer
    # ausgetretenen Person stand hier sonst im Dienstplan).
    from diakronos_app.frappe_compat.personen_anzeige import namen_map

    mitglied_name_map = namen_map(sorted(mitglied_ids))

    dienstrolle_name_map: dict[str, str] = {}
    if dienstrolle_ids:
        drows = get_all(
            "Dienstrolle",
            filters={"name": ["in", list(dienstrolle_ids)]},
            fields=["name", "rollenname"],
        ) or []
        for d in drows:
            dienstrolle_name_map[d["name"]] = d.get("rollenname") or d["name"]

    result: dict[str, list[dict]] = {}
    for r in rows:
        # AUSTRITT-b (B1): Ist der Name nicht auflösbar, steht hier nie die
        # Kennung (sie ist oft die Adresse), sondern ein neutraler Text.
        kennung = str(r.get("mitglied") or "")
        result.setdefault(r["parent"], []).append({
            "mitglied": kennung,
            "mitglied_name": mitglied_name_map.get(kennung) or (
                "Ehemaliges Mitglied" if kennung else ""),
            "dienstrolle": r.get("dienstrolle") or "",
            "dienstrolle_name": dienstrolle_name_map.get(r.get("dienstrolle"), r.get("dienstrolle") or ""),
            "bestaetigt": int(r.get("bestaetigt") or 0),
        })
    return result


def _terminart_for(element):
    """Terminart (Vorbereitung/Einsatz/Sonstiges) der Eventkategorie eines Elements.

    Quelle: dienstplan.py:119-124.
    """
    kategorie = element.get("element_category")
    if kategorie:
        return get_value("Eventkategorie", kategorie, "terminart") or ""
    return ""


def _build_eintraege(elements):
    """Baut die Dienstplan-Eintraege aus Elementen + deren Mitarbeitern.

    Quelle: dienstplan.py:127-175. Ein Eintrag je Mitarbeiter-Zeile (Element
    joined mit Element Mitarbeiter). Elemente ohne Mitarbeiter liefern genau
    einen Eintrag mit leeren mitglied/dienstrolle-Feldern.
    """
    element_names = [e["name"] for e in elements]
    mitarbeiter_map = _resolve_mitarbeiter(element_names)
    terminart_map = {}
    for e in elements:
        terminart_map[e["name"]] = _terminart_for(e)

    eintraege = []
    for e in elements:
        ressource_name = ""
        if e.get("ressource"):
            ressource_name = get_value("Ressource", e["ressource"], "ressource_name") or ""

        base = {
            "element": e["name"],
            "element_name": e.get("element_name") or "",
            "element_start": str(e["element_start"]),
            "element_end": str(e["element_end"]) if e.get("element_end") else None,
            "element_category": e.get("element_category") or "",
            "terminart": terminart_map.get(e["name"], ""),
            "gruppe": e.get("gruppe") or "",
            "ressource_name": ressource_name,
        }

        mitarbeiter_rows = mitarbeiter_map.get(e["name"], [])
        if not mitarbeiter_rows:
            entry = dict(base)
            entry.update({
                "mitglied": "",
                "mitglied_name": "",
                "dienstrolle": "",
                "dienstrolle_name": "",
                "bestaetigt": 0,
            })
            eintraege.append(entry)
            continue

        for mr in mitarbeiter_rows:
            entry = dict(base)
            entry.update(mr)
            eintraege.append(entry)

    return eintraege


def _filter_entwurf_elements(elements):
    """Entfernt Elemente, deren Dienstplan ein Entwurf ist (ist_entwurf=1).

    Quelle: dienstplan.py:178-198. Die Verklammerung laeuft ueber
    `Element.dienstplan`.
    """
    if not elements:
        return elements
    plan_names = {e.get("dienstplan") for e in elements if e.get("dienstplan")}
    if not plan_names:
        return elements
    entwuerfe = set(
        get_all(
            "Dienstplan",
            filters=_coerce_filters(
                "Dienstplan",
                {"ist_entwurf": 1, "name": ["in", list(plan_names)]},
            ),
            fields=["name"],
            pluck="name",
        ) or []
    )
    if not entwuerfe:
        return elements
    return [e for e in elements if e.get("dienstplan") not in entwuerfe]


def _filter_by_permission(elements, current_mitglied=None):
    """Filtert Elemente ohne Lesezugriff auf den Dienstbereich ihrer Gruppe.

    Quelle: dienstplan.py:201-218. Eigene Dienste (Mitarbeiter-Zeile mit dem
    eigenen Mitglied) bleiben immer sichtbar, Admin ebenso.
    """
    filtered = []
    for e in elements:
        dienstbereich = _element_dienstbereich(e)
        if _can_see_dienstbereich(dienstbereich, gruppe=e.get("gruppe")):
            filtered.append(e)
            continue
        # Eigene Dienste immer sichtbar, auch ohne Bereichs-Zugriff
        if current_mitglied and _exists(
            "Element Mitarbeiter", {"parent": e["name"], "mitglied": current_mitglied}
        ):
            filtered.append(e)
    return filtered


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_dienstrollen():
    """Alle Dienstrollen als [{name, rollenname, farbe}].

    Quelle: dienstplan.py:221-237. Direkter Zugriff ueber
    /api/resource/Dienstrolle scheidet aus (nur fuer System Manager lesbar);
    diese App reicht Stammdaten ueber whitelisted Endpunkte heraus.
    """
    _throw_if_guest()
    return get_all(
        "Dienstrolle",
        fields=["name", "rollenname", "farbe"],
        order_by="rollenname asc",
    ) or []


@whitelist(allow_guest=False)
def get_dienstplan(start_date=None, end_date=None):
    """Gibt Dienstplan-Eintraege (Element + Mitarbeiter) fuer einen Zeitraum zurueck.

    Quelle: dienstplan.py:240-301.

    Leseberechtigung wird pro Eintrag gegen den Dienstbereich der Gruppe des
    Elements geprueft; zusaetzlich greift — vor allem bei Bestandsterminen
    ohne `gruppe` — die Kalender-Sichtbarkeit (`get_accessible_calendars`).
    """
    _throw_if_guest()

    if not start_date or not end_date:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        sunday = monday + datetime.timedelta(days=6)
        start_date = str(monday)
        end_date = str(sunday)

    if not _is_admin():
        current_mitglied = _current_user_mitglied_name()
    else:
        current_mitglied = None

    # frappe.get_all umgeht Permissions. Der Dienstbereich der Gruppe reicht als
    # Schranke NICHT: Element.gruppe ist neu und auf Bestandsterminen leer.
    # Massgeblich ist die Kalender-Sichtbarkeit — dieselbe Regel wie im Kalender
    # und in ablaufplan_api.get_termine_am_tag.
    element_filters = [
        ["element_start", ">=", _day_start(start_date)],
        ["element_start", "<=", _day_end(end_date)],
    ]
    if not _is_admin():
        erlaubte_kalender = [c["name"] for c in get_accessible_calendars()]
        if not erlaubte_kalender:
            return {"start_date": start_date, "end_date": end_date, "eintraege": []}
        element_filters.append(["element_calendar", "in", erlaubte_kalender])

    elements = get_all(
        "Element",
        filters=element_filters,
        fields=[
            "name",
            "element_name",
            "element_start",
            "element_end",
            "element_category",
            "element_calendar",
            "gruppe",
            "ressource",
            "dienstplan",
        ],
        order_by="element_start asc",
    ) or []

    elements = _filter_entwurf_elements(elements)
    elements = _filter_by_permission(elements, current_mitglied=current_mitglied)
    eintraege = _build_eintraege(elements)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "eintraege": eintraege,
    }


@whitelist(allow_guest=False)
def get_meine_dienste():
    """Gibt die zukuenftigen Dienste des aktuellen Users, aufgeteilt nach Terminart.

    Quelle: dienstplan.py:304-384.

    Returns: {vorbereitung: [...], einsatz: [...]} — je maximal 10, aufsteigend
    sortiert. Jeder Termin enthaelt zusätzlich den Ablaufplan (falls vorhanden)
    samt Markierung, welche Positionen der Nutzer selbst verantwortet.

    SICHTBARKEIT: nur die Dienste des eigenen Mitglieds. Ein Benutzer sieht
    dort niemals die Dienste eines anderen (per Test belegt).
    """
    _throw_if_guest()

    current_mitglied = _current_user_mitglied_name()
    if not current_mitglied:
        return {"vorbereitung": [], "einsatz": []}

    now = datetime.datetime.now()

    # Elemente, bei denen der User als Mitarbeiter eingetragen ist (zukuenftig)
    element_names = [
        r["parent"]
        for r in (
            get_all(
                "Element Mitarbeiter",
                filters={"mitglied": current_mitglied},
                fields=["parent"],
            ) or []
        )
    ]

    if not element_names:
        return {"vorbereitung": [], "einsatz": []}

    elements = get_all(
        "Element",
        filters=[
            ["name", "in", element_names],
            ["element_start", ">=", now],
        ],
        fields=[
            "name",
            "element_name",
            "element_start",
            "element_end",
            "element_category",
            "gruppe",
            "ressource",
            "dienstplan",
        ],
        order_by="element_start asc",
    ) or []

    elements = _filter_entwurf_elements(elements)
    eintraege = _build_eintraege(elements)

    vorbereitung = []
    einsatz = []
    for entry in eintraege:
        # Nur die eigene Mitarbeiter-Zeile des Users, nicht Zeilen anderer
        # Mitarbeiter desselben Elements.
        if entry.get("mitglied") != current_mitglied:
            continue

        # Ablaufplan mitliefern, Positionen des Users markieren
        ablaufplan = _get_ablaufplan_mit_markierung(entry.get("element"), current_mitglied)
        entry["ablaufplan"] = ablaufplan

        terminart = entry.get("terminart") or ""
        if terminart == "Vorbereitung":
            vorbereitung.append(entry)
        else:
            # Einsatz, Sonstiges und Termine ohne Kategorie landen bewusst hier.
            # Ein eingetragener Dienst darf in "Was steht an" NIE verschwinden,
            # nur weil seine Eventkategorie noch keine terminart gesetzt hat.
            einsatz.append(entry)

    # Nur zukuenftige, aufsteigend sortiert, max 10 je Liste
    vorbereitung = vorbereitung[:10]
    einsatz = einsatz[:10]

    return {
        "vorbereitung": vorbereitung,
        "einsatz": einsatz,
    }


def _get_ablaufplan_mit_markierung(element_name, current_mitglied):
    """Laedt den Ablaufplan eines Elements und markiert eigene Positionen.

    Quelle: dienstplan.py:387-424.

    Returns dict mit 'positionen' (je 'verantwortet': bool) oder None.
    """
    if not element_name:
        return None

    ablaufplan_name = get_value("Element", element_name, "ablaufplan")
    if not ablaufplan_name:
        return None

    try:
        ablaufplan = get_doc("Ablaufplan", ablaufplan_name)
    except Exception:  # noqa: BLE001 — Original schluckt jeden Ladefehler
        return None

    positionen = []
    for row in _child_rows(
        "Ablaufplan Position",
        ablaufplan.name,
        "positionen",
        [
            "reihenfolge",
            "bezeichnung",
            "dauer_minuten",
            "verantwortlicher",
            "notiz",
            "referenz_doctype",
            "referenz_name",
            "funktion",
            "gruppe",
            "detail",
        ],
    ):
        positionen.append({
            "reihenfolge": row.get("reihenfolge"),
            "bezeichnung": row.get("bezeichnung") or "",
            "dauer_minuten": row.get("dauer_minuten"),
            "verantwortlicher": row.get("verantwortlicher") or "",
            "verantwortet": bool(
                row.get("verantwortlicher") and row.get("verantwortlicher") == current_mitglied
            ),
            "notiz": row.get("notiz") or "",
            "referenz_doctype": row.get("referenz_doctype") or "",
            "referenz_name": row.get("referenz_name") or "",
            "funktion": row.get("funktion") or "",
            "gruppe": row.get("gruppe") or "",
            "detail": row.get("detail") or "",
        })

    return {
        "ablaufplan": ablaufplan_name,
        "titel": ablaufplan.get("titel") or "",
        "positionen": positionen,
    }
