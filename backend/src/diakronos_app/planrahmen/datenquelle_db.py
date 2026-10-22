"""DB-Adapter fuer das ``Datenquelle``-Protokoll des Plan-Rahmens (PR4, P4a).

Die Engine (``engine/datenquelle.py``) arbeitet ausschliesslich auf
In-Memory-Daten (P8). Dieser Adapter ist die eine Stelle, an der diese Daten
aus der Datenbank kommen: :class:`DBDatenquelle` laedt beim Konstruieren
**gebuendelt** (wenige ORM-Abfragen, keine N+1) und delegiert danach alle
Protokoll-Methoden an eine vorgeladene :class:`InMemoryDatenquelle`. Die
Session wird nur waehrend des Konstruierens benoetigt — danach arbeitet die
Quelle rein im Speicher.

Konstruktion (von den Planrahmen-Diensten genutzt)::

    quelle = DBDatenquelle(session, plantyp="chorplan",
                           plan_id=plan_id, veranstaltung=element_id)

``plan_id`` ist die Kennung (``pr_plan.id``) des Plans, fuer den die Engine
arbeitet (oder ``None``); ``plantyp`` ist der **Schluessel**
(``pr_plantyp.schluessel``, nie die UUID); ``veranstaltung`` ist die
Kronos-``element``-Kennung einer Veranstaltung, auf die sich Anmeldungen
beziehen (leer = keine Bindung). Alle drei Bindungen steuern fail-closed-
Zuordnungen, siehe unten.

Zuordnung (P4-Karte a) und fail-closed-Regeln — nichts wird geraten:

* **Personen** = ``mitglied`` (``docstatus < 2``). ``kennung`` ist
  ``mitglied.name``; ``name`` ist der Anzeigename ``Vorname Nachname``
  (Fallback: Nachname, Vorname, zuletzt der Dokument-Name). ``kuerzel`` bleibt
  leer — die Modelle kennen kein Kuerzel-Feld (geprueft: models/, api/);
  wer es braucht, fuehrt ein Merkmal ``kuerzel`` ein. Mitglieder mit
  ``status='Ausgetreten'`` oder ``ausgeschlossen`` werden NICHT still
  ausgefiltert: die bestehende API kennt keinen einheitlichen
  Standard-Filter dafuer (api/mitglieder.py), der Ausschluss waere geraten.
* **Merkmale** = ``pr_merkmal`` (``ziel='person'``) + ``pr_merkmal_wert``.
  Werte sind JSON; skalar bleibt skalar, ein Dict mit genau dem Schlüssel
  ``wert`` wird auf diesen Wert entpackt (Schreibkonvention der
  Merkmal-Dienste), alles andere bleibt unveraendert. Werte ohne passenden
  Merkmals-Host (z. B. verwaistes Mitglied) fallen weg.
* **Gruppen** = ``gruppe`` + ``gruppenmitgliedschaft``, gueltig nur bei
  ``parenttype='Gruppe'`` UND ``parentfield='mitglieder'`` (und
  ``docstatus < 2``); ``obergruppe`` kommt aus ``gruppe.obergruppe``.
  ``pflicht_mitglieder`` bleibt ``None``: das Datenmodell hat kein Feld fuer
  Pflicht-Mitgliedschaften (``gruppenmitgliedschaft.rolle`` zu raten waere
  fail-open) — die Team-Regel behandelt ``None`` korrekt als "unbekannt".
* **Anmeldungen** = ``anmeldung`` + ``anmeldung_antwort``. Die bestehende
  API kennt den Anmeldestatus ``"Bestätigt"`` (api/admin_hub.py;
  ``"Anmeldeanfrage"``/``"Abgelehnt"`` sind Alt-Status, api/cleanup.py); ein
  Status ``"angenommen"`` existiert dort NICHT und wird deshalb nicht als
  Bestaetigung gelesen — nur die Konstante :data:`ANMELDUNG_BESTAETIGTE_STATUS`
  wuerde ihn aufnehmen, falls er eingefuehrt wird. Die Rolle kommt
  **ausschliesslich** aus einer expliziten Antwort ``feldlabel='rolle'``
  (``antwort`` = Rollen-Kennung, z. B. ``mitarbeiter``) derselben Anmeldung;
  ``antwort`` und ``element`` (Veranstaltungs-Kennung) werden uebernommen.
  Anmeldungen ohne solche Antwort oder ohne ``mitglied`` liefern niemanden —
  es wird **keine** Mitarbeiterrolle geraten (Konzept B4: ``{anmeldung: ...}``
  ist ein expliziter Filter, kein Default). Mit Bindung ``veranstaltung``
  werden nur Anmeldungen dieser Veranstaltung geladen; ein leerer
  ``veranstaltung``-Argument im ``anmeldungen()``-Aufruf nutzt dann die
  Bindung.
* **Sammlung 'lieder'** = aktive ``lied``-Datensaetze (``aktiv``,
  ``docstatus < 2``) plus Merkmalswerte mit
  ``pr_merkmal.ziel='sammlung:lieder'`` (``ziel_id`` = ``lied.name``).
  Eingebaute Attribute: ``titel``, ``alternativtitel``,
  ``gesangbuch_nummer`` mit Aliassen ``nr``/``nummer``, ``ccli_nummer`` mit
  Alias ``ccli``, ``zuletzt_gesungen``, ``anzahl_gesungen``; ``buch`` bleibt
  leer und ``seite`` fehlt, weil das Lied-Modell diese Spalten nicht hat.
  Existiert zusaetzlich eine ``pr_sammlung``-Zeile ``'lieder'``, wird ihre
  Eintragsliste ignoriert (die Lied-Tabelle ist die Quelle), ihre Merkmale
  gelten weiter.
* **Eigene Sammlungen** = ``pr_sammlung`` + aktive ``pr_sammlung_eintrag``;
  ``kennung`` ist die Eintrags-ID, ``titel`` kommt aus ``daten['titel']``,
  ``daten`` wird als ``attribute`` mitgefuehrt (dazu ``titel``/``reihenfolge``
  als setdefault). **Umfang** (Review PR1: ``gemeinde``/``plan``): die
  Spalten ``umfang``/``plan`` werden vom PR4-Nachtrag an ``pr_sammlung``
  ergaenzt; bis dahin liest der Adapter die Schlüssel defensiv aus
  ``definition`` (Spalte hat Vorrang). ``umfang='plan'`` liefert die Sammlung
  nur, wenn ihre ``plan``-Kennung der Bindung ``plan_id`` entspricht;
  unbekannte Umfange und ungebundene Plansammlungen fallen aus (fail-closed).
  Teilen Gemeinde- und planbezogene Sammlung denselben ``schluessel`` und
  beide sind sichtbar, hat die **planbezogene Fassung deterministisch
  Vorrang** (die Reihenfolge der Zeilen waere sonst zufaellig).
* **Abwesenheiten** = ``pr_abwesenheit``; ``nur_plantyp`` (Schluessel) muss
  zur Bindung ``plantyp`` passen, sonst wird die Zeile nicht geliefert
  (ohne Bindung bleiben nur plantyp-ungebundene Zeilen sichtbar).
* **Historie** = ``pr_eintrag`` frueherer Termine **aller** Plaene (Karte a),
  mit ``plantyp`` als **Schluessel** des Plantyps (Aufloesung ueber
  ``pr_plantyp.schluessel``; eine UUID-Angabe in ``plantyp`` findet nichts,
  weil die Engine nur Schlüssel kennt). Der eigene, gebundene Plan
  (``plan_id``) ist ausgeschlossen (eine Historie gegen sich selbst waere
  falsch). Listen-Werte (Mehrplatz-Slots) werden pro Wert zu einem Eintrag
  entfaltet, damit Abstandsregeln je Person/Lied greifen; ``feld='*'`` und
  die ``feld_pfad``-Normalisierung ueber ``pfade.passt_zu_feld`` uebernimmt
  die InMemory-Quelle.
  **Gleiche Sammlung (Version/Slots):** ist ein Plan gebunden und hat sein
  Plantyp eine gueltige Version, wird fuer Eintraege **dieses Plantyps**
  geprueft, dass das historische Feld zur selben Sammlung gehoert wie das
  aktuelle Feld: die aktive Definition (``gueltige_version_zu_datum`` des
  gebundenen Plantyps, Parameter des gebundenen Plans) und die zum
  historischen Termin fixierte Version (``pr_termin.plantyp_version``,
  Parameter des historischen Plans) werden je ueber
  ``struktur.aufloesen_mit_eintraegen`` in Slots aufgeloest; das
  ``eintrag``-Slot ``sammlung`` muss (nach Parameter-Aufloesung)
  übereinstimmen. Weicht es ab (alte Version ``a``, aktuell ``b``), faellt
  der Historie-Eintrag heraus — ein Lied aus einer anderen Sammlung darf
  den Mindestabstand eines anderen Feldes nicht zaehlen. Felder ohne
  Sammlung (person/text/...) und **alle anderen Plantypen** bleiben
  planuebergreifend uneingeschraenkt lesbar. Fail-closed-Grenzen: fehlt die
  zum Termin fixierte Version oder laesst sich das Feld dort nicht
  auflösen, wird der Eintrag NICHT geliefert (nicht verifizierbar);
  existiert im System noch gar keine Version, gibt es nichts zu pruefen
  und die Historie bleibt vollstaendig. Ablauf-Felder
  (``ablauf/<id>...``) tragen in ``pr_termin`` keine Metadaten und
  entgehen der Pruefung (Protokoll-Grenze, dokumentiert).
* **Kalender** = ``element``-Dokumente mit ``status='Festgelegt'`` — genau
  die Freigabe des bestehenden Kalender-Endpunkts
  (api/kronos/kalender.py ``get_events``; ``Vorschlag``/``Konflikt``/
  ``Angefragt`` sind nicht freigegeben). Ausgeliefert werden **nur** die
  oeffentlich sichtbaren Felder (Titel, Datum/Uhrzeit, Kategorie, Gruppe);
  Beschreibungen, Teilnehmer, Mitarbeiter, Ressourcen und Anmeldeschluessel
  bleiben privat und werden hier nicht gelesen (DSGVO).

Alle Abfragen laufen beim Konstruieren gebuendelt ueber Selects (je
Tabellengruppe eine Abfrage inklusive Joins) — kein Protokoll-Aufruf greift
mehr auf die DB zu.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.models.diakonos import (
    Anmeldung,
    AnmeldungAntwort,
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.kronos import Element
from diakronos_app.models.psalmos import Lied
from diakronos_app.models.planrahmen import Abwesenheit as PrAbwesenheit
from diakronos_app.models.planrahmen import Merkmal as PrMerkmal
from diakronos_app.models.planrahmen import MerkmalWert as PrMerkmalWert
from diakronos_app.models.planrahmen import Plan as PrPlan
from diakronos_app.models.planrahmen import Plantyp as PrPlantyp
from diakronos_app.models.planrahmen import PlantypVersion as PrPlantypVersion
from diakronos_app.models.planrahmen import Sammlung as PrSammlung
from diakronos_app.models.planrahmen import SammlungEintrag as PrSammlungEintrag

from .engine.datenquelle import (
    Abwesenheit,
    Anmeldung as AnmeldungDaten,
    Datenquelle,
    Gruppe as GruppeDaten,
    Historieneintrag,
    InMemoryDatenquelle,
    Kalendertermin,
    Person,
    Sammlungseintrag,
)
from .engine.modell import Eintrag as EngineEintrag
from .engine.modell import Termin as EngineTermin
from .engine.pfade import feld_basis
from .engine.struktur import aufloesen_mit_eintraegen
from .speicher import gueltige_version_zu_datum

__all__ = [
    "ANMELDUNG_BESTAETIGTE_STATUS",
    "ANMELDUNG_ROLLE_LABEL",
    "DBDatenquelle",
    "KALENDER_FREIGEGEBEN_STATUS",
    "LIEDER_SAMMLUNG",
    "SAMMLUNG_UMFANG_GEMEINDE",
    "SAMMLUNG_UMFANG_PLAN",
]

# --------------------------------------------------------------------------- #
# Konstanten der Zuordnung (fail-closed: wer etwas neu aufnimmt, aendert hier)
# --------------------------------------------------------------------------- #

#: Eingebaute Sammlung aus der ``lied``-Tabelle (Karte a).
LIEDER_SAMMLUNG = "lieder"

#: Nur diese Antwort-Zeile darf eine Rollen-Kennung tragen.
ANMELDUNG_ROLLE_LABEL = "rolle"

#: Bestaetigte Anmeldungen — geprueft gegen die bestehende API:
#: ``api/admin_hub.py`` setzt ``"Bestätigt"``; ``"Anmeldeanfrage"`` und
#: ``"Abgelehnt"`` sind Alt-/Ablehnungs-Status (``api/cleanup.py``). Ein
#: Status ``"angenommen"`` gibt es dort nicht (Stand 2026-10-08) und wird
#: deshalb bewusst NICHT aufgenommen — sonst muesste diese Konstante
#: erweitert werden, nicht die Logik erraten.
ANMELDUNG_BESTAETIGTE_STATUS = frozenset({"bestätigt"})

#: Kalender-Freigabe des bestehenden Endpunkts api/kronos/kalender.py.
KALENDER_FREIGEGEBEN_STATUS = "Festgelegt"

#: Umfaenge einer ``pr_sammlung`` (Review PR1: gemeinde vs. planbezogen).
SAMMLUNG_UMFANG_GEMEINDE = "gemeinde"
SAMMLUNG_UMFANG_PLAN = "plan"

#: Ziel-Praefix der Merkmale eines Sammlungseintrags (``pr_merkmal.ziel``).
_ZIEL_PRAEFIX_SAMMLUNG = "sammlung:"


# --------------------------------------------------------------------------- #
# kleine Helfer
# --------------------------------------------------------------------------- #


def _skalar(wert: Any) -> Any:
    """Entpackt einen JSON-Merkmalswert zu einem skalaren Wert.

    Skalare (bool/int/float/str/None) bleiben unveraendert. Ein Dict mit
    **genau** dem Schlüssel ``wert`` wird auf diesen Wert entpackt — das ist
    die Schreibkonvention der Merkmal-Dienste. Alles andere (Listen, andere
    Dicts) bleibt unveraendert, damit nichts still verloren geht.
    """
    if isinstance(wert, dict) and set(wert) == {"wert"}:
        return wert["wert"]
    return wert


def _anzeigename(vorname: str, nachname: str, fallback: str) -> str:
    """Anzeigename ``Vorname Nachname`` mit sinnvollen Fallbacks."""
    voll = " ".join(t for t in (vorname, nachname) if t).strip()
    return voll or nachname or vorname or fallback


def _reihe_aus_pfad(feld_pfad: str, definition: dict[str, Any]) -> str:
    """Terminreihe aus einem Feldpfad- Praefix ('probe:team' -> 'probe')."""
    if ":" in feld_pfad:
        praefix = feld_pfad.split(":", 1)[0]
        for reihe in definition.get("terminreihen") or []:
            if isinstance(reihe, dict) and reihe.get("id") == praefix:
                return praefix
    return "standard"


def _eintrag_slot(slots: list[Any], basis: str) -> Any | None:
    """Das ``eintrag``-Slot zu einer Feldpfad-Basis (sonst None)."""
    for slot in slots:
        if slot.art == "eintrag" and feld_basis(slot.feld_pfad) == basis:
            return slot
    return None


class _SammlungsPruefung:
    """Prueft historische Eintrag-Felder auf „gleiche Sammlung“ (Version/Slots).

    Fuer den gebundenen Plantyp (Plantyp des ``plan_id``-Plans) wird die
    aktive Definition gegen die zum historischen Termin fixierte Version
    (``pr_termin.plantyp_version``) gestellt: beide werden mit
    ``struktur.aufloesen_mit_eintraegen`` in Slots aufgeloest (Parameter der
    jeweiligen Plaene), und das ``eintrag``-Slot ``sammlung`` muss
    uebereinstimmen. Ergebnis je Feld:

    * ``"identisch"`` — gleiche Sammlung (oder aktuell kein Sammlungs-Feld):
      aufnehmen;
    * ``"verschieden"`` — andere Sammlung: ausschliessen;
    * ``"unbestimmt"`` — historisch nicht verifizierbar (keine fixierte
      Version oder Slot nicht auflösbar): fail-closed ausschliessen.
    """

    def __init__(
        self,
        plantyp_schluessel: str,
        definition: dict[str, Any],
        parameter: dict[str, Any],
        versionen: dict[str, dict[str, Any]],
    ) -> None:
        self.plantyp_schluessel = plantyp_schluessel
        self.definition = definition
        self.parameter = parameter
        self.versionen = versionen
        self._aktive_slots: dict[tuple[Any, ...], list[Any]] = {}

    def _slots(
        self,
        cache: dict[tuple[Any, ...], list[Any]],
        schluessel: Any,
        definition: dict[str, Any],
        parameter: dict[str, Any],
        engine_termin: EngineTermin,
        engine_eintraege: list[EngineEintrag],
    ) -> list[Any] | None:
        """Slots je (Definition, Termin) cachen; None bei defekter Definition."""
        key = (schluessel, engine_termin.datum, engine_termin.reihe,
               engine_termin.anlaesse)
        if key not in cache:
            try:
                cache[key] = aufloesen_mit_eintraegen(
                    definition, engine_termin, engine_eintraege,
                    parameter=parameter,
                )
            except Exception:  # noqa: BLE001 — defekte Definition: nicht liefern
                cache[key] = []
        return cache.get(key)

    def pruefe(
        self,
        feld_pfad: str,
        *,
        datum: date,
        anlaesse: frozenset[str],
        engine_eintraege: list[EngineEintrag],
        historische_version: str | None,
        historische_parameter: dict[str, Any],
    ) -> str:
        """Bewertet einen historischen Feldpfad (siehe Klassen-Docstring)."""
        basis = feld_basis(feld_pfad)
        engine_termin = EngineTermin(datum, _reihe_aus_pfad(feld_pfad, self.definition),
                                     anlaesse=anlaesse)
        aktive = self._slots(self._aktive_slots, "aktiv", self.definition,
                             self.parameter, engine_termin, engine_eintraege)
        slot = _eintrag_slot(aktive or [], basis)
        if slot is None or not slot.sammlung:
            return "identisch"  # aktuell kein Sammlungs-Feld -> kein Bezug
        definition_h = self.versionen.get(historische_version or "")
        if definition_h is None:
            return "unbestimmt"  # keine fixierte Version -> nicht verifizierbar
        historische = self._slots({}, historische_version, definition_h,
                                  historische_parameter, engine_termin,
                                  engine_eintraege)
        slot_h = _eintrag_slot(historische or [], basis)
        if slot_h is None or not slot_h.sammlung:
            return "unbestimmt"
        return "identisch" if slot_h.sammlung == slot.sammlung else "verschieden"


# --------------------------------------------------------------------------- #
# DB-Adapter
# --------------------------------------------------------------------------- #


def kuerzel_aus_name(vorname: str, nachname: str) -> str:
    """Alltagskuerzel einer Person fuer Formatvorlagen (UXP-R3).

    Das Datenmodell hat kein Kuerzel-Feld; die Formatvorlagen der
    Kochbuch-Plantypen nutzen aber ``{dirigent.kuerzel}`` — mit einem immer
    leeren Attribut standen Dirigent und Klavier nie im Chorplan. Deshalb
    wird das Kuerzel aus dem Namen abgeleitet („D. Krüger“). Fehlen beide
    Namensteile, bleibt es leer (fail-closed, kein erfundener Wert).
    """
    vorname = (vorname or "").strip()
    nachname = (nachname or "").strip()
    if vorname and nachname:
        return f"{vorname[0]}. {nachname}"
    return nachname or vorname


class DBDatenquelle:
    """Datenquelle des Plan-Rahmens aus der Datenbank (Protokoll-konform).

    Implementiert das ``Datenquelle``-Protokoll aus
    ``engine/datenquelle.py`` durch **gebuendeltes Vorladen**: beim
    Konstruieren werden alle benoetigten Tabellen in je einer Abfrage
    (inkl. Joins) gelesen und in eine :class:`InMemoryDatenquelle`
    ueberfuehrt; jede Protokoll-Methode liest danach nur noch aus dem
    Speicher. Damit bleibt die Engine frei von DB-Zugriffen (P8) und die
    Anfrage-Zahl ist konstant (keine N+1).

    Parameter
    ----------
    session:
        Offene SQLAlchemy-Session; sie wird nur waehrend des Konstruierens
        benoetigt und vom Aufrufer verwaltet (diese Klasse committet nichts).
    plantyp:
        **Schluessel** des Plantyps (``pr_plantyp.schluessel``, z. B.
        ``"chorplan"``) oder ``None``. Steuert den Plantyp-Filter der
        ``pr_abwesenheit``-Zeilen (``nur_plantyp``). Eine UUID wird hier
        bewusst nicht akzeptiert — die Engine argumentiert mit Schlüsseln.
    plan_id:
        Kennung des laufenden Plans (``pr_plan.id``) oder ``None``. Steuert
        (a) den Ausschluss der Historie gegen sich selbst und (b) die
        Sichtbarkeit planbezogener Sammlungen (``umfang='plan'``).
    veranstaltung:
        Kennung der Veranstaltung (``element.name``) oder ``""``. Bindet die
        Anmeldungen auf diese Veranstaltung; ein leeres
        ``veranstaltung``-Argument im ``anmeldungen()``-Aufruf nutzt dann
        die Bindung.
    pool_gruppen:
        Gebundene Gruppen der Planvorlage (ST3, ``pr_plantyp_version.definition
        ['gruppen']``) oder ``None``/leer. Ist eine Menge gesetzt, kommen als
        Personen **nur** Mitglieder dieser Gruppen in Frage (PERSONENPOOL);
        alles andere (Personenliste, Abwesenheiten) wird serverseitig zentral
        hier eingeschraenkt — nicht in jeder Komponente. Leer = bisheriges
        Verhalten (alle Personen).
    pool_inkl_untergruppen:
        true = Mitglieder aller Untergruppen der gebundenen Gruppen zaehlen
        mit. Nur wirksam, wenn ``pool_gruppen`` gesetzt ist. Untergruppe =
        eine Gruppe, deren ``obergruppe`` (ggf. transitiv) eine gebundene
        Gruppe ist.

    Fail-closed-Details und dokumentierte Grenzen stehen im Modul-Docstring.
    """

    def __init__(
        self,
        session: Session,
        *,
        plantyp: str | None = None,
        plan_id: str | None = None,
        veranstaltung: str = "",
        pool_gruppen: frozenset[str] | tuple[str, ...] | None = None,
        pool_inkl_untergruppen: bool = False,
    ) -> None:
        self.plantyp = plantyp
        self.plan_id = plan_id
        self.veranstaltung = veranstaltung
        self.pool_gruppen = frozenset(pool_gruppen or ())
        self.pool_inkl_untergruppen = bool(pool_inkl_untergruppen)

        merkmale_person, merkmale_sammlung = self._merkmale_laden(session)
        gruppen_liste = self._gruppen_laden(session)
        pool_mitglieder = self._pool_mitglieder(gruppen_liste)
        personen_liste = self._personen_laden(session, merkmale_person, gruppen_liste)
        anmeldungen_liste = self._anmeldungen_laden(session)
        sammlungen = self._sammlungen_laden(session, merkmale_sammlung)
        abwesenheiten_liste = self._abwesenheiten_laden(session)
        historie_liste = self._historie_laden(session)
        # Die Kalendertermine sind auf den LESE-/Arbeitsseiten (Plan oeffnen,
        # Stammdaten, Kandidaten) nie noetig und kosten eine eigene Abfrage
        # ueber alle freigegebenen Elemente. Sie werden deshalb erst beim
        # ersten Zugriff geladen (siehe ``_kalender`` und ``kalender_termine``).
        self._session = session
        self._kalender_liste: list[Kalendertermin] | None = None

        # ST3-PERSONENPOOL: eine zentrale Einschraenkung hier (nicht in jeder
        # Komponente). Ohne gebundene Gruppen bleibt alles unveraendert.
        if self.pool_gruppen:
            personen_liste = [p for p in personen_liste if p.kennung in pool_mitglieder]
            abwesenheiten_liste = [a for a in abwesenheiten_liste if a.person in pool_mitglieder]

        self._quelle = InMemoryDatenquelle(
            personen_liste=personen_liste,
            gruppen_liste=gruppen_liste,
            anmeldungen_liste=anmeldungen_liste,
            sammlungen=sammlungen,
            abwesenheiten_liste=abwesenheiten_liste,
            historie_liste=historie_liste,
            kalender_liste=[],
        )

    def _kalender(self) -> list[Kalendertermin]:
        """Kalendertermine erst beim ersten Zugriff laden (Lazy-Cache)."""
        if self._kalender_liste is None:
            self._kalender_liste = self._kalender_laden(self._session)
        return self._kalender_liste

    def _pool_mitglieder(self, gruppen_liste: list[GruppeDaten]) -> frozenset[str]:
        """Mitglieds-Kennungen des Personenpools (ST3).

        Ohne gebundene Gruppen: alle Mitglieder aller Gruppen (die Pool-Menge
        wird dann ohnehin nicht angewandt). Mit ``inkl_untergruppen`` werden
        die Mitglieder aller (transitiv) untergeordneten Gruppen mitgezaehlt.
        Die Aufloesung nutzt ``obergruppe``; Zyklen werden abgesichert.
        """
        if not self.pool_gruppen:
            return frozenset()
        nach_kennung = {g.kennung: g for g in gruppen_liste}
        if not self.pool_inkl_untergruppen:
            ziel = set(self.pool_gruppen)
        else:
            ziel = set(self.pool_gruppen)
            geaendert = True
            while geaendert:
                geaendert = False
                for g in gruppen_liste:
                    if g.kennung in ziel:
                        continue
                    if g.obergruppe and g.obergruppe in ziel:
                        ziel.add(g.kennung)
                        geaendert = True
        mitglieder: set[str] = set()
        for kennung in ziel:
            g = nach_kennung.get(kennung)
            if g is not None:
                mitglieder.update(g.mitglieder)
        return frozenset(mitglieder)

    # -- gebuendelte Lade-Abfragen (je Tabellengruppe eine Abfrage) ---------- #

    def _merkmale_laden(
        self, session: Session
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
        """Liest alle Merkmalswerte (1 Abfrage mit Join auf ``pr_merkmal``).

        Rueckgabe: ``(personen_merkmale, sammlungs_merkmale)`` —
        ``personen_merkmale[mitglied.name][schluessel] = Wert`` und
        ``sammlungs_merkmale[sammlung][ziel_id][schluessel] = Wert`` fuer
        ``ziel='person'`` bzw. ``ziel='sammlung:<schluessel>'``. Werte ohne
        passenden Host werden spaeter verworfen (fail-closed).
        """
        wert_zeilen = session.execute(
            select(
                PrMerkmalWert.ziel_id,
                PrMerkmal.ziel,
                PrMerkmal.schluessel,
                PrMerkmalWert.wert,
            ).join(PrMerkmal, PrMerkmalWert.merkmal == PrMerkmal.id)
        ).all()

        personen_merkmale: dict[str, dict[str, Any]] = {}
        sammlungs_merkmale: dict[str, dict[str, dict[str, Any]]] = {}
        for ziel_id, ziel, schluessel, wert in wert_zeilen:
            if ziel == "person":
                personen_merkmale.setdefault(ziel_id, {})[schluessel] = _skalar(wert)
            elif ziel.startswith(_ZIEL_PRAEFIX_SAMMLUNG):
                sammlung = ziel[len(_ZIEL_PRAEFIX_SAMMLUNG):]
                sammlungs_merkmale.setdefault(sammlung, {}).setdefault(ziel_id, {})[
                    schluessel
                ] = _skalar(wert)
        return personen_merkmale, sammlungs_merkmale

    def _gruppen_laden(self, session: Session) -> list[GruppeDaten]:
        """Liest Gruppen UND Untergruppen als Teams (UXP-R4).

        Die App pflegt Untergruppen in der eigenen Tabelle ``untergruppe``
        (mit ``gruppe`` als Obergruppe); der Plan-Rahmen loest Teams dagegen
        ueber ``gruppe.obergruppe`` auf. Weil keine Oberflaeche ``obergruppe``
        setzt, war ein Team (Beispiel C3 „Musikteams“) fuer einen Laien nicht
        nachbaubar: ``_kandidaten_fuer`` fand nie ein Team. Deshalb wird hier
        die Bruecke geschlagen: jede aktive Untergruppe wird als Team mit
        ``obergruppe = <Name der zugehoerigen Gruppe>`` geliefert, ihre
        Mitglieder stammen aus ``untergruppenmitgliedschaft``. Gruppen mit
        gesetztem ``obergruppe`` bleiben unveraendert.

        Gueltig sind nur Zeilen mit ``parenttype='Gruppe'`` bzw.
        ``'Untergruppe'`` und ``parentfield='mitglieder'`` (ohne diese
        Pruefung waeren auch fremd-parentete Child-Zeilen Mitgliedschaften).
        """
        gruppen_zeilen = (
            session.execute(
                select(Gruppe).where(Gruppe.docstatus < 2).order_by(Gruppe.name)
            )
            .scalars()
            .all()
        )
        mitgliedschaften = session.execute(
            select(Gruppenmitgliedschaft.parent, Gruppenmitgliedschaft.mitglied).where(
                Gruppenmitgliedschaft.docstatus < 2,
                Gruppenmitgliedschaft.parenttype == "Gruppe",
                Gruppenmitgliedschaft.parentfield == "mitglieder",
                Gruppenmitgliedschaft.mitglied.is_not(None),
            )
        ).all()

        mitglieder_je_gruppe: dict[str, list[str]] = {}
        for parent, mitglied in mitgliedschaften:
            mitglieder_je_gruppe.setdefault(parent, []).append(mitglied)

        gruppen = [
            GruppeDaten(
                kennung=g.name,
                name=g.gruppenname or g.name,
                mitglieder=frozenset(mitglieder_je_gruppe.get(g.name, [])),
                obergruppe=g.obergruppe or "",
                # Kein Datenfeld fuer Pflicht-Mitgliedschaften; die ``rolle``
                # zu raten waere fail-open -> None = "unbekannt".
                pflicht_mitglieder=None,
            )
            for g in gruppen_zeilen
        ]
        gruppen.extend(self._untergruppen_als_teams(session))
        return gruppen

    def _untergruppen_als_teams(self, session: Session) -> list[GruppeDaten]:
        """Aktive Untergruppen als Teams mit ihrer Gruppe als Obergruppe (UXP-R4).

        Die Obergruppe ist der ANZEIGENAME der zugehoerigen Gruppe, denn
        genau den vergleicht ``engine/fuellen.py`` (``slot.teams["gruppe_unter"]``)
        und ``inkl_untergruppen``. Ohne lesbare Referenz bleibt das Team
        trotzdem enthalten (Obergruppe leer) — es faellt dann nur unter keinen
        Gruppenschirm.
        """
        anzeigenamen = {
            g.name: (g.gruppenname or g.name)
            for g in session.execute(select(Gruppe)).scalars().all()
        }
        zeilen = session.execute(
            select(Untergruppe.name, Untergruppe.untergruppenname, Untergruppe.gruppe)
            .where(Untergruppe.docstatus < 2).order_by(Untergruppe.name)
        ).all()
        if not zeilen:
            return []
        mitgliedschaften = session.execute(
            select(Untergruppenmitgliedschaft.parent, Untergruppenmitgliedschaft.mitglied).where(
                Untergruppenmitgliedschaft.docstatus < 2,
                Untergruppenmitgliedschaft.parenttype == "Untergruppe",
                Untergruppenmitgliedschaft.parentfield == "mitglieder",
                Untergruppenmitgliedschaft.mitglied.is_not(None),
            )
        ).all()
        mitglieder_je_untergruppe: dict[str, list[str]] = {}
        for parent, mitglied in mitgliedschaften:
            mitglieder_je_untergruppe.setdefault(parent, []).append(mitglied)
        return [
            GruppeDaten(
                kennung=name,
                name=untergruppenname or name,
                mitglieder=frozenset(mitglieder_je_untergruppe.get(name, [])),
                obergruppe=anzeigenamen.get(gruppe, "") if gruppe else "",
                pflicht_mitglieder=None,
            )
            for name, untergruppenname, gruppe in zeilen
        ]

    def _personen_laden(
        self,
        session: Session,
        merkmale_person: dict[str, dict[str, Any]],
        gruppen_liste: list[GruppeDaten],
    ) -> list[Person]:
        """Liest ``mitglied`` und baut Personen inkl. Merkmalen/Gruppen (1 Abfrage)."""
        mitglieder = (
            session.execute(
                select(Mitglied)
                .where(Mitglied.docstatus < 2)
                .order_by(Mitglied.name)
            )
            .scalars()
            .all()
        )
        gruppen_je_person: dict[str, list[str]] = {}
        for g in gruppen_liste:
            for kennung in g.mitglieder:
                gruppen_je_person.setdefault(kennung, []).append(g.kennung)

        personen: list[Person] = []
        # AUSTRITT A3 / AUSTRITT-b (B4): ZWEI getrennte Fragen.
        #
        #  * ZUTEILBARKEIT — fachlich: wer ausgetreten oder ausgeschlossen ist,
        #    wird NIEMANDEM mehr als Kandidat angeboten (der Admin ebenso
        #    wenig wie der Leser). Sonst aenderte die Rolle still das
        #    Engine-Ergebnis; die Kandidatenmenge ist ein Planeingang, keine
        #    Ansicht.
        #  * ANZEIGE — die Kuerzung des Namens bleibt rollenabhaengig
        #    („Elvira D." fuer Nicht-Admins). Sie beruehrt NUR Textfelder,
        #    nie `gruppen`/`merkmale`.
        from diakronos_app.frappe_compat.personen_anzeige import (
            GELOESCHT_ANZEIGE, PersonenSicht, ist_ausgeschieden, ist_geloescht,
            kuerze_name, maskiere_email,
        )

        sicht = PersonenSicht.aus()

        def _person(vorname: str, nachname: str, kennung: str, email: str,
                    ausgeschieden: bool = False,
                    ausgetreten: bool = False,
                    geloescht: bool = False) -> Person:
            """Eine Person aus der Mitgliedszeile.

            AUSTRITT-e (NR2): ZWEI Fragen, zwei Merkmale.
            ``ausgeschieden`` ist die MARKEN-Frage (Austritt oder Ausschluss)
            und steuert nur die ZUTEILBARKEIT (`personen()` filtert danach).
            ``ausgetreten`` ist das Austrittsmerkmal (`ist_ausgeschieden`) und
            steuert nur die ANZEIGE. Ein Ausschluss bleibt deshalb voll
            sichtbar — wie in `main`.

            DSGVO-2d: Für eine GELOESCHTE Person gibt es genau einen Text
            (``Gelöschte Person``) für alle Rollen — kein „Gelöschte P.“ aus
            einem Rest-Namen, kein Kürzel mit Initialen.
            """
            if geloescht:
                return Person(kennung=kennung, name=GELOESCHT_ANZEIGE,
                              vorname=GELOESCHT_ANZEIGE, nachname="", kuerzel="",
                              email="",
                              merkmale=dict(merkmale_person.get(kennung, {})),
                              gruppen=frozenset(gruppen_je_person.get(kennung, [])),
                              ausgeschieden=True)
            kuerzel = kuerzel_aus_name(vorname, nachname)
            if ausgetreten:
                # Gekuerzter Name (Nicht-Admin); Gruppen bleiben stehen, das
                # Kuerzen darf die Zuteilbarkeit nicht verstecken (frueher:
                # `gruppen=frozenset()` je Rolle).
                # AUSTRITT-d (NB1): Auch das KUERZEL wird gekuerzt. Vorher stand
                # dort „E. Dorn“ — der Klarname der Ausgetretenen ueber einen
                # zweiten Weg (`{dirigent.kuerzel}` in den Formatvorlagen).
                kurz = kuerze_name(vorname, nachname, kennung)
                if sicht.darf_vollstaendig(kennung):
                    kurz = _anzeigename(vorname, nachname, kennung)
                else:
                    kuerzel = f"{vorname[0].upper()}. {nachname[0].upper()}." \
                        if vorname and nachname else kurz
                return Person(kennung=kennung, name=kurz, vorname=kurz,
                              nachname="", kuerzel=kuerzel,
                              email=maskiere_email(email) or "",
                              merkmale=dict(merkmale_person.get(kennung, {})),
                              gruppen=frozenset(gruppen_je_person.get(kennung, [])),
                              ausgeschieden=ausgeschieden)
            name = _anzeigename(vorname, nachname, kennung)
            return Person(kennung=kennung, name=name, vorname=vorname,
                          nachname=nachname, kuerzel=kuerzel, email=email,
                          merkmale=dict(merkmale_person.get(kennung, {})),
                          gruppen=frozenset(gruppen_je_person.get(kennung, [])),
                          ausgeschieden=ausgeschieden)

        for m in mitglieder:
            personen.append(_person(
                m.vorname or "", m.nachname or "", m.name, m.email or "",
                # Zuteilbarkeit: die Marke (Austritt UND Ausschluss).
                ausgeschieden=bool(m.ausgeschlossen),
                # Anzeige: nur das Austrittsmerkmal (AUSTRITT-e/NR2).
                ausgetreten=ist_ausgeschieden(
                    {"status": m.status, "austritt_datum": m.austritt_datum}),
                # DSGVO-2d: Endstatus „geloescht“ — eigener Anzeigetext.
                geloescht=ist_geloescht({"name": m.name, "status": m.status}),
            ))
        return personen

    def _anmeldungen_laden(self, session: Session) -> list[AnmeldungDaten]:
        """Liest bestaetigte Anmeldungen mit expliziter Rollen-Antwort (1 Abfrage).

        Siehe ``ANMELDUNG_BESTAETIGTE_STATUS`` und ``ANMELDUNG_ROLLE_LABEL``:
        ohne explizite ``feldlabel='rolle'``-Antwort gibt es keine Rolle.
        Mit Bindung ``veranstaltung`` wird zusaetzlich auf diese
        Veranstaltung (``element``) eingegrenzt.
        """
        bedingungen = [
            Anmeldung.docstatus < 2,
            AnmeldungAntwort.docstatus < 2,
            AnmeldungAntwort.parenttype == "Anmeldung",
            AnmeldungAntwort.parentfield == "antworten",
            AnmeldungAntwort.feldlabel == ANMELDUNG_ROLLE_LABEL,
            AnmeldungAntwort.antwort.is_not(None),
            Anmeldung.mitglied.is_not(None),
        ]
        if self.veranstaltung:
            bedingungen.append(Anmeldung.element == self.veranstaltung)

        zeilen = session.execute(
            select(
                Anmeldung.mitglied,
                Anmeldung.element,
                Anmeldung.status,
                AnmeldungAntwort.antwort,
            )
            .join(AnmeldungAntwort, AnmeldungAntwort.parent == Anmeldung.name)
            .where(*bedingungen)
        ).all()
        # Der Status-Vergleich passiert in Python (casefold): SQLite's
        # SQL-lower() kleinschreibt keine Umlaute, Postgres schon — hier
        # engine-unabhaengig und eine Abfrage (kein N+1).
        return [
            AnmeldungDaten(
                person=mitglied,
                rolle=antwort.strip(),
                veranstaltung=element or "",
            )
            for mitglied, element, status, antwort in zeilen
            if antwort and antwort.strip()
            and (status or "").strip().casefold() in ANMELDUNG_BESTAETIGTE_STATUS
        ]

    def _kategorien_quellen_merkmale(self, session: Session) -> set[str]:
        """Merkmal-Schluessel der Sammlung 'lieder' mit quelle='psalmos.kategorie'.

        Liest die juengste Definition des gebundenen Plantyps (``self.plantyp``
        = Schluessel). Nur diese Merkmale beziehen ihre Werte aus den
        Psalmos-Liedkategorien (ST3, Themen-Vereinheitlichung).
        """
        if not self.plantyp:
            return set()
        # Eine Abfrage: juengste Definition des Plantyps (Join plantyp/version).
        letzte = session.scalars(select(PrPlantypVersion)
            .join(PrPlantyp, PrPlantypVersion.plantyp == PrPlantyp.id)
            .where(PrPlantyp.schluessel == self.plantyp)
            .order_by(PrPlantypVersion.versionsnummer.desc())).first()
        if letzte is None or not isinstance(letzte.definition, dict):
            return set()
        lieder = (letzte.definition.get("merkmale") or {}).get(LIEDER_SAMMLUNG) or []
        return {m["id"] for m in lieder
                if isinstance(m, dict) and m.get("quelle") == "psalmos.kategorie"
                and isinstance(m.get("id"), str)}

    def _kategorien_laden(self, session: Session) -> dict[str, list[str]]:
        """Lied-Kennung -> Liste der Liedkategorie-Namen (1 Abfrage, 2 Joins).

        Quelle ist ausschliesslich die Psalmos-Tabelle ``lied_kategorie``
        (Zuordnung) mit ihrem Katalog ``liedkategorie`` (Name). Nur der
        Kategoriename wird gelesen.
        """
        from diakronos_app.models.psalmos import LiedKategorie, Liedkategorie
        zeilen = session.execute(
            select(LiedKategorie.parent, Liedkategorie.kategoriename)
            .join(Liedkategorie, LiedKategorie.kategorie == Liedkategorie.name)
            .where(
                LiedKategorie.docstatus < 2,
                LiedKategorie.parenttype == "Lied",
                LiedKategorie.parentfield == "kategorien",
                LiedKategorie.parent.is_not(None),
                LiedKategorie.kategorie.is_not(None),
            )
        ).all()
        result: dict[str, list[str]] = {}
        for parent, name in zeilen:
            if not name:
                continue
            result.setdefault(parent, []).append(name)
        return result

    def _sammlungen_laden(
        self,
        session: Session,
        merkmale_sammlung: dict[str, dict[str, dict[str, Any]]],
    ) -> dict[str, list[Sammlungseintrag]]:
        """Liest die Sammlungen: 'lieder' aus ``lied``, eigene aus ``pr_sammlung``.

        ``merkmale_sammlung`` sind die zuvor gelesenen Merkmalswerte mit
        ``ziel='sammlung:<schluessel>'``, geordnet nach Ziel-ID.
        """
        sammlungen: dict[str, list[Sammlungseintrag]] = {}

        # -- eingebaute Sammlung 'lieder' aus der Lied-Tabelle -------------- #
        lieder = (
            session.execute(
                select(Lied)
                .where(Lied.aktiv.is_(True), Lied.docstatus < 2)
                .order_by(Lied.name)
            )
            .scalars()
            .all()
        )
        lieder_merkmale = merkmale_sammlung.get(LIEDER_SAMMLUNG, {})
        # ST3-Themen-Vereinheitlichung: Merkmale der Sammlung 'lieder', die
        # deklarativ auf die Psalmos-Liedkategorien zeigen
        # (quelle='psalmos.kategorie'), lesen ihre Werte aus 'liedkategorie'
        # ueber 'lied_kategorie' (EINE Wahrheit) — nicht aus pr_merkmal_wert.
        kategorie_merkmale = self._kategorien_quellen_merkmale(session)
        kategorien_je_lied = self._kategorien_laden(session) if kategorie_merkmale else {}
        eintraege: list[Sammlungseintrag] = []
        for lied in lieder:
            nummer = lied.gesangbuch_nummer or ""
            ccli = lied.ccli_nummer or ""
            titel = lied.titel or ""
            merkmale = dict(lieder_merkmale.get(lied.name, {}))
            for schluessel in kategorie_merkmale:
                kats = kategorien_je_lied.get(lied.name, [])
                if kats:
                    # mehrfach-Werte als Liste, sonst als Skalar
                    merkmale[schluessel] = kats if len(kats) > 1 else kats[0]
            eintraege.append(
                Sammlungseintrag(
                    kennung=lied.name,
                    sammlung=LIEDER_SAMMLUNG,
                    titel=titel,
                    reihenfolge=0,
                    merkmale=merkmale,
                    attribute={
                        "titel": titel,
                        "reihenfolge": 0,
                        "alternativtitel": lied.alternativtitel or "",
                        "gesangbuch_nummer": nummer,
                        # Aliasse der Formatvorlagen (Konzept B5/C4).
                        "nr": nummer,
                        "nummer": nummer,
                        "buch": getattr(lied, "buch", None) or "",
                        "seite": getattr(lied, "seite", None) or "",
                        # LN1: Quelle des Liedes ('buch'/'kopie'/'ohne'). Die
                        # Formatvorlagen blenden Nummer/Seite bei 'kopie' aus.
                        "quelle": getattr(lied, "quelle", None) or "",
                        "ccli_nummer": ccli,
                        "ccli": ccli,
                        "zuletzt_gesungen": lied.zuletzt_gesungen,
                        "anzahl_gesungen": lied.anzahl_gesungen,
                    },
                )
            )
        sammlungen[LIEDER_SAMMLUNG] = eintraege

        # -- eigene Sammlungen aus pr_sammlung / pr_sammlung_eintrag ------- #
        sammlungs_zeilen = (
            session.execute(select(PrSammlung).order_by(PrSammlung.schluessel))
            .scalars()
            .all()
        )
        eintrag_zeilen = (
            session.execute(
                select(PrSammlungEintrag)
                .where(PrSammlungEintrag.aktiv.is_(True))
                .order_by(
                    PrSammlungEintrag.sammlung,
                    PrSammlungEintrag.reihenfolge,
                    PrSammlungEintrag.id,
                )
            )
            .scalars()
            .all()
        )
        eintraege_je_sammlung: dict[str, list[PrSammlungEintrag]] = {}
        for e in eintrag_zeilen:
            eintraege_je_sammlung.setdefault(e.sammlung, []).append(e)

        je_schluessel: dict[str, dict[str, list[Sammlungseintrag]]] = {}
        for s in sammlungs_zeilen:
            if s.schluessel == LIEDER_SAMMLUNG:
                # Die Lied-Tabelle ist die Quelle 'lieder'; eine gleichnamige
                # pr_sammlung-Zeile traegt ggf. nur Merkmals-Definitionen.
                continue
            definition = s.definition if isinstance(s.definition, dict) else {}
            # Uebergangs-Lesung: die Spalten umfang/plan kommen mit dem
            # PR4-Nachtrag; bis dahin gilt der definition-JSON-Schluessel,
            # danach hat die Spalte Vorrang.
            umfang = (
                getattr(s, "umfang", None)
                or definition.get("umfang")
                or SAMMLUNG_UMFANG_GEMEINDE
            )
            gebundener_plan = getattr(s, "plan", None) or definition.get("plan")
            if umfang == SAMMLUNG_UMFANG_PLAN:
                # Nur sichtbar, wenn diese Sammlung an genau den gebundenen
                # Plan haengt — sonst kein Zugriff (fail-closed).
                if not self.plan_id or gebundener_plan != self.plan_id:
                    continue
            elif umfang != SAMMLUNG_UMFANG_GEMEINDE:
                # Unbekannter Umfang -> nicht ausliefern (fail-closed).
                continue

            samm_merkmale = merkmale_sammlung.get(s.schluessel, {})
            liste: list[Sammlungseintrag] = []
            for e in eintraege_je_sammlung.get(s.id, []):
                daten = e.daten if isinstance(e.daten, dict) else {}
                titel = str(daten.get("titel") or "")
                attribute = dict(daten)
                attribute.setdefault("titel", titel)
                attribute.setdefault("reihenfolge", e.reihenfolge or 0)
                liste.append(
                    Sammlungseintrag(
                        kennung=e.id,
                        sammlung=s.schluessel,
                        titel=titel,
                        reihenfolge=e.reihenfolge or 0,
                        merkmale=dict(samm_merkmale.get(e.id, {})),
                        attribute=attribute,
                    )
                )
            je_schluessel.setdefault(s.schluessel, {})[umfang] = liste
        # Gleicher Schluessel in gemeinde- UND plan-Fassung: die planbezogene
        # Fassung hat deterministisch Vorrang (dokumentiert).
        for schluessel, faenge in je_schluessel.items():
            sammlungen[schluessel] = faenge.get(
                SAMMLUNG_UMFANG_PLAN, faenge.get(SAMMLUNG_UMFANG_GEMEINDE, [])
            )
        return sammlungen

    def _abwesenheiten_laden(self, session: Session) -> list[Abwesenheit]:
        """Liest ``pr_abwesenheit``; ``nur_plantyp`` muss zur Bindung passen."""
        zeilen = (
            session.execute(
                select(PrAbwesenheit).order_by(PrAbwesenheit.von, PrAbwesenheit.bis)
            )
            .scalars()
            .all()
        )
        liste: list[Abwesenheit] = []
        for a in zeilen:
            if a.nur_plantyp and a.nur_plantyp != self.plantyp:
                continue  # nicht zutreffend -> nicht liefern (fail-closed)
            liste.append(
                Abwesenheit(
                    person=a.mitglied,
                    von=a.von,
                    bis=a.bis,
                    grund=a.grund or "",
                )
            )
        return liste

    def _historie_laden(self, session: Session) -> list[Historieneintrag]:
        """Liest fruehere Werte aus den VEROEFFENTLICHTEN Staenden fremder Plaene.

        OP-CHOR-2: Frueher zaehlten alle ``pr_eintrag``-Zeilen aller Plaene —
        auch unveroeffentlichte Entwuerfe. Ein zweiter, ueberlappender Plan
        derselben Vorlage hat damit die Historie "verbraucht": die Meldung
        lautete „zuletzt vor 0 Tagen“, der Generator waehlte dieselben wenigen
        Lieder immer wieder. Historie ist, was die Gemeinde tatsaechlich
        gesehen hat — also der beim Veroeffentlichen eingefrorene Stand
        (``pr_plan.veroeffentlichter_stand``). Welche Termine davon im
        Einzelfall zaehlen (nur die VOR dem eigenen Termin), entscheidet
        ``regeln/auswertung.py::_daten``.

        Der eigene, gebundene Plan (``plan_id``) ist ausgeschlossen;
        ``plantyp`` wird zum **Schluessel** aufgeloest (nie UUID). Listen-
        Werte werden je Wert zu einem Historieneintrag entfaltet. Grenze:
        Feldpfade tragen keine Version/Sammlungs-Kennung — siehe
        Modul-Docstring.
        """
        plantyp_schluessel = dict(
            session.execute(select(PrPlantyp.id, PrPlantyp.schluessel)).all()
        )
        zeilen = (
            session.execute(
                select(PrPlan.id, PrPlan.plantyp, PrPlan.veroeffentlichter_stand)
                .where(PrPlan.veroeffentlichter_stand.is_not(None))
                .order_by(PrPlan.id)
            )
            .all()
        )

        eintraege: list[Historieneintrag] = []
        for plan_id, plantyp_id, stand in zeilen:
            if self.plan_id is not None and plan_id == self.plan_id:
                continue  # eigener Plan zaehlt nicht als Historie
            schluessel = plantyp_schluessel.get(plantyp_id)
            if schluessel is None:
                continue  # aufloesbarer Plantyp fehlt -> nicht liefern (fail-closed)
            termine = {
                t["id"]: t.get("datum")
                for t in (stand or {}).get("termine", [])
                if isinstance(t, dict) and t.get("id")
            }
            for eintrag in (stand or {}).get("eintraege", []):
                if not isinstance(eintrag, dict):
                    continue
                feld_pfad = eintrag.get("feld_pfad")
                datum = termine.get(eintrag.get("termin"))
                if not feld_pfad or datum is None:
                    continue  # fail-closed: ohne Termin/Datum keine Historie
                try:
                    tag = date.fromisoformat(str(datum)[:10])
                except ValueError:
                    continue  # unlesbares Datum -> nicht liefern
                wert = eintrag.get("wert")
                for w in (wert if isinstance(wert, list) else [wert]):
                    if w is None:
                        continue
                    eintraege.append(
                        Historieneintrag(
                            datum=tag,
                            plantyp=schluessel,
                            feld_pfad=feld_pfad,
                            wert=w if isinstance(w, str) else str(w),
                            plan=plan_id,
                        )
                    )
        return eintraege

    def _kalender_laden(self, session: Session) -> list[Kalendertermin]:
        """Liest freigegebene Kalender-Elemente (``status='Festgelegt'``).

        Genau die Freigabe des bestehenden Kalender-Endpunkts
        (api/kronos/kalender.py). Es werden keine privaten Felder gelesen
        (Beschreibung, Teilnehmer, Mitarbeiter, Ressourcen).
        """
        zeilen = (
            session.execute(
                select(Element)
                .where(
                    Element.docstatus < 2,
                    Element.status == KALENDER_FREIGEGEBEN_STATUS,
                    Element.element_start.is_not(None),
                )
                .order_by(Element.element_start, Element.name)
            )
            .scalars()
            .all()
        )
        termine: list[Kalendertermin] = []
        for e in zeilen:
            start = e.element_start
            termine.append(
                Kalendertermin(
                    kennung=e.name,
                    datum=start.date(),
                    uhrzeit=None if e.all_day else start.time(),
                    name=e.element_name or "",
                    kategorie=e.element_category or "",
                    gruppe=e.gruppe or "",
                )
            )
        return termine

    # -- Datenquelle-Protokoll ---------------------------------------------- #

    def personen(self) -> list[Person]:
        """Alle Personen (Mitglieder) mit Merkmalen und Gruppen.

        AUSTRITT-b (B4): Ausgetretene und Ausgeschlossene sind hier NICHT
        enthalten — die Zuteilbarkeit ist fachlich und nicht ansichtsabhaengig
        (siehe ``_personen_laden``). Kein Weg liefert sie als Kandidaten.
        """
        return [p for p in self._quelle.personen() if not p.ausgeschieden]

    def personen_anzeige(self) -> list[Person]:
        """ALLE Personen inklusive Ausgeschiedener — fuer die ANZEIGE.

        AUSTRITT-d (NB1): Die Anzeige alter Plaene, der Regelmeldungen und der
        Wertpruefung braucht die Namen AUCH von Ausgetretenen. Vorher las sie
        ``personen()`` (seit B4 gefiltert) — eine Ausgetretene verlor damit in
        jedem alten Plan ihren Namen, fuer alle Rollen. Die Kuerzung fuer
        Nicht-Admins steht schon in der Person (``_personen_laden``); die
        Zuteilbarkeit bleibt an ``personen()`` gebunden.
        """
        return list(self._quelle.personen())

    def gruppen(self) -> list[GruppeDaten]:
        """Alle Gruppen mit gueltigen Mitgliedschaften."""
        return self._quelle.gruppen()

    def merkmal_werte(self, merkmal: str) -> dict[str, Any]:
        """Person-Kennung -> Merkmalswert (fuer Rollenfilter 'merkmal')."""
        return self._quelle.merkmal_werte(merkmal)

    def gruppen_mitglieder(self, gruppe: str) -> frozenset[str]:
        """Mitglieds-Kennungen einer Gruppe (leer bei unbekannter Gruppe)."""
        return self._quelle.gruppen_mitglieder(gruppe)

    def anmeldungen(self, rolle: str, veranstaltung: str = "") -> frozenset[str]:
        """Angegemeldete Personen einer expliziten Rolle (fail-closed).

        Ohne Argument ``veranstaltung`` gilt die Bindung der Quelle (falls
        eine gesetzt ist); eine explizite Angabe gewinnt.
        """
        return self._quelle.anmeldungen(rolle, veranstaltung or self.veranstaltung)

    def sammlung(self, schluessel: str) -> list[Sammlungseintrag]:
        """Eintraege einer Sammlung ('lieder' aus der Lied-Tabelle)."""
        return self._quelle.sammlung(schluessel)

    def abwesenheiten(self, von: date, bis: date) -> list[Abwesenheit]:
        """Abwesenheiten, die den Zeitraum schneiden (plantyp-gefiltert)."""
        return self._quelle.abwesenheiten(von, bis)

    def historie(
        self, feld: str, bis_datum: date, plantyp: str | None = None
    ) -> list[Historieneintrag]:
        """Fruehere Werte (Schluessel-Filter, eigener Plan ausgeschlossen)."""
        return self._quelle.historie(feld, bis_datum, plantyp)

    def kalender_termine(self, filter: dict[str, Any]) -> list[Kalendertermin]:
        """Freigegebene Kalendertermine; Filter: kategorie, gruppe, von, bis."""
        # Erst hier laden (Lazy): Leseseiten brauchen die Kalenderliste nie.
        # Danach dieselbe (1:1 unveraenderte) InMemory-Filterung wie zuvor.
        self._quelle.kalender_liste = self._kalender()
        termine = self._quelle.kalender_termine(filter)
        von = filter.get("von")
        bis = filter.get("bis")
        if von is not None:
            termine = [t for t in termine if t.datum >= von]
        if bis is not None:
            termine = [t for t in termine if t.datum <= bis]
        return termine
