"""Reproduktionstests fuer P1-13 (Plaene: Generator und Planung).

Jeder Test gehoert zu genau einer Befund-ID des vorausgehenden Reviews
(Paket P1-13).
Die Tests sind zuerst ROT (Bug reproduziert) und nach der Behebung GRUEN.

- OP-CHOR-2 / OP-CHOR-8: Historie fuer den Generator kommt nur noch aus dem
  veroeffentlichten Stand und nur von Terminen VOR dem eigenen Termin.
- OP-CHOR-9: Regelmeldungen nennen den Liedtitel, nie die interne Kennung.
- UXP-R18: Optionales Feld ohne ``fuellen`` bleibt beim Generator leer.
- UXP-R3: ``kuerzel`` wird aus Vor-/Nachname abgeleitet (nie leer).
- UXP-R14: Namen mit ``fuer``/``für`` werden nicht mehr als Feldpfad ersetzt.
- UXP-R16: „Vorschlag erzeugen" auf veroeffentlichtem Plan oeffnet den Entwurf;
  der Modus „nur Luecken und Regelverstoesse" laesst gefuellte Plaetze stehen.
"""
from __future__ import annotations

from datetime import date

import pytest

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine import (
    InMemoryDatenquelle,
    Person,
    Sammlungseintrag,
    erzeuge_termine,
    generiere,
)
from diakronos_app.planrahmen.engine.datenquelle import Historieneintrag
from diakronos_app.planrahmen.regeln.auswertung import (
    Kontext,
    bewerte_alle,
    index_aufbauen,
)


# --------------------------------------------------------------------------- #
# Helfer
# --------------------------------------------------------------------------- #


def _chorplan() -> dict:
    return ressourcen.kochbuch_laden("chorplan")


def _quelle(n_personen: int = 30, n_lieder: int = 400) -> InMemoryDatenquelle:
    """Wie ``test_planrahmen_engine._chor_datenquelle`` (gleiche Testdaten)."""
    personen = []
    for i in range(n_personen):
        p = Person(f"p{i}", name=f"Person {i}", vorname=f"Person", nachname=f"{i}",
                   kuerzel=f"P{i}")
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


def _termine(plantyp: dict, von: date, bis: date):
    return erzeuge_termine(plantyp, {}, _quelle(), von=von, bis=bis)["standard"]


def _liedslot():
    """Ein Lied-Slot mit korrekt gesetzter Sammlung (``feld`` ist Position 3)."""
    from diakronos_app.planrahmen.engine.modell import Slot

    return Slot("lieder[0]", "eintrag", {"id": "lieder", "art": "eintrag",
                                         "sammlung": "lieder"}, sammlung="lieder")


@pytest.fixture()
def _db_quelle_zwei_plaene(session_factory):
    """DB-Datenquelle mit einem veroeffentlichten und einem Entwurfs-Plan.

    Der Entwurf (PLAN-D) enthaelt ein Lied, das nur dort vorkommt; der
    veroeffentlichte Plan (PLAN-B) einen eingefrorenen Stand mit LIED-1.
    """
    from diakronos_app.models.planrahmen import (
        Eintrag as PrEintrag,
        Plan as PrPlan,
        Plantyp as PrPlantyp,
        PlantypVersion as PrPlantypVersion,
        Termin as PrTermin,
    )
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    s = session_factory()
    s.add_all([
        PrPlantyp(id="PT-CHOR", schluessel="chorplan", name="Chorplan"),
        PrPlantypVersion(id="PV-CHOR", plantyp="PT-CHOR", versionsnummer=1,
                         gueltig_ab=date(2025, 1, 1), definition={}),
        PrPlan(id="PLAN-B", plantyp="PT-CHOR", titel="Chorplan 2025",
               status="veroeffentlicht",
               veroeffentlichter_stand={
                   "plan": {},
                   "termine": [{"id": "T-B1", "datum": "2026-01-04"}],
                   "eintraege": [{"termin": "T-B1", "feld_pfad": "lieder[0]", "wert": "LIED-1"}],
               }),
        PrPlan(id="PLAN-D", plantyp="PT-CHOR", titel="Chorplan Entwurf", status="entwurf"),
        PrTermin(id="T-B1", plan="PLAN-B", plantyp_version="PV-CHOR",
                 datum=date(2026, 1, 4)),
        PrTermin(id="T-D1", plan="PLAN-D", plantyp_version="PV-CHOR",
                 datum=date(2026, 1, 11)),
    ])
    s.commit()
    s.add_all([
        # Der Entwurf traegt ein eigenes Lied — er darf keine Historie liefern.
        PrEintrag(id="E-D1", termin="T-D1", feld_pfad="lieder[0]", wert="LIED-ENTWURF"),
    ])
    s.commit()
    yield DBDatenquelle(s, plantyp="chorplan")
    s.close()


# --------------------------------------------------------------------------- #
# OP-CHOR-2: Strafen-Skala der Regeln
# --------------------------------------------------------------------------- #


def test_op_chor_2_mindestabstand_strafe_bleibt_im_bereich_0_bis_1():
    """``mindestabstand`` liefert 0...1, wenn der Abstand fehlt.

    Vorher: die Strafe wuchs linear mit ``(grenze - tage) / grenze`` und war
    damit schon bei 0 Tagen Abstand nur 1,0 — nach 8 Wochen aber exakt 0.
    Zusammen mit ``vorher_geuebt`` (bis 2,0) verschob das die Auswahl: die
    billigsten Kandidaten waren Mindestabstand-Verstoesse. Beide Regeln
    muessen auf derselben Skala liegen.
    """
    chor = _chorplan()
    termine = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))
    termin = termine[0]
    quelle = _quelle()
    slot = None
    slot = _liedslot()
    # Verstoss: dasselbe Lied 1 Tag vorher (Regel: 8 Wochen = 56 Tage).
    historie = [Historieneintrag(datum=date(2026, 10, 1), plantyp="chorplan",
                                 feld_pfad="lieder[0]", wert="l1")]
    k = Kontext(chor, termin, quelle, {}, [], historie)
    index_aufbauen(k)
    regel = next(r for r in chor["regeln"] if r["baustein"] == "mindestabstand")
    b = bewerte_alle("l1", slot, k, [regel])
    assert b.meldungen, "Mindestabstand muss den Verstoss melden"
    assert 0.0 < b.strafe <= 1.0, f"Strafe ausserhalb 0..1: {b.strafe}"


def test_op_chor_2_strafen_der_regeln_liegen_auf_derselben_skala():
    """Jede Regelstrafe bleibt in einem Bereich, das Gewichten vergleichbar ist."""
    chor = _chorplan()
    termine = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))
    termin = termine[0]
    quelle = _quelle()
    slot = _liedslot()
    historie = [
        # OP-CHOR-2: derselbe Tag zaehlt bewusst NICHT mehr als Historie,
        # deshalb ein Termin VOR dem eigenen (2 Tage zuvor).
        Historieneintrag(datum=date(2026, 10, 2), plantyp="chorplan",
                         feld_pfad="lieder[0]", wert="l1"),
        Historieneintrag(datum=date(2026, 9, 1), plantyp="chorplan",
                         feld_pfad="lieder[0]", wert="l2"),
    ]
    k = Kontext(chor, termin, quelle, {}, [], historie)
    index_aufbauen(k)
    strafen = {}
    for regel in chor["regeln"]:
        if regel["stufe"] == "muss":
            continue
        b = bewerte_alle("l1", slot, k, [regel])
        if b.meldungen:
            strafen[regel["baustein"]] = b.strafe
    assert "mindestabstand" in strafen
    for baustein, strafe in strafen.items():
        assert -1.0 <= strafe <= 1.0, f"{baustein}: Strafe {strafe} ausserhalb -1..1"


def test_op_chor_2_max_strafe_bleibt_bei_vielen_ueberschreitungen_in_0_bis_1():
    """``max_pro_zeitraum`` wird hart auf 0..1 geklemmt.

    Vorher wuchs die Strafe unbegrenzt (n + 1 - anzahl): bei einer Person mit
    vielen Diensten im Zeitraum war sie ein Vielfaches schwerer als die 0..1-
    Strafen der anderen Bausteine. Geprueft mit mehrfacher Ueberschreitung.
    """
    chor = _chorplan()
    termin = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))[0]
    quelle = _quelle()
    from diakronos_app.planrahmen.engine.modell import Slot

    slot = Slot("einsingen", "person", {"id": "einsingen", "art": "person"})
    regel = {"baustein": "max_pro_zeitraum", "feld": "einsingen", "anzahl": 2,
             "zeitraum": "monat", "stufe": "sollte"}

    for ueberschreitung in (0, 1, 4, 20):
        historie = [
            Historieneintrag(datum=date(2026, 10, d), plantyp="chorplan",
                             feld_pfad="einsingen", wert="p0")
            for d in range(1, 3 + ueberschreitung)
        ]
        k = Kontext(chor, termin, quelle, {}, [], historie)
        index_aufbauen(k)
        b = bewerte_alle("p0", slot, k, [regel])
        assert b.meldungen, "Ueberschreitung muss gemeldet werden"
        assert 0.0 < b.strafe <= 1.0, f"{ueberschreitung}x: Strafe {b.strafe} ausserhalb 0..1"


# --------------------------------------------------------------------------- #
# OP-CHOR-2 / OP-CHOR-8: Historie nur aus veroeffentlichten Staenden
# --------------------------------------------------------------------------- #


def test_op_chor_2_historie_sieht_eigenen_plan_beidseitig_fremdplan_nur_vorher():
    """Abstand: eigener Plan beidseitig, Fremdplan nur VOR dem eigenen Termin.

    P1-14b (vorher hiess der Test ``..._nimmt_nur_termine_vor_dem_eigenen_termin``,
    pruefte aber das Gegenteil fuer den eigenen Plan):
    * ``plan`` des EIGENEN Plans: derselbe Tag zaehlt NICHT, ein anderer Tag
      desselben Plans — auch ein spaeterer — bleibt gueltig.
    * Eintrag eines FREMDPLANS: nur Daten VOR dem eigenen Termin zaehlen;
      ein spaeterer Termin eines ueberlappenden Zweitplans derselben Vorlage
      zaehlt NICHT.
    """
    chor = _chorplan()
    termine = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))
    tag = termine[0].datum
    spaeter = termine[1].datum
    quelle = _quelle()
    slot = _liedslot()
    regel = next(r for r in chor["regeln"] if r["baustein"] == "mindestabstand")
    eigen = "PLAN-EIGEN"

    # Eigener Plan, derselbe Tag: keine Meldung.
    k = Kontext(chor, termine[0], quelle, {}, [],
                [Historieneintrag(datum=tag, plantyp="chorplan", feld_pfad="lieder[0]",
                                  wert="l1", plan=eigen)])
    k.eigener_plan = eigen
    index_aufbauen(k)
    assert not bewerte_alle("l1", slot, k, [regel]).meldungen, "Derselbe Tag zaehlt als Historie"

    # Eigener Plan, ein anderer (spaeterer) Tag: zaehlt weiter (beidseitig).
    k = Kontext(chor, termine[0], quelle, {}, [],
                [Historieneintrag(datum=spaeter, plantyp="chorplan", feld_pfad="lieder[0]",
                                  wert="l1", plan=eigen)])
    k.eigener_plan = eigen
    index_aufbauen(k)
    assert bewerte_alle("l1", slot, k, [regel]).meldungen, \
        "Spaeterer Tag des EIGENEN Plans ging verloren"

    # FREMDPLAN, spaeterer Tag: zaehlt NICHT (der Aushang war noch nicht).
    k = Kontext(chor, termine[0], quelle, {}, [],
                [Historieneintrag(datum=spaeter, plantyp="chorplan", feld_pfad="lieder[0]",
                                  wert="l1", plan="PLAN-FREMD")])
    k.eigener_plan = eigen
    index_aufbauen(k)
    assert not bewerte_alle("l1", slot, k, [regel]).meldungen, \
        "Spaeterer Tag eines FREMDplans zaehlt faelschlich"

    # FREMDPLAN, frueherer Tag: zaehlt.
    k = Kontext(chor, termine[1], quelle, {}, [],
                [Historieneintrag(datum=tag, plantyp="chorplan", feld_pfad="lieder[0]",
                                  wert="l1", plan="PLAN-FREMD")])
    k.eigener_plan = eigen
    index_aufbauen(k)
    assert bewerte_alle("l1", slot, k, [regel]).meldungen, \
        "Frueherer Tag eines FREMDplans muss zaehlen"


def test_op_chor_2_veroeffentlichter_stand_zaehlt_als_historie(_db_quelle_zwei_plaene):
    """Nur der veroeffentlichte Stand eines fremden Plans ist Historie.

    Vorher las ``_historie_laden`` alle Plaene samt Entwuerfen; ein zweiter,
    ueberlappender Plan derselben Vorlage drueckte die Liedauswahl auf wenige
    Titel ("zuletzt vor 0 Tagen"). Veroeffentlichte Staende zaehlen weiterhin,
    Entwuerfe nicht mehr.
    """
    quelle = _db_quelle_zwei_plaene
    werte = {(h.plantyp, h.feld_pfad, h.wert) for h in quelle.historie("*", date(2027, 12, 31))}
    # Der Entwurf (PLAN-D, nie veroeffentlicht) ist keine Historie.
    assert ("chorplan", "lieder[0]", "LIED-ENTWURF") not in werte
    # Der veroeffentlichte Plan (PLAN-B mit Stand) zaehlt weiter.
    assert ("chorplan", "lieder[0]", "LIED-1") in werte


# --------------------------------------------------------------------------- #
# OP-CHOR-9: Meldungen nennen den Titel, nicht die Kennung
# --------------------------------------------------------------------------- #


def test_op_chor_9_mindestabstand_nennt_den_liedtitel():
    """Die Meldung enthaelt den Titel aus der Sammlung, nicht die Kennung."""
    chor = _chorplan()
    termine = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))
    termin = termine[0]
    quelle = _quelle()
    slot = _liedslot()
    historie = [Historieneintrag(datum=date(2026, 9, 30), plantyp="chorplan",
                                 feld_pfad="lieder[0]", wert="l7")]
    k = Kontext(chor, termin, quelle, {}, [], historie)
    index_aufbauen(k)
    regel = next(r for r in chor["regeln"] if r["baustein"] == "mindestabstand")
    b = bewerte_alle("l7", slot, k, [regel])
    assert b.meldungen
    text = " ".join(b.meldungen)
    assert "Lied 7" in text, f"Titel fehlt: {text}"
    assert "l7:" not in text and not text.startswith("l7"), f"Kennung in der Meldung: {text}"


def test_op_chor_9_passend_zum_anlass_nennt_den_titel():
    """Auch ``passend_zum_anlass`` nennt den Titel statt der Kennung.

    Der Anlass kommt aus einem *konfigurierten* Feiertag
    (``_anlaesse_fuer_datum``), deshalb hier ein kleiner Plantyp mit dem
    Anlass ``erntedank`` statt des vollen Chorplans.
    """
    chor = _chorplan()
    chor = {**chor, "termine": {**chor["termine"], "feiertage": ["erntedank"]}}
    termine = _termine(chor, date(2026, 10, 4), date(2026, 10, 31))
    termin = next(t for t in termine if "erntedank" in (t.anlaesse or frozenset()))
    quelle = _quelle()
    slot = _liedslot()
    k = Kontext(chor, termin, quelle, {}, [], [])
    index_aufbauen(k)
    regel = next(r for r in chor["regeln"] if r["baustein"] == "passend_zum_anlass")
    # l1 hat Thema 'sonstiges', passt nicht zu Erntedank.
    b = bewerte_alle("l1", slot, k, [regel])
    assert b.meldungen
    text = " ".join(b.meldungen)
    assert "Lied 1" in text, f"Titel fehlt: {text}"
    assert "für" in text and "fuer" not in text, f"Umlaut fehlt ('fuer' statt 'für'): {text}"


# --------------------------------------------------------------------------- #
# UXP-R18: Optionales Feld ohne fuellen bleibt leer
# --------------------------------------------------------------------------- #


def test_ux_r18_optionales_solo_bleibt_beim_generator_leer():
    """``solo`` ist optional und ohne ``fuellen`` -> der Vorschlag laesst es leer."""
    chor = _chorplan()
    lieder_feld = next(f for f in chor["felder"] if f["id"] == "lieder")
    solo = next(f for f in lieder_feld["inhalt"] if f["id"] == "solo")
    assert solo.get("pflicht") is False
    termin_liste = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))[:3]
    quelle = _quelle()
    vorschlag = generiere(chor, {}, termin_liste, [], quelle, 1)
    solo_werte = [e for e in vorschlag.eintraege if ".solo" in e.feld_pfad]
    assert not solo_werte, f"Solo wurde automatisch besetzt: {[e.wert for e in solo_werte]}"


# --------------------------------------------------------------------------- #
# UXP-R3: Kuerzel wird abgeleitet
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("vorname,nachname,erwartet", [
    ("David", "Krüger", "D. Krüger"),
    ("Ines", "Beispiel", "I. Beispiel"),
    ("Ben", "Neumann", "B. Neumann"),
    ("Anna", "", "Anna"),
    ("", "Beispiel", "Beispiel"),
])
def test_ux_r3_kuerzel_aus_vor_und_nachname(vorname, nachname, erwartet):
    """Das eingebaute Attribut ``kuerzel`` ist nie leer, wenn ein Name da ist."""
    from diakronos_app.planrahmen.datenquelle_db import kuerzel_aus_name

    assert kuerzel_aus_name(vorname, nachname) == erwartet


def test_ux_r3_kuerzel_ohne_namen_bleibt_leer():
    from diakronos_app.planrahmen.datenquelle_db import kuerzel_aus_name

    assert kuerzel_aus_name("", "") == ""


# --------------------------------------------------------------------------- #
# OP-CHOR-11: vorbelegen ohne Quelle faellt auf die Reihum-Rotation zurueck
# --------------------------------------------------------------------------- #


def test_op_chor_11_vorbelegen_ohne_quelle_besetzt_dirigent_und_klavier():
    """Dirigent/Klavier sind besetzt, auch wenn 0 von 140 Liedern sie pflegt.

    Vorher blieb jedes ``lieder[n].dirigent``/``.klavier`` leer und der Planer
    musste jede Zelle von Hand waehlen (Bedarfsdialog „Wer spielt Klavier?“
    wirkte nur als Filter der Handauswahl).
    """
    chor = _chorplan()
    termine = _termine(chor, date(2026, 10, 1), date(2026, 12, 31))
    quelle = _quelle()
    vorschlag = generiere(chor, {}, termine, [], quelle, 3)
    dirigenten = [e for e in vorschlag.eintraege if e.feld_pfad.endswith(".dirigent")]
    klavere = [e for e in vorschlag.eintraege if e.feld_pfad.endswith(".klavier")]
    assert len(dirigenten) == 3 * len(termine), len(dirigenten)
    assert len(klavere) == 3 * len(termine), len(klavere)
    assert all(e.wert for e in dirigenten + klavere), "Es blieb ein Platz leer"
    # Nur als Dirigent gekennzeichnete Personen (p0..p3) kommen infrage.
    assert {e.wert for e in dirigenten} <= {f"p{i}" for i in range(4)}
    assert {e.wert for e in klavere} <= {f"p{i}" for i in range(2, 6)}


def test_op_chor_11_vorbelegung_am_lied_gewinnt_weiterhin():
    """Gepflegte Lied-Vorbelegung schlaegt den Reihum-Rueckfall."""
    chor = _chorplan()
    termine = _termine(chor, date(2026, 10, 1), date(2026, 10, 31))
    quelle = _quelle()
    # Alle Lieder tragen p3 als Dirigent-Vorbelegung.
    for e in quelle.sammlung("lieder"):
        e.merkmale["dirigent"] = "p3"
    vorschlag = generiere(chor, {}, termine, [], quelle, 3)
    werte = {e.wert for e in vorschlag.eintraege if e.feld_pfad.endswith(".dirigent")}
    assert werte == {"p3"}, werte


def test_op_chor_11_quelle_deklariert_ist_pflicht_ohne_stillen_rueckfall():
    """Ein anderer Aufrufer darf NICHT unbemerkt in den Reihum-Rueckfall laufen.

    ``fuellen()`` ist die einzige Stelle, an der die Reihum-Rotation fuer eine
    leere Vorbelegungs-Quelle einspringt. Waere ``quelle_deklariert`` ein
    Default (``False``), bekaeme JEDER andere Aufrufer ohne eigenes Zutun den
    Rueckfall. Der Parameter ist daher Pflicht: fehlt er, bricht der Aufruf mit
    ``TypeError`` ab, statt still das falsche Verhalten zu waehlen.
    """
    import random

    from diakronos_app.planrahmen.engine.fuellen import Fuellzustand, fuellen
    from diakronos_app.planrahmen.engine.modell import Slot, Termin

    chor = _chorplan()
    termin = Termin(date(2026, 10, 4), "standard")
    zustand = Fuellzustand(plantyp=chor, datenquelle=_quelle(), parameter={})
    # Ein 'vorbelegen'-Slot, dessen Quelle 'eintrag.lied' deklariert ist, aber
    # aktuell leer bleibt — genau der Fall, in dem die Rotation einspringen
    # KOENNTE. Ohne den Parameter muss der Aufruf scheitern (kein Default).
    slot = Slot("lieder[0].dirigent", "person", {"id": "dirigent", "art": "person"},
                sammlung="dirigent", fuellen="vorbelegen", aus="eintrag.lied")
    with pytest.raises(TypeError):
        fuellen(slot, termin, zustand, random.Random(0))

    # Explizit deklariert -> kein Rueckfall, der Platz bleibt wartend leer.
    wert, meldung = fuellen(slot, termin, zustand, random.Random(0), quelle_deklariert=True)
    assert wert is None and "leer" in meldung
    assert zustand.quelle_der_fuellung == "vorbelegen"


# --------------------------------------------------------------------------- #
# UXP-R16: veroeffentlichter Plan wird per Knopf zum Entwurf; „nur Luecken"
# --------------------------------------------------------------------------- #

PFAD = "/api/method/diakronos.planrahmen.api."


def _api(client, name: str, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def _stammdaten(session_factory) -> None:
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Dienstbereich, Gruppe, Gruppenmitgliedschaft, Mitglied
    from diakronos_app.models.psalmos import Lied

    with session_factory.begin() as s:
        # Der Chorplan bindet den Dienstbereich "Chor" (sonst /bereich-Fehler).
        s.add(Dienstbereich(name="Chor"))
        s.add_all([User(name=k, email=k, enabled=True) for k in ("a", "b")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k, nachname=k)
                   for k in ("a", "b")])
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add_all([Gruppenmitgliedschaft(name=k, parent="Chor", parenttype="Gruppe",
                                        parentfield="mitglieder", mitglied=k, status="Aktiv")
                   for k in ("a", "b")])
        s.add_all([Lied(name=f"lied{i}", titel=f"Lied {i:02d}", aktiv=True)
                   for i in range(6)])


def _plan(client, session_factory) -> str:
    _stammdaten(session_factory)
    definition = ressourcen.kochbuch_laden("chorplan")
    _api(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    p = _api(client, "plan_anlegen", plantyp="chorplan", titel="Quartal",
             von="2026-10-01", bis="2026-12-31")
    return p["id"]


def test_ux_r16_plan_entwurf_oeffnet_veroeffentlichten_plan(client, patched_db):
    """Der Dienst macht aus einem veroeffentlichten Plan einen Entwurf (Undo-faehig)."""
    pid = _plan(client, patched_db)
    _api(client, "plan_generieren", plan=pid)
    _api(client, "veroeffentlichen", plan=pid)
    stand = _api(client, "plan_holen", plan=pid)
    assert stand["plan"]["status"] == "veroeffentlicht"
    frozen = stand["plan"]["veroeffentlichter_stand"]

    erg = _api(client, "plan_entwurf", plan=pid)
    assert erg["status"] == "entwurf" and erg["schon_entwurf"] is False
    stand = _api(client, "plan_holen", plan=pid)
    assert stand["plan"]["status"] == "entwurf"
    # Mitglieder sehen weiter den eingefrorenen Stand.
    assert stand["plan"]["veroeffentlichter_stand"] == frozen


def test_ux_r16_plan_entwurf_ist_idempotent(client, patched_db):
    pid = _plan(client, patched_db)
    _api(client, "plan_generieren", plan=pid)
    erst = _api(client, "plan_entwurf", plan=pid)
    assert erst["status"] == "entwurf" and erst["schon_entwurf"] is True


def test_ux_r16_nur_luecken_laesst_gefuellte_plaetze_stehen(client, patched_db):
    """Nach einer Abwesenheit aendert „nur Luecken" nicht den ganzen Plan."""
    pid = _plan(client, patched_db)
    voll = _api(client, "plan_generieren", plan=pid)
    assert voll["diff"], "Der volle Vorschlag muss etwas aendern"
    nur = _api(client, "plan_generieren", plan=pid, nur_vorschau=True, nur_luecken=True)
    # Alles ist belegt und regelkonform -> nur Luecken hat nichts zu tun.
    assert nur["diff"] == [], f"nur Luecken aendert trotzdem: {len(nur['diff'])}"
