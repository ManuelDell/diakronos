"""Benachrichtigungen bei Terminaenderungen (OP-HANDY-6).

Wer zu einem Termin eingeteilt ist (Kind-Tabelle ``mitarbeiter``), erfaehrt
bisher NICHTS, wenn der Termin verschoben, abgesagt oder die Zuteilung
geaendert wird — genau der Fall, den die Nachtpruefung als OP-HANDY-6
bemangelt.

Diese Datei schreibt in ``Notification Log`` (dieselbe Quelle wie
``api.audit.get_my_notifications`` und die Glocke in der Oberflaeche). Sie
wird aus ``moderation.wende_termin_aenderung_an`` aufgerufen — dem EINEN
Schreibweg fuer alle Terminaenderungen.

Regeln (Nachtpruefung P2-4b):
* B-2: Gemeldet werden nur WIRKLICH geaenderte Werte — der Aufrufer vergleicht
  alt/neu; hier kommen nur die betroffenen Feldnamen an.
* W-2: Massenaenderungen (Serie, Batch) buendeln zu EINER Nachricht je Person
  (``TerminSammler``), nicht zu bis zu 100.
* W-3: Nur Empfaenger, die den Kalender LESEN duerfen, bekommen Titel und
  Zeit; ohne Leserecht wird gar nicht benachrichtigt.

Schreiben ist BEIWERK: ein Fehler hier darf den Terminvorgang nie scheitern
lassen.
"""
from __future__ import annotations

from typing import Any, Iterable

from diakronos_app.benachrichtigungen import schreibe_meldung, user_zu_mitglied
from diakronos_app.frappe_compat.api_helpers import get_all, log_error, session
from diakronos_app.frappe_compat.query import get_value

# Felder, deren Aenderung fuer die Eingeteilten wirklich von Belang ist.
RELEVANTE_FELDER = {
    "element_start": "Datum/Uhrzeit",
    "element_end": "Ende",
    "element_calendar": "Kalender",
    "all_day": "Ganztags",
    "ressource": "Ort/Ressource",
    "zusaetzliche_ressourcen": "Weitere Orte/Ressourcen",
}

_TITEL = "Termin"


def _benutzer_zu_mitglied(mitglied: str | None) -> str | None:
    """Benutzername eines Mitglieds (``user``, sonst eindeutige E-Mail)."""
    from diakronos_app.db import sitzung_fuer_lesen

    db_session, eigene = sitzung_fuer_lesen()
    try:
        return user_zu_mitglied(db_session, mitglied)
    finally:
        if eigene:
            db_session.close()


def empfaenger_der_mitarbeiter(element_name: str) -> set[str]:
    """Benutzernamen aller zu einem Termin eingeteilten Personen.

    W-3: Nur wer den Kalender des Termins lesen darf, bekommt eine Nachricht.
    Ein privater Kalender darf seinen Titel nicht ueber die Glocke eines
    Eingeteilten verraten. Ist der Kalender nicht ermittelbar, wird
    vorsichtshalber NICHT benachrichtigt (fail closed).
    """
    rows = get_all(
        "Element Mitarbeiter",
        filters={"parent": element_name, "parentfield": "mitarbeiter"},
        fields=["mitglied"],
    ) or []
    treffer: set[str] = set()
    for r in rows:
        u = _benutzer_zu_mitglied(str(r.get("mitglied") or "") or None)
        if u:
            treffer.add(u)
    if not treffer:
        return treffer
    kalender = str(get_value("Element", element_name, "element_calendar") or "")
    erlaubt = _leseberechtigte_empfaenger(kalender, treffer)
    return erlaubt


def _leseberechtigte_empfaenger(calendar: str, empfaenger: Iterable[str]) -> set[str]:
    """Filtert Empfaenger auf die, die den Kalender lesen duerfen (W-3)."""
    if not calendar:
        return set()
    from diakronos_app.api.kronos.permissions import hat_leserecht_fuer

    treffer: set[str] = set()
    for user in empfaenger:
        try:
            if hat_leserecht_fuer(user, calendar):
                treffer.add(user)
        except Exception as ex:  # noqa: BLE001 — Beiwerk
            log_error(str(ex), f"leserecht_empfaenger {user}")
    return treffer


def _aufrufer() -> str | None:
    """Benutzername des Ausloesers (wird nicht selbst benachrichtigt)."""
    try:
        return session.user
    except Exception:  # noqa: BLE001
        return None


def _meldezeilen(element_name: str, *, titel: str | None, geaenderte_felder: list[str],
                 wartet: bool) -> tuple[str, str]:
    """Betreff und Text einer Terminaenderung."""
    name = titel or _TITEL
    beschreibung = ", ".join(RELEVANTE_FELDER[f] for f in geaenderte_felder if f in RELEVANTE_FELDER)
    if wartet:
        subject = f"Termin geändert (wartet auf Freigabe): {name}"
        inhalt = (f"Die Änderung am Termin „{name}“ ({beschreibung}) ist eingegangen "
                  f"und wird noch geprüft. Der Termin zeigt bis dahin die bisherige Fassung.")
    else:
        subject = f"Termin geändert: {name}"
        inhalt = (f"Der Termin „{name}“ wurde geändert ({beschreibung}). "
                  f"Bitte prüfe deine Angaben im Kalender.")
    return subject, inhalt


def benachrichtige_termin(
    element_name: str,
    *,
    titel: str | None,
    geaenderte_felder: list[str],
    wartet: bool = False,
) -> int:
    """Informiert die Eingeteilten ueber eine wirksame Terminaenderung.

    ``wartet=True`` bedeutet: die Aenderung ist als Vorschlag gespeichert und
    noch nicht sichtbar — die Nachricht sagt das ausdruecklich, sonst wuerde
    der Termin beim Nachsehen unveraendert wirken.
    """
    try:
        empfaenger = empfaenger_der_mitarbeiter(element_name)
    except Exception as ex:  # noqa: BLE001 — Beiwerk
        log_error(str(ex), f"termin_empfaenger {element_name}")
        return 0
    # Wer die Aenderung selbst ausgeloest hat, muss keine Nachricht bekommen.
    aufrufer = _aufrufer()
    if aufrufer:
        empfaenger.discard(aufrufer)
    if not empfaenger:
        return 0

    subject, inhalt = _meldezeilen(element_name, titel=titel,
                                   geaenderte_felder=geaenderte_felder, wartet=wartet)
    geschrieben = 0
    for user in empfaenger:
        if schreibe_meldung(for_user=user, subject=subject, inhalt=inhalt,
                            document_type="Element", document_name=element_name):
            geschrieben += 1
    return geschrieben


def benachrichtige_absage(element_name: str, titel: str, empfaenger: set[str]) -> None:
    """Nach erfolgreichem Loeschen an zuvor leseberechtigte Eingeteilte melden.

    Empfaenger muessen VOR dem Loeschen ermittelt werden: danach fehlen sowohl
    Kalender als auch Mitarbeiter. Der Ausloeser bekommt keine eigene Meldung.
    """
    for user in empfaenger - {_aufrufer()}:
        schreibe_meldung(
            for_user=user, subject=f"Termin abgesagt: {titel or _TITEL}",
            inhalt=f"Der Termin „{titel or _TITEL}“ wurde abgesagt und aus dem Kalender entfernt.",
            document_type="Element", document_name=element_name,
        )


def absage_vorbereiten(element_name: str) -> dict[str, Any] | None:
    """Empfänger und lesbare Angaben vor Löschung/Rückstufung festhalten."""
    try:
        from diakronos_app.frappe_compat.api_helpers import get_doc
        doc = get_doc("Element", element_name)
        if doc.get("status") != "Festgelegt":
            return None
        return {"empfaenger": empfaenger_der_mitarbeiter(element_name) - {_aufrufer()},
                "titel": str(doc.get("element_name") or _TITEL),
                "beginn": str(doc.get("element_start") or "")[:10]}
    except Exception as exc:  # Beiwerk: keine gespeicherte Änderung scheitern lassen
        log_error(type(exc).__name__, "Absage vorbereiten")
        return None


def _terminliste(termine: list[tuple[str, str]]) -> str:
    from datetime import date
    def datum(wert: str) -> str:
        try:
            return date.fromisoformat(wert).strftime("%d.%m.%Y")
        except ValueError:
            return "Datum unbekannt"
    tage = sorted({tag for _, tag in termine if tag})
    zeitraum = f"{datum(tage[0])} bis {datum(tage[-1])}" if tage else "Datum unbekannt"
    titel = ", ".join(sorted({name for name, _ in termine}))
    return f"{zeitraum}: {titel}"


class AbsageSammler:
    """Erst nach erfolgreichem Schreiben aufnehmen; eine Meldung je Person."""
    def __init__(self) -> None:
        self._je_user: dict[str, list[tuple[str, str]]] = {}

    def merke(self, stand: dict[str, Any] | None) -> None:
        if not stand:
            return
        for user in stand["empfaenger"]:
            self._je_user.setdefault(user, []).append((stand["titel"], stand["beginn"]))

    def melden(self) -> None:
        for user, termine in self._je_user.items():
            schreibe_meldung(for_user=user, subject=f"Termine abgesagt: {len(termine)}",
                            inhalt=f"Diese Termine sind nicht mehr festgelegt: {_terminliste(termine)}. Bitte prüfe deine Planung.",
                            document_type="Element", document_name="")


class TerminSammler:
    """Buendelt Terminaenderungen einer Massnahme zu EINER Nachricht je Person.

    W-2: ``update_series_batch_fast`` ruft fuer JEDEN Termin einer Serie
    ``wende_termin_aenderung_an`` auf — ohne Buendelung entstanden bis zu 100
    Nachrichten je Eingeteiltem fuer denselben Vorgang. Der Aufrufer sammelt
    und meldet am Ende einmal.
    """

    def __init__(self, *, grund: str) -> None:
        self.grund = grund                 # z. B. "Serientermin geändert"
        self._je_user: dict[str, set[str]] = {}
        self._elemente: dict[str, str] = {}  # user -> erster Termin (Verknuepfung)
        self._termine: dict[str, list[tuple[str, str]]] = {}

    def merke(self, element_name: str, *, titel: str | None, geaenderte_felder: list[str]) -> None:
        """Eine Terminaenderung aufnehmen (Beiwerk — niemals werfen)."""
        try:
            empfaenger = empfaenger_der_mitarbeiter(element_name)
            aufrufer = _aufrufer()
            if aufrufer:
                empfaenger.discard(aufrufer)
            for user in empfaenger:
                self._je_user.setdefault(user, set()).update(geaenderte_felder)
                self._elemente.setdefault(user, element_name)
                beginn = str(get_value("Element", element_name, "element_start") or "")[:10]
                self._termine.setdefault(user, []).append((titel or _TITEL, beginn))
        except Exception as ex:  # noqa: BLE001 — Beiwerk
            log_error(str(ex), f"termin_sammler {element_name}")

    def melden(self) -> int:
        """Je Empfaenger EINE Nachricht ueber alle aufgenommenen Termine."""
        geschrieben = 0
        for user, felder in self._je_user.items():
            beschreibung = ", ".join(RELEVANTE_FELDER[f] for f in sorted(felder)
                                     if f in RELEVANTE_FELDER)
            subject = f"{self.grund}: mehrere Termine betroffen"
            inhalt = (f"{self.grund}: Es wurden mehrere Termine geändert "
                      f"({beschreibung or 'Terminangaben'}). "
                      f"{_terminliste(self._termine.get(user, []))}. "
                      f"Bitte prüfe deine Angaben im Kalender.")
            if schreibe_meldung(for_user=user, subject=subject, inhalt=inhalt,
                                document_type="Element", document_name=self._elemente.get(user, "")):
                geschrieben += 1
        return geschrieben


def geaenderte_relevante_felder(werte: dict[str, Any]) -> list[str]:
    """Die fuer Eingeteilte bedeutsamen Felder aus einem Feldsatz."""
    return [f for f in werte if f in RELEVANTE_FELDER]


__all__ = [
    "RELEVANTE_FELDER",
    "TerminSammler",
    "benachrichtige_termin",
    "empfaenger_der_mitarbeiter",
    "geaenderte_relevante_felder",
    "schreibe_meldung",
]
