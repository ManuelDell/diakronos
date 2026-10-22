"""P0-2 — Server-Hänger beseitigen (BLD-R2 + UXP-R1, UXP-R11).

Die Nachtpruefung vom 16.10. zeigte, dass EINE einzige Plan-Vorlage mit einer
unbegrenzten Wiederholungsregel (``INTERVAL=0`` oder ``FREQ=SECONDLY``) die
gesamte App lahmlegen kann: die Pruefung liess sie durch, die Engine lief in
``dateutil.rrule.between()`` endlos, und weil nur ein Uvicorn-Prozess lief,
blockierte die Anfrage jeden anderen Nutzer (BLD-R2, gemeldet auch als UXP-R1).

Diese Tests reproduzieren beide Ursachen und pruefen die Behebung, ohne dass
sie haengen bleiben koennen:

- ``test_rrule_*``: die Pruefung lehnt ``INTERVAL=0`` und zu feine Frequenzen
  als FEHLER ab (vorher: ``gueltig: true``); sinnvolle Regeln bleiben gueltig.
- ``test_engine_*``: die Engine hat eine harte Mengen- und Zeitgrenze und
  meldet einen Bedienfehler (``TerminLimitUeberschritten``) statt zu haengen.
- ``test_speichern_*``: eine unzulässige Regel laesst sich nicht speichern.

Reines Python ohne DB/Redis/HTTP.
"""

from __future__ import annotations

import time
from datetime import date

import pytest

from diakronos_app.planrahmen.engine.termine import (
    MAX_TERMINE_JE_REIHE,
    TerminLimitUeberschritten,
    erzeuge_termine,
)
from diakronos_app.planrahmen.pruefung import Meldung, pruefe_plantyp


def _plantyp(regel: str, **termine_extra) -> dict:
    return {
        "schema": "diakronos/plantyp@1",
        "id": "test",
        "termine": {"regel": regel, "uhrzeit": "10:00", **termine_extra},
    }


def _codes(meldungen: list[Meldung]) -> set[str]:
    return {m.code for m in meldungen}


def _fehler_mit_code(meldungen: list[Meldung], code: str) -> Meldung:
    for m in meldungen:
        if m.code == code:
            return m
    raise AssertionError(f"keine Meldung mit code {code!r} in {[m.code for m in meldungen]}")


class _LeereQuelle:
    """Minimale Datenquelle: keine Kalender-/Personendaten greifbar."""

    def kalender_termine(self, *_args, **_kwargs):  # noqa: D102
        return []

    def personen(self, *_args, **_kwargs):  # noqa: D102
        return []

    def merkmale(self, *_args, **_kwargs):  # noqa: D102
        return []


# --------------------------------------------------------------------------- #
# BLD-R2 / UXP-R1 — Pruefung lehnt unbegrenzte Regeln ab
# --------------------------------------------------------------------------- #


def test_rrule_interval_null_ist_fehler() -> None:
    """INTERVAL=0 wiederholt sich nie fort -> FEHLER (vorher: gueltig)."""
    m = pruefe_plantyp(_plantyp("FREQ=WEEKLY;INTERVAL=0"))
    fehler = _fehler_mit_code(m, "rrule_interval_ungueltig")
    assert fehler.pfad == "/termine/regel"
    assert fehler.stufe == "fehler"


def test_rrule_interval_negativ_ist_fehler() -> None:
    m = pruefe_plantyp(_plantyp("FREQ=WEEKLY;INTERVAL=-1"))
    assert "rrule_interval_ungueltig" in _codes(m)


def test_rrule_interval_leer_ist_fehler() -> None:
    m = pruefe_plantyp(_plantyp("FREQ=WEEKLY;INTERVAL="))
    assert "rrule_interval_ungueltig" in _codes(m)


def test_rrule_interval_eins_ist_gueltig() -> None:
    """INTERVAL=1 ist die Vorgabe — ausdruecklich erlaubt."""
    assert pruefe_plantyp(_plantyp("FREQ=WEEKLY;INTERVAL=1;BYDAY=SU")) == []


def test_rrule_interval_zwei_ist_gueltig() -> None:
    assert pruefe_plantyp(_plantyp("FREQ=WEEKLY;INTERVAL=2")) == []


@pytest.mark.parametrize("freq", ["SECONDLY", "MINUTELY", "HOURLY"])
def test_rrule_zu_feine_frequenz_ist_fehler(freq: str) -> None:
    """SECONDLY/MINUTELY/HOURLY erzeugen unnoetig viele Termine -> FEHLER."""
    m = pruefe_plantyp(_plantyp(f"FREQ={freq}"))
    fehler = _fehler_mit_code(m, "rrule_freq_zu_fein")
    assert fehler.pfad == "/termine/regel"


@pytest.mark.parametrize("freq", ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"])
def test_rrule_grobe_frequenz_ist_gueltig(freq: str) -> None:
    assert pruefe_plantyp(_plantyp(f"FREQ={freq}")) == []


def test_rrule_kleingeschrieben_wird_erkannt() -> None:
    """Die Pruefung ist gross-/kleinschreibungsunabhaengig."""
    assert "rrule_freq_zu_fein" in _codes(pruefe_plantyp(_plantyp("FREQ=secondly")))


def test_rrule_wird_auch_in_terminreihen_geprueft() -> None:
    """Eine unbegrenzte Regel in einer Terminreihe ist genauso unsicher."""
    d = {
        "schema": "diakronos/plantyp@1",
        "id": "test",
        "terminreihen": [
            {"id": "probe", "termine": {"regel": "FREQ=SECONDLY"}},
        ],
    }
    fehler = _fehler_mit_code(pruefe_plantyp(d), "rrule_freq_zu_fein")
    assert fehler.pfad == "/terminreihen/0/termine/regel"


def test_speichern_lehnt_unbegrenzte_regel_ab() -> None:
    """Pruefung UND Speichern nutzen dieselbe Regel: ungueltig bleibt ungueltig.

    ``plantyp_speichern`` ruft intern ``_definition`` -> ``plantyp_pruefen``;
    die ungueltige Regel darf also nie in einer Version landen (Ursache 4
    laut BLD-R2: 'die Vorlage laesst sich speichern und blockiert danach jede
    Plan-Aktion'). Hier direkt gegen die Pruefung geprueft, die das Speichern
    gated — die DB-Variante deckt test_planrahmen_dienste.py ab.
    """
    ergebnis = pruefe_plantyp(_plantyp("FREQ=WEEKLY;INTERVAL=0"))
    fehler = [m for m in ergebnis if m.stufe == "fehler"]
    assert fehler, "unbegrenzte Regel darf nicht als gueltig durchgehen"


# --------------------------------------------------------------------------- #
# BLD-R2 — harte Engine-Grenze (Menge + Rechenzeit)
# --------------------------------------------------------------------------- #


def test_engine_bricht_bei_zu_vielen_termine_ab() -> None:
    """Eine Regel, die mehr als MAX_TERMINE_JE_REIHE ergibt, bricht ab.

    Ohne die Grenze liefe ``rr.between`` ueber den ganzen Zeitraum und legte
    die App lahm. Der Abbruch ist eine verstaendliche Meldung, kein Haenger.
    """
    # FREQ=DAILY ueber viele Jahre: weit mehr als 2 000 Termine. Bewusst KEIN
    # FREQ=SECONDLY — das wird von der Vorabpruefung in der Engine schon vor
    # der Iteration abgelehnt (siehe test_engine_lehnt_zu_feine_frequenz_vorab_ab).
    plantyp = _plantyp("FREQ=DAILY")
    start = time.monotonic()
    with pytest.raises(TerminLimitUeberschritten) as info:
        erzeuge_termine(plantyp, {}, _LeereQuelle(),
                        von=date(2000, 1, 1), bis=date(2100, 1, 1))
    dauer = time.monotonic() - start
    # Muss SCHNELL abbrechen (die Grenze greift beim 2001. Termin).
    assert dauer < 5.0, f"Abbruch dauerte {dauer:.2f}s — Grenze greift nicht"
    assert str(MAX_TERMINE_JE_REIHE) in info.value.meldung


def test_engine_lehnt_zu_feine_frequenz_vorab_ab() -> None:
    """FREQ=SECONDLY bricht SOFORT ab, ohne die Iteration zu starten (B1).

    Die Regelpruefung in der Engine (``rrule_problem``) lehnt die Regel ab,
    bevor dateutil ueberhaupt zu iterieren beginnt — schneller und mit
    praeziserer Meldung als das Mengenlimit.
    """
    plantyp = _plantyp("FREQ=SECONDLY")
    start = time.monotonic()
    with pytest.raises(TerminLimitUeberschritten) as info:
        erzeuge_termine(plantyp, {}, _LeereQuelle(),
                        von=date(2026, 1, 1), bis=date(2026, 1, 2))
    assert time.monotonic() - start < 1.0
    assert "SECONDLY" in info.value.meldung or "feiner" in info.value.meldung


def test_engine_begrenzt_kalendertermine_nicht_faelschlich() -> None:
    """Eine sinnvolle Regel liefert weiter alle Termine (keine Regression)."""
    from datetime import date

    plantyp = _plantyp("FREQ=WEEKLY;BYDAY=SU")
    ergebnis = erzeuge_termine(plantyp, {}, _LeereQuelle(), von=date(2026, 1, 1), bis=date(2026, 12, 31))
    assert len(ergebnis["standard"]) == 52


def test_engine_haengt_nicht_bei_interval_null() -> None:
    """INTERVAL=0 in einer Alt-JSON darf die Engine nicht mehr blockieren.

    Der Parser akzeptiert ``INTERVAL=0`` syntaktisch; die Engine muss dennoch
    innerhalb der Zeitgrenze zurueckkehren oder sauber abbrechen — nie
    unbegrenzt laufen (genau das war der Ausfall in BLD-R2).
    """
    from datetime import date

    plantyp = _plantyp("FREQ=WEEKLY;INTERVAL=0")
    start = time.monotonic()
    try:
        erzeuge_termine(plantyp, {}, _LeereQuelle(), von=date(2026, 1, 1), bis=date(2026, 3, 1))
    except TerminLimitUeberschritten:
        pass  # erlaubt: saubere Meldung statt Haenger
    dauer = time.monotonic() - start
    assert dauer < 12.0, f"Engine lief {dauer:.2f}s — Grenze greift nicht"


# --------------------------------------------------------------------------- #
# P0-2b — Nacharbeit: harte Grenze fuer ALLE FREQ (Befund B1)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("freq", ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"])
@pytest.mark.parametrize("schreibweise", ["FREQ={freq};INTERVAL=0", "freq={freq_lower};interval=0"])
def test_engine_bricht_bei_interval_null_fuer_jede_freq_ab(freq: str, schreibweise: str) -> None:
    """INTERVAL=0 muss fuer JEDE Frequenz sofort abbrechen (P0-2b, B1).

    Vorher deckte der Test nur WEEKLY ab (das zufaellig "day is out of range"
    wirft) — DAILY/MONTHLY/YEARLY drehten in ``dateutil.rrule._iter`` endlos
    OHNE yield, sodass die spaetere Mengen-/Fristpruefung nie zum Zug kam.
    Der Test wuerde ohne die Grenze in der Engine selbst haengen; pytest-timeout
    (siehe pyproject) bricht ihn dann ab (nicht bestanden) statt zu blockieren.
    """
    from datetime import date

    regel = schreibweise.format(freq=freq, freq_lower=freq.lower())
    plantyp = _plantyp(regel)
    start = time.monotonic()
    with pytest.raises(TerminLimitUeberschritten):
        erzeuge_termine(plantyp, {}, _LeereQuelle(), von=date(2026, 1, 1), bis=date(2026, 3, 1))
    dauer = time.monotonic() - start
    assert dauer < 2.0, f"Engine lief {dauer:.2f}s — die Grenze greift nicht vor der Iteration"


def test_engine_bricht_bei_parameter_platzhalter_mit_interval_null_ab() -> None:
    """Auch eine Regeln mit ``{parameter.x}`` darf die Engine nicht blockieren.

    Die Pruefung ueberspringt Regeln mit Parameter-Platzhaltern; erst die
    Engine ersetzt sie. Genau hier fehlte die zweite Verteidigungslinie (B1).
    """
    from datetime import date

    plantyp = _plantyp("FREQ={parameter.frequenz};INTERVAL=0")
    with pytest.raises(TerminLimitUeberschritten):
        erzeuge_termine(plantyp, {"frequenz": "DAILY"}, _LeereQuelle(),
                        von=date(2026, 1, 1), bis=date(2026, 3, 1))


def test_engine_meldet_pfad_der_terminreihe_als_index() -> None:
    """Die Meldung nennt denselben Pfad wie die Pruefung (K1: Index statt id)."""
    from datetime import date

    plantyp = {
        "schema": "diakronos/plantyp@1",
        "id": "test",
        "terminreihen": [
            {"id": "proben", "termine": {"regel": "FREQ=WEEKLY"}},
            {"id": "gottesdienste", "termine": {"regel": "FREQ=DAILY;INTERVAL=0"}},
        ],
    }
    with pytest.raises(TerminLimitUeberschritten) as info:
        erzeuge_termine(plantyp, {}, _LeereQuelle(), von=date(2026, 1, 1), bis=date(2026, 3, 1))
    assert info.value.reihe == "/terminreihen/1/termine/regel"


# --------------------------------------------------------------------------- #
# P0-2b — Pruefung: Mehrzeiler, Expansion, Kleinschreibung (W1, W3, K2)
# --------------------------------------------------------------------------- #


def test_rrule_mehrzeilig_wird_abgelehnt() -> None:
    """Eine mehrzeilige Regel mit einer zweiten RRULE ist ein FEHLER (W1).

    Vorher lieferte ``'FREQ=WEEKLY\\nRRULE:FREQ=SECONDLY'`` 0 Meldungen, weil
    nur der ERSTE FREQ-Treffer geprueft wurde.
    """
    m = pruefe_plantyp(_plantyp("FREQ=WEEKLY\nRRULE:FREQ=SECONDLY"))
    assert "rrule_mehrzeilig" in _codes(m)


@pytest.mark.parametrize("praefix", ["RRULE:", "EXRULE:", "RDATE:", "EXDATE:"])
def test_rrule_praefigierte_zeile_wird_abgelehnt(praefix: str) -> None:
    m = pruefe_plantyp(_plantyp(f"{praefix}FREQ=WEEKLY"))
    assert _codes(m) & {"rrule_mehrzeilig", "rrule_unvollstaendig", "rrule_unlesbar"}


def test_rrule_zweiter_freq_treffer_wird_geprueft() -> None:
    """Auch ein zweiter FREQ-Wert im selben String wird erkannt (W1)."""
    m = pruefe_plantyp(_plantyp("FREQ=WEEKLY;FREQ=SECONDLY"))
    assert "rrule_freq_zu_fein" in _codes(m)


@pytest.mark.parametrize("regel", [
    "FREQ=DAILY;BYHOUR=0,1,2",
    "FREQ=DAILY;BYMINUTE=0,15,30,45",
    "FREQ=DAILY;BYSECOND=0",
])
def test_rrule_expansion_wird_abgelehnt(regel: str) -> None:
    """BYHOUR/BYMINUTE/BYSECOND vervielfachen Termine je Tag (W3).

    BYSETPOS gehoert NICHT dazu (P0-4b/N1): es vervielfacht nichts, sondern
    waehlt aus — 'letzter Sonntag im Monat' ist
    `FREQ=MONTHLY;BYDAY=SU;BYSETPOS=-1`. Siehe
    `tests/test_p0_4b_registrierung_nacharbeit.py::test_n1_bysetpos_erlaubt`.
    """
    m = pruefe_plantyp(_plantyp(regel))
    assert "rrule_expansion_zu_fein" in _codes(m)


def test_rrule_bysetpos_ist_erlaubt() -> None:
    """P0-4b/N1: BYSETPOS waehlt aus und ist deshalb zulaessig."""
    m = pruefe_plantyp(_plantyp("FREQ=MONTHLY;BYDAY=SU;BYSETPOS=-1"))
    assert "rrule_expansion_zu_fein" not in _codes(m)


def test_rrule_interval_null_mit_expansion_ist_fehler() -> None:
    m = pruefe_plantyp(_plantyp("FREQ=DAILY;BYHOUR=0;INTERVAL=0"))
    assert "rrule_interval_ungueltig" in _codes(m)


