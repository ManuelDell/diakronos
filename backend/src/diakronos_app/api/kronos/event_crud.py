"""Portierung von `diakronos.kronos.api.event_crud` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/event_crud.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    create_event   update_event   delete_event   save_event   create_series

plus die im Original oeffentlichen Helfer:

    parse_iso_datetime_raw   _assert_write_access   _assert_read_access

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.new_doc("Element"); doc.save()   -> _create("Element", {...})
    frappe.get_doc("Element", name)         -> get_doc("Element", name)
    doc.feld = X; doc.save()                -> _update_doc("Element", name, {...})
    doc.append(parentfield, row)            -> _child_insert(...)
    doc.zusaetzliche_ressourcen = []        -> _child_delete(...)
    frappe.delete_doc("Element", name)      -> _delete_doc("Element", name)
    frappe.db.commit()                      -> entfaellt (die Helfer committen)
    frappe.generate_hash(length=12)         -> _generate_hash(12)
    frappe.flags.allow_series_edit          -> flags.allow_series_edit
    frappe.throw(...)                       -> throw(...)
    frappe.log_error(...)                   -> log_error(...)

Abweichung zur Vorlage (dokumentiert): Das Original laesst `doc.save()` die
Kind-Tabellen (`zusaetzliche_ressourcen`, `mitarbeiter`) implizit schreiben und
`_apply_*` ueberschreibt sie ueber `doc.<feld> = []`. Im Standalone-Backend ist
das Schreiben von Kind-Zeilen explizit (`_child_replace`), weil `Document` kein
`append` kennt. Die Normalisierungsregeln (leere Zeilen, Status-Whitelist,
`bestaetigt` als 0/1) sind 1:1 uebernommen.
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.event_crud"

import json as _json
from datetime import datetime as _datetime
from datetime import timedelta

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _child_delete,
    _child_insert,
    _create,
    _delete_doc,
    _generate_hash,
    _rethrow,
    _update_doc,
    flags,
    get_all,
    get_doc,
    log_error,
    session,
    throw,
)

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# P1-1b: die moderationspflichtigen Felder kommen aus der zentralen Regel
# (`moderation.py`), damit hier keine zweite, abweichende Liste entsteht.
from diakronos_app.api.kronos.moderation import (  # noqa: E402
    MODERATIONSPFLICHTIGE_FELDER as _MODERATIONSPFLICHTIGE_FELDER,
)


# ── Datum ───────────────────────────────────────────────────────────────────


def parse_iso_datetime_raw(iso_string):
    """Parse ISO-UTC-String – strikt validiert, kein blindes Durchleiten."""
    if not iso_string:
        return None

    try:
        iso_str = str(iso_string).strip()

        # Wenn bereits im Format "YYYY-MM-DD HH:MM[:SS]", strict validieren
        if " " in iso_str and "T" not in iso_str:
            # Sekunden optional: Flatpickr (Y-m-d H:i) liefert 'YYYY-MM-DD HH:MM'
            fmt = _DATETIME_FORMAT if len(iso_str) > 16 else "%Y-%m-%d %H:%M"
            _datetime.strptime(iso_str, fmt)  # wirft ValueError bei ungueltigem Wert
            return iso_str if len(iso_str) > 16 else iso_str + ":00"

        # Parse als ISO-8601 / UTC
        dt = dateutil_parser.isoparse(iso_str)
        # Offsetbehaftete API-Werte sind Zeitpunkte, naive Werte Ortszeit.
        # Gleicher Vertrag wie beim Kalenderimport (CALENDAR_TIMEZONE).
        if dt.tzinfo is not None:
            from zoneinfo import ZoneInfo
            from diakronos_app.settings import settings
            dt = dt.astimezone(ZoneInfo(settings.calendar_timezone))
        dt_naive = dt.replace(tzinfo=None)
        return dt_naive.strftime(_DATETIME_FORMAT)

    except Exception as e:  # noqa: BLE001 — Original faengt alles und wirft fachlich
        log_error(f"Fehler: {e}", "parse_iso_datetime_raw ERROR")
        throw(f"Ungültiges Datum: {iso_string}")


# ── Berechtigungen ──────────────────────────────────────────────────────────


def _assert_write_access(calendar_name):
    """Wirft PermissionError, wenn der User kein Schreibrecht auf den Kalender hat."""
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    calendars = get_accessible_calendars()
    writable = {c["name"] for c in calendars if c.get("write")}
    if calendar_name not in writable:
        throw(
            f"Kein Schreibzugriff auf Kalender: {calendar_name}",
            FrappePermissionError,
        )


def _assert_read_access(calendar_name):
    """Wirft PermissionError, wenn der User kein Leserecht auf den Kalender hat."""
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    calendars = get_accessible_calendars()
    readable = {c["name"] for c in calendars}
    if calendar_name not in readable:
        throw(
            f"Kein Lesezugriff auf Kalender: {calendar_name}",
            FrappePermissionError,
        )


def _erzwungener_status(status, ist_moderator: bool) -> str:
    """Freigabe nur fuer Moderatoren — sonst immer "Vorschlag".

    Ohne diese Schranke konnte jeder mit Schreibrecht den Moderationsworkflow
    umgehen, indem er einfach `status="Festgelegt"` uebergibt (der Server
    nahm den Wert ungeprueft an). Nicht-Moderatoren landen damit wieder im
    Vorschlag-Workflow, genau wie es `create_event` dokumentiert.

    Auch ein Moderator bekommt ohne ausdrueckliche Statusangabe "Vorschlag"
    (BF1-A: ein neuer Termin ist erst nach der Freigabe sichtbar) — die
    Moderation ist ein bewusster Schritt, kein Nebeneffekt der Rolle.
    """
    if status:
        return status if ist_moderator else "Vorschlag"
    return "Vorschlag"


# Laenge des Feldtyps `element.element_name` (siehe models/kronos.py).
_MAX_TITEL_LAENGE = 140


# Operator-Regel 16.10. (P1-1): Die Feldlisten und der Vergleich liegen in
# `moderation.py` — EINE Quelle fuer ALLE Schreibwege (save_event, update_event,
# Serien, Drag&Drop, Ressourcen-/Mitarbeiter-Zuordnung, Kanban). P1-1b (Review
# Review-Befund zu B1/B2) hat sie dorthin gezogen, weil verstreute Einzelpruefungen
# genau die Luecken erzeugt haben, die das Review gefunden hat.
def _ist_moderator(calendar_name) -> bool:
    """Moderiert der aktuelle Nutzer diesen Kalender? (Delegation, s. moderation)."""
    from diakronos_app.api.kronos.moderation import ist_moderator

    return ist_moderator(calendar_name)


def _normalisiere_datum(wert) -> str | None:
    """Datums-/Zeitwert auf die Vergleichsform `YYYY-MM-DD HH:MM:SS` bringen."""
    if wert is None:
        return None
    if isinstance(wert, _datetime):
        return wert.strftime(_DATETIME_FORMAT)
    text = str(wert).strip()
    if not text:
        return None
    try:
        return parse_iso_datetime_raw(text)
    except Exception:  # noqa: BLE001 — unparsbarer Wert bleibt Wort fuer Wort
        return text


def _wert_fuer_vergleich(feld: str, wert):
    """Wert fuer den alt/neu-Vergleich normalisieren (Delegation, s. moderation)."""
    from diakronos_app.api.kronos.moderation import _wert_fuer_vergleich as _impl

    return _impl(feld, wert)


def _hat_materielle_aenderung(doc, werte: dict[str, object]) -> bool:
    """Aendert `werte` einen moderationspflichtigen Punkt gegenueber `doc`?"""
    from diakronos_app.api.kronos.moderation import _hat_materielle_aenderung as _impl

    return _impl(doc, werte)


def _naechster_name(prefix: str) -> str:
    """Eindeutigen Zeilennamen bilden (`_generate_hash` reicht als Suffix)."""
    return f"{prefix}-{_generate_hash(12)}"


def _speichere_aenderungsvorschlag(
    element_name: str,
    element_calendar: str,
    antragsteller: str,
    vorschlag: dict[str, object],
    kind_tabellen: dict[str, object] | None = None,
) -> str:
    """Offenen Aenderungsvorschlag ablegen (Delegation, s. moderation).

    Nur die moderationspflichtigen Felder wandern in den Vorschlag (Befund W2),
    Ressourcen als Kind-Tabelle (Befund W1).
    """
    from diakronos_app.api.kronos import moderation

    return moderation.speichere_aenderungsvorschlag(
        element_name, element_calendar, antragsteller, vorschlag, kind_tabellen
    )


def _aenderungen_zu_element_entfernen(element_name: str) -> int:
    """Offene Aenderungsvorschlaege eines Termins loeschen (s. moderation)."""
    from diakronos_app.api.kronos import moderation

    return moderation.aenderungen_zu_element_entfernen(element_name)


def _pruefe_titel(element_name) -> str:
    """Titel auf die Feldlaenge begrenzen — Klartextfehler statt SQL-Text.

    UXK-009: Ein Titel ueber 140 Zeichen lief bisher in den Datenbankfehler
    (`StringDataRightTruncation`); der rohe Treibertext samt Spaltenliste ging
    an den Client. Diese Vorabpruefung meldet die Grenze verstaendlich, bevor
    die DB ueberhaupt gefragt wird.
    """
    name = "" if element_name is None else str(element_name)
    if len(name) > _MAX_TITEL_LAENGE:
        throw(
            f"Der Titel ist zu lang ({len(name)} Zeichen). "
            f"Erlaubt sind höchstens {_MAX_TITEL_LAENGE} Zeichen."
        )
    return name


# ── Kind-Tabellen normalisieren ─────────────────────────────────────────────


def _gespeicherte_ressourcen_status(element_name: str) -> dict[tuple[str, str], str]:
    """Status der bereits gespeicherten Termin-Ressourcen (je Ressource + Zeitraum).

    P1-4b (B2): Der Vergleichsstand fuer `_normalize_ressourcen`. Schluessel ist
    das Paar `(ressource, freitext_ressource)` — die Termin-Ressource hat keine
    eigene Periode; „Zeitraum“ ist der Zeitraum des Termins, also ist der
    Termin (`element_name`) selbst der Bezug. Leerer Terminname liefert {}.
    """
    if not element_name:
        return {}
    zeilen = get_all(
        "Element Ressource",
        filters={"parent": element_name, "parentfield": "zusaetzliche_ressourcen"},
        fields=["ressource", "freitext_ressource", "status"],
    ) or []
    stand: dict[tuple[str, str], str] = {}
    for z in zeilen:
        if not isinstance(z, dict):
            continue
        schluessel = (
            (z.get("ressource") or "").strip(),
            (z.get("freitext_ressource") or "").strip(),
        )
        stand[schluessel] = (z.get("status") or "").strip()
    return stand


def _normalize_ressourcen(
    zusaetzliche_ressourcen,
    element_name: str = "",
    gespeichert: dict[tuple[str, str], str] | None = None,
) -> list[dict[str, object]]:
    """`_apply_additional_resources` — Zeilen normalisieren (ohne Doc-Schreiben).

    OP-EVENT-10: Ein Status „Bestätigt“ auf einer Termin-Ressource ist eine
    Ressourcen-Moderation, kein Feld des Termin-Formulars. Ohne diese Schranke
    konnte jeder mit Kalenderschreibrecht den Beamer am eigenen Termin
    selbst bestätigen und damit die Ressourcen-Moderation umgehen — für Dritte
    unsichtbar und ohne Konfliktprüfung. Nur ein Ressourcenmoderator darf
    bestätigen; für alle anderen wird die Zeile zur Anfrage („Angefragt“),
    die in der Ressourcen-Moderation sichtbar ist.

    P1-4b (B2): Die Schranke gilt nur fuer NEUE oder geaenderte Zuordnungen.
    Bereits gespeicherte Zeilen behalten ihren Status: der Bearbeiten-Dialog
    schickt die geladenen Zeilen samt „Bestätigt“ zurueck, und ein Nutzer ohne
    Ressourcenmoderator-Rolle (z. B. ein reiner Kalendermoderator, der nur den
    Titel aendert) stufte sie damit still auf „Angefragt“ zurueck. Verglichen
    wird je Schluessel `(ressource, freitext_ressource)` mit dem DB-Stand:
    steht dort „Bestätigt“, bleibt es „Bestätigt“.
    """
    if not zusaetzliche_ressourcen:
        return []
    if isinstance(zusaetzliche_ressourcen, str):
        try:
            zusaetzliche_ressourcen = _json.loads(zusaetzliche_ressourcen)
        except Exception:  # noqa: BLE001 — Original faellt auf [] zurueck
            zusaetzliche_ressourcen = []
    if not isinstance(zusaetzliche_ressourcen, list):
        return []

    from diakronos_app.api.ressourcen import _is_ressourcenmoderator

    darf_bestaetigen = _is_ressourcenmoderator()
    if gespeichert is None:
        gespeichert = _gespeicherte_ressourcen_status(element_name)

    valid: list[dict[str, object]] = []
    for row in zusaetzliche_ressourcen:
        if not isinstance(row, dict):
            continue
        ressource = (row.get("ressource") or "").strip()
        freitext = (row.get("freitext_ressource") or "").strip()
        # Leere Zeilen (weder Katalog noch Freitext) ueberspringen
        if not ressource and not freitext:
            continue
        status = (row.get("status") or "Angefragt").strip()
        if status not in ("Angefragt", "Bestätigt"):
            status = "Angefragt"
        if status == "Bestätigt" and not darf_bestaetigen:
            # B2: schon bestaetigt gespeichert -> Status nicht zurueckstufen.
            # Nur eine NEUE Zeile (kein DB-Eintrag fuer diesen Schluessel) wird
            # zur Anfrage; der Ressourcenmoderator bleibt die Instanz.
            if gespeichert.get((ressource, freitext)) == "Bestätigt":
                status = "Bestätigt"
            else:
                status = "Angefragt"
        valid.append({
            "ressource": ressource,
            "freitext_ressource": freitext,
            "status": status,
            "notiz": (row.get("notiz") or "").strip(),
        })
    return valid


def _normalize_mitarbeiter(mitarbeiter) -> list[dict[str, object]]:
    """`_apply_mitarbeiter` — Zeilen normalisieren (ohne Doc-Schreiben)."""
    if not mitarbeiter:
        return []
    if isinstance(mitarbeiter, str):
        try:
            mitarbeiter = _json.loads(mitarbeiter)
        except Exception:  # noqa: BLE001
            mitarbeiter = []
    if not isinstance(mitarbeiter, list):
        return []

    valid: list[dict[str, object]] = []
    for row in mitarbeiter:
        if not isinstance(row, dict):
            continue
        mitglied = (row.get("mitglied") or "").strip()
        dienstrolle = (row.get("dienstrolle") or "").strip()
        notiz = (row.get("notiz") or "").strip()
        # Leere Zeilen (kein Mitglied und keine Dienstrolle) ueberspringen
        if not mitglied and not dienstrolle:
            continue
        valid.append({
            "mitglied": mitglied,
            "dienstrolle": dienstrolle,
            "bestaetigt": 1 if row.get("bestaetigt") else 0,
            "notiz": notiz,
        })
    return valid


def _apply_additional_resources(name: str, zusaetzliche_ressourcen) -> None:
    """Kind-Tabelle `zusaetzliche_ressourcen` eines Events setzen (ersetzt alles)."""
    # P1-4b (B2): den gespeicherten Stand VOR dem Loeschen lesen — sonst sieht
    # `_normalize_ressourcen` nur die leere Tabelle und stufte jede bestaetigte
    # Zuordnung auf „Angefragt“ zurueck.
    gespeichert = _gespeicherte_ressourcen_status(name)
    _child_delete("Element Ressource", name, "zusaetzliche_ressourcen")
    for row in _normalize_ressourcen(zusaetzliche_ressourcen, name, gespeichert):
        _child_insert("Element Ressource", name, "zusaetzliche_ressourcen", dict(row))


def _apply_mitarbeiter(name: str, mitarbeiter) -> None:
    """Kind-Tabelle `mitarbeiter` eines Events setzen (ersetzt alles)."""
    _child_delete("Element Mitarbeiter", name, "mitarbeiter")
    for row in _normalize_mitarbeiter(mitarbeiter):
        _child_insert("Element Mitarbeiter", name, "mitarbeiter", dict(row))


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def create_event(
    element_name,
    element_start,
    element_end,
    element_calendar,
    all_day=False,
    description=None,
    status=None,
    element_category=None,
    ressource=None,
    ignore_conflict=False,
    zusaetzliche_ressourcen=None,
    mitarbeiter=None,
):
    """Erstelle neues Event – Standard-Status: Vorschlag.

    `status="Festgelegt"` wirkt nur fuer Moderatoren; fuer alle anderen wird
    serverseitig auf "Vorschlag" gezwungen (P0-3 Befund 1: die Freigabe ist
    eine Moderationshandlung, kein Schreibrecht).
    """
    try:
        _assert_write_access(element_calendar)
        element_name = _pruefe_titel(element_name)
        start_dt = parse_iso_datetime_raw(element_start)
        end_dt = parse_iso_datetime_raw(element_end) if element_end else start_dt

        gesetzt = _erzwungener_status(status, _ist_moderator(element_calendar))

        name = _create("Element", {
            "element_name": element_name,
            "element_calendar": element_calendar,
            "element_start": start_dt,
            "element_end": end_dt,
            "all_day": int(all_day) if all_day else 0,
            "status": gesetzt,
            "description": description or "",
            "element_category": element_category or "",
            "ressource": ressource or "",
            "ignore_conflict": int(ignore_conflict) if ignore_conflict else 0,
        })

        _apply_additional_resources(name, zusaetzliche_ressourcen)
        _apply_mitarbeiter(name, mitarbeiter)

        # BF1-A: Der angelegte Status gehoert in die Antwort. Ein neuer Termin
        # ist „Vorschlag“ und damit im Lesemodus unsichtbar — die SPA muss das
        # ehrlich melden und auf die Terminmoderation verweisen koennen, statt
        # einen Erfolg ohne sichtbare Wirkung zu zeigen.
        return {"success": True, "id": name, "status": gesetzt}

    except Exception as e:  # noqa: BLE001 — Original faengt alles und wirft weiter
        _rethrow(e, "create_event ERROR")


@whitelist(allow_guest=False)
def update_event(
    name,
    element_name=None,
    element_start=None,
    element_end=None,
    element_calendar=None,
    all_day=None,
    description=None,
    status=None,
    element_category=None,
    ressource=None,
    zusaetzliche_ressourcen=None,
    mitarbeiter=None,
):
    """Update existierendes Event.

    BEFUND P1-1b (B1): Dieser Endpunkt ist whitelisted und von aussen
    aufrufbar; er umging die Moderationsregel vollstaendig (Datum, Uhrzeit,
    Kalender, Ganztag sofort; zusaetzlich konnte ein Nicht-Moderator per
    ``status="Vorschlag"`` einen festgelegten Termin zurueckstufen und damit
    aus dem Kalender entfernen). Er laeuft jetzt ueber dieselbe zentrale
    Pruef-/Aufteilfunktion wie `save_event`.
    """
    try:
        if not name or name in ["undefined", "null", ""]:
            throw(f"Invalid ID: {name}")

        doc = get_doc("Element", name)
        current_calendar = doc.get("element_calendar")
        _assert_write_access(current_calendar)

        values: dict[str, object] = {}

        if element_name is not None:
            values["element_name"] = _pruefe_titel(element_name)

        if element_start is not None:
            values["element_start"] = parse_iso_datetime_raw(element_start)

        if element_end is not None:
            values["element_end"] = parse_iso_datetime_raw(element_end)
        elif element_start is not None:
            # Original: Enddatum folgt dem neuen Startdatum
            values["element_end"] = values["element_start"]

        if element_calendar is not None:
            _assert_write_access(element_calendar)
            values["element_calendar"] = element_calendar

        if all_day is not None:
            values["all_day"] = all_day

        if description is not None:
            values["description"] = description

        if element_category is not None:
            values["element_category"] = element_category

        if ressource is not None:
            values["ressource"] = ressource or ""

        ist_mod = _ist_moderator(current_calendar)
        # P1-5c (7): Kalenderwechsel nur mit Moderationsrecht am Zielkalender
        # (wie die Freigabe) — sonst wartet er als Vorschlag.
        from diakronos_app.api.kronos import moderation

        if not moderation.kalenderwechsel_wirkt_sofort(
            current_calendar, element_calendar, ist_mod
        ):
            ist_mod = False
        kind_tabellen: dict[str, object] = {}
        if zusaetzliche_ressourcen is not None:
            kind_tabellen["zusaetzliche_ressourcen"] = zusaetzliche_ressourcen
        if mitarbeiter is not None:
            kind_tabellen["mitarbeiter"] = mitarbeiter

        # Statuswechsel ist Moderationssache (P0-3 Befund 1): ohne
        # Moderationsrecht wird er verworfen — auch "Vorschlag", das waere die
        # Rueckstufung (Befund B1).
        if status is not None and ist_mod:
            values["status"] = status

        from diakronos_app.api.kronos import moderation

        ergebnis = moderation.wende_termin_aenderung_an(
            doc,
            values,
            ist_mod,
            kind_tabellen=kind_tabellen or None,
        )

        antwort: dict[str, object] = {"success": True, "id": name}
        if ergebnis.aenderung_wartet:
            antwort["aenderung_wartet"] = True
            antwort["meldung"] = ergebnis.meldung
        return antwort

    except Exception as e:  # noqa: BLE001
        _rethrow(e, f"update_event ERROR: {name}")


@whitelist(allow_guest=False)
def delete_event(name):
    """Loesche Event (raeumt offene Aenderungsvorschlaege mit ab)."""
    try:
        if not name or name in ["undefined", "null", ""]:
            throw(f"Invalid ID: {name}")

        doc = get_doc("Element", name)
        _assert_write_access(doc.get("element_calendar"))

        from diakronos_app.api.kronos import benachrichtigung

        empfaenger = set()
        if doc.get("status") == "Festgelegt":
            try:
                empfaenger = benachrichtigung.empfaenger_der_mitarbeiter(name)
            except Exception as ex:  # noqa: BLE001 — Meldung ist Beiwerk
                log_error(str(ex), f"absage_empfaenger {name}")

        # Befund W3: ohne Aufraeumen bleibt ein offener Vorschlag als Waise
        # stehen (die Freigabe liefe dann in "Termin nicht gefunden").
        _aenderungen_zu_element_entfernen(name)

        _delete_doc("Element", name)
        if empfaenger:
            try:
                benachrichtigung.benachrichtige_absage(
                    name, str(doc.get("element_name") or ""), empfaenger,
                )
            except Exception as ex:  # noqa: BLE001 — Meldung ist Beiwerk
                log_error(str(ex), f"termin_absage {name}")

        return {"success": True}

    except Exception as e:  # noqa: BLE001
        _rethrow(e, f"delete_event ERROR: {name}")


@whitelist(allow_guest=False)
def save_event(
    name,
    element_name,
    element_start,
    element_end,
    element_calendar,
    all_day=0,
    description=None,
    status=None,
    element_category=None,
    series_id=None,
    ressource=None,
    ignore_conflict=None,
    zusaetzliche_ressourcen=None,
    mitarbeiter=None,
):
    """Volles Ueberschreiben eines Events – kein Diff, alle Felder werden gesetzt."""
    try:
        if not name or name in ["undefined", "null", ""]:
            throw(f"Invalid ID: {name}")

        doc = get_doc("Element", name)
        current_calendar = doc.get("element_calendar")
        _assert_write_access(current_calendar)

        # Leeres element_calendar bedeutet: Kalender unveraendert lassen
        if not element_calendar or element_calendar in ("undefined", "null"):
            element_calendar = current_calendar
        elif element_calendar != current_calendar:
            _assert_write_access(element_calendar)

        zeitpunkt_start = parse_iso_datetime_raw(element_start)
        zeitpunkt_end = parse_iso_datetime_raw(element_end)
        element_name = _pruefe_titel(element_name)
        # P0-3 Befund 1: Der Default "Festgelegt" war die Umgehung selbst —
        # `save_event` ohne Status hat jeden Vorschlag freigegeben. Ohne
        # ausdrueckliche Statusangabe bleibt der bisherige Status erhalten
        # (auch fuer Moderatoren: reines Bearbeiten ist keine Freigabe). Ein
        # Nicht-Moderator kann "Festgelegt" auch ausdruecklich nicht setzen.
        bisheriger = doc.get("status") or "Vorschlag"
        # N1: Das Moderationsrecht gilt fuer den KALENDER DES TERMINS (Quelle),
        # nicht fuer einen moeglichen Zielkalender. Mit dem Zielkalender konnte
        # ein Nur-Schreiber im Quellkalender einen festgelegten Termin durch
        # einen Kalenderwechsel sofort in einen Kalender verschieben, den er
        # moderiert — der Vorgang umging die Moderation des Quellkalenders.
        ist_moderator = _ist_moderator(current_calendar)
        # P1-5c (7): Ein Kalenderwechsel ist eine Freigabehandlung und verlangt
        # deshalb — wie die Freigabe eines Vorschlags — das Moderationsrecht am
        # ZIELKALENDER. Fehlt es, wirkt der Wechsel nicht sofort, sondern wird
        # als Vorschlag abgelegt (die Aufteilung unten erledigt das, wenn wir
        # hier `ist_moderator` auf False setzen).
        from diakronos_app.api.kronos import moderation

        if not moderation.kalenderwechsel_wirkt_sofort(
            current_calendar, element_calendar, ist_moderator
        ):
            ist_moderator = False
        if status is None:
            # Reines Bearbeiten ist keine Statusentscheidung: der bisherige
            # Status bleibt — auch fuer Nicht-Moderatoren (der Termin bleibt
            # "Festgelegt", die Aenderung wartet ggf. als Vorschlag).
            status = bisheriger
        elif status == "Festgelegt" and not ist_moderator:
            # Ein ausdrueckliches "Festgelegt" darf nur ein Moderator setzen;
            # ohne Moderationsrecht faellt der Termin auf seinen bisherigen
            # Status zurueck (nicht auf "Vorschlag" — das waere die
            # Rueckstufung, die den Termin aus dem Kalender entfernt).
            status = bisheriger

        values: dict[str, object] = {
            "element_name": element_name,
            "element_calendar": element_calendar,
            "element_start": zeitpunkt_start,
            "element_end": zeitpunkt_end,
            "all_day": int(all_day) if all_day else 0,
            "description": description or "",
            "status": status,
            "element_category": element_category or "",
            "series_id": series_id or "",
        }
        if ressource is not None:
            values["ressource"] = ressource or ""
        if ignore_conflict is not None:
            values["ignore_conflict"] = int(ignore_conflict)

        # Operator-Regel 16.10. (P1-1): Aendert ein Nicht-Moderator einen
        # FESTGELEGTEN Termin an Datum, Uhrzeit, Ort/Ressource, Kalender oder
        # Ganztags-Kennzeichen, wirkt das nicht sofort — der Termin bleibt in
        # der alten Fassung sichtbar, die Aenderung wartet als Vorschlag auf
        # die Freigabe. Kleinigkeiten (Titel, Beschreibung, Kategorie) werden
        # P1-1b: die Aufteilung macht `moderation.py` —
        # inklusive der zusaetzlichen Ressourcen (Befund W1), die vorher im
        # Vorschlagszweig sofort geschrieben wurden.
        from diakronos_app.api.kronos import moderation

        # UXK-R4 / N2 (Datenverlust): Kind-Tabellen werden nur noch geaendert,
        # wenn der Aufrufer das Feld AUSDRUECKLICH gesendet hat. `None` heisst
        # „keine Angabe" — frueher loeschte das die Mitarbeiter bzw. die
        # zusaetzlichen Ressourcen eines Termins (auch beim Verschieben per
        # Drag&Drop, das beide Felder nicht mitschickt). Eine ausdruecklich
        # gesendete LEERE Liste leert die Tabelle weiterhin.
        kind_tabellen: dict[str, object] = {}
        if zusaetzliche_ressourcen is not None:
            kind_tabellen["zusaetzliche_ressourcen"] = zusaetzliche_ressourcen
        if mitarbeiter is not None:
            kind_tabellen["mitarbeiter"] = mitarbeiter

        ergebnis = moderation.wende_termin_aenderung_an(
            doc,
            values,
            ist_moderator,
            kind_tabellen=kind_tabellen,
        )
        # Steuerfelder sind keine moderationspflichtigen Terminfelder:
        # sie werden auch im Vorschlagszweig sofort gesetzt.
        nachzuegler: dict[str, object] = {}
        if ignore_conflict is not None:
            nachzuegler["ignore_conflict"] = values["ignore_conflict"]
        if series_id:
            nachzuegler["series_id"] = values["series_id"]
        if nachzuegler:
            flags.allow_series_edit = True
            _update_doc("Element", name, nachzuegler)

        antwort: dict[str, object] = {"success": True, "id": name}
        if ergebnis.aenderung_wartet:
            antwort["aenderung_wartet"] = True
            antwort["meldung"] = ergebnis.meldung
        return antwort

    except Exception as e:  # noqa: BLE001
        _rethrow(e, f"save_event ERROR: {name}")


@whitelist(allow_guest=False)
def create_series(
    element_name,
    element_start,
    element_end,
    element_calendar,
    repeat_type="weekly",
    series_end=None,
    all_day=False,
    description=None,
    status=None,
    element_category=None,
    ressource=None,
    ignore_conflict=False,
    zusaetzliche_ressourcen=None,
    mitarbeiter=None,
):
    """Erstelle eine Serie wiederkehrender Termine.

    Der Status folgt derselben Regel wie bei Einzelterminen: "Festgelegt" nur
    fuer Moderatoren, sonst "Vorschlag" (P0-3 Befund 1) — sonst waere die
    Serienanlage das Hintertuerchen am Einzeltermin vorbei.
    """
    try:
        _assert_write_access(element_calendar)
        element_name = _pruefe_titel(element_name)
        gesetzt = _erzwungener_status(status, _ist_moderator(element_calendar))

        start_str = parse_iso_datetime_raw(element_start)
        end_str = parse_iso_datetime_raw(element_end) if element_end else start_str

        start_dt = _datetime.strptime(str(start_str), "%Y-%m-%d %H:%M:%S")
        end_dt = _datetime.strptime(str(end_str), "%Y-%m-%d %H:%M:%S")
        duration = end_dt - start_dt

        if series_end:
            series_end_dt = _datetime.strptime(series_end[:10], "%Y-%m-%d")
        else:
            series_end_dt = None  # Nur max_events begrenzt

        series_id = _generate_hash(12)
        created = 0
        created_ids: list[str] = []
        max_events = 100  # Maximale Terminanzahl

        # UXK-R7: Jeder Termin wird aus dem STARTDATUM berechnet
        # (`start_dt + n * Schrittweite`), nicht schrittweise fortgeschrieben.
        # Das schrittweise Addieren (`current = advance(current)`) liess eine
        # Monatsserie auf den 28. driften: der 31.01. + relativedelta(months=1)
        # ist der 28.02., und der naechste Schritt rechnete vom 28. weiter
        # (28.03., 28.04., ...). Vom Startdatum aus bleiben 31.01., 28.02.,
        # 31.03., 30.04., 31.05. erhalten — relativedelta saettigt jeden Monat
        # nur so weit wie noetig.
        def termin_nummer(n: int) -> _datetime:
            if n == 0:
                return start_dt
            if repeat_type == "daily":
                return start_dt + timedelta(days=n)
            if repeat_type == "monthly":
                return start_dt + relativedelta(months=n)
            if repeat_type == "yearly":
                return start_dt + relativedelta(years=n)
            return start_dt + timedelta(weeks=n)

        n = 0
        current = termin_nummer(n)
        while created < max_events and (series_end_dt is None or current.date() <= series_end_dt.date()):
            name = _create("Element", {
                "element_name": element_name,
                "element_calendar": element_calendar,
                "element_start": current.strftime(_DATETIME_FORMAT),
                "element_end": (current + duration).strftime(_DATETIME_FORMAT),
                "all_day": int(all_day) if all_day else 0,
                "status": gesetzt,
                "description": description or "",
                "element_category": element_category or "",
                "ressource": ressource or "",
                "ignore_conflict": int(ignore_conflict) if ignore_conflict else 0,
                "series_id": series_id,
                "repeat_this_event": 1,
            })

            _apply_additional_resources(name, zusaetzliche_ressourcen)
            _apply_mitarbeiter(name, mitarbeiter)

            created_ids.append(name)
            created += 1
            n += 1
            current = termin_nummer(n)

        return {
            "success": True,
            "series_id": series_id,
            "created_count": created,
            "created_ids": created_ids,
        }

    except Exception as e:  # noqa: BLE001
        _rethrow(e, "create_series ERROR")


# ── Termindaenderungen aus der Moderation (Operator-Regel 16.10., P1-1) ──────


def _lade_offene_aenderungen(calendar_names: list[str]) -> list[dict[str, object]]:
    """Alle offenen Aenderungsvorschlaege der uebergebenen Kalender (alt/neu).

    Liefert je Zeile die aktuelle (alte) Fassung des Termins und die
    vorgeschlagene (neue) Fassung, damit die Oberflaeche beides vergleichen
    kann. Nur Moderatoren des jeweiligen Kalenders duerfen das sehen — die
    Pruefung macht der Aufrufer (`get_offene_aenderungen`).
    """
    if not calendar_names:
        return []
    rows = get_all(
        "Element Aenderung",
        filters={"element_calendar": ["in", calendar_names]},
        fields=["name", "element", "element_calendar", "antragsteller", "vorschlag"],
        order_by="creation asc",
    ) or []
    ergebnis: list[dict[str, object]] = []
    for row in rows:
        element_name = row.get("element") if isinstance(row, dict) else None
        if not element_name:
            continue
        try:
            doc = get_doc("Element", str(element_name))
        except Exception:  # noqa: BLE001 — Termin geloescht -> Vorschlag verwaist
            continue
        try:
            neu = _json.loads(row.get("vorschlag") or "{}")
        except Exception:  # noqa: BLE001
            neu = {}
        # P1-1b (Befund W2): der Vorschlag traegt nur noch die
        # moderationspflichtigen Felder. "geaenderte_felder" nennt genau die,
        # die die Freigabe anwenden wuerde — die Oberflaeche zeigt damit ehrlich,
        # was sich aendert (und nicht den ganzen Feldstand).
        geaendert = [
            feld for feld in _MODERATIONSPFLICHTIGE_FELDER
            if feld in neu
            and _wert_fuer_vergleich(feld, neu.get(feld))
            != _wert_fuer_vergleich(feld, doc.get(feld))
        ]
        ergebnis.append({
            "name": row.get("name"),
            "element": element_name,
            "element_calendar": row.get("element_calendar"),
            "antragsteller": row.get("antragsteller"),
            "geaenderte_felder": geaendert,
            "alt": {
                "element_name": doc.get("element_name"),
                "element_start": _wert_fuer_vergleich("element_start", doc.get("element_start")),
                "element_end": _wert_fuer_vergleich("element_end", doc.get("element_end")),
                "ressource": doc.get("ressource") or "",
                "element_calendar": doc.get("element_calendar"),
                "all_day": _wert_fuer_vergleich("all_day", doc.get("all_day")),
            },
            "neu": {
                "element_name": neu.get("element_name", doc.get("element_name")),
                "element_start": _wert_fuer_vergleich("element_start", neu.get("element_start")),
                "element_end": _wert_fuer_vergleich("element_end", neu.get("element_end")),
                "ressource": neu.get("ressource") or "",
                "element_calendar": neu.get("element_calendar", doc.get("element_calendar")),
                "all_day": _wert_fuer_vergleich("all_day", neu.get("all_day")),
            },
        })
    return ergebnis


@whitelist(allow_guest=False)
def get_offene_aenderungen():
    """Offene Termindaenderungen der Kalender, die der Nutzer moderiert."""
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    mod_cals = [
        c["name"] for c in get_accessible_calendars() if c.get("is_moderator")
    ]
    return _lade_offene_aenderungen(mod_cals)


@whitelist(allow_guest=False)
def aenderung_freigeben(name, nur_pruefen=0):
    """Vorgeschlagene Termindaenderung uebernehmen (nur Moderatoren).

    Befund W2: angewandt werden NUR die im Vorschlag stehenden
    moderationspflichtigen Felder (plus hinterlegte zusaetzliche Ressourcen).
    Titel/Beschreibung/Kategorie bleiben unberuehrt — sonst ueberschriebe die
    Freigabe zwischenzeitliche Sofortaenderungen mit dem Stand von der
    Einreichung des Vorschlags.

    P1-2-Rest (K1): `nur_pruefen=1` prueft die Belegung, OHNE freizugeben. Die
    Oberflaeche fragt damit VOR der Freigabe nach — vorher wurde der Vorschlag
    angewandt und die Warnung kam zu spaet („Freigabe nur nach Bestaetigung“).
    """
    try:
        from diakronos_app.api.kronos import moderation

        doc = moderation.pruefe_moderationsrecht(name)
        neu, ziel = moderation.vorschlag_lesen(doc)
        if not ziel:
            throw("Vorschlag ohne Termin")
            return {"success": False}  # pragma: no cover — throw wirft immer
        element_name: str = ziel
        get_doc("Element", element_name)  # Existenzpruefung (klare Meldung)
        # K1: Belegung erneut pruefen — die Freigabe konnte sonst denselben
        # Raum doppelt vergeben. Die Freigabe bleibt moeglich (der Moderator
        # entscheidet), die Antwort nennt aber die Ueberschneidungen.
        konflikte = moderation.pruefe_belegungskonflikt(element_name, neu)

        if _als_flag(nur_pruefen):
            antwort: dict[str, object] = {
                "success": True, "geprueft": True, "id": element_name,
            }
            if konflikte:
                antwort["belegung_konflikt"] = konflikte
                antwort["meldung"] = (
                    "Achtung: der Termin ueberschneidet sich mit einer "
                    "anderen Belegung."
                )
            return antwort

        moderation.vorschlag_anwenden(name, element_name, neu)
        _delete_doc("Element Aenderung", name)
        antwort = {"success": True, "id": element_name}
        if konflikte:
            antwort["belegung_konflikt"] = konflikte
            antwort["meldung"] = (
                "Freigegeben — Achtung: der Termin ueberschneidet sich mit "
                "einer anderen Belegung."
            )
        return antwort
    except Exception as e:  # noqa: BLE001
        _rethrow(e, f"aenderung_freigeben ERROR: {name}")


def _als_flag(wert) -> bool:
    """Frappe-uebliche Wahrheitswerte aus dem Request (`1`, `"1"`, `true`)."""
    if isinstance(wert, bool):
        return wert
    return str(wert).strip().lower() in ("1", "true", "yes", "on")


@whitelist(allow_guest=False)
def aenderung_ablehnen(name):
    """Vorgeschlagene Termindaenderung verwerfen (nur Moderatoren)."""
    try:
        from diakronos_app.api.kronos import moderation

        moderation.pruefe_moderationsrecht(name)
        _delete_doc("Element Aenderung", name)
        return {"success": True}
    except Exception as e:  # noqa: BLE001
        _rethrow(e, f"aenderung_ablehnen ERROR: {name}")


__all__ = [
    "_assert_read_access",
    "_assert_write_access",
    "aenderung_ablehnen",
    "aenderung_freigeben",
    "create_event",
    "create_series",
    "delete_event",
    "get_offene_aenderungen",
    "parse_iso_datetime_raw",
    "save_event",
    "update_event",
]
