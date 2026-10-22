"""Reproduktionstests fuer P1-14 (Plaene: Vorlagen, Gruppen, Freizeit/Programm).

Jeder Test gehoert zu genau einer Befund-ID des vorausgehenden Reviews
(Paket P1-14).
Die Tests sind zuerst ROT (Bug reproduziert) und nach der Behebung GRUEN.

- UXP-R4   Untergruppen sind als Teams nutzbar (Obergruppe = Gruppenname).
- UXP-R5   „Neue Planvorlage" mit vorhandener Kennung ueberschreibt nicht still.
- UXP-R6   Gepflegter Auswahl-/Tag-Wert bleibt nach dem Neuladen sichtbar.
- UXP-R9   Bereich ist eine Auswahlliste (Kennung + Anzeigename).
- UXP-R12  Zahl der von einer neuen Version umgebundenen Termine ist abfragbar.
- UXP-R13  Gruppen/Bereiche erscheinen mit Anzeigename, nicht mit interner ID.
- UXP-R20  „Rueckgaengig" nimmt Veröffentlichung/Versionswechsel nicht zurueck.
- OP-CHOR-1  Termine eines Plans lassen sich nachtraeglich aendern.
- OP-EVENT-6 Programm-Elemente tragen Beginn/Dauer/Verantwortlich/Technik.
- OP-EVENT-7 Bedarf nennt „Mitarbeiter aus Anmeldungen: 0" (keine Sackgasse).
- OP-EVENT-9 Uhrzeit des Programms wird nicht mehr stillschweigend verworfen.
- OP-EVENT-17 Freizeit-Regen-Variante hat Programm + Leitung.
- OP-EVENT-18 Geltende Sonne/Regen-Variante ist je Termin festlegbar.
- OP-UI-12  Plaene lassen sich loeschen/archivieren/kopieren/aendern.
- UXP-R4/OP-EVENT-7 Bedarfspruefung nennt Teams unter „X".
"""

from __future__ import annotations

import pytest

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine import InMemoryDatenquelle, Person, Gruppe
from diakronos_app.planrahmen.engine.bedarf import bedarfspruefung

PFAD = "/api/method/diakronos.planrahmen.api."


# ── Geruest (Muster test_p1_11_planrahmen_mitglieder.py) ───────────────────


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


def stammdaten(sf, *benutzer):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Mitglied,
    )
    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        s.add_all([User(name=k, email=k, enabled=True) for k in benutzer])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in benutzer])
        s.add(DienstbereichVerantwortlicher(
            name="bv-chor", parent="Chor", parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer"))


@pytest.fixture()
def planer(client, patched_db):
    stammdaten(patched_db, "planer", "mitglied")
    anmelden(client, "planer")
    return client


def _progdefinition(id_="prog-p114", uhrzeit="17:00"):
    return {
        "schema": "diakronos/plantyp@1", "id": id_, "name": "Programmablauf",
        "bereich": "Chor",
        "termine": {"manuell": [{"datum": "2026-12-06", "uhrzeit": "{parameter.uhrzeit}"}]},
        "parameter": [{"id": "uhrzeit", "art": "text", "name": "Uhrzeit"}],
        "felder": [{
            "id": "ablauf", "art": "ablauf",
            "elemente": [{"typ": "lied", "name": "Lied", "inhalt": [
                {"id": "lied", "art": "eintrag", "sammlung": "lieder"},
                {"id": "beginn", "art": "text", "name": "Beginn (Uhrzeit)", "pflicht": False},
                {"id": "dauer", "art": "zahl", "name": "Dauer (Minuten)", "pflicht": False},
                {"id": "verantwortlich", "art": "person", "name": "Verantwortlich", "pflicht": False},
                {"id": "technik", "art": "text", "name": "Technik", "pflicht": False},
            ]}],
        }],
    }


# ── OP-EVENT-9: Uhrzeit aus dem Parameter wird uebernommen ─────────────────


def test_op_event_9_programm_uhrzeit_aus_parameter(planer):
    """Vorher: uhrzeit = null, weil die Kopfvorlage den Parameter nicht aufloeste."""
    aufruf(planer, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    p = aufruf(planer, "plan_anlegen", plantyp="prog-p114", titel="Adventssingen",
               von="2026-12-01", bis="2026-12-31", parameter={"uhrzeit": "17:00"})["id"]
    plan = aufruf(planer, "plan_holen", plan=p)
    assert plan["termine"][0]["uhrzeit"] is not None
    assert str(plan["termine"][0]["uhrzeit"]).startswith("17:00")


def test_op_event_9_ungueltige_uhrzeit_wird_gemeldet(planer):
    """Eine unsinnige Uhrzeit ist keine stille Leere mehr, sondern eine Meldung."""
    with pytest.raises(AssertionError):
        aufruf(planer, "plantyp_speichern", definition=_progdefinition("prog-p114b"),
               gueltig_ab="2026-01-01")
        aufruf(planer, "plan_anlegen", plantyp="prog-p114b", titel="Kaputt",
               von="2026-12-01", bis="2026-12-31", parameter={"uhrzeit": "keine-uhrzeit"})
        aufruf(planer, "trockenlauf", definition=_progdefinition("prog-p114b"),
               parameter={"uhrzeit": "keine-uhrzeit"}, ab="2026-12-01", wochen=4)


# ── OP-EVENT-6: Programm-Elemente tragen Beginn/Dauer/Verantwortlich/Technik ─


def test_op_event_6_programmelemente_mit_beginn_dauer_technik(planer):
    aufruf(planer, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    p = aufruf(planer, "plan_anlegen", plantyp="prog-p114", titel="Adventssingen",
               von="2026-12-01", bis="2026-12-31", parameter={"uhrzeit": "17:00"})["id"]
    termin = aufruf(planer, "plan_holen", plan=p)["termine"][0]["id"]
    # Der Ablauf ist eine Liste von Elementen; erst ein Element anlegen, dann
    # erscheinen dessen Unterfelder als Slots.
    aufruf(planer, "ablauf_aendern", plan=p, termin=termin, feld="ablauf",
           aktion="hinzufuegen", element_typ="lied")
    struktur = aufruf(planer, "termin_struktur", plan=p, termin=termin)
    pfade = {s["feld_pfad"] for s in (struktur.get("slots") or [])}
    # Der Slots-Pfad nutzt eine stabile Element-Kennung: 'ablauf/<id>.<feld>'.
    assert any(p.endswith(".beginn") for p in pfade), pfade
    assert any(p.endswith(".dauer") for p in pfade), pfade
    assert any(p.endswith(".verantwortlich") for p in pfade), pfade
    assert any(p.endswith(".technik") for p in pfade), pfade


# ── UXP-R5: Kennungskollision ──────────────────────────────────────────────


def test_uxp_r5_neue_vorlage_mit_vorhandener_kennung_blockiert(planer):
    aufruf(planer, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    r = planer.post(PFAD + "plantyp_speichern", json={
        "definition": _progdefinition(), "gueltig_ab": "2026-06-01",
        "kommentar": "zweiter Anlauf", "bestehende_erlauben": False,
        "name": "Zweiter Anlauf"})
    assert r.status_code == 417, r.text
    meldungen = r.json().get("meldungen") or []
    assert any(m["pfad"] == "/id" for m in meldungen), meldungen
    assert any("bereits" in m["meldung"] for m in meldungen), meldungen


def test_uxp_r5_explizite_version_bleibt_erlaubt(planer):
    """Der reguläre Weg „Version speichern" bleibt unveraendert (Standard True)."""
    aufruf(planer, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    zweite = aufruf(planer, "plantyp_speichern", definition=_progdefinition(),
                    gueltig_ab="2026-06-01", kommentar="Fortsetzung")
    assert zweite["versionsnummer"] == 2


# ── UXP-R12: Auswirkung vorab ──────────────────────────────────────────────


def test_uxp_r12_auswirkung_nennt_termine_und_plaene(planer):
    aufruf(planer, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    aufruf(planer, "plan_anlegen", plantyp="prog-p114", titel="Adventssingen",
           von="2026-12-01", bis="2026-12-31", parameter={"uhrzeit": "17:00"})
    frueh = aufruf(planer, "plantyp_auswirkung", plantyp="prog-p114", gueltig_ab="2026-01-01")
    assert frueh["termine"] >= 1, frueh
    assert frueh["plaene"] == 1, frueh
    spaet = aufruf(planer, "plantyp_auswirkung", plantyp="prog-p114", gueltig_ab="2027-01-01")
    assert spaet["termine"] == 0 and spaet["plaene"] == 0, spaet


# ── UXP-R9/R13: Bereich als Auswahlliste mit Anzeigename ───────────────────


def test_uxp_r9_bereich_als_auswahlliste(planer):
    rechte = aufruf(planer, "einrichten_rechte")
    assert "bereich_liste" in rechte, rechte
    assert {"kennung": "Chor", "name": "Chor"} in rechte["bereich_liste"], rechte


def test_uxp_r13_bereichsname_statt_interner_kennung(planer, patched_db):
    """Neu angelegte Bereiche tragen die ID als name, den Text in ministry."""
    from diakronos_app.models.diakonos import Dienstbereich, DienstbereichVerantwortlicher
    with patched_db.begin() as s:
        s.add(Dienstbereich(name="b3f1a2c4-9", ministry="Technik", sortierung=1))
        s.add(DienstbereichVerantwortlicher(
            name="bv-technik", parent="b3f1a2c4-9", parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer"))
    aufruf(planer, "plantyp_speichern",
           definition={**_progdefinition("prog-p114c"), "bereich": "b3f1a2c4-9"},
           gueltig_ab="2026-01-01")
    rechte = aufruf(planer, "einrichten_rechte")
    treffer = [b for b in rechte["bereich_liste"] if b["kennung"] == "b3f1a2c4-9"]
    assert treffer and treffer[0]["name"] == "Technik", rechte["bereich_liste"]
    typ = [t for t in aufruf(planer, "plantypen_liste") if t["schluessel"] == "prog-p114c"][0]
    assert typ["bereich_name"] == "Technik", typ


# ── UXP-R6: gepflegter Auswahlwert bleibt sichtbar ─────────────────────────


def test_uxp_r6_gepflegter_auswahlwert_ueberlebt_neuladen(planer, patched_db):
    from diakronos_app.models.psalmos import Lied
    with patched_db.begin() as s:
        s.add(Lied(name="lied-a", titel="Golgatha", aktiv=True, idx=0, docstatus=0))
    definition = {
        "schema": "diakronos/plantyp@1", "id": "chor-p114", "name": "Chorplan",
        "bereich": "Chor",
        "merkmale": {"lieder": [{"id": "instrument", "art": "auswahl", "name": "Instrument",
                                 "werte": ["Geige", "Gitarre", "Kontrabass"]}]},
        "termine": {"manuell": [{"datum": "2026-11-15"}]},
        "felder": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}],
    }
    aufruf(planer, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    aufruf(planer, "sammlungsmerkmal_werte_pflegen", plantyp="chor-p114",
           schluessel="instrument", aktion="hinzufuegen", wert="Cello")
    daten = aufruf(planer, "stammdaten_holen", plantyp="chor-p114")
    werte = daten["merkmale"]["lieder"][0]["werte"]
    assert "Cello" in werte, werte
    assert "Geige" in werte, werte


# ── UXP-R4: Untergruppen als Teams + Bedarf ────────────────────────────────


def test_uxp_r4_bedarf_nennt_teams_unter_obergruppe():
    """Bedarfspruefung meldet Teams unter der erwarteten Obergruppe."""
    definition = {
        "schema": "diakronos/plantyp@1", "id": "mt-p114", "name": "Musikteams",
        "bereich": "Chor",
        "felder": [{"id": "team", "art": "team", "name": "Team",
                    "teams": {"gruppe_unter": "Musikteams"}}],
    }
    quelle = InMemoryDatenquelle(
        personen_liste=[Person(kennung="p1", name="Anna"), Person(kennung="p2", name="Ben")],
        gruppen_liste=[Gruppe(kennung="team-a", name="Team A",
                              mitglieder=frozenset({"p1"}), obergruppe="Musikteams")],
    )
    bedarfe = bedarfspruefung(definition, quelle)
    team = [b for b in bedarfe if b.art == "team"]
    assert team, bedarfe
    assert "Musikteams" in team[0].abdeckung, team[0]


def test_uxp_r4_leere_obergruppe_wird_ausdruecklich_gemeldet():
    definition = {
        "schema": "diakronos/plantyp@1", "id": "mt-p114", "name": "Musikteams",
        "bereich": "Chor",
        "felder": [{"id": "team", "art": "team", "teams": {"gruppe_unter": "Musikteams"}}],
    }
    bedarfe = bedarfspruefung(definition, InMemoryDatenquelle())
    team = [b for b in bedarfe if b.art == "team"]
    assert team and "0 vorhanden" in team[0].abdeckung, team


def test_uxp_r4_untergruppen_sind_ueber_die_datenquelle_als_teams_nutzbar(
        client, patched_db):
    """Eine Untergruppe (App-Tabelle) ist ein Team mit ihrer Gruppe als Obergruppe."""
    from diakronos_app.models.diakonos import (
        Gruppe as GruppeModell, Untergruppe, Untergruppenmitgliedschaft, Mitglied,
    )
    from diakronos_app.models.core import User
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle
    with patched_db.begin() as s:
        s.add(User(name="u1", email="u1", enabled=True))
        s.add(Mitglied(name="u1", user="u1", vorname="Anna", nachname="Test",
                       status="Mitglied", docstatus=0, idx=0))
        s.add(GruppeModell(name="Musikteams", gruppenname="Musikteams", docstatus=0, idx=0))
        s.add(Untergruppe(name="team-a", untergruppenname="Team A", gruppe="Musikteams",
                          docstatus=0, idx=0))
        s.add(Untergruppenmitgliedschaft(name="um1", parent="team-a", parenttype="Untergruppe",
                                         parentfield="mitglieder", mitglied="u1",
                                         docstatus=0, idx=0))
    with patched_db.begin() as s:
        quelle = DBDatenquelle(s, plantyp="mt-p114")
        teams = {g.kennung: g for g in quelle.gruppen()}
    assert "team-a" in teams, teams
    assert teams["team-a"].obergruppe == "Musikteams", teams["team-a"]
    assert teams["team-a"].mitglieder == frozenset({"u1"}), teams["team-a"]


# ── OP-EVENT-7: Bedarf nennt „Mitarbeiter aus Anmeldungen: 0" ──────────────


def test_op_event_7_bedarf_nennt_anmeldungsfilter():
    freizeit = ressourcen.kochbuch_laden("freizeit")
    quelle = InMemoryDatenquelle(
        personen_liste=[Person(kennung="p1", name="Anna")],
        anmeldungen_liste=[],
    )
    bedarfe = bedarfspruefung(freizeit, quelle)
    anmeldung = [b for b in bedarfe if b.art == "anmeldung"]
    assert anmeldung, [b.art for b in bedarfe]
    assert "Anmeldungen" in anmeldung[0].abdeckung, anmeldung[0]
    assert anmeldung[0].einstufung == "blockiert_automatik", anmeldung[0]


def test_op_event_17_freizeit_regen_hat_programm_und_leitung():
    """Die Regen-Variante verdrängt nicht mehr Programm und Leitung."""
    freizeit = ressourcen.kochbuch_laden("freizeit")
    nachmittag = next(f for f in freizeit["felder"] if f["id"] == "nachmittag")
    regen = next(v for v in nachmittag["varianten"] if isinstance(v, dict) and v["id"] == "regen")
    ids = {f["id"] for f in regen["inhalt"]}
    assert "halle" in ids, ids
    assert any("leitung" in i for i in ids), ids
    assert any("programm" in i for i in ids), ids
    # Abend: Leitung steht ausserhalb der Teile (gilt fuer beide Varianten).
    abend = next(f for f in freizeit["felder"] if f["id"] == "abend")
    assert any(f["id"] == "leitung" for f in abend["inhalt"]), abend["inhalt"]


# ── OP-CHOR-1 / OP-EVENT-18: Termine nachtraeglich aendern ─────────────────


@pytest.fixture()
def chorplan(client, patched_db):
    stammdaten(patched_db, "planer", "mitglied")
    anmelden(client, "planer")
    aufruf(client, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="prog-p114", titel="Programm",
               von="2026-12-01", bis="2026-12-31", parameter={"uhrzeit": "17:00"})["id"]
    termin = aufruf(client, "plan_holen", plan=p)["termine"][0]["id"]
    return p, termin


def test_op_chor_1_termin_aendern_und_entfernen(chorplan, client):
    p, termin = chorplan
    neu = aufruf(client, "termin_aendern", plan=p, termin=termin,
                 datum="2026-12-13", uhrzeit="18:30", titel="Sonderprobe",
                 anlaesse=["probe"])
    assert neu["termin"]["datum"] == "2026-12-13", neu
    assert str(neu["termin"]["uhrzeit"]).startswith("18:30"), neu
    assert neu["termin"]["titel"] == "Sonderprobe", neu
    assert neu["termin"]["anlaesse"] == ["probe"], neu
    # Absagen
    aus = aufruf(client, "termin_aendern", plan=p, termin=termin, entfaellt=True)
    assert aus["termin"]["entfaellt"] is True, aus


def test_op_chor_1_termin_hinzufuegen_und_entfernen(chorplan, client):
    p, termin = chorplan
    neu = aufruf(client, "termin_hinzufuegen", plan=p, datum="2026-12-20",
                 uhrzeit="19:30", titel="Sonderprobe", anlaesse=["probe"])
    assert neu["termin"]["datum"] == "2026-12-20", neu
    assert neu["termin"]["quelle"] == "manuell", neu
    vorher = len(aufruf(client, "plan_holen", plan=p)["termine"])
    aufruf(client, "termin_entfernen", plan=p, termin=neu["termin"]["id"])
    nachher = len(aufruf(client, "plan_holen", plan=p)["termine"])
    assert nachher == vorher - 1, (vorher, nachher)


def test_op_event_18_variante_je_termin_festlegen(client, patched_db):
    """Sonne/Regen: die je Termin geltende Variante bleibt erhalten."""
    stammdaten(patched_db, "planer", "mitglied")
    anmelden(client, "planer")
    definition = {
        "schema": "diakronos/plantyp@1", "id": "fz-p114", "name": "Freizeit",
        "bereich": "Chor",
        "termine": {"manuell": [{"datum": "2026-07-05"}]},
        "felder": [{
            "id": "nachmittag", "art": "gruppe",
            "varianten": [
                "sonne",
                {"id": "regen", "name": "Regen",
                 "inhalt": [{"id": "halle", "art": "text", "name": "Ausweichraum"}]},
            ],
            "inhalt": [{"id": "programm", "art": "text"}],
        }],
    }
    aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="fz-p114", titel="Freizeit",
               von="2026-07-01", bis="2026-07-10")["id"]
    termin = aufruf(client, "plan_holen", plan=p)["termine"][0]["id"]

    def pfade():
        s = aufruf(client, "termin_struktur", plan=p, termin=termin)
        return {x["feld_pfad"] for x in (s.get("slots") or [])}

    # Ohne Auswahl gelten beide Varianten (bisheriges Verhalten).
    ohne = pfade()
    assert any("@sonne" in x for x in ohne), ohne
    assert any("@regen" in x for x in ohne), ohne
    # Regen festlegen -> nur noch die Regen-Variante ist aktiv.
    aufruf(client, "termin_aendern", plan=p, termin=termin, variante="regen",
           variante_setzen=True)
    mit = pfade()
    assert any("@regen" in x for x in mit), mit
    assert not any("@sonne" in x for x in mit), mit
    # Der Termin traegt die Auswahl dauerhaft.
    assert aufruf(client, "plan_holen", plan=p)["termine"][0].get("variante") == "regen"


# ── OP-UI-12: Plaene loeschen/archivieren/kopieren/aendern ─────────────────


def test_op_ui_12_plan_kopieren_und_aendern(chorplan, client):
    p, _termin = chorplan
    kopie = aufruf(client, "plan_kopieren", plan=p, titel="Programm (Kopie)",
                   mit_eintraegen=True)
    assert kopie["plan"] != p, kopie
    neu = aufruf(client, "plan_holen", plan=kopie["plan"])
    assert neu["plan"]["titel"] == "Programm (Kopie)", neu["plan"]
    assert neu["plan"]["status"] == "entwurf", neu["plan"]
    assert len(neu["termine"]) == 1, neu["termine"]
    # Umbenennen
    geaendert = aufruf(client, "plan_aendern", plan=kopie["plan"], titel="Neuer Titel")
    assert geaendert["titel"] == "Neuer Titel", geaendert


def test_op_ui_12_entwurf_loeschen_veroeffentlichter_archivieren(chorplan, client):
    p, _termin = chorplan
    # Entwurf loeschen (P1-14b: die unwiderrufliche Loeschung verlangt die
    # ausdrueckliche Bestaetigung des Servers).
    entwurf = aufruf(client, "plan_kopieren", plan=p, titel="Wegwerf")
    aufruf(client, "plan_loeschen", plan=entwurf["plan"], bestaetigt=True)
    r = client.post(PFAD + "plan_holen", json={"plan": entwurf["plan"]})
    assert r.status_code in (403, 417, 404), r.text
    # Veroeffentlichen -> Loeschen verboten, Archivieren erlaubt
    aufruf(client, "veroeffentlichen", plan=p)
    r = client.post(PFAD + "plan_loeschen", json={"plan": p})
    assert r.status_code == 417, r.text
    arch = aufruf(client, "plan_archivieren", plan=p)
    assert arch["status"] == "archiviert", arch
    zurueck = aufruf(client, "plan_archivieren", plan=p, archivieren=False)
    assert zurueck["status"] == "veroeffentlicht", zurueck


# ── UXP-R20: Rueckgaengig nimmt Veroeffentlichung nicht zurueck ────────────


def test_uxp_r20_undo_nimmt_veroeffentlichung_nicht_zurueck(chorplan, client):
    p, _termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    vorschau = aufruf(client, "undo_vorschau", plan=p)
    # Die Veroeffentlichung ist KEIN Rueckgaengig-Ziel.
    assert vorschau["moeglich"] is False, vorschau
    r = client.post(PFAD + "undo", json={"plan": p})
    assert r.status_code == 417, r.text
    # Der Plan bleibt veroeffentlicht — kein stiller Rueckzug fuer Mitglieder.
    assert aufruf(client, "plan_holen", plan=p)["plan"]["status"] == "veroeffentlicht"


def test_uxp_r20_undo_beschreibt_das_ziel(chorplan, client):
    """Ein Eintrags-Undo nennt in Klartext, was zurueckgenommen wird."""
    p, termin = chorplan
    aufruf(client, "termin_aendern", plan=p, termin=termin, titel="Geaendert")
    vorschau = aufruf(client, "undo_vorschau", plan=p)
    assert vorschau["moeglich"] is True, vorschau
    assert vorschau["beschreibung"], vorschau
    ergebnis = aufruf(client, "undo", plan=p)
    assert ergebnis["beschreibung"], ergebnis
