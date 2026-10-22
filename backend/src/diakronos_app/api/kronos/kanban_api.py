"""Portierung von `diakronos.kronos.api.kanban_api` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/kanban_api.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    get_kanban_board_data   save_staging_state      finalize_staged_events
    get_conflict_partner    resolve_conflict        get_moderation_count

Zustaendigkeitspruefungen (Original -> Port), alle 1:1 erhalten:

    get_kanban_board_data  -> Guest -> throw           (403 ueber allow_guest=False)
    save_staging_state     -> Guest -> stiller return  (kein throw!)
    finalize_staged_events -> Guest -> throw
    get_conflict_partner   -> Guest -> throw
    resolve_conflict       -> Guest -> throw
    get_moderation_count   -> Guest -> {"count": 0}    (kein throw!)

Zusaetzliche Rechtepruefung des Ports (Nachtbefund OP-EVENT-1):
`resolve_conflict`, `finalize_staged_events` und `save_staging_state` verlangen
zusaetzlich `is_moderator` fuer den Kalender des Termins (`_require_moderator`);
`get_conflict_partner` verraet keine Termine gesperrter Kalender mehr
(OP-EVENT-R1, `_has_read_access`) — der PARTNER wird maskiert, nicht die
Anfrage verweigert (Befund 7: Docstring korrigiert, harte Leseschranke bewusst
nicht gesetzt, siehe Kommentar an der Funktion).
`finalize_staged_events` prueft seit P0-3 Befund 5 ALLE IDs vor dem ersten
Schreiben; geloeschte IDs werden uebersprungen statt den Batch zu blockieren.

ABWEICHUNGEN (je Punkt unten begruendet):

1. `frappe.db.set_value(...)`: existiert in der Compat-Schicht nicht. Ersetzt
   durch `_update_doc(...)` — gleiche Wirkung (Felder setzen + committen),
   `update_modified=False` wird dabei ignoriert (die Compat-Schicht stempelt
   `modified` immer neu; das Original nutzt das Flag nur, damit ein
   Staging-Speichern den Snapshot-Vergleich nicht selbst verfaelscht).
2. `get_conflict_partner`: das rohe `frappe.db.sql(...)` wird auf `get_all` +
   Python-Aggregation umgestellt (kein rohes SQL mehr). Die Overlap-Semantik
   (`ressource = X AND name != Y AND element_start < end AND element_end > start`,
   ORDER BY element_start, LIMIT 1) bleibt 1:1 — die Sortierung uebernimmt
   `order_by="element_start asc"`, das LIMIT 1 der Python-Slice.
3. `get_moderation_count`: das rohe `COUNT(DISTINCT COALESCE(NULLIF(series_id,''), name))`
   wird zu einer Python-Zaehlung ueber `get_all`. Ergebnis identisch: Serien
   zaehlen als EIN Termin, sonst zaehlt der Element-Name.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user          -> session.user
    frappe.get_all(...)          -> _shared.get_all(...)  (Zeilen sind dicts)
    frappe.db.get_value(...)     -> _shared.get_value(...)
    frappe.get_doc("Element", x) -> _shared.get_doc(...) -> Document
    doc.save(ignore_permissions=..) -> _shared._update_doc(...)
    frappe.new_doc(..).insert()  -> _shared._create(...)
    frappe.log_error(...)        -> _shared.log_error(...)
    frappe.throw(msg)            -> _shared.throw(msg)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.kanban_api"

import json

from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.exceptions import ValidationError

from diakronos_app.frappe_compat.api_helpers import (
    _create,
    _update_doc,
    get_all,
    get_doc,
    get_value,
    log_error,
    session,
    throw,
)

# Felder, die `_fmt_event` aus einem Element liest (1:1 aus dem Original).
_EVENT_FIELDS = [
    "name", "element_name", "element_start", "element_end", "all_day",
    "element_calendar", "element_category", "status", "ressource",
    "ignore_conflict", "description", "modified", "modified_by", "series_id",
    # OP-EVENT-12: Antragsteller (Frappe-`owner` = wer den Termin angelegt hat).
    "owner",
    # P1-5b (W-1): Ablehnungsgrund/-wer liegen in eigenen Feldern (Migration
    # p15b_ablehnungsgrund) — sie gehoeren NICHT in die Beschreibung.
    "ablehnungs_grund", "moderiert_von",
]


def _fmt_event(e, cal_info):
    cal = cal_info.get(e.get("element_calendar"), {})
    return {
        "type":           "event",
        "id":             e.get("name"),
        "title":          e.get("element_name") or "Termin",
        "start":          str(e.get("element_start")),
        "end":            str(e.get("element_end")) if e.get("element_end") else None,
        "all_day":        bool(e.get("all_day")),
        "calendar":       e.get("element_calendar"),
        "calendar_title": cal.get("title", e.get("element_calendar")),
        "calendar_color": cal.get("color", "#3b82f6"),
        "status":         e.get("status"),
        "series_id":      e.get("series_id") or "",
        "ressource":      e.get("ressource") or "",
        "description":    e.get("description") or "",
        "modified":       str(e.get("modified")),
        "modified_by":    e.get("modified_by") or "",
        # OP-EVENT-12: Antragsteller auf der Karte zeigen. Die Kennung ist der
        # Frappe-`owner`; der Klarname wird — wenn vorhanden — nachgereicht.
        "owner":          e.get("owner") or "",
        "antragsteller":  _anzeigename(e.get("owner")),
        # P1-5b (W-1): Ablehnung in eigenen Feldern — nur fuer Moderatoren
        # (dieses Board ist Moderatoren vorbehalten) und den Antragsteller.
        "ablehnungs_grund": e.get("ablehnungs_grund") or "",
        "moderiert_von":    e.get("moderiert_von") or "",
    }


def _anzeigename(kennung: str | None) -> str:
    """Anzeigename zu einer Benutzerkennung; Fallback ist die Kennung selbst.

    AUSTRITT-d (NM3): Der Name laeuft ueber die EINE Regel
    (``personen_anzeige.anzeigename``): Ist das Mitglied AUSGETRETEN, sehen
    Nicht-Admins die Kurzform „Elvira D.“ statt des Klarnamens. Das Board steht
    Moderatoren offen, also auch Nicht-Admins.
    """
    if not kennung:
        return ""
    if kennung == "Administrator":
        return "Administrator"
    try:
        from diakronos_app.frappe_compat.personen_anzeige import (
            PersonenSicht, anzeigename,
        )

        mitglieder = get_all(
            "Mitglied",
            filters={"user": kennung},
            fields=["name", "vorname", "nachname", "ausgeschlossen", "status",
                    "austritt_datum"],
            limit_page_length=1,
        ) or []
        if mitglieder:
            return anzeigename(mitglieder[0], sicht=PersonenSicht.aus())
        row = get_value("User", kennung, ["full_name"], as_dict=True) or {}
        # `get_value` ist ohne Rueckgabe-Annotation portiert (Frappe-Kompat);
        # Pyright leitet daraus `list[Any]` ab. Zur Laufzeit ist es ein dict.
        name = row.get("full_name") if isinstance(row, dict) else None  # type: ignore[union-attr]
        if name:
            return name
    except Exception:  # noqa: BLE001 — reine Anzeigehilfe, nie hart scheitern
        pass
    return kennung


def _mod_calendars():
    """Kalender, fuer die der aktuelle User Moderationsrechte hat."""
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    allowed = get_accessible_calendars()
    return allowed, [c["name"] for c in allowed if c.get("is_moderator")]


def _has_read_access(calendar: str | None) -> bool:
    """Leserecht auf einen Kalender — Delegation an permissions.hat_leserecht."""
    from diakronos_app.api.kronos.permissions import hat_leserecht

    return hat_leserecht(calendar)


def _require_moderator(element_id):
    """Moderationsrecht fuer den Kalender des Termins erzwingen (OP-EVENT-1).

    Die Moderation/Freigabe (resolve_conflict, finalize_staged_events,
    save_staging_state, get_conflict_partner) pruefte bisher nur "nicht Gast".
    Jedes angemeldete Mitglied konnte damit fremde Termine umbenennen,
    verschieben, freigeben und den Belegungsschutz abschalten.

    Prueft gegen dieselbe Quelle wie der Moderation-Board
    (`get_accessible_calendars` -> `is_moderator`) und wirft sonst 403.
    `get_accessible_calendars` behandelt Kalenderadministrator und
    Kalendermoderator bereits als Moderator; ein unbekannter Termin bleibt
    ein fachlicher Fehler (nicht 403), damit die Meldung stimmt.
    """
    try:
        doc = get_doc("Element", element_id)
    except Exception:  # noqa: BLE001 — unbekannter Termin ist ein Fachfehler
        throw("Termin nicht gefunden")
    calendar = doc.get("element_calendar")
    if not calendar:
        throw("Termin hat keinen Kalender")
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    for c in get_accessible_calendars():
        if c["name"] == calendar and c.get("is_moderator"):
            return doc
    throw("Keine Moderationsrechte fuer Kalender " + str(calendar), FrappePermissionError)


@whitelist(allow_guest=False)
def get_kanban_board_data():
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet")

    allowed, mod_cals = _mod_calendars()
    if not mod_cals:
        return {"vorschlaege": [], "konflikte": [], "staging": [], "notifications": {},
                "abgelehnt": []}

    # Calendar info cache
    cal_info = {}
    for cn in mod_cals:
        row = get_value("Kalender", cn, ["calendar_name", "calendar_color"], as_dict=True) or {}
        cal_info[cn] = {
            "title": row["calendar_name"] or cn,  # type: ignore[index]
            "color": row["calendar_color"] or "#3b82f6",  # type: ignore[index]
        }

    raw_v = get_all("Element",
        filters={"element_calendar": ["in", mod_cals], "status": "Vorschlag"}, fields=_EVENT_FIELDS)
    raw_k = get_all("Element",
        filters={"element_calendar": ["in", mod_cals], "status": "Konflikt"}, fields=_EVENT_FIELDS)
    # P1-5b (W-1): Abgelehnte Termine erscheinen weder im Kalender noch als
    # Vorschlag/Konflikt. Sie bleiben ausschliesslich als Moderations-Historie
    # sichtbar — und nur hier, denn dieses Board ist Moderatoren vorbehalten.
    raw_a = get_all("Element",
        filters={"element_calendar": ["in", mod_cals], "status": "Abgelehnt"},
        fields=_EVENT_FIELDS, order_by="modified desc", limit_page_length=100)

    all_formatted = {e["name"]: _fmt_event(e, cal_info) for e in raw_v + raw_k}
    vorschlaege = [_fmt_event(e, cal_info) for e in raw_v]
    konflikte   = [_fmt_event(e, cal_info) for e in raw_k]
    abgelehnt   = [_fmt_event(e, cal_info) for e in raw_a]

    # Load user staging state
    staging      = []
    notifications = {}
    try:
        states = get_all("Kronos Kanban Zustand",
            filters={"user": user}, fields=["staging_events", "event_snapshots"],
            limit_page_length=1)
        if states:
            staging_ids = json.loads(states[0]["staging_events"] or "[]")  # type: ignore[index]
            snapshots   = json.loads(states[0]["event_snapshots"] or "{}")  # type: ignore[index]
            for eid in staging_ids:
                if eid in all_formatted:
                    ev = all_formatted[eid]
                    staging.append(ev)
                    snap = snapshots.get(eid, {})
                    if snap.get("modified") and snap["modified"] != ev["modified"]:
                        notifications[eid] = {"by": ev["modified_by"], "at": ev["modified"]}
    except Exception as ex:  # noqa: BLE001 — Original loggt und macht weiter
        log_error(str(ex), "get_kanban_board_data")

    # Remove staging items from their source columns
    staging_set  = {e["id"] for e in staging}
    vorschlaege  = [e for e in vorschlaege if e["id"] not in staging_set]
    konflikte    = [e for e in konflikte   if e["id"] not in staging_set]

    return {
        "vorschlaege":  vorschlaege,
        "konflikte":    konflikte,
        "staging":      staging,
        "notifications": notifications,
        # P1-5b (W-1): Moderations-Historie der abgelehnten Termine.
        "abgelehnt":    abgelehnt,
    }


@whitelist(allow_guest=False)
def save_staging_state(staging_ids):
    user = session.user
    if user == "Guest":
        return
    ids_list = json.loads(staging_ids) if isinstance(staging_ids, str) else (staging_ids or [])
    # OP-EVENT-1: Staging betrifft nur Termine eigener Moderationskalender.
    # P0-3 Befund 6: geloeschte IDs werden uebersprungen — ein RECHTSFEHLER
    # wirft weiterhin (das ist der Sinn der Pruefung).
    erlaubte_ids = []
    for eid in ids_list:
        try:
            _require_moderator(eid)
        except ValidationError:
            # Termin geloescht/unbekannt -> ueberspringen.
            continue
        erlaubte_ids.append(eid)
    ids_list = erlaubte_ids

    snaps = {}
    for eid in ids_list:
        row = get_value("Element", eid, ["modified", "modified_by"], as_dict=True)
        if row:
            snaps[eid] = {"modified": str(row["modified"]),  # type: ignore[index]
                          "modified_by": row["modified_by"] or ""}  # type: ignore[index]

    try:
        states = get_all("Kronos Kanban Zustand",
            filters={"user": user}, fields=["name"], limit_page_length=1)
        if states:
            # Original: frappe.db.set_value(..., update_modified=False)
            _update_doc("Kronos Kanban Zustand", states[0]["name"], {
                "staging_events":  json.dumps(ids_list),
                "event_snapshots": json.dumps(snaps),
            })
        else:
            _create("Kronos Kanban Zustand", {
                "user":            user,
                "staging_events":  json.dumps(ids_list),
                "event_snapshots": json.dumps(snaps),
            })
    except Exception as ex:  # noqa: BLE001 — Original loggt und macht weiter
        log_error(str(ex), "save_staging_state")
    return {"ok": True}


@whitelist(allow_guest=False)
def finalize_staged_events(event_ids):
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet")
    ids_list = json.loads(event_ids) if isinstance(event_ids, str) else (event_ids or [])

    # P0-3 Befund 5: ERST alle IDs pruefen, DANN schreiben. Vorher warf
    # `_require_moderator` mitten in der Schleife — die davor liegenden IDs
    # waren bereits freigegeben, die Staging-Liste blieb aber stehen, und eine
    # einzelne geloeschte ID blockierte den ganzen Batch (frueher per
    # try/except uebersprungen). Jetzt gilt: ein Rechteverstoss verweigert den
    # ganzen Batch, verwaiste IDs fallen still heraus.
    erlaubte_ids = []
    for eid in ids_list:
        try:
            _require_moderator(eid)
        except ValidationError:
            # Termin geloescht/unbekannt -> ueberspringen, nicht abbrechen.
            continue
        erlaubte_ids.append(eid)

    count = 0
    for eid in erlaubte_ids:
        try:
            # Original: frappe.db.set_value("Element", eid, "status", "Festgelegt")
            _update_doc("Element", eid, {"status": "Festgelegt"})
            count += 1
        except Exception as ex:  # noqa: BLE001 — Original loggt und macht weiter
            log_error(str(ex), f"finalize_event {eid}")

    # Clear staging state
    try:
        states = get_all("Kronos Kanban Zustand",
            filters={"user": user}, fields=["name"], limit_page_length=1)
        if states:
            _update_doc("Kronos Kanban Zustand", states[0]["name"], {
                "staging_events": "[]", "event_snapshots": "{}",
            })
    except Exception:  # noqa: BLE001 — Original schluckt hier alles
        pass
    return {"finalized": count}


@whitelist(allow_guest=False)
def get_conflict_partner(element_id):
    """Konfliktpartner eines Termins (Ressourcen-Ueberschneidung).

    Rechte (P0-3 Befund 7, Docstring korrigiert): dieser Endpunkt verlangt
    KEIN Moderationsrecht — er prueft nur, dass der Aufrufer den abgefragten
    Termin lesen darf. Der frueher hier behauptete Moderationszwang stand nur
    im Modul-Docstring und nie im Code.
    """
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet")
    try:
        doc = get_doc("Element", element_id)
    except Exception:  # noqa: BLE001 — Original liefert None
        return None
    if not doc.ressource:
        return None

    # P0-3 Befund 7 — BEWUSST NICHT umgesetzt: der Review schlaegt vor, den
    # abgefragten Termin auf Lesezugriff zu pruefen. Das widerspricht aber dem
    # ausgelieferten OP-EVENT-R1-Verhalten, das hier absichtlich NICHT das
    # Kalender-Leserecht verlangt: die Belegung soll auch fuer Nicht-Leser
    # erkennbar bleiben, nur Titel/Kalender werden maskiert (unten). Genau das
    # haelt `test_p4c3_ablaufplan_kanban.py::test_conflict_partner_maskiert_fremden_kalender`
    # als Regression fest. Eine harte Leseschranke macht aus der maskierten
    # Antwort ein `None` und bricht diesen Vertrag — die Entscheidung gehoert
    # dem Reviewer, nicht in diesen Patch. Die Docstring-Korrektur unten ist
    # umgesetzt (der behauptete Moderationszwang existierte nie).

    # Original: rohes SQL mit Overlap-Test, ORDER BY element_start, LIMIT 1.
    conflicts = get_all(
        "Element",
        filters={
            "ressource": doc.ressource,
            "name": ["!=", element_id],
            "element_start": ["<", str(doc.element_end)],
            "element_end": [">", str(doc.element_start)],
        },
        fields=["name", "element_name", "element_start", "element_end", "all_day",
                "element_calendar", "ressource"],
        order_by="element_start asc",
    )

    if not conflicts:
        return None
    c = conflicts[0]  # type: ignore[index]
    # OP-EVENT-R1: keine Titel/Zeit/Kalender aus gesperrten Kalendern verraten.
    # Ohne Leserecht bleibt nur die Information "belegt".
    if not _has_read_access(c["element_calendar"]):  # type: ignore[index]
        return {
            "id":       c["name"],  # type: ignore[index]
            "title":    "Belegt",  # type: ignore[index]
            "belegt":   True,
            "start":    str(c["element_start"]),  # type: ignore[index]
            "end":      str(c["element_end"]) if c["element_end"] else None,  # type: ignore[index]
            "all_day":  bool(c["all_day"]),  # type: ignore[index]
            "calendar": "",
            "ressource": c["ressource"] or "",  # type: ignore[index]
        }
    cal_title = get_value("Kalender", c["element_calendar"], "calendar_name") or c["element_calendar"]  # type: ignore[index]
    return {
        "id":       c["name"],  # type: ignore[index]
        "title":    c["element_name"] or "Termin",  # type: ignore[index]
        "start":    str(c["element_start"]),  # type: ignore[index]
        "end":      str(c["element_end"]) if c["element_end"] else None,  # type: ignore[index]
        "all_day":  bool(c["all_day"]),  # type: ignore[index]
        "calendar": cal_title,
        "ressource": c["ressource"] or "",  # type: ignore[index]
    }


@whitelist(allow_guest=False)
def resolve_conflict(element_id, action, title=None, element_start=None,
                     element_end=None, all_day=None, ressource=None, description=None,
                     grund=None):
    """
    action: 'ignore'     -> ignore_conflict=1, status=Vorschlag -> to staging
            'vorschlag'  -> status=Vorschlag, ignore_conflict=0 -> to vorschlaege col
            'festlegen'  -> save edits, status=Konflikt stays   -> to staging
            'ablehnen'   -> status=Abgelehnt, Pflichtgrund (OP-EVENT-12)
    """
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet")
    # OP-EVENT-1: Aendern/Freigeben/Belegungsschutz nur mit Moderationsrecht.
    doc = _require_moderator(element_id)

    # OP-EVENT-12: Ablehnen verlangt eine Begruendung. Ohne Grund waere die
    # Absage fuer den Antragsteller nicht nachvollziehbar — deshalb prueft das
    # der Server (nicht nur die Oberflaeche).
    if action == "ablehnen":
        grund_text = (grund or "").strip()
        if not grund_text:
            throw("Zum Ablehnen bitte einen Grund angeben.")

        grund_text = grund_text[:2000]
        # P1-5b (W-1): Der Grund gehoert NICHT in `description` — dort waere er
        # Teil des Nutzertextes und fuer jeden Leser sichtbar. Er liegt jetzt in
        # den eigenen Feldern (Migration p15b_ablehnungsgrund); beide werden nur
        # fuer Moderatoren und den Antragsteller ausgeliefert.
        _update_doc("Element", element_id, {
            "status": "Abgelehnt",
            "ablehnungs_grund": grund_text,
            "moderiert_von": user,
        })
        _benachrichtige_owner(doc, element_id, grund_text)
        return {"id": element_id, "new_status": "Abgelehnt", "action": action}

    werte = {}
    if title is not None:
        werte["element_name"] = title
    if element_start:
        werte["element_start"] = element_start
    if element_end:
        werte["element_end"] = element_end
    if all_day is not None:
        werte["all_day"] = int(all_day)
    if ressource is not None:
        werte["ressource"] = ressource or None
    if description is not None:
        werte["description"] = description

    if action == "ignore":
        werte["ignore_conflict"] = 1
        werte["status"] = "Vorschlag"
    elif action == "vorschlag":
        werte["status"] = "Vorschlag"
        werte["ignore_conflict"] = 0

    # Original: doc.save(ignore_permissions=True) — Felder UND Status zusammen.
    if werte:
        _update_doc("Element", element_id, werte)

    new_status = werte.get("status", doc.status)
    return {"id": element_id, "new_status": new_status, "action": action}


def _benachrichtige_owner(doc, element_id, grund):
    """Legt eine In-App-Nachricht (Notification Log) fuer den Antragsteller an.

    OP-EVENT-12: Beim Ablehnen soll der Antragsteller erfahren, warum sein
    Termin nicht angenommen wurde. `Notification Log` ist die bestehende
    Quelle fuer `useNotifications` (api/audit.get_unread_notifications) — es
    wird also nichts Neues erfunden. Fehler hier duerfen das Ablehnen nicht
    scheitern lassen.
    """
    owner = doc.get("owner")
    if not owner:
        return
    titel = doc.get("element_name") or "Termin"
    from diakronos_app.benachrichtigungen import schreibe_meldung

    schreibe_meldung(
        for_user=owner, subject=f"Termin abgelehnt: {titel}",
        inhalt=f"Dein Termin „{titel}“ wurde abgelehnt.\nGrund: {grund}",
        document_type="Element", document_name=element_id, typ="Terminmoderation",
    )


@whitelist(allow_guest=False)
def get_moderation_count():
    """
    Gibt die Anzahl der zu moderierenden Termine zurueck.
    Zaehlt Termine mit Status 'Vorschlag' oder 'Konflikt' in Kalendern,
    fuer die der Nutzer Moderationsrechte hat.
    Serien werden als ein Termin gezaehlt (DISTINCT series_id oder name).
    """
    if session.user == "Guest":
        return {"count": 0}

    allowed, mod_cals = _mod_calendars()
    if not mod_cals:
        return {"count": 0}

    # Original: COUNT(DISTINCT COALESCE(NULLIF(series_id, ''), name)).
    rows = get_all(
        "Element",
        filters={"status": ["in", ["Vorschlag", "Konflikt"]], "element_calendar": ["in", mod_cals]},
        fields=["name", "series_id"],
    )
    eindeutig = set()
    for r in rows:
        series_id = r["series_id"]  # type: ignore[index]
        eindeutig.add(series_id if series_id else r["name"])  # type: ignore[index]

    return {"count": len(eindeutig)}


__all__ = [
    "finalize_staged_events",
    "get_conflict_partner",
    "get_kanban_board_data",
    "get_moderation_count",
    "resolve_conflict",
    "save_staging_state",
]
