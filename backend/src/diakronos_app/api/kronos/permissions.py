"""Portierung von `diakronos.kronos.api.permissions` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/permissions.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    get_session_info          get_accessible_calendars
    get_writable_calendars

NICHT portiert (gehoeren zur Diakronos-Home-Modulverwaltung, Karte P4b ist
Kronos-Kern — siehe Portierungsliste):

    get_accessible_modules    set_home_preference    clear_home_preference

Diese drei haengen an `Diakronos Einstellungen` + den KNOWN_MODULES-Tabellen
aus `diakronos.diakonos.doctype.diakronos_einstellungen`, die im
Standalone-Backend noch nicht portiert sind. Ein Nachbau ohne diese Quelle
waere eine Erfindung — deshalb bleiben sie offen (siehe Portier-Doku).

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.get_all("Has Role", filters=..., fields=...)   -> get_all(...)
    frappe.get_roles(user)                                -> get_roles(user)
    frappe.get_doc("User", user)                          -> get_doc(...)
    frappe.get_doc("Kalender", name)                      -> get_doc(...)
    frappe.session.user                                   -> session.user
    frappe.throw(...)                                     -> _shared.throw(...)
    frappe.log_error(...)                                 -> _shared.log_error(...)
    get_effective_user()                                  -> _get_effective_user()
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.permissions"

from typing import Any

from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _child_rows,
    get_all,
    get_doc,
    get_value,
    log_error,
    session,
    throw,
)

DESK_ROLES = {"Kalenderadministrator"}

# Admin-Rollen fuer die Impersonation (Original: `impersonation.ADMIN_ROLES`).
_ADMIN_ROLES = ("System Manager", "Mitgliederadministrator")

# ── Modul-Konfiguration (P4g) ───────────────────────────────────────────────
# 1:1 aus dem Original-DocType-Modul
# `diakronos/diakronos/doctype/diakronos_einstellungen/diakronos_einstellungen.py`
# uebernommen (KNOWN_MODULES / MODULE_DEFAULTS / MODULE_ROUTES). Die
# Standalone-App hat kein DocType-Modul, aus dem sie importiert werden
# koennten, deshalb stehen sie hier als Modulkonstanten.
KNOWN_MODULES = [
    ("diakronos", "Diakronos"),
    ("kronos", "Kronos"),
    ("diakonos", "Diakonos"),
    ("psalmos", "Psalmos"),
    ("seelsorge", "Seelsorge"),
]

MODULE_DEFAULTS = {
    "Diakronos": {
        "anzeige_name": "Diakronos",
        "standard_icon": "/assets/diakronos/images/diakronos-logo.svg",
        "im_app_bereich_anzeigen": 1,
    },
    "Kronos": {
        "anzeige_name": "Kronos",
        "standard_icon": "/assets/diakronos/images/kronos-logo.svg",
        "im_app_bereich_anzeigen": 1,
    },
    "Diakonos": {
        "anzeige_name": "Diakonos",
        "standard_icon": "/assets/diakronos/images/diakronos-logo.svg",
        "im_app_bereich_anzeigen": 1,
    },
    "Psalmos": {
        "anzeige_name": "Psalmos",
        "standard_icon": "/assets/diakronos/images/psalmos-logo.svg",
        "im_app_bereich_anzeigen": 0,
    },
    "Seelsorge": {
        "anzeige_name": "Seelsorge",
        "standard_icon": "/assets/diakronos/images/seelsorge-logo.svg",
        "im_app_bereich_anzeigen": 0,
    },
}

MODULE_ROUTES = {
    "Diakronos": "/app/kronos",
    "Kronos": "/kronos",      # Hub-Seite (leitet bei 1 Tool direkt weiter)
    "Psalmos": "/psalmos",    # Eigene www-Seite
}

# ── Modul -> SPA-Ziel (A1c5) ────────────────────────────────────────────────
# `MODULE_ROUTES` oben ist der Original-Wert und zeigt auf echte Frappe-www-
# Seiten. Dieser Stack liefert genau EINE Oberflaeche aus: die SPA unter
# `/diakonos`. Deshalb liefert `MODULE_ROUTES` hier 404 — gemessen am laufenden
# Stack, mit gueltiger Sitzung:
#
#     /app/kronos  -> 404      /kronos  -> 404
#     /app/diakonos-> 404      /psalmos -> 404
#
# Welche Seite ein Modul in der SPA meint, steht im Original in EINER zweiten
# Tabelle: `MODULE_PAGES` (Referenz
# `diakronos/doctype/diakronos_einstellungen/diakronos_einstellungen.py:52`).
# Genau daraus leitet `www/kronos/index.py:47` seine Tool-Liste ab — das ist
# also die belegte Antwort auf "welche Seite gehoert zu diesem Modul", nicht
# eine eigene Erfindung. Der Wert ist bewusst die ERSTE Tool-Route, genau so
# wie der Original-Hub (`index.py:27-29`, Smart-Redirect auf `pages[0]`).
#
# FORM: hash-relativ (`#/kalender`), NICHT `/diakonos#/kalender`. Das geht mit
# beiden gaengigen Aufrufern:
#   * `navigate(route)` — `router.js:121-128` macht aus allem ohne `#` ein
#     `#<pfad>`; ein Praefix-Pfad ergaebe `#/diakonos#/kalender` (kaputt).
#   * `<a :href="route">` — loest relativ gegen die aktuelle URL auf.
# Ein hash-relativer Wert kann ausserdem NIE einen 404 erzeugen, weil er das
# Dokument nie verlaesst. Genau das ist die Eigenschaft, die die A1c5-Abnahme
# verlangt.
#
# `None` = das Modul hat in der SPA keine Entsprechung. Der Wert wird dann
# weggelassen (unten), nicht auf eine erfundene Seite gezeigt. Zwei solche
# Module: `Diakronos` (leeres `MODULE_PAGES`, im Original ein Frappe-Workspace)
# und `Seelsorge` (gibt es im Original-Frontend als App nicht).
#
# Nachweis der Benutzung (A1c5, gemessen): `route` wird in `frontend/src`
# nirgends angesteuert, im Backend nur hier, und im Referenz-Repo liest der
# einzige route-Verbraucher (`www/kronos/index.html:159`) die ANDERE Tabelle
# `MODULE_PAGES`. Die Fixierung war latent, nicht sichtbar.
MODUL_ZIEL_SPA = {
    "Kronos": "#/kalender",     # MODULE_PAGES["Kronos"][0] = /kronos/calendar
    "Diakonos": "#/mitglieder",  # MODULE_PAGES["Diakonos"][0] = /app/diakonos
    "Psalmos": "#/lieder",       # MODULE_PAGES["Psalmos"][0] = /psalmos
    # "Diakronos": None  — leeres MODULE_PAGES, im Original ein Workspace
    # "Seelsorge": None  — keine SPA-Seite (Backend-Endpunkte existieren)
}


# ── Interne Helfer (1:1 aus dem Original) ───────────────────────────────────


def _get_effective_user() -> str:
    """`impersonation.get_effective_user()`.

    Original: der echte Aufrufer; nur Admins duerfen per `__impersonated_as`
    (Mitglied-Docname) die Sicht auf ein Mitglied umschalten.

    OBEN-OHNE (ehrlich): Die Compat-Schicht hat KEINEN Request-Args-Kontext
    (`frappe.form_dict` existiert nicht, siehe `frappe_compat/__init__.py`).
    Solange die Impersonation nicht portiert ist, ist das Ergebnis deshalb
    immer `session.user`. Die Admin-Rollen-Konstante bleibt erhalten, damit der
    spaetere Impersonation-Port nur den Args-Zugriff ergaenzen muss.
    """
    return session.user



def _user_has_role(user: str, role_name: str | None) -> bool:
    """Prueft, ob User die angegebene Role hat (Kind-Tabelle `Has Role`).

    Sonderrollen (wie `frappe.get_roles`, OP-HANDY-1):
      * `All`  — jeder angemeldete Nutzer traegt diese Rolle implizit.
      * `Guest` — nur der unangemeldete Gast (`user == "Guest"`).
    Ohne diese Auswertung blieben Kalender mit Leserecht "All" fuer alle
    normalen Mitglieder unsichtbar (OP-HANDY-1).

    R-P1-8/W3: Die Rollen kommen aus `permissions.get_roles`, NICHT mehr aus
    einer eigenen `Has Role`-Abfrage. Nur dieser Weg kennt die beiden
    zusaetzlichen Schranken (ausgeschlossenes Mitglied -> keine Rollen,
    `Guest` -> keine Rollen); eine eigene Abfrage umging sie und liess eine
    ausgeschlossene Person weiter Kalender verwalten (bis zu 30 s bzw. bis
    zum Ende der Sitzung).
    """
    if user == "Administrator":
        return True
    if role_name == "All":
        # "All" = jeder angemeldete Nutzer; der Gast ist NICHT angemeldet.
        return user != "Guest"
    if role_name == "Guest":
        return user == "Guest"
    from diakronos_app.frappe_compat.permissions import get_roles

    return bool(role_name) and role_name in set(get_roles(user))


def _is_kalenderadministrator(user: str) -> bool:
    """Globale Kalenderadministrator-Rolle (oder Administrator)."""
    if user == "Administrator":
        return True
    return _user_has_role(user, "Kalenderadministrator")


def _is_moderator_of(user: str, calendar_doc: Any) -> bool:
    """Ist der User Moderator dieses Kalenders (`Kalendermoderatoren`-Tabelle)?"""
    if user == "Administrator":
        return True
    for row in _child_rows("Kalender Moderator", calendar_doc.name, "kalendermoderatoren", ["user"]):
        if row.get("user") == user:
            return True
    return False


def hat_leserecht(calendar: str | None) -> bool:
    """Leserecht des aktuellen Nutzers auf einen Kalender (OP-EVENT-R1).

    Eine Quelle fuer alle Konflikt-/Terminantworten: `get_accessible_calendars`.
    Ohne Leserecht duerfen Titel/Zeit/Kalender eines Termins nicht ausgeliefert
    werden.
    """
    if not calendar:
        return False
    return any(c["name"] == calendar for c in get_accessible_calendars())


def hat_leserecht_fuer(user: str, calendar: str | None) -> bool:
    """Leserecht eines BELIEBIGEN Nutzers auf einen Kalender (W-3, P2-4b).

    `hat_leserecht` prueft immer den Aufrufer — fuer eine Benachrichtigung an
    DRITTE (die eingeteilten Personen) braucht es dieselbe Pruefung, aber mit
    deren Namen. Gleiche Regeln wie `get_accessible_calendars`:
    Kalenderadministrator/Administrator, Leserecht-/Schreibrechts-Rolle,
    Moderator. Gate-Auswertung erfolgt ueber `_user_has_role(user, ...)`, das
    die Sonderrolle "All" richtig behandelt.
    """
    if not calendar or user == "Guest":
        return False
    try:
        doc = get_doc("Kalender", calendar)
    except Exception:  # noqa: BLE001 — unbekannter Kalender = kein Leserecht
        return False
    if _is_kalenderadministrator(user):
        return True
    for feld in ("leserechte", "schreibrechte"):
        for row in _child_rows("User Role", doc.name, feld, ["role"]):
            if _user_has_role(user, row.get("role")):
                return True
    return _is_moderator_of(user, doc)


def _can_access_desk(user: str) -> bool:
    """Nur Administrator und Kalenderadministrator duerfen in den Desk."""
    if user == "Administrator":
        return True
    return bool(DESK_ROLES & set(get_roles(user)))


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_session_info():
    """Kopfdaten fuer die SPA: Initial, Name, Rollen, Desk-/Moderationsrechte."""
    user = _get_effective_user()
    if user == "Guest":
        throw("Nicht angemeldet")
    user_doc = get_doc("User", user)
    accessible = get_accessible_calendars()
    can_moderate = any(c.get("is_moderator") for c in accessible)
    full_name = (user_doc.get("full_name") or user) if hasattr(user_doc, "get") else user
    return {
        "initial": str(full_name)[0].upper() if full_name else "?",
        "full_name": full_name,
        "name": user,
        "user_image": (user_doc.get("user_image") if hasattr(user_doc, "get") else None) or None,
        "roles": list(get_roles(user)),
        "can_access_desk": _can_access_desk(user),
        "can_moderate": can_moderate,
    }


@whitelist(allow_guest=False)
def get_accessible_calendars():
    """Alle Kalender, auf die der User mindestens Leserecht hat.

    Frontend erwartet: name, title, color, write, is_moderator, selbstverwaltet.
    """
    user = _get_effective_user()
    if user == "Guest":
        return []

    try:
        is_global_admin = _is_kalenderadministrator(user)
        calendars = get_all("Kalender", fields=["name"]) or []

        result = []
        for cal in calendars:
            doc = get_doc("Kalender", cal["name"])  # type: ignore[index]
            selbstverwaltet = bool(doc.get("selbstverwaltet"))

            # Kalenderadministrator hat vollen Zugriff auf alle Kalender.
            if is_global_admin:
                result.append({
                    "name": doc.name,
                    "title": doc.get("calendar_name") or doc.name,
                    "color": doc.get("calendar_color") or "#9ca3af",
                    "write": True,
                    "is_moderator": True,
                    "selbstverwaltet": selbstverwaltet,
                })
                continue

            can_read = False
            can_write = False

            # Leserechte pruefen.
            for row in _child_rows("User Role", doc.name, "leserechte", ["role"]):
                if _user_has_role(user, row.get("role")):
                    can_read = True

            # Schreibrechte pruefen (impliziert Leserecht).
            for row in _child_rows("User Role", doc.name, "schreibrechte", ["role"]):
                if _user_has_role(user, row.get("role")):
                    can_write = True
                    can_read = True

            is_mod = _is_moderator_of(user, doc)
            if is_mod:
                can_read = True
                can_write = True

            if can_read:
                result.append({
                    "name": doc.name,
                    "title": doc.get("calendar_name") or doc.name,
                    "color": doc.get("calendar_color") or "#9ca3af",
                    "write": can_write,
                    "is_moderator": is_mod,
                    "selbstverwaltet": selbstverwaltet,
                })

        return result

    except Exception as e:  # noqa: BLE001 — Original faengt hier alles und gibt [] zurueck
        log_error(str(e), "get_accessible_calendars")
        return []


@whitelist(allow_guest=False)
def get_writable_calendars():
    """Nur Kalender, auf die der User Schreibzugriff hat.

    K3: `is_moderator` kommt mit, damit die SPA den Hinweis „Sichtbar unter
    Terminmoderation“ nur zeigt, wenn der Aufrufer den Vorschlag dort auch
    wirklich sieht. Ohne dieses Feld behauptete der Hinweis fuer
    Schreibberechtigte ohne Moderationsrecht etwas Falsches.
    """
    accessible = get_accessible_calendars()
    return [
        {
            "name": c["name"],
            "calendar_name": c["title"],
            "calendar_color": c["color"],
            "is_moderator": bool(c.get("is_moderator")),
        }
        for c in accessible
        if c.get("write")
    ]


@whitelist(allow_guest=False)
def get_accessible_modules():
    """Zugaengliche Diakronos-Module fuer den aktuellen Nutzer (P4g).

    Quelle (READ-ONLY):
    `referenz/diakronos-frappe/diakronos/kronos/api/permissions.py:141`.

    Nutzt die Konfiguration aus `Diakronos Einstellungen` (Single). Die
    Konstanten `KNOWN_MODULES` / `MODULE_DEFAULTS` / `MODULE_ROUTES` stammen
    1:1 aus dem DocType-Modul
    `referenz/diakronos-frappe/diakronos/diakronos/doctype/diakronos_einstellungen/diakronos_einstellungen.py`
    und sind hier als Modulkonstanten nachgebildet (kein DocType-Modul in der
    Standalone-App). Ein Fehler beim Laden der Single fuehrt 1:1 wie im
    Original zu `[]` — Aufrufer (`session.get_current_user_context`) faengt
    zusaetzlich alles ab.

    `settings = frappe.get_single("Diakronos Einstellungen")` ist ein
    Frappe-Single (eine Zeile, name = DocType-Name) —
    `get_value("Diakronos Einstellungen", "Diakronos Einstellungen", ..., as_dict=True)`.
    `role_row.role` auf der Kind-Tabelle -> `_child_rows(...)`.

    Modul-Zugriff -> Compat-Schicht:

        frappe.session.user      -> session.user
        frappe.get_roles(user)   -> get_roles(user)
        frappe.get_single(...)   -> get_value(..., as_dict=True)
        getattr(settings, f"...")-> settings.get(...)   (as_dict liefert ein dict)
    """
    user = session.user

    settings = get_value(
        "Diakronos Einstellungen",
        "Diakronos Einstellungen",
        [
            "diakronos_sichtbar", "diakronos_icon", "diakronos_anzeige_name",
            "kronos_sichtbar", "kronos_icon", "kronos_anzeige_name",
            "diakonos_sichtbar", "diakonos_icon", "diakonos_anzeige_name",
            "psalmos_sichtbar", "psalmos_icon", "psalmos_anzeige_name",
            "seelsorge_sichtbar", "seelsorge_icon", "seelsorge_anzeige_name",
        ],
        as_dict=True,
    )
    if not settings:
        return []

    user_roles = set(get_roles(user))
    result = []
    for prefix, module_name in KNOWN_MODULES:
        mod_defaults = MODULE_DEFAULTS.get(module_name, {})
        sichtbar = settings.get(f"{prefix}_sichtbar")
        if sichtbar is None:
            sichtbar = mod_defaults.get("im_app_bereich_anzeigen", 1)
        if not sichtbar:
            continue

        # Rollenfilter: nur Module, fuer die der User eine der Rollen hat.
        role_rows = _child_rows(
            "Diakronos Modul Rolle", "Diakronos Einstellungen", f"{prefix}_rollen",
            ["role"],
        )
        if role_rows:
            allowed_roles = {row.get("role") for row in role_rows}
            if not (user_roles & allowed_roles):
                continue

        icon = settings.get(f"{prefix}_icon") or mod_defaults.get("standard_icon", "")
        label = (
            settings.get(f"{prefix}_anzeige_name")
            or mod_defaults.get("anzeige_name", module_name)
        )
        eintrag = {
            "module_name": module_name,
            "prefix": prefix,
            "anzeige_name": label,
            "icon": icon,
        }
        # A1c5: `route` zeigt in die SPA, nicht auf eine Frappe-www-Seite, die
        # dieser Stack nicht ausliefert. Ohne Entsprechung in der SPA entfaellt
        # der Schluessel GANZ (nicht `None`): ein `null` waere fuer jeden
        # Aufrufer ein Fallstrick (`href=null` laedt die Seite neu), ein
        # fehlender Schluessel ist schlicht "gibt es nicht". Siehe MODUL_ZIEL_SPA.
        ziel = MODUL_ZIEL_SPA.get(module_name)
        if ziel is not None:
            eintrag["route"] = ziel
        result.append(eintrag)
    return result


__all__ = [
    "DESK_ROLES",
    "KNOWN_MODULES",
    "MODULE_DEFAULTS",
    "MODULE_ROUTES",
    "MODUL_ZIEL_SPA",
    "get_accessible_calendars",
    "get_accessible_modules",
    "get_session_info",
    "get_writable_calendars",
]
