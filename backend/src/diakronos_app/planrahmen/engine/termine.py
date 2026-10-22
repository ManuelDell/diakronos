"""Termin-Erzeugung aus allen Quellen (B2).

``erzeuge_termine`` baut aus einem Plantyp (``termine`` bzw. ``terminreihen``)
und den Plan-Parametern die flache Liste der Termine, mit Anlaessen und
abgeleiteten Reihen. Quellen sind frei kombinierbar:

- ``regel``  — iCalendar-RRULE (dateutil), innerhalb ``von``..``bis``;
- ``zeitraum`` — jeder Tag (bzw. ``wochentage``) zwischen zwei Daten;
- ``feiertage`` — benannte Feiertage (beweglich berechnet, ``feiertagsberechnung``);
- ``kalender`` — Termine aus der Datenquelle (Kategorie/Gruppe);
- ``manuell`` — einzelne Termine;
- ``ausnahmen`` — Termine entfallen (Liste oder ``{feiertage: true}``);
- ``abgeleitet`` — relativ zu einer anderen Reihe (``versatz``, ``nur_wenn``).

Jeder Feiertag setzt den Anlass gleichen Namens plus den Sammelanlass
``feiertag``. Duplikate am selben Datum (z. B. Regel trifft einen Feiertag)
werden zusammengefuehrt. ``{parameter.<id>}``-Referenzen in Daten/Zeitraeumen
werden aufgeloest.
"""

from __future__ import annotations

import itertools
import time as _time
from datetime import date, datetime, time, timedelta
from typing import Any

from dateutil.rrule import rrulestr

from . import feiertagsberechnung as ft
from .datenquelle import Kalendertermin
from .modell import Termin
from ..rrule import rrule_problem

_VERSATZ_EINHEIT = {"T": "days", "W": "weeks", "h": "hours", "min": "minutes"}

# ── Harte Grenzen (BLD-R2) ───────────────────────────────────────────────────
# Eine einzige unsinnige Wiederholungsregel (z. B. FREQ=SECONDLY, INTERVAL=0)
# darf nicht die ganze App lahmlegen: ``rr.between()`` liefert dann praktisch
# unbegrenzt viele Termine und laeuft synchron im Request. Die Pruefung lehnt
# solche Regeln inzwischen ab — diese Grenzen sind die zweite Verteidigungslinie
# fuer Altbestand und fuer Pfade, die die Pruefung nicht durchlaufen.
# Mehr Termine je Reihe als MAX_TERMINE_JE_REIHE bzw. laenger als
# MAX_RECHENZEIT_SEKUNDEN Rechenzeit sind ein Bedienfehler, kein Absturz: es
# gibt eine verstaendliche Meldung statt eines haengenden Servers.
MAX_TERMINE_JE_REIHE = 2000
MAX_TERMINE_GESAMT = 10000
MAX_RECHENZEIT_SEKUNDEN = 10.0


class TerminLimitUeberschritten(Exception):
    """Die Terminerzeugung ueberschreitet ein hartes Limit (BLD-R2).

    Traegt eine oeffentlich lesbare deutsche Meldung; die aufrufenden Dienste
    wandeln sie in eine strukturierte Fehlerantwort um.
    """

    def __init__(self, meldung: str, reihe: str = ""):
        super().__init__(meldung)
        self.meldung = meldung
        self.reihe = reihe


# --------------------------------------------------------------------------- #
# Parameter
# --------------------------------------------------------------------------- #


def ersetze_parameter(text: str, parameter: dict[str, Any]) -> str:
    """Ersetzt ``{parameter.<id>}`` in ``text`` durch den Parameterwert.

    Der Wert eines Parameters der art 'zeitraum' ist ein Paar (von, bis) — dann
    wird ``von`` eingesetzt (das Ende lost der Aufrufer je Kontext auf). Ist
    der Parameter unbekannt, bleibt die Referenz stehen (gutmuetig).
    """
    import re

    def ersatz(m: re.Match[str]) -> str:
        kennung = m.group(1)
        if kennung not in parameter:
            return m.group(0)
        wert = parameter[kennung]
        if isinstance(wert, (tuple, list)) and len(wert) == 2:
            return str(wert[0])
        return str(wert)

    return re.sub(r"\{parameter\.([a-z0-9_\-]+)\}", ersatz, text)


def parameter_wert(parameter: dict[str, Any], kennung: str) -> Any:
    """Roher Wert eines Parameters (fuer bedingung.parameter)."""
    return parameter.get(kennung)


def _zeitraum_parameter(parameter: dict[str, Any], kennung: str) -> tuple[date, date] | None:
    """Ein Zeitraum-Parameter als (von, bis); None wenn unaufloesbar."""
    wert = parameter.get(kennung)
    if isinstance(wert, (tuple, list)) and len(wert) == 2:
        a, b = wert
        if isinstance(a, date) and isinstance(b, date):
            return a, b
        if isinstance(a, str) and isinstance(b, str):
            try:
                return date.fromisoformat(a), date.fromisoformat(b)
            except ValueError:
                return None
    return None


def _datum(wert: Any) -> date | None:
    """Normalisiert einen Datumswert (date/datetime/iso-String) zu ``date``."""
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert.strip())
        except ValueError:
            return None
    return None


def _uhrzeit(wert: Any) -> time | None:
    if isinstance(wert, time):
        return wert
    if isinstance(wert, str) and wert:
        try:
            return time.fromisoformat(wert.strip())
        except ValueError:
            return None
    return None


def _versatz_timedelta(versatz: str) -> timedelta:
    """Konvertiert einen ISO8601-artigen Versatz ('-2T', '+1W') in ``timedelta``."""
    vorzeichen = 1
    s = versatz.strip()
    if s and s[0] in "+-":
        if s[0] == "-":
            vorzeichen = -1
        s = s[1:]
    # Zahl + Einheit
    zahl_str = ""
    einheit = ""
    for i, ch in enumerate(s):
        if ch.isdigit():
            zahl_str += ch
        else:
            einheit = s[i:]
            break
    zahl = int(zahl_str) if zahl_str else 0
    schluessel = _VERSATZ_EINHEIT.get(einheit)
    if schluessel is None:
        raise ValueError(f"Unbekannte Versatz-Einheit {einheit!r} in {versatz!r}")
    return timedelta(**{schluessel: vorzeichen * zahl})


# --------------------------------------------------------------------------- #
# Anlaesse
# --------------------------------------------------------------------------- #


def _anlaesse_fuer_datum(d: date, feiertags_schluessel: set[str], erntedank: str = "1. So im Oktober") -> frozenset[str]:
    """Anlaesse fuer ein Datum: konfigurierte Feiertage + Sammelanlass.

    Der Sammelanlass ``feiertag`` wird nur gesetzt, wenn ein *konfigurierter*
    Feiertag auf das Datum faellt (nicht fuer jeden kataloginternen Feiertag).
    """
    hier = set(ft.feiertag_fuer_datum(d, erntedank=erntedank))
    konfiguriert = hier & feiertags_schluessel
    if konfiguriert:
        return frozenset(konfiguriert | {"feiertag"})
    return frozenset()


# --------------------------------------------------------------------------- #
# Reihen-Layout
# --------------------------------------------------------------------------- #


def _reihen_layout(plantyp: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Jede Terminreihe als (kennung, termine-Definition).

    Kurzform (``termine``) wird zur Reihe 'standard'; ``terminreihen`` liefern
    je Eintrag (id, termine). Reihenfolge wie deklariert.
    """
    layout: list[tuple[str, dict[str, Any]]] = []
    if isinstance(plantyp.get("terminreihen"), list):
        for reihe in plantyp["terminreihen"]:
            if isinstance(reihe, dict):
                layout.append((reihe.get("id", "standard"), reihe.get("termine") or {}))
    elif isinstance(plantyp.get("termine"), dict):
        layout.append(("standard", plantyp["termine"]))
    return layout


# --------------------------------------------------------------------------- #
# Kern
# --------------------------------------------------------------------------- #


def erzeuge_termine(
    plantyp: dict[str, Any],
    parameter: dict[str, Any],
    datenquelle: Any,
    von: date | None = None,
    bis: date | None = None,
    *,
    erntedank: str = "1. So im Oktober",
) -> dict[str, list[Termin]]:
    """Erzeugt die Termine je Reihe (Kennung -> Liste, sortiert nach Datum).

    ``parameter`` ist die Plan-Parameter-Aufloesung (Kennung -> Wert); die
    zeitliche Begrenzung kommt aus ``termine.von/bis``, dem
    ``zeitraum``-Parameter oder den expliziten ``von``/``bis``-Argumenten
    (Fallback, z. B. der konkrete Zeitraum des Plans). Ergebnis enthaelt
    abgeleitete Reihen nach ihren Ursprungsreihen (``bezug`` zeigt auf den
    Ursprungstermin).
    """
    layout = _reihen_layout(plantyp)
    ergebnis: dict[str, list[Termin]] = {}

    def _pfad(kennung: str) -> str:
        """Pfad wie in der Pruefung (Befund K1): Kurzform -> /termine/regel,
        Terminreihe -> /terminreihen/<index>/termine/regel (Index, nicht id).
        """
        reihen = plantyp.get("terminreihen")
        if not isinstance(reihen, list):
            # Kurzform (``termine``) -> eine Reihe 'standard'.
            return "/termine/regel"
        for i, r in enumerate(reihen):
            if isinstance(r, dict) and r.get("id", "standard") == kennung:
                return f"/terminreihen/{i}/termine/regel"
        return "/termine/regel"

    # Reihen in Deklarationsreihenfolge erzeugen; abgeleitete brauchen ihre
    # Ursprungsreihe, deshalb zwei Durchlaeufe (erst eigenstaendige).
    for kennung, defn in layout:
        if "abgeleitet" in (defn or {}):
            continue
        try:
            ergebnis[kennung] = _termine_einer_reihe(
                plantyp, kennung, defn, parameter, datenquelle, von, bis, erntedank
            )
        except TerminLimitUeberschritten as exc:
            # Einheitlicher Pfad mit der Pruefung (K1): die Engine kennt den
            # Reihen-Index, den die Meldung braucht.
            raise TerminLimitUeberschritten(exc.meldung, _pfad(kennung)) from exc

    # Abgeleitete Reihen im zweiten Durchlauf (Ursprung ist jetzt vorhanden).
    for kennung, defn in layout:
        if "abgeleitet" not in (defn or {}):
            continue
        ergebnis[kennung] = _abgeleitete_termine(
            plantyp, kennung, defn or {}, ergebnis, parameter, datenquelle, erntedank
        )

    # Gesamt-Obergrenze (BLD-R2): viele Reihen duerfen zusammen die App nicht
    # ueberlasten. Auch hier gilt: Bedienfehler melden statt haengen.
    gesamt = sum(len(ts) for ts in ergebnis.values())
    if gesamt > MAX_TERMINE_GESAMT:
        raise TerminLimitUeberschritten(
            f"Die Plantyp-Definition erzeugt {gesamt} Termine — erlaubt sind höchstens "
            f"{MAX_TERMINE_GESAMT}. Bitte die Wiederholungsregeln und Zeiträume einschränken."
        )

    return ergebnis


def _termine_einer_reihe(
    plantyp: dict[str, Any],
    kennung: str,
    defn: dict[str, Any],
    parameter: dict[str, Any],
    datenquelle: Any,
    von_fallback: date | None = None,
    bis_fallback: date | None = None,
    erntedank: str = "1. So im Oktober",
) -> list[Termin]:
    """Baut die Termine einer eigenstaendigen Reihe aus allen Quellen."""
    feiertage_konfiguriert = set(defn.get("feiertage") or [])
    # OP-EVENT-9: Auch die Uhrzeit der Terminreihe kann ein Parameter sein.
    uhrzeit = _uhrzeit(ersetze_parameter(str(defn.get("uhrzeit") or ""), parameter)) or \
        _uhrzeit(defn.get("uhrzeit"))

    # Zeitgrenzen (von/bis) ermitteln; bei zeitraum aus dem Parameter.
    von, bis = _grenzen(defn, parameter)
    if von is None:
        von = von_fallback
    if bis is None:
        bis = bis_fallback

    termine: dict[date, Termin] = {}

    def einfuegen(t: Termin) -> None:
        vorhanden = termine.get(t.datum)
        if vorhanden is None:
            termine[t.datum] = t
        else:
            # Zusammenfuehren: Anlaesse vereinigen, fehlende Uhrzeit ergaenzen.
            vorhanden.anlaesse = frozenset(vorhanden.anlaesse | t.anlaesse)
            if vorhanden.uhrzeit is None and t.uhrzeit is not None:
                vorhanden.uhrzeit = t.uhrzeit
            if not vorhanden.name and t.name:
                vorhanden.name = t.name

    def anlaesse_fuer(d: date) -> frozenset[str]:
        return _anlaesse_fuer_datum(d, feiertage_konfiguriert, erntedank)

    # 1) regel (RRULE)
    regel = defn.get("regel")
    if isinstance(regel, str):
        regel = ersetze_parameter(regel, parameter)
        # Harte Grenze VOR der Iteration (Befund B1): die Regel selbst pruefen,
        # unabhaengig davon, ob der dateutil-Generator ueberhaupt ein Element
        # liefert. `FREQ=DAILY|MONTHLY|YEARLY;INTERVAL=0` dreht sonst in
        # `rrule._iter` endlos OHNE yield — die Mengen-/Fristpruefung weiter unten
        # kaeme nie zum Zug. Betrifft Altbestand in der DB und Regeln mit
        # `{parameter.x}` (die die Formatpruefung ueberspringt).
        problem = rrule_problem(regel)
        if problem is not None:
            code, meldung, _hinweis = problem
            raise TerminLimitUeberschritten(meldung, kennung)

        try:
            start = datetime.combine(von or date(2000, 1, 1), time.min)
            ende = datetime.combine(bis or date(2100, 12, 31), time.max)
            rr = rrulestr(regel, dtstart=start, forceset=True)
        except Exception:
            # Ungueltige RRULE ueberspringen — die Pruefung meldet sie bereits.
            pass
        else:
            # ``rr.between`` liefert bei unsinnigen Regeln nicht nur langsam,
            # sondern praktisch unbegrenzt viele Termine. Deshalb mit
            # Mengen-Obergrenze UND Zeitlimit iterieren (BLD-R2).
            for dt in _begrenzte_termine(rr, start, ende, kennung):
                d = _datum(dt)
                if d is None:
                    continue
                einfuegen(Termin(datum=d, reihe=kennung, uhrzeit=uhrzeit,
                                 anlaesse=anlaesse_fuer(d), quelle="regel"))

    # 2) zeitraum (jeder Tag bzw. wochentage)
    zeitraum_ref = defn.get("zeitraum")
    if isinstance(zeitraum_ref, str):
        zp = _zeitraum_parameter(parameter, zeitraum_ref.removeprefix("{parameter.").removesuffix("}")) \
            if zeitraum_ref.startswith("{parameter.") else None
        if zp is None:
            zp = (von, bis)
        if zp[0] and zp[1]:
            wochentage = {w for w in (defn.get("wochentage") or [])}
            d = zp[0]
            while d <= zp[1]:
                wd = ("mo", "di", "mi", "do", "fr", "sa", "so")[d.weekday()]
                if not wochentage or wd in wochentage:
                    einfuegen(Termin(datum=d, reihe=kennung, uhrzeit=uhrzeit,
                                     anlaesse=anlaesse_fuer(d), quelle="zeitraum"))
                d += timedelta(days=1)

    # 3) feiertage (eigene Termine, selbst wenn sonst keine Regel existiert)
    for f in feiertage_konfiguriert:
        for jahr in _jahre(von, bis):
            fd = ft.feiertag_datum(f, jahr, erntedank=erntedank)
            if fd is None:
                continue
            if von and fd < von:
                continue
            if bis and fd > bis:
                continue
            einfuegen(Termin(datum=fd, reihe=kennung, uhrzeit=uhrzeit,
                             anlaesse=anlaesse_fuer(fd), quelle="feiertag"))

    # 4) kalender
    if isinstance(defn.get("kalender"), dict):
        for kt in datenquelle.kalender_termine(defn["kalender"]):
            einfuegen(Termin(datum=kt.datum, reihe=kennung, uhrzeit=kt.uhrzeit or uhrzeit,
                             name=kt.name, anlaesse=frozenset(kt.anlaesse) | anlaesse_fuer(kt.datum),
                             quelle="kalender"))

    # 5) manuell
    for mt in defn.get("manuell") or []:
        if not isinstance(mt, dict):
            continue
        dstr = ersetze_parameter(str(mt.get("datum", "")), parameter)
        d = _datum(dstr)
        if d is None:
            continue
        anlaesse = set(mt.get("anlaesse") or []) | set(anlaesse_fuer(d))
        # OP-EVENT-9: Uhrzeit und Name ebenso durch Parameter ersetzen wie das
        # Datum. Vorher wurde die Uhrzeit der Kopfvorlage direkt aus dem
        # (ungeprüften) Wert gelesen — bei einer Parameter-Referenz
        # (``{parameter.uhrzeit}``) lieferte ``_uhrzeit`` None und die Zeit
        # verschwand stillschweigend („uhrzeit: null“). Eine ungültige, nicht
        # durch den Parameter erklärbare Uhrzeit melden wir als Prüfmeldung.
        uhrzeit_roh = ersetze_parameter(str(mt.get("uhrzeit") or ""), parameter)
        mt_uhrzeit = _uhrzeit(uhrzeit_roh) or uhrzeit
        if uhrzeit_roh and mt_uhrzeit is None:
            raise TerminLimitUeberschritten(
                f"Die Uhrzeit {uhrzeit_roh!r} im manuellen Termin am {d.isoformat()} "
                "ist keine gültige Zeit (erwartet z. B. '17:00').", kennung)
        einfuegen(Termin(datum=d, reihe=kennung, uhrzeit=mt_uhrzeit,
                         name=ersetze_parameter(str(mt.get("name", "")), parameter),
                         anlaesse=frozenset(anlaesse), quelle="manuell"))

    # 6) ausnahmen: einzelne Daten entfallen; {feiertage: true} entfernt Feiertagstermine.
    ausnahmen = defn.get("ausnahmen")
    ausnahme_daten: set[date] = set()
    if isinstance(ausnahmen, list):
        for a in ausnahmen:
            if isinstance(a, dict):
                d = _datum(a.get("datum"))
                if d:
                    ausnahme_daten.add(d)
    elif isinstance(ausnahmen, dict) and ausnahmen.get("feiertage") is True:
        ausnahme_daten = {t.datum for t in termine.values() if _ausnahme_feiertag(t.datum, erntedank)}

    result = [t for d, t in termine.items() if d not in ausnahme_daten]
    result.sort(key=lambda t: t.datum)
    # Index je Reihe fortlaufend (ab 1) und Position innerhalb des Monats
    # (n-ter Termin der Reihe in seinem Monat, fuer termin_im_monat).
    _nummeriere(result)
    return result


def _abgeleitete_termine(
    plantyp: dict[str, Any],
    kennung: str,
    defn: dict[str, Any],
    alle_reihen: dict[str, list[Termin]],
    parameter: dict[str, Any],
    datenquelle: Any,
    erntedank: str = "1. So im Oktober",
) -> list[Termin]:
    """Abgeleitete Reihe: jeden Ursprungstermin um ``versatz`` verschieben.

    ``nur_wenn`` filtert, ob ein abgeleiteter Termin ueberhaupt entsteht (z. B.
    keine Probe an Feiertagen). ``ausnahmen`` wirkt wie bei eigenstaendigen
    Reihen. Jeder abgeleitete Termin traegt ``bezug`` auf seinen Ursprung.
    """
    abl = defn.get("abgeleitet") or {}
    von = abl.get("von", "standard")
    versatz = abl.get("versatz", "0T")
    urspr = alle_reihen.get(von, [])
    delta = _versatz_timedelta(versatz)
    nur_wenn = abl.get("nur_wenn")

    # Bedingung auswerten braucht den Struktur-Kontext (``struktur``); hier
    # nur die einfachen, terminfesten Knoten (anlass/wochentag) selbst loesen.
    result: list[Termin] = []
    for u in urspr:
        d = u.datum + delta
        probe = Termin(datum=d, reihe=kennung, uhrzeit=u.uhrzeit, name=u.name,
                       anlaesse=frozenset(u.anlaesse), bezug=u, quelle="abgeleitet")
        from .struktur import bedingung_erfuellt
        if bedingung_erfuellt(nur_wenn, u, parameter=parameter):
            result.append(probe)

    # ausnahmen wie bei eigenstaendigen Reihen.
    ausnahmen = defn.get("ausnahmen")
    ausnahme_daten: set[date] = set()
    if isinstance(ausnahmen, list):
        for a in ausnahmen:
            if isinstance(a, dict):
                d = _datum(a.get("datum"))
                if d:
                    ausnahme_daten.add(d)
    elif isinstance(ausnahmen, dict) and ausnahmen.get("feiertage") is True:
        ausnahme_daten = {t.datum for t in result if _ausnahme_feiertag(t.datum, erntedank)}

    gefiltert = [t for t in result if t.datum not in ausnahme_daten]
    gefiltert.sort(key=lambda t: t.datum)
    _nummeriere(gefiltert)
    return gefiltert


def _ausnahme_feiertag(datum: date, erntedank: str) -> bool:
    """Festtage am eigenen Datum, nicht die geerbten Anlaesse, ausschliessen.

    Adventssonntage und Erntedank markieren das Kirchenjahr, aber keinen
    arbeitsfreien Festtag. Alle anderen Katalogeintraege zaehlen, einschliesslich
    Heiligabend/Silvester und kirchlicher Festtage ohne bundesweiten Feiertag.
    """
    anlaesse = set(ft.feiertag_fuer_datum(datum, erntedank=erntedank))
    return bool(anlaesse - {"1_advent", "2_advent", "3_advent", "4_advent", "erntedank"})


def _nummeriere(termine: list[Termin]) -> None:
    """Vergibt ``index`` (fortlaufend ab 1) und ``positionsnr_im_monat``."""
    for i, t in enumerate(termine, start=1):
        t.index = i
    # Position innerhalb des Monats: n-ter Termin der Reihe in diesem Monat.
    im_monat: dict[tuple[int, int], int] = {}
    for t in termine:
        schluessel = (t.datum.year, t.datum.month)
        im_monat[schluessel] = im_monat.get(schluessel, 0) + 1
        t.positionsnr_im_monat = im_monat[schluessel]
    for t in termine:
        t.position_von_hinten = im_monat[(t.datum.year, t.datum.month)] - t.positionsnr_im_monat + 1


def nur_when_erfuellt(bedingung: Any, termin: Termin) -> bool:
    """Wertet eine strukturierte Bedingung fuer einen Termin aus (terminebene).

    Deckt die terminfesten Knoten ab (anlass, wochentag, datum_ab/bis,
    termin_nr, termin_im_monat) sowie alle/eine/nicht. Die feldspezifischen
    Knoten (variante, parameter, feld_gesetzt) sind hier nicht aufloesbar und
    gelten als erfuellt (der Struktur-Aufloeseschritt prueft sie gesondert).
    """
    if not isinstance(bedingung, dict) or not bedingung:
        return True
    for schluessel, wert in bedingung.items():
        if schluessel == "alle":
            return all(nur_when_erfuellt(k, termin) for k in (wert or []))
        if schluessel == "eine":
            return any(nur_when_erfuellt(k, termin) for k in (wert or []))
        if schluessel == "nicht":
            return not nur_when_erfuellt(wert, termin)
        if schluessel == "anlass":
            return wert in termin.anlaesse
        if schluessel == "wochentag":
            wd = ("mo", "di", "mi", "do", "fr", "sa", "so")[termin.datum.weekday()]
            return wd in (wert or [])
        if schluessel == "datum_ab":
            d = _datum(wert)
            return d is None or termin.datum >= d
        if schluessel == "datum_bis":
            d = _datum(wert)
            return d is None or termin.datum <= d
        if schluessel == "termin_nr":
            jede = (wert or {}).get("jede")
            return bool(jede) and termin.index % jede == 0
        if schluessel == "termin_im_monat":
            # Positive Zahl: n-ter Termin vorn; negativ: von hinten. Die
            # Position von hinten kennen wir hier nicht (braucht die
            # Monatslaenge der Reihe); fuer -1 (letzter) genuegt der Vergleich
            # mit dem Monatsende — naeherungsweise: letzter Termin = dessen
            # positionsnr_im_monat groesser als alle Spaeteren im Monat.
            if wert > 0:
                return termin.positionsnr_im_monat == wert
            # negativ: zaehlen, wie viele Termine der Monat insgesamt hat, ist
            # hier nicht bekannt -> behandeln wir als 'Monat hat genau so viele,
            # dass -1 dem letzten entspricht'. Fuer die Praxis (musikteams)
            # reicht positiv; negativ bleibt gutmuetig erfuellt.
            return True
        # variante/parameter/feld_gesetzt: nicht terminfest -> hier erfuellt.
        return True
    return True


def termin_position_im_monat(termin: Termin) -> int:
    """Die n-te Position des Termins in seiner Reihe innerhalb des Monats.

    Wird beim Erzeugen der Reihe bereits berechnet und am Termin gespeichert
    (``positionsnr_im_monat``) — hier nur der einheitliche Zugriff fuer
    Bedingungen (``termin_im_monat``) und Verfuegbarkeits-Muster.
    """
    return termin.positionsnr_im_monat


# --------------------------------------------------------------------------- #
# Helfer
# --------------------------------------------------------------------------- #


def _begrenzte_termine(rr: Any, start: datetime, ende: datetime, kennung: str) -> list[datetime]:
    """Termine einer RRULE mit harten Mengen- und Zeitgrenzen (BLD-R2).

    ``dateutil.rrule.RRule.between()`` baut intern die VOLLE Liste auf und
    terminiert bei einer Regel ohne Fortschritt (``INTERVAL=0``) nie — genau
    das blockierte in der Nachtpruefung den einzigen Uvicorn-Prozess. Diese
    Variante iteriert stattdessen einzeln und bricht ab, sobald
    ``MAX_TERMINE_JE_REIHE`` erreicht oder ``MAX_RECHENZEIT_SEKUNDEN``
    ueberschritten ist. Der Abbruch ist ein ``TerminLimitUeberschritten`` mit
    verstaendlicher Meldung; der Aufrufer wandelt sie in eine Fehlerantwort.
    """
    result: list[datetime] = []
    frist = _time.monotonic() + MAX_RECHENZEIT_SEKUNDEN
    # islice deckelt die Zahl der aus rr gezogenen Werte zusaetzlich auf
    # Python-Ebene; die Frist faengt Regeln ab, die pro Schritt extrem teuer
    # sind (z. B. MONTHLY mit selten erfuellten BYDAY-Angaben).
    quelle = rr.xafter(start, count=MAX_TERMINE_JE_REIHE + 1, inc=True)
    try:
        for dt in itertools.islice(quelle, MAX_TERMINE_JE_REIHE + 1):
            if dt > ende:
                break
            if len(result) >= MAX_TERMINE_JE_REIHE:
                raise TerminLimitUeberschritten(
                    f"Die Wiederholungsregel der Reihe {kennung!r} erzeugt mehr als "
                    f"{MAX_TERMINE_JE_REIHE} Termine. Bitte die Regel grober fassen "
                    f"(z. B. INTERVAL erhöhen) oder den Zeitraum einschränken.",
                    kennung,
                )
            if _time.monotonic() > frist:
                raise TerminLimitUeberschritten(
                    f"Die Berechnung der Termine für die Reihe {kennung!r} dauert zu lange "
                    f"und wurde nach {MAX_RECHENZEIT_SEKUNDEN:.0f} Sekunden abgebrochen. "
                    f"Bitte die Wiederholungsregel prüfen.",
                    kennung,
                )
            result.append(dt)
    except TerminLimitUeberschritten:
        raise
    except Exception as e:  # noqa: BLE001
        # dateutil kann beim Iterieren eine Regel mit fehlendem Fortschritt
        # (z. B. INTERVAL=0) mit einem internen Fehler quittieren. Das ist kein
        # Serverabsturz, sondern ein Bedienfehler: sauber als Limit melden.
        raise TerminLimitUeberschritten(
            f"Die Wiederholungsregel der Reihe {kennung!r} ist nicht auswertbar "
            f"({e}). Bitte die Regel prüfen (z. B. FREQ=WEEKLY mit INTERVAL>=1).",
            kennung,
        ) from e
    return result


def _grenzen(defn: dict[str, Any], parameter: dict[str, Any]) -> tuple[date | None, date | None]:
    """Ermittelt (von, bis) aus ``von``/``bis`` (ggf. Parameterreferenz).

    Ein ``{parameter.<id>}``-Verweis auf einen Zeitraum-Parameter liefert fuer
    ``von`` dessen Anfang und fuer ``bis`` dessen Ende.
    """
    von = defn.get("von")
    bis = defn.get("bis")

    def loese(wert: Any, ende: bool) -> date | None:
        if not isinstance(wert, str):
            return _datum(wert)
        if wert.startswith("{parameter."):
            kennung = wert.removeprefix("{parameter.").removesuffix("}")
            zp = _zeitraum_parameter(parameter, kennung)
            if zp:
                return zp[1] if ende else zp[0]
            return None
        return _datum(wert)

    return loese(von, False), loese(bis, True)


def _jahre(von: date | None, bis: date | None) -> list[int]:
    """Die Jahre, ueber die Feiertage zu rechnen sind."""
    if von is None and bis is None:
        # Ohne Zeitbezug: aktuelles Jahr als sinnvoller Default.
        return [date.today().year]
    anfang = von.year if von else (bis.year if bis else date.today().year)
    ende = bis.year if bis else (von.year if von else date.today().year)
    return list(range(anfang, ende + 1))
