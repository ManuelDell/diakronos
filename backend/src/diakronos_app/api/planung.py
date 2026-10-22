"""Portierung von `diakronos.diakonos.api.planung` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/planung.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    get_vorlagen                get_plaene              get_plan_uebersicht
    get_positionen              set_position_verantwortlicher
    get_teilnehmer              set_rollenbesetzung     get_besetzungsmatrix
    generiere_rotation          generiere_plan          speichere_plan_entwurf
    veroeffentliche_plan        zurueckziehen_plan      get_abgeleitete_positionen
    create_plan

Berechtigungen, im Original ueber Frappe-Rollen und das `_permissions`-Modul:

    _require_login        -> Login-Guard (Guest -> 403)
    _is_admin             -> permissions.is_admin()
    _require_plan_read    -> Entwurfsschranke + check_permission + Leitung/Verantwortliche
    _require_plan_write   -> Admin | Plan-Leitung | Verantwortlicher
    _require_plan_create  -> Admin | Verantwortlicher Bereich/Gruppe

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user          -> session.user
    frappe.get_roles(user)       -> permissions.get_roles(user)
    frappe.get_all(...)          -> query.get_all(...)      (Zeilen sind dicts)
    frappe.get_doc(...)          -> query.get_doc(...)      -> Document
    frappe.db.get_value(...)     -> query.get_value(...)
    frappe.db.exists(...)        -> _exists(...) (Modell-Lookup ueber count)
    frappe.db.count(...)         -> _count(...)
    frappe.new_doc(..).insert()  -> _create(...)
    doc.feld = x; doc.save()     -> _update_doc(...)
    doc.append(feld, row)        -> _child_insert(...) / _child_replace(...)
    frappe.delete_doc(...)       -> _delete_doc(...)
    frappe.db.commit()           -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)       -> throw(msg, exc)
    frappe.utils.now()           -> _now()
    frappe.utils.today()         -> _today()
    frappe.utils.getdate(x)      -> _to_date(x)
    frappe.utils.get_datetime(x) -> _to_datetime(x)
    frappe._dict                 -> SimpleNamespace
    frappe.db.get_table_columns  -> column_names(...)
    frappe.has_permission(...)   -> check_permission(...)   (keine Entsprechung)
    frappe.db.sql(...)           -> get_all(...) + Python-Aggregation

Nicht portiert aus `auswahl.py` (Modul ist noch nicht portiert): `ERLAUBTE_DOCTYPES`
und `referenz_label` sind hier 1:1 nachgebildet — dieselbe Whitelist und dasselbe
Anzeigefeld je DocType, damit die Validierung in `speichere_plan_entwurf` nicht
schwaecher wird als im Original. Sobald `auswahl.py` portiert ist, gehoeren die
beiden hierher importiert.
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.planung"

import datetime
import hashlib
import json
import random
from types import SimpleNamespace
from typing import Any

from diakronos_app.frappe_compat.mitglied_sichtbarkeit import (
    darf_vertrauliches_sehen,
    maskiere_datensatz,
)
from diakronos_app.frappe_compat.db import db as _db
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.permissions import (
    check_permission,
    darf_entwurf_sehen,
    get_roles,
    is_admin,
)
from diakronos_app.frappe_compat.permissions import (
    ist_verantwortlich_fuer as _ist_verantwortlich_fuer,
)
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session

from diakronos_app.frappe_compat.api_helpers import (
    _child_delete,
    _child_insert,
    _child_rows,
    _count,
    _create,
    _delete_doc,
    _now,
    _today,
    _update_doc,
    column_names,
    get_all,
    get_doc,
    get_value,
    is_known,
    throw,
)
from diakronos_app.api.kronos.permissions import get_accessible_calendars


ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]

# ── Whitelist der Inhalts-DocTypes (Quelle: auswahl.py, noch nicht portiert) ──
# Nur diese DocTypes darf eine Position referenzieren. Ein nicht gelisteter
# DocType -> throw. Niemals den Parameter ungeprueft durchreichen.
ERLAUBTE_DOCTYPES = {
    "Lied",
    "Dienstrolle",
    "Gruppe",
    "Eventkategorie",
}

# Anzeigefeld je erlaubtem DocType (fuer `referenz_label`).
# Lied.autoname = hash -> das Frontend muss ueber `name` verlinken, nie ueber
# den Titel. name ist der Hash, label der Titel.
ANZEIGEFELD = {
    "Lied": "titel",
    "Dienstrolle": "rollenname",
    "Gruppe": "gruppenname",
    "Eventkategorie": "event_category_name",
}


# ── Compat-Helfer (Frappe-Utilities ohne Entsprechung) ──────────────────────


def _exists(doctype: str, filters) -> bool:
    """`frappe.db.exists(doctype, name|filters)` ueber die Compat-Schicht.

    `db.exists` reicht Filter unveraendert an `count` weiter; ein String-Name
    wird vorher auf `{"name": name}` normalisiert (Frappe-Semantik).
    """
    if not is_known(doctype):
        return False
    if isinstance(filters, str):
        filters = {"name": filters}
    return bool(_db.exists(doctype, filters))


def _to_date(value):
    """`frappe.utils.getdate` — ISO-Datum oder datetime -> `date`."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value)[:10])


def _to_datetime(value):
    """`frappe.utils.get_datetime` — ISO-String/datetime -> `datetime`."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _get_user_mitglied_name(user: str) -> str | None:
    """Mitglied-Name zu einem User (via `user`-Link, Fallback `email`)."""
    name = get_value("Mitglied", {"user": user}, "name")
    if not name:
        email = get_value("User", user, "email") or user
        name = get_value("Mitglied", {"email": email}, "name")
    return name


def _referenz_label(referenz_doctype, referenz_name):
    """Anzeigetext einer Dienstplan-Referenz (Quelle: auswahl.referenz_label).

    `ANZEIGEFELD` ist die EINE Quelle der Wahrheit. Gibt es das Anzeigefeld
    nicht (unbekannter DocType) oder ist es leer, faellt das Label auf
    `referenz_name` zurueck.
    """
    if not referenz_doctype or not referenz_name:
        return referenz_name or ""
    feld = ANZEIGEFELD.get(referenz_doctype)
    if feld and is_known(referenz_doctype):
        wert = get_value(referenz_doctype, referenz_name, feld)
        if wert:
            return wert
    return referenz_name


# ── Berechtigungen ──────────────────────────────────────────────────────────


def _require_login() -> str:
    """Wirft PermissionError, falls nicht angemeldet (Guest)."""
    user = session.user
    if user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)
    return user


def _is_admin(user=None) -> bool:
    user = user or session.user
    if user == "Administrator":
        return True
    return is_admin(user)


def _current_user_mitglied_name():
    """Mitglied-Name des aktuellen Users (via user-Link, Fallback email)."""
    user = session.user
    if user in ("Guest", "Administrator"):
        return None
    return _get_user_mitglied_name(user)


def _get_plan(plan):
    """Laedt einen Dienstplan und prueft die Existenz (klare Fehlermeldung)."""
    if not plan or not _exists("Dienstplan", plan):
        throw(
            "Dienstplan '{}' nicht gefunden.".format(plan),
            DoesNotExistError,
        )
    return get_doc("Dienstplan", plan)


def _plan_dienstbereich(plan_doc):
    """Dienstbereich-Name eines Plans (aus eigenem Feld oder der Vorlage)."""
    if plan_doc.dienstbereich:
        return plan_doc.dienstbereich
    if plan_doc.vorlage:
        return get_value(
            "Dienstplan Vorlage", plan_doc.vorlage, "dienstbereich"
        )
    return None


def _ist_verantwortlich(plan_doc) -> bool:
    """True, wenn der User Verantwortlicher des Dienstbereichs oder der Gruppe
    des Plans ist."""
    return _ist_verantwortlich_fuer(_plan_dienstbereich(plan_doc), plan_doc.gruppe)


def _require_plan_read(plan_doc) -> None:
    """Lesezugriff auf den Dienstbereich des Plans erzwingen (Admin frei)."""
    _require_login()

    # Entwurfsschranke (P2-3): Ein Plan im Entwurf ist NUR fuer Ersteller,
    # Verantwortliche und Admins sichtbar — bewusst VOR der Bereichspruefung,
    # denn Ersteller und Verantwortliche sind haeufig in keiner Gruppe des
    # Bereichs und haetten ueber check_permission sonst keinen Zugriff.
    if plan_doc.ist_entwurf:
        if not darf_entwurf_sehen(
            plan_doc.owner, _plan_dienstbereich(plan_doc), plan_doc.gruppe
        ):
            throw("Keine Leseberechtigung für diesen Entwurf.", FrappePermissionError)
        return

    if _is_admin():
        return
    dienstbereich = _plan_dienstbereich(plan_doc)
    if not dienstbereich:
        # ABWEICHUNG: das Original ruft hier `frappe.has_permission("Dienstplan",
        # "read", name)`. Diese Funktion existiert in der Compat-Schicht nicht
        # (fehlende Bereichszuordnung -> fail closed). Die Pruefung faellt
        # daher auf Admin/Leitung/Verantwortliche
        # zurueck und verweigert sonst.
        if _is_admin():
            return
        if plan_doc.leitung and plan_doc.leitung == _current_user_mitglied_name():
            return
        if _ist_verantwortlich(plan_doc):
            return
        throw("Keine Leseberechtigung für diesen Plan.", FrappePermissionError)
    perm = check_permission("Dienstbereich", dienstbereich, "read")
    if not perm.get("allowed"):
        # Leitung des Plans darf ihren eigenen Plan lesen.
        if plan_doc.leitung == _current_user_mitglied_name():
            return
        # Verantwortliche ebenso — sie sind oft in keiner Gruppe des Bereichs
        # und haetten ueber den ancestor_path sonst keinerlei Sicht.
        if _ist_verantwortlich(plan_doc):
            return
        throw(
            "Keine Leseberechtigung fuer diesen Dienstbereich.",
            FrappePermissionError,
        )


def _require_plan_write(plan_doc) -> None:
    """Schreibzugriff erzwingen: Admin oder Plan-Leitung."""
    _require_login()
    if _is_admin():
        return
    if plan_doc.leitung and plan_doc.leitung == _current_user_mitglied_name():
        return
    if _ist_verantwortlich(plan_doc):
        return
    throw(
        "Keine Schreibberechtigung fuer diesen Plan. Erforderlich: "
        "Plan-Leitung, Verantwortlicher des Dienstbereichs bzw. der "
        "Gruppe, oder Rolle Mitgliederadministrator / "
        "System Manager.",
        FrappePermissionError,
    )


def _require_plan_create(dienstbereich, gruppe) -> None:
    """Schreibrecht zum ANLEGEN eines neuen Dienstplans erzwingen.

    Da der Plan noch nicht existiert, gibt es (noch) keine Plan-Leitung —
    relevant sind daher Admin, Verantwortlicher des Dienstbereichs oder
    der Gruppe.
    """
    _require_login()
    if _is_admin():
        return
    user = session.user
    if dienstbereich and _exists(
        "Dienstbereich Verantwortlicher",
        {"user": user, "parent": dienstbereich},
    ):
        return
    if gruppe and _exists(
        "Gruppe Verantwortlicher",
        {"user": user, "parent": gruppe},
    ):
        return
    throw(
        "Keine Berechtigung zum Anlegen eines Dienstplans. "
        "Erforderlich: Verantwortlicher des Dienstbereichs bzw. der "
        "Gruppe, oder Rolle Mitgliederadministrator / System "
        "Manager.",
        FrappePermissionError,
    )


# ── Vorlagen ────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_vorlagen(dienstbereich=None):
    """Alle Dienstplan-Vorlagen, optional auf einen Dienstbereich gefiltert."""
    _require_login()
    filters = {}
    if dienstbereich:
        filters["dienstbereich"] = dienstbereich
    vorlagen = (
        get_all(
            "Dienstplan Vorlage",
            filters=filters,
            fields=[
                "name",
                "vorlagenname",
                "dienstbereich",
                "betriebsmodus",
                "beschreibung",
                "icon",
                "farbe",
                "positions_doctype",
                "positions_label",
                "positions_plural",
                "zuteilung_modus",
                "rotation_einheit",
                "standard_kalender",
                "einsatz_rhythmus",
                "einsatz_wochentag",
                "einsatz_uhrzeit",
                "rotation_modus",
            ],
            order_by="vorlagenname asc",
        )
        or []
    )

    result = []
    for v in vorlagen:
        kategorien = (
            get_all(
                "Dienstplan Vorlage Kategorie",
                filters={"parent": v["name"]},
                fields=["eventkategorie"],
                pluck="eventkategorie",
            )
            or []
        )
        slots = (
            get_all(
                "Dienstplan Vorlage Slot",
                filters={"parent": v["name"]},
                fields=[
                    "reihenfolge",
                    "bezeichnung",
                    "inhalt_doctype",
                    "inhalt_sammlung",
                    "dienstrolle",
                ],
                order_by="reihenfolge asc",
            )
            or []
        )
        result.append(
            {
                "name": v["name"],
                "vorlagenname": v["vorlagenname"],
                "dienstbereich": v["dienstbereich"],
                "betriebsmodus": v["betriebsmodus"],
                "beschreibung": v["beschreibung"],
                "icon": v["icon"],
                "farbe": v["farbe"],
                "positions_doctype": v["positions_doctype"],
                "positions_label": v["positions_label"],
                "positions_plural": v["positions_plural"],
                "zuteilung_modus": v["zuteilung_modus"],
                "rotation_einheit": v["rotation_einheit"],
                "standard_kalender": v["standard_kalender"],
                "einsatz_rhythmus": v["einsatz_rhythmus"],
                "einsatz_wochentag": v["einsatz_wochentag"],
                "einsatz_uhrzeit": v["einsatz_uhrzeit"],
                "rotation_modus": v["rotation_modus"],
                "kategorien": kategorien,
                "slots": slots,
            }
        )
    return result


@whitelist(allow_guest=False)
def get_plaene(dienstbereich=None, status=None):
    """Liste der Dienstplaene, optional nach Dienstbereich / Status gefiltert."""
    _require_login()
    filters = {}
    if dienstbereich:
        filters["dienstbereich"] = dienstbereich
    if status:
        filters["status"] = status
    plaene = (
        get_all(
            "Dienstplan",
            filters=filters,
            fields=[
                "name",
                "plantitel",
                "vorlage",
                "dienstbereich",
                "gruppe",
                "jahr",
                "status",
                "start_datum",
                "ende_datum",
                "leitung",
                "ist_entwurf",
                "owner",
            ],
            order_by="start_datum desc, plantitel asc",
        )
        or []
    )

    # get_all umgeht Permissions — ohne Filterung saehe jedes eingeloggte
    # Mitglied saemtliche Plaene aller Dienstbereiche.
    admin = _is_admin()
    eigenes_mitglied = None if admin else _current_user_mitglied_name()

    result = []
    for p in plaene:
        if not admin:
            bereich = p["dienstbereich"]
            if not bereich and p["vorlage"]:
                bereich = get_value("Dienstplan Vorlage", p["vorlage"], "dienstbereich")
            sichtbar = False
            if bereich:
                perm = check_permission("Dienstbereich", bereich, "read")
                sichtbar = bool(perm.get("allowed"))
            if not sichtbar and eigenes_mitglied and p["leitung"] == eigenes_mitglied:
                sichtbar = True  # eigener Plan bleibt sichtbar
            if not sichtbar and _ist_verantwortlich_fuer(bereich, p["gruppe"]):
                sichtbar = True  # Verantwortliche sehen ihren Bereich
            if not sichtbar:
                continue

            # Entwurfsschranke (P2-3): Entwuerfe fremder Leute ausfiltern —
            # nur Ersteller (owner), Verantwortliche und Admins sehen sie.
            if p["ist_entwurf"] and not darf_entwurf_sehen(
                p["owner"], bereich, p["gruppe"]
            ):
                continue

        result.append(
            {
                "name": p["name"],
                "plantitel": p["plantitel"],
                "vorlage": p["vorlage"],
                "dienstbereich": p["dienstbereich"],
                "gruppe": p["gruppe"],
                "jahr": p["jahr"],
                "status": p["status"],
                "start_datum": p["start_datum"],
                "ende_datum": p["ende_datum"],
                "leitung": p["leitung"],
                "ist_entwurf": p["ist_entwurf"],
            }
        )
    return result


@whitelist(allow_guest=False)
def get_plan_uebersicht(plan):
    """Kopf, Soll/Ist (Planzahlen) und Fortschritt je Positionsstatus."""
    doc = _get_plan(plan)
    _require_plan_read(doc)

    positionen = _child_rows(
        "Dienstplan Position",
        doc.name,
        "positionen",
        ["name", "idx", "status", "verantwortlicher"],
    )
    mitwirkende_rows = _child_rows(
        "Dienstplan Mitwirkender",
        doc.name,
        "mitwirkende",
        ["mitglied", "funktion", "hauptverantwortlich", "verfuegbar_ab", "verfuegbar_bis"],
    )
    teilnehmer_rows = _child_rows(
        "Dienstplan Teilnehmer", doc.name, "teilnehmer", ["name"]
    )

    # Fortschritt je Positionsstatus
    fortschritt = {}
    for p in positionen:
        status = p["status"] or "Geplant"
        fortschritt[status] = fortschritt.get(status, 0) + 1

    # Mitwirkende nativ aus der Child-Table (nicht aus Positions-Verantwortlichen erraten)
    # AUSTRITT-d (NM1): eine Namenssicht je Anfrage statt einer je Name.
    namen = _MitgliedNamen()
    mitwirkende = []
    for m in mitwirkende_rows:
        mitwirkende.append(
            {
                "mitglied": m["mitglied"],
                "mitglied_name": namen.fuer(m["mitglied"]),
                "funktion": m["funktion"],
                "hauptverantwortlich": bool(m["hauptverantwortlich"]),
                "verfuegbar_ab": m["verfuegbar_ab"],
                "verfuegbar_bis": m["verfuegbar_bis"],
            }
        )

    return {
        "plan": {
            "name": doc.name,
            "plantitel": doc.plantitel,
            "vorlage": doc.vorlage,
            "dienstbereich": doc.dienstbereich,
            "gruppe": doc.gruppe,
            "jahr": doc.jahr,
            "status": doc.status,
            "start_datum": doc.start_datum,
            "ende_datum": doc.ende_datum,
            "leitung": doc.leitung,
            "kalender": doc.kalender,
        },
        "soll_ist": {
            "plan_anzahl_positionen": doc.plan_anzahl_positionen,
            "plan_anzahl_verantwortliche": doc.plan_anzahl_verantwortliche,
            "plan_anzahl_teilnehmer": doc.plan_anzahl_teilnehmer,
            "ist_positionen": len(positionen),
            "ist_verantwortliche": len(
                {p["verantwortlicher"] for p in positionen if p["verantwortlicher"]}
            ),
            "ist_teilnehmer": len(teilnehmer_rows),
        },
        "fortschritt": fortschritt,
        "mitwirkende": mitwirkende,
    }


@whitelist(allow_guest=False)
def get_positionen(plan):
    """Alle Positionen eines Plans (inkl. Unterstuetzter je Position)."""
    doc = _get_plan(plan)
    _require_plan_read(doc)

    positionen = _child_rows(
        "Dienstplan Position",
        doc.name,
        "positionen",
        [
            "name",
            "idx",
            "reihenfolge",
            "bezeichnung",
            "referenz_doctype",
            "referenz_name",
            "fassung",
            "gruppe",
            "verantwortlicher",
            "dienstrolle",
            "faellig_ab",
            "status",
            "detail",
            "szene",
            "notiz",
        ],
    )
    # AUSTRITT-d (NM1): eine Namenssicht je Anfrage (Positionen + Unterstuetzter).
    namen = _MitgliedNamen()
    result = []
    for p in positionen:
        unterstuetzer_rows = _child_rows(
            "Dienstplan Position Mitglied",
            p["name"],
            "unterstuetzer",
            ["mitglied"],
        )
        unterstuetzer = [
            {
                "mitglied": u["mitglied"],
                "mitglied_name": namen.fuer(u["mitglied"]),
            }
            for u in unterstuetzer_rows
        ]
        result.append(
            {
                "name": p["name"],
                "idx": p["idx"],
                "reihenfolge": p["reihenfolge"],
                "bezeichnung": p["bezeichnung"],
                "referenz_doctype": p["referenz_doctype"],
                "referenz_name": p["referenz_name"],
                "fassung": p["fassung"],
                "gruppe": p["gruppe"],
                "verantwortlicher": p["verantwortlicher"],
                "verantwortlicher_name": namen.fuer(p["verantwortlicher"]),
                "dienstrolle": p["dienstrolle"],
                "unterstuetzer": unterstuetzer,
                "faellig_ab": p["faellig_ab"],
                "status": p["status"],
                "detail": p["detail"],
                "szene": p["szene"],
                "notiz": p["notiz"],
            }
        )
    return result


@whitelist(allow_guest=False)
def set_position_verantwortlicher(plan, row, mitglied):
    """Setzt den Verantwortlichen einer Position (row = idx oder name)."""
    doc = _get_plan(plan)
    _require_plan_write(doc)

    position = _find_position(doc, row)
    if position is None:
        throw("Position nicht gefunden (row='{}').".format(row))

    if mitglied:
        if not _exists("Mitglied", mitglied):
            throw("Mitglied '{}' nicht gefunden.".format(mitglied))
        _update_doc(
            "Dienstplan Position", position["name"], {"verantwortlicher": mitglied}
        )
        gesetzt = mitglied
    else:
        _update_doc(
            "Dienstplan Position", position["name"], {"verantwortlicher": None}
        )
        gesetzt = ""

    return {
        "success": True,
        "position": position["name"] or position["idx"],
        "verantwortlicher": gesetzt,
        "verantwortlicher_name": _mitglied_name(mitglied) if mitglied else "",
    }


# ── Teilnehmer ──────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_teilnehmer(plan):
    """Teilnehmer eines Plans mit aufgeloestem Elternkontakt.

    Je Kind: Name, Alter (aus geburtstag), Untergruppe, Rolle (Dienstrolle
    des Mitwirkenden bzw. leer). Der Elternkontakt wird zur Laufzeit aus
    "Mitglied Beziehung" aufgeloest (beziehungstyp=Elternteil); alternativ
    zaehlt `kontakt_abweichend` der Teilnehmer-Zeile. Es wird nicht dupliziert:
    gleiche Eltern werden pro Kind nur einmal geliefert.
    """
    doc = _get_plan(plan)
    _require_plan_read(doc)

    teilnehmer = _child_rows(
        "Dienstplan Teilnehmer",
        doc.name,
        "teilnehmer",
        ["mitglied", "status", "untergruppe", "kontakt_abweichend", "kann_solo"],
    )
    mitwirkende = _child_rows(
        "Dienstplan Mitwirkender",
        doc.name,
        "mitwirkende",
        ["mitglied", "funktion", "hauptverantwortlich"],
    )

    # Rolle je Teilnehmer aus den Mitwirkenden ableiten
    rolle_map = {}
    haupt_map = {}
    for m in mitwirkende:
        if m["mitglied"]:
            rolle_map.setdefault(m["mitglied"], m["funktion"])
            if m["hauptverantwortlich"]:
                haupt_map[m["mitglied"]] = m["funktion"]

    mitglied_names = [t["mitglied"] for t in teilnehmer if t["mitglied"]]
    alter_map = _alter_map(mitglied_names)
    eltern_map = _eltern_map(mitglied_names)

    # AUSTRITT-d (NM1): eine Namenssicht je Anfrage.
    namen = _MitgliedNamen()
    result = []
    for t in teilnehmer:
        mitglied = t["mitglied"] or ""
        eltern = eltern_map.get(mitglied, [])
        kontakt = t["kontakt_abweichend"] or ""
        kontakt_name = namen.fuer(kontakt)

        # Rolle: Dienstrolle des Mitwirkenden (Hauptverantwortlicher zuerst)
        rolle = haupt_map.get(mitglied) or rolle_map.get(mitglied) or ""

        result.append(
            {
                "mitglied": mitglied,
                "mitglied_name": namen.fuer(mitglied),
                "alter": alter_map.get(mitglied),
                "untergruppe": t["untergruppe"] or "",
                "rolle": rolle or "",
                "status": t["status"] or "",
                "kann_solo": bool(t["kann_solo"]),
                "kontakt_abweichend": kontakt,
                "kontakt_name": kontakt_name,
                "elternkontakte": eltern,
            }
        )
    return result


@whitelist(allow_guest=False)
def set_rollenbesetzung(plan, rolle, mitglied, besetzung_nr=1):
    """Setzt/tauscht eine Rollenbesetzung. Prueft Eindeutigkeit.

    Rollenbesetzung hat KEINEN DB-Unique-Schutz. Die Pruefung
    (dienstplan, rolle, besetzung_nr) ist daher hier: ein bestehender
    Datensatz mit gleichem Tripel wird aktualisiert statt dupliziert; eine
    abweichende Besetzung derselben Nummer ersetzt den bisherigen.
    """
    doc = _get_plan(plan)
    _require_plan_write(doc)

    if not rolle:
        throw("Rolle darf nicht leer sein.")
    if not mitglied:
        throw("Mitglied darf nicht leer sein.")
    if not _exists("Mitglied", mitglied):
        throw("Mitglied '{}' nicht gefunden.".format(mitglied))

    try:
        besetzung_nr = int(besetzung_nr or 1)
    except (TypeError, ValueError):
        besetzung_nr = 1

    # Bestehenden Datensatz mit gleichem Tripel suchen (Eindeutigkeit)
    existing = get_value(
        "Rollenbesetzung",
        {"dienstplan": plan, "rolle": rolle, "besetzung_nr": besetzung_nr},
        "name",
    )
    if existing:
        _update_doc(
            "Rollenbesetzung",
            existing,
            {
                "teilnehmer": mitglied,
                "status": "Vorschlag",
                "zugeteilt_von": _current_user_mitglied_name(),
                "zugeteilt_am": _now(),
            },
        )
        rb_name = existing
    else:
        rb_name = _create(
            "Rollenbesetzung",
            {
                "dienstplan": plan,
                "rolle": rolle,
                "teilnehmer": mitglied,
                "besetzung_nr": besetzung_nr,
                "status": "Vorschlag",
                "zugeteilt_von": _current_user_mitglied_name(),
                "zugeteilt_am": _now(),
            },
        )

    return {
        "success": True,
        "rollenbesetzung": rb_name,
        "rolle": rolle,
        "mitglied": mitglied,
        "mitglied_name": _mitglied_name(mitglied),
        "besetzung_nr": besetzung_nr,
    }


@whitelist(allow_guest=False)
def get_besetzungsmatrix(plan):
    """Besetzungsmatrix: je Rolle + Besetzungs-Nr. der zugeordnete Teilnehmer."""
    doc = _get_plan(plan)
    _require_plan_read(doc)

    rows = (
        get_all(
            "Rollenbesetzung",
            filters={"dienstplan": plan},
            fields=["name", "rolle", "teilnehmer", "besetzung_nr", "status"],
            order_by="rolle asc, besetzung_nr asc",
        )
        or []
    )

    # Matrix: rolle -> {besetzung_nr: teilnehmer}
    # AUSTRITT-e (NR4): EINMAL die Sicht bilden, nicht je Name (N+1).
    namen = _MitgliedNamen()
    matrix = {}
    rollen = []
    seen_rollen = set()
    for r in rows:
        rolle = r["rolle"]
        if rolle not in seen_rollen:
            seen_rollen.add(rolle)
            rollen.append(rolle)
        nr = int(r["besetzung_nr"] or 1)
        matrix.setdefault(rolle, {})[nr] = {
            "teilnehmer": r["teilnehmer"],
            "teilnehmer_name": namen.fuer(r["teilnehmer"]),
            "status": r["status"],
            "rollenbesetzung": r["name"],
        }

    # Normalisierte, nach Besetzungs-Nr. geordnete Matrix
    besetzungen = []
    for rolle in rollen:
        slots = matrix[rolle]
        max_nr = max(slots.keys()) if slots else 1
        zeile = [
            slots.get(
                i,
                {"teilnehmer": "", "teilnehmer_name": "", "status": ""},
            )
            for i in range(1, max_nr + 1)
        ]
        if not zeile:
            zeile = [{"teilnehmer": "", "teilnehmer_name": "", "status": ""}]
        besetzungen.append({"rolle": rolle, "besetzungen": zeile})

    return {"rollen": rollen, "besetzungen": besetzungen, "matrix": matrix}


# ── Rotation ────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def generiere_rotation(plan, von, bis, dry_run=True):
    """Verteilt die Positionen reihum ueber die Einsatztermine im Zeitraum.

    rotation_einheit der Vorlage steuert, WAS rotiert: Mitglied, Familie
    (ueber Mitglied Beziehung), Untergruppe oder ganze Gruppe (rotation_pool).
    Schreibt Element Mitarbeiter je Termin — aber nur, wenn dry_run falsch ist
    (Default True: nur Vorschlag zurueckgeben, nichts schreiben).

    Abgeloest durch `generiere_plan` (P2-2): dieses Modul erzeugt die Termine
    selbst aus der Vorlage und schreibt in keinem Fall `Element` / `Element
    Mitarbeiter` — das macht erst der Veroeffentlichungs-Schritt (P2-3). Die
    Funktion bleibt fuer Bestandsaufrufe erhalten.
    """
    doc = _get_plan(plan)
    _require_plan_read(doc)
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() not in ("false", "0", "no")

    vorlage = get_doc("Dienstplan Vorlage", doc.vorlage)
    rot_einheit = vorlage.rotation_einheit or "Mitglied"

    # Einsatztermine im Zeitraum (Elemente mit Element.dienstplan == plan)
    elemente = (
        get_all(
            "Element",
            filters={
                "dienstplan": plan,
                "element_start": ["between", [von, bis]],
            },
            fields=["name", "element_name", "element_start"],
            order_by="element_start asc",
        )
        or []
    )
    if not elemente:
        return {
            "vorschlag": [],
            "dry_run": dry_run,
            "hinweis": "Keine Einsatztermine im Zeitraum gefunden.",
        }

    # Rotationspool aus Positionen des Plans
    positionen = _child_rows(
        "Dienstplan Position", doc.name, "positionen", ["verantwortlicher"]
    )
    pool = [p for p in positionen if p["verantwortlicher"]]

    if rot_einheit == "Gruppe":
        # rotation_pool der Vorlage: Liste von Gruppen (Dienstplan Vorlage Gruppe)
        gruppen = (
            get_all(
                "Dienstplan Vorlage Gruppe",
                filters={"parent": doc.vorlage},
                fields=["gruppe"],
                pluck="gruppe",
            )
            or []
        )
        einheiten = [
            {"typ": "gruppe", "name": g, "label": g, "mitglieder": []} for g in gruppen
        ]
    elif rot_einheit == "Untergruppe":
        # Untergruppen der Plan-Gruppe
        subfilters = {}
        if doc.gruppe:
            subfilters["gruppe"] = doc.gruppe
        untergruppen = (
            get_all("Untergruppe", filters=subfilters, fields=["name"], pluck="name")
            or []
        )
        einheiten = [
            {"typ": "untergruppe", "name": u, "label": u, "mitglieder": []}
            for u in untergruppen
        ]
    elif rot_einheit == "Familie":
        # Familien-Cluster ueber Mitglied Beziehung (Ehepartner/Elternteil)
        einheiten = _familien_einheiten([p["verantwortlicher"] for p in pool])
    else:
        # Standard: jedes Mitglied ist seine eigene Rotationseinheit
        namen = _MitgliedNamen()
        einheiten = [
            {
                "typ": "mitglied",
                "name": p["verantwortlicher"],
                "label": namen.fuer(p["verantwortlicher"]),
                "mitglieder": [p["verantwortlicher"]],
            }
            for p in pool
        ]

    if not einheiten:
        return {
            "vorschlag": [],
            "dry_run": dry_run,
            "hinweis": "Kein Rotationspool verfügbar "
            "(keine verantwortlichen Positionen bzw. "
            "leerer rotation_pool).",
        }

    vorschlag = []
    for i, element in enumerate(elemente):
        einheit = einheiten[i % len(einheiten)]
        mitglieder = einheit.get("mitglieder") or []
        # Fallback: bei Gruppen-/Untergruppen-Einheiten die Mitglieder aufloesen
        if not mitglieder and einheit["typ"] in ("gruppe", "untergruppe"):
            mitglieder = _einheit_mitglieder(einheit["typ"], einheit["name"])
        vorschlag.append(
            {
                "element": element["name"],
                "element_name": element["element_name"],
                "element_start": str(element["element_start"]),
                "einheit_typ": einheit["typ"],
                "einheit": einheit["name"],
                "einheit_label": einheit["label"],
                "mitglieder": mitglieder,
            }
        )

        # Schreiben nur bei Bestaetigung (dry_run=False)
        if not dry_run:
            _schreibe_element_mitarbeiter(
                element["name"], mitglieder, vorlage.standard_dienstrolle
            )

    return {"vorschlag": vorschlag, "dry_run": dry_run, "rotation_einheit": rot_einheit}


# ── Generator (P2-2) ────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def generiere_plan(
    plan,
    von,
    bis,
    dry_run=True,
    rhythmus=None,
    wochentag=None,
    rotation_modus=None,
    slots=None,
    pool=None,
):
    """Erzeugt aus Vorlage + Zeitraum einen Planungs-Vorschlag (P2-2).

    Abgeloest `generiere_rotation`: Hier werden die Termine NICHT als
    existierende `Element`-Datensaetze vorausgesetzt, sondern aus dem
    `einsatz_rhythmus` der Vorlage selbst erzeugt. Es wird in keinem Fall
    `Element` / `Element Mitarbeiter` geschrieben — auch bei dry_run=False
    entstehen nur Child-Zeilen unter `Dienstplan.termine` und
    `Dienstplan.positionen`; das Veroeffentlichen nach Kronos uebernimmt P2-3.

    Rueckgabe: {"termine": [...], "positionen": [...], "anzahl": {...}}.
    dry_run=True (Default) schreibt nichts.
    """
    doc = _get_plan(plan)
    _require_plan_read(doc)
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() not in ("false", "0", "no")

    vorlage = get_doc("Dienstplan Vorlage", doc.vorlage)

    # Wizard-Uebersteuerungen (P2-8): gesetzte Werte schlagen die Vorlage;
    # ungesetzte (None) verhalten sich exakt wie der Bestand.
    eff_rhythmus = (
        None if not (rhythmus and str(rhythmus).strip()) else str(rhythmus).strip()
    )
    eff_wochentag = (
        None
        if not (wochentag and str(wochentag).strip())
        else str(wochentag).strip()
    )
    eff_rot_modus = (
        None
        if not (rotation_modus and str(rotation_modus).strip())
        else str(rotation_modus).strip()
    )

    # Schritt 1 — Datumsliste
    daten = _rhythmus_daten(
        vorlage, doc, von, bis, rhythmus=eff_rhythmus, wochentag=eff_wochentag
    )
    if len(daten) > 200:
        throw(
            "Zeitraum erzeugt {n} Termine — Obergrenze ist 200. Bitte "
            "den Zeitraum (von/bis) verkleinern.".format(n=len(daten))
        )

    # Slots: Wizard liefert ggf. eigene (leere Liste ist eine gueltige
    # Uebersteuerung), sonst die Slots der Vorlage.
    if slots is not None:
        slot_rows = _normalisiere_slots(slots)
    else:
        slot_rows = (
            get_all(
                "Dienstplan Vorlage Slot",
                filters={"parent": vorlage.name},
                fields=[
                    "reihenfolge",
                    "bezeichnung",
                    "inhalt_doctype",
                    "inhalt_sammlung",
                    "dienstrolle",
                ],
                order_by="reihenfolge asc",
            )
            or []
        )
        # get_all liefert dicts -> in attributlesbare Zeilen heben, damit der
        # Generator-Kern (wie im Original mit frappe._dict) `.feld` lesen kann.
        slot_rows = [
            SimpleNamespace(
                reihenfolge=s["reihenfolge"],
                bezeichnung=s["bezeichnung"],
                inhalt_doctype=s["inhalt_doctype"],
                inhalt_sammlung=s["inhalt_sammlung"],
                dienstrolle=s["dienstrolle"],
            )
            for s in slot_rows
        ]

    # Rotations-Kontext
    rot_modus = (eff_rot_modus or vorlage.rotation_modus or "").strip() or "Reihenfolge"
    zufall = rot_modus == "Zufall"
    seed = _seed_from(plan)

    # Personen-Rotation nur bei zuteilung_modus == "Rotation"
    person_einheiten = None
    if (vorlage.zuteilung_modus or "").strip() == "Rotation":
        if pool is not None:
            # Wizard-Pool ersetzt die aus den Positionen abgeleitete Liste.
            person_pool = _normalisiere_pool(pool)
        else:
            person_pool = [
                SimpleNamespace(verantwortlicher=p["verantwortlicher"])
                for p in _child_rows(
                    "Dienstplan Position",
                    doc.name,
                    "positionen",
                    ["verantwortlicher"],
                )
                if p["verantwortlicher"]
            ]
        person_einheiten = _rotation_einheiten(doc, vorlage, person_pool)
    person_ptr = seed
    termin_used_personen = set()

    # Inhalts-Rotation: eigener Zeiger pro (inhalt_doctype, sammlung)
    content_ptr = {}
    candidate_cache = {}

    termine = []
    positionen = []
    for datum in daten:
        termine.append(
            {
                "datum": str(datum),
                "ressource": _ressource_bestimmen(vorlage),
            }
        )
        # "Niemand wird zweimal am selben Datum gezogen" — ein used-Set pro
        # Termin fuer Personen UND Inhalte, das Teil des Generators ist (nicht
        # der spaeteren Konflikterkennung).
        termin_used_personen.clear()
        termin_used_inhalt = set()

        for slot in slot_rows:
            pos = {
                "faellig_ab": str(datum),
                "reihenfolge": slot.reihenfolge or 0,
                "bezeichnung": slot.bezeichnung or "",
                "referenz_doctype": None,
                "referenz_name": None,
                "fassung": None,
                "verantwortlicher": None,
                "dienstrolle": slot.dienstrolle,
                "_inhalt_sammlung": slot.inhalt_sammlung or None,
            }

            # Inhalts-Rotation (sobald der Slot einen Inhalt-DocType hat)
            if slot.inhalt_doctype:
                ziehung = _inhalt_ziehen(
                    slot.inhalt_doctype,
                    slot.inhalt_sammlung,
                    content_ptr,
                    candidate_cache,
                    seed,
                    zufall,
                    termin_used_inhalt,
                )
                if ziehung.get("referenz_name"):
                    pos["referenz_doctype"] = slot.inhalt_doctype
                    pos["referenz_name"] = ziehung["referenz_name"]
                    pos["fassung"] = ziehung.get("fassung")
                    termin_used_inhalt.add(ziehung["referenz_name"])

            # Personen-Rotation
            if person_einheiten:
                einheit, person_ptr = _person_ziehen(
                    person_einheiten, person_ptr, zufall, termin_used_personen
                )
                person = einheit.get("verantwortlicher")
                if person:
                    pos["verantwortlicher"] = person
                    termin_used_personen.add(person)

            positionen.append(pos)

    # Anzeige-Labels nur fuer die Rueckgabe ergaenzen (inhalt_sammlung des Slots
    # + referenz_label). Beide Felder existieren NICHT auf der Child-Tabelle
    # `Dienstplan Position` — deshalb bleiben sie aus `positionen` (Schreibpfad)
    # heraus und werden nur fuer den Vorschlag/Diff (P2-6) angereichert.
    result_positionen = []
    for pos in positionen:
        anreicherung = dict(pos)
        anreicherung["inhalt_sammlung"] = pos.pop("_inhalt_sammlung", None)
        if pos.get("referenz_doctype") and pos.get("referenz_name"):
            anreicherung["referenz_label"] = _referenz_label(
                pos["referenz_doctype"], pos["referenz_name"]
            )
        else:
            anreicherung["referenz_label"] = None
        result_positionen.append(anreicherung)

    result = {
        "termine": termine,
        "positionen": result_positionen,
        "anzahl": {
            "termine": len(termine),
            "positionen": len(positionen),
            "slots": len(slot_rows),
        },
        "dry_run": dry_run,
        "generator": "generiere_plan",
    }

    if not dry_run:
        # Schreibpfad: nur unter `Dienstplan`, niemals `Element`.
        _require_plan_write(doc)
        for t in termine:
            _child_insert(
                "Dienstplan Termin",
                doc.name,
                "termine",
                {"datum": t["datum"], "ressource": t["ressource"]},
            )
        for p in positionen:
            schreib = {k: v for k, v in p.items() if not k.startswith("_")}
            _child_insert("Dienstplan Position", doc.name, "positionen", schreib)

    return result


# ── Raster-Treue speichern (P2-8) ───────────────────────────────────────────


def _normalisiere_slots(slots):
    """Wizard-Slots in die Form der `Dienstplan Vorlage Slot`-Tabelle bringen.

    Erwartet eine Liste von Dicts mit den Schluesseln `reihenfolge`,
    `bezeichnung`, `inhalt_doctype`, `inhalt_sammlung`, `dienstrolle` (die
    fehlenden Keys werden defensiv mit leerem Wert ergaenzt, damit der
    Generator-Kern keine Attribute nachschlaegt, die die Child-Zeilen nicht
    tragen). Rueckgabe sind attributlesbare Objekte — genauso wie `get_all` sie
    im Original liefert — damit der Generator-Kern sie per Attributzugriff
    lesen kann.
    """
    out = []
    for i, s in enumerate(slots or []):
        if not isinstance(s, dict):
            # Auch objektartige (Child-Zeile) tolerieren.
            s = s.as_dict() if hasattr(s, "as_dict") else {}
        out.append(
            SimpleNamespace(
                reihenfolge=(
                    s.get("reihenfolge") if s.get("reihenfolge") is not None else i + 1
                ),
                bezeichnung=s.get("bezeichnung") or "",
                inhalt_doctype=s.get("inhalt_doctype") or None,
                inhalt_sammlung=s.get("inhalt_sammlung") or None,
                dienstrolle=s.get("dienstrolle") or None,
            )
        )
    return out


def _normalisiere_pool(pool):
    """Wizard-Pool auf die Form des `generiere_plan`-Rotationspools bringen.

    `pool` ist im Frontend eine Liste von Mitglied-IDs/-Namen. Der
    Generator-Kern liest vom Rotationspool ausschliesslich `.verantwortlicher`
    (siehe `_rotation_einheiten`), weshalb jede Nennung in ein Objekt mit
    genau diesem Attribut gehoben wird. Leere Eintraege fallen weg.
    """
    out = []
    for m in pool or []:
        if not isinstance(m, str):
            # Bereits ein Objekt (Child-Zeile / Namespace) -> so lassen.
            out.append(m)
            continue
        m = m.strip()
        if not m:
            continue
        out.append(SimpleNamespace(verantwortlicher=m))
    return out


@whitelist(allow_guest=False)
def speichere_plan_entwurf(plan, payload):
    """Persistiert den tatsaechlichen Rasterinhalt eines Dienstplan-Entwurfs.

    P2-8: `saveDraft` im Wizard darf den Plan NICHT ueber `generiere_plan`
    regenerieren (das wirft jede Handarbeit weg). Dieser Endpunkt ersetzt
    stattdessen `Dienstplan.termine` und `Dienstplan.positionen` vollstaendig
    durch den aus dem Raster serialisierten Inhalt. `ist_entwurf` bleibt
    unberuehrt (das macht `veroeffentliche_plan` / `zurueckziehen_plan`).

    Validierung (NICHT blind uebernehmen, stilles Verwerfen ist genau der
    Fehler, den diese Karte behebt):
      - `referenz_doctype` muss aus derselben Whitelist stammen, die auch
        `auswahl.get_inhalt_optionen` nutzt (ERLAUBTE_DOCTYPES).
      - `referenz_name` muss im jeweiligen DocType existieren.
      - `ressource` (Termin) muss existieren.
      - `verantwortlicher` (Position) muss ein `Mitglied` sein.
      - Ungueltige Zeile -> throw mit Datum und Bezeichnung.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            throw("Payload konnte nicht als JSON gelesen werden.")
    payload = payload or {}

    doc = _get_plan(plan)
    _require_plan_write(doc)

    # ── Validierung der Zeilen AUSSERHALB des Doc, damit ein Wurf weder
    #    einen Teil-Commit noch einen Teil-Save zuruecklaesst.
    termine = [_validiere_termin(doc, t) for t in (payload.get("termine") or [])]
    positionen = [
        _validiere_position(doc, p) for p in (payload.get("positionen") or [])
    ]

    # Bestehende Element-Verknuepfungen je Datum erhalten (falls der Plan
    # bereits veroeffentlicht und zurueckgezogen wurde): das Raster
    # transportiert `element` nicht mit, darf es aber nicht zerstoeren.
    vor_element = {}
    for t in _child_rows(
        "Dienstplan Termin", doc.name, "termine", ["datum", "element"]
    ):
        if t["datum"] and t["element"]:
            vor_element.setdefault(str(t["datum"]), t["element"])

    # ── Vollstaendig ersetzen (schlaefrige Vergleiche vermeiden) ──────────
    _child_delete("Dienstplan Termin", doc.name, "termine")
    _child_delete("Dienstplan Position", doc.name, "positionen")

    for t in termine:
        row = {
            "datum": t["datum"],
            "ressource": t["ressource"],
            "notiz": t["notiz"],
        }
        el = vor_element.get(str(t["datum"]))
        if el:
            row["element"] = el
        termin_name = _child_insert("Dienstplan Termin", doc.name, "termine", row)
        for zr in t["zusatzressourcen"]:
            _child_insert(
                "Element Ressource",
                termin_name,
                "zusatzressourcen",
                {
                    "ressource": zr["ressource"],
                    "freitext_ressource": zr["freitext_ressource"],
                    "status": zr["status"],
                    "notiz": zr["notiz"],
                },
                parenttype="Dienstplan Termin",
            )

    for p in positionen:
        _child_insert(
            "Dienstplan Position",
            doc.name,
            "positionen",
            {
                "reihenfolge": p["reihenfolge"],
                "bezeichnung": p["bezeichnung"],
                "faellig_ab": p["datum"],
                "referenz_doctype": p["referenz_doctype"],
                "referenz_name": p["referenz_name"],
                "fassung": p["fassung"],
                "verantwortlicher": p["verantwortlicher"],
                "dienstrolle": p["dienstrolle"],
            },
        )

    # Rueckgabe nach Reload, damit sie nicht einen Teil-Zustand vor dem Save zeigt.
    gespeichert = _get_plan(doc.name)
    return {
        "success": True,
        "plan": gespeichert.name,
        "ist_entwurf": gespeichert.ist_entwurf,
        "termine": len(_child_rows("Dienstplan Termin", gespeichert.name, "termine")),
        "positionen": len(
            _child_rows("Dienstplan Position", gespeichert.name, "positionen")
        ),
    }


def _datum_wert(datum, kontext=""):
    """Validiert ein Datum-Feld und gibt den normalisierten String zurueck."""
    if datum in (None, ""):
        throw(
            "Datum fehlt{ctx}.".format(
                ctx=(" bei " + kontext) if kontext else ""
            )
        )
    try:
        d = _to_date(str(datum))
    except Exception:
        throw(
            "Ungueltiges Datum '{d}'{ctx}.".format(
                d=datum, ctx=(" bei " + kontext) if kontext else ""
            )
        )
    return str(d)


def _validiere_termin(doc, t):
    """Eine `termin`-Zeile des Payloads pruefen; gibt ein sauberes Dict zurueck.

    Anmerkung: ohne einen Termin-Bezug hat keine (Zusatz-)"Ressource" Sinn —
    jede Ressourcen-Referenz wird deshalb gegen die DocType-Existenz der
    `Ressource` geprueft.
    """
    t = t or {}
    if not isinstance(t, dict):
        t = t.as_dict() if hasattr(t, "as_dict") else {}
    datum = _datum_wert(t.get("datum"), "Termin")
    ressource = t.get("ressource") or None
    if ressource and not _exists("Ressource", ressource):
        throw(
            "Ressource '{r}' existiert nicht (Termin am {d}).".format(
                r=ressource, d=datum
            )
        )

    zusatz = []
    for zr in t.get("zusatzressourcen") or []:
        if not isinstance(zr, dict):
            zr = zr.as_dict() if hasattr(zr, "as_dict") else {}
        rz = zr.get("ressource") or zr.get("name") or None
        if rz and not _exists("Ressource", rz):
            throw(
                "Zusatzressource '{r}' existiert nicht (Termin am "
                "{d}).".format(r=rz, d=datum)
            )
        if not rz and not (zr.get("freitext_ressource") or "").strip():
            # Weder Link noch Freitext -> Zeile ist leer und wertlos.
            continue
        zusatz.append(
            {
                "ressource": rz,
                "freitext_ressource": None
                if rz
                else (zr.get("freitext_ressource") or "").strip(),
                "status": (zr.get("status") and str(zr["status"]).strip() or "Angefragt"),
                "notiz": (zr.get("notiz") or "").strip() or None,
            }
        )

    return {
        "datum": datum,
        "ressource": ressource,
        "zusatzressourcen": zusatz,
        "notiz": (t.get("notiz") or "").strip() or None,
    }


def _validiere_position(doc, p):
    """Eine `position`-Zeile des Payloads pruefen; gibt ein sauberes Dict zurueck.

    Wuerfe nennen IMMER Datum und Bezeichnung — stilles Verwerfen ist exakt
    der Fehler, den diese Karte behebt.
    """
    p = p or {}
    if not isinstance(p, dict):
        p = p.as_dict() if hasattr(p, "as_dict") else {}
    datum = _datum_wert(p.get("datum"), "Position")
    bezeichnung = (p.get("bezeichnung") or "").strip()
    if not bezeichnung:
        throw(
            "Position am {d} hat keine Bezeichnung — jede Zeile "
            "braucht einen Namen.".format(d=datum)
        )
    kontext = "{d} / {b}".format(d=datum, b=bezeichnung)

    referenz_doctype = p.get("referenz_doctype") or None
    referenz_name = p.get("referenz_name") or None
    if referenz_doctype:
        if referenz_doctype not in ERLAUBTE_DOCTYPES:
            throw(
                "referenz_doctype '{dt}' ist fuer die Position "
                "{k} nicht freigegeben (erlaubt: {ok}).".format(
                    dt=referenz_doctype,
                    k=kontext,
                    ok=", ".join(sorted(ERLAUBTE_DOCTYPES)),
                )
            )
        if referenz_name and not _exists(referenz_doctype, referenz_name):
            throw(
                "Referenz '{n}' existiert nicht im DocType '{dt}' "
                "(Position {k}).".format(
                    n=referenz_name, dt=referenz_doctype, k=kontext
                )
            )
    else:
        # Ohne referenz_doctype darf auch kein referenz_name stehen.
        if referenz_name:
            throw(
                "Position {k} hat ein referenz_name '{n}', aber "
                "keinen referenz_doctype.".format(k=kontext, n=referenz_name)
            )

    verantwortlicher = p.get("verantwortlicher") or None
    if verantwortlicher and not _exists("Mitglied", verantwortlicher):
        throw(
            "Verantwortlicher '{v}' ist kein Mitglied (Position "
            "{k}).".format(v=verantwortlicher, k=kontext)
        )

    fassung = p.get("fassung") or None
    if fassung and not _exists("Liedfassung", fassung):
        throw(
            "Fassung '{f}' existiert nicht (Position {k}).".format(
                f=fassung, k=kontext
            )
        )

    dienstrolle = p.get("dienstrolle") or None
    if dienstrolle and not _exists("Dienstrolle", dienstrolle):
        throw(
            "Dienstrolle '{dr}' existiert nicht (Position {k}).".format(
                dr=dienstrolle, k=kontext
            )
        )

    try:
        reihenfolge = int(p.get("reihenfolge") or 0)
    except (TypeError, ValueError):
        reihenfolge = 0

    return {
        "datum": datum,
        "reihenfolge": reihenfolge,
        "bezeichnung": bezeichnung,
        "referenz_doctype": referenz_doctype,
        "referenz_name": referenz_name,
        "fassung": fassung,
        "verantwortlicher": verantwortlicher,
        "dienstrolle": dienstrolle,
    }


# ── Veroeffentlichen / Zurueckziehen (P2-3) ─────────────────────────────────

_ELEMENT_DAUER_MINUTEN = 60  # Default-Dauer je Einsatz (kein Dauerfeld im Plan)


def _element_times(datum, einsatz_uhrzeit):
    """Start-/End-Zeitstempel eines Einsatz-Elements aus Datum + Uhrzeit."""
    uhrzeit = einsatz_uhrzeit or "09:00:00"
    start = _to_datetime("%s %s" % (str(datum), uhrzeit))
    return start, start + datetime.timedelta(minutes=_ELEMENT_DAUER_MINUTEN)


def _plan_elementnamen(plan_doc):
    """Namen der Kronos-Elemente, die einem Plan (ueber seine Termine) gehoeren."""
    return [
        t["element"]
        for t in _child_rows(
            "Dienstplan Termin", plan_doc.name, "termine", ["element"]
        )
        if t["element"]
    ]


@whitelist(allow_guest=False)
def veroeffentliche_plan(plan):
    """Veroeffentlicht einen Entwurf: materialisiert ihn als Kronos-Elemente.

    Ablauf:
      1. Schreibrecht erzwingen (Plan-Leitung, Verantwortlicher, Admin).
      2. Fuer jeden `Dienstplan Termin` ohne `element` ein Kronos-`Element`
         anlegen; erzeugtes Element in `termin.element` zurueckschreiben.
      3. Fuer jede `Dienstplan Position` mit `verantwortlicher` eine
         `Element Mitarbeiter`-Zeile am Element des passenden Datums
         (mitglied, dienstrolle, bestaetigt = 0).
      4. `ist_entwurf = 0` setzen.

    **Idempotent**: Zweimal veroeffentlichen darf weder doppelte Elemente noch
    doppelte Mitarbeiter-Zeilen erzeugen.
    """
    doc = _get_plan(plan)
    _require_plan_write(doc)

    vorlage = get_doc("Dienstplan Vorlage", doc.vorlage) if doc.vorlage else None
    kalender = doc.kalender
    if not kalender:
        throw(
            "Der Plan hat keinen Kalender — bitte zuerst "
            "`kalender` am Dienstplan setzen."
        )
    einsatz_uhrzeit = vorlage.einsatz_uhrzeit if vorlage else None

    # ── Schritt 2: Elemente fuer Termine ohne Element ---------------------
    for termin in _child_rows(
        "Dienstplan Termin", doc.name, "termine", ["name", "datum", "element", "ressource"]
    ):
        if termin["element"]:
            continue  # idempotent: vorhandenes Element ueberspringen

        start, end = _element_times(termin["datum"], einsatz_uhrzeit)
        element_name = _create(
            "Element",
            {
                "element_name": _element_name(doc, termin["datum"]),
                "element_calendar": kalender,
                "gruppe": doc.gruppe,
                "dienstplan": doc.name,
                "ressource": termin["ressource"] or "",
                "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
                "element_end": end.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Festgelegt",
            },
        )
        # Zusatzressourcen uebernehmen (gleiche Child-Struktur: Element Ressource)
        for zr in _child_rows(
            "Element Ressource",
            termin["name"],
            "zusatzressourcen",
            ["ressource", "freitext_ressource", "status", "notiz"],
        ):
            _child_insert(
                "Element Ressource",
                element_name,
                "zusaetzliche_ressourcen",
                {
                    "ressource": zr["ressource"],
                    "freitext_ressource": zr["freitext_ressource"],
                    "status": zr["status"] or "Angefragt",
                    "notiz": zr["notiz"],
                },
            )
        _update_doc("Dienstplan Termin", termin["name"], {"element": element_name})

    # ── Schritt 3: Mitarbeiter-Zeilen je Position -------------------------
    daten_zu_element = {
        t["datum"]: t["element"]
        for t in _child_rows(
            "Dienstplan Termin", doc.name, "termine", ["datum", "element"]
        )
        if t["element"]
    }
    for pos in _child_rows(
        "Dienstplan Position",
        doc.name,
        "positionen",
        ["verantwortlicher", "faellig_ab", "dienstrolle"],
    ):
        if not pos["verantwortlicher"] or not pos["faellig_ab"]:
            continue
        element_name = daten_zu_element.get(pos["faellig_ab"])
        if not element_name:
            continue  # kein Termin zu diesem Datum -> nichts anzuhaengen
        # Idempotent: (parent, mitglied, dienstrolle) bereits vorhanden?
        if _exists(
            "Element Mitarbeiter",
            {
                "parent": element_name,
                "mitglied": pos["verantwortlicher"],
                "dienstrolle": pos["dienstrolle"] or None,
            },
        ):
            continue
        _child_insert(
            "Element Mitarbeiter",
            element_name,
            "mitarbeiter",
            {
                "mitglied": pos["verantwortlicher"],
                "dienstrolle": pos["dienstrolle"] or None,
                "bestaetigt": 0,
            },
        )

    # ── Schritt 4: Entwurf aufheben ---------------------------------------
    _update_doc("Dienstplan", doc.name, {"ist_entwurf": 0})

    doc = _get_plan(plan)
    elementnamen = _plan_elementnamen(doc)
    anzahl_mitarbeiter = 0
    if elementnamen:
        anzahl_mitarbeiter = len(
            get_all(
                "Element Mitarbeiter",
                filters={"parent": ["in", elementnamen]},
                fields=["name"],
            )
            or []
        )
    return {
        "success": True,
        "plan": doc.name,
        "ist_entwurf": 0,
        "elemente": len(elementnamen),
        "mitarbeiter": anzahl_mitarbeiter,
    }


def _element_name(plan_doc, datum):
    """Sprechender Elementname: 'Plantitel 10.01.' (kein Unique-Zwang)."""
    tag = ""
    if datum:
        try:
            tag = " %s" % _to_date(datum).strftime("%d.%m.")
        except Exception:
            tag = ""
    return "%s%s" % (plan_doc.plantitel or plan_doc.name, tag)


@whitelist(allow_guest=False)
def zurueckziehen_plan(plan):
    """Zieht einen veroeffentlichten Plan zurueck in den Entwurf.

    - setzt `ist_entwurf = 1`, und
    - entfernt die bei der Veroeffentlichung erzeugten `Element
      Mitarbeiter`-Zeilen von den Plan-Elementen.

    Die Kronos-`Element` selbst BLEIBEN stehen: An ihnen haengen ggf. inzwischen
    fremde Daten (Teilnehmer-Zusagen, Notizen, Verknuepfungen, Konflikte) — die
    duerfen durch ein Zurueckziehen nicht zerstoert werden.
    """
    doc = _get_plan(plan)
    _require_plan_write(doc)

    elementnamen = _plan_elementnamen(doc)
    entfernte = 0
    if elementnamen:
        rows = (
            get_all(
                "Element Mitarbeiter",
                filters={"parent": ["in", elementnamen]},
                fields=["name"],
            )
            or []
        )
        for r in rows:
            _delete_doc("Element Mitarbeiter", r["name"])
            entfernte += 1

    _update_doc("Dienstplan", doc.name, {"ist_entwurf": 1})

    return {
        "success": True,
        "plan": doc.name,
        "ist_entwurf": 1,
        "entfernte_mitarbeiter": entfernte,
        "elemente_verbleiben": len(elementnamen),
    }


# ── Rotationseinheiten (gemeinsam fuer beide Generatoren) ───────────────────


def _rotation_einheiten(plan_doc, vorlage, pool):
    """Rotationspool als Liste von Einheiten (Wiederverwendung aus
    `generiere_rotation`, nicht neu geschrieben)."""
    rot_einheit = vorlage.rotation_einheit or "Mitglied"

    if rot_einheit == "Gruppe":
        gruppen = (
            get_all(
                "Dienstplan Vorlage Gruppe",
                filters={"parent": vorlage.name},
                fields=["gruppe"],
                pluck="gruppe",
            )
            or []
        )
        einheiten = [
            {
                "typ": "gruppe",
                "name": g,
                "label": g,
                "mitglieder": _einheit_mitglieder("gruppe", g),
                "verantwortlicher": _erster_mitglied("gruppe", g),
            }
            for g in gruppen
        ]
    elif rot_einheit == "Untergruppe":
        subfilters = {}
        if plan_doc.gruppe:
            subfilters["gruppe"] = plan_doc.gruppe
        untergruppen = (
            get_all("Untergruppe", filters=subfilters, fields=["name"], pluck="name")
            or []
        )
        einheiten = [
            {
                "typ": "untergruppe",
                "name": u,
                "label": u,
                "mitglieder": _einheit_mitglieder("untergruppe", u),
                "verantwortlicher": _erster_mitglied("untergruppe", u),
            }
            for u in untergruppen
        ]
    elif rot_einheit == "Familie":
        names = sorted({p.verantwortlicher for p in pool if p.verantwortlicher})
        einheiten = _familien_einheiten(names)
    else:
        # Standard: jedes Mitglied ist seine eigene Einheit
        # AUSTRITT-e (NR4): EINMAL die Sicht bilden, nicht je Name (N+1).
        namen = _MitgliedNamen()
        einheiten = []
        for p in pool:
            if not p.verantwortlicher:
                continue
            einheiten.append(
                {
                    "typ": "mitglied",
                    "name": p.verantwortlicher,
                    "label": namen.fuer(p.verantwortlicher),
                    "mitglieder": [p.verantwortlicher],
                    "verantwortlicher": p.verantwortlicher,
                }
            )

    # Deduplicate nach primaerem Verantwortlichen
    seen = set()
    sauber = []
    for e in einheiten:
        k = e.get("verantwortlicher")
        if k in seen:
            continue
        seen.add(k)
        sauber.append(e)
    return sauber


def _erster_mitglied(typ, name):
    """Erstes Mitglied einer Gruppe/Untergruppe (fuer die Einheiten-Struktur)."""
    mitglieder = _einheit_mitglieder(typ, name)
    if not mitglieder:
        return None
    for m in mitglieder:
        if m:
            return m
    return None


def _person_ziehen(einheiten, ptr, zufall, used):
    """Naechste Rotationseinheit (mit Umlauf), ueberspringt Einheiten, deren
    Mitglied eine am Datum bereits benutzte Person ist."""
    n = len(einheiten)
    if n == 0:
        return {"verantwortlicher": None}, ptr
    start = ptr % n
    for step in range(n):
        idx = (start + step) % n
        einheit = einheiten[idx]
        person = einheit.get("verantwortlicher")
        if person and person in used:
            continue
        if zufall:
            # Zufall: je Aufruf neu wuerfeln, bis eine freie Einheit trifft
            kandidaten = [
                e
                for e in einheiten
                if not (e.get("verantwortlicher") and e["verantwortlicher"] in used)
            ]
            kandidaten = kandidaten or einheiten
            gewaehlt = kandidaten[random.randrange(len(kandidaten))]
            return gewaehlt, ptr + 1
        return einheit, idx + 1
    # Alle Personen sind am Datum bereits vergeben -> naechste auf jeden Fall
    einheit = einheiten[ptr % n]
    return einheit, ptr + 1


def _inhalt_ziehen(
    inhalt_doctype, sammlung, content_ptr, candidate_cache, seed, zufall, used
):
    """Zieht den naechsten Inhalt eines Slots aus DocType + optionaler Sammlung.

    Kandidaten:
      - mit inhalt_sammlung (nur Lied): `Liedgruppe Lied` mit parent=sammlung,
        sortiert nach reihenfolge. Die Zeile liefert `lied` UND ggf. `fassung`.
      - ohne Sammlung: alle Datensaetze des `inhalt_doctype`.
    Pro (DocType, Sammlung) ein eigener fortlaufender Zeiger, damit zwei
    Lied-Slots am selben Tag nicht dasselbe Lied ziehen.
    """
    key = (inhalt_doctype, sammlung or "")
    kandidaten = candidate_cache.get(key)
    if kandidaten is None:
        if inhalt_doctype == "Lied":
            kandidaten = _lied_kandidaten(sammlung)
        else:
            kandidaten = [
                {"referenz_name": r["name"], "fassung": None}
                for r in get_all(inhalt_doctype, fields=["name"], order_by="name asc")
            ]
        candidate_cache[key] = kandidaten

    if not kandidaten:
        return {"referenz_name": None, "fassung": None}

    n = len(kandidaten)
    ptr = content_ptr.get(key, seed % n)

    # Naechsten freien Kandidaten (nicht bereits heute gezogen) suchen
    for step in range(n):
        idx = (ptr + step) % n
        k = kandidaten[idx]
        if k["referenz_name"] and k["referenz_name"] in used:
            continue
        content_ptr[key] = (idx + 1) % n
        return k

    # Alles am Datum bereits vergeben -> trotzdem einen liefern
    content_ptr[key] = (ptr + 1) % n
    return kandidaten[ptr % n]


def _lied_kandidaten(sammlung):
    """Kandidatenliste fuer einen Lied-Slot.

    Mit Sammlung: aus `Liedgruppe Lied` mit parent=sammlung, sortiert nach
    reihenfolge — NICHT aus `Lied Gruppenzuordnung` (das ist die
    Organisations-Gruppe und hat eine andere Semantik). Eine vorhandene
    `fassung` wird mitgenommen. Ohne Sammlung: alle aktiven Lieder
    (deterministisch nach Titel).
    """
    if sammlung:
        rows = (
            get_all(
                "Liedgruppe Lied",
                filters={"parent": sammlung},
                fields=["lied", "fassung", "reihenfolge"],
                order_by="reihenfolge asc, creation asc",
            )
            or []
        )
        return [
            {"referenz_name": r["lied"], "fassung": r["fassung"]}
            for r in rows
            if r["lied"]
        ]
    rows = (
        get_all(
            "Lied",
            filters={"aktiv": 1},
            fields=["name"],
            order_by="titel asc, name asc",
        )
        or []
    )
    return [{"referenz_name": r["name"], "fassung": None} for r in rows]


# ── Rhythmus / Datumsliste ──────────────────────────────────────────────────

_WOCHENTAGE = {
    "Montag": 0,
    "Dienstag": 1,
    "Mittwoch": 2,
    "Donnerstag": 3,
    "Freitag": 4,
    "Samstag": 5,
    "Sonntag": 6,
}


def _rhythmus_daten(vorlage, plan_doc, von, bis, rhythmus=None, wochentag=None):
    """Datumsliste aus Vorlage + Zeitraum (Schritt 1).

    - Woechentlich / 14-taegig: auf `einsatz_wochentag`, ab dem ersten
      passenden Datum >= von.
    - Monatlich: der erste `einsatz_wochentag` jedes Monats (= 1. Montag etc.).
    - Einzeltermine: die konkreten Kalender-Termine (Element) der Plan-Gruppe
      im Zeitraum.
    - Keiner / leer: keine terminierten Termine.

    `rhythmus`/`wochentag` (P2-8): optionale Wizard-Uebersteuerungen. Werden
    sie NICHT gesetzt, dienen `einsatz_rhythmus`/`einsatz_wochentag` der
    Vorlage als Wahrheit — Bestandsaufrufe aendern sich nicht.
    """
    rhythm = (rhythmus or vorlage.einsatz_rhythmus or "").strip()
    tag_str = (wochentag or vorlage.einsatz_wochentag or "").strip()
    tag_nr = _WOCHENTAGE.get(tag_str)
    von_d = _to_date(von) if von else None
    bis_d = _to_date(bis) if bis else None

    if rhythm == "Woechentlich":
        return _wochentage_ab(von_d, bis_d, tag_nr, step=7)
    if rhythm == "14-taegig":
        return _wochentage_ab(von_d, bis_d, tag_nr, step=14)
    if rhythm == "Monatlich":
        return _erster_wochentag_pro_monat(von_d, bis_d, tag_nr)
    if rhythm == "Einzeltermine":
        return _einzeltermine(vorlage, plan_doc, von_d, bis_d)
    # "Keiner" / leer
    return []


def _wochentage_ab(von_d, bis_d, wochentag, step):
    if wochentag is None:
        return []
    if not von_d:
        return []
    # erster passender Wochentag >= von
    delta = (wochentag - von_d.weekday()) % 7
    d = von_d + datetime.timedelta(days=delta)
    out = []
    while d <= (bis_d or datetime.date.max) and len(out) < 200:
        out.append(d)
        d += datetime.timedelta(days=step)
    return out


def _erster_wochentag_pro_monat(von_d, bis_d, wochentag):
    if wochentag is None or not von_d or not bis_d:
        return []
    out = []
    y, m = von_d.year, von_d.month
    while (y, m) <= (bis_d.year, bis_d.month) and len(out) < 200:
        first = datetime.date(y, m, 1)
        delta = (wochentag - first.weekday()) % 7
        d = first + datetime.timedelta(days=delta)
        if von_d <= d <= bis_d:
            out.append(d)
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def _einzeltermine(vorlage, plan_doc, von_d, bis_d):
    """Konkrete Kalender-Termine (Element) als 'Einzeltermine'.

    Quelle sind die Elemente der Plan-Gruppe im Zeitraum — das sind die real
    terminierten Einzeltermine. Gelesen, nie geschrieben.
    """
    filters = []
    if plan_doc.gruppe:
        filters.append(["gruppe", "=", plan_doc.gruppe])
    if von_d:
        filters.append(["element_start", ">=", str(von_d)])
    if bis_d:
        filters.append(["element_start", "<=", str(bis_d)])
    elemente = (
        get_all(
            "Element", filters=filters, fields=["element_start"], order_by="element_start asc"
        )
        or []
    )
    daten = []
    for e in elemente:
        if not e["element_start"]:
            continue
        d = _to_date(e["element_start"])
        if d not in daten:
            daten.append(d)
        if len(daten) >= 200:
            break
    return daten


def _seed_from(plan):
    """Deterministischer, stabiler Seed aus dem Plannamen (fuer Reihenfolge)."""
    digest = hashlib.sha256(str(plan).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _ressource_bestimmen(vorlage):
    """Ressource aus `standard_kalender`-Umfeld bzw. leer.

    `standard_kalender` verweist auf einen `Kalender`, das Feld `ressource` am
    `Dienstplan Termin` aber auf `Ressource`. Wir setzen die Ressource nur,
    wenn sich ein `Ressource`-Datensatz mit dem Namen des Standardkalenders
    finden laesst (Namens-Gleichheit); sonst leer — defensiv, kein ungueltiger
    Link.
    """
    kalender = vorlage.standard_kalender
    if not kalender:
        return None
    if _exists("Ressource", kalender):
        return kalender
    return None


# ── Abgeleitete Positionen (Begleitplaene) ──────────────────────────────────


@whitelist(allow_guest=False)
def get_abgeleitete_positionen(plan):
    """Lieder aus den Ablaufplaenen kommender Einsaetze der Plan-Gruppe.

    Fuer Begleitplaene (z. B. Gesangsgruppe): aus jedem Ablaufplan kommender
    Einsaetze, bei denen die Gruppe eingetragen ist, werden die Lied-Positionen
    uebernommen und mit Herkunfts-Label ("aus Gottesdienst 14.09.") versehen.

    Defensiv: leere Liste, falls die Ablaufplan-Positionen die Felder
    referenz_doctype/referenz_name noch nicht haben.
    """
    doc = _get_plan(plan)
    _require_plan_read(doc)

    gruppe = doc.gruppe
    if not gruppe:
        return []

    # Spalten defensiv pruefen (Karte 1a-1)
    pos_columns = column_names("Ablaufplan Position")
    if "referenz_doctype" not in pos_columns or "referenz_name" not in pos_columns:
        return []
    elem_columns = column_names("Element")
    if "gruppe" not in elem_columns:
        return []

    now = _now()

    elemente = (
        get_all(
            "Element",
            filters=[["gruppe", "=", gruppe], ["element_start", ">=", now]],
            fields=["name", "element_name", "element_start", "ablaufplan"],
            order_by="element_start asc",
        )
        or []
    )

    result = []
    for e in elemente:
        if not e["ablaufplan"]:
            continue
        ablaufplan = get_doc("Ablaufplan", e["ablaufplan"])
        datum_label = _format_datum(e["element_start"])

        for p in _child_rows(
            "Ablaufplan Position",
            ablaufplan.name,
            "positionen",
            ["referenz_doctype", "referenz_name", "fassung", "funktion", "detail"],
        ):
            # Nur Lied-Referenzen gelten als abgeleitete Position
            if p["referenz_doctype"] != "Lied" or not p["referenz_name"]:
                continue
            lied_titel = get_value("Lied", p["referenz_name"], "titel")
            result.append(
                {
                    "lied": p["referenz_name"],
                    "lied_titel": lied_titel or p["referenz_name"],
                    "fassung": p["fassung"],
                    "funktion": p["funktion"],
                    "detail": p["detail"],
                    "herkunft": "aus {element} {datum}".format(
                        element=e["element_name"] or e["name"], datum=datum_label
                    ),
                    "element": e["name"],
                    "element_name": e["element_name"] or "",
                    "element_start": str(e["element_start"]),
                }
            )
    return result


# ── Anlegen (PlanWizard) ────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def create_plan(payload):
    """Legt einen neuen Dienstplan an (Anlege-Schritt des PlanWizard).

    Payload-Struktur (aus PlanWizard.vue):
      { dienstbereich, vorlage, plantitel, jahr, gruppe, status,
        start_datum, ende_datum,
        positionen:  [{bezeichnung, referenz_doctype, referenz_name,
                       fassung, verantwortlicher}],
        mitwirkende: [{name, mitglied_name}] }

    - `vorlage` und `plantitel` sind Pflicht.
    - `dienstbereich` wird aus der Vorlage vorbelegt, falls leer.
    - `referenz_doctype` der Positionen wird aus `vorlage.positions_doctype`
      gesetzt (NICHT blind vom Client uebernommen); bei Freitext-Vorlagen
      (positions_doctype leer) wird der Client-Wert uebernommen bzw. leer gelassen.
    - Schreibrecht: Admin / Verantwortlicher des Dienstbereichs oder der Gruppe
      (Plan-Leitung existiert beim Anlegen noch nicht).
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            throw("Payload konnte nicht als JSON gelesen werden.")
    payload = payload or {}
    vorlage = payload.get("vorlage")
    plantitel = (payload.get("plantitel") or "").strip()

    if not vorlage:
        throw("Vorlage fehlt — ein Dienstplan braucht eine Vorlage.")
    if not plantitel:
        throw("Plantitel fehlt — bitte einen Titel vergeben.")

    vorlage_doc = get_doc("Dienstplan Vorlage", vorlage)

    dienstbereich = payload.get("dienstbereich")
    if not dienstbereich:
        dienstbereich = vorlage_doc.dienstbereich

    _require_plan_create(dienstbereich, payload.get("gruppe"))

    # `kalender` nicht blind uebernehmen, sondern gegen die fuer den Aufrufer
    # zugaenglichen Kalender pruefen (get_accessible_calendars ist die eine
    # Quelle der Wahrheit fuer Kalenderzugriff).
    kalender = payload.get("kalender") or None
    if kalender:
        erlaubte = {c["name"] for c in get_accessible_calendars()}
        if kalender not in erlaubte:
            throw(
                "Kein Zugriff auf den Kalender '{}' — bitte einen der "
                "verfuegbaren Kalender waehlen.".format(kalender),
                FrappePermissionError,
            )

    plan_name = _create(
        "Dienstplan",
        {
            "plantitel": plantitel,
            "vorlage": vorlage,
            "dienstbereich": dienstbereich or None,
            "gruppe": payload.get("gruppe") or None,
            "jahr": payload.get("jahr"),
            "status": payload.get("status") or "Planung",
            "start_datum": payload.get("start_datum"),
            "ende_datum": payload.get("ende_datum"),
            "leitung": payload.get("leitung") or None,
            "kalender": kalender,
            "beschreibung": (payload.get("beschreibung") or "").strip() or None,
        },
    )

    # Positionen — referenz_doctype aus der Vorlage (falls dort gesetzt),
    # sonst darf der Client einen liefern (Freitext-Vorlagen).
    pos_doctype = vorlage_doc.positions_doctype or None
    for p in payload.get("positionen") or []:
        bezeichnung = (p.get("bezeichnung") or "").strip()
        if not bezeichnung:
            throw(
                "Position ohne Bezeichnung — jede Position braucht "
                "einen Namen."
            )
        _child_insert(
            "Dienstplan Position",
            plan_name,
            "positionen",
            {
                "bezeichnung": bezeichnung,
                "referenz_doctype": pos_doctype or p.get("referenz_doctype") or None,
                "referenz_name": p.get("referenz_name") or None,
                "fassung": p.get("fassung") or None,
                "verantwortlicher": p.get("verantwortlicher") or None,
            },
        )

    # Mitwirkende gelten fuer JEDE Vorlage. hat_rollenbesetzung und
    # hat_teilnehmerliste steuern Rollenbesetzung und Teilnehmerliste — nicht
    # die Mitwirkenden. Waeren sie daran gekoppelt, verloeren sechs der sieben
    # Vorlagen ihre Dirigenten, Prediger und Teamleiter stillschweigend.
    for m in payload.get("mitwirkende") or []:
        mitglied = (m.get("mitglied") or m.get("name") or "").strip()
        if not mitglied:
            continue
        _child_insert(
            "Dienstplan Mitwirkender",
            plan_name,
            "mitwirkende",
            {
                "mitglied": mitglied,
                "funktion": m.get("funktion") or None,
                "hauptverantwortlich": 1 if m.get("hauptverantwortlich") else 0,
            },
        )

    return {"success": True, "name": plan_name, "plantitel": plantitel}


# ── Helfer ──────────────────────────────────────────────────────────────────


def _find_position(doc, row):
    """Findet eine Position im Plan ueber idx oder Namen."""
    for p in _child_rows(
        "Dienstplan Position", doc.name, "positionen", ["name", "idx"]
    ):
        if str(row) in (str(p["idx"]), str(p["name"])):
            return p
    return None


class _MitgliedNamen:
    """Anzeigenamen fuer EINE Anfrage — die Sicht entsteht genau einmal.

    AUSTRITT-d (NM1): ``anzeigename(zeile)`` ohne ``sicht`` fragt bei JEDEM
    Namen erneut die Rollen des Aufrufers ab (``PersonenSicht.aus`` ->
    ``get_roles``); mit 30 Namen waren das 120 Abfragen statt 60. Der Aufrufer
    bildet stattdessen EINMAL eine Zuordnung und reicht sie weiter:

        namen = _MitgliedNamen()
        ...
        namen.von(zeile)        # statt _mitglied_name(kennung)

    ``_mitglied_name`` bleibt als Einzelabfrage fuer die Stellen, die genau
    einen Namen brauchen — mit derselben (einmal gebildeten) Sicht.
    """

    def __init__(self) -> None:
        from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht

        self._sicht = PersonenSicht.aus()
        self._cache: dict[str, str] = {}

    def von(self, zeile) -> str:
        """Anzeigename einer gelesenen Mitgliedszeile (ohne Abfrage)."""
        from diakronos_app.frappe_compat.personen_anzeige import anzeigename

        if not zeile:
            return ""
        kennung = str(zeile.get("name") or "")
        if kennung and kennung in self._cache:
            return self._cache[kennung]
        name = anzeigename(zeile, sicht=self._sicht) or kennung
        if kennung:
            self._cache[kennung] = name
        return name

    def fuer(self, kennung) -> str:
        """Anzeigename einer Kennung (je Kennung hoechstens eine Abfrage)."""
        if not kennung:
            return ""
        if str(kennung) in self._cache:
            return self._cache[str(kennung)]
        zeile = get_value(
            "Mitglied", kennung, ["name", "vorname", "nachname", "ausgeschlossen",
                                  "status", "austritt_datum"],
            as_dict=True,
        )
        if isinstance(zeile, list):
            zeile = zeile[0] if zeile else None
        if not zeile:
            return str(kennung)
        return self.von(zeile) or str(kennung)


def _mitglied_name(mitglied):
    if not mitglied:
        return ""
    # AUSTRITT-b (B1): Klarname einer ausgetretenen Person nur noch fuer
    # Administratoren und die Person selbst (`personen_anzeige.anzeigename`).
    # Die Zeile wird in EINER Abfrage gelesen — die Kurzform braucht den
    # Vornamen, den die Kennung allein nicht hergibt.
    return _MitgliedNamen().fuer(mitglied)


def _alter_map(mitglied_names):
    """{mitglied: alter}; Geburtstag vor Ableitung zentral maskieren.

    Bewusste Datenschutz-Abweichung: Das Frappe-Original leitet das Alter
    auch aus verborgenen Geburtstagen ab. Plan-/Gruppenleitung gibt keine
    Feldfreigabe; eigene und Admin-Daten bleiben vollstaendig.
    """
    if not mitglied_names:
        return {}
    names = [m for m in mitglied_names if m]
    if not names:
        return {}
    today = _to_date(_today())
    alter_map = {}
    for name in names:
        record = get_value("Mitglied", name,
                           ["geburtstag", "adressbuch_sichtbarkeit"], as_dict=True)
        visible = maskiere_datensatz(
            record if isinstance(record, dict) else None,
            vollstaendig=darf_vertrauliches_sehen(name),
        )
        geburtstag = (visible or {}).get("geburtstag")
        if not geburtstag:
            alter_map[name] = None
            continue
        try:
            geb = _to_date(geburtstag)
            alter = today.year - geb.year
            if (today.month, today.day) < (geb.month, geb.day):
                alter -= 1
            alter_map[name] = alter
        except Exception:
            alter_map[name] = None
    return alter_map


def _eltern_map(mitglied_names):
    """{kind: [{mitglied, mitglied_name}]} der Elternteile je Kind.

    Eltern werden ueber die Child-Table "Mitglied Beziehung" aufgeloest:
    Zeilen auf dem Datensatz des Kindes (parent=kind) mit
    beziehungstyp='Elternteil'; beziehung_zu verweist auf den Elternteil.
    Zusaetzlich zaehlt das direkte Feld Mitglied.elternteil als Fallback.
    Duplikate (gleicher Elternteil ueber beide Wege) werden eliminiert.
    """
    if not mitglied_names:
        return {}
    names = [m for m in mitglied_names if m]
    if not names:
        return {}

    eltern_map = {n: [] for n in names}

    rows = (
        get_all(
            "Mitglied Beziehung",
            filters={"parent": ["in", names], "beziehungstyp": "Elternteil"},
            fields=["parent", "beziehung_zu"],
        )
        or []
    )
    for r in rows:
        if r["beziehung_zu"]:
            eltern_map.setdefault(r["parent"], []).append(r["beziehung_zu"])

    # Fallback: direktes Feld Mitglied.elternteil
    for name in names:
        elternteil = get_value("Mitglied", name, "elternteil")
        if elternteil and elternteil not in eltern_map.get(name, []):
            eltern_map.setdefault(name, []).append(elternteil)

    # Duplikate entfernen und Namen aufloesen
    # AUSTRITT-d (NM1): eine Namenssicht fuer die ganze Liste.
    namen = _MitgliedNamen()
    result = {}
    for kind, eltern in eltern_map.items():
        seen = []
        fertig = []
        for name in eltern:
            if name in seen:
                continue
            seen.append(name)
            fertig.append({"mitglied": name, "mitglied_name": namen.fuer(name)})
        result[kind] = fertig
    return result


def _familien_einheiten(mitglied_names):
    """Cluster verwandter Mitglieder (Ehepartner/Elternteil) als Einheiten."""
    mitglied_names = [m for m in mitglied_names if m]
    if not mitglied_names:
        return []

    paired = (
        get_all(
            "Mitglied Beziehung",
            filters={
                "parent": ["in", mitglied_names],
                "beziehungstyp": ["in", ["Ehepartner", "Elternteil"]],
            },
            fields=["parent", "beziehung_zu"],
        )
        or []
    )

    # Union-Find ueber Verwandtschaft (vereinfachte Komponentenbildung)
    parent_map = {m: m for m in mitglied_names}

    def find(x):
        while parent_map[x] != x:
            parent_map[x] = parent_map[parent_map[x]]
            x = parent_map[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent_map[rb] = ra

    for r in paired:
        if r["beziehung_zu"] and r["beziehung_zu"] in parent_map:
            union(r["parent"], r["beziehung_zu"])
        union(r["parent"], r["parent"])

    clusters = {}
    for m in mitglied_names:
        clusters.setdefault(find(m), []).append(m)

    # AUSTRITT-d (NM1): eine Namenssicht fuer alle Cluster.
    namen = _MitgliedNamen()
    einheiten = []
    for root, members in clusters.items():
        members = sorted(set(members))
        label = ", ".join(namen.fuer(m) for m in members)
        einheiten.append(
            {
                "typ": "familie",
                "name": root,
                "label": label,
                "mitglieder": members,
            }
        )
    return einheiten


def _einheit_mitglieder(typ, name):
    """Mitglieder einer Gruppe/Untergruppe aufloesen."""
    if typ == "gruppe":
        rows = (
            get_all(
                "Gruppenmitgliedschaft",
                filters={"parent": name},
                fields=["mitglied"],
                pluck="mitglied",
            )
            or []
        )
    elif typ == "untergruppe":
        rows = (
            get_all(
                "Untergruppenmitgliedschaft",
                filters={"parent": name},
                fields=["mitglied"],
                pluck="mitglied",
            )
            or []
        )
    else:
        rows = []
    return [m for m in rows if m]


def _schreibe_element_mitarbeiter(element_name, mitglieder, dienstrolle):
    """Setzt die Mitarbeiter-Zeilen eines Elements (ersetzend)."""
    if not element_name:
        return
    _child_replace(
        "Element Mitarbeiter",
        element_name,
        "mitarbeiter",
        [
            {"mitglied": m, "dienstrolle": dienstrolle, "bestaetigt": 0}
            for m in mitglieder
        ],
    )


def _format_datum(element_start):
    """'14.09.' aus einem Element-Start-Zeitstempel (None-safe)."""
    if not element_start:
        return ""
    try:
        d = _to_datetime(element_start).date()
        return d.strftime("%d.%m.")
    except Exception:
        return ""


__all__ = [
    "ERLAUBTE_DOCTYPES",
    "FRAPPE_MODULE",
    "create_plan",
    "generiere_plan",
    "generiere_rotation",
    "get_abgeleitete_positionen",
    "get_besetzungsmatrix",
    "get_plan_uebersicht",
    "get_plaene",
    "get_positionen",
    "get_teilnehmer",
    "get_vorlagen",
    "set_position_verantwortlicher",
    "set_rollenbesetzung",
    "speichere_plan_entwurf",
    "veroeffentliche_plan",
    "zurueckziehen_plan",
]
