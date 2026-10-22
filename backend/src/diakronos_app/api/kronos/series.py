"""Portierung von `diakronos.kronos.api.series` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/series.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    update_series_batch_fast      delete_future_series_events
    delete_series_batch_fast

Abweichung zur Vorlage (dokumentiert): Das Original macht den Massenupdate per
rohem `frappe.db.sql("UPDATE `tabElement` SET ... WHERE series_id = %s", ...)`.
Die Compat-Schicht uebersetzt nur `%(name)s`-Platzhalter (siehe
`frappe_compat/db.py::_adapt_placeholders`), Positional-`%s` wuerde fehlschlagen.
Der Massenupdate laeuft daher ueber `_shared._bulk_update_by_field`
(SQLAlchemy-Tabelle) — gleiche Semantik, gleiche Whitelist-Pruefung, aber
typsicher. Die Feld-Whitelist und die Fehlermeldungen bleiben 1:1.
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.kronos.api.series"

import json
import re as _re
from datetime import date as _date
from typing import Any

from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _bulk_update_by_field,
    _count,
    _delete_doc,
    get_all,
    get_doc,
    get_value,
    log_error,
    throw,
)

# Erlaubte Update-Felder (1:1 aus dem Original).
_ALLOWED_SERIES_FIELDS = {
    "element_name",
    "event_category_name",
    "status",
    "element_color",
    "element_start",
    "element_end",
}

# K2 (Review P1-3): Der ISO-Tag muss GENAU aus vier Ziffern, Bindestrich,
# zwei Ziffern, Bindestrich, zwei Ziffern bestehen. Ohne diese Wache akzeptierte
# `date.fromisoformat` ab Python 3.11 auch das Basisformat `20261108` und
# `text[:10]` schnitt Muell (`2026-11-08xyz`) still ab.
_DATUM_MUSTER = _re.compile(r"\d{4}-\d{2}-\d{2}")


def _assert_write_access(calendar_name: str) -> None:
    """Import-Proxie auf `event_crud._assert_write_access` (Original macht das inline).

    Der Import steht bewusst in der Funktion, damit `series` <-> `event_crud`
    keinen Importzyklus beim Laden der Module bilden.
    """
    from diakronos_app.api.kronos.event_crud import _assert_write_access as _impl

    _impl(calendar_name)


def _first_calendar_of_series(series_id: str) -> str | None:
    """Kalender des ersten Elements einer Serie (Original: `frappe.get_value`)."""
    value = get_value("Element", {"series_id": series_id}, "element_calendar")
    return str(value) if value else None


def _aenderungen_entfernen(element_name: str) -> int:
    """Offene Aenderungsvorschlaege eines Termins loeschen (Befund W3).

    Import in der Funktion: `series` <-> `moderation` sollen keinen
    Importzyklus beim Laden bilden (gleiches Muster wie `_assert_write_access`).
    """
    from diakronos_app.api.kronos import moderation

    return moderation.aenderungen_zu_element_entfernen(element_name)


@whitelist(allow_guest=False)
def update_series_batch_fast(series_id, updates):
    """Schneller Update aller Elemente einer Serie.

    BEFUND P1-1b (B2): Ohne Moderationsrecht durften `element_start`/
    `element_end` (Datum/Uhrzeit ALLER Termine, auch festgelegter) sofort
    geschrieben werden, und `status="Vorschlag"` stufte eine ganze Serie
    zurueck. Beides laeuft jetzt ueber die zentrale Moderationsregel
    (`moderation.py`):

      * `status` ist nur noch fuer Moderatoren setzbar (sonst verworfen).
      * Datum/Uhrzeit/Alltag/Kalender eines FESTGELEGTEN Termins werden fuer
        Nicht-Moderatoren je Termin als offener Aenderungsvorschlag abgelegt;
        der Termin bleibt in der alten Fassung sichtbar.
      * Titel, Kategorie, Farbe bleiben sofort gueltig (Kleinigkeiten).
    """
    if isinstance(updates, str):
        updates = json.loads(updates)

    if not series_id:
        throw("Series ID fehlt")

    first_calendar = _first_calendar_of_series(series_id)
    if not first_calendar:
        throw(f"Serie nicht gefunden: {series_id}")
    _assert_write_access(str(first_calendar))

    if not updates or not isinstance(updates, dict):
        throw("Updates müssen ein Dictionary sein")

    invalid = set(updates) - _ALLOWED_SERIES_FIELDS
    if invalid:
        throw(f"Nicht erlaubte Felder: {', '.join(sorted(invalid))}")

    from diakronos_app.api.kronos import moderation

    updates = dict(updates)
    ist_mod = moderation.ist_moderator(str(first_calendar))

    # Serien-Status ist wie der Einzel-Status eine Moderationsentscheidung.
    verworfen: list[str] = []
    if "status" in updates and not ist_mod:
        updates.pop("status")
        verworfen.append("status")

    zeitfelder = {
        feld: updates.pop(feld)
        for feld in ("element_start", "element_end", "all_day", "element_calendar")
        if feld in updates
    }

    elemente = get_all(
        "Element",
        filters={"series_id": series_id},
        fields=["name", "status"],
    ) or []
    # W-A (R-P1-8): ein abgelehnter Termin ist erledigt — der Serien-Batch darf
    # ihn weder ueberschreiben noch als wartende Aenderung fuehren. Er bleibt
    # nur in der Moderations-Historie sichtbar.
    elemente = [e for e in elemente if (e.get("status") or "") != "Abgelehnt"]
    wartend = 0
    # Status-Rückstufungen laufen ebenfalls über die zentrale Melderegel.
    if "status" in updates:
        zeitfelder["status"] = updates.pop("status")
    if zeitfelder:
        # W-2: Eine Serienverschiebung betrifft bis zu 100 Termine — die
        # Eingeteilten bekommen EINE Nachricht, nicht eine je Termin.
        from diakronos_app.api.kronos import benachrichtigung

        sammler = benachrichtigung.TerminSammler(grund="Serientermin geändert")
        absage_sammler = benachrichtigung.AbsageSammler()
        for elem in elemente:
            eid = str(elem.get("name"))  # type: ignore[union-attr]
            try:
                doc = get_doc("Element", eid)
            except Exception:  # noqa: BLE001 — verschwundener Termin
                continue
            # Die sofort gueltigen Felder schreibt `wende_termin_aenderung_an`
            # selbst (bei einem Moderator also der ganze Feldsatz).
            ergebnis = moderation.wende_termin_aenderung_an(
                doc, dict(zeitfelder), ist_mod,
                calendar_fuer_vorschlag=str(first_calendar),
                sammler=sammler,
                absage_sammler=absage_sammler,
            )
            if ergebnis.aenderung_wartet:
                wartend += 1
        sammler.melden()
        absage_sammler.melden()

    if updates:
        # W-A: abgelehnte Termine der Serie bleiben unveraendert.
        _bulk_update_by_field(
            "Element", "series_id", series_id, dict(updates),
            ausschluss_status="Abgelehnt",
        )

    count = _count("Element", {"series_id": series_id})
    antwort: dict[str, object] = {"success": True, "updated_count": count}
    if verworfen:
        # N5: Ein stillschweigend verworfener Status liess den Nutzer an eine
        # wirksame Aenderung glauben. Die Meldung nennt das Feld.
        antwort["verworfen"] = list(verworfen)
        antwort["meldung"] = (
            "Der Serien-Status wurde nicht geaendert: die Freigabe ist eine "
            "Moderationshandlung (Terminmoderation)."
        )
    if wartend:
        antwort["aenderung_wartet"] = True
        antwort["wartende_termine"] = wartend
        antwort["meldung"] = (
            f"{wartend} Termin(e) der Serie warten auf Freigabe "
            "(Terminmoderation)."
        )
    return antwort


@whitelist(allow_guest=False)
def delete_future_series_events(series_id, from_date):
    """Loescht alle Elemente einer Serie ab einem bestimmten Datum (inklusive)."""
    if not series_id:
        throw("Series ID erforderlich")
    if not from_date:
        throw("Startdatum erforderlich")

    # BLD-R5: Datum VOR der Abfrage pruefen (sonst 500er aus PostgreSQL).
    from_date = _series_datum(from_date, "Startdatum")

    first_calendar = _first_calendar_of_series(series_id)
    if not first_calendar:
        throw(f"Serie nicht gefunden: {series_id}")
    _assert_write_access(str(first_calendar))

    elements = get_all(
        "Element",
        filters={"series_id": series_id, "element_start": [">=", from_date]},
        fields=["name", "element_calendar"],
    ) or []

    if not elements:
        return {"success": True, "deleted_count": 0}

    from diakronos_app.api.kronos.benachrichtigung import AbsageSammler, absage_vorbereiten
    absagen = AbsageSammler()
    deleted_count = 0
    for elem in elements:
        name = str(elem.get("name"))  # type: ignore[union-attr]
        try:
            stand = absage_vorbereiten(name)
            # W3: offene Aenderungsvorschlaege des Termins mit aufraeumen.
            _aenderungen_entfernen(name)
            _delete_doc("Element", name)
            deleted_count += 1
            absagen.merke(stand)
        except Exception as e:  # noqa: BLE001 — Original loggt und macht weiter
            log_error(f"Fehler beim Löschen von {name}: {e}", "Series Delete Future Error")

    absagen.melden()
    return {"success": True, "deleted_count": deleted_count}


def _series_datum(wert: Any, feldname: str) -> str:
    """Datum aus einer Serien-Anfrage als ISO-Tag lesen (BLD-R5).

    `from_date` kam ungeprueft bis in die SQL-Abfrage: mit einem deutschen
    Datum („08.11.2026“) oder einem Zeitstempel („2026-11-08 10:00:00“)
    verglich PostgreSQL `timestamp >= varchar` — ein unbehandelter 500er
    („operator does not exist“) statt einer verstaendlichen Meldung. Hier wird
    der Wert deshalb VOR der Abfrage geprueft und auf den Tag gekuerzt: der
    Aufruf loescht ohnehin ganze Termine, die Uhrzeit ist ohne Bedeutung.

    K2 (Review P1-3): Zwei stille Schwaechen sind behoben. Ein Zeitstempel ist
    ausdruecklich erlaubt (`2026-11-08 10:00:00` -> Tag), aber der Tag selbst
    muss dem Muster `JJJJ-MM-TT` entsprechen. Vorher schnitt `text[:10]` alles
    nach dem zehnten Zeichen ab: `2026-11-08xyz` wurde still zu einem gueltigen
    Datum, und `20261108` (Basisformat, von `date.fromisoformat` ab 3.11
    akzeptiert) ging als `20261108` in die Abfrage. Beides wird jetzt mit 417
    abgelehnt, wie die uebrigen Endpunkte.
    """
    text = str(wert or "").strip()
    if not text:
        throw(f"{feldname} erforderlich")
    # Erlaubt: ein reiner ISO-Tag ODER ein Zeitstempel, der MIT dem Tag beginnt
    # (Trenner Leerzeichen oder `T`). Der Tag selbst muss `JJJJ-MM-TT` sein.
    # Geprueft wird der GANZE Text — nicht `text[:10]`. Sonst waere
    # `2026-11-08xyz` nach dem Abschneiden wieder gueltig (Review P1-3, K2).
    if not _DATUM_MUSTER.fullmatch(text[:10]) or (
        len(text) > 10 and text[10] not in (" ", "T")
    ):
        throw(
            f"{feldname} muss ein Datum im Format JJJJ-MM-TT sein "
            f"(z. B. 2026-11-08), erhalten: {text!r}"
        )
    tag = text[:10]
    try:
        _date.fromisoformat(tag)
    except ValueError:
        throw(
            f"{feldname} muss ein Datum im Format JJJJ-MM-TT sein "
            f"(z. B. 2026-11-08), erhalten: {text!r}"
        )
    return tag


@whitelist(allow_guest=False)
def delete_series_batch_fast(series_id):
    """Loescht alle Elemente einer Serie."""
    if not series_id:
        throw("Series ID erforderlich")

    # BLD-R5: Ein LEERES `series_id` ist keine Serie. Frueher lief der Aufruf
    # weiter, `_assert_write_access(None)` wurde stillschweigend uebersprungen
    # und die Abfrage `series_id = NULL` traf in SQL JEDEN Termin ohne Serie —
    # ein versehentlicher Aufruf haette alle Einzeltermine geloescht.
    if str(series_id).strip().lower() in {"null", "none", "undefined"}:
        throw("Series ID erforderlich")

    first_calendar = _first_calendar_of_series(series_id)
    if not first_calendar:
        throw(f"Serie nicht gefunden: {series_id}")
    _assert_write_access(str(first_calendar))

    elements = get_all("Element", filters={"series_id": series_id}, fields=["name"]) or []

    if not elements:
        return {
            "success": True,
            "deleted_count": 0,
            "message": "Keine Termine in dieser Serie gefunden",
        }

    from diakronos_app.api.kronos.benachrichtigung import AbsageSammler, absage_vorbereiten
    absagen = AbsageSammler()
    deleted_count = 0
    for elem in elements:
        name = str(elem.get("name"))  # type: ignore[union-attr]
        try:
            stand = absage_vorbereiten(name)
            # W3: offene Aenderungsvorschlaege des Termins mit aufraeumen.
            _aenderungen_entfernen(name)
            _delete_doc("Element", name)
            deleted_count += 1
            absagen.merke(stand)
        except Exception as e:  # noqa: BLE001 — Original loggt und macht weiter
            log_error(f"Fehler beim Löschen von {name}: {e}", "Series Delete Error")

    absagen.melden()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"{deleted_count} Termine gelöscht",
    }


__all__ = [
    "delete_future_series_events",
    "delete_series_batch_fast",
    "update_series_batch_fast",
]
