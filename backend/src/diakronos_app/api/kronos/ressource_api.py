"""Portierung von `diakronos.kronos.api.ressource_api` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/ressource_api.py`

Portierte Endpunkte dieses Moduls:

    get_ressources          (Original: ressource_api.py:9-42)
    get_kronos_settings     (Original: ressource_api.py:45-52)
    check_resource_conflict (Original: ressource_api.py:55-158)
    get_conflict_events     (Original: ressource_api.py:183-202)  — A1c9

NICHT portiert (Karte P4c1 ist bewusst schmal; Restliste s. `inventar/PORTIERUNGSLISTE.md`):

    finalize_pending_events     — schreibt `Element.vorschlag` (Vorschlags-Flag)
    get_calendar_pending_info   — braucht `frappe.db.count` + Kalender-Singles
    confirm_element             — Moderations-Workflow, harte Konflikt-Sperre

WARUM `get_conflict_events` trotzdem da ist (A1c9)
------------------------------------------------
Die Fixture `dashboard_widget` zeigt mit `api_method` auf genau diese
Funktion (Widget `pending-registrations`, »Zu moderierende Termine«). Ohne
sie war das Widget im Dashboard **dauerhaft kaputt** (`lookup()` -> `None`,
dann `None()` -> `'NoneType' object is not callable`), sichtbar fuer jeden
Administrator.

Portiert ist deshalb die **Abfrage**, nicht der Workflow drumherum: es gibt
hier keine Schreibfunktion, kein `vorschlag`-Flag, kein `confirm_element`.
Was diese Karte anzeigt, ist eine Liste von Konflikten, die jemand im
Kalender ansehen kann — das ist genau das, was auch der Zaehler im Widget-Kopf
(`dashboard._count_ueberlappende_ressourcen_events`) zaehlt. Die Karte
verspricht nichts, das die portierte Funktion nicht liefert.

`confirm_element` bleibt bewusst unportiert: eine Schreibfunktion ohne
dazugehoerigen Moderations-Workflow (und ohne die zweite Haelfte des
Originals, den Kalender-Singles-Zustand) waere eine halbe Sache mit
Schreibzugriff.

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.get_meta("Ressource").fields   -> _typ_options() (s.u.)
    frappe.db.sql(<SELECT ... ORDER BY COALESCE>)  -> get_all + Python-Sortierung
    frappe.get_single("Kronos Einstellungen")     -> _kronos_settings()
    frappe.db.sql(<Element-Ueberlappung>)         -> get_all("Element", ...)
    frappe.get_all("Ressourcen Buchung")          -> get_all(...)
    frappe.whitelist(allow_guest=False)           -> whitelist(allow_guest=False)

Bewusste Abweichung zum Frappe-Standard: kein rohes SQL. Die `COALESCE`-Sortierung
und das `EXISTS` auf die Kind-Tabelle werden als gleichwertige Mengenausdruecke
in Python nachgebildet (siehe `_typ_options` und `_conflicting_events`).
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.ressource_api"

import json as _json
from datetime import datetime as _datetime
from typing import Any

from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _coerce,
    _coerce_filters,
    get_all,
    get_doc,
    get_value,
)
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.exceptions import throw
from diakronos_app.frappe_compat.session import session

__all__ = [
    "check_resource_conflict",
    "get_conflict_events",
    "get_kronos_settings",
    "get_ressources",
]


# ── DocType-Optionen (Ersatz fuer `frappe.get_meta`) ────────────────────────
#
# Das Original liest die Select-Optionen des Feldes `typ` aus den DocType-
# Metadaten (`frappe.get_meta("Ressource").fields`). Die Compat-Schicht hat
# kein Meta-Objekt: `tabDocField` ist nicht Teil des Live-Schemas
# (Portierungsbericht), und die generierten Modelle fuehren Options nicht.
#
# Die Optionsliste steht daher als Konstante hier — uebernommen aus dem
# DocType-JSON des Altcodes, das genau die Quelle ist, aus der Frappe seine
# `meta.fields[...].options` baut:
#
#     referenz/diakronos-frappe/diakronos/kronos/doctype/ressource/ressource.json
#     -> {"fieldname": "typ", "fieldtype": "Select",
#         "options": "Raum\nFahrzeug\nGegenstand"}
#
# `_typ_options()` parst denselben String wie das Original (Split auf "\n",
# Trim, leere Eintraege raus) — dadurch bleibt die Formatregel identisch.
_TYPE_OPTIONS_RAW = "Raum\nFahrzeug\nGegenstand"


def _typ_options() -> list[str]:
    """`[t.strip() for t in options.split("\\n") if t.strip()]` (Original P:15)."""
    return [t.strip() for t in _TYPE_OPTIONS_RAW.split("\n") if t.strip()]


# `_coerce_filters` kommt zentral aus `frappe_compat/api_helpers` (P8): die
# frueh hier liegende Kopie war identisch mit der Fassung in `_shared.py`
# (jetzt `api_helpers.py`) und mit der in `kalender.py`. Eine Sicherung, die
# man dreimal schreibt, wird zweimal vergessen — siehe `frappe_compat/query.py`,
# wo die Koerzierung zusaetzlich im gemeinsamen Filter-Engpass sitzt.


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_ressources():
    """Alle Ressourcen fuer Dropdown und Resource-Timeline.

    Quelle: ressource_api.py:9-42.

        SELECT name, ressource_name, typ, kapazitaet, beschreibung, bild
        FROM `tabRessource`
        ORDER BY COALESCE(typ, '') ASC, COALESCE(ressource_name, name) ASC

    Die zweistufige `COALESCE`-Sortierung bildet `get_all(order_by=...)` nicht
    ab (nur Einzelspalten) — sie wird daher in Python nachgezogen, mit exakt
    derselben Null-Fallback-Semantik.
    """
    rows = get_all(
        "Ressource",
        fields=["name", "ressource_name", "typ", "kapazitaet", "beschreibung", "bild"],
    ) or []

    rows = sorted(
        rows,
        key=lambda r: (
            r.get("typ") or "",
            r.get("ressource_name") or r.get("name"),
        ),
    )

    return {
        "types": _typ_options(),
        "resources": [
            {
                "id": r["name"],
                "title": r.get("ressource_name") or r["name"],
                "typ": r.get("typ") or "Sonstiges",
                "kapazitaet": r.get("kapazitaet"),
                "beschreibung": r.get("beschreibung") or "",
                "bild": r.get("bild"),
            }
            for r in rows
        ],
    }


def _kronos_settings() -> dict[str, Any] | None:
    """`frappe.get_single("Kronos Einstellungen")` -> Einstellungszeile oder None.

    Die Compat-Schicht hat keinen Single-Zugriff (`frappe.get_single` fehlt,
    wie bei `Diakronos Einstellungen`, s. `orgchart_api`). Der Single ist als
    Tabelle `kronos_einstellungen` modelliert; gelesen wird die Zeile mit dem
    Namen `"Kronos Einstellungen"`. Gibt es keine, faellt der Aufrufer auf die
    Original-Defaults zurueck (`or 0` / `or ""`).
    """
    row = get_value(
        "Kronos Einstellungen",
        filters={"name": "Kronos Einstellungen"},
        fieldname=["ressource_pflichtfeld", "standard_ressource"],
        as_dict=True,
    )
    if row:
        return row
    # Fallback: erste vorhandene Zeile (Single-Tabelle kann anders benannt sein).
    rows = get_all(
        "Kronos Einstellungen",
        fields=["ressource_pflichtfeld", "standard_ressource"],
        limit_page_length=1,
    ) or []
    return rows[0] if rows else None


@whitelist(allow_guest=False)
def get_kronos_settings():
    """Kronos-Einstellungen fuer die Ressourcen-Pflichtfeld-Konfiguration.

    Quelle: ressource_api.py:45-52.
    """
    settings = _kronos_settings()
    if settings is None:
        return {"ressource_pflichtfeld": 0, "standard_ressource": ""}
    return {
        "ressource_pflichtfeld": settings.get("ressource_pflichtfeld") or 0,
        "standard_ressource": settings.get("standard_ressource") or "",
    }


def _buchung_fuer_dialog(buchung: dict[str, Any]) -> dict[str, Any]:
    """Eine `Ressourcen Buchung`-Zeile fuer den Konfliktdialog aufbereiten.

    OP-EVENT-11: Der Dialog zeigt Ressourcenbuchungen bislang nur mit dem
    Gegenstand („Die gewaehlte Ressource ist bereits belegt: Beamer“) — wer
    bucht wann und wofuer, blieb unsichtbar, obwohl es in der Antwort stand.
    Hier kommen Zweck, lesbarer Zeitraum und Bucher dazu. Der Zeitraum ist
    derselbe Text wie in `ressourcen._zeitraum` („25.12.2026 16:00 - 18:00“),
    damit beide Oberflaechen gleich sprechen.

    P1-4b (K1): Der Bucher-Name ist eine Ressourcen-Sicht, keine Kalenderangabe.
    Jeder Termin-Schreiber bekam ihn bisher ueber den Konfliktdialog zu sehen.
    Nur Ressourcen-Moderatoren/Admins bekommen ihn; alle anderen sehen „Belegt“.
    """
    von = _als_datetime(buchung.get("datum_von"))
    bis = _als_datetime(buchung.get("datum_bis"))

    from diakronos_app.api.ressourcen import _darf_ressourcen_buchen

    nutzer = buchung.get("gebucht_von_name") or ""
    if not _darf_ressourcen_buchen():
        nutzer = "Belegt"

    return {
        **buchung,
        "titel": buchung.get("zweck") or "",
        "zeitraum": (
            f"{von.strftime('%d.%m.%Y %H:%M')} - {bis.strftime('%H:%M')}"
            if von and bis else ""
        ),
        "nutzer": nutzer,
    }


def _als_datetime(wert):
    """Datumswert aus der DB oder dem Request in `datetime` wandeln (None bleibt None)."""
    if wert is None or wert == "":
        return None
    if isinstance(wert, _datetime):
        return wert
    try:
        return _datetime.fromisoformat(str(wert).replace("Z", "+00:00").replace("T", " "))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return _datetime.strptime(str(wert), fmt)
            except ValueError:
                continue
    return None


@whitelist(allow_guest=False)
def check_resource_conflict(
    ressource,
    element_start,
    element_end,
    exclude_id=None,
    zusaetzliche_ressourcen=None,
):
    """Prueft ob eine Ressource im Zeitraum bereits belegt ist.

    Quelle: ressource_api.py:55-158 (Verhalten 1:1).

    `zusaetzliche_ressourcen`: Liste von dicts
    `[{ressource: ID, freitext_ressource: str, ...}]` oder JSON-String.
    Freitext-Ressourcen werden ignoriert (nur Katalog-Ressourcen geprueft).

    Rueckgabe: `{has_conflict, conflict, events, conflicts}` — `conflict` und
    `events` bleiben als rueckwaertskompatibles Paar fuer den Haupt-Ort erhalten.
    """
    empty = {"has_conflict": False, "conflict": False, "events": [], "conflicts": []}

    if not ressource and not zusaetzliche_ressourcen:
        return dict(empty)

    if not element_start or not element_end:
        return dict(empty)

    # Parse zusaetzliche_ressourcen if string
    additional_ids: list[str] = []
    if zusaetzliche_ressourcen:
        if isinstance(zusaetzliche_ressourcen, str):
            try:
                zusaetzliche_ressourcen = _json.loads(zusaetzliche_ressourcen)
            except Exception:  # noqa: BLE001 — Original faellt auf [] zurueck
                zusaetzliche_ressourcen = []
        if isinstance(zusaetzliche_ressourcen, list):
            for row in zusaetzliche_ressourcen:
                if isinstance(row, dict):
                    rid = (row.get("ressource") or "").strip()
                    if rid:
                        additional_ids.append(rid)

    # Collect all resource IDs to check: primary Ort + catalog resources from additional
    all_resources: list[str] = []
    if ressource:
        all_resources.append(ressource)
    for rid in additional_ids:
        if rid not in all_resources:
            all_resources.append(rid)

    if not all_resources:
        return dict(empty)

    conflicts: list[dict[str, Any]] = []
    primary_events: list[Any] = []

    for rid in all_resources:
        events = _conflicting_events(rid, element_start, element_end, exclude_id)

        # ── Harte Konflikte: Bestaetigte Ressourcen Buchungen ──────────────
        buchung_filters: dict[str, Any] = {
            "ressource": rid,
            "status": "Bestätigt",
            "datum_von": ["<", element_end],
            "datum_bis": [">", element_start],
        }
        if exclude_id:
            buchung_filters["name"] = ["!=", exclude_id]

        buchungen = get_all(
            "Ressourcen Buchung",
            filters=_coerce_filters("Ressourcen Buchung", buchung_filters),
            fields=["name", "zweck", "datum_von", "datum_bis", "gebucht_von_name"],
        ) or []

        # OP-EVENT-11: Der Konfliktdialog nennt bei Ressourcenbuchungen bisher
        # nur den Gegenstand. Zweck, Zeitraum und Bucher mitliefern, damit er
        # „wer bucht wann wofuer“ anzeigen kann (vorher nur `zweck`).
        buchungen = [_buchung_fuer_dialog(b) for b in buchungen]

        if events:
            conflicts.append({"ressource": rid, "events": events})
            if rid == ressource:
                primary_events = events

        if buchungen:
            conflicts.append({"ressource": rid, "events": [], "buchungen": buchungen})

    has_conflict = len(conflicts) > 0

    return {
        "has_conflict": has_conflict,
        "conflict": has_conflict,  # backward compat
        "events": primary_events,  # backward compat: events for primary ressource
        "conflicts": conflicts,    # new: all conflicts per resource
    }


def _has_read_access(calendar: str | None) -> bool:
    """Leserecht auf einen Kalender — Delegation an permissions.hat_leserecht."""
    from diakronos_app.api.kronos.permissions import hat_leserecht

    return hat_leserecht(calendar)


def _conflicting_events(
    rid: str,
    element_start: Any,
    element_end: Any,
    exclude_id: Any = None,
) -> list[dict[str, Any]]:
    """Ueberlappende `Element`-Zeilen fuer eine Ressource (Original: ein SQL).

    Quelle: ressource_api.py:104-119.

        SELECT DISTINCT ke.name, ke.element_name, ke.element_start,
               ke.element_end, ke.element_calendar
        FROM `tabElement` ke
        WHERE (ke.ressource = %s
               OR EXISTS (SELECT 1 FROM `tabElement Ressource` er
                          WHERE er.parent = ke.name AND er.ressource = %s))
          AND ke.element_start < %s
          AND ke.element_end   > %s
          AND ke.docstatus != 2
          [AND ke.name != %s]

    Das `EXISTS` auf die Kind-Tabelle wird in Python als Mengenausdruck
    nachgebildet: erst die Eltern-IDs der Kind-Tabelle holen, dann `Element`
    einmal mit `ressource = rid` und einmal mit `name IN <parents>` abfragen
    und per Primaerschluessel deduplizieren (= `DISTINCT`).
    """
    base_filters: dict[str, Any] = {
        "element_start": ["<", element_end],
        "element_end": [">", element_start],
        "docstatus": ["!=", 2],
    }
    if exclude_id:
        base_filters["name"] = ["!=", exclude_id]

    fields = ["name", "element_name", "element_start", "element_end", "element_calendar"]

    direct = get_all(
        "Element",
        filters=_coerce_filters("Element", {**base_filters, "ressource": rid}),
        fields=fields,
    ) or []

    child_rows = get_all(
        "Element Ressource",
        filters={"ressource": rid},
        fields=["parent"],
    ) or []
    parent_ids = sorted({c["parent"] for c in child_rows if c.get("parent")})
    # OP-EVENT-4: `exclude_id` darf nicht ueber den `name`-Schluessel verloren
    # gehen. Der Zusammenbau `{**base_filters, "name": ["in", parent_ids]}`
    # ueberschrieb das zuvor gesetzte `name != exclude_id` vollstaendig — die
    # Pruefung meldete dann den Termin als Konflikt mit SICH SELBST, und wer
    # „Trotzdem speichern“ waehlte, verlor dessen Belegungsschutz. Der
    # Ausschluss wird deshalb nach dem Laden in Python gefiltert (gleiche
    # Mengenaussage wie `AND ke.name != %s`).
    via_child = []
    if parent_ids:
        via_child = get_all(
            "Element",
            filters=_coerce_filters("Element", {**base_filters, "name": ["in", parent_ids]}),
            fields=fields,
        ) or []
        if exclude_id:
            via_child = [row for row in via_child if row.get("name") != exclude_id]  # type: ignore[union-attr]

    seen: set[Any] = set()
    merged: list[dict[str, Any]] = []
    # OP-EVENT-R1: Titel/Kalender fremder (nicht lesbarer) Kalender nicht
    # verraten. Die Belegung bleibt erkennbar ("Belegt"), damit der
    # Konfliktdialog weiterhin funktioniert.
    for row in (*direct, *via_child):
        key = row.get("name")
        if key in seen:
            continue
        seen.add(key)
        if not _has_read_access(row.get("element_calendar")):
            row = {**row, "element_name": "Belegt", "element_calendar": ""}
        merged.append(row)
    return merged


# ── Konflikt-Liste (A1c9) ─────────────────────────────────────────────────


def _darf_konflikte_sehen() -> bool:
    """`frappe.has_permission("Element", "read")` fuer diesen Endpunkt.

    Das Original ruft Frappe mit DocType + `read` auf; die Compat-Schicht
    kennt kein DocType-Recht, sondern nur `check_permission(doctype, docname)`.
    Fuer `Element` gibt es dort keinen Zweig — `check_permission` laeuft in
    `unsupported_doctype` und damit auf `False`, auch fuer einen Admin, der
    es im Original waere. Das waere eine **Falsch-Zugriff-Verweigerung**:
    die Karte waere fuer niemanden sichtbar, auch nicht fuer den Admin, und
    der Fehlerfaelle waere eine leere Karte statt eines Hinweises.

    Der Weg, den dieses Modul fuer Kalenderrechte bereits hat, ist derselbe
    wie im Originalcode daneben (`confirm_element`, ressource_api.py:249-265):
    `Administrator` ODER globale Kalenderadministrator-Rolle. Genau das ist
    auch die Rolle, die die Widget-Zeile selbst verlangt
    (`dashboard_widget.required_role = "Kalenderadministrator"`) — der
    Endpunkt ist damit nicht *weiter* als das Widget, das ihn aufruft. Ein
    Kalendermoderator einer einzelnen Kalender (`_is_moderator_of`) darf
    Konflikte ebenfalls sehen: sie sind Konflikte *seiner* Kalender.

    Fail closed: `Guest` und jeder Unbekannte fallen auf `False`.
    """
    user = session.user
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True

    from diakronos_app.api.kronos.permissions import _is_kalenderadministrator

    if _is_kalenderadministrator(user):
        return True

    # Kalendermoderatoren: Moderation einer Kalender ist genau die Aufgabe,
    # zu der die Konfliktliste gehoert. Bewusst ueber die Modulgrenze hinweg
    # importiert (zirkulaere Abhaengigkeit vermeiden).
    try:
        from diakronos_app.api.kronos import permissions as kronos_permissions

        ist_moderator = getattr(kronos_permissions, "_is_moderator_of", None)
        if callable(ist_moderator) and _is_moderator_von_irgendeiner_kalender(user):
            return True
    except Exception:  # noqa: BLE001 — Moderator-Pruefung ist Zusatz, nie Kern
        pass
    return False


def _is_moderator_von_irgendeiner_kalender(user: str) -> bool:
    """Traegt `user` die Moderatorrolle in *irgendeiner* Kalender?

    Frappes `_is_moderator_of(user, cal_doc)` vergleicht die Kind-Zeilen
    `Kalender Moderator` einer Kalender. Das Original fuer `get_conflict_events`
    ruft diese Funktion gar nicht auf (es kennt nur das DocType-Recht) — das
    hier ist die Entsprechung dieser Rechtepruefung im Port, damit ein
    Kalendermoderator seine eigene Karte sieht statt einer leeren.

    Die Liste der moderierten Kalender wird einmal geholt und lokal geprueft
    (statt je Kalender `_is_moderator_of` zu rufen): die Karte zeigt
    *alle* Konflikte, nicht die einer Kalender, also genuegt die Frage
    "irgendeine".

    `_is_moderator_of` greift mit `calendar_doc.name` auf das Dokument zu —
    ein echtes Doc-Objekt, kein dict. Deshalb wird hier `get_doc`
    benutzt; ein blosses `{"name": ...}` wuerde als `AttributeError`
    scheitern und (ueber den `except` in `_darf_konflikte_sehen`) still zu
    `False` fuehren — ein Modrator saehe eine leere Karte und wuesste nicht
    warum.
    """
    from diakronos_app.api.kronos.permissions import _is_moderator_of

    zeilen = [
        z for z in (get_all(
            "Kalender Moderator",
            filters={"user": user},
            fields=["parent", "name"],
        ) or [])
        if isinstance(z, dict)
    ]
    for zeile in zeilen:
        kalender_name = zeile.get("parent")
        if not kalender_name:
            continue
        try:
            kalender = get_doc("Kalender", kalender_name)
        except Exception:  # noqa: BLE001 — Kalender weg: Moderatorrolle nicht belegbar
            continue
        try:
            if _is_moderator_of(user, kalender):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


@whitelist(allow_guest=False)
def get_conflict_events():
    """Gibt Konflikt-Events zurueck (nur fuer Moderatoren).

    Quelle: ressource_api.py:183-202 (Verhalten 1:1).

        SELECT a.name, a.element_name, a.element_start, a.element_end,
               a.ressource, a.element_calendar
        FROM `tabElement` a
        JOIN `tabElement` b
          ON a.ressource = b.ressource
         AND a.name != b.name
         AND a.element_start < b.element_end
         AND a.element_end > b.element_start
         AND a.docstatus != 2
         AND b.docstatus != 2
        WHERE a.ressource IS NOT NULL AND a.ressource != ''
        ORDER BY a.ressource, a.element_start

    Der Self-JOIN auf dieselbe Tabelle ist in `get_all` nicht ausdrueckbar
    (kein rohes SQL, s. Modulkopf). Beide Seiten sind aber Zeilen derselben
    Tabelle: **ein** Lesevorgang reicht, die Paarbildung und das `docstatus`
    auf beiden Seiten passieren in Python. Das ist dieselbe Technik wie in
    `dashboard._count_ueberlappende_ressourcen_events` — beide lesen
    `Element` und bilden dieselbe Menge; der Zaehler im Widget-Kopf und die
    Karte koennen deshalb nicht auseinanderlaufen.

    `a` (linke Seite) wird fuer jedes kollidierende `b` einmal geliefert —
    das Original-SQL ebenfalls, deshalb sind hier beide Partner auf
    `EL-1`/`EL-2` zu sehen. Das entspricht der Zahl im Badge und dem, was
    der Kalender anzeigt.
    """
    if not _darf_konflikte_sehen():
        throw("Keine Berechtigung", FrappePermissionError)

    rows = [
        r for r in (get_all(
            "Element",
            filters=[["docstatus", "!=", 2]],
            fields=["name", "element_name", "element_start", "element_end",
                    "ressource", "element_calendar", "status"],
        ) or [])
        if isinstance(r, dict)
    ]

    # P0-3 Befund 4: Die Konfliktliste zeigte Titel und Kalender ALLER
    # Termine, sobald jemand irgendeinen Kalender moderiert — auch aus
    # Kalendern, die er nicht lesen darf. Zeilen ohne Leserecht werden
    # anonymisiert ("Belegt"), genau wie in `_conflicting_events` und in
    # `get_conflict_partner` (OP-EVENT-R1). Die Belegung bleibt dadurch
    # sichtbar, das Konfliktbilden funktioniert weiter.
    rows = [
        r if _has_read_access(r.get("element_calendar"))
        else {**r, "element_name": "Belegt", "element_calendar": ""}
        for r in rows
    ]

    # `WHERE a.ressource IS NOT NULL AND a.ressource != ''` — ohne diese
    # Zeile waere jeder termin ohne Ort ein Konflikt mit jedem anderen.
    kandidaten = [
        r for r in rows
        if r.get("ressource") and r.get("element_start") and r.get("element_end")
    ]

    by_ressource: dict[Any, list[dict[str, Any]]] = {}
    for r in kandidaten:
        by_ressource.setdefault(r["ressource"], []).append(r)

    # Die Paarbildung entspricht `ORDER BY a.ressource, a.element_start`.
    kollidierend: list[dict[str, Any]] = []
    for ressource, eintraege in by_ressource.items():
        for a in eintraege:
            for b in eintraege:
                if a["name"] == b["name"]:
                    continue
                if a["element_start"] < b["element_end"] and a["element_end"] > b["element_start"]:
                    kollidierend.append(a)
                    break

    kollidierend.sort(key=lambda r: (r["ressource"], str(r["element_start"])))
    return kollidierend
