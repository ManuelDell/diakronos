"""Zentrale Moderationsregel fuer Termin-Aenderungen (Operator-Regel 16.10.).

BEFUND P1-1b (B1/B2/W1): Die Regel

    "Ein Nicht-Moderator aendert an einem FESTGELEGTEN Termin nur
     Kleinigkeiten (Titel, Beschreibung, Kategorie) sofort; Datum, Uhrzeit,
     Ort/Ressource, Kalender und Ganztags-Kennzeichen warten als offener
     Vorschlag auf die Freigabe durch einen Moderator."

war in P1-1 nur im Hauptpfad von `save_event` umgesetzt. `update_event`,
`update_series_batch_fast`, das Verschieben per Drag&Drop, die Zuordnung von
Ressourcen/Mitarbeitern sowie die Kanban-Endpunkte schrieben an der Regel
vorbei — teils sofort, teils sogar mit Rueckstufung auf "Vorschlag" (der
Termin verschwand damit aus dem Kalender).

Diese Datei haelt die Regel an EINER Stelle. Alle Schreibwege rufen
`wende_termin_aenderung_an` auf; kein Aufrufer prueft die Felder selbst.

Aufteilung eines Feldsatzes in drei Toepfe:

  * ``sofort``       — am Termin unmittelbar wirksam (Titel, Beschreibung,
                       Kategorie; fuer Moderatoren alles).
  * ``vorschlag``    — moderationspflichtig und gegenueber dem Termin
                       tatsaechlich geaendert -> offener Aenderungsvorschlag.
  * ``abgelehnt``    — moderationspflichtig, aber der Aufrufer hat keine
                       Berechtigung und die Aenderung ist nicht als Vorschlag
                       darstellbar (z. B. Statuswechsel) -> wird verworfen bzw.
                       mit ``streng=True`` als Fehler gemeldet.

``status`` ist NIE Teil eines Vorschlags: die Freigabe ist eine
Moderationshandlung, kein Feldwert. Ein Nicht-Moderator kann den Status eines
festgelegten Termins damit weder setzen noch zurueckstufen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from diakronos_app.api.kronos.benachrichtigung import AbsageSammler

import json as _json
from dataclasses import dataclass, field
from datetime import datetime as _datetime

from diakronos_app.frappe_compat.api_helpers import (
    _create,
    _delete_doc,
    _generate_hash,
    _update_doc,
    get_all,
    get_doc,
    log_error,
    session,
    throw,
)
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError

from diakronos_app.frappe_compat.api_helpers import flags

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Felder, deren Aenderung an einem FESTGELEGTEN Termin moderationspflichtig ist.
MODERATIONSPFLICHTIGE_FELDER = (
    "element_start",
    "element_end",
    "ressource",
    "element_calendar",
    "all_day",
)

# Felder, die ein Nicht-Moderator auch am festgelegten Termin sofort aendern darf.
SOFORT_FELDER = (
    "element_name",
    "description",
    "element_category",
)

# Kind-Tabellen, die zur moderierten Aenderung dazugehoeren. Sie werden im
# Vorschlag mitgespeichert und erst bei der Freigabe angewandt (Befund W1:
# zusaetzliche Ressourcen wurden im P1-1-Vorschlagszweig sofort geschrieben).
VORSCHLAG_KIND_TABELLEN = ("zusaetzliche_ressourcen",)

# Mitarbeiter-Zuordnung ist laut Review "zu klaeren"; sie bleibt sofort
# gueltig (reine Personaleinteilung, kein Belegungskonflikt).
SOFORT_KIND_TABELLEN = ("mitarbeiter",)


@dataclass
class TerminAenderung:
    """Ergebnis der Aufteilung eines Feldsatzes durch die Moderationsregel."""

    #: Felder, die am Termin sofort geschrieben werden.
    sofort: dict[str, object] = field(default_factory=dict)
    #: Moderationspflichtige Felder fuer den offenen Aenderungsvorschlag.
    vorschlag: dict[str, object] = field(default_factory=dict)
    #: Kind-Tabellen fuer den Vorschlag (Ressourcen).
    vorschlag_kind: dict[str, object] = field(default_factory=dict)
    #: Kind-Tabellen, die sofort geschrieben werden (Mitarbeiter).
    sofort_kind: dict[str, object] = field(default_factory=dict)

    @property
    def wartet(self) -> bool:
        return bool(self.vorschlag or self.vorschlag_kind)


@dataclass
class ErgebnisAenderung:
    """Ergebnis von `wende_termin_aenderung_an` (Aufteilung + Antwortfelder)."""

    aufteilung: "TerminAenderung"
    aenderung_wartet: bool = False
    meldung: str = ""


def ist_moderator(calendar_name) -> bool:
    """Moderiert der aktuelle Nutzer diesen Kalender?

    Sicht auf ``get_accessible_calendars`` (`is_moderator` ist dort schon
    ausgewertet). Ein ``None``-Kalender ist nie moderierbar.
    """
    if not calendar_name:
        return False
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    return any(
        c["name"] == calendar_name and c.get("is_moderator")
        for c in get_accessible_calendars()
    )


def kalenderwechsel_wirkt_sofort(
    alter_kalender,
    neuer_kalender,
    ist_mod_quelle: bool,
) -> bool:
    """Darf ein Kalenderwechsel unmittelbar wirken? (P1-5c, Punkt 7)

    Das Verschieben in einen anderen Kalender ist eine Freigabehandlung: der
    Termin verlaesst den einen und erscheint im anderen Kalender. Genau wie bei
    der Freigabe eines Vorschlags (`vorschlag_anwenden`) wird deshalb das
    Moderationsrecht am ZIELKALENDER verlangt. Zusaetzlich muss der Aufrufer den
    QUELLKALENDER moderieren — sonst duerfte er an einem festgelegten Termin
    ohnehin nichts sofort aendern (Befund P1-2/N1).

    Kein Wechsel (`neuer_kalender` leer oder gleich dem alten) ist keine
    Verschiebung und damit nicht betroffen.
    """
    if not neuer_kalender or str(neuer_kalender) == str(alter_kalender or ""):
        return ist_mod_quelle
    return ist_mod_quelle and ist_moderator(neuer_kalender)


def _normalisiere_datum(wert) -> str | None:
    """Datums-/Zeitwert auf die Vergleichsform `YYYY-MM-DD HH:MM:SS` bringen."""
    if wert is None:
        return None
    if isinstance(wert, _datetime):
        return wert.strftime(_DATETIME_FORMAT)
    text = str(wert).strip()
    if not text:
        return None
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw

    try:
        return parse_iso_datetime_raw(text)
    except Exception:  # noqa: BLE001 — unparsbarer Wert bleibt Wort fuer Wort
        return text


def _wert_fuer_vergleich(feld: str, wert):
    """Wert fuer den alt/neu-Vergleich normalisieren (u. a. bool -> 0/1)."""
    if feld in ("element_start", "element_end"):
        return _normalisiere_datum(wert)
    if feld == "all_day":
        return 1 if wert else 0
    if feld == "zusaetzliche_ressourcen":
        from diakronos_app.api.kronos.event_crud import _normalize_ressourcen

        # Verglichen wird der Ort, nicht technische Zeilen-IDs, Reihenfolge,
        # Notizen oder der Freigabestatus der Ressourcenanfrage.
        return sorted((r["ressource"], r["freitext_ressource"])
                      for r in _normalize_ressourcen(wert))
    return "" if wert is None else str(wert)


def _hat_materielle_aenderung(doc, werte: dict[str, object]) -> bool:
    """Aendert `werte` einen moderationspflichtigen Punkt gegenueber `doc`?"""
    for feld in MODERATIONSPFLICHTIGE_FELDER:
        if feld not in werte:
            continue
        alt = _wert_fuer_vergleich(feld, doc.get(feld))
        neu = _wert_fuer_vergleich(feld, werte[feld])
        if alt != neu:
            return True
    return False


def trenne_aenderung(
    doc,
    werte: dict[str, object],
    ist_mod: bool,
    *,
    kind_tabellen: dict[str, object] | None = None,
) -> TerminAenderung:
    """Feldsatz nach der Moderationsregel in sofort/vorschlag aufteilen.

    `doc` ist der aktuelle Termin (`Document` oder Modell-Objekt mit `.get`),
    `werte` der gewuenschte Feldstand. `ist_mod` sagt, ob der Aufrufer den
    KALENDER DES TERMINS moderiert.

    ``status`` ist in `werte` nur dann sinnvoll, wenn der Aufrufer Moderator
    ist (die Aufrufer setzen das bereits so); die Regel laesst es dann durch.
    """
    ergebnis = TerminAenderung()
    festgelegt = (doc.get("status") or "Vorschlag") == "Festgelegt"
    moderationsbeduerftig = bool(not ist_mod and festgelegt)

    for feld, wert in werte.items():
        if feld in ("series_id", "ignore_conflict"):
            # Steuerfelder, kein Terminfeld: der Aufrufer entscheidet.
            continue
        if feld == "status":
            # Moderatoren duerfen den Status setzen; fuer Nicht-Moderatoren
            # haben die Aufrufer ihn schon entfernt (Befund B1/B2).
            if ist_mod:
                ergebnis.sofort[feld] = wert
            continue
        if not moderationsbeduerftig or feld in SOFORT_FELDER:
            ergebnis.sofort[feld] = wert
        elif _wert_fuer_vergleich(feld, doc.get(feld)) != _wert_fuer_vergleich(feld, wert):
            ergebnis.vorschlag[feld] = wert

    if kind_tabellen:
        for name, wert in kind_tabellen.items():
            # N2 (Review P1-2) / P1-5c (8): Ein `None` heisst an dieser Stelle
            # "keine Angabe" — die Tabelle bleibt, wie sie ist. Frueher fiel
            # `None` im else-Zweig in die SOFORT-Schreibung und leerte die
            # Kind-Tabelle (`wende_kind_tabellen_an` schreibt None = leer). Die
            # heutigen Aufrufer filtern `None` selbst; diese zentrale Funktion
            # darf sich darauf aber nicht verlassen.
            if wert is None:
                continue
            if name in SOFORT_KIND_TABELLEN or not moderationsbeduerftig:
                ergebnis.sofort_kind[name] = wert
            else:
                # P1-1b: nur eine TATSAECHLICH gesetzte Ressourcenliste ist
                # eine offene Aenderung. Eine ausdruecklich gesendete (ggf.
                # leere) Liste ist eine gewollte Aenderung und wartet als
                # Vorschlag; sonst wartete jede reine Textaenderung auf die
                # Moderation.
                ergebnis.vorschlag_kind[name] = wert

    return ergebnis


def speichere_aenderungsvorschlag(
    element_name: str,
    element_calendar: str,
    antragsteller: str,
    vorschlag: dict[str, object],
    kind_tabellen: dict[str, object] | None = None,
) -> str:
    """Offenen Aenderungsvorschlag ablegen (neuere Fassung ersetzt die alte).

    Befund W4: Ersetzen darf nicht als "loeschen, dann anlegen" ueber zwei
    getrennte Schreibungen laufen — schlaegt das Anlegen fehl, waere der alte
    Vorschlag weg. Der Router der Frappe-kompatiblen Endpunkte oeffnet keinen
    eigenen Request-Rahmen (jeder Compat-Helfer committet fuer sich), deshalb
    laeuft der Ersatz hier ausdruecklich in EINER Sitzung und EINER
    Transaktion: erst anlegen, dann die alten Zeilen loeschen, dann EIN Commit.
    Faellt irgendetwas dazwischen aus, wird zurueckgerollt und der alte
    Vorschlag bleibt unveraendert bestehen.

    Gespeichert werden NUR die moderationspflichtigen Felder (Befund W2): die
    sofort gueltigen Felder (Titel, Beschreibung, Kategorie) gehoeren nicht in
    den Vorschlag, sonst ueberschriebe die Freigabe zwischenzeitliche
    Sofortaenderungen.

    P1-8 (K-a): Die Ressourcenliste eines Vorschlags wird mit DERSELBEN
    Schranke normalisiert wie eine direkt gespeicherte Liste
    (`event_crud._normalize_ressourcen`). Sonst koennte ein Nicht-Moderator
    „Bestätigt" per API in den Vorschlag einschleusen; bei der Freigabe
    entschied dann der Status des Freigebenden, nicht die Rolle des
    Antragstellers — die Ressourcen-Moderation waere umgangen.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.api_helpers import model_for

    nutzlast: dict[str, object] = dict(vorschlag)
    for name, wert in (kind_tabellen or {}).items():
        if name == "zusaetzliche_ressourcen":
            wert = _normalisiere_ressourcen_fuer_vorschlag(element_name, wert)
        nutzlast[name] = wert

    neuer_name = f"ELEMAEND-{_generate_hash(12)}"
    model = model_for("Element Aenderung")
    bestehende = get_all(
        "Element Aenderung",
        filters={"element": element_name},
        fields=["name"],
    ) or []

    sess = SessionLocal()
    try:
        sess.add(model(
            name=neuer_name,
            element=element_name,
            element_calendar=element_calendar,
            antragsteller=antragsteller,
            vorschlag=_json.dumps(nutzlast, ensure_ascii=False),
            docstatus=0,
            idx=0,
        ))
        sess.flush()  # Anlegen scheitert hier -> alte Zeilen sind noch da
        for row in bestehende:
            alt = str(row.get("name"))  # type: ignore[union-attr]
            if alt == neuer_name:
                continue
            obj = sess.get(model, alt)
            if obj is not None:
                sess.delete(obj)
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
    return neuer_name


def _normalisiere_ressourcen_fuer_vorschlag(element_name: str, wert) -> list:
    """Ressourcenliste eines Vorschlags mit der Moderationsschranke belegen (K-a).

    Delegiert an die EINE Normalisierung aus `event_crud` — keine zweite Kopie
    der Regel. Wichtig ist hier der `gespeichert`-Vergleich: die bereits am
    Termin gespeicherten Zeilen sind der Ausgangspunkt, damit eine unveraenderte
    bestaetigte Zuordnung nicht versehentlich zur Anfrage wird (B2).
    """
    from diakronos_app.api.kronos import event_crud

    gespeichert = event_crud._gespeicherte_ressourcen_status(element_name)
    return event_crud._normalize_ressourcen(wert, element_name, gespeichert)


def _ressourcen_nach_zeitwechsel_erneut_anfragen(
    doc, werte: dict[str, object], ist_mod: bool, element_name: str
) -> None:
    """K-b: Zeit-/Ressourcenwechsel eines Vorschlagstermins stufen Bestaetigtes zurueck.

    Aendert ein NICHT-Moderator Datum/Uhrzeit oder die Ressource eines noch
    nicht festgelegten Termins, ist eine zuvor bestaetigte Ressourcen-Zuordnung
    nicht mehr gedeckt: der Termin liegt jetzt zu einem anderen Zeitpunkt (oder
    auf einer anderen Ressource) vor. Die Zuordnung wird deshalb erneut
    „Angefragt" und laeuft wieder durch die Ressourcen-Moderation.
    """
    if ist_mod:
        return
    zeit_oder_ressource = {"element_start", "element_end", "ressource", "all_day"}
    if not (set(werte) & zeit_oder_ressource):
        return
    from diakronos_app.api.kronos import event_crud

    zeilen = event_crud._gespeicherte_ressourcen_status(element_name)
    zurueck = {
        schluessel for schluessel, status in zeilen.items() if status == "Bestätigt"
    }
    if not zurueck:
        return
    for ressource, freitext in zurueck:
        event_crud._child_delete(
            "Element Ressource", element_name, "zusaetzliche_ressourcen",
            {"ressource": ressource, "freitext_ressource": freitext},
        )
        event_crud._child_insert(
            "Element Ressource", element_name, "zusaetzliche_ressourcen",
            {"ressource": ressource, "freitext_ressource": freitext,
             "status": "Angefragt", "notiz": ""},
        )


def wende_termin_aenderung_an(
    doc,
    werte: dict[str, object],
    ist_mod: bool,
    *,
    kind_tabellen: dict[str, object] | None = None,
    calendar_fuer_vorschlag: str | None = None,
    antragsteller: str | None = None,
    sammler: "object | None" = None,
    absage_sammler: "AbsageSammler | None" = None,
) -> "ErgebnisAenderung":
    """DIE zentrale Moderationsregel fuer alle Termin-Schreibwege.

    Teilt `werte` auf, schreibt die sofort gueltigen Felder, legt bei Bedarf
    den offenen Aenderungsvorschlag ab und liefert die Antwortfelder
    (``aenderung_wartet``, ``meldung``) zurueck.

    Der Aufrufer hat die Schreibrechte bereits geprueft.

    ``sammler`` (optional, W-2): eine ``benachrichtigung.TerminSammler``. Dann
    wird hier NICHT einzeln gemeldet — der Aufrufer buendelt mehrere Termine
    (Serie/Batch) und meldet am Ende einmal je Person.
    """
    # K-b (P1-8): Ein Zeitwechsel durch einen Nicht-Moderator an einem noch
    # nicht festgelegten Termin hebt die Deckung einer bestaetigten
    # Ressourcen-Zuordnung auf — sie wird erneut „Angefragt". Das geschieht
    # VOR dem Schreiben der Kind-Tabellen, damit der neue Zeitpunkt gilt.
    _ressourcen_nach_zeitwechsel_erneut_anfragen(
        doc, werte, ist_mod, str(doc.get("name"))
    )

    aufteilung = trenne_aenderung(
        doc,
        werte,
        ist_mod,
        kind_tabellen=kind_tabellen,
    )

    # B-2: Fuer die Benachrichtigung zaehlt nur, was sich WIRKLICH aendert.
    # `save_event` schickt immer den vollen Feldsatz; ohne diesen Vergleich
    # meldete jede Moderator-Speicherung (auch reines Titel/Text-Speichern)
    # faelschlich „Termin geaendert“ mit Zeit/Kalender. Der ALTE Stand muss
    # VOR dem Schreiben gelesen werden — danach ist er weg.
    meldewerte = {**aufteilung.sofort, **aufteilung.sofort_kind}
    alte_werte = _alte_meldewerte(doc, meldewerte)
    from diakronos_app.api.kronos import benachrichtigung
    rueckstufung = (doc.get("status") == "Festgelegt"
                   and "status" in aufteilung.sofort
                   and aufteilung.sofort["status"] != "Festgelegt")
    absage = benachrichtigung.absage_vorbereiten(str(doc.get("name"))) if rueckstufung else None

    # Die sofort gueltigen Felder wandern in JEDEM Fall an den Termin — ohne
    # Vorschlag ist das der volle Feldsatz, mit Vorschlag nur die Kleinigkeiten
    # (die alte Fassung bleibt fuer den Rest sichtbar).
    if aufteilung.sofort:
        flags.allow_series_edit = True
        _update_doc("Element", str(doc.get("name")), aufteilung.sofort)

    # Kindwerte gehoeren zur wirksamen Aenderung. Erst erfolgreich schreiben,
    # dann melden; sonst koennte eine fehlgeschlagene Kindschreibung bereits
    # eine falsche Nachricht hinterlassen.
    wende_kind_tabellen_an(str(doc.get("name")), aufteilung.sofort_kind)
    if "zusaetzliche_ressourcen" in meldewerte:
        meldewerte["zusaetzliche_ressourcen"] = _alte_meldewerte(doc, meldewerte)["zusaetzliche_ressourcen"]

    if aufteilung.wartet:
        speichere_aenderungsvorschlag(
            str(doc.get("name")),
            calendar_fuer_vorschlag or str(doc.get("element_calendar") or ""),
            antragsteller or session.user,
            aufteilung.vorschlag,
            aufteilung.vorschlag_kind,
        )
        # W-2: Eine wartende Aenderung ist noch NICHT wirksam — die Eingeteilten
        # erfahren erst bei der Freigabe davon. Vorher bekamen sie bei jedem
        # Vorschlag eine „wartet auf Freigabe“-Nachricht, die bei Ablehnung nie
        # eine Korrektur erhielt.
        return ErgebnisAenderung(
            aufteilung=aufteilung,
            aenderung_wartet=True,
            meldung="Änderung wartet auf Freigabe (Terminmoderation).",
        )

    # OP-HANDY-6: wirksame Aenderung an einem festgelegten Termin — die
    # Eingeteilten informieren. Entwuerfe und Vorschlaege loesen nichts aus;
    # nur echte Wertaenderungen (B-2) erzeugen eine Nachricht.
    if rueckstufung:
        sammlung = absage_sammler if absage_sammler is not None else benachrichtigung.AbsageSammler()
        sammlung.merke(absage)
        if absage_sammler is None:
            sammlung.melden()
    elif str(doc.get("status") or "") == "Festgelegt" and meldewerte:
        felder = _echte_aenderungen(alte_werte, meldewerte)
        if felder:
            if sammler is not None:
                sammler.merke(str(doc.get("name") or ""), titel=str(doc.get("element_name") or ""),
                              geaenderte_felder=felder)
            else:
                _benachrichtige(doc, aufteilung.sofort, wartet=False, felder=felder)

    return ErgebnisAenderung(aufteilung=aufteilung, aenderung_wartet=False)


def _alte_meldewerte(doc, neue_werte: dict[str, object]) -> dict[str, object]:
    """Vergleichsstand inklusive Ressourcen-Kindzeilen vor der Schreibung."""
    from diakronos_app.api.kronos import benachrichtigung

    alt = {feld: doc.get(feld) for feld in neue_werte
           if feld in benachrichtigung.RELEVANTE_FELDER}
    if "zusaetzliche_ressourcen" in alt:
        alt["zusaetzliche_ressourcen"] = get_all(
            "Element Ressource",
            filters={"parent": str(doc.get("name")), "parentfield": "zusaetzliche_ressourcen"},
            fields=["ressource", "freitext_ressource"],
        ) or []
    return alt


def _echte_aenderungen(alte_werte: dict[str, object], neue_werte: dict[str, object]) -> list[str]:
    """Nur Felder, deren WERT sich gegenueber dem alten Stand unterscheidet.

    B-2: `geaenderte_relevante_felder` prueft nur, ob der Schluessel im
    Feldsatz steht — `save_event` sendet immer den vollen Feldsatz, deshalb
    galt jede Speicherung als relevant. Verglichen wird mit derselben
    Normalisierung wie die Moderationsregel (`_wert_fuer_vergleich`).
    """
    from diakronos_app.api.kronos import benachrichtigung

    treffer: list[str] = []
    for feld in neue_werte:
        if feld not in benachrichtigung.RELEVANTE_FELDER:
            continue
        alt = _wert_fuer_vergleich(feld, alte_werte.get(feld))
        neu = _wert_fuer_vergleich(feld, neue_werte[feld])
        if alt != neu:
            treffer.append(feld)
    return treffer


def _benachrichtige(doc, geschriebene_werte: dict[str, object], *, wartet: bool,
                    felder: list[str] | None = None) -> None:
    """Meldet eine Terminaenderung an die eingeteilten Personen (Beiwerk)."""
    try:
        from diakronos_app.api.kronos import benachrichtigung

        if felder is None:
            felder = benachrichtigung.geaenderte_relevante_felder(geschriebene_werte)
        if not felder:
            return
        element_name = str(doc.get("name") or "")
        if not element_name:
            return
        benachrichtigung.benachrichtige_termin(
            element_name,
            titel=str(doc.get("element_name") or ""),
            geaenderte_felder=felder,
            wartet=wartet,
        )
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        log_error(str(ex), f"termin_benachrichtigung {doc.get('name')}")


def aenderungen_zu_element_entfernen(element_name: str) -> int:
    """Offene Aenderungsvorschlaege eines Termins loeschen (Befund W3).

    Wird beim Loeschen eines Termins und beim Loeschen einer Serie aufgerufen,
    damit keine Waisen zurueckbleiben. Laeuft im Request-Rahmen (eine
    Transaktion), Fehler beim Einzel-Loeschen werden geloggt und nicht
    weitergereicht — ein kaputter Altvorschlag darf das Loeschen des Termins
    nicht verhindern.
    """
    if not element_name:
        return 0
    rows = get_all(
        "Element Aenderung",
        filters={"element": element_name},
        fields=["name"],
    ) or []
    entfernt = 0
    for row in rows:
        try:
            _delete_doc("Element Aenderung", str(row.get("name")))  # type: ignore[union-attr]
            entfernt += 1
        except Exception as e:  # noqa: BLE001
            log_error(str(e), "Element Aenderung aufraeumen")
    return entfernt


def kind_tabelle_schreiben(element_name: str, name: str, wert) -> None:
    """Kind-Tabelle (Ressourcen bzw. Mitarbeiter) eines Termins setzen."""
    from diakronos_app.api.kronos import event_crud

    if name == "zusaetzliche_ressourcen":
        event_crud._apply_additional_resources(element_name, wert)
    elif name == "mitarbeiter":
        event_crud._apply_mitarbeiter(element_name, wert)
    else:  # pragma: no cover — Programmierfehler
        raise ValueError(f"Unbekannte Kind-Tabelle: {name}")


def wende_kind_tabellen_an(element_name: str, tabellen: dict[str, object] | None) -> None:
    for name, wert in (tabellen or {}).items():
        kind_tabelle_schreiben(element_name, name, wert)


def pruefe_belegungskonflikt(element_name: str, neu: dict[str, object]) -> list[dict]:
    """Belegungskonflikt eines Vorschlags pruefen (Befund K1).

    Die Freigabe wandte Zeit/Ressource ohne erneute Pruefung an; zwei
    Moderatoren konnten so denselben Raum doppelt belegen. Geprueft wird gegen
    den Zieldatensatz des Termins, mit dem Termin selbst ausgenommen
    (`exclude_id`). Rueckgabe: Liste der Konflikte (leer = frei).
    """
    doc = get_doc("Element", element_name)
    start = neu.get("element_start", doc.get("element_start"))
    ende = neu.get("element_end", doc.get("element_end"))
    ressource = neu.get("ressource", doc.get("ressource"))
    zusatz = neu.get("zusaetzliche_ressourcen")

    if not start or not ende or (not ressource and not zusatz):
        return []

    from diakronos_app.api.kronos.ressource_api import check_resource_conflict

    try:
        ergebnis = check_resource_conflict(
            ressource or "",
            _normalisiere_datum(start),
            _normalisiere_datum(ende),
            exclude_id=element_name,
            zusaetzliche_ressourcen=zusatz,
        )
    except Exception as e:  # noqa: BLE001 — Pruefung darf die Freigabe nicht sprengen
        log_error(str(e), "Belegungspruefung bei der Freigabe")
        return []
    return list(ergebnis.get("conflicts") or [])


def vorschlag_anwenden(name: str, element_name: str, neu: dict[str, object]) -> None:
    """Freigabe: NUR die im Vorschlag stehenden Felder am Termin anwenden.

    Befund W2: Die Freigabe schrieb bisher den ganzen Feldstand zurueck (inkl.
    Titel/Beschreibung/Kategorie aus dem Zeitpunkt der Einreichung) und
    verwarf damit zwischenzeitliche Sofortaenderungen. Hier wandern
    ausschliesslich moderationspflichtige Felder sowie die im Vorschlag
    hinterlegten Kind-Tabellen an den Termin.
    """
    werte: dict[str, object] = {}
    for feld in MODERATIONSPFLICHTIGE_FELDER:
        if feld not in neu:
            continue
        if feld in ("element_start", "element_end"):
            from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw

            wert = neu.get(feld)
            werte[feld] = parse_iso_datetime_raw(wert) if wert else None
        elif feld == "all_day":
            werte[feld] = 1 if neu.get(feld) in (1, True, "1") else 0
        else:
            werte[feld] = neu.get(feld) or ""

    # Zielt der Vorschlag auf einen anderen Kalender, muss der Freigebende
    # auch dort moderieren duerfen. N3: verglichen wurde der Zielkalender mit
    # der TERMIN-ID (`element_name`) — der Ausdruck war damit immer wahr und
    # die Pruefung lief gegen den falschen Kalender. Verglichen wird jetzt mit
    # dem bisherigen Kalender des Termins.
    neuer_kalender = werte.get("element_calendar")
    if neuer_kalender:
        altes_doc = get_doc("Element", element_name)
        alter_kalender = altes_doc.get("element_calendar")
        if str(neuer_kalender) != str(alter_kalender) and not ist_moderator(
            str(neuer_kalender)
        ):
            throw(
                f"Keine Moderationsrechte fuer Kalender {neuer_kalender}",
                FrappePermissionError,
            )

    vorher = get_doc("Element", element_name)
    meldewerte = {**werte, **{kind: neu[kind] for kind in VORSCHLAG_KIND_TABELLEN if kind in neu}}
    alte_werte = _alte_meldewerte(vorher, meldewerte)
    if werte:
        flags.allow_series_edit = True
        _update_doc("Element", element_name, werte)

    for kind in VORSCHLAG_KIND_TABELLEN:
        if kind in neu:
            kind_tabelle_schreiben(element_name, kind, neu.get(kind))

    # Vorschlaege bleiben still, erst die tatsaechliche Freigabe informiert.
    felder = _echte_aenderungen(alte_werte, meldewerte)
    if vorher.get("status") == "Festgelegt" and felder:
        _benachrichtige(vorher, werte, wartet=False, felder=felder)


def vorschlag_lesen(doc) -> tuple[dict[str, object], str | None]:
    """Vorschlags-JSON und Zieldatum (Termin) aus einer `Element Aenderung`."""
    try:
        neu = _json.loads(doc.get("vorschlag") or "{}")
    except Exception:  # noqa: BLE001
        neu = {}
    if not isinstance(neu, dict):
        neu = {}
    element = doc.get("element")
    return neu, str(element) if element else None


def pruefe_moderationsrecht(name: str):
    """Laedt den Vorschlag und erzwingt Moderationsrecht am Kalender."""
    if not name or name in ("undefined", "null", ""):
        throw(f"Invalid ID: {name}")
    doc = get_doc("Element Aenderung", name)
    calendar = doc.get("element_calendar")
    if not ist_moderator(calendar):
        throw(
            f"Keine Moderationsrechte fuer Kalender {calendar}",
            FrappePermissionError,
        )
    return doc


__all__ = [
    "MODERATIONSPFLICHTIGE_FELDER",
    "SOFORT_FELDER",
    "SOFORT_KIND_TABELLEN",
    "VORSCHLAG_KIND_TABELLEN",
    "TerminAenderung",
    "ist_moderator",
    "kind_tabelle_schreiben",
    "pruefe_belegungskonflikt",
    "pruefe_moderationsrecht",
    "speichere_aenderungsvorschlag",
    "trenne_aenderung",
    "vorschlag_anwenden",
    "vorschlag_lesen",
    "wende_kind_tabellen_an",
    "wende_termin_aenderung_an",
]
