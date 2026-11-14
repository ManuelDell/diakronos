"""UX2b — Papierkorb: weiches Loeschen, Wiederherstellen, endgueltiges Entfernen.

WAS HIER STEHT (und was NICHT)
------------------------------
„Loeschen“ in der Verwaltung heisst ab jetzt: die Zeile bekommt
``geloescht_am`` (+ ``geloescht_von``) und verschwindet aus JEDER Lese-Ausgabe.
Nach ``AUFBEWAHRUNG_TAGE`` (7 — Fachentscheidung Manuel, Karte UX2b P3)
entfernt der taegliche Scheduler-Job sie endgueltig, mit der vorhandenen
Loeschlogik (Kind-Zeilen, Dateien). Bis dahin laesst sie sich
wiederherstellen.

Fuenf Bereiche (Karte P1). Je Bereich:

============  ===============  =========================  =======================
Bereich       DocType          Rechte zum Loeschen        Aufraeumen am Ende
============  ===============  =========================  =======================
Beitrag       ``Beitrag``      Administrator              (keine Kind-Zeilen)
Termin        ``Element``      Schreibrecht am Kalender   Kind-Zeilen (Mitarbeiter,
                                                          Ressourcen, …)
Gruppe        ``Gruppe``       Administrator              Mitgliedschaften,
                                                          Verantwortliche, Bild
Wiki-Seite    ``Wiki Artikel`` Administrator              (keine Kind-Zeilen)
Lied          ``Lied``         Musikverantwortlich/Admin  Strophen, Fassungen,
                                                          Zuordnungen
============  ===============  =========================  =======================

Dieses Modul kapselt NUR das Aufraeumen (``endgueltig_entfernen``); WER
loeschen darf, entscheidet der jeweilige Endpunkt — dort steht die
bestehende Rechtepruefung, hier wird sie nicht nachgebaut.

WARUM DIE FILTER HIER STEHEN
----------------------------
``nicht_geloescht_ist(...)`` ist die EINE Bedingung, die jede Abfrage auf eine
dieser fuenf Tabellen mitfuehren muss. Sie liegt bei den Modellen, weil die
Abfragen ueber ``get_all`` (Filter-Liste) UND direkt ueber SQLAlchemy
(``select(...)``) laufen — beide Wege koennen dieselbe Liste verwenden.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from diakronos_app.models.diakonos import Beitrag, Gruppe, WikiArtikel
from diakronos_app.models.kronos import Element
from diakronos_app.models.psalmos import Lied

logger = logging.getLogger("diakronos_app.papierkorb")

#: Fachentscheidung Manuel (Karte UX2b): hoechstens 7 Tage im Papierkorb.
AUFBEWAHRUNG_TAGE = 7

#: DocType -> Modell. Reihenfolge = Reihenfolge im Scheduler-Lauf.
BEREICHE: dict[str, Any] = {
    "Beitrag": Beitrag,
    "Element": Element,
    "Gruppe": Gruppe,
    "Wiki Artikel": WikiArtikel,
    "Lied": Lied,
}

#: Feldname (Spalte) der fuenf Tabellen — eine Wahrheit fuer Filter und set_value.
GELOESCHT_AM = "geloescht_am"
GELOESCHT_VON = "geloescht_von"


def nicht_geloescht_ist(doctype: str):
    """SQLAlchemy-Bedingung ``<tabelle>.geloescht_am IS NULL``.

    Fuer den ``select(...)``-Weg. ``KeyError`` bei einem DocType ohne
    Papierkorb — ein stilles „alles zeigen“ waere genau der Fehler, den diese
    Karte verhindern soll (Fail closed).
    """
    return BEREICHE[doctype].geloescht_am.is_(None)


def nur_aktive_filter(doctype: str) -> list:
    """Filter-Liste ``[["geloescht_am", "is", "not set"]]`` fuer ``get_all``.

    Fuer den Frappe-Compat-Weg (``get_all(filters=[...] + nur_aktive_filter(..))``).
    ``KeyError`` bei einem DocType ohne Papierkorb (siehe oben).
    """
    BEREICHE[doctype]
    return [[GELOESCHT_AM, "is", "not set"]]


def ist_geloescht(doctype: str, name: str) -> bool:
    """Liegt die Zeile im Papierkorb? Unbekannte Zeile -> ``False``."""
    from diakronos_app.frappe_compat.query import get_value

    wert = get_value(doctype, name, GELOESCHT_AM)
    return wert is not None


def loeschen(doctype: str, name: str, *, von: str) -> datetime:
    """Zeile in den Papierkorb legen (setzt ``geloescht_am``/``geloescht_von``).

    Idempotent: liegt sie schon im Papierkorb, bleibt der ERSTE Zeitpunkt
    stehen (die Frist laeuft nicht mit jedem Aufruf neu). Rueckgabe ist der
    wirksame Zeitpunkt — die Kennung fuer „Rueckgaengig“ (Karte P4).

    Nicht vorhandene Zeile -> ``DoesNotExistError`` (wie ``get_doc``).
    """
    from diakronos_app.frappe_compat.query import get_doc, get_value
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    get_doc(doctype, name)  # wirft DoesNotExistError, wenn es die Zeile nicht gibt
    bisher = get_value(doctype, name, GELOESCHT_AM)
    if bisher is not None:
        return bisher
    zeitpunkt = datetime.now().replace(microsecond=0)
    _update_doc(doctype, name, {GELOESCHT_AM: zeitpunkt, GELOESCHT_VON: von})
    return zeitpunkt


def wiederherstellen(doctype: str, name: str) -> bool:
    """Zeile aus dem Papierkorb holen. ``True`` = sie war drin.

    Das Rechte-Pruefen macht der Endpunkt (gleiche Rechte wie Loeschen);
    hier steht nur die Wirkung.

    UX2b2 (F4): eigener ``SessionLocal.begin()``-Block — ein Commit, ein
    Rollback, und die Sitzung ist danach zu (die frueher hier offen gelassene
    Sitzung hielt eine Verbindung, bis der GC sie einsammelte).
    """
    from diakronos_app.frappe_compat.query import get_doc
    from diakronos_app.frappe_compat.registry_gen import model_for

    get_doc(doctype, name)
    # Direkt am Modell schreiben: `_update_doc` laesst None-Werte stehen
    # („nur mitgeschickte Felder aendern“) — das Zurueckholen MUSS aber genau
    # auf NULL setzen.
    with _sitzung_begin() as sess:
        model = model_for(doctype)
        obj = sess.get(model, name)
        if obj is None:
            return False
        if getattr(obj, GELOESCHT_AM) is None:
            return False
        obj.geloescht_am = None
        obj.geloescht_von = None
    return True


def ablaufzeitpunkt() -> datetime:
    """Zeitpunkt, vor dem geloeschte Zeilen endgueltig entfernt werden."""
    return datetime.now().replace(microsecond=0) - timedelta(days=AUFBEWAHRUNG_TAGE)


def bild_datei_entfernen(wert: Any) -> None:
    """Bild-Datei einer geloeschten Zeile entfernen (nach der Loeschlogik).

    Der Datenbankwert ist eine Datei-URL (``/files/x.png``) oder ein
    Dateiname; entfernt wird ueber ``files.stored_path`` — dieselbe Pruefung
    wie beim Ausliefern (kein Pfad, kein ``..``, kein Symlink, kein Ausbruch
    aus dem Ordner). Ein Altbestandswert ohne Datei bleibt folgenlos.
    Fehler werden protokolliert, nicht geworfen: die Zeile muss weg, auch
    wenn die Datei schon fehlt.
    """
    from diakronos_app import files

    roh = str(wert or "").strip()
    if not roh:
        return
    dateiname = roh.rsplit("/", 1)[-1]
    try:
        pfad = files.stored_path(dateiname)
        if pfad is not None:
            pfad.unlink()
    except Exception as fehler:  # noqa: BLE001 — kein Grund, das Aufraeumen zu stoppen
        logger.warning("Papierkorb: Bild %r nicht entfernt (%s)", dateiname, fehler)


def _endgueltig_beitrag(name: str) -> None:
    """Beitrag endgueltig entfernen — Kommentare und Bild mit.

    UX2b2 (F2): ``beitrag_kommentar`` traegt Personendaten (Autor, Text). Beim
    endgueltigen Loeschen des Beitrags muessen sie mit weg — sonst ueberlebte
    der Inhalt die Loeschfrist. ``_delete_doc`` raeumt die Kind-Tabelle in
    derselben Transaktion (dieselbe Logik wie der generische CRUD); hier wird
    nur noch das Bild nachgezogen.
    """
    from diakronos_app.frappe_compat.api_helpers import _delete_doc
    from diakronos_app.frappe_compat.query import get_value

    bild = get_value("Beitrag", name, "bild")
    _delete_doc("Beitrag", name)
    bild_datei_entfernen(bild)


#: Verweise auf ``element.name`` und was beim endgueltigen Loeschen passiert.
#: ``None`` = Verweis auf NULL setzen (die Zeile bleibt, der Bezug faellt).
#: Ein DocType hier ohne Eintrag waere ein stiller Fremdschluessel-Fehler —
#: deshalb steht die Liste vollstaendig (siehe ``test_ux2b2_*``).
_ELEMENT_VERWEISE_NULL: tuple[str, ...] = (
    "Ablaufplan",           # ablaufplan.element            — Plan bleibt bestehen
    "Dienstplan Termin",    # dienstplan_termin.element     — Dienst bleibt bestehen
    "Anmeldung",            # anmeldung.element             — Anmeldung bleibt bestehen
    "Registrierungslink",   # registrierungslink.element    — Link bleibt, Bezug faellt
)


def _endgueltig_element(name: str) -> None:
    """Termin endgueltig entfernen — Verweise loesen, dann die vorhandene Logik.

    Was auf ``element.name`` zeigt, wird VOR dem Loeschen geloest (die Zeilen
    selbst bleiben, nur der Verweis faellt):

      * ``ablaufplan.element``, ``dienstplan_termin.element`` -> NULL (der
        Verweis ist Beiwerk; der Plan bleibt als Fachvorgang bestehen),
      * ``anmeldung.element`` -> NULL (die ANMELDUNG bleibt, nur der Termin
        ist weg — dieselbe Richtung wie bei der DSGVO-Neutralisierung),
      * ``registrierungslink.element`` -> NULL (UX2b2/F2: der Link bleibt
        nutzbar, er zeigt nur auf keinen Termin mehr).

    ``element_aenderung`` haengt per ``ON DELETE CASCADE`` am Termin und geht
    mit der Zeile (``_delete_doc``). Alles in EINER Transaktion: entweder ist
    der Termin samt geloester Verweise weg oder nichts passiert (F4).

    UX2b3: der Loeschaufruf steht INNERHALB von ``_sitzung_begin()``. Frueher
    committete der Verweis-Block allein und ``_delete_doc`` lief danach in
    einer eigenen Transaktion — schlug das Loeschen fehl, standen die
    Referenzen bereits auf NULL (Anmeldung ohne Termin, obwohl der Termin
    noch da war). ``_delete_doc`` committet eine GELIEHENE Sitzung nur
    (``_abschluss`` -> ``flush``); der Commit des Blocks macht beides
    gemeinsam fest, ein Fehler rollt beides zurueck.
    """
    from sqlalchemy import update

    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.frappe_compat.api_helpers import _delete_doc
    from diakronos_app.frappe_compat.registry_gen import model_for

    with _sitzung_begin() as sess:
        with als_aktuelle_sitzung(sess):
            for doctype in _ELEMENT_VERWEISE_NULL:
                model = model_for(doctype)
                sess.execute(update(model).where(model.element == name).values(element=None))
            # Loeschen in DERSELBEN Sitzung: `als_aktuelle_sitzung` laesst
            # `sitzung_fuer_lesen` (aus `diakronos_app.db`) die geliehene
            # Sitzung liefern, `_delete_doc` committet sie dann nicht selbst
            # (`_abschluss` -> flush). Der Commit unten ist der EINE Commit.
            _delete_doc("Element", name)


#: Verweise auf ``gruppe.name`` (UX2b2/F2, vollstaendig per grep ueber die
#: Modelle). Alle sind ``nullable`` — es gibt keinen fachlichen Grund, eine
#: Zeile zu loeschen, nur weil ihre Gruppe verschwindet.
_GRUPPE_VERWEISE_NULL: tuple[str, ...] = (
    "Anmeldung",                 # anmeldung.gruppe
    "Dienstplan",                # dienstplan.gruppe
    "Dienstplan Position",       # dienstplan_position.gruppe
    "Dienstplan Vorlage Gruppe", # dienstplan_vorlage_gruppe.gruppe
    "Element",                   # element.gruppe (Termin ohne Gruppe)
    "Gruppe",                    # gruppe.obergruppe (Untergruppe ohne Eltern)
    "Gruppen Ankuendigung",      # gruppen_ankuendigung.gruppe
    "Untergruppe",               # untergruppe.gruppe
    "Ablaufplan Position",       # ablaufplan_position.gruppe
    "Lied Gruppenzuordnung",     # lied_gruppenzuordnung.gruppe
    "Liedfassung",               # liedfassung.gruppe
)

#: Verweise auf ``gruppe.name``, deren Zeile MIT der Gruppe geht.
#: ``liedgruppe`` ist selbst eine Gruppe (Sammlung von Liedern) — sie hat ohne
#: die Gruppe keinen Inhalt mehr; ihre Zuordnungszeilen haengen ueber
#: ``parent`` daran und gehen mit (Kaskade der Gruppe auf sich selbst bleibt
#: aus, deshalb raeumt ``_endgueltig_gruppe`` die ``liedgruppe_lied``-Zeilen).
_GRUPPE_VERWEISE_LOESCHEN: tuple[str, ...] = (
    "Liedgruppe",                # liedgruppe.gruppe
    # R-7b: eine Aufgabe ohne Gruppe ist eine EIGENE Aufgabe ihres Erstellers —
    # Gruppenaufgaben gehen deshalb mit der Gruppe, statt privat zu werden.
    "Gruppen Aufgabe",           # gruppen_aufgabe.gruppe
)


def _endgueltig_gruppe(name: str) -> None:
    """Gruppe endgueltig entfernen — ALLE Verweise loesen (UX2b2/F2).

    Vorher scheiterte das unter PostgreSQL an Fremdschluesseln: eine Gruppe ist
    oft die ``obergruppe`` anderer Gruppen, hat Liedzuordnungen, Dienstplaene,
    Aufgaben, Ankuendigungen und Termine, die auf sie zeigen. Die Fachlogik
    (``_GRUPPE_VERWEISE_NULL``/``_GRUPPE_VERWEISE_LOESCHEN``) entscheidet je
    Verweis: NULL setzen, wo die Zeile ohne Gruppe weiterlebt, loeschen, wo
    die Zeile ohne Gruppe nichts mehr bedeutet.

    Die eigenen Kind-Zeilen (``gruppenmitgliedschaft``,
    ``gruppe_verantwortlicher``) gehen mit. Alles in EINER Transaktion (F4).
    """
    from sqlalchemy import delete, select, update

    from diakronos_app.frappe_compat.query import get_value
    from diakronos_app.frappe_compat.registry_gen import model_for

    bild = get_value("Gruppe", name, "bild")
    sess = _sitzung()
    try:
        with sess.begin():
            # 1) Zeilen, die MIT der Gruppe verschwinden (vor dem Loesen der
            #    Verweise, damit ihre eigenen Bezuege mit aufgeraeumt werden).
            for doctype in _GRUPPE_VERWEISE_LOESCHEN:
                model = model_for(doctype)
                if doctype == "Liedgruppe":
                    zuordnung = model_for("Liedgruppe Lied")
                    unter = select(model.name).where(model.gruppe == name)
                    sess.execute(
                        delete(zuordnung).where(zuordnung.parent.in_(unter))
                    )
                sess.execute(delete(model).where(model.gruppe == name))

            # 2) Verweise loesen.
            for doctype in _GRUPPE_VERWEISE_NULL:
                model = model_for(doctype)
                spalte = model.obergruppe if doctype == "Gruppe" else model.gruppe
                sess.execute(update(model).where(spalte == name).values(
                    **{spalte.key: None}
                ))

            # 3) Eigene Kind-Zeilen und die Zeile selbst.
            for doctype in ("Gruppenmitgliedschaft", "Gruppe Verantwortlicher"):
                kind = model_for(doctype)
                sess.execute(delete(kind).where(kind.parent == name))
            # R-11d: das EINE Rechtesystem — Rollen, Module und Gruppen-
            # Freigaben gehen mit; Objekte der Gruppe werden zu Gemeinde-
            # Objekten (nur Admin/Fachverwaltung, fail closed), Aufgaben-
            # Objekte verschwinden mit ihren Aufgaben.
            from diakronos_app.models.rechte import (
                RechteFreigabe, RechteGastlink, RechteGruppenrolle, RechteModul, RechteObjekt,
            )

            for modell in (RechteGruppenrolle, RechteModul, RechteFreigabe):
                sess.execute(delete(modell).where(modell.gruppe == name))
            aufgaben = select(RechteObjekt.objekt).where(
                RechteObjekt.gruppe == name, RechteObjekt.typ == "aufgabe")
            for modell in (RechteFreigabe, RechteGastlink):
                sess.execute(delete(modell).where(
                    modell.typ == "aufgabe", modell.objekt.in_(aufgaben)))
            sess.execute(delete(RechteObjekt).where(
                RechteObjekt.gruppe == name, RechteObjekt.typ == "aufgabe"))
            sess.execute(update(RechteObjekt).where(RechteObjekt.gruppe == name).values(gruppe=None))
            sess.execute(model_for("Gruppe").__table__.delete().where(
                model_for("Gruppe").name == name
            ))
    finally:
        sess.close()
    bild_datei_entfernen(bild)


def _endgueltig_wiki(name: str) -> None:
    from diakronos_app.frappe_compat.registry_gen import model_for

    model = model_for("Wiki Artikel")
    with _sitzung_begin() as sess:
        sess.execute(model.__table__.delete().where(model.name == name))


def _endgueltig_lied(name: str) -> None:
    """Lied endgueltig entfernen — Strophen, Fassungen, Zuordnungen, Material.

    Reihenfolge von unten nach oben: Material der Fassungen, Fassungen,
    Kind-Zeilen des Liedes, dann die Zeile selbst. Alles in EINER Transaktion
    (UX2b2/F4) — ein Fehler laesst kein halb geloeschtes Lied zurueck.
    """
    from sqlalchemy import delete, select

    from diakronos_app.frappe_compat.registry_gen import model_for

    fassungen = model_for("Liedfassung")
    with _sitzung_begin() as sess:
        fassungsnamen = list(
            sess.execute(
                select(fassungen.name).where(fassungen.lied == name)
            ).scalars().all()
        )
        if fassungsnamen:
            material = model_for("Lied Material")
            sess.execute(delete(material).where(material.parent.in_(fassungsnamen)))
            sess.execute(delete(fassungen).where(fassungen.lied == name))
        for doctype, parentfield in (
            ("Liedstrophe", "strophen"),
            ("Lied Gruppenzuordnung", "gruppen"),
            ("Lied Kategorie", "kategorien"),
            ("Lied Anlass", "anlaesse"),
        ):
            kind = model_for(doctype)
            sess.execute(delete(kind).where(kind.parent == name, kind.parentfield == parentfield))
        # Liedgruppen: die Zeile der Zuordnung faellt weg, die Gruppe bleibt.
        in_gruppe = model_for("Liedgruppe Lied")
        sess.execute(delete(in_gruppe).where(in_gruppe.lied == name))
        lied = model_for("Lied")
        sess.execute(delete(lied).where(lied.name == name))


_ENDGUELTIG = {
    "Beitrag": _endgueltig_beitrag,
    "Element": _endgueltig_element,
    "Gruppe": _endgueltig_gruppe,
    "Wiki Artikel": _endgueltig_wiki,
    "Lied": _endgueltig_lied,
}


def _sitzung():
    """Kurze Schreib-Sitzung (siehe ``db.SessionLocal``)."""
    from diakronos_app.db import SessionLocal

    return SessionLocal()


@contextmanager
def _sitzung_begin():
    """Kurze Schreib-Sitzung MIT eigener Transaktion (UX2b2/F4).

    ``with SessionLocal.begin()``: alles im Block wird EIN Commit, bei einem
    Fehler EIN Rollback — keine halb geloesten Verweise, keine offene Sitzung
    (der Block schliesst die Sitzung auch im Fehlerfall).
    """
    from diakronos_app.db import SessionLocal

    with SessionLocal.begin() as sess:
        yield sess


def endgueltig_entfernen(doctype: str, name: str) -> None:
    """Zeile wirklich weg — mit allem, was an ihr haengt."""
    _ENDGUELTIG[doctype](name)


def aufraeumen(*, jetzt: datetime | None = None) -> int:
    """Alle abgelaufenen Papierkorb-Zeilen endgueltig entfernen.

    Rueckgabe: Anzahl entfernte Zeilen. Fehler in EINEM Bereich halten die
    anderen nicht auf (jede Zeile einzeln versucht); protokolliert wird.

    ``jetzt`` dient dem Test (Zeitsimulation) — im Betrieb gilt die Uhr.
    """
    from diakronos_app.frappe_compat.query import get_all

    grenze = (jetzt or datetime.now().replace(microsecond=0)) - timedelta(days=AUFBEWAHRUNG_TAGE)
    anzahl = 0
    for doctype in BEREICHE:
        zeilen = get_all(
            doctype,
            filters=[[GELOESCHT_AM, "is", "set"], [GELOESCHT_AM, "<=", grenze]],
            fields=["name"],
        ) or []
        for zeile in zeilen:
            try:
                endgueltig_entfernen(doctype, zeile["name"])
            except Exception:  # noqa: BLE001 — naechste Zeile weiter
                logger.exception(
                    "Papierkorb: %s %r nicht entfernt", doctype, zeile.get("name")
                )
                continue
            anzahl += 1
    return anzahl


__all__ = [
    "AUFBEWAHRUNG_TAGE",
    "BEREICHE",
    "GELOESCHT_AM",
    "GELOESCHT_VON",
    "nicht_geloescht_ist",
    "nur_aktive_filter",
    "ist_geloescht",
    "loeschen",
    "wiederherstellen",
    "ablaufzeitpunkt",
    "endgueltig_entfernen",
    "aufraeumen",
]
