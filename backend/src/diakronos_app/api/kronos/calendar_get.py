"""Portierung von `diakronos.kronos.api.calendar_get` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/calendar_get.py`

Portierter Endpunkt (Original-dotted path ueber `FRAPPE_MODULE`):

    get_calendar_events

Der RE-EXPORT `get_accessible_calendars` des Originals (die SPA ruft BEIDE
Pfade: `permissions.get_accessible_calendars` und
`calendar_get.get_accessible_calendars`) entsteht hier ueber denselben
`FRAPPE_MODULE`-Mechanismus — siehe `_register_calendar_get_reexports`.

Die Formatierung ist die Altcode-Fachlogik und wird 1:1 uebernommen:
Lesemodus (`view_mode=True`) zeigt ausschliesslich `status == "Festgelegt"`;
im Bearbeitungsmodus kommen fuer moderierte Kalender alle Status dazu.
Farben/Border folgen dem Status (Vorschlag = transparent, Konflikt = rot).

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.session.user                       -> session.user
    frappe.get_all("Element", filters, fields) -> get_all(...)
    frappe.db.get_value("Kalender", n, feld)   -> get_value(...)
    frappe.db.sql(<SELECT ... IN ...>)         -> _child_rows / get_all(...)
    frappe.throw(...)                          -> throw(...)
    frappe.log_error(...)                      -> log_error(...)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.calendar_get"

import json
from datetime import date as _date
from datetime import datetime as _datetime
from datetime import timedelta
from typing import Any

from diakronos_app.frappe_compat.exceptions import DoesNotExistError, FrappeCompatError
from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _rethrow,
    get_all,
    get_value,
    log_error,
    session,
    throw,
)
from diakronos_app.api.kronos.permissions import get_accessible_calendars

# Feldauswahl fuer `get_all("Element", ...)` — identisch zum Original.
_EVENT_FIELDS = [
    "name",
    "element_name as title",
    "element_start as start",
    "element_end as end",
    "all_day",
    "element_color",
    "element_calendar",
    "element_category",
    "ressource",
    "ignore_conflict",
    "status",
    "description",
    "repeat_this_event",
    "series_id",
    # K-A (R-P1-8): Ablehnungsgrund + Moderator fuer die Detailansicht des
    # Antragstellers. Der Wert wird nur an den Antragsteller (owner) bzw. an
    # Moderatoren ausgeliefert — siehe `_darf_ablehnung_sehen`.
    "ablehnungs_grund",
    "moderiert_von",
    "owner",
]


def _as_bool(value: Any) -> bool:
    """`view_mode` als bool normalisieren.

    Der POST-Body kann den Wert als Bool, Zahl oder String tragen. Die SPA
    sendet den Modus ALS WORT: `view_mode: 'view'` im Lesemodus und
    `view_mode: 'edit'` im Bearbeitungsmodus (KronosCalendar.vue). Ein
    pauschales `not in ("false","0","")` machte daraus fuer `'edit'` ein
    `True` — der Bearbeitungsmodus wurde damit als Lesemodus ausgewertet und
    der Kalendermoderator sah seine eigenen Vorschlaege nie
    (Live-Befund BF1-A/C: „nichts gespeichert“).

    Deshalb: die beiden Modus-Worte werden ausdruecklich aufgeloest,
    `edit`/`bearbeiten` -> False (Bearbeitungsmodus), `view`/`lesen` -> True.
    """
    if isinstance(value, str):
        wort = value.strip().lower()
        if wort in {"edit", "bearbeiten", "write", "schreiben"}:
            return False
        if wort in {"view", "lesen", "read"}:
            return True
        return wort not in ("false", "0", "")
    return bool(value)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    """Feld eines `get_all`-Treffers lesen (`dict`)."""
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _als_datetime(wert: Any):
    """Wert als `datetime` lesen (DB kann `datetime`, `date` oder String liefern).

    K7: Statt eines Formats ueber `text[: len(fmt) + 2]` zu stutzen (Kunstgriff,
    der nur fuer genau diese vier Formate passt und bei ISO mit Offset oder
    Millisekunden still daneben liegt), wird zuerst das reine ISO-Format
    (`fromisoformat`, versteht auch `T` und Bruchteile) versucht und danach die
    bekannten Frappe-Formate — jeweils auf dem getrimmten Text.
    """
    if wert is None:
        return None
    if isinstance(wert, _datetime):
        return wert
    if isinstance(wert, _date):
        return _datetime(wert.year, wert.month, wert.day)
    text = str(wert).strip()
    if not text:
        return None
    # ISO 8601 zuerst (deckt `YYYY-MM-DD`, `...THH:MM:SS`, `...T...Z`, Offsets
    # und Sekundenbruchteile ab). `Z` -> `+00:00`, dann Zone verwerfen: alle
    # Werte im System sind naive Ortszeiten (siehe Kopfhinweis Zeitumstellung).
    try:
        iso = _datetime.fromisoformat(text.replace("Z", "+00:00"))
        return iso.replace(tzinfo=None) if iso.tzinfo else iso
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _ueberlappt_fenster(start: Any, end: Any, fenster_start: str, fenster_ende: str) -> bool:
    """BF1-C: Beruehrt `[start, end]` das Fenster `[fenster_start, fenster_ende]`?

    Ein Termin ohne Ende zaehlt als Punkttermin (`end = start`). Ein Termin,
    dessen Ende auf Mitternacht des Folgetags faellt, reicht nicht in den
    Folgetag hinein — deshalb wird das Ende um eine Sekunde zurueckgenommen.

    K7: Ein Termin mit unlesbarem Start wird NICHT stillschweigend verworfen.
    Die SQL-Abfrage hat ihn bereits als Fenster-Treffer geliefert (nur so kommt
    er hier an); ihn dann in Python wegzuwerfen hiesse: ein Termin verschwindet
    aus genau den Ansichten, in denen er hingehoert. Deshalb wird er angezeigt
    (fail-open in der ANZEIGE — hier wird nichts verborgen, nur gezeigt).
    """
    s = _als_datetime(start)
    if s is None:
        # Anzeige-Fail-open (K7): Termin zeigen statt verwerfen.
        return True
    e = _als_datetime(end) or s
    if e < s:
        e = s
    fs = _als_datetime(fenster_start)
    fe = _als_datetime(fenster_ende)
    if fs is None or fe is None:
        return True
    # K7: Bei unlesbarem Ende den Termin zeigen (siehe oben) statt als
    # Punkttermin zu verwerfen.
    if _als_datetime(end) is None and end is not None:
        return True
    if e.hour == 0 and e.minute == 0 and e.second == 0 and e > s:
        e = e - timedelta(seconds=1)
    return s <= fe and e >= fs


@whitelist(allow_guest=False)
def get_calendar_events(start_date, end_date, calendar_filter=None, view_mode=True):
    """Liefert Events fuer FullCalendar.

    view_mode=True  -> Lesemodus: alle sehen nur 'Festgelegt'
    view_mode=False -> Bearbeitungsmodus: Moderatoren sehen auch Vorschlag/Konflikt
    """
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet")

    # BF1-C: Der Tagesdialog der SPA uebergibt `dateStr` aus dem Kalender —
    # das ist ein voller ISO-Zeitstempel (`2026-10-15T00:00:00`). Frueher
    # wurde der Wert ungeprueft an `f"{datum} 23:59:59"` gehaengt; die SQL-
    # Abfrage scheiterte dann und der Dialog meldete „Keine Termine an diesem
    # Tag“, obwohl der Tag Termine hatte. Deshalb hier auf das reine Datum
    # kuerzen (der Zeitanteil ist fuer ein Tagesfenster ohne Bedeutung).
    start_date = str(start_date).strip()[:10]
    end_date = str(end_date).strip()[:10]

    view_mode = _as_bool(view_mode)

    try:
        # Zeitraum (BF1-C): Ein Kalendertag enthaelt JEDEN Termin, der den Tag
        # beruehrt — auch mehrtägige, ganztägige und ueber Mitternacht
        # laufende. Die frueher hier benutzte Bedingung
        # (`start >= Tag 00:00 UND end <= Tag 23:59`) schnitt genau diese
        # Termine weg, obwohl das Monatsraster sie am Tag anzeigt — im
        # Tages-Popup stand dann „Keine Termine an diesem Tag.“
        # Die Abfrage holt deshalb eine OBERMENGE (`start <= Tagesende`) und
        # die genaue Ueberlappung (`end >= Tagesanfang`) wird unten geprueft.
        fenster_start = f"{start_date} 00:00:00"
        fenster_ende = f"{end_date} 23:59:59"
        # BLD-R6: ECHTE UEBERLAPPUNG statt der frueheren Obermenge
        # (`start <= Fensterende`). Die Obermenge lud bei jedem Kalenderaufruf
        # die gesamte Termin-Historie bis zum Fensterende; erst die
        # Python-Pruefung unten filterte — die Last wuchs linear mit den Jahren
        # (Befund BF1b-W5).
        #
        # BEIDE Grenzen in SQL, mit der Mitternachts-Regel der Anzeige: ein
        # Termin MIT Ende beruehrt das Fenster, wenn `start <= Fensterende AND
        # end >= Fensteranfang`. Ein Termin OHNE Ende ist ein Punkttermin; er
        # wird ueber die ODER-Bedingung `end IS NULL` mitgenommen und unten in
        # Python genau gegen den Fensteranfang geprueft (das ODER-Modell kann
        # keine UND-Verknuepfung ausdruecken). Punkttermine sind selten, die
        # Last der frueheren Vollhistorie kam aus den datierten Terminen.
        filters = {
            "element_start": ["<=", fenster_ende],
        }
        or_filters = [
            ["element_end", ">=", fenster_start],
            ["element_end", "is", "not set"],
        ]

        # Erlaubte Kalender (inkl. is_moderator, selbstverwaltet Flags)
        allowed_calendars = get_accessible_calendars()
        cal_info = {
            cal["name"]: cal
            for cal in allowed_calendars
            if isinstance(cal, dict) and "name" in cal
        }
        allowed = list(cal_info.keys())

        if calendar_filter:
            try:
                requested = json.loads(calendar_filter)
                effective = list(set(requested) & set(allowed))
            except Exception:  # noqa: BLE001 — Original faellt auf `allowed` zurueck
                effective = allowed
        else:
            effective = allowed

        if not effective:
            return []

        events = []

        if view_mode:
            # Lesemodus: alle Kalender -> nur Festgelegt, egal ob Moderator oder nicht
            f = {**filters, "element_calendar": ["in", effective], "status": "Festgelegt"}
            events = get_all("Element", filters=f, or_filters=or_filters,
                             fields=_EVENT_FIELDS) or []
        else:
            # Bearbeitungsmodus: Moderatoren sehen alle Status
            mod_cals = [n for n in effective if cal_info.get(n, {}).get("is_moderator")]
            regular_cals = [n for n in effective if not cal_info.get(n, {}).get("is_moderator")]

            if mod_cals:
                # P1-5b (W-1): Moderatoren sehen hier alle Status AUSSER "Abgelehnt".
                # Ein abgelehnter Termin ist erledigt — er darf auch im
                # Bearbeitungsmodus nicht mehr im Kalender auftauchen, sondern
                # nur noch in der Moderations-Historie (kanban_api.get_kanban_board_data).
                events.extend(
                    get_all(
                        "Element",
                        filters={
                            **filters,
                            "element_calendar": ["in", mod_cals],
                            "status": ["not in", ["Abgelehnt"]],
                        },
                        or_filters=or_filters,
                        fields=_EVENT_FIELDS,
                    )
                    or []
                )
            if regular_cals:
                events.extend(
                    get_all(
                        "Element",
                        filters={
                            **filters,
                            "element_calendar": ["in", regular_cals],
                            "status": "Festgelegt",
                        },
                        or_filters=or_filters,
                        fields=_EVENT_FIELDS,
                    )
                    or []
                )

        formatted = []
        for e in events:
            element_calendar = _row_get(e, "element_calendar")
            element_color = _row_get(e, "element_color")
            status = _row_get(e, "status")
            element_category = _row_get(e, "element_category")
            ressource = _row_get(e, "ressource")
            start = _row_get(e, "start")
            end = _row_get(e, "end")

            # BF1-C: genaue Ueberlappung mit dem angefragten Fenster. Die
            # Abfrage oben holt die Obermenge; hier faellt alles heraus, was
            # das Fenster nur nach hinten beruehrt.
            if not _ueberlappt_fenster(start, end, fenster_start, fenster_ende):
                continue

            # K-A (R-P1-8): Der Ablehnungsgrund geht nur an den Antragsteller
            # (owner) und an Moderatoren des Kalenders — nicht an jeden Leser.
            ablehnung_felder: dict[str, Any] = {}
            if _darf_ablehnung_sehen(
                str(_row_get(e, "owner") or ""), str(element_calendar or "")
            ):
                ablehnung_felder = {
                    "ablehnungs_grund": _row_get(e, "ablehnungs_grund") or "",
                    "moderiert_von": _row_get(e, "moderiert_von") or "",
                    "ist_antwortsteller": str(_row_get(e, "owner") or "") == str(session.user or ""),
                }

            color = (
                get_value("Kalender", element_calendar, "calendar_color")
                or element_color
                or "#3b82f6"
            )

            category_name = ""
            if element_category:
                try:
                    category_name = (
                        get_value(
                            "Eventkategorie", element_category, "event_category_name"
                        )
                        or element_category
                    )
                except Exception:  # noqa: BLE001 — keine Rechte -> Fallback auf ID
                    pass

            # Status-basiertes Styling: Vorschlag = gestrichelt, Konflikt = rot
            border_color = str(color)
            bg_color = str(color)
            if status == "Vorschlag":
                bg_color = str(color) + "99"  # leicht transparent
            elif status == "Konflikt":
                border_color = "#ef4444"
                bg_color = "#ef444433"

            formatted.append({
                "id": _row_get(e, "name"),
                "title": _row_get(e, "title") or "Termin",
                "start": str(start),
                "end": str(end) if end else None,
                "allDay": bool(_row_get(e, "all_day")),
                "backgroundColor": bg_color,
                "borderColor": border_color,
                "resourceId": ressource or "__unassigned__",
                "extendedProps": {
                    "name": _row_get(e, "name"),
                    "element_name": _row_get(e, "title"),
                    "element_calendar": element_calendar,
                    "element_category": element_category,
                    "event_category_name": category_name,
                    "element_start": str(start),
                    "element_end": str(end) if end else None,
                    "all_day": _row_get(e, "all_day"),
                    "status": status,
                    "element_color": color,
                    "ressource": ressource or None,
                    "ignore_conflict": bool(_row_get(e, "ignore_conflict")),
                    "description": _row_get(e, "description") or "",
                    "repeat_this_event": _row_get(e, "repeat_this_event"),
                    "series_id": _row_get(e, "series_id"),
                    "zusaetzliche_ressourcen": [],
                    "mitarbeiter": [],
                    # K-A (R-P1-8): Ablehnungsgrund nur fuer den Antragsteller
                    # und Moderatoren — nicht fuer jeden Kalenderleser.
                    **ablehnung_felder,
                },
            })

        # Zusatz-Ressourcen und Mitarbeiter je Event nachladen.
        event_names = [_row_get(e, "name") for e in events]
        if event_names:
            _attach_zusaetzliche_ressourcen(formatted, event_names)
            _attach_mitarbeiter(formatted, event_names)
        _attach_serien_anzahl(formatted, effective, bool(view_mode))

        return formatted
    except Exception as e:  # noqa: BLE001 — Original faengt und wirft fachlich
        if isinstance(e, FrappeCompatError):
            raise
        log_error(str(e), "get_calendar_events")
        throw("Fehler beim Laden der Termine")


def _darf_ablehnung_sehen(owner: str, kalender: str) -> bool:
    """Darf der aktuelle Nutzer Ablehnungsgrund/Moderator dieses Termins sehen?

    K-A (R-P1-8): Der Ablehnungsgrund ist eine Nachricht an den Antragsteller;
    Moderatoren sehen ihn ohnehin (Historie). Jeder andere Kalenderleser darf
    ihn NICHT bekommen — er nennt oft interne Gruende.
    """
    aktuell = str(session.user or "")
    if not aktuell or aktuell == "Guest":
        return False
    if owner and owner == aktuell:
        return True
    from diakronos_app.api.kronos.event_crud import _ist_moderator

    return bool(kalender) and _ist_moderator(kalender)


@whitelist(allow_guest=False)
def get_mein_termin(element_id):
    """Detailansicht EINES eigenen Termins — auch wenn er abgelehnt wurde (K-A).

    DER BEFUND (R-P1-8b, W-b)
    -------------------------
    `ablehnungs_grund` wird nur an Zeilen mit Status „Abgelehnt“ gesetzt, und
    abgelehnte Termine liefert `get_calendar_events` in KEINEM Modus mehr aus
    (W-A: Lesemodus nur „Festgelegt“, Moderator „nicht Abgelehnt“, Normalnutzer
    nur „Festgelegt“). Der Antragsteller konnte seinen abgelehnten Termin also
    nirgends oeffnen — die Anzeige im Frontend hatte keine Datenquelle. Der
    Grund erreichte ihn nur ueber die Benachrichtigung.

    Diese Ansicht ist eng: GENAU EIN Termin, den der Aufrufer selbst angelegt
    hat (`Element.owner`), oder ein Moderator des Kalenders. Abgelehnte Termine
    bleiben weiterhin aus ALLEN Listen heraus — hier wird ein einzelner,
    ausdruecklich angefragter Termin geliefert, kein Listenweg geoeffnet.
    """
    aktuell = str(session.user or "")
    if not aktuell or aktuell == "Guest":
        throw("Nicht angemeldet")

    felder = [
        "name", "element_name", "element_start", "element_end", "all_day",
        "element_calendar", "element_category", "status", "ressource",
        "description", "owner", "series_id", "ablehnungs_grund",
        "moderiert_von", "modified",
    ]
    doc = get_value("Element", element_id, felder, as_dict=True)
    if not doc:
        raise DoesNotExistError("Termin nicht gefunden.")

    owner = str(doc.get("owner") or "")
    kalender = str(doc.get("element_calendar") or "")
    # P1-8d (Pflicht e): NUR der Antragsteller oder ein Moderator dieses
    # Kalenders bekommt diesen Einzeltermin. VORHER genuegte ein Leserecht am
    # Kalender — damit lieferte der Endpunkt jedem Kalenderleser Titel, Zeit,
    # Beschreibung und Status fremder Termine (auch `Abgelehnt`/`Vorschlag`)
    # und umging so den Statusfilter der Listen.
    if owner != aktuell and not _darf_ablehnung_sehen(owner, kalender):
        from diakronos_app.frappe_compat.exceptions import (
            PermissionError as _PE,
        )

        throw(
            "Nur der Antragsteller oder ein Moderator dieses Kalenders darf "
            "diesen Termin einsehen.",
            _PE,
        )

    cal_info = get_value(
        "Kalender", kalender, ["calendar_name", "calendar_color"], as_dict=True
    ) or {}
    return {
        "name": doc.get("name"),
        "title": doc.get("element_name") or "Termin",
        "start": str(doc.get("element_start")),
        "end": str(doc.get("element_end")) if doc.get("element_end") else None,
        "all_day": bool(doc.get("all_day")),
        "calendar": kalender,
        "calendar_title": cal_info.get("calendar_name") or kalender,
        "calendar_color": cal_info.get("calendar_color") or "#3b82f6",
        "status": doc.get("status"),
        "ressource": doc.get("ressource") or "",
        "description": doc.get("description") or "",
        "series_id": doc.get("series_id") or "",
        "owner": owner,
        "ist_antwortsteller": owner == aktuell,
        # K-A: der Grund nur fuer den Antragsteller und Moderatoren.
        "ablehnungs_grund": (
            doc.get("ablehnungs_grund") or ""
            if _darf_ablehnung_sehen(owner, kalender)
            else ""
        ),
        "moderiert_von": (
            doc.get("moderiert_von") or ""
            if _darf_ablehnung_sehen(owner, kalender)
            else ""
        ),
    }


@whitelist(allow_guest=False)
def get_meine_abgelehnten_termine():
    """Die eigenen abgelehnten Termine des Antragstellers (K-A).

    Abgelehnte Termine bleiben aus ALLEN Listen heraus (W-A) — der Antragsteller
    hat aber ein Recht zu erfahren, was aus seinem Termin geworden ist. Diese
    Liste zeigt GENAU SEINE eigenen (`Element.owner`), damit die Detailansicht
    (`get_mein_termin`) erreichbar ist. Ein Moderator sieht hier nichts Fremdes;
    seine Moderation laeuft ueber das Moderationsboard.
    """
    aktuell = str(session.user or "")
    if not aktuell or aktuell == "Guest":
        throw("Nicht angemeldet")

    zeilen = get_all(
        "Element",
        filters={"owner": aktuell, "status": "Abgelehnt"},
        fields=[
            "name", "element_name", "element_start", "element_end", "all_day",
            "element_calendar", "ablehnungs_grund", "moderiert_von",
        ],
        order_by="element_start desc",
        limit_page_length=50,
    ) or []

    ergebnis = []
    for e in zeilen:
        kalender = str(_row_get(e, "element_calendar") or "")
        cal_info = get_value(
            "Kalender", kalender, ["calendar_name", "calendar_color"], as_dict=True
        ) or {}
        ergebnis.append({
            "id": _row_get(e, "name"),
            "title": _row_get(e, "element_name") or "Termin",
            "start": str(_row_get(e, "element_start")),
            "end": str(_row_get(e, "element_end")) if _row_get(e, "element_end") else None,
            "all_day": bool(_row_get(e, "all_day")),
            "calendar": kalender,
            "calendar_title": cal_info.get("calendar_name") or kalender,
            "calendar_color": cal_info.get("calendar_color") or "#3b82f6",
            "ablehnungs_grund": _row_get(e, "ablehnungs_grund") or "",
            "moderiert_von": _row_get(e, "moderiert_von") or "",
        })
    return ergebnis


def _attach_zusaetzliche_ressourcen(formatted: list[dict[str, Any]], event_names: list[str]) -> None:
    """Kind-Tabelle `Element Ressource` je Event anhaengen (Original: ein SQL)."""
    child_rows = get_all(
        "Element Ressource",
        filters={"parent": ["in", event_names]},
        fields=["parent", "ressource", "freitext_ressource", "status", "notiz"],
        order_by="idx asc",
    ) or []

    # Ressourcen-Namen aller referenzierten Katalogeintraege in einem Zug.
    ressource_ids = list({r["ressource"] for r in child_rows if r.get("ressource")})  # type: ignore[index]
    name_map: dict[str, str] = {}
    if ressource_ids:
        name_rows = get_all(
            "Ressource",
            filters={"name": ["in", ressource_ids]},
            fields=["name", "ressource_name"],
        ) or []
        name_map = {r["name"]: (r.get("ressource_name") or r["name"]) for r in name_rows}  # type: ignore[index]

    child_map: dict[str, list[dict[str, Any]]] = {}
    for cr in child_rows:
        rid = cr.get("ressource")  # type: ignore[union-attr]
        child_map.setdefault(cr["parent"], []).append({  # type: ignore[index]
            "ressource": rid or "",
            "ressource_name": name_map.get(rid, "") if rid else "",
            "freitext_ressource": cr.get("freitext_ressource") or "",  # type: ignore[union-attr]
            "status": cr.get("status") or "Angefragt",  # type: ignore[union-attr]
            "notiz": cr.get("notiz") or "",  # type: ignore[union-attr]
        })

    # Primaere Ressource je Event aufloesen (Original: eigene Query).
    primary_ids = list({
        p["extendedProps"].get("ressource")
        for p in formatted
        if p["extendedProps"].get("ressource")
    })
    primary_map: dict[str, str] = {}
    if primary_ids:
        primary_rows = get_all(
            "Ressource",
            filters={"name": ["in", primary_ids]},
            fields=["name", "ressource_name"],
        ) or []
        primary_map = {r["name"]: (r.get("ressource_name") or r["name"]) for r in primary_rows}  # type: ignore[index]

    for f_item in formatted:
        f_item["extendedProps"]["zusaetzliche_ressourcen"] = child_map.get(f_item["id"], [])
        rid = f_item["extendedProps"].get("ressource")
        if rid:
            f_item["extendedProps"]["ressource_name"] = primary_map.get(rid, rid)


def _attach_mitarbeiter(formatted: list[dict[str, Any]], event_names: list[str]) -> None:
    """Kind-Tabelle `Element Mitarbeiter` je Event anhaengen (Original: ein SQL)."""
    mitarbeiter_rows = get_all(
        "Element Mitarbeiter",
        filters={"parent": ["in", event_names]},
        fields=["parent", "mitglied", "dienstrolle", "bestaetigt", "notiz"],
        order_by="idx asc",
    ) or []

    # Mitarbeiter-Namen (Vorname Nachname) in einem Zug aufloesen.
    # AUSTRITT-b (B1): ueber `personen_anzeige.namen_map` — der Klarname einer
    # ausgetretenen Person stand hier sonst in jedem Kalendertermin.
    mitglied_ids = {mr["mitglied"] for mr in mitarbeiter_rows if mr.get("mitglied")}  # type: ignore[index]
    from diakronos_app.frappe_compat.personen_anzeige import namen_map

    mitglied_name_map = namen_map(sorted(mitglied_ids))

    mitarbeiter_map: dict[str, list[Any]] = {}
    for mr in mitarbeiter_rows:
        mitarbeiter_map.setdefault(mr["parent"], []).append(mr)  # type: ignore[index]

    for f_item in formatted:
        resolved = []
        for mr in mitarbeiter_map.get(f_item["id"], []):
            mitglied = mr.get("mitglied") or ""
            resolved.append({
                "mitglied": mitglied,
                # AUSTRITT-b (B1): nie die Kennung als Name (sie ist oft die
                # Adresse) — sonst ein neutraler Text.
                "mitglied_name": mitglied_name_map.get(mitglied) or (
                    "Ehemaliges Mitglied" if mitglied else ""),
                "dienstrolle": mr.get("dienstrolle") or "",
                "bestaetigt": int(mr.get("bestaetigt") or 0),
            })
        f_item["extendedProps"]["mitarbeiter"] = resolved


def _attach_serien_anzahl(
    formatted: list[dict[str, Any]],
    erlaubte_kalender: list[str],
    nur_festgelegt: bool,
) -> None:
    """Anzahl der Termine je Serie an die Termine haengen (UXK-R3).

    Die Rueckfrage vor dem Loeschen einer ganzen Serie soll die Folge in Zahlen
    nennen koennen ("4 Termine loeschen?"). Die Kalenderdaten enthalten die
    Seriengroesse nicht; sie wird in EINER Abfrage je vorkommender Serien-ID
    ermittelt.

    W5: Frueher lief je Serien-ID ein eigener `get_all`-Aufruf — bei einem
    Monat mit vielen Serienterminen also ein Dutzend Abfragen fuer Daten, die
    derselbe Termin-Bestand bereits mitbringt. Jetzt werden die Namen aller
    Serientermine in einem Zug geholt und in Python gezaehlt.

    K1 (Review P1-3): Gezaehlt wird nur, was der Nutzer auch SEHEN darf —
    dieselben Kalender- und Statusfilter wie die Terminliste. Vorher zaehlte
    die Abfrage auch Termine unlesbarer Kalender und Vorschlaege mit und
    verriet damit die Groesse fremder Serien (und zeigte eine Zahl, die der
    Nutzer im Kalender nicht nachvollziehen konnte).

    W-1/P1-8 (auf der P1-5c-Signatur): Die Zaehlung muss DENSELBEN Filter sehen
    wie die Terminliste — sonst nennt die Rueckfrage mehr Termine, als der
    Nutzer ueberhaupt sieht (und als geloescht werden). `nur_festgelegt` ist der
    Lesemodus (`view_mode`): dann zaehlen alle uebergebenen Kalender nur
    `Festgelegt`. Im Bearbeitungsmodus wird wie in der Terminliste je Kalender
    unterschieden: Moderatorkalender -> alles AUSSER `Abgelehnt`; uebrige
    Kalender -> nur `Festgelegt`.
    """
    serien_ids = sorted({
        str(p["extendedProps"].get("series_id"))
        for p in formatted
        if p["extendedProps"].get("series_id")
    })
    if not serien_ids or not erlaubte_kalender:
        return
    anzahl: dict[str, int] = {sid: 0 for sid in serien_ids}
    try:
        rows = _serien_termine(serien_ids, erlaubte_kalender, nur_festgelegt)
    except Exception as e:  # noqa: BLE001 — Zaehlung darf das Laden nicht sprengen
        log_error(str(e), "Serienanzahl ermitteln")
        return
    for row in rows:
        sid = _row_get(row, "series_id")
        if sid is not None and str(sid) in anzahl:
            anzahl[str(sid)] += 1
    for p in formatted:
        sid = p["extendedProps"].get("series_id")
        if sid and str(sid) in anzahl:
            p["extendedProps"]["series_count"] = anzahl[str(sid)]


def _serien_termine(
    serien_ids: list[str],
    erlaubte_kalender: list[str],
    nur_festgelegt: bool,
) -> list[Any]:
    """Die Element-Zeilen einer Serie unter dem Statusfilter der Liste (W-1).

    Lesemodus (`nur_festgelegt`): kalenderuebergreifend nur `Festgelegt`.
    Bearbeitungsmodus: dieselbe Aufteilung wie die Terminliste — Moderatoren
    sehen alles AUSSER `Abgelehnt`, die uebrigen Kalender nur `Festgelegt`.
    """
    basis = {"series_id": ["in", serien_ids]}
    if nur_festgelegt:
        return get_all(
            "Element",
            filters={**basis, "element_calendar": ["in", erlaubte_kalender],
                     "status": "Festgelegt"},
            fields=["name", "series_id"],
        ) or []

    # Bearbeitungsmodus: dieselbe Aufteilung wie die Terminliste.
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    cal_info = {
        cal["name"]: cal
        for cal in get_accessible_calendars()
        if isinstance(cal, dict) and "name" in cal
    }
    mod_cals = [n for n in erlaubte_kalender if cal_info.get(n, {}).get("is_moderator")]
    regular_cals = [n for n in erlaubte_kalender if not cal_info.get(n, {}).get("is_moderator")]

    rows: list[Any] = []
    if mod_cals:
        rows.extend(
            get_all(
                "Element",
                filters={**basis, "element_calendar": ["in", mod_cals],
                         "status": ["not in", ["Abgelehnt"]]},
                fields=["name", "series_id"],
            )
            or []
        )
    if regular_cals:
        rows.extend(
            get_all(
                "Element",
                filters={**basis, "element_calendar": ["in", regular_cals],
                         "status": "Festgelegt"},
                fields=["name", "series_id"],
            )
            or []
        )
    return rows


__all__ = ["get_calendar_events", "get_mein_termin", "get_meine_abgelehnten_termine"]


# ── Re-Export `get_accessible_calendars` (Original: `from .permissions import ...`) ──
#
# Die SPA ruft BEIDE Pfade:
#     diakronos.kronos.api.permissions.get_accessible_calendars
#     diakronos.kronos.api.calendar_get.get_accessible_calendars
# `get_accessible_calendars` funktioniert NUR ueber sein eigenes Modul, weil
# `registry._register` die Konstante aus `sys.modules[fn.__module__]` liest —
# ein blosses Wiederholen der Funktion in `calendar_get` wuerde einen zweiten
# Eintrag unter dem `permissions`-Pfad erzeugen, nicht unter `calendar_get`.
#
# Deshalb der Weg ueber die Registry-API: einmalige Zusatz-Registrierung mit
# explizitem Frappe-Modulnamen. Das ist derselbe Mechanismus (kein zweiter Weg),
# nur mit dem Modul als Parameter statt als Modulkonstante.
def _register_calendar_get_reexports() -> None:
    """Registriert die Original-Re-Exports dieses Moduls (idempotent)."""
    from diakronos_app.frappe_compat.registry import register_with_frappe_module

    register_with_frappe_module(
        FRAPPE_MODULE, "get_accessible_calendars", get_accessible_calendars
    )


_register_calendar_get_reexports()
