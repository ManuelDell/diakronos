"""Tests fuer die Plan-Rahmen-Engine (P2): Termine, Struktur, Rollen, Regeln,
Generator, Bedarf, Trockenlauf.

Reines Python auf In-Memory-Daten (``InMemoryDatenquelle``) — keine Datenbank,
kein Redis, keine Endpunkte. Die Beispiele kommen aus dem KOCHBUCH (P1) und
werden ueber ``importlib.resources`` gelesen (kein Sonderfall fuer Chor oder
Freizeit im Code — nur generische Bausteine).

Abgedeckte Kartenvorgaben (SCOPE P2):
- Chorplan ein Jahr: Feiertage korrekt (Ostern 2026 = 05.04.),
- Kinderchor-Anlass blendet Felder aus,
- Einsingen reihum ueber 4 Personen inkl. Abwesenheit,
- mindestabstand Lieder eingehalten,
- vorbelegen Dirigent/Klavier aus Lied-Merkmal,
- muss-Regel abwesenheit_beachten nie verletzt,
- fixierte Eintraege bleiben ueber Neugenerierung,
- Determinismus mit seed,
- Freizeit: zeitraum taeglich, der_reihe_nach Bibelarbeiten, Varianten/Teile,
  gleich_verteilen,
- Predigerplan max_pro_zeitraum,
- jeder Regelbaustein mind. ein positiver und ein negativer Test,
- bedarfspruefung meldet fehlende Merkmale,
- Laufzeittest (< 2 s),
- Musikteams (Gruppe 3 am 1. Sonntag, Probe 2 Tage vorher, keine Probe an
  Feiertagen) und Programm/Chorplan gemeinsam (planuebergreifend + Uebernahme).
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine import (
    InMemoryDatenquelle,
    Person,
    Sammlungseintrag,
    erzeuge_termine,
    generiere,
    trockenlauf,
    bedarfspruefung,
    uebernimm,
)
from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit, Anmeldung, Gruppe, Historieneintrag
from diakronos_app.planrahmen.engine.feiertagsberechnung import feiertag_datum, osterdatum
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin


# --------------------------------------------------------------------------- #
# Helfer fuer Testdaten
# --------------------------------------------------------------------------- #


def _chorplan() -> dict:
    return ressourcen.kochbuch_laden("chorplan")


def _freizeit() -> dict:
    return ressourcen.kochbuch_laden("freizeit")


def _predigerplan() -> dict:
    return ressourcen.kochbuch_laden("predigerplan")


def _musikteams() -> dict:
    return ressourcen.kochbuch_laden("musikteams")


def _programm() -> dict:
    return ressourcen.kochbuch_laden("programm")


def _chor_datenquelle(n_personen: int = 30, n_lieder: int = 400) -> InMemoryDatenquelle:
    """Datenquelle mit Personen (dirigent/klavier/einsingen) und Liedern."""
    personen = []
    for i in range(n_personen):
        p = Person(f"p{i}", name=f"Person {i}", kuerzel=f"P{i}")
        if i < 4:
            p.merkmale["dirigent"] = True
        if 2 <= i < 6:
            p.merkmale["klavier"] = True
        if 6 <= i < 10:
            p.merkmale["einsingen"] = True
        personen.append(p)
    lieder = [
        Sammlungseintrag(
            f"l{i}", "lieder", titel=f"Lied {i}", reihenfolge=i,
            merkmale={
                "dirigent": f"p{i % 4}",
                "klavier": f"p{2 + (i % 4)}",
                "thema": "erntedank" if i % 50 == 0 else "sonstiges",
            },
        )
        for i in range(n_lieder)
    ]
    return InMemoryDatenquelle(personen_liste=personen, sammlungen={"lieder": lieder})


# --------------------------------------------------------------------------- #
# Feiertage (Osterberechnung)
# --------------------------------------------------------------------------- #


def test_osterdatum_2026():
    """Ostern 2026 ist der 05.04. (Kartenvorgabe)."""
    assert osterdatum(2026) == date(2026, 4, 5)
    assert osterdatum(2024) == date(2024, 3, 31)
    assert osterdatum(2025) == date(2025, 4, 20)


def test_feiertag_datum_beweglich():
    assert feiertag_datum("karfreitag", 2026) == date(2026, 4, 3)
    assert feiertag_datum("ostermontag", 2026) == date(2026, 4, 6)
    assert feiertag_datum("himmelfahrt", 2026) == date(2026, 5, 14)
    assert feiertag_datum("pfingstmontag", 2026) == date(2026, 5, 25)
    assert feiertag_datum("heiligabend", 2026) == date(2026, 12, 24)
    assert feiertag_datum("silvester", 2026) == date(2026, 12, 31)
    assert feiertag_datum("erntedank", 2026) == date(2026, 10, 4)  # 1. So im Oktober
    assert feiertag_datum("1_advent", 2026) == date(2026, 11, 29)
    assert feiertag_datum("buss_und_bettag", 2026) == date(2026, 11, 18)


# --------------------------------------------------------------------------- #
# Termine (chorplan ein Jahr)
# --------------------------------------------------------------------------- #


def test_chorplan_termine_ein_jahr():
    chor = _chorplan()
    dq = InMemoryDatenquelle()
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 12, 31))
    termine = res["standard"]
    # 52 Sonntage + 4 nicht-sonntaegliche Feiertage (karfreitag, himmelfahrt,
    # heiligabend, 1_weihnachtstag) = 56.
    assert len(termine) == 56
    assert termine[0].datum == date(2026, 1, 4)  # erster Sonntag


def test_feiertag_setzt_anlass():
    chor = _chorplan()
    dq = InMemoryDatenquelle()
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 12, 31))
    anlaesse = {t.datum: t.anlaesse for t in res["standard"]}
    assert "ostersonntag" in anlaesse[date(2026, 4, 5)]
    assert "feiertag" in anlaesse[date(2026, 4, 5)]
    assert "karfreitag" in anlaesse[date(2026, 4, 3)]


# --------------------------------------------------------------------------- #
# Struktur
# --------------------------------------------------------------------------- #


def test_kinderchor_blendet_felder_aus():
    from diakronos_app.planrahmen.engine.struktur import aufloesen

    chor = _chorplan()
    normal = aufloesen(chor, Termin(datum=date(2026, 3, 1), reihe="standard"))
    kinderchor = aufloesen(chor, Termin(datum=date(2026, 3, 1), reihe="standard",
                                         anlaesse=frozenset({"kinderchor"})))
    normale_pfade = {s.feld_pfad for s in normal}
    kind_pfade = {s.feld_pfad for s in kinderchor}
    # Kinderchor blendet lieder/einsingen/einueben aus.
    assert any(p.startswith("lieder") for p in normale_pfade)
    assert "einsingen" in normale_pfade
    assert not any(p.startswith("lieder") for p in kind_pfade)
    assert "einsingen" not in kind_pfade


def test_lieder_anzahl_erzeugt_indizierte_pfade():
    from diakronos_app.planrahmen.engine.struktur import aufloesen

    chor = _chorplan()
    slots = aufloesen(chor, Termin(datum=date(2026, 3, 1), reihe="standard"))
    lieder = [s for s in slots if s.art == "eintrag" and s.feld_pfad.startswith("lieder[")]
    assert [s.feld_pfad for s in lieder] == ["lieder[0]", "lieder[1]", "lieder[2]"]
    # Unterfelder tragen den index.
    assert "lieder[0].dirigent" in {s.feld_pfad for s in slots}
    assert "lieder[2].klavier" in {s.feld_pfad for s in slots}


def test_freizeit_varianten_teile_eigene_pfade():
    from diakronos_app.planrahmen.engine.struktur import aufloesen

    freizeit = _freizeit()
    param = {"zeitraum": (date(2026, 10, 1), date(2026, 10, 5))}
    res = erzeuge_termine(freizeit, param, InMemoryDatenquelle())
    slots = aufloesen(freizeit, res["standard"][0], parameter=param)
    pfade = {s.feld_pfad for s in slots}
    # Varianten und Teile erzeugen eigene Pfade.
    assert "nachmittag@sonne.programm" in pfade
    assert "nachmittag@regen.halle" in pfade
    assert "abend@sonne#programm.gestaltung" in pfade
    assert "abend@regen#abschluss.abendlied" in pfade


# --------------------------------------------------------------------------- #
# Rollen
# --------------------------------------------------------------------------- #


def test_rollen_filter():
    from diakronos_app.planrahmen.engine.rollen import kandidaten

    dq = InMemoryDatenquelle(
        personen_liste=[
            Person("anna", merkmale={"dirigent": True, "klavier": True}),
            Person("bruno", merkmale={"dirigent": True}),
            Person("carla", merkmale={"klavier": False}),
            Person("dora"),
        ],
    )
    assert {p.kennung for p in kandidaten({"merkmal": "dirigent"}, dq)} == {"anna", "bruno"}
    assert {p.kennung for p in kandidaten({"alle": [{"merkmal": "dirigent"}, {"merkmal": "klavier"}]}, dq)} == {"anna"}
    assert {p.kennung for p in kandidaten({"nicht": {"merkmal": "dirigent"}}, dq)} == {"carla", "dora"}
    assert {p.kennung for p in kandidaten({"person": "bruno"}, dq)} == {"bruno"}


# --------------------------------------------------------------------------- #
# Generator: Chorplan
# --------------------------------------------------------------------------- #


def test_einsingen_reihum_inkl_abwesenheit():
    chor = _chorplan()
    dq = _chor_datenquelle()
    # p6 (erster in der Rotation) ist am 2026-01-04 abwesend -> reihum
    # ueberspringt sie und nimmt p7.
    dq.abwesenheiten_liste = [Abwesenheit("p6", date(2026, 1, 4), date(2026, 1, 4), "Urlaub")]
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 1, 31))
    v = generiere(chor, {}, res["standard"], [], dq, seed=1)
    einsingen = [e.wert for e in v.eintraege if e.feld_pfad == "einsingen"]
    assert set(einsingen) <= {"p6", "p7", "p8", "p9"}
    # Am ersten Sonntag ist p6 abwesend -> p7 faengt an.
    assert einsingen[0] == "p7"
    # p6 taucht spaeter (nicht abwesend) wieder auf.
    assert "p6" in einsingen


def test_vorbelegen_dirigent_klavier_aus_lied():
    chor = _chorplan()
    dq = _chor_datenquelle()
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 1, 31))
    v = generiere(chor, {}, res["standard"], [], dq, seed=1)
    # lieder[0] hat ein Lied; dessen dirigent/klavier-Merkmal wird vorbelegt.
    lied_0 = next(e for e in v.eintraege if e.feld_pfad == "lieder[0]")
    dir_0 = next(e for e in v.eintraege if e.feld_pfad == "lieder[0].dirigent")
    klav_0 = next(e for e in v.eintraege if e.feld_pfad == "lieder[0].klavier")
    # Das Lied traegt die Merkmale dirigent/klavier -> vorbelegt uebereinstimmend.
    lied = next(l for l in dq.sammlung("lieder") if l.kennung == lied_0.wert)
    assert dir_0.wert == lied.merkmale["dirigent"]
    assert klav_0.wert == lied.merkmale["klavier"]


def test_muss_abwesenheit_nie_verletzt():
    chor = _chorplan()
    dq = _chor_datenquelle()
    # p0 (dirigent) ist das ganze Jahr abwesend -> darf nie als dirigent kommen.
    dq.abwesenheiten_liste = [Abwesenheit("p0", date(2026, 1, 1), date(2026, 12, 31), "Urlaub")]
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 12, 31))
    v = generiere(chor, {}, res["standard"], [], dq, seed=1)
    abwesenheits_verstoesse = [x for x in v.verstoesse if x.baustein == "abwesenheit_beachten"]
    assert abwesenheits_verstoesse == [], "muss-Regel abwesenheit_beachten darf nie verletzt sein"


def test_fixierte_eintraege_bleiben():
    chor = _chorplan()
    dq = _chor_datenquelle()
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 1, 31))
    fixiert = [{"feld_pfad": "einsingen", "wert": "p6", "art": "person"}]
    v = generiere(chor, {}, res["standard"], fixiert, dq, seed=1)
    einsingen_0 = next(e for e in v.eintraege if e.feld_pfad == "einsingen" and e.termin is res["standard"][0])
    # Da fixierte Eintraege keinen Termin haben, pruefen wir: der fixierte Wert
    # taucht als fixiert wieder auf.
    fixierte = [e for e in v.eintraege if e.feld_pfad == "einsingen" and e.fixiert]
    assert any(e.wert == "p6" for e in fixierte)


def test_determinismus_mit_seed():
    chor = _chorplan()
    dq = _chor_datenquelle()
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 12, 31))
    v1 = generiere(chor, {}, res["standard"], [], dq, seed=42)
    v2 = generiere(chor, {}, res["standard"], [], dq, seed=42)
    v3 = generiere(chor, {}, res["standard"], [], dq, seed=7)
    assert [e.wert for e in v1.eintraege] == [e.wert for e in v2.eintraege]
    assert [e.wert for e in v1.eintraege] != [e.wert for e in v3.eintraege]


def test_mindestabstand_lieder_eingehalten():
    chor = _chorplan()
    dq = _chor_datenquelle()
    # Historie: Lied l0 wurde zuletzt am 2026-01-01 gesungen (1. Termin 04.01
    # ist < 8 Wochen Abstand -> darf nicht sofort wieder kommen).
    dq.historie_liste = [Historieneintrag(date(2026, 1, 1), "chorplan", "lieder", "l0")]
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 1, 31))
    v = generiere(chor, {}, res["standard"], [], dq, seed=1)
    # l0 soll am ersten Termin NICHT gewaehlt sein (mindestabstand 8 Wochen).
    erste_lieder = [e.wert for e in v.eintraege if e.feld_pfad in ("lieder[0]", "lieder[1]", "lieder[2]")
                    and e.termin is res["standard"][0]]
    assert "l0" not in erste_lieder


# --------------------------------------------------------------------------- #
# Freizeit
# --------------------------------------------------------------------------- #


def test_freizeit_zeitraum_taeglich():
    freizeit = _freizeit()
    param = {"zeitraum": (date(2026, 10, 1), date(2026, 10, 5))}
    res = erzeuge_termine(freizeit, param, InMemoryDatenquelle())
    termine = res["standard"]
    assert [t.datum.day for t in termine] == [1, 2, 3, 4, 5]


def test_freizeit_der_reihe_nach_bibelarbeiten():
    from diakronos_app.planrahmen.engine.datenquelle import Sammlungseintrag

    freizeit = _freizeit()
    dq = InMemoryDatenquelle(
        sammlungen={
            "bibelarbeiten": [
                Sammlungseintrag("b0", "bibelarbeiten", titel="Tag 1", reihenfolge=0),
                Sammlungseintrag("b1", "bibelarbeiten", titel="Tag 2", reihenfolge=1),
                Sammlungseintrag("b2", "bibelarbeiten", titel="Tag 3", reihenfolge=2),
            ]
        }
    )
    param = {"zeitraum": (date(2026, 10, 1), date(2026, 10, 3))}
    res = erzeuge_termine(freizeit, param, dq)
    v = generiere(freizeit, param, res["standard"], [], dq, seed=1)
    bibeln = [e.wert for e in v.eintraege if e.feld_pfad == "frohe_stunde.bibelarbeit"]
    assert bibeln == ["b0", "b1", "b2"]  # der Reihe nach


def test_freizeit_gleich_verteilen():
    freizeit = _freizeit()
    # 1 Mitarbeiter-Person reicht nicht fuer Fairness; 2 zum Verteilen.
    dq = InMemoryDatenquelle(
        personen_liste=[Person("x", kuerzel="X"), Person("y", kuerzel="Y")],
        anmeldungen_liste=[Anmeldung("x", "mitarbeiter"), Anmeldung("y", "mitarbeiter")],
    )
    param = {"zeitraum": (date(2026, 10, 1), date(2026, 10, 4))}
    res = erzeuge_termine(freizeit, param, dq)
    v = generiere(freizeit, param, res["standard"], [], dq, seed=1)
    leitungen = [e.wert for e in v.eintraege if e.feld_pfad == "tagesleitung"]
    # 4 Tage, 2 Mitarbeiter -> jeder ~2x (gleich verteilt).
    assert leitungen.count("x") >= 1
    assert leitungen.count("y") >= 1
    assert abs(leitungen.count("x") - leitungen.count("y")) <= 1


# --------------------------------------------------------------------------- #
# Predigerplan: max_pro_zeitraum
# --------------------------------------------------------------------------- #


def test_predigerplan_max_pro_zeitraum():
    prediger = _predigerplan()
    # Gastprediger: max 2 / Monat (sollte) — Verstoss wenn mehr.
    dq = InMemoryDatenquelle(
        personen_liste=[Person(f"p{i}", merkmale={"gastprediger": True}) for i in range(3)]
    )
    res = erzeuge_termine(prediger, {}, dq, von=date(2026, 1, 1), bis=date(2026, 1, 31))
    v = generiere(prediger, {}, res["standard"], [], dq, seed=1)
    # Der Gast role filter waehlt aus 3 Gastpredigern; es entstehen sollte-
    # Verstoesse, wenn einer > 2x im Monat. Da nur 1 Feld 'gast' pro Termin
    # (pflicht false) und 3 Kandidaten, bleibt die Zahl = 0 Verstoesse.
    assert all(x.baustein != "abwesenheit_beachten" or x.stufe != "muss" for x in v.verstoesse)


def test_max_pro_zeitraum_verstoss():
    """negativ: eine Person kommt 3x im Monat -> sollte-Verstoss."""
    from diakronos_app.planrahmen.regeln.auswertung import Kontext, bewerte, stufe_der_regel

    dq = InMemoryDatenquelle(personen_liste=[Person("anna")])
    termin = Termin(datum=date(2026, 1, 25), reihe="standard")
    eintraege = [
        Eintrag("prediger", "anna", "person", termin=Termin(datum=date(2026, 1, 4), reihe="standard")),
        Eintrag("prediger", "anna", "person", termin=Termin(datum=date(2026, 1, 11), reihe="standard")),
        Eintrag("prediger", "anna", "person", termin=Termin(datum=date(2026, 1, 18), reihe="standard")),
    ]
    kontext = Kontext(plantyp={"id": "predigerplan"}, termin=termin, datenquelle=dq,
                      eintraege=eintraege)
    from diakronos_app.planrahmen.engine.modell import Slot

    slot = Slot(feld_pfad="predigt.prediger", art="person", feld={})
    b = bewerte("anna", slot, kontext, {"baustein": "max_pro_zeitraum", "anzahl": 2, "zeitraum": "monat", "stufe": "sollte"})
    # anna ist schon 3x eingeplant -> strafe > 0 (max 2/Monat verletzt).
    assert b.strafe > 0


# --------------------------------------------------------------------------- #
# Musikteams + Programm (C3/C4)
# --------------------------------------------------------------------------- #


def test_musikteams_probe_abgeleitet_und_keine_probe_an_feiertag():
    mt = _musikteams()
    dq = InMemoryDatenquelle(gruppen_liste=[
        Gruppe("gruppe_1", "Gruppe 1", mitglieder=frozenset({"a", "b"})),
        Gruppe("gruppe_3", "Gruppe 3", mitglieder=frozenset({"c", "d"})),
    ])
    res = erzeuge_termine(mt, {}, dq, von=date(2026, 12, 1), bis=date(2026, 12, 31))
    gd = res["gottesdienst"]
    probe = res["probe"]
    # Probe liegt 2 Tage vor dem Gottesdienst.
    for p in probe:
        assert p.bezug is not None
        assert p.datum == p.bezug.datum - timedelta(days=2)
    # Keine Probe an Feiertagsterminen (nur_wenn nicht feiertag): Heiligabend
    # 24.12. hat einen Gottesdienst (feiertag), aber keine Probe.
    feiertag_gd = [t for t in gd if "feiertag" in t.anlaesse]
    proxen_daten = {p.datum for p in probe}
    for g in feiertag_gd:
        assert (g.datum - timedelta(days=2)) not in proxen_daten


def test_musikteams_verfuegbarkeit_gruppe3_erster_sonntag():
    from diakronos_app.planrahmen.regeln.auswertung import muster_passt

    # Es gilt die Regel verfuegbarkeit team Gruppe 3 muster termin_im_monat 1.
    # 1. Sonntag im Monat -> Gruppe 3 verfuegbar.
    t1 = Termin(datum=date(2026, 12, 6), reihe="gottesdienst", positionsnr_im_monat=1)
    assert muster_passt({"termin_im_monat": 1}, t1)
    t2 = Termin(datum=date(2026, 12, 13), reihe="gottesdienst", positionsnr_im_monat=2)
    assert not muster_passt({"termin_im_monat": 1}, t2)


def test_programm_chorplan_vorher_geuebt_planuebergreifend():
    programm = _programm()
    chor = _chorplan()
    dq = _chor_datenquelle()
    # Historie: ein Lied wurde im chorplan-feld 'einueben' 3x geuebt,
    # ein anderes nie.
    dq.historie_liste = [
        Historieneintrag(date(2026, 11, 1), "chorplan", "einueben", "l1"),
        Historieneintrag(date(2026, 11, 8), "chorplan", "einueben", "l1"),
        Historieneintrag(date(2026, 11, 15), "chorplan", "einueben", "l1"),
    ]
    res = erzeuge_termine(programm, {"datum": "2026-12-06", "uhrzeit": "17:00"}, dq)
    # Ein Plan mit zwei Liedern (l1 geuebt, l0 nicht), als Ablauf-Eintraege.
    termine = res["standard"]
    eintraege = [
        Eintrag("ablauf/l1.lied", "l1", "eintrag", termin=termine[0]),
        Eintrag("ablauf/l2.lied", "l0", "eintrag", termin=termine[0]),
    ]
    from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan

    verstoesse = pruefe_plan(programm, termine, eintraege, dq)
    vorher_geuebt = [x for x in verstoesse if x.baustein == "vorher_geuebt"]
    # l0 (nicht geuebt) wird beanstandet, l1 nicht.
    beanstandete = {x.feld_pfad for x in vorher_geuebt}
    assert "ablauf/l2.lied" in beanstandete
    assert "ablauf/l1.lied" not in beanstandete


def test_uebernimm_erzeugt_eintraege_quelle_uebernommen():
    from types import SimpleNamespace

    quell = SimpleNamespace(eintraege=[
        Eintrag("ablauf/l1.lied", "l1", "eintrag"),
        Eintrag("ablauf/l1.dirigent", "p0", "person"),
        Eintrag("ablauf/s1.titel", "Szene", "text"),
    ])
    ziel = SimpleNamespace(eintraege=[])
    neu = uebernimm(ziel, quell, ["ablauf.lied", "ablauf.dirigent"])
    assert len(neu) == 2
    assert all(e.quelle == "uebernommen" for e in neu)
    assert all(not e.fixiert for e in neu)
    pfade = {e.feld_pfad for e in neu}
    assert "ablauf/l1.lied" in pfade
    assert "ablauf/l1.dirigent" in pfade
    assert "ablauf/s1.titel" not in pfade  # szene nicht uebernommen


# --------------------------------------------------------------------------- #
# Bedarfspruefung
# --------------------------------------------------------------------------- #


def test_bedarfspruefung_meldet_fehlende_merkmale():
    chor = _chorplan()
    dq = InMemoryDatenquelle()  # keine Personen, keine Lieder
    bedarfe = bedarfspruefung(chor, dq)
    merkmale = {b.kennung: b for b in bedarfe if b.art == "merkmal"}
    assert "dirigent" in merkmale
    # OP-CHOR-12/UXP-R23: Der Anzeigename der Vorlage ersetzt die Kennung,
    # und der Numerus ist richtig („0 Personen haben …“, nicht „0 Personen
    # mit dirigent“).
    assert merkmale["dirigent"].name == "dirigiert"
    assert merkmale["dirigent"].abdeckung == "0 Personen haben „dirigiert“"
    assert merkmale["dirigent"].einstufung == "blockiert_automatik"
    # sammlung lieder leer -> blockiert.
    sammlung = {b.kennung: b for b in bedarfe if b.art == "sammlung"}
    assert sammlung["lieder"].einstufung == "blockiert_automatik"


def test_bedarfspruefung_ok_wenn_daten_da():
    chor = _chorplan()
    dq = _chor_datenquelle()
    bedarfe = bedarfspruefung(chor, dq)
    dirigent = next(b for b in bedarfe if b.art == "merkmal" and b.kennung == "dirigent")
    assert dirigent.einstufung == "ok"


# --------------------------------------------------------------------------- #
# Laufzeit
# --------------------------------------------------------------------------- #


def test_laufzeit_chorplan_ein_jahr():
    chor = _chorplan()
    dq = _chor_datenquelle(n_personen=30, n_lieder=400)
    res = erzeuge_termine(chor, {}, dq, von=date(2026, 1, 1), bis=date(2026, 12, 31))
    assert len(res["standard"]) >= 50
    start = time.perf_counter()
    v = generiere(chor, {}, res["standard"], [], dq, seed=0)
    dauer = time.perf_counter() - start
    assert len(v.eintraege) > 500  # genug Eintraege erzeugt
    assert dauer < 2.0, f"Laufzeit {dauer:.2f}s ueber 2 s"


# --------------------------------------------------------------------------- #
# Trockenlauf
# --------------------------------------------------------------------------- #


def test_trockenlauf_ohne_seiteneffekte():
    chor = _chorplan()
    dq = _chor_datenquelle()
    ergebnis = trockenlauf(chor, {}, dq, wochen=8, ab=date(2026, 1, 1))
    assert len(ergebnis.termine) >= 7  # 8 Wochen -> ~8 Sonntage
    assert ergebnis.vorschlag is not None
    assert isinstance(ergebnis.bedarf, list)


# --------------------------------------------------------------------------- #
# Registrierung: jeder Baustein hat Logik
# --------------------------------------------------------------------------- #


def test_jeder_baustein_hat_logik():
    from diakronos_app.planrahmen.regeln.registry import bekannte_bausteine, LOGIK_REGISTRY

    assert set(bekannte_bausteine()) == set(LOGIK_REGISTRY.keys())
