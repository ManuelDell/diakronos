"""UI1-Erweiterungen des Plan-Rahmens: erweiterte Lese- und Schreibdienste.

Je Slice rot/grün: erst die Tests (Endpunkt fehlt -> rot), dann die
Implementierung. Isolierte In-Memory-SQLite ueber die Standard-Fixtures;
kein Zugriff auf den Betriebs-Stack.
"""
import uuid
import runpy
from pathlib import Path

import pytest


def test_disposable_seed_guard_und_vier_kochbuecher(patched_db, monkeypatch):
    seed = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "ui1_seed.py"))
    with pytest.raises(SystemExit, match="kein isolierter"):
        seed["main"]()
    for key, value in {"UI1_DISPOSABLE": "ui1-test", "APP_ENV": "test",
                       "DATABASE_URL": "postgresql://test:test@db/test",
                       "REDIS_URL": "redis://redis:6379/0"}.items():
        monkeypatch.setenv(key, value)
    seed["main"]()
    from sqlalchemy import select
    from diakronos_app.models.planrahmen import Plantyp
    with patched_db() as s:
        assert set(s.scalars(select(Plantyp.schluessel))) == {"chorplan", "freizeit", "musikteams", "programm"}


def test_plaene_liste_metadaten_aus_publiziertem_stand(client, patched_db):
    p, _ = kandidaten_setup(client, patched_db)
    row = aufruf(client, "plaene_liste")[0]
    assert row["bereich"] == "Chor" and row["plantyp_name"] == "Kandidaten"
    assert row["zeitraum_von"] == "2026-01-01" and row["darf_bearbeiten"] is True
    aufruf(client, "veroeffentlichen", plan=p)
    from diakronos_app.models.planrahmen import Plan
    with patched_db.begin() as s:
        s.get(Plan, p).titel = "Nicht veröffentlicht"
    anmelden(client, "mitglied")
    row = aufruf(client, "plaene_liste")[0]
    assert row["titel"] == "Kandidatenplan" and row["darf_bearbeiten"] is False


def test_plan_holen_anzeige_und_capabilities(client, patched_db):
    p, termin = kandidaten_setup(client, patched_db)
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="solistin", wert="mia")
    stand = aufruf(client, "plan_holen", plan=p)
    assert stand["darf_bearbeiten"] is True
    assert stand["anzeige"]["mia"]["name"] == "Mia Test"
    aufruf(client, "veroeffentlichen", plan=p)
    anmelden(client, "mitglied")
    stand = aufruf(client, "plan_holen", plan=p)
    assert stand["darf_bearbeiten"] is False
    assert set(stand["anzeige"]) == {"mia"}
    assert set(stand["anzeige"]["mia"]) <= {"kennung", "name", "anzeige", "kuerzel", "vorname"}


def test_generische_sammlungsanzeige_reload_und_mitglied(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "Administrator")
    d = definition("themen-ui1", "Themen", "Chor")
    d["sammlungen"] = [{"id": "themen", "name": "Themen"}]
    d["merkmale"] = {"themen": [{"id": "stelle", "art": "text", "name": "Bibelstelle"}]}
    d["felder"] = [{"id": "thema", "art": "eintrag", "sammlung": "themen"}]
    d["ansichten"] = [{"art": "tabelle", "format": {"thema": "{eintrag.titel} {eintrag.stelle}"}}]
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    aufruf(client, "sammlung_pflegen", plantyp=d["id"], sammlung="themen",
           eintraege=[{"daten": {"titel": "Auftakt", "stelle": "Psalm 1", "intern": "privat"}},
                      {"daten": {"titel": "Nicht eingeteilt", "stelle": "Psalm 2"}}])
    p = aufruf(client, "plan_anlegen", plantyp=d["id"], titel="Themen", von="2026-01-01", bis="2026-12-31")["id"]
    t = aufruf(client, "plan_holen", plan=p)["termine"][0]["id"]
    k = next(k for k in aufruf(client, "feld_kandidaten", plan=p, termin=t, feld_pfad="thema")["kandidaten"]
             if k["titel"] == "Auftakt")
    assert k.get("stelle") == "Psalm 1"  # deklarierte freie Attribute
    assert "intern" not in k
    aufruf(client, "merkmale_pflegen", plantyp=d["id"], werte=[{
        "ziel": "sammlung:themen", "schluessel": "stelle", "ziel_id": k["kennung"], "wert": "Psalm 23"}])
    k = next(x for x in aufruf(client, "feld_kandidaten", plan=p, termin=t, feld_pfad="thema")["kandidaten"]
             if x["kennung"] == k["kennung"])
    assert k.get("stelle") == "Psalm 23"  # Merkmal hat Vorrang
    aufruf(client, "eintrag_setzen", plan=p, termin=t, feld_pfad="thema", wert=k["kennung"])
    for _ in range(2):
        assert aufruf(client, "plan_holen", plan=p)["anzeige"][k["kennung"]]["stelle"] == "Psalm 23"
    aufruf(client, "veroeffentlichen", plan=p)
    anmelden(client, "mitglied")
    stand = aufruf(client, "plan_holen", plan=p)
    assert set(stand["anzeige"]) == {k["kennung"]}
    assert stand["anzeige"][k["kennung"]]["stelle"] == "Psalm 23"
    assert "intern" not in stand["anzeige"][k["kennung"]]
    assert "merkmale" not in stand["anzeige"][k["kennung"]]
    assert client.post(PFAD + "feld_kandidaten", json={"plan": p, "termin": t, "feld_pfad": "thema"}).status_code == 403


def test_ablauf_aendern_undo_rechte_und_fehler(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "Administrator")
    d = definition("ablauf-ui1", "Ablauf", "Chor")
    d["felder"] = [{"id": "ablauf", "art": "ablauf", "anzahl": "1..*",
                    "elemente": [{"typ": "szene", "inhalt": [{"id": "titel", "art": "text"}]}]}]
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp=d["id"], titel="Ablauf", von="2026-01-01", bis="2026-12-31")
    tid = aufruf(client, "plan_holen", plan=p["id"])["termine"][0]["id"]
    args = {"plan": p["id"], "termin": tid, "feld": "ablauf"}
    first = aufruf(client, "ablauf_aendern", **args, aktion="hinzufuegen", element_typ="szene")
    eid = first["element_id"]
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=tid, feld_pfad="ablauf/" + eid + ".titel", wert="Auftakt")
    second = aufruf(client, "ablauf_aendern", **args, aktion="hinzufuegen", element_typ="szene")
    aufruf(client, "ablauf_aendern", **args, aktion="verschieben", element_id=second["element_id"], position=0)
    assert aufruf(client, "plan_holen", plan=p["id"])["termine"][0]["ablauf"]["ablauf"][0]["id"] == second["element_id"]
    aufruf(client, "ablauf_aendern", **args, aktion="loeschen", element_id=eid)
    assert not aufruf(client, "plan_holen", plan=p["id"])["eintraege"]
    aufruf(client, "undo", plan=p["id"])
    assert aufruf(client, "plan_holen", plan=p["id"])["eintraege"][0]["wert"] == "Auftakt"
    r = client.post(PFAD + "ablauf_aendern", json={**args, "aktion": "hinzufuegen", "element_typ": "unbekannt"})
    assert r.status_code == 417 and r.json()["meldungen"]
    aufruf(client, "veroeffentlichen", plan=p["id"])
    anmelden(client, "mitglied")
    assert client.post(PFAD + "ablauf_aendern", json={**args, "aktion": "loeschen", "element_id": eid}).status_code == 403

def test_manuelle_meldungen_nur_am_betroffenen_eintrag(client, patched_db, monkeypatch):
    from types import SimpleNamespace
    from diakronos_app.planrahmen import dienste
    p, termin = kandidaten_setup(client, patched_db)
    def pruefen(definition, termine, *args, **kwargs):
        t = termine[0]
        return [SimpleNamespace(stufe="sollte", baustein="test", feld_pfad=pfad,
                                meldung=pfad, termin=t) for pfad in ("solistin", "lied")]
    monkeypatch.setattr(dienste, "pruefe_plan", pruefen)
    r = aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="solistin", wert="mia")
    assert [m["feld_pfad"] for m in r["eintrag"]["meldungen"]] == ["solistin"]
    assert len(r["meldungen"]) == 2  # Gesamtwarnungen bleiben in der Aktionsantwort.


PFAD = "/api/method/diakronos.planrahmen.api."


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def stammdaten(sf):
    """Bereiche, Konten, Mitglieder und Verantwortlichkeiten für UI1-Tests."""
    from diakronos_app.models.diakonos import Dienstbereich, DienstbereichVerantwortlicher, Mitglied
    from diakronos_app.models.core import User
    with sf.begin() as s:
        s.add_all([Dienstbereich(name="Chor"), Dienstbereich(name="Freizeit")])
        s.add_all([User(name=k, email=k, enabled=True)
                   for k in ("planer_chor", "planer_freizeit", "mitglied", "gast")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(), nachname="Test")
                   for k in ("planer_chor", "planer_freizeit", "mitglied")])
        s.add_all([DienstbereichVerantwortlicher(name="bv-" + b.lower(), parent=b, parenttype="Dienstbereich",
                                                 parentfield="verantwortliche", user=u)
                   for b, u in (("Chor", "planer_chor"), ("Freizeit", "planer_freizeit"))])


def definition(schluessel, name, bereich=None):
    d = {"schema": "diakronos/plantyp@1", "id": schluessel, "name": name,
         "termine": {"manuell": [{"datum": "2026-01-04"}]},
         "felder": [{"id": "notiz", "art": "text", "fuellen": "manuell"}]}
    if bereich:
        d["bereich"] = bereich
    return d


def anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


# --------------------------------------------------------------------------- #
# Slice 1: plantypen_liste — neueste Definition + Rechte-Flags je Plantyp
# --------------------------------------------------------------------------- #

def test_plantypen_liste_verweigert_unberechtigte(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "gast")
    assert client.get(PFAD + "plantypen_liste").status_code == 403


def test_plantypen_liste_bereichsfilter_und_letzte_version(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "Administrator")
    aufruf(client, "plantyp_speichern", definition=definition("chor-ui1", "Chor UI1", "Chor"), gueltig_ab="2026-01-01")
    v2 = aufruf(client, "plantyp_speichern", definition=definition("chor-ui1", "Chor UI1", "Chor"), gueltig_ab="2026-07-01")
    aufruf(client, "plantyp_speichern", definition=definition("fz-ui1", "Freizeit UI1", "Freizeit"), gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    liste = client.get(PFAD + "plantypen_liste")
    assert liste.status_code == 200, liste.text
    plantypen = liste.json()["message"]
    assert [p["schluessel"] for p in plantypen] == ["chor-ui1"]
    chor = plantypen[0]
    assert chor["name"] == "Chor UI1" and chor["bereich"] == "Chor" and chor["aktiv"] is True
    # Neueste Version (hoechste Versionsnummer) inkl. voller Definition.
    assert chor["letzte_version"]["id"] == v2["id"]
    assert chor["letzte_version"]["versionsnummer"] == 2
    assert chor["letzte_version"]["definition"]["id"] == "chor-ui1"
    assert chor["letzte_version"]["gueltig_ab"] == "2026-07-01"
    # Rechte-Flags: Bereichsverantwortung erlaubt Anlegen UND Bearbeiten.
    assert chor["darf_plan_anlegen"] is True and chor["darf_bearbeiten"] is True


def test_plantypen_liste_planverantwortliche_und_adminsicht(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "Administrator")
    from diakronos_app.models.planrahmen import Plantyp
    with patched_db.begin() as s:
        s.add(Plantyp(schluessel="gemeinde-ui1", name="Gemeinde UI1", bereich=None))
    aufruf(client, "plantyp_speichern", definition=definition("fz-ui1", "Freizeit UI1", "Freizeit"), gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="fz-ui1", titel="Mein Plan", von="2026-01-01",
               bis="2026-12-31", verantwortlich="mitglied")
    # Admin sieht alles inkl. Plantyp ohne Bereich, darf ueberall anlegen.
    liste = {x["schluessel"]: x for x in aufruf(client, "plantypen_liste")}
    assert "gemeinde-ui1" in liste and liste["gemeinde-ui1"]["letzte_version"] is None
    assert all(x["darf_plan_anlegen"] and x["darf_bearbeiten"] for x in liste.values())
    # Planverantwortliche ohne Verantwortungsbereich: nur der eigene Plantyp,
    # anlegen NICHT erlaubt, bearbeiten (eigener Plan) ja.
    anmelden(client, "mitglied")
    liste = {x["schluessel"]: x for x in aufruf(client, "plantypen_liste")}
    assert set(liste) == {"fz-ui1"}
    assert liste["fz-ui1"]["darf_plan_anlegen"] is False
    assert liste["fz-ui1"]["darf_bearbeiten"] is True
    # Ohne jede Verantwortung gibt es keinerlei Plantyp-Auskunft.
    anmelden(client, "gast")
    assert client.get(PFAD + "plantypen_liste").status_code == 403


# --------------------------------------------------------------------------- #
# Slice 2: feld_kandidaten — rollengefilterte Kandidaten mit Regelbewertung
# --------------------------------------------------------------------------- #

def kandidaten_definition():
    return {"schema": "diakronos/plantyp@1", "id": "kand-ui1", "name": "Kandidaten",
            "bereich": "Chor",
            "merkmale": {"person": [
                {"id": "dirigent", "art": "tag", "name": "dirigiert"},
                {"id": "klavier", "art": "tag", "name": "spielt Klavier"},
                {"id": "orgel", "art": "tag", "name": "spielt Orgel"}]},
            "rollen": [{"id": "solisten", "filter": {"merkmal": "klavier"}}],
            "termine": {"manuell": [{"datum": "2026-03-01"}]},
            "regeln": [
                {"baustein": "abwesenheit_beachten", "stufe": "muss"},
                {"baustein": "mindestabstand", "feld": "solistin", "wochen": 4, "stufe": "sollte"}],
            "felder": [
                {"id": "solistin", "art": "person", "rolle": "@solisten"},
                {"id": "kapellmeister", "art": "person", "rolle": {"merkmal": "dirigent"}},
                {"id": "orgel", "art": "person", "rolle": {"merkmal": "orgel"}},
                {"id": "begleitung", "art": "team", "teams": {"gruppe_unter": "Musik"}},
                {"id": "lied", "art": "eintrag", "sammlung": "lieder"},
                {"id": "farbe", "art": "auswahl", "werte": ["rot", "blau"]},
                {"id": "notiz", "art": "text", "fuellen": "manuell"}]}


def kandidaten_setup(client, patched_db):
    """Plantyp mit Rollen/Merkmalen, Plan, Merkmalswerten, Team und Liedern."""
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
    from diakronos_app.models.psalmos import Lied
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add_all([Mitglied(name=k, email=k + "@example.org", vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in ("mia", "jonas", "lena")])
        s.add(Gruppe(name="team-musik", gruppenname="Musik-Team", obergruppe="Musik"))
        s.flush()
        s.add_all([Gruppenmitgliedschaft(name=k, parent="team-musik", parenttype="Gruppe",
                                         parentfield="mitglieder", mitglied=k, status="Aktiv")
                   for k in ("mia", "jonas")])
        s.add_all([Lied(name="lied" + str(i), titel="Lied " + str(i), aktiv=True,
                        gesangbuch_nummer=str(100 + i)) for i in range(2)])
    anmelden(client, "Administrator")
    aufruf(client, "plantyp_speichern", definition=kandidaten_definition(), gueltig_ab="2026-01-01")
    werte = [{"ziel": "person", "schluessel": "klavier", "ziel_id": m, "wert": True}
             for m in ("mia", "jonas")]
    werte += [{"ziel": "person", "schluessel": "dirigent", "ziel_id": "mia", "wert": True}]
    aufruf(client, "merkmale_pflegen", plantyp="kand-ui1", werte=werte)
    p = aufruf(client, "plan_anlegen", plantyp="kand-ui1", titel="Kandidatenplan",
               von="2026-01-01", bis="2026-12-31")
    termin = aufruf(client, "plan_holen", plan=p["id"])["termine"][0]["id"]
    return p["id"], termin


def test_feld_kandidaten_verweigert_unberechtigte(client, patched_db):
    plan, termin = kandidaten_setup(client, patched_db)
    anmelden(client, "mitglied")
    r = client.get(PFAD + "feld_kandidaten",
                   params={"plan": plan, "termin": termin, "feld_pfad": "solistin"})
    assert r.status_code == 403


def test_feld_kandidaten_rollenfilter_und_engine_meldungen(client, patched_db):
    plan, termin = kandidaten_setup(client, patched_db)
    kand = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="solistin")
    assert kand["art"] == "person" and kand["feld_pfad"] == "solistin"
    personen = {k["kennung"]: k for k in kand["kandidaten"]}
    assert set(personen) == {"mia", "jonas"}
    # Sichere Anzeigedaten: Name, Vorname, Kuerzel — keine E-Mail.
    assert personen["mia"]["anzeige"] == "Mia Test" and personen["mia"]["name"] == "Mia Test"
    assert personen["mia"]["vorname"] == "Mia" and personen["mia"]["nachname"] == "Test"
    # UXP-R3: abgeleitet aus Vor-/Nachname ("Mia Test" -> "M. Test").
    assert personen["mia"]["kuerzel"] == "M. Test"
    # Nur deklarierte Merkmale des Plantyps, als Werte.
    assert personen["mia"]["merkmale"] == {"klavier": True, "dirigent": True}
    assert personen["jonas"]["merkmale"] == {"klavier": True}
    # Bedarfswarnung der Engine: 2 Träger -> ok/hinweis.
    klavier = next(m for m in kand["meldungen"] if m["kennung"] == "klavier")
    assert klavier["stufe"] == "hinweis" and klavier["einstufung"] == "ok"
    # Ein Träger -> eingeschraenkt/sollte.
    kapell = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="kapellmeister")
    assert [k["kennung"] for k in kapell["kandidaten"]] == ["mia"]
    dirigent = next(m for m in kapell["meldungen"] if m["kennung"] == "dirigent")
    assert dirigent["stufe"] == "sollte" and dirigent["einstufung"] == "eingeschraenkt"
    # Kein Träger -> muss-Blockade plus kandidaten.leer.
    orgel = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="orgel")
    assert orgel["kandidaten"] == []
    orgel_meldung = next(m for m in orgel["meldungen"] if m["kennung"] == "orgel")
    assert orgel_meldung["stufe"] == "muss" and orgel_meldung["einstufung"] == "blockiert_automatik"
    assert any(m["code"] == "kandidaten.leer" for m in orgel["meldungen"])


def test_feld_kandidaten_regelbewertung_je_kandidat(client, patched_db):
    plan, termin = kandidaten_setup(client, patched_db)
    # Abwesenheit nur fuer den Zeitraum, ohne Wirkung auf andere Kandidaten.
    aufruf(client, "abwesenheit_melden", mitglied="mia", von="2026-03-01", bis="2026-03-01",
           grund="Krankheit", plantyp="kand-ui1")
    kand = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="solistin")
    personen = {k["kennung"]: k for k in kand["kandidaten"]}
    # Abwesenheitsregel der Engine je Kandidat — ohne Nennung des Grundes.
    assert personen["mia"]["abwesend"] is True
    assert personen["mia"]["bewertung"]["zulaessig"] is False
    assert any("abwesend" in m for m in personen["mia"]["bewertung"]["meldungen"])
    assert personen["jonas"]["abwesend"] is False
    assert personen["jonas"]["bewertung"]["zulaessig"] is True
    assert personen["jonas"]["bewertung"]["meldungen"] == []
    # Datenschutz: kein Abwesenheitsgrund, keine E-Mail-Adressen.
    r = client.get(PFAD + "feld_kandidaten",
                   params={"plan": plan, "termin": termin, "feld_pfad": "solistin"})
    assert "Krankheit" not in r.text and "example.org" not in r.text
    # Ein bereits gesetzter Wert zaehlt sich nicht selbst (ausgeschlossen).
    aufruf(client, "eintrag_setzen", plan=plan, termin=termin, feld_pfad="solistin", wert="mia")
    kand = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="solistin")
    mia = next(k for k in kand["kandidaten"] if k["kennung"] == "mia")
    assert not any("mindestabstand" in m or "zuletzt" in m for m in mia["bewertung"]["meldungen"])


def test_feld_kandidaten_auswahlarten_und_grenzen(client, patched_db):
    plan, termin = kandidaten_setup(client, patched_db)
    team = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="begleitung")
    assert team["kandidaten"][0]["kennung"] == "team-musik"
    assert team["kandidaten"][0]["anzeige"] == "Musik-Team"
    assert team["kandidaten"][0]["mitglieder"] == 2
    assert "bewertung" in team["kandidaten"][0]
    lieder = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="lied")
    eintraege = {k["kennung"]: k for k in lieder["kandidaten"]}
    assert set(eintraege) == {"lied0", "lied1"}
    # Anzeigedaten eines Liedes: Titel, Buch, Nummer, Seite — sicher und minimal.
    assert eintraege["lied0"]["anzeige"] == "Lied 0" and eintraege["lied0"]["titel"] == "Lied 0"
    assert eintraege["lied0"]["nr"] == "100" and eintraege["lied0"]["merkmale"] == {}
    assert "bewertung" in eintraege["lied0"]
    farbe = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="farbe")
    assert farbe["kandidaten"] == ["rot", "blau"] and farbe["art"] == "auswahl"
    notiz = aufruf(client, "feld_kandidaten", plan=plan, termin=termin, feld_pfad="notiz")
    assert notiz["kandidaten"] == []
    assert client.get(PFAD + "feld_kandidaten", params={
        "plan": plan, "termin": termin, "feld_pfad": "gibt.es.nicht"}).status_code == 417
    # Termin eines anderen Plans ist kein Ersatz (fremdes Objekt).
    anderer = aufruf(client, "plan_anlegen", plantyp="kand-ui1", titel="Anderer",
                     von="2026-01-01", bis="2026-12-31")
    fremder_termin = aufruf(client, "plan_holen", plan=anderer["id"])["termine"][0]["id"]
    assert client.get(PFAD + "feld_kandidaten", params={
        "plan": plan, "termin": fremder_termin, "feld_pfad": "solistin"}).status_code == 417
