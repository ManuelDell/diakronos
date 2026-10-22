"""Einheitliche Regelbewertung fuer Auswahl und vollstaendige Planpruefung.

Historie wird wertweise und je Plantyp gelesen. Kontext und Indizes gehoeren
immer zu einem Aufruf; keine globalen Ergebnis-Caches oder DB-Zugriffe.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
import re
from typing import Any, Callable

from ..engine.datenquelle import Datenquelle, Historieneintrag, Sammlungseintrag
from ..engine.modell import Bewertung, Eintrag, Slot, Termin, Verstoss
from ..datum import datum_de, datum_de_lang
from ..engine.pfade import feld_basis, passt_zu_feld
from ..engine.rollen import kandidaten
from .registry import registriere_logik


def stufe_der_regel(regel: dict[str, Any]) -> str:
    """Standardstufe eines Regelbausteins."""
    return regel.get("stufe", "sollte")


@dataclass
class Kontext:
    """Aufruflokale Umgebung mit vorberechneter Historie und Werteindex."""

    plantyp: dict[str, Any]
    termin: Termin
    datenquelle: Datenquelle
    parameter: dict[str, Any] = field(default_factory=dict)
    eintraege: list[Eintrag] = field(default_factory=list)
    historie: list[Historieneintrag] | None = None
    haeufigkeit: Counter = field(default_factory=Counter)
    fairness: Counter = field(default_factory=Counter)
    historie_werte: dict[tuple[str, str, str], list[date]] = field(default_factory=dict)
    # P1-14b: Eintraege aus FREMDPLAEN (zaehlen nur vor dem eigenen Termin).
    historie_fremd: dict[tuple[str, str, str], list[date]] = field(default_factory=dict)
    # P1-14b: Kennung des Plans, der gerade geplant wird. Nur DIESER zaehlt
    # beidseitig im Abstand; jeder andere Plan ist ein Fremdplan.
    eigener_plan: str | None = None
    sammlungsindex: dict[str, dict[str, Sammlungseintrag]] = field(default_factory=dict)
    rollenindex: dict[str, set[str]] = field(default_factory=dict)
    ausgeschlossen: Eintrag | None = None
    struktur_slots: dict[str, Slot] | None = None

    def eintraege_des_termins(self) -> list[Eintrag]:
        """Regelwerte desselben Termins ohne Selbstzaehlung; Struktur bleibt vollstaendig."""
        return [e for e in self.eintraege if e.termin is self.termin and e is not self.ausgeschlossen]


def _werte(wert: Any) -> list[str]:
    """Personenlisten und Einzelkennungen einheitlich betrachten."""
    if wert is None:
        return []
    if isinstance(wert, (list, tuple, set, frozenset)):
        return [str(w) for w in wert]
    return [str(wert)]


def historie_laden(plantyp: dict[str, Any], quelle: Datenquelle, bis: date) -> list[Historieneintrag]:
    """Laedt die benoetigten Plantypen einmal, einschliesslich anderer Feldpfade."""
    typen = {plantyp.get("id", "")}
    for regel in plantyp.get("regeln", []):
        typen.update(regel.get("auch_in", []))
        if isinstance(regel.get("uebung"), dict):
            typen.add(regel["uebung"]["plantyp"])
    return [h for typ in sorted(typen) for h in quelle.historie("*", bis, typ)]


def index_aufbauen(kontext: Kontext, felder: set[str] | None = None) -> None:
    """Baut wertweise Historie; wiederholter Aufruf zaehlt niemals doppelt.

    P1-14b: Die Historie wird nach PLAN getrennt indiziert. Eintraege aus dem
    EIGENEN Plan (``eigener_plan``) landen in ``historie_werte`` und zaehlen
    beidseitig; Eintraege aus FREMDPLAEN landen in ``historie_fremd`` und
    zaehlen nur vor dem eigenen Termin. Die Eintraege des laufenden Kontexts
    (aus ``eintraege``) gehoeren zum eigenen Plan.
    """
    if kontext.historie is None:
        kontext.historie = historie_laden(kontext.plantyp, kontext.datenquelle, kontext.termin.datum)
    kontext.haeufigkeit.clear()
    kontext.fairness.clear()
    kontext.historie_werte.clear()
    kontext.historie_fremd.clear()
    eigener_typ = kontext.plantyp.get("id", "")
    # P1-14b: Ohne ausdrueckliche Bindung den Plan der Datenquelle nehmen —
    # die DB-Quelle kennt ihn (``plan_id``), In-Memory-Kontexte nicht.
    eigen = kontext.eigener_plan if kontext.eigener_plan is not None else \
        getattr(kontext.datenquelle, "plan_id", None)
    for h in kontext.historie:
        # Ohne Planbindung ist keine externe Historie der eigene Plan.
        # Nur neue Kontexteintraege (unten) zaehlen im Trockenlauf beidseitig.
        eigen_plan = eigen is not None and h.plan == eigen
        index_ergaenzen(kontext, h.plantyp, h.feld_pfad, h.wert, h.datum,
                        eigen_plan=eigen_plan)
    for e in kontext.eintraege:
        if e.termin:
            index_ergaenzen(kontext, eigener_typ, e.feld_pfad, e.wert, e.termin.datum,
                            quelle=e.quelle, art=e.art, eigen_plan=True)
    for datenliste in kontext.historie_werte.values():
        datenliste.sort()
    for datenliste in kontext.historie_fremd.values():
        datenliste.sort()


def index_ergaenzen(kontext: Kontext, typ: str, pfad: str, wert: Any, datum: date,
                    *, quelle: str = "", art: str | None = None,
                    eigen_plan: bool = True) -> None:
    """Fuegt nur den neu vergebenen Wert hinzu, statt den ganzen Plan zu indizieren.

    ``eigen_plan=False`` markiert einen Eintrag aus einem FREMDPLAN: er zaehlt
    nur vor dem eigenen Termin (siehe :func:`_daten`).
    """
    basis = feld_basis(pfad)
    ziel = kontext.historie_werte if eigen_plan else kontext.historie_fremd
    for w in _werte(wert):
        for schluessel in {basis, basis.split(":", 1)[-1], "*"}:
            ziel.setdefault((typ, schluessel, w), []).append(datum)
        if typ == kontext.plantyp.get("id", ""):
            kontext.haeufigkeit[w] += 1
            if art in (None, "person", "personen", "team"):
                for schluessel in {basis, basis.split(":", 1)[-1], "*"}:
                    kontext.fairness[(True, schluessel, w)] += 1
                    if quelle not in ("vorbelegen", "vorbelegt", "abgeleitet"):
                        kontext.fairness[(False, schluessel, w)] += 1


def _rolle(regel: dict[str, Any], kontext: Kontext) -> set[str] | None:
    """Rollenfilter je Kontext zwischenspeichern."""
    rolle = regel.get("rolle")
    if rolle is None:
        return None
    schluessel = repr(rolle)
    if schluessel not in kontext.rollenindex:
        kontext.rollenindex[schluessel] = {p.kennung for p in kandidaten(rolle, kontext.datenquelle, kontext.plantyp, parameter=kontext.parameter)}
    return kontext.rollenindex[schluessel]


def _wirkt_feld(regel: dict[str, Any], slot: Slot) -> bool:
    """Kandidatenunabhaengiger Regelfilter: nur Feld-/Felder-Zuordnung.

    Genau der Teil von :func:`_wirkt`, der ausschliesslich von Slot und Regel
    abhaengt. Er wird im Hotpath vorab geprueft, weil er sich je Kandidat nicht
    aendert (23k Kandidatenbewertungen je Generatorlauf).
    """
    if regel.get("feld") and not passt_zu_feld(slot.feld_pfad, regel["feld"]):
        return False
    if regel.get("felder") and not any(passt_zu_feld(slot.feld_pfad, f) for f in regel["felder"]):
        return False
    return True


def _wirkt(regel: dict[str, Any], wert: Any, slot: Slot, kontext: Kontext) -> bool:
    """Regeln wirken nur auf deklarierte Wertefelder bzw. passende Rollen."""
    if not _wirkt_feld(regel, slot):
        return False
    rolle = _rolle(regel, kontext)
    if rolle is not None and not _personen(wert, slot, kontext) & rolle:
        return False
    if regel.get("person") and regel["person"] not in _personen(wert, slot, kontext):
        return False
    if regel.get("team") and regel["team"] not in _werte(wert) and not (regel["baustein"] == "verfuegbarkeit" and slot.art == "team"):
        return False
    return True


def _daten(wert: str, feld: str, typ: str, kontext: Kontext) -> list[date]:
    """Daten eines Werts im gewuenschten Feld (oder '*' fuer Fremdplaene).

    OP-CHOR-2: Aus FREMDEN Plaenen zaehlt nur, was VOR dem eigenen Termin
    liegt. Frueher kamen auch deren spaetere Termine durch — ein zweiter,
    ueberlappender Plan verbrauchte die Lieder damit im Voraus ("zuletzt vor
    0 Tagen"), obwohl die Gemeinde sie nie gehoert hatte.

    P1-14b: „Fremd“ heisst ein ANDERER PLAN, nicht ein anderer Plantyp. Die
    Unterscheidung laeuft deshalb ueber ``kontext.eigener_plan`` und die
    ``plan``-Kennung des Historieneintrags (siehe ``index_aufbauen``): nur der
    EIGENE Plan zaehlt beidseitig, jeder andere Plan — auch ein ueberlappender
    veroeffentlichter derselben Vorlage — nur vor dem eigenen Termin.

    Innerhalb des EIGENEN Plans bleibt die Planung in beide Richtungen
    gueltig: ein bereits festgelegter (fixierter) Termin in der Zukunft
    gehoert in denselben Abstand wie ein vergangener (sonst legte man das
    Lied kurzfristig zweimal aufeinander).
    """
    daten = list(kontext.historie_werte.get((typ, feld, wert), []))
    daten += [d for d in kontext.historie_fremd.get((typ, feld, wert), [])
              if d < kontext.termin.datum]
    e = kontext.ausgeschlossen
    if e is not None and e.termin and wert in _werte(e.wert) and (feld == "*" or passt_zu_feld(e.feld_pfad, feld)):
        daten = [d for d in daten if d != e.termin.datum]
    return [d for d in daten if d != kontext.termin.datum]


def _gleicher_zeitraum(a: date, b: date, zeitraum: str) -> bool:
    """Kalenderzeitraum, inklusive ISO-Wochenjahr."""
    if zeitraum == "termin":
        return a == b
    if zeitraum == "woche":
        return a.isocalendar()[:2] == b.isocalendar()[:2]
    if zeitraum == "jahr":
        return a.year == b.year
    return (a.year, a.month) == (b.year, b.month)


def _zaehle(wert: str, regel: dict[str, Any], kontext: Kontext) -> int:
    """Dienste einschliesslich frueherer Plaene, auf Personen/Teams begrenzt."""
    zeitraum = regel.get("zeitraum", "monat")
    return sum(1 for e in kontext.eintraege if e is not kontext.ausgeschlossen and e.art in ("person", "personen", "team") and e.termin
               and wert in _werte(e.wert) and _gleicher_zeitraum(e.termin.datum, kontext.termin.datum, zeitraum)) + sum(
        1 for h in kontext.historie or [] if h.plantyp == kontext.plantyp.get("id", "")
        and wert in _werte(h.wert) and _gleicher_zeitraum(h.datum, kontext.termin.datum, zeitraum))


def _sammlungseintrag(wert: str, slot: Slot, kontext: Kontext) -> Sammlungseintrag | None:
    """Liest genau die Sammlung des Slots, ohne fest eingebaute Planart."""
    if not slot.sammlung:
        return None
    if slot.sammlung not in kontext.sammlungsindex:
        kontext.sammlungsindex[slot.sammlung] = {e.kennung: e for e in kontext.datenquelle.sammlung(slot.sammlung)}
    return kontext.sammlungsindex[slot.sammlung].get(wert)


def _wertname(wert: str, slot: Slot, kontext: Kontext) -> str:
    """Alltagssprache fuer eine Kennung: Liedtitel, Personenname, sonst Kennung.

    OP-CHOR-9: Regelmeldungen nannten die interne Kennung
    (``d2cbfb42-5: zuletzt am …``). Der Titel steht in der Sammlung; fehlt
    er (oder ist es keine Sammlung), bleibt die Kennung der einzige Name.
    """
    if slot.art in ("person", "personen"):
        # AUSTRITT-d (NB1): Anzeigename, nicht Kandidatenmenge — sonst nennt
        # die Regelmeldung fuer eine Ausgetretene nur noch die Kennung.
        quelle = getattr(kontext.datenquelle, "personen_anzeige", None)
        personen = quelle() if quelle else kontext.datenquelle.personen()
        person = next((p for p in personen if p.kennung == wert), None)
        if person is not None and (person.name or person.kennung):
            return person.name or person.kennung
        return wert
    eintrag = _sammlungseintrag(wert, slot, kontext)
    titel = getattr(eintrag, "titel", "") if eintrag is not None else ""
    return titel or wert


def _personen(wert: Any, slot: Slot, kontext: Kontext, *, nur_pflicht: bool = False) -> set[str]:
    """Tatsaechliche Besetzung; nur Abwesenheit beschraenkt auf Pflichtmitglieder."""
    if slot.art != "team":
        return set(_werte(wert)) if slot.art in ("person", "personen") else set()
    mitglieder = set(kontext.datenquelle.gruppen_mitglieder(str(wert)))
    if slot.mitglieder:
        mitglieder &= {p.kennung for p in kandidaten(slot.mitglieder, kontext.datenquelle, kontext.plantyp)}
    for gruppe in kontext.datenquelle.gruppen() if nur_pflicht else []:
        if gruppe.kennung == wert and gruppe.pflicht_mitglieder is not None:
            mitglieder &= gruppe.pflicht_mitglieder
    return mitglieder


def _personen_des_eintrags(eintrag: Eintrag, kontext: Kontext) -> set[str]:
    """Besetzung mit der deklarierten Team-Teilmenge desselben Termins."""
    if eintrag.art != "team":
        return set(_werte(eintrag.wert)) if eintrag.art in ("person", "personen") else set()
    if kontext.struktur_slots is not None:
        slot = kontext.struktur_slots.get(eintrag.feld_pfad, Slot(eintrag.feld_pfad, eintrag.art, {}))
        return _personen(eintrag.wert, slot, kontext)
    from ..engine.struktur import aufloesen_mit_eintraegen

    slots = aufloesen_mit_eintraegen(
        kontext.plantyp, kontext.termin, kontext.eintraege, parameter=kontext.parameter,
    )
    slot = next((s for s in slots if s.feld_pfad == eintrag.feld_pfad),
                Slot(eintrag.feld_pfad, eintrag.art, {}))
    return _personen(eintrag.wert, slot, kontext)


def _abwesenheit(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Abwesenheiten fuer Personen und Team-Pflichtmitglieder."""
    personen = _personen(wert, slot, k, nur_pflicht=True)
    abwesend = [a for a in k.datenquelle.abwesenheiten(k.termin.datum, k.termin.datum) if a.person in personen]
    return (1.0, f"{', '.join(a.person for a in abwesend)} am {datum_de_lang(k.termin.datum)} abwesend (Pflichtbesetzung).") if abwesend else (0.0, "")


def _mindestabstand(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Mindestabstand zum selben Wert, auch bei anders benannten Fremdfeldern."""
    daten = _daten(str(wert), r["feld"], k.plantyp.get("id", ""), k)
    for typ in r.get("auch_in", []):
        daten += _daten(str(wert), "*", typ, k)
    # Endpruefung meldet jede Kollision am spaeteren Termin nur einmal;
    # Auswahl muss auch bereits fixierte zukuenftige Werte respektieren.
    if k.ausgeschlossen is not None:
        daten = [d for d in daten if d <= k.termin.datum]
    if not daten:
        return 0.0, ""
    zuletzt = min(daten, key=lambda d: abs((k.termin.datum - d).days))
    tage = abs((k.termin.datum - zuletzt).days)
    grenze = r["wochen"] * 7
    # OP-CHOR-9: Alltagssprache mit Titel statt interner Kennung.
    name = _wertname(str(wert), slot, k)
    return ((grenze - tage) / grenze, f"{name}: zuletzt am {datum_de_lang(zuletzt)} (vor {tage} Tagen, Regel: mind. {r['wochen']} Wochen).") if tage < grenze else (0.0, "")


def _max(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Hoechstzahl: Kandidat kommt zu den bisherigen Diensten hinzu.

    OP-CHOR-2: Die Strafe war ``n + 1 - anzahl`` und wuchs unbegrenzt (bei 5
    Diensten 4,0). Damit war sie gegenueber ``mindestabstand`` (0..1) und
    ``vorher_geuebt`` (0..1) um ein Vielfaches schwerer. Jetzt zaehlt je
    ueberschreitendem Dienst ``1/anzahl`` — die Ueberschreitung bleibt
    spuerbar, bleibt aber auf derselben Skala.
    """
    if slot.art not in ("person", "personen", "team"):
        return 0.0, ""
    n = max((_zaehle(w, r, k) for w in _werte(wert)), default=0)
    anzahl = max(1, r["anzahl"])
    if n < r["anzahl"]:
        return 0.0, ""
    # OP-CHOR-2: je ueberschreitendem Dienst 1/anzahl — und hart auf 0..1
    # geklemmt. Ohne die Klemmung wuchs die Strafe bei vielen Ueberschreitungen
    # ueber 1 hinaus (bei 5 Diensten 4,0) und war damit um ein Vielfaches
    # schwerer als ``mindestabstand``/``vorher_geuebt`` (beide 0..1).
    strafe = min(1.0, float(n + 1 - anzahl) / anzahl)
    return (strafe, f"{wert}: {n + 1} Dienste im {r['zeitraum']} (Regel: max. {r['anzahl']}).")


def _min(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Auswahl bevorzugt bisher unterversorgte Personen; Endpruefung separat."""
    if slot.art not in ("person", "personen", "team"):
        return 0.0, ""
    # Kein harter Filter: fehlende Mindestdienste koennen erst am Periodenende
    # beurteilt werden. Negative Strafen belohnen die noch fehlenden Dienste.
    n = max((_zaehle(w, r, k) for w in _werte(wert)), default=0)
    return -float(max(0, r["anzahl"] - n)), ""


def _gleich(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Bisherige Dienste als Auswahlstrafe; Endpruefung vergleicht Verteilung."""
    if slot.art not in ("person", "personen", "team"):
        return 0.0, ""
    if not r.get("vorbelegte_mitzaehlen", False) and slot.fuellen == "vorbelegen":
        return 0.0, ""
    return float(sum(k.fairness[(r.get("vorbelegte_mitzaehlen", False), r.get("feld", "*"), w)]
                     for w in _werte(wert))), ""


def _nicht_gleichzeitig(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Verschiedene benannte Wertefelder duerfen keine Personen teilen."""
    for e in k.eintraege_des_termins():
        if e.feld_pfad != slot.feld_pfad and any(passt_zu_feld(e.feld_pfad, f) for f in r["felder"]):
            if _personen_des_eintrags(e, k) & _personen(wert, slot, k):
                return 1.0, f"{wert} besetzt {slot.feld_pfad} und {e.feld_pfad} zugleich."
    return 0.0, ""


def _zusammen(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Muss-Paare nur als vollstaendige Personenliste oder mit vorhandener Besetzung."""
    personen = set(r["personen"])
    vorhanden = _personen(wert, slot, k) | {w for e in k.eintraege_des_termins() for w in _personen_des_eintrags(e, k)}
    if vorhanden & personen and not personen <= vorhanden:
        return 1.0, f"Zusammen einteilen: Es fehlen {', '.join(sorted(personen - vorhanden))}."
    return 0.0, ""


def _nicht_zusammen(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Nur die benannten Personen schliessen sich gegenseitig aus."""
    personen = set(r["personen"])
    if not personen & _personen(wert, slot, k):
        return 0.0, ""
    vorhanden = _personen(wert, slot, k) | {w for e in k.eintraege_des_termins() for w in _personen_des_eintrags(e, k)}
    return (1.0, "Nicht zusammen einteilen: " + ", ".join(sorted(vorhanden & personen))) if len(vorhanden & personen) > 1 else (0.0, "")


def _vorher_geuebt(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Nur Uebungen desselben Werts strikt vor dem Veranstaltungsdatum zaehlen.

    OP-CHOR-2: Die Strafe lag frueher bei ``mindestens - n`` (bis 2,0) und
    damit doppelt so hoch wie ``mindestabstand`` (0..1). Zusammen mit dem
    Skalenfehler des Mindestabstands gewann dadurch der Abstandsverstoss gegen
    das „noch nie geuebt" — die Auswahl wiederholte dieselben wenigen Lieder,
    obwohl ein ungeuebtes Lied teurer sein muss. Beide Regeln liegen jetzt auf
    derselben 0..1-Skala; ``gewicht`` bleibt der einzige Feintrieb.
    """
    uebung = r.get("uebung", {"plantyp": k.plantyp.get("id", ""), "feld": r.get("uebungsfeld", r["feld"])})
    daten = _daten(str(wert), uebung["feld"], uebung["plantyp"], k)
    for typ in r.get("auch_in", []):
        daten += _daten(str(wert), uebung["feld"], typ, k)
    n = len({d for d in daten if d < k.termin.datum})
    # OP-CHOR-9: Titel statt Kennung; „Übungen" statt „Uebungen".
    name = _wertname(str(wert), slot, k)
    mindestens = max(1, r["mindestens"])
    return ((mindestens - n) / mindestens, f"{name}: erst {n} von {r['mindestens']} Übungen vor {datum_de_lang(k.termin.datum)}.") if n < r["mindestens"] else (0.0, "")


def _passend(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Sammlungsmerkmal muss mindestens einen Anlass des Termins treffen."""
    if not k.termin.anlaesse:
        return 0.0, ""
    eintrag = _sammlungseintrag(str(wert), slot, k)
    if eintrag is None:
        return 0.0, ""
    themen = {w.lower() for w in _werte(eintrag.attribut(r["merkmal"]))}
    # OP-CHOR-9: Titel statt Kennung, Umlaute statt ASCII-Ersatz.
    name = _wertname(str(wert), slot, k)
    return (1.0, f"{name}: kein passendes {r['merkmal']} für {', '.join(sorted(k.termin.anlaesse))}.") if not themen & {a.lower() for a in k.termin.anlaesse} else (0.0, "")


def muster_passt(muster: Any, termin: Termin) -> bool:
    """Verfuegbarkeit als n-ter Reihentermin oder n-ter/letzter Wochentag."""
    if isinstance(muster, dict):
        n = muster["termin_im_monat"]
        return (termin.positionsnr_im_monat if n > 0 else termin.position_von_hinten) == abs(n)
    m = re.fullmatch(r"(-?[1-5])\.(Mo|Di|Mi|Do|Fr|Sa|So)", str(muster), re.IGNORECASE)
    if not m:
        raise ValueError(f"Unbekanntes Verfuegbarkeitsmuster: {muster!r}")
    n = int(m[1])
    wochentag = ("mo", "di", "mi", "do", "fr", "sa", "so").index(m[2].lower())
    if termin.datum.weekday() != wochentag:
        return False
    if n > 0:
        return (termin.datum.day - 1) // 7 + 1 == n
    import calendar
    return (calendar.monthrange(termin.datum.year, termin.datum.month)[1] - termin.datum.day) // 7 + 1 == -n


def _verfuegbarkeit(wert: Any, slot: Slot, k: Kontext, r: dict[str, Any]) -> tuple[float, str]:
    """Zeitmuster fuer Personen und Teams."""
    termin = k.termin.bezug or k.termin
    passt = muster_passt(r["muster"], termin)
    if slot.art == "team" and r.get("team"):
        passt = passt == (wert == r["team"])
    return (0.0, "") if passt else (1.0, f"{wert} am {datum_de_lang(k.termin.datum)} nicht verfügbar (reserviertes Zeitmuster).")


_AUSWERTUNG = {"abwesenheit_beachten": _abwesenheit, "mindestabstand": _mindestabstand,
    "max_pro_zeitraum": _max, "min_pro_zeitraum": _min, "gleich_verteilen": _gleich,
    "nicht_gleichzeitig": _nicht_gleichzeitig, "zusammen": _zusammen, "nicht_zusammen": _nicht_zusammen,
    "vorher_geuebt": _vorher_geuebt, "passend_zum_anlass": _passend, "verfuegbarkeit": _verfuegbarkeit}


def bewerte(kandidat: Any, slot: Slot, kontext: Kontext, regel: dict[str, Any]) -> Bewertung:
    """Einheitliche Stufen: Muss filtert, Sollte gewichtet, Hinweis nur meldet."""
    return bewerte_alle(kandidat, slot, kontext, [regel])


def bewerte_alle(kandidat: Any, slot: Slot, kontext: Kontext, regeln: list[dict[str, Any]]) -> Bewertung:
    """Summiert direkt; keine Zwischenobjekte je Regel im Kandidaten-Hotpath."""
    zulaessig = True
    strafe = 0.0
    meldungen: list[str] = []
    if kandidat is not None:
        for regel in regeln:
            # Feldfilter der Regel haengt NUR an Slot/Regel, nicht am Kandidaten:
            # er wird im Hotpath (23k Aufrufe je Generatorlauf) einmal geprueft
            # und die uebrigen Kandidatenfilter erst danach.
            if not _wirkt_feld(regel, slot):
                continue
            if not _wirkt(regel, kandidat, slot, kontext):
                continue
            regelstrafe, meldung = _AUSWERTUNG[regel["baustein"]](kandidat, slot, kontext, regel)
            stufe = stufe_der_regel(regel)
            if stufe == "muss" and meldung:
                zulaessig = False
            if stufe == "sollte":
                strafe += regelstrafe * regel.get("gewicht", 1.0)
            if meldung:
                meldungen.append(meldung)
    return Bewertung(zulaessig, strafe, meldungen)


def pruefe_plan(plantyp: dict[str, Any], termine: list[Termin], eintraege: list[Eintrag],
                datenquelle: Datenquelle, parameter: dict[str, Any] | None = None,
                historie: list[Historieneintrag] | None = None) -> list[Verstoss]:
    """Bewertet den fertigen Plan ohne Selbstzaehlung, inklusive Mindestzahl/Fairness."""
    from ..engine.struktur import aufloesen_mit_eintraegen

    historie = historie if historie is not None else historie_laden(plantyp, datenquelle, max((t.datum for t in termine), default=date.today()))
    verstoesse: list[Verstoss] = []
    regeln = plantyp.get("regeln", [])
    basis = Kontext(plantyp, termine[0] if termine else Termin(date.today(), "standard"), datenquelle, parameter or {}, eintraege, historie)
    index_aufbauen(basis)
    for termin in termine:
        slots = {s.feld_pfad: s for s in aufloesen_mit_eintraegen(
            plantyp, termin, eintraege, parameter=parameter,
        )}
        for e in (e for e in eintraege if e.termin is termin and e.wert is not None):
            slot = slots.get(e.feld_pfad, Slot(e.feld_pfad, e.art, {}))
            k = Kontext(plantyp, termin, datenquelle, parameter or {}, eintraege, historie)
            k.struktur_slots = slots
            k.historie_werte = basis.historie_werte
            k.historie_fremd = basis.historie_fremd
            k.sammlungsindex = basis.sammlungsindex
            k.ausgeschlossen = e
            for r in regeln:
                if r["baustein"] in ("min_pro_zeitraum", "gleich_verteilen"):
                    continue
                b = bewerte(e.wert, slot, k, r)
                for meldung in b.meldungen:
                    verstoesse.append(Verstoss(stufe_der_regel(r), r["baustein"], e.feld_pfad, meldung, termin))
    # Globale Regeln einmal je Bezugszeitraum, auch fuer nie besetzte Personen.
    for r in regeln:
        if r["baustein"] not in ("min_pro_zeitraum", "gleich_verteilen"):
            continue
        gruppen: list[list[Termin]] = []
        for t in termine:
            gruppe = next((g for g in gruppen if _gleicher_zeitraum(g[0].datum, t.datum, r.get("zeitraum", "jahr"))), None)
            if gruppe is None:
                gruppen.append([t])
            else:
                gruppe.append(t)
        for gruppe in gruppen:
            t = max(gruppe, key=lambda t: t.datum)
            k = Kontext(plantyp, t, datenquelle, parameter or {}, eintraege, historie)
            personen = _rolle(r, k)
            if personen is None:
                personen = {p.kennung for p in datenquelle.personen()}
                if r.get("feld"):
                    personen = {w for e in eintraege if passt_zu_feld(e.feld_pfad, r["feld"]) for w in _werte(e.wert)}
            zaehler = Counter(w for e in eintraege if e.termin in gruppe and e.art in ("person", "personen", "team")
                              and (r["baustein"] != "gleich_verteilen" or r.get("vorbelegte_mitzaehlen", False) or e.quelle not in ("vorbelegen", "vorbelegt", "abgeleitet"))
                              and (not r.get("feld") or passt_zu_feld(e.feld_pfad, r["feld"])) for w in _werte(e.wert) if w in personen)
            if r["baustein"] == "min_pro_zeitraum":
                for p in sorted(personen):
                    n = _zaehle(p, r, k)
                    if n < r["anzahl"]:
                        verstoesse.append(Verstoss(stufe_der_regel(r), r["baustein"], "", f"{p}: nur {n}/{r['anzahl']} Dienste im {r['zeitraum']}.", t))
            elif personen and max(zaehler[p] for p in personen) - min(zaehler[p] for p in personen) > 1:
                verstoesse.append(Verstoss(stufe_der_regel(r), r["baustein"], r.get("feld", ""), "Dienste ungleich verteilt: " + ", ".join(f"{p}: {zaehler[p]}" for p in sorted(personen)), t))
    return sorted(verstoesse, key=lambda v: (0 if v.stufe == "muss" else 1, v.feld_pfad))


def regeln_mit_strategie(plantyp: dict[str, Any]) -> list[dict[str, Any]]:
    """Liefert alle deklarierten Regeln fuer die Auswahl."""
    return plantyp.get("regeln", [])


def _fabrik(schluessel: str) -> Callable:
    """Adaptierter Registry-Vertrag: Fabrik -> Bewertung eines Kandidaten."""
    def fabrik(regel: dict[str, Any]) -> Callable:
        def bew(kandidat: Any, slot: Slot, kontext: Kontext, r: dict[str, Any] | None = None) -> Bewertung:
            return bewerte(kandidat, slot, kontext, r or regel)
        return bew
    return fabrik


REGEL_LOGIK = {schluessel: _fabrik(schluessel) for schluessel in _AUSWERTUNG}
for _schluessel, _logik in REGEL_LOGIK.items():
    registriere_logik(_schluessel, _logik)
