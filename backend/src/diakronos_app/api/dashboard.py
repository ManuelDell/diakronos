"""Portierung von `diakonos/api/dashboard.py` (P4h) — Widgets + Daten, 11 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/dashboard.py`

Die SPA ruft ausschliesslich die ORIGINAL-Pfade
`diakronos.diakonos.api.dashboard.<fn>` auf (hooks.py; u. a.
`Dashboard.vue` -> `get_events_for_month`, `get_widget_badge_counts`,
`get_widget_data`). Dafuer traegt dieses Modul die Konstante `FRAPPE_MODULE`.

Das Original ist DREI aneinandergehaengte Dateien (Zeilen 1-160, 161-300,
301-342) — hier bewusst EIN Modul, weil `FRAPPE_MODULE` genau EIN Modul
adressiert und Regel 12 ein Modul nicht aufteilt.

Schema-Realitaet (geprueft gegen `Spaltenabzug der Betriebs-DB`, NICHT
angenommen — das DocType-JSON ist nicht die Wahrheit):

  Dashboard Widget (Z. 22):  alle im Original benutzten Felder vorhanden:
      widget_id, label, description, widget_type, category, icon,
      required_role, required_permission, api_method, api_args,
      refresh_interval, grid_size, default_position, default_visible,
      enabled, is_system, empty_state_mode, empty_state_message

  Dashboard Widget User Config (Z. 23): alle Felder vorhanden:
      user, widget, position, visible, size, collapsed

  Element (Z. 12): element_name, element_category, element_calendar,
      element_start, element_end, ressource, docstatus, gruppe, dienstplan

  Kalender (Z. 14): calendar_color vorhanden.

Aggregat-Sichtbarkeit (ausdruecklich dokumentiert, weil die Karte danach
fragt): `get_widget_badge_counts` ist der einzige Zaehler-Endpunkt. Das
Original zaehlt NUR, wenn der Nutzer die passende Rolle traegt
(`Kalenderadministrator`/`System Manager` bzw.
`Mitgliederadministrator`/`System Manager`). Ein Nicht-Berechtigter bekommt
den Schluessel GAR NICHT (nicht etwa 0) — diese Schranke wird 1:1
uebernommen und per Test belegt. `get_widget_data` prueft je Widget
`radius_role`/`required_permission` ueber `_user_can_see_widget` und wirft
sonst `PermissionError` (403).

Abweichungen des Ports (Nachtbefunde OP-HANDY-R1 / OP-HANDY-11):

  * `get_upcoming_events` und `get_events_for_month` uebernehmen das
    `ignore_permissions=True` des Originals NICHT: gefiltert wird auf
    `get_accessible_calendars()` und `status = "Festgelegt"`.
  * `_user_can_see_widget` bildet die DocTypes ohne Compat-Rechtemapping
    ("Kronos Element", "Wiki Artikel") auf die tatsaechliche Leseregel ab
    (`_custom_permission`), sonst blieben Mitgliedern "Anstehende Termine",
    Mini-Kalender und Wiki-Eintraege ausgeblendet.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user            -> session.user
    frappe.get_roles(user)         -> permissions.get_roles(user)
    frappe.get_all(...)            -> query.get_all(...)   (Zeilen sind dicts)
    frappe.db.get_value(...)       -> query.get_value(...)
    frappe.db.exists(...)          -> _exists(...)  (count > 0)
    frappe.db.count(...)           -> db.count(...)
    frappe.has_permission(...)     -> permissions.check_permission(...)
    frappe.get_attr(...)           -> registry.lookup(...)
    frappe.get_doc({...})          -> _create(...)
    doc.save(ignore_permissions=..) -> _update_doc(...)
    frappe.db.delete(...)          -> _db_delete(...)  (SQLAlchemy-Delete)
    frappe.db.commit()             -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)         -> throw(msg, exc)
    frappe.db.sql(...)             -> get_all(...) + Python-Aggregation
    frappe.log_error(...)          -> log_error(...)  (stderr)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.dashboard"

import datetime
import json
from typing import Any

from diakronos_app.frappe_compat.api_helpers import (
    _coerce_filters,
    _create,
    _update_doc,
    get_all,
    get_value,
    log_error,
    throw,
)
from diakronos_app.frappe_compat import db as _db
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.registry import lookup, whitelist
from diakronos_app.frappe_compat.session import session

__all__ = [
    "get_available_widgets",
    "get_events_for_month",
    "get_meine_buchungen_widget",
    "get_navigation_zaehler",
    "get_pinned_beitraege",
    "get_recent_articles",
    "get_upcoming_events",
    "get_user_config",
    "get_widget_badge_counts",
    "get_widget_data",
    "reset_user_config",
    "set_user_config",
]


# ── Compat-Helfer (Frappe-Utilities ohne direkte Entsprechung) ──────────────


def _exists(doctype: str, filters) -> bool:
    """`frappe.db.exists(doctype, filters)` — String-Name -> `{"name": ...}`.

    Gleiche Semantik wie in `planung._exists` (P4d1): ein String wird als
    Name interpretiert, alles andere als Filtersatz.
    """
    if isinstance(filters, str):
        filters = {"name": filters}
    try:
        return bool(_db.exists(doctype, filters))
    except DoesNotExistError:
        return False


def _has_permission(doctype: str, permission_type: str, user: str) -> bool:
    """`frappe.has_permission(doctype, perm, user=user)`.

    Die Compat-Schicht hat keine Entsprechung; `check_permission` verlangt
    einen `docname`. Da im Original ausschliesslich der DocType-Name geprueft
    wird (kein einzelner Datensatz), wird eine leere Dokument-Referenz
    uebergeben — das Ergebnis ist `allowed` und deckt sich mit dem, was
    Frappe fuer ein reines DocType-Recht liefert.

    Fail closed: eine unbekannte DocType/Permission-Kombination -> `False`.
    """
    try:
        result = permissions.check_permission(doctype, "", permission_type)
    except Exception:  # noqa: BLE001 — Original schluckt hier ebenfalls
        return False
    return bool(result.get("allowed")) if isinstance(result, dict) else bool(result)


# ── Sichtbarkeit eines Widgets (1:1 aus dem Original) ───────────────────────


_PERMISSION_SONDERFAELLE = {
    # `fr._user_can_see_widget` ruft `frappe.has_permission(doctype, perm)`.
    # Fuer DocTypes ohne eigenen Rechtemapping in der Compat-Schicht
    # ("Kronos Element", "Wiki Artikel") liefert `check_permission` fail closed
    # -> False. Das blendete Mitgliedern "Anstehende Termine" und
    # Mini-Kalender aus (OP-HANDY-11). Die beiden DocTypes werden deshalb auf
    # die tatsaechliche Leseregel abgebildet:
    #   * Kronos Element: sichtbar, wenn der Nutzer mindestens einen Kalender
    #     lesen darf (derselbe Filter wie OP-HANDY-R1).
    #   * Wiki Artikel:   jeder angemeldete Nutzer darf lesen (wiki.py: _get_user).
    "Kronos Element": "kronos_element_read",
    "Wiki Artikel":   "wiki_artikel_read",
}


def _custom_permission(doctype: str, permission_type: str, user: str) -> bool | None:
    """Sonder-Leseregel fuer DocTypes ohne Compat-Rechtemapping.

    Rueckgabe `None` heisst: kein Sonderfall -> generische Pruefung.
    """
    if permission_type != "read":
        return None
    kind = _PERMISSION_SONDERFAELLE.get(doctype)
    if kind is None:
        return None
    if user == "Guest" or not user:
        return False
    if kind == "kronos_element_read":
        # Mindestens ein lesbarer Kalender -> Widget sinnvoll.
        return bool(_sichtbare_kalender())
    if kind == "wiki_artikel_read":
        return True
    return None


def _user_can_see_widget(user: str, widget) -> bool:
    """Prueft ob der Nutzer das Widget sehen darf.

    Quelle: dashboard.py:8-27. `widget` ist beim `get_all` ein dict, beim
    `db.get_value(..., as_dict=True)` ebenfalls — der Original-Dual-Pfad
    (dict vs. Attribut) faellt damit zusammen.
    """
    required_role = widget.get("required_role") if isinstance(widget, dict) else widget.required_role
    required_permission = (
        widget.get("required_permission") if isinstance(widget, dict)
        else widget.required_permission
    )

    if required_role:
        # R-P1-8/W3: ueber `get_roles` pruefen (kennt Ausschluss/Sperre), nicht
        # ueber eine eigene `Has Role`-Abfrage.
        from diakronos_app.frappe_compat.permissions import get_roles

        if required_role not in set(get_roles(user)):
            return False

    if required_permission:
        try:
            parts = [p.strip() for p in required_permission.split(",")]
            doctype = parts[0]
            perm = parts[1] if len(parts) > 1 else "read"
            sonderfall = _custom_permission(doctype, perm, user)
            if sonderfall is not None:
                if not sonderfall:
                    return False
            elif not _has_permission(doctype, perm, user):
                return False
        except Exception:  # noqa: BLE001 — Original schluckt Parse-Fehler
            pass

    return True


# ── Widget-Konfiguration ────────────────────────────────────────────────────

# Feldliste des Originals (dashboard.py:37-42) — als Konstante, damit
# `get_available_widgets` und `get_user_config` dieselbe Basis nutzen.
_WIDGET_FIELDS = [
    "widget_id", "label", "category", "icon", "widget_type",
    "grid_size", "empty_state_mode", "empty_state_message",
    "refresh_interval", "default_position", "default_visible",
    "required_role", "required_permission", "api_method",
]


@whitelist(allow_guest=False)
def get_available_widgets():
    """Gibt alle fuer den aktuellen Nutzer sichtbaren Widgets zurueck (nur Metadaten).

    Quelle: dashboard.py:30-45.
    """
    user = session.user
    widgets = get_all(
        "Dashboard Widget",
        filters=_coerce_filters("Dashboard Widget", {"enabled": 1}),
        fields=list(_WIDGET_FIELDS),
        order_by="default_position asc",
    ) or []
    return [w for w in widgets if _user_can_see_widget(user, w)]


@whitelist(allow_guest=False)
def get_user_config():
    """Gibt das personalisierte Dashboard-Layout des aktuellen Nutzers zurueck.

    Quelle: dashboard.py:48-81.
    """
    user = session.user
    available = get_available_widgets()

    configs = get_all(
        "Dashboard Widget User Config",
        filters={"user": user},
        fields=["widget", "position", "visible", "size", "collapsed"],
    ) or []
    config_map = {c["widget"]: c for c in configs}

    result = []
    for w in available:
        cfg = config_map.get(w["widget_id"])
        result.append({
            "widget_id":           w["widget_id"],
            "label":               w["label"],
            "category":            w["category"],
            "icon":                w.get("icon") or "",
            "widget_type":         w.get("widget_type") or "info_card",
            "api_method":          w.get("api_method") or "",
            "grid_size":           (cfg.get("size") if cfg and cfg.get("size") != "default" else None) or w["grid_size"],
            "position":            cfg.get("position") if cfg else w["default_position"],
            "visible":             bool(cfg.get("visible") if cfg else w["default_visible"]),
            "collapsed":           bool(cfg.get("collapsed") if cfg else False),
            "empty_state_mode":    w["empty_state_mode"],
            "empty_state_message": w["empty_state_message"] or "Keine Daten.",
            "refresh_interval":    w["refresh_interval"] or 0,
        })

    result.sort(key=lambda x: x["position"])
    return result


@whitelist(allow_guest=False)
def set_user_config(layout_json):
    """Speichert das personalisierte Layout fuer den aktuellen Nutzer.

    Quelle: dashboard.py:84-119. Nicht sichtbare Widget-IDs werden still
    uebersprungen (Schranke gegen Layout-Manipulation fremder Widgets).
    """
    if isinstance(layout_json, str):
        layout = json.loads(layout_json)
    else:
        layout = layout_json

    user = session.user
    available_ids = {w["widget_id"] for w in get_available_widgets()}

    for item in layout:
        widget_id = item.get("widget_id")
        if widget_id not in available_ids:
            continue

        existing = get_value(
            "Dashboard Widget User Config",
            {"user": user, "widget": widget_id},
            "name",
        )
        if not existing:
            _create("Dashboard Widget User Config", {
                "user": user,
                "widget": widget_id,
                "position": int(item.get("position", 0)),
                "visible": 1 if item.get("visible", True) else 0,
                "size": item.get("size", "default") or "default",
                "collapsed": 1 if item.get("collapsed", False) else 0,
            })
            continue

        _update_doc("Dashboard Widget User Config", existing, {
            "position": int(item.get("position", 0)),
            "visible": 1 if item.get("visible", True) else 0,
            "size": item.get("size", "default") or "default",
            "collapsed": 1 if item.get("collapsed", False) else 0,
        })

    return {"status": "ok"}


@whitelist(allow_guest=False)
def reset_user_config():
    """Setzt das Layout auf die Standardwerte zurueck.

    Quelle: dashboard.py:122-128 (`frappe.db.delete` auf alle Zeilen des
    Nutzers).
    """
    user = session.user
    _db_delete("Dashboard Widget User Config", {"user": user})
    return {"status": "ok"}


def _db_delete(doctype: str, filters: dict[str, Any]) -> int:
    """`frappe.db.delete(doctype, filters)` — Massenloesche ueber SQLAlchemy.

    Die Compat-Schicht hat kein `db.delete`; das Original nutzt es genau
    einmal (`reset_user_config`) und dort ohne Permission-Ruecksicht.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.query import _compile_filters, _require_doctype

    model = _require_doctype(doctype)
    sess = SessionLocal()
    try:
        conditions = _compile_filters(doctype, model, filters)
        result = sess.execute(model.__table__.delete().where(*conditions))
        sess.commit()
        return int(result.rowcount or 0)
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


# ── Widget-Daten (dynamischer Dispatch) ─────────────────────────────────────


@whitelist(allow_guest=False)
def get_widget_data(widget_id, extra_args=None):
    """Laedt die Daten fuer ein einzelnes Widget (dynamischer API-Aufruf).

    Quelle: dashboard.py:131-160.

    Permission (Pflicht, unveraendert): fehlt das Widget -> `DoesNotExistError`
    (404); sieht der Nutzer es nicht -> `PermissionError` (403).
    """
    user = session.user
    widget = get_value(
        "Dashboard Widget",
        _coerce_filters("Dashboard Widget", {"widget_id": widget_id, "enabled": 1}),
        ["api_method", "required_role", "required_permission", "api_args"],
        as_dict=True,
    )
    if not widget:
        throw("Widget nicht gefunden.", DoesNotExistError)
    if not _user_can_see_widget(user, widget):
        throw("Zugriff verweigert.", FrappePermissionError)
    if not widget.get("api_method"):
        return {"widget_id": widget_id, "data": None}

    # A1c9 — `lookup` KANN `None` liefern, und dann ist `method(**args)` ein
    # `TypeError` ueber `None`. Genau daraus wurde die Fehlerkarte
    # »Fehler beim Laden«: ein KONFIGURATIONSFEhler (die Tabelle zeigt auf
    # eine Funktion, die es nicht gibt) landete als roter Text auf einer
    # Karte, die der Benutzer nicht reparieren kann — und in keinem Log,
    # das jemand ansieht.
    #
    # Die Unterscheidung ist die ganze Aufgabe:
    #   * nicht auffindbar  -> loggen, `data: None`, KEIN `error`-Feld.
    #                           Der Benutzer sieht den dokumentierten
    #                           Leerzustand; der Betreiber sieht den Log.
    #   * Fehler IN der Funktion -> wie bisher `error`-Feld (unveraendert).
    method = lookup(widget["api_method"])
    if method is None:
        log_error(
            "api_method nicht auffindbar: %r (Widget %r)" % (
                widget["api_method"], widget_id,
            ),
            f"get_widget_data:{widget_id}",
        )
        return {"widget_id": widget_id, "data": None}

    try:
        args = json.loads(widget.get("api_args") or "{}")
        if extra_args:
            if isinstance(extra_args, str):
                extra_args = json.loads(extra_args)
            args.update(extra_args)
        data = method(**args)
    except Exception as e:  # noqa: BLE001 — Original loggt und antwortet mit error
        log_error(str(e), f"get_widget_data:{widget_id}")
        return {"widget_id": widget_id, "data": None, "error": str(e)}

    return {"widget_id": widget_id, "data": data}


# ── Daten-Endpunkte (Phase 2) ───────────────────────────────────────────────


def _sichtbare_kalender() -> list[str]:
    """Kalendernamen, auf die der aktuelle Nutzer Leserecht hat (OP-HANDY-R1).

    Dieselbe Quelle wie die SPA (`get_accessible_calendars`). Die
    Dashboard-Terminlisten duerfen Termine gesperrter Kalender nicht liefern.
    Ein leeres Ergebnis bedeutet: keine Kalender -> keine Termine.
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    return [c["name"] for c in get_accessible_calendars()]


@whitelist(allow_guest=False)
def get_upcoming_events(limit=5):
    """Naechste Termine ab heute fuer das Dashboard-Widget.

    Quelle: dashboard.py:169-201. Das Original liest mit
    `ignore_permissions=True` — die Liste ist fuer JEDEN angemeldeten Nutzer
    gleich (kein Kalender-/Bereichsfilter).

    OP-HANDY-R1: Der Port übernimmt das bewusst NICHT. Es werden nur Termine
    aus Kalendern mit Leserecht (`get_accessible_calendars`) und im Status
    "Festgelegt" geliefert — sonst leakt das Widget fremde Termine.
    """
    kalender = _sichtbare_kalender()
    if not kalender:
        return []
    now = datetime.datetime.now()
    events = get_all(
        "Element",
        filters=[
            ["element_start", ">=", now],
            ["docstatus", "!=", 2],
            ["status", "=", "Festgelegt"],
            ["element_calendar", "in", kalender],
        ],
        fields=["name", "element_name", "element_start", "element_end", "element_calendar"],
        order_by="element_start asc",
        limit_page_length=int(limit),
    ) or []
    cal_colors: dict[str, str] = {}
    for e in events:
        cal = e.get("element_calendar")
        if cal and cal not in cal_colors:
            cal_colors[cal] = get_value("Kalender", cal, "calendar_color") or ""
    return [
        {
            "id":       e["name"],
            "title":    e.get("element_name") or "(Kein Titel)",
            "start":    str(e["element_start"]) if e.get("element_start") else "",
            "end":      str(e["element_end"]) if e.get("element_end") else "",
            "calendar": e.get("element_calendar") or "",
            "color":    cal_colors.get(e.get("element_calendar"), ""),
        }
        for e in events
    ]


@whitelist(allow_guest=False)
def get_events_for_month(year=None, month=None):
    """Gibt Termine-Tage fuer den Mini-Kalender zurueck.

    Quelle: dashboard.py:204-225.

    Original-SQL:
        SELECT DATE(element_start) AS day FROM `tabElement`
        WHERE element_start >= %s AND element_start < %s AND docstatus != 2
        GROUP BY DATE(element_start)

    Umgestellt auf `get_all` + Python-Aggregation (kein rohes SQL): die
    Tage sind die eindeutigen `DATE(element_start)`-Werte. Sortierung
    aufsteigend — das entspricht der ungeordneten GROUP-BY-Ausgabe der
    Original-Datenbank ohne ORDER BY, ist aber deterministisch.

    OP-HANDY-R1: nur Termine aus Kalendern mit Leserecht und Status
    "Festgelegt" — sonst verraet der Mini-Kalender fremde Termintage.
    """
    kalender = _sichtbare_kalender()
    if not kalender:
        return {"year": int(year or datetime.date.today().year),
                "month": int(month or datetime.date.today().month),
                "event_days": []}
    today = datetime.date.today()
    year = int(year or today.year)
    month = int(month or today.month)
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year + 1, 1, 1) if month == 12 else datetime.datetime(year, month + 1, 1)

    rows = get_all(
        "Element",
        filters=[
            ["element_start", ">=", start],
            ["element_start", "<", end],
            ["docstatus", "!=", 2],
            ["status", "=", "Festgelegt"],
            ["element_calendar", "in", kalender],
        ],
        fields=["element_start"],
    ) or []
    days = sorted({str(r["element_start"])[:10] for r in rows if r.get("element_start")})
    return {"year": year, "month": month, "event_days": days}


@whitelist(allow_guest=False)
def get_pinned_beitraege(limit=3):
    """Neueste veroeffentlichte Beitraege fuer das Dashboard.

    Quelle: dashboard.py:229-249 (`ignore_permissions=True`, nur
    `veroeffentlicht = 1`).
    """
    rows = get_all(
        "Beitrag",
        filters=_coerce_filters("Beitrag", {"veroeffentlicht": 1}),
        fields=["name", "titel", "auszug", "datum", "autor", "bild"],
        order_by="datum desc",
        limit_page_length=int(limit),
    ) or []
    return [
        {
            "id":      r["name"],
            "title":   r.get("titel") or "",
            "excerpt": r.get("auszug") or "",
            "date":    str(r["datum"]) if r.get("datum") else "",
            "author":  r.get("autor") or "",
            "image":   r.get("bild") or "",
        }
        for r in rows
    ]


@whitelist(allow_guest=False)
def get_recent_articles(limit=3):
    """Zuletzt geaenderte Wiki-Artikel fuer das Dashboard.

    Quelle: dashboard.py:253-270 (`ignore_permissions=True`, Sortierung
    nach `modified desc`).
    """
    rows = get_all(
        "Wiki Artikel",
        fields=["name", "titel", "modified", "kategorie"],
        order_by="modified desc",
        limit_page_length=int(limit),
    ) or []
    return [
        {
            "id":       r["name"],
            "title":    r.get("titel") or r["name"],
            "modified": str(r["modified"]) if r.get("modified") else "",
            "category": r.get("kategorie") or "",
        }
        for r in rows
    ]


@whitelist(allow_guest=False)
def get_meine_buchungen_widget(upcoming_only=1, limit=3):
    """Kommende Ressourcen-Buchungen des aktuellen Nutzers.

    Quelle: dashboard.py:274-300.

    Nutzt `get_effective_user()` (Impersonation), NICHT `session.user` — das
    ist die Sichtbarkeitsschranke dieses Endpunkts: gefiltert wird hart auf
    `gebucht_von = <effektiver Nutzer>`. Fremde Buchungen koennen so nicht in
    der Liste erscheinen (per Test belegt).
    """
    user = _get_effective_user()
    filters: dict[str, Any] = {"gebucht_von": user, "status": "Aktiv"}
    if int(upcoming_only):
        filters["datum_von"] = [">=", datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)]
    rows = get_all(
        "Ressourcen Buchung",
        filters=_coerce_filters("Ressourcen Buchung", filters),
        fields=["name", "ressource", "datum_von", "datum_bis", "zweck", "status"],
        order_by="datum_von asc",
        limit_page_length=int(limit),
    ) or []
    result = []
    for r in rows:
        ressource_name = get_value("Ressource", r["ressource"], "ressource_name") or r["ressource"]
        result.append({
            "id":             r["name"],
            "ressource":      r["ressource"],
            "ressource_name": ressource_name,
            "start":          str(r["datum_von"]) if r.get("datum_von") else "",
            "end":            str(r["datum_bis"]) if r.get("datum_bis") else "",
            "zweck":          r.get("zweck") or "",
            "status":         r.get("status") or "",
        })
    return result


@whitelist(allow_guest=False)
def get_moderation_vorschlaege(limit=20):
    """BF1-G/W6: Zur Moderation anstehende TERMINE (Vorschlaege).

    Die Kachel „Zu moderierende Termine“ hing bisher an
    `ressource_api.get_conflict_events` — das sind Ressourcen-Doppelbelegungen
    aus allen Terminen (jeder Status, auch vergangene), sortiert nach
    Ressource. Genau das ist NICHT die Moderationswarteschlange: ein neu
    angelegter Vorschlag erschien dort nie. Diese Funktion liefert, was der
    Titel verspricht: die offenen Vorschlaege der Kalender, die der Aufrufer
    moderiert — nach Startzeit sortiert, Vergangenes ausgeblendet, ohne
    interne IDs (Titel/Zeit/Ort).

    Berechtigung: nur Kalender-Moderatoren (dieselbe Schranke wie
    `kanban_api._mod_calendars`, also `get_accessible_calendars` mit
    `is_moderator`). Ohne Moderationskalender -> leere Liste (kein Fehler),
    dieselbe Antwort wie im Kanban-Brett.
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    allowed = get_accessible_calendars() or []
    mod_cals = [c["name"] for c in allowed if isinstance(c, dict) and c.get("is_moderator")]
    if not mod_cals:
        return []

    grenze = max(int(limit or 0), 0)
    jetzt = datetime.datetime.now()
    rows = get_all(
        "Element",
        filters={
            "element_calendar": ["in", mod_cals],
            "status": "Vorschlag",
            "element_start": [">=", jetzt],
        },
        fields=["name", "element_name", "element_start", "element_end",
                "all_day", "ressource", "element_calendar", "status"],
        order_by="element_start asc",
        limit_page_length=grenze or None,
    ) or []

    cal_info: dict[str, dict[str, str]] = {}
    out: list[dict[str, Any]] = []
    for e in rows:
        cal = e.get("element_calendar")
        if cal not in cal_info:
            row = get_value("Kalender", cal, ["calendar_name", "calendar_color"],
                            as_dict=True) or {}
            cal_info[cal] = {
                "title": row.get("calendar_name") or cal or "",
                "color": row.get("calendar_color") or "#3b82f6",
            }
        out.append({
            "id":             e.get("name"),
            "element_name":   e.get("element_name") or "Termin",
            "element_start":  str(e.get("element_start")) if e.get("element_start") else "",
            "element_end":    str(e.get("element_end")) if e.get("element_end") else None,
            "all_day":        bool(e.get("all_day")),
            "ressource":      e.get("ressource") or "",
            "element_calendar": cal or "",
            "calendar_title": cal_info[cal]["title"],
            "calendar_color": cal_info[cal]["color"],
            "status":         e.get("status") or "",
        })
    return out


def _get_effective_user() -> str:
    """`impersonation.get_effective_user()` — Impersonation-Sonderfall.

    Das Original importiert die Funktion aus `diakronos.diakonos.api.
    impersonation`. Ist der aktuelle Nutzer ein Administrator mit gesetzter
    Impersonations-Flag, liefert sie den impersonierten User, sonst
    `session.user`. Die Impersonations-API selbst ist nicht Teil dieser Karte;
    hier wird exakt dasselbe Verhalten nachgebildet, damit die Schranke
    (`gebucht_von = <effektiver Nutzer>`) nicht aufweicht: nur eine aktive
    Impersonation veraendert den Wert, sonst ist es der Session-Nutzer.
    """
    try:
        from diakronos_app.api import impersonation as _impersonation

        fn = getattr(_impersonation, "get_effective_user", None)
        if callable(fn):
            return fn()
    except Exception:  # noqa: BLE001 — Modul (noch) nicht portiert
        pass
    return session.user


# ── Badge-Counts (Phase 4) ──────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_widget_badge_counts():
    """Gibt Anzahl-Badges fuer Action-Widgets zurueck.

    Quelle: dashboard.py:307-342.

    AGGREGAT-SICHTBARKEIT (Kern dieser Karte): jeder Zaehler steht hinter
    einer Rollenpruefung. Ein Nutzer ohne die Rolle erhaelt den Schluessel
    GAR NICHT — die Zahl wird also nicht einmal berechnet. Genau das
    verhindert, dass ein Aggregat Dinge mitzaehlt, die der Betrachter einzeln
    nicht sehen darf. 1:1 uebernommen, per Test belegt.
    """
    user = session.user
    roles = permissions.get_roles(user)
    result: dict[str, int] = {}

    # pending-registrations: Termine zur Moderation (Kalenderadmin)
    if "Kalenderadministrator" in roles or "System Manager" in roles:
        count = _count_ueberlappende_ressourcen_events()
        result["pending-registrations"] = int(count or 0)

    # manage-registrations: Offene Anmeldungen (Admin)
    #
    # UXD-R18: Der Zaehler fragte den Status „Ausstehend“ ab — den gibt es in
    # dieser Anwendung fuer Anmeldungen NICHT. Offene Anfragen stehen als
    # „Anmeldeanfrage“ in der Tabelle (Vorgabe: einen Status, der nie
    # vorkommt, meldet immer 0). Gezaehlt wird deshalb ueber die EINE Quelle
    # `admin_hub.OFFENE_ANMELDESTATI` — so koennen Seitenleiste und
    # Anmelde-Verwaltung nicht auseinanderlaufen.
    if "Mitgliederadministrator" in roles or "System Manager" in roles:
        from diakronos_app.api.admin_hub import OFFENE_ANMELDESTATI

        count = _db.count(
            "Anmeldung",
            _coerce_filters("Anmeldung", {"status": ["in", list(OFFENE_ANMELDESTATI)]}),
        )
        result["manage-registrations"] = int(count or 0)

        # open-signups: Aktive Registrierungslinks
        count = _db.count(
            "Registrierungslink",
            _coerce_filters("Registrierungslink", {"aktiv": 1}),
        )
        result["open-signups"] = int(count or 0)

    return result


@whitelist(allow_guest=False)
def get_navigation_zaehler():
    """Kennzahlen fuer die Seitenleiste (UXD-R18).

    Eigener, kleiner Endpunkt statt des Widget-Endpunkts: die Seitenleiste
    laeuft auf JEDER Seite (auch mobil im „Mehr“-Blatt) und braucht genau eine
    Zahl — den Stand offener Anmeldeanfragen. `get_widget_badge_counts` bleibt
    unveraendert der Widget-Zaehler; beide lesen denselben Status-Vorrat
    (`admin_hub.OFFENE_ANMELDESTATI`), deshalb koennen sie nicht
    auseinanderlaufen.

    Rolle wie beim Zaehler: nur `Mitgliederadministrator`/`System Manager`
    bekommen die Zahl. Ohne Rolle fehlt der Schluessel GANZ (nicht 0) — die
    Oberflaeche blendet dann nichts ein.
    """
    user = session.user
    if not user or user == "Guest":
        return {}
    roles = permissions.get_roles(user)
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        return {}

    from diakronos_app.api.admin_hub import OFFENE_ANMELDESTATI

    offene = _db.count(
        "Anmeldung",
        _coerce_filters("Anmeldung", {"status": ["in", list(OFFENE_ANMELDESTATI)]}),
    )
    return {"anfragen": int(offene or 0)}


def _count_ueberlappende_ressourcen_events() -> int:
    """COUNT(DISTINCT a.name) ueber die Selbst-Ueberlappung von `Element`.

    Original-SQL (dashboard.py:319-330) — die Original-Datenbank erlaubt
    einen Self-JOIN auf dieselbe Tabelle:

        SELECT COUNT(DISTINCT a.name)
        FROM `tabElement` a
        JOIN `tabElement` b
          ON a.ressource = b.ressource AND a.name != b.name
         AND a.element_start < b.element_end AND a.element_end > b.element_start
         AND a.docstatus != 2 AND b.docstatus != 2
        WHERE a.ressource IS NOT NULL AND a.ressource != ''

    Umgestellt auf `get_all` + Python-Aggregation (kein rohes SQL): beide
    Seiten sind Zeilen derselben Tabelle, daher genuegt EIN Lesevorgang.
    Ergebnis ist die Zahl der Elemente mit mindestens einer ueberlappenden
    zweiten Belegung derselben Ressource.
    """
    rows = get_all(
        "Element",
        filters=[
            ["docstatus", "!=", 2],
        ],
        fields=["name", "ressource", "element_start", "element_end"],
    ) or []

    # Nur vollstaendige Zeilen (beide Zeiten + Ressource) sind vergleichbar.
    aktiv = [
        r for r in rows
        if r.get("ressource") and r.get("element_start") and r.get("element_end")
    ]

    by_ressource: dict[str, list[dict[str, Any]]] = {}
    for r in aktiv:
        by_ressource.setdefault(r["ressource"], []).append(r)

    kollidierend: set[str] = set()
    for eintraege in by_ressource.values():
        for i, a in enumerate(eintraege):
            for b in eintraege:
                if a["name"] == b["name"]:
                    continue
                if a["element_start"] < b["element_end"] and a["element_end"] > b["element_start"]:
                    kollidierend.add(a["name"])
                    break
    return len(kollidierend)
