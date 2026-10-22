"""Generator: aus Plantyp + Datenquelle einen Plan-Vorschlag erzeugen (P6).

``generiere`` loest je Termin den Feldbaum zu Slots auf und fuellt jeden Slot
nach seiner Fuellstrategie. Fixierte Eintraege werden nie ueberschrieben und
gehen in die Bewertung ein (P6). Kann ein Pflicht-Slot nicht gefuellt werden,
bleibt er leer und es erscheint eine Meldung (P10: nie Absturz).

Nach dem Fuellen wird der Plan ueber ``pruefe_plan`` gegen alle Regeln geprueft;
Verstoesse erscheinen verstaendlich im Vorschlag.

Laufzeit: fuer ein Jahr Chorplan (60 Termine, 400 Lieder, 30 Personen) deutlich
unter 2 s (reines Python, In-Memory).
"""

from __future__ import annotations

import random
from datetime import date
from typing import Any, Callable

from .datenquelle import Datenquelle, Historieneintrag
from .fuellen import Fuellzustand, fuellen
from .modell import Eintrag, Slot, Termin, Vorschlag
from .pfade import feld_deklaration, feld_bezug_passt
from .struktur import aufloesen


def _quelle_deklariert(slot: Slot, sammlungsquellen: set[str]) -> bool:
    """OP-CHOR-11: Ist fuer diesen Slot eine Sammlungs-Quelle ueberhaupt deklariert?

    Die Reihum-Rotation darf nur einspringen, wenn die Vorbelegungs-Quelle
    fehlt (im Chorplan: kein Lied als Geschwister des Felds). Ist ein
    Eintrag-Geschwister deklariert — auch wenn es gerade ausgeblendet oder von
    Hand zu fuellen ist — bleibt der Platz wartend leer.
    """
    if not (slot.aus or "").startswith("eintrag."):
        return False
    eltern = slot.feld_pfad.rsplit(".", 1)[0] if "." in slot.feld_pfad else ""
    return any(p == eltern or p.rsplit(".", 1)[0] == eltern for p in sammlungsquellen)


def generiere(
    plantyp: dict[str, Any],
    plan_parameter: dict[str, Any],
    termine: list[Termin],
    bestehende_eintraege: list[Any],
    datenquelle: Datenquelle,
    seed: int = 0,
    *,
    bezugsplaene: list[tuple[dict[str, Any], Vorschlag]] | None = None,
) -> Vorschlag:
    """Erzeugt einen Plan-Vorschlag (P6).

    ``bestehende_eintraege`` sind die bereits vorhandenen (fixierten) Eintraege
    des Plans — sie werden beibehalten und gehen in die Bewertung ein. Format
    je Eintrag: ein Objekt mit ``feld_pfad`` und ``wert`` (bzw. ein
    ``Eintrag``-Wert).
    """
    # Erst beim Aufruf laden: Schema/Registry duerfen vor der Engine importieren.
    from ..regeln.auswertung import pruefe_plan
    from ..regeln.uebungsbedarf import uebungsregeln
    from .uebungen import fuelle_uebungsbedarf

    bezugsplaene = bezugsplaene or []
    uebungsfelder = {ziel["feld"] for _, ziel, _ in uebungsregeln(plantyp, bezugsplaene)}
    rng = random.Random(seed)
    zustand = Fuellzustand(plantyp=plantyp, datenquelle=datenquelle, parameter=plan_parameter, vorbereitung_planen=True)

    termine = sorted(termine, key=lambda t: (t.datum, t.reihe))
    # Proben koennen vor dem Ursprung liegen; Besetzung zuerst dort ermitteln.
    reihenfolge: list[Termin] = []
    aktiv: set[Termin] = set()
    def einordnen(termin: Termin) -> None:
        if termin in reihenfolge:
            return
        if termin in aktiv:
            raise ValueError("Zyklischer Terminbezug.")
        aktiv.add(termin)
        if termin.bezug is not None and termin.bezug in termine:
            einordnen(termin.bezug)
        aktiv.remove(termin)
        reihenfolge.append(termin)
    for termin in termine:
        einordnen(termin)

    # Historie vorab laden (fuer mindestabstand/vorher_geuebt/reihum-Fortsetzung).
    historie = _historie_laden(plantyp, datenquelle, termine)
    zustand.historie = historie

    # schon gefuellte Eintraege je Termin (fixiert zuerst).
    gefuellt_je_termin: dict[Termin, dict[str, Eintrag]] = {}

    # Fixierte in den Zustand uebernehmen (P6: nie ueberschreiben).
    for eintrag in _fixiert_als_eintraege(bestehende_eintraege, termine):
        zustand.eintraege.append(eintrag)
        if eintrag.termin is not None:
            gefuellt_je_termin.setdefault(eintrag.termin, {})[eintrag.feld_pfad] = eintrag

    bearbeitet_je_termin: dict[Termin, set[str]] = {}

    def termin_fuellen(
        termin: Termin,
        uebung_fuellen: Callable[[Slot, Termin], tuple[Any, str]] | None = None,
        umfang: dict[str, int] | None = None,
    ) -> None:
        """Beide Phasen loesen Bedingungen und Vorbelegungen bis zur Ruhe auf.

        Aufgeschobene Slots bleiben unversucht; die zweite Phase setzt dieselbe
        Aufloesung fort, ohne bereits getroffene Entscheidungen neu zu ziehen.
        """
        bearbeitet = bearbeitet_je_termin.setdefault(termin, set(gefuellt_je_termin.get(termin, {})))
        inaktiv: set[str] = set()
        bekannte_slots: set[str] = set()
        offene_felder: set[str] = set()
        ablauf_typen: dict[str, str] = {}

        def feld_bereit(pfad: str) -> bool:
            """Alle konkreten Quellslots klaeren, auch bei fixierter Teilbesetzung."""
            bezug = pfad if ":" in pfad or termin.reihe == "standard" else f"{termin.reihe}:{pfad}"
            # Selbst null optionale Instanzen sind vor der Bedarfsphase noch
            # nicht endgueltig leer. Auch negierte Verbraucher muessen warten.
            if zustand.vorbereitung_planen and any(
                feld_bezug_passt(bezug, f, termin, unterfelder=True)
                or feld_bezug_passt(f, bezug, termin, unterfelder=True)
                for f in uebungsfelder
            ):
                return False
            # Ein Uebungs-Wertefeld wartet auf seine Instanzen, nicht auf
            # bedingte Kinder, die ihrerseits genau diesen Wert benoetigen.
            unterfelder = not any(feld_bezug_passt(pfad, f, termin) for f in uebungsfelder)
            if any(
                feld_bezug_passt(p, pfad, termin, unterfelder=unterfelder, ablauf_typen=ablauf_typen)
                or feld_bezug_passt(bezug, feld_deklaration(p, termin, ablauf_typen), termin, unterfelder=unterfelder, ablauf_typen=ablauf_typen)
                for p in vorher_offen
            ):
                return False
            quellen = {p for p in bekannte_slots if feld_bezug_passt(p, pfad, termin, unterfelder=unterfelder, ablauf_typen=ablauf_typen)}
            if quellen:
                return quellen <= bearbeitet
            return any(
                feld_bezug_passt(bezug, p, termin, unterfelder=True, ablauf_typen=ablauf_typen)
                or feld_bezug_passt(bezug, feld_deklaration(p, termin, ablauf_typen), termin, unterfelder=True, ablauf_typen=ablauf_typen)
                for p in vorher_inaktiv
            )

        while True:
            vorher_inaktiv = set(inaktiv)
            vorher_bekannt = set(bekannte_slots)
            vorher_offen = set(offene_felder)
            offene_felder = set()
            sammlungsquellen: set[str] = set()
            slots = aufloesen(
                plantyp, termin, parameter=plan_parameter,
                feld_gesetzt=lambda pfad: any(
                    feld_bezug_passt(p, pfad, termin, unterfelder=True, ablauf_typen=ablauf_typen) and e.wert is not None
                    for p, e in gefuellt_je_termin.get(termin, {}).items()
                ),
                feld_bereit=feld_bereit,
                bestehende_eintraege=zustand.eintraege, inaktive_felder=inaktiv,
                offene_felder=offene_felder, ablauf_typen=ablauf_typen,
                sammlungsquellen=sammlungsquellen, fuellumfang=umfang,
            )
            bekannte_slots.update(s.feld_pfad for s in slots)
            offen = [s for s in slots if s.feld_pfad not in bearbeitet]
            if not offen:
                if inaktiv != vorher_inaktiv or bekannte_slots != vorher_bekannt or offene_felder != vorher_offen:
                    continue
                break
            # Erst Quellen, dann Verbraucher; noch unversucht ist nicht leer.
            fortschritt = False
            for slot in offen:
                uebungsbaum = any(feld_bezug_passt(
                    slot.feld_pfad, f, termin, unterfelder=True) for f in uebungsfelder)
                if zustand.vorbereitung_planen and uebungsbaum and (
                    slot.art != "eintrag" or slot.fuellen == "optimieren"
                ):
                    continue
                if slot.fuellen == "vorbelegen" and slot.aus and slot.aus.startswith("bezug."):
                    ursprung = termin.bezug
                    if zustand.vorbereitung_planen and uebungsfelder and ursprung is not None and not any(
                        feld_bezug_passt(p, slot.aus[len("bezug."):], ursprung)
                        for p in bearbeitet_je_termin.get(ursprung, set())
                    ):
                        # Der Ursprung wurde besucht, aber seine aufgeschobene
                        # Quelle (oder Verbraucherkette) ist noch nicht leer.
                        continue
                if slot.fuellen == "vorbelegen" and slot.aus and not slot.aus.startswith("bezug."):
                    if slot.aus.startswith("eintrag."):
                        eltern = slot.feld_pfad.rsplit(".", 1)[0] if "." in slot.feld_pfad else ""
                        quellen = [p for p in sammlungsquellen if (
                            p == eltern or p.rsplit(".", 1)[0] == eltern)]
                        # Bedingte Geschwister koennen noch ohne aktiven Slot
                        # sein. Nur ihren Wert klaeren, nicht den Unterbaum.
                        if any(p not in bearbeitet and not any(
                            p == verborgen or any(p.startswith(verborgen + t) for t in ".[@#/")
                            for verborgen in inaktiv
                        ) for p in quellen):
                            continue
                    elif not feld_bereit(slot.aus):
                        continue
                fortschritt = True
                bearbeitet.add(slot.feld_pfad)
                if slot.fuellen == "manuell":
                    continue
                if uebung_fuellen is not None and slot.art == "eintrag" and slot.fuellen == "optimieren" and any(
                    feld_bezug_passt(slot.feld_pfad, f, termin) for f in uebungsfelder
                ):
                    wert, meldung = uebung_fuellen(slot, termin)
                else:
                    wert, meldung = fuellen(
                        slot, termin, zustand, rng,
                        quelle_deklariert=_quelle_deklariert(slot, sammlungsquellen),
                    )
                if wert is None:
                    if slot.pflicht:
                        zustand.eintraege.append(Eintrag(
                            feld_pfad=slot.feld_pfad, wert=None, art=slot.art,
                            termin=termin, quelle="", meldung=meldung,
                        ))
                    continue
                eintrag = Eintrag(
                    feld_pfad=slot.feld_pfad, wert=wert, art=slot.art,
                    termin=termin, quelle=zustand.quelle_der_fuellung, meldung=meldung,
                )
                zustand.eintraege.append(eintrag)
                gefuellt_je_termin.setdefault(termin, {})[slot.feld_pfad] = eintrag
            if not fortschritt and inaktiv == vorher_inaktiv and bekannte_slots == vorher_bekannt and offene_felder == vorher_offen:
                if zustand.vorbereitung_planen and uebungsfelder:
                    break
                # Ungeloeste/zyklische Quellen nie mit einem leeren Wert verwechseln.
                for slot in offen:
                    if slot.pflicht:
                        zustand.eintraege.append(Eintrag(
                            slot.feld_pfad, None, slot.art, termin,
                            meldung=f"Vorbelegen-Quelle {slot.aus!r} für {slot.feld_pfad} ist noch ungeklärt.",
                        ))
                break

    for termin in reihenfolge:
        termin_fuellen(termin)

    zustand.vorbereitung_planen = False
    kapazitaet: list[Any] = []
    fuelle_uebungsbedarf(zustand, reihenfolge, bezugsplaene, rng, termin_fuellen, kapazitaet)

    verstoesse = pruefe_plan(plantyp, termine, zustand.eintraege, datenquelle,
                             parameter=plan_parameter, historie=historie)

    # Unvorbereitete automatische Einsaetze nie als Muss-Verletzung ausgeben.
    unvorbereitet = {(v.termin, v.feld_pfad): v.meldung for v in verstoesse
                    if v.baustein == "vorher_geuebt" and v.stufe == "muss"}
    abgelehnt = {(e.termin, e.feld_pfad): unvorbereitet[(e.termin, e.feld_pfad)]
                for e in zustand.eintraege if (e.termin, e.feld_pfad) in unvorbereitet
                and not e.fixiert and e.quelle not in ("manuell", "uebernommen")}
    if abgelehnt:
        behalten = []
        for e in zustand.eintraege:
            if (e.termin, e.feld_pfad) in abgelehnt:
                behalten.append(Eintrag(e.feld_pfad, None, e.art, e.termin,
                                        meldung=abgelehnt[(e.termin, e.feld_pfad)]))
            elif e.fixiert or e.quelle in ("manuell", "uebernommen") or not any(
                e.termin is t and e.feld_pfad.startswith(pfad + ".") for t, pfad in abgelehnt
            ):
                behalten.append(e)
        zustand.eintraege = behalten
        verstoesse = pruefe_plan(plantyp, termine, behalten, datenquelle,
                                parameter=plan_parameter, historie=historie)

    # Meldungen aus leeren Pflicht-Slots sammeln.
    meldungen = [e.meldung for e in zustand.eintraege if e.meldung]

    # Kapazitaetsmeldungen fuer von Hand festgelegte Singtermine: ersetzt die
    # generische "erst 0 von 2"-Meldung am selben Eintrag durch den klaren
    # Kapazitaetstext (nummerierte Uebungsplaetze statt abstrakter Zahl).
    if kapazitaet:
        belegt = {(v.termin, v.feld_pfad) for v in kapazitaet}
        def ersetzt(v: Any) -> bool:
            return bool(v.baustein == "vorher_geuebt"
                        and (v.termin, v.feld_pfad) in belegt)
        verstoesse = [v for v in verstoesse if not ersetzt(v)] + list(kapazitaet)
        verstoesse.sort(key=lambda v: (0 if v.stufe == "muss" else 1, v.feld_pfad))

    return Vorschlag(
        termine=termine,
        eintraege=zustand.eintraege,
        verstoesse=verstoesse,
        meldungen=meldungen,
    )


def _fixiert_als_eintraege(bestehende: list[Any], termine: list[Termin]) -> list[Eintrag]:
    """Wandelt bestehende/fixierte Eintraege in Eintrag-Objekte (mit Termin)."""
    result: list[Eintrag] = []
    termin_je_reihe: dict[str, list[Termin]] = {}
    for t in termine:
        termin_je_reihe.setdefault(t.reihe, []).append(t)
    for b in bestehende or []:
        if isinstance(b, Eintrag):
            if b.fixiert or b.quelle in ("manuell", "uebernommen"):
                result.append(b)
            continue
        if isinstance(b, dict):
            feld_pfad = b.get("feld_pfad")
            wert = b.get("wert")
            art = b.get("art", _art_aus_wert(wert))
            termin = b.get("termin")
            if termin is None:
                termin = _termine_raten(feld_pfad, b, termin_je_reihe)
            if b.get("fixiert", True) or b.get("quelle") in ("manuell", "uebernommen"):
                result.append(Eintrag(feld_pfad=feld_pfad, wert=wert, art=art, termin=termin,
                                      fixiert=b.get("fixiert", True), quelle=b.get("quelle", "manuell")))
    return result


def _art_aus_wert(wert: Any) -> str:
    if isinstance(wert, dict):
        return wert.get("art", "text")
    if isinstance(wert, str):
        return "text"
    if isinstance(wert, (int, float)):
        return "zahl"
    return "text"


def _termine_raten(feld_pfad: str, b: dict[str, Any], termin_je_reihe: dict[str, list[Termin]]) -> Termin | None:
    # Ein bestehender Eintrag traegt optional ein datum oder eine reihe.
    datum = b.get("datum")
    if isinstance(datum, str):
        try:
            d = date.fromisoformat(datum)
        except ValueError:
            d = None
        if d:
            for ts in termin_je_reihe.values():
                for t in ts:
                    if t.datum == d:
                        return t
    reihe = b.get("reihe")
    if reihe and reihe in termin_je_reihe and termin_je_reihe[reihe]:
        return termin_je_reihe[reihe][0]
    # Fallback: erster Termin.
    for ts in termin_je_reihe.values():
        if ts:
            return ts[0]
    return None


def _historie_laden(
    plantyp: dict[str, Any], datenquelle: Datenquelle, termine: list[Termin]
) -> list[Historieneintrag]:
    """Laedt wertweise Historie ueber die gemeinsame Regel-Schnittstelle."""
    from ..regeln.auswertung import historie_laden

    return historie_laden(plantyp, datenquelle, max((t.datum for t in termine), default=date.today()))
