"""Fuellstrategien mit gemeinsamer Muss-Pruefung und stabiler Rotation."""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

from .datenquelle import Datenquelle, Historieneintrag
from .modell import Eintrag, Slot, Termin
from .pfade import feld_basis, feld_bezug_passt, passt_zu_feld
from .rollen import kandidaten


@dataclass
class Fuellzustand:
    """Aufruflokale Rotation und bereits vergebene Werte."""

    plantyp: dict[str, Any]
    datenquelle: Datenquelle
    parameter: dict[str, Any] = field(default_factory=dict)
    rotation: dict[str, int] = field(default_factory=dict)
    eintraege: list[Eintrag] = field(default_factory=list)
    historie: list[Historieneintrag] = field(default_factory=list)
    regelkontext: Any = None
    indizierte_eintraege: int = 0
    vorbereitung_planen: bool = False
    quelle_der_fuellung: str = ""


def _kandidaten_fuer(slot: Slot, zustand: Fuellzustand) -> list[str]:
    """Kandidaten in stabiler Stammdaten-/Sammlungsreihenfolge."""
    if slot.art in ("person", "personen"):
        return [p.kennung for p in kandidaten(slot.rolle, zustand.datenquelle, zustand.plantyp, parameter=zustand.parameter)]
    if slot.art == "eintrag":
        return [e.kennung for e in sorted(zustand.datenquelle.sammlung(slot.sammlung or ""), key=lambda e: (e.reihenfolge, e.kennung))]
    if slot.art == "team":
        if isinstance(slot.teams, list):
            return list(slot.teams)
        if isinstance(slot.teams, dict):
            return [g.kennung for g in zustand.datenquelle.gruppen() if g.obergruppe == slot.teams.get("gruppe_unter")]
    if slot.art == "auswahl":
        return list(slot.feld.get("werte", []))
    return []


def _eintrag_zu(pfad: str, termin: Termin, zustand: Fuellzustand) -> Eintrag | None:
    """Exakten oder einzigen gesetzten Instanzwert desselben Termins lesen.

    Ein deklarativer Bezug auf ein Mehrfachfeld ist nur eindeutig, wenn genau
    eine Instanz gesetzt ist; mehrere Werte werden nie willkuerlich ausgewaehlt.
    """
    exakt = next((e for e in zustand.eintraege if e.termin is termin and e.feld_pfad == pfad), None)
    if exakt is not None:
        return exakt
    werte = [e for e in zustand.eintraege if e.termin is termin and e.wert is not None
             and feld_bezug_passt(e.feld_pfad, pfad, termin)]
    return werte[0] if len(werte) == 1 else None


def _wert_aus_referenz(aus: str, slot: Slot, termin: Termin, zustand: Fuellzustand) -> Any:
    """Sammlungsmerkmal, anderes Wertefeld oder Ursprung einer abgeleiteten Reihe."""
    if aus.startswith("eintrag."):
        eltern = slot.feld_pfad.rsplit(".", 1)[0] if "." in slot.feld_pfad else ""
        eintrag = _eintrag_zu(eltern, termin, zustand)
        if eintrag is None:
            # Im Ablauf liegen Lied und Besetzung nebeneinander, nicht ineinander.
            eintrag = next((e for e in zustand.eintraege if e.termin is termin and e.art == "eintrag"
                            and e.feld_pfad.rsplit(".", 1)[0] == eltern), None)
        if eintrag is None:
            return None
        sammlung = slot.sammlung
        if not sammlung:
            return None
        katalog = next((e for e in zustand.datenquelle.sammlung(sammlung) if e.kennung == eintrag.wert), None)
        return katalog.attribut(aus[len("eintrag."):]) if katalog else None
    if aus.startswith("bezug."):
        ursprung = termin.bezug
        if ursprung is None:
            return None
        feld = aus[len("bezug."):]
        pfad = feld if ursprung.reihe == "standard" or ":" in feld else f"{ursprung.reihe}:{feld}"
        eintrag = _eintrag_zu(pfad, ursprung, zustand)
    else:
        eintrag = _eintrag_zu(aus, termin, zustand)
        if eintrag is None and ":" in slot.feld_pfad and ":" not in aus:
            eintrag = _eintrag_zu(slot.feld_pfad.split(":", 1)[0] + ":" + aus, termin, zustand)
    return eintrag.wert if eintrag else None


def _reihum_waehlen(slot: Slot, termin: Termin, zustand: Fuellzustand, kn: list[str],
                    bewertung) -> Any:
    """Stabile Rotation ueber die Kandidaten (auch als Rueckfall bei 'vorbelegen').

    Die Rotation setzt dort fort, wo zuletzt eingeteilt wurde: die Historie
    und die bereits gefuellten Termine desselben Feldes geben den Ausgangspunkt.
    Nicht zulaessige Kandidaten (Muss-Regeln, Abwesenheit) werden uebersprungen.
    """
    if not kn:
        return None
    basis = feld_basis(slot.feld_pfad)
    if basis not in zustand.rotation:
        vorige = [(h.datum, h.wert) for h in zustand.historie if h.plantyp == zustand.plantyp.get("id", "")
                  and passt_zu_feld(h.feld_pfad, basis) and h.datum < termin.datum]
        vorige += [(e.termin.datum, e.wert) for e in zustand.eintraege if e.termin and e.termin.datum < termin.datum
                   and passt_zu_feld(e.feld_pfad, basis)]
        zuletzt = max(vorige, key=lambda x: x[0])[1] if vorige else None
        zustand.rotation[basis] = kn.index(zuletzt) + 1 if zuletzt in kn else 0
    for schritt in range(len(kn)):
        idx = (zustand.rotation[basis] + schritt) % len(kn)
        if bewertung(kn[idx]).zulaessig:
            zustand.rotation[basis] = idx + 1
            return kn[idx]
    return None


def fuellen(slot: Slot, termin: Termin, zustand: Fuellzustand, rng: random.Random,
            *, bedarfskandidaten: list[str] | None = None,
            quelle_deklariert: bool) -> tuple[Any, str]:
    """Waehlt einen Wert; keine Strategie darf Muss-Regeln umgehen.

    ``quelle_deklariert`` ist bewusst PFLICHT (kein stiller Default): es
    steuert, ob die Reihum-Rotation einspringt, wenn eine Vorbelegungs-Quelle
    ('eintrag.*') leer bleibt. Ein Default ``False`` liesse jeden anderen
    Aufrufer unbemerkt in den Rueckfall laufen (OP-CHOR-11); so muss jeder
    Aufrufer die Entscheidung sichtbar treffen.
    """
    from ..regeln.auswertung import Kontext, bewerte_alle, index_aufbauen, index_ergaenzen

    zustand.quelle_der_fuellung = slot.fuellen
    if slot.fuellen == "manuell":
        return None, ""
    if zustand.regelkontext is None:
        zustand.regelkontext = Kontext(zustand.plantyp, termin, zustand.datenquelle, zustand.parameter, zustand.eintraege, zustand.historie)
        index_aufbauen(zustand.regelkontext)
        zustand.indizierte_eintraege = len(zustand.eintraege)
    k = zustand.regelkontext
    k.termin = termin
    for e in zustand.eintraege[zustand.indizierte_eintraege:]:
        if e.termin:
            index_ergaenzen(k, zustand.plantyp.get("id", ""), e.feld_pfad, e.wert, e.termin.datum, quelle=e.quelle, art=e.art)
    zustand.indizierte_eintraege = len(zustand.eintraege)
    regeln = [r for r in zustand.plantyp.get("regeln", [])
              if (not r.get("feld") or passt_zu_feld(slot.feld_pfad, r["feld"]))
              and (r["baustein"] != "abwesenheit_beachten" or slot.art in ("person", "personen", "team"))]
    if zustand.vorbereitung_planen:
        # Lokale Vorbereitung wird in Phase zwei gebaut; harte Ablehnung erst
        # nach dieser Phase. Fremde Historie und alle anderen Muss-Regeln gelten.
        regeln = [dict(r, stufe="sollte") if r["baustein"] == "vorher_geuebt" and r.get("stufe") == "muss"
                  and r.get("uebung", {}).get("plantyp", zustand.plantyp.get("id", "")) == zustand.plantyp.get("id", "")
                  else r for r in regeln]
        if slot.fuellen == "optimieren":
            def neutraler_vorbereitungsbedarf(regel: dict[str, Any]) -> bool:
                """Ohne jede Uebungshistorie ist die weiche Strafe fuer alle gleich.

                Die finale Pruefung bleibt verbindlich. Historie, fixierte
                Uebungen und kandidatenbezogene Filter duerfen nie entfallen.
                """
                eigener_typ = zustand.plantyp.get("id", "")
                if regel["baustein"] != "vorher_geuebt" or regel.get("stufe") == "muss" or any(
                    regel.get(filter) is not None for filter in ("rolle", "person", "team")
                ):
                    return False
                uebung = regel.get("uebung", {"plantyp": eigener_typ, "feld": regel.get("uebungsfeld", regel["feld"])})
                if uebung["plantyp"] != eigener_typ:
                    return False
                typen = {eigener_typ, *regel.get("auch_in", [])}
                return not any(typ in typen and feld == uebung["feld"] and
                               any(d < termin.datum for d in daten)
                               for index in (k.historie_werte, k.historie_fremd)
                               for (typ, feld, _), daten in index.items())

            regeln = [r for r in regeln if not neutraler_vorbereitungsbedarf(r)]
    kn = _kandidaten_fuer(slot, zustand)
    def bewertung(wert: Any):
        return bewerte_alle(wert, slot, k, regeln)

    if bedarfskandidaten is not None:
        for wert in bedarfskandidaten:
            if wert in kn and bewertung(wert).zulaessig:
                return wert, ""
        return None, ""

    if slot.fuellen == "vorbelegen":
        wert = _wert_aus_referenz(slot.aus or "", slot, termin, zustand)
        if wert is None:
            # OP-CHOR-11: Fehlt die Sammlungs-Quelle ganz (im Chorplan: kein
            # Lied gesetzt), ist „woraus vorbelegen?" gegenstandslos — die
            # stabile Reihum-Rotation aus der Rolle uebernimmt. Ist die Quelle
            # deklariert, aber ihr Wert offen/ungepflegt, bleibt der Platz
            # wartend leer (test_planrahmen_engine_sammlungsquelle).
            if (slot.aus or "").startswith("eintrag.") and not quelle_deklariert:
                gewaehlt = _reihum_waehlen(slot, termin, zustand, kn, bewertung)
                if gewaehlt is not None:
                    zustand.quelle_der_fuellung = "reihum"
                    return gewaehlt, ""
            return None, f"Vorbelegen-Quelle {slot.aus!r} für {slot.feld_pfad} ist leer."
        if slot.art == "personen" and isinstance(wert, str):
            wert = [wert]
        b = bewertung(wert)
        if b.zulaessig:
            return wert, ""
        ersatz = [w for w in kn if bewertung(w).zulaessig]
        zustand.quelle_der_fuellung = "optimieren"
        return (ersatz[rng.randrange(len(ersatz))] if ersatz else None), "; ".join(b.meldungen) + "; Ersatz aus Rolle/Quelle."

    if slot.fuellen == "der_reihe_nach":
        verwendet = {str(e.wert) for e in zustand.eintraege if e.art == "eintrag" and e.wert is not None}
        verwendet |= {str(h.wert) for h in zustand.historie if h.plantyp == zustand.plantyp.get("id", "")}
        for w in kn:
            if w not in verwendet and bewertung(w).zulaessig:
                return w, ""
    elif slot.fuellen == "reihum":
        gewaehlt = _reihum_waehlen(slot, termin, zustand, kn, bewertung)
        if gewaehlt is not None:
            return gewaehlt, ""
    else:
        bewertet = [(w, bewertung(w)) for w in kn]
        erlaubt = [(w, b) for w, b in bewertet if b.zulaessig]
        if erlaubt:
            # Fairness ist tatsaechliches zweites Kriterium, nicht nur Sortierung.
            def haeufigkeit(wert: str) -> int:
                if slot.art in ("person", "personen", "team"):
                    return k.fairness[(False, "*", wert)]
                return k.haeufigkeit[wert]
            minimum = min((b.strafe, haeufigkeit(w)) for w, b in erlaubt)
            beste = [w for w, b in erlaubt if (b.strafe, haeufigkeit(w)) == minimum]
            return beste[rng.randrange(len(beste))], ""
    return None, f"Kein Kandidat erfüllt die Muss-Regeln für {slot.feld_pfad} (Quelle leer oder aufgebraucht)."
