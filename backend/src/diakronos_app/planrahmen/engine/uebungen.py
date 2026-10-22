"""Zweite Generatorphase: terminierte Bedarfe nach Dringlichkeit einplanen."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import random
from typing import Any, Callable

from ..datum import datum_de_lang, datum_kurz_de, datum_de
from ..regeln.uebungsbedarf import Uebungsbedarf, uebungsbedarfe, uebungsregeln
from .fuellen import Fuellzustand, fuellen
from .modell import Slot, Termin, Vorschlag
from .pfade import feld_bezug_passt, passt_zu_feld
from .struktur import aufloesen


def fuelle_uebungsbedarf(
    zustand: Fuellzustand,
    termine: list[Termin],
    bezugsplaene: list[tuple[dict[str, Any], Vorschlag]],
    rng: random.Random,
    termin_fuellen: Callable[[Termin, Callable[[Slot, Termin], tuple[Any, str]], dict[str, int]], None],
    verstoesse: list[Any] | None = None,
) -> None:
    """Bedarfskandidaten in die regulaere abhaengigkeitsbewusste Fuellung geben.

    Fruehere Uebungen bleiben gueltig; der Vorlauf begrenzt nur neu geplante
    Uebungen. Fixierte Plaetze verbrauchen Kapazitaet, aber werden nie ersetzt.
    Pro Wert und Datum zaehlt hoechstens eine Uebung, auch bei mehreren Slots.
    Die Kapazitaetsschaetzung enthaelt neben aktiven auch noch ungeklaerte
    Unterbaeume als moegliche Tage. Aktive Slots aktualisieren sie waehrend
    der Fuellung. Nur sicher unerfuellbare Fristen sperren einen Kandidaten;
    die finalen Slots loest der Generator nach jeder Entscheidung erneut auf.

    **Vorrang:** Von Hand festgelegte Singtermine sind Uebungsbedarf mit
    hoechster Prioritaet. Sie werden je Datum vor allen automatischen Bedarfen
    angeboten und bekommen so die Plaetze zuerst. Reicht die Kapazitaet nicht,
    entsteht eine klare kapazitaetsbezogene Meldung (``verstoesse``).
    """
    bedarfe = uebungsbedarfe(zustand.plantyp, zustand.eintraege, bezugsplaene)
    felder = {ziel["feld"] for _, ziel, _ in uebungsregeln(zustand.plantyp, bezugsplaene)}
    if not felder:
        return
    eigener_typ = zustand.plantyp.get("id", "")
    daten: dict[tuple[str, str, str], set[date]] = defaultdict(set)

    def merken(typ: str, pfad: str, wert: Any, datum: date) -> None:
        for feld in felder:
            if wert is not None and passt_zu_feld(pfad, feld):
                daten[(typ, feld, str(wert))].add(datum)

    for h in zustand.historie:
        merken(h.plantyp, h.feld_pfad, h.wert, h.datum)
    weitere_typen = {typ for b in bedarfe for typ in b.auch_in}
    for typ in sorted(weitere_typen):
        for h in zustand.datenquelle.historie("*", max(b.bis for b in bedarfe), typ):
            merken(h.plantyp, h.feld_pfad, h.wert, h.datum)
    for e in zustand.eintraege:
        if e.termin:
            merken(eigener_typ, e.feld_pfad, e.wert, e.termin.datum)
    for typ, vorschlag in bezugsplaene:
        for e in vorschlag.eintraege:
            if e.termin:
                merken(typ.get("id", ""), e.feld_pfad, e.wert, e.termin.datum)

    umfang = {feld: len({b.wert for b in bedarfe if b.feld == feld}) for feld in felder}
    moegliche_tage: dict[str, set[date]] = {feld: set() for feld in felder}
    for termin in termine:
        offene_felder: set[str] = set()
        slots = aufloesen(
            zustand.plantyp, termin, parameter=zustand.parameter,
            bestehende_eintraege=zustand.eintraege, fuellumfang=umfang,
            # Feldabhaengige Kapazitaet ist vor Phase zwei noch ungeklaert,
            # nicht sicher inaktiv. Der regulaere Resolver entscheidet spaeter
            # mit den tatsaechlichen Werten, welche Slots gefuellt werden.
            feld_bereit=lambda pfad: False, offene_felder=offene_felder,
        )
        vorhanden = {e.feld_pfad for e in zustand.eintraege if e.termin is termin}
        for feld in felder:
            if any(s.art == "eintrag" and s.fuellen == "optimieren"
                   and feld_bezug_passt(s.feld_pfad, feld, termin)
                   and s.feld_pfad not in vorhanden for s in slots) or any(
                       feld_bezug_passt(feld, pfad, termin, unterfelder=True)
                       for pfad in offene_felder):
                moegliche_tage[feld].add(termin.datum)

    # Fristfenster sind waehrend dieses Laufs konstant. Nur der Fehlbedarf
    # aendert sich je Slot; ihn weiterhin aus den aktuellen Uebungstagen lesen.
    # Vorrang-Bedarfe stehen je Datum vor allen automatischen (Prioritaet).
    def nach_vorrang(b: Uebungsbedarf) -> tuple[int, date]:
        return (0 if b.vorrang else 1, b.bis)

    bedarfe_je_datum = {datum: sorted(
        [b for b in bedarfe if b.bis - timedelta(weeks=b.vorlauf_wochen) <= datum < b.bis],
        key=nach_vorrang)
        for datum in {t.datum for t in termine}}

    def uebung_fuellen(slot: Slot, termin: Termin) -> tuple[Any, str]:
        """Nur vorbereitbaren, noch offenen Bedarf als Kandidaten anbieten."""
        kandidaten: list[str] = []
        for bedarf in bedarfe_je_datum[termin.datum]:
            if not feld_bezug_passt(slot.feld_pfad, bedarf.feld, termin):
                continue
            # Der aktive Slot ist ein aktueller Kapazitaetsnachweis, selbst
            # wenn sein Feld erst durch eine Verbraucherkette sichtbar wurde.
            moegliche_tage[bedarf.feld].add(termin.datum)
            uebungstage = set(daten[(eigener_typ, bedarf.feld, bedarf.wert)])
            for typ in bedarf.auch_in:
                uebungstage |= daten[(typ, bedarf.feld, bedarf.wert)]
            fehlend = bedarf.mindestens - len({d for d in uebungstage if d < bedarf.bis})
            verbleibend = {d for d in moegliche_tage[bedarf.feld] - uebungstage
                           if max(termin.datum, bedarf.bis - timedelta(weeks=bedarf.vorlauf_wochen)) <= d < bedarf.bis}
            # Eine einzelne Uebung kurz vor einer unmoeglichen Frist darf
            # keine rechtzeitig erfuellbare spaetere Vorbereitung verdraengen.
            if termin.datum not in uebungstage and 0 < fehlend <= len(verbleibend):
                if bedarf.wert not in kandidaten:
                    kandidaten.append(bedarf.wert)
        wert, meldung = fuellen(slot, termin, zustand, rng, bedarfskandidaten=kandidaten,
                                quelle_deklariert=False)
        if wert is not None:
            merken(eigener_typ, slot.feld_pfad, wert, termin.datum)
        elif slot.pflicht:
            meldung = f"Kein erfüllbarer Übungsbedarf für Pflichtfeld {slot.feld_pfad}."
        return wert, meldung

    for termin in termine:
        termin_fuellen(termin, uebung_fuellen, umfang)

    if verstoesse is not None:
        _kapazitaetsmeldungen(bedarfe, eigener_typ, daten, zustand, verstoesse, termine)


def _wert_titel(wert: str, feld: str, zustand: Fuellzustand) -> str:
    """Titel eines Sammlungseintrags fuer sichtbare Meldungen (sonst Kennung).

    Das Uebungsfeld (z. B. ``einueben``) liest seine Werte aus einer Sammlung
    (hier ``lieder``); deren Eintraege liefern den Titel. Deshalb wird zuerst
    die zum Feld deklarierte Sammlung geprueft, dann jede bekannte Sammlung.
    """
    sammlungen: list[str] = []
    def sammle(felder: Any) -> None:
        for f in felder or []:
            if not isinstance(f, dict):
                continue
            if f.get("id") == feld and isinstance(f.get("sammlung"), str):
                sammlungen.append(f["sammlung"])
            sammle(f.get("inhalt"))
            for zweig in (f.get("varianten") or []) + (f.get("teile") or []):
                if isinstance(zweig, dict):
                    sammle(zweig.get("inhalt"))
    sammle(zustand.plantyp.get("felder"))
    for reihe in zustand.plantyp.get("terminreihen") or []:
        if isinstance(reihe, dict):
            sammle(reihe.get("felder"))
    for schluessel in sammlungen + ["lieder"]:
        for e in zustand.datenquelle.sammlung(schluessel):
            if e.kennung == wert:
                return e.titel or wert
    return wert


def _kapazitaetsmeldungen(
    bedarfe: list[Uebungsbedarf],
    eigener_typ: str,
    daten: dict[tuple[str, str, str], set[date]],
    zustand: Fuellzustand,
    verstoesse: list[Any],
    termine: list[Termin],
) -> None:
    """Vorrang-Bedarfe ohne genug Uebungen als klare Kapazitaetsmeldung melden.

    Nur Vorrang-Bedarfe (von Hand festgelegte Singtermine) erzeugen eine
    Meldung; automatische Einsaetze sind bereits Best-Effort. Der Text nennt
    Wert, Termin und die tatsaechlich freie Kapazitaet, ohne ISO-Daten.
    """
    from .modell import Verstoss

    termine_je_datum = {t.datum: t for t in termine}
    for b in bedarfe:
        if not b.vorrang:
            continue
        tage = set(daten.get((eigener_typ, b.feld, b.wert), set()))
        for typ in b.auch_in:
            tage |= daten.get((typ, b.feld, b.wert), set())
        erreicht = len({d for d in tage if d < b.bis})
        if erreicht >= b.mindestens:
            continue
        titel = _wert_titel(b.wert, b.feld, zustand)
        meldung = (f"{titel} am {datum_kurz_de(b.bis)}: nur {erreicht} von "
                   f"{b.mindestens} Uebungsplaetzen frei vor dem Termin "
                   f"({datum_de_lang(b.bis)}).")
        termin = termine_je_datum.get(b.bis)
        # Am deklarierten Singfeld melden, damit der Generator die generische
        # „erst n von m"-Meldung desselben Eintrags ersetzen kann (und die
        # Oberflaeche die Meldung am Singtermin zeigt).
        feld_pfad = b.einsatz_feld or b.feld
        verstoesse.append(Verstoss("sollte", "vorher_geuebt", feld_pfad, meldung, termin))
