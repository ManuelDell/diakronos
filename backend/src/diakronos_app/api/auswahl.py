"""Portierung von `diakonos/api/auswahl.py` (P4g) — Suchdropdowns, 4 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/auswahl.py`

Die SPA ruft die ORIGINAL-Pfade `diakronos.diakonos.api.auswahl.<fn>` auf
(Aufrufliste des Frappe-Frontends).

SICHERHEIT (Kartenanforderung, ausdruecklich belegt):
`get_all` umgeht Berechtigungen. Darum
  (1) JEDER Endpunkt ist `allow_guest=False` UND ruft `_require_login()` —
      direkte Aufrufe werden zusaetzlich geprueft, nicht nur der HTTP-Gate.
  (2) `doctype` wird NUR gegen die Whitelist `ERLAUBTE_DOCTYPES` geprueft,
      bevor es an `get_all` geht. Kein ungepruefter Durchgriff auf beliebige
      DocTypes (sonst waere jeder DocType der App ueber einen Endpunkt lesbar).
  (3) `_cap_limit` deckelt hart bei `MAX_LIMIT` (200).
Test: `test_p4g_auswahl_*` in `backend/tests/test_p4g_audit_auswahl_session.py`.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user       -> session.user
    frappe.db.get_value(...)  -> get_value(...)      (Signature identisch)
    frappe.get_all(...)       -> get_all(...)        (dicts)
    frappe.db.count(...)      -> db.count(...)
    frappe.throw(msg, exc)    -> throw(msg, exc)
    frappe._(...)             -> (i18n entfernt, Rohstring)
    diakronos.kronos.api.permissions.get_accessible_calendars
                              -> diakronos_app.api.kronos.permissions.get_accessible_calendars
    diakronos.kronos.api.ressource_api.get_ressources
                              -> diakronos_app.api.kronos.ressource_api.get_ressources
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.auswahl"

from diakronos_app.frappe_compat.api_helpers import (
    get_all,
    get_value,
    session,
    throw,
)
from diakronos_app.frappe_compat import db
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.registry import whitelist

# ── Whitelist erlaubter DocTypes fuer Inhaltszellen ─────────────────────────
# Nur diese DocTypes darf get_inhalt_optionen abfragen. Ein nicht gelisteter
# DocType -> throw. Niemals den Parameter ungeprueft durchreichen.
ERLAUBTE_DOCTYPES = {
    "Lied",
    "Dienstrolle",
    "Gruppe",
    "Eventkategorie",
}

# Anzeigefeld je erlaubtem DocType (fuer `suche` + `label`).
# Lied.autoname = hash -> das Frontend muss ueber `name` verlinken, nie ueber
# den Titel. name ist hier der Hash, label der Titel.
ANZEIGEFELD = {
    "Lied": "titel",
    "Dienstrolle": "rollenname",
    "Gruppe": "gruppenname",
    "Eventkategorie": "event_category_name",
}

# Hartes Limit — nie hoeher, egal was der Aufrufer verlangt.
MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def _require_login():
    """Erzwingt Anmeldung UND Planungs-Zugriff.

    - Anonymer Guest wird immer abgelehnt (`allow_guest=False` ist nur der
      HTTP-Gate; direkte Aufrufe brauchen die aktive Pruefung).
    - Eine Mitglied-Zuordnung mit Status "Gast" wird abgelehnt: Gast hat nach
      dem Status-Modell nur Dashboard + Kalender + Profil — keine
      Planungs-Stammdaten. Mitglieder (Status "Mitglied" oder ohne
      Mitglied-Eintrag) haben Vollzugriff und passieren.
    """
    user = session.user
    if user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)

    email = get_value("User", user, "email") or user
    status = get_value("Mitglied", {"email": email}, "status")
    if status == "Gast":
        throw(
            "Keine Berechtigung für die Planungs-Stammdaten.",
            FrappePermissionError,
        )


def _cap_limit(limit):
    try:
        limit = int(limit or 0)
    except (TypeError, ValueError):
        limit = 0
    return min(limit or DEFAULT_LIMIT, MAX_LIMIT)


def referenz_label(referenz_doctype, referenz_name):
    """Anzeigetext einer Dienstplan-Referenz (Wiederverwendet von generiere_plan).

    `ANZEIGEFELD` (oben) ist die EINE Quelle der Wahrheit fuer die Anzeige der
    erlaubten Inhalts-DocTypes: bei `Lied` (autoname = hash) der `titel`,
    bei den uebrigen der `name`-Feldwert des DocTypes selbst. Gibt es das
    Anzeigefeld nicht (unbekannter DocType) oder ist es leer, faellt das Label
    auf `referenz_name` zurueck — derselbe Anzeigepfad wie in
    `get_inhalt_optionen` (keine zweite Wahrheit).
    """
    if not referenz_doctype or not referenz_name:
        return referenz_name or ""
    anzeigefeld = ANZEIGEFELD.get(referenz_doctype)
    if anzeigefeld:
        wert = get_value(referenz_doctype, referenz_name, anzeigefeld)
        if wert:
            return str(wert)
    return str(referenz_name)


@whitelist(allow_guest=False)
def get_inhalt_optionen(doctype, sammlung=None, suche=None, limit=50):
    """Kandidaten fuer eine Inhaltszelle.

    - doctype:  nur aus ERLAUBTE_DOCTYPES, sonst throw.
    - sammlung: (nur sinnvoll bei Lied) Kandidaten aus `Liedgruppe Lied` mit
                parent = sammlung, sortiert nach `reihenfolge`. Zusaetzlich
                `fassung` und `nummer` je Zeile.
    - suche:    Teilstring auf dem Anzeigefeld, case-insensitive.
    - Rueckgabe: [{"name": <docname>, "label": <Anzeigetext>, "fassung": …}]
                Bei Lied ist name der Hash und label der Titel.
    """
    _require_login()

    if doctype not in ERLAUBTE_DOCTYPES:
        throw(
            f"DocType '{doctype}' ist für diesen Endpunkt nicht freigegeben.",
            ValidationError,
        )

    limit = _cap_limit(limit)
    like = f"%{suche.strip()}%" if suche and suche.strip() else None

    # ── Lied mit Sammlung: Kandidaten aus Liedgruppe Lied, sortiert nach
    #    `reihenfolge`. `lied` ist der Hash (Lied.autoname = hash); Titel und
    #    gefuellte Anzeige kommen aus dem Lied, fassung/nummer aus der Zeile.
    if doctype == "Lied" and sammlung:
        kind_hashes = get_all(
            "Liedgruppe Lied",
            filters={"parent": sammlung},
            fields=["lied", "fassung", "nummer", "reihenfolge"],
            order_by="reihenfolge asc",
            limit_page_length=limit,
        )
        if not kind_hashes:
            return []

        hashes = [k["lied"] for k in kind_hashes]
        titel_map = {}
        for r in get_all(
            "Lied",
            filters={"name": ["in", hashes]},
            fields=["name", "titel"],
        ):
            titel_map[r["name"]] = r["titel"]

        result = []
        for k in kind_hashes:
            label = titel_map.get(k["lied"])
            if not label:
                continue
            if like and like.lower() not in label.lower():
                continue
            result.append({
                "name": k["lied"],
                "label": label,
                "fassung": k["fassung"],
                "nummer": k["nummer"],
            })
        return result

    # ── Alle uebrigen Faelle: direkte Abfrage auf dem Anzeigefeld ──────────
    anzeigefeld = ANZEIGEFELD[doctype]
    filters = []
    if like:
        filters.append([anzeigefeld, "like", like])

    rows = get_all(
        doctype,
        filters=filters,
        fields=["name", anzeigefeld],
        order_by=f"{anzeigefeld} asc",
        limit_page_length=limit,
    )

    return [
        {"name": r["name"], "label": r.get(anzeigefeld) or r["name"]}
        for r in rows
    ]


@whitelist(allow_guest=False)
def get_sammlungen(doctype="Lied"):
    """Liste der Liedgruppen mit name, typ, status und Liedanzahl.

    Nur status = "Aktiv". Fuer andere DocTypes leere Liste (nur Lied kennt
    Sammlungen).
    """
    _require_login()

    if doctype != "Lied":
        return []

    gruppen = get_all(
        "Liedgruppe",
        filters={"status": "Aktiv"},
        fields=["name", "gruppenname", "typ", "status"],
        order_by="gruppenname asc",
    )

    result = []
    for g in gruppen:
        anzahl = db.count(
            "Liedgruppe Lied",
            filters={"parent": g["name"]},
        )
        result.append({
            "name": g["name"],
            "gruppenname": g["gruppenname"],
            "typ": g["typ"],
            "status": g["status"],
            "anzahl_lieder": anzahl,
        })
    return result


@whitelist(allow_guest=False)
def get_kalender_optionen():
    """Kalender + Eventkategorien fuer die Wizard-Dropdowns.

    Die Stammdaten `Kalender` / `Eventkategorie` sind nur fuer System Manager
    ueber /api/resource lesbar — genau der dokumentierte Fallstrick, der
    Dirigenten ohne Admin-Rolle ein leeres Kalender-Dropdown beschert. Dieser
    Endpunkt reicht whitelisted heraus:

      - calendars:  aus `kronos.api.permissions.get_accessible_calendars()`
                    (der EINEN Quelle der Wahrheit fuer Kalenderzugriff),
                    umgemappt auf das vom Wizard erwartete
                    {name, calendar_name, calendar_color, write} Shape.
      - categories: die Eventkategorien als {name} — globale Stammdaten,
                    nicht pro Kalender getrennt.

    Vorbild: `dienstplan.get_dienstrollen`. `get_calendar_and_category_options`
    (kronos.doctype.element) wird bewusst NICHT umgebaut — andere Aufrufer
    haengen daran.
    """
    _require_login()

    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    calendars = [
        {
            "name": c["name"],
            "calendar_name": c.get("title") or c["name"],
            "calendar_color": c.get("color"),
            "write": bool(c.get("write")),
        }
        for c in get_accessible_calendars()
    ]

    categories = [
        {"name": r["name"]}
        for r in get_all(
            "Eventkategorie", fields=["name"], order_by="name asc")
    ] or []

    return {"calendars": calendars, "categories": categories}


@whitelist(allow_guest=False)
def get_ressourcen_optionen(typ=None, suche=None):
    """Ressourcen fuer die Datumszeile des Wizards.

    Wiederverwendet `kronos.api.ressource_api.get_ressources()` als einzige
    Quelle der Wahrheit und ergaenzt hier nur Typfilter und Suche — es wird
    keine zweite Ressourcen-Abfrage aufgebaut. `typ` filtert auf Raum /
    Fahrzeug / Gegenstand.
    """
    _require_login()

    from diakronos_app.api.kronos.ressource_api import get_ressources

    data = get_ressources()
    ressourcen = data.get("resources") or []

    if typ:
        ressourcen = [r for r in ressourcen if r.get("typ") == typ]
    if suche and suche.strip():
        needle = suche.strip().lower()
        ressourcen = [
            r for r in ressourcen
            if needle in (r.get("title") or "").lower()
        ]

    # Hard-Cap deckeln (get_ressources liefert unbegrenzt).
    ressourcen = ressourcen[:MAX_LIMIT]

    return [
        {
            "name": r.get("id"),
            "label": r.get("title") or r.get("id"),
            "typ": r.get("typ"),
        }
        for r in ressourcen
    ]


__all__ = [
    "ANZEIGEFELD",
    "ERLAUBTE_DOCTYPES",
    "FRAPPE_MODULE",
    "MAX_LIMIT",
    "get_inhalt_optionen",
    "get_kalender_optionen",
    "get_ressourcen_optionen",
    "get_sammlungen",
    "referenz_label",
]
