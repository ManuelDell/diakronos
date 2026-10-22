"""UI2-Erweiterungen des Plan-Rahmens: Editor- und Stammdatendienste.

Je Slice rot/gruen: erst die Tests (Endpunkt fehlt -> rot), dann die
Implementierung. Isolierte In-Memory-SQLite ueber die Standard-Fixtures;
kein Zugriff auf den Betriebs-Stack.

Slices:
1. kochbuch_holen — gepruefte Vorlage ueber Whitelist statt Pfadangabe.
2. schema_holen + x-regel-bausteine — Registry der Regel-Bausteine als
   x-Erweiterung, ohne das Hauptschema zu beschaedigen.
3. stammdaten_holen — deklarierte Merkmale samt Werten, Personen, eigene
   Sammlungen und eingebaute Lieder; ohne PII, Plan-Umfang getrennt.
4. plantypen_liste/einrichten_rechte — Serverfaehigkeiten fuer Plantyp-
   Edit gegen Plan-Stammdaten; Anlegerechte auch bei leerer Liste.
5. trockenlauf — neue ungespeicherte Definitionen nur im eigenen Bereich;
   viewtaugliches Ergebnis (Termine mit IDs, Eintraege mit termin,
   anzeige wie plan_holen) ohne Persistenz.
"""
PFAD = "/api/method/diakronos.planrahmen.api."


def aufruf(client, methode, **daten):
    r = client.post(PFAD + methode, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def stammdaten(sf):
    """Bereiche, Konten, Mitglieder und Verantwortlichkeiten fuer UI2-Tests."""
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


def zaehle(patched_db):
    """Persistenz-Zaehler: Trockenlauf/Stammdaten duerfen nichts schreiben."""
    from sqlalchemy import func, select
    from diakronos_app.models.planrahmen import Eintrag, MerkmalWert, Plan, PlantypVersion, SammlungEintrag, Termin, Verlauf
    with patched_db() as s:
        return {t.__tablename__: s.scalar(select(func.count()).select_from(t))
                for t in (Plan, PlantypVersion, Termin, Eintrag, Verlauf, MerkmalWert, SammlungEintrag)}


# --------------------------------------------------------------------------- #
# Slice 1: kochbuch_holen — Whitelist statt Ressourcenpfad
# --------------------------------------------------------------------------- #

def test_kochbuch_holen_liefert_gueltiges_beispiel(client, patched_db):
    from diakronos_app.planrahmen import ressourcen
    for name in ("chorplan", "freizeit"):
        daten = aufruf(client, "kochbuch_holen", name=name)
        assert daten == ressourcen.kochbuch_laden(name)
        assert daten["id"] == name


def test_kochbuch_holen_unbekannt_oder_pfad_417(client, patched_db):
    r = client.post(PFAD + "kochbuch_holen", json={"name": "gibtsnicht"})
    assert r.status_code == 417
    assert r.json()["meldungen"][0]["pfad"] == "/name"
    for name in ("../../settings", "../instanzen/adventssingen", "kochbuch/chorplan"):
        assert client.post(PFAD + "kochbuch_holen", json={"name": name}).status_code == 417


# --------------------------------------------------------------------------- #
# Slice 2: schema_holen + x-regel-bausteine Registry
# --------------------------------------------------------------------------- #

def test_schema_holen_regel_bausteine_als_x_erweiterung(client, patched_db):
    from diakronos_app.planrahmen.regeln.registry import REGEL_BAUSTEINE
    schema = aufruf(client, "schema_holen")
    assert schema["$schema"].startswith("https://json-schema.org")
    bausteine = schema["x-regel-bausteine"]
    assert set(bausteine) == {b.schluessel for b in REGEL_BAUSTEINE}
    for b in REGEL_BAUSTEINE:
        eintrag = bausteine[b.schluessel]
        assert set(eintrag) == {"beschreibung", "parameter_schema"}
        assert eintrag["beschreibung"] == b.kurz
        assert eintrag["parameter_schema"] == b.parameter_schema


def test_schema_holen_beschaedigt_hauptschema_nicht(client, patched_db):
    """Die Registry landet nur in der Antwort; Ressourcen-Schema bleibt roh."""
    from diakronos_app.planrahmen import ressourcen
    vorher = ressourcen.schema_daten()
    aufruf(client, "schema_holen")
    danach = ressourcen.schema_daten()
    assert "x-regel-bausteine" not in danach
    assert danach == vorher
    # Zwei Aufrufe liefern identische, unveraenderte Daten.
    assert aufruf(client, "schema_holen") == {**vorher, "x-regel-bausteine": aufruf(client, "schema_holen")["x-regel-bausteine"]}


# --------------------------------------------------------------------------- #
# Slice 3: stammdaten_holen — deklarierte Daten ohne PII
# --------------------------------------------------------------------------- #

def stamm_definition():
    return {"schema": "diakronos/plantyp@1", "id": "stamm-ui2", "name": "Stamm UI2",
            "bereich": "Chor",
            "merkmale": {"person": [{"id": "dirigent", "art": "tag", "name": "dirigiert"}],
                         "lieder": [{"id": "thema", "art": "text", "name": "Thema"}],
                         "themen": [{"id": "stelle", "art": "text", "name": "Bibelstelle"}]},
            "sammlungen": [{"id": "themen", "name": "Themen"},
                           {"id": "tagesordnung", "name": "Tagesordnung", "umfang": "plan"}],
            "termine": {"manuell": [{"datum": "2026-01-04"}]},
            "felder": [{"id": "lieder", "art": "eintrag", "sammlung": "lieder"},
                       {"id": "themen", "art": "eintrag", "sammlung": "themen"}]}


def stamm_setup(client, patched_db, verantwortlich=None):
    """Plantyp, Personen (inkl. PII-Fallen), Lieder, Sammlungen, Merkmale."""
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
    from diakronos_app.models.psalmos import Lied
    from diakronos_app.models.planrahmen import Abwesenheit, Merkmal, MerkmalWert
    from datetime import date
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add_all([Mitglied(name=k, email=k + "@example.org", vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in ("mia", "jonas")])
        s.add(Gruppe(name="team-musik", gruppenname="Musik-Team", obergruppe="Musik"))
        s.flush()
        s.add_all([Gruppenmitgliedschaft(name=k, parent="team-musik", parenttype="Gruppe",
                                         parentfield="mitglieder", mitglied=k, status="Aktiv")
                   for k in ("mia",)])
        s.add_all([Lied(name="lied" + str(i), titel="Lied " + str(i), aktiv=True) for i in range(3)])
        s.add(Lied(name="liedinaktiv", titel="Nicht aktiv", aktiv=False))
        # Nicht deklariertes Merkmal: darf in keiner Antwort erscheinen.
        geheim = Merkmal(ziel="person", schluessel="geheim", art="text",
                         definition={"id": "geheim", "art": "text"})
        s.add(geheim)
        s.flush()
        s.add(MerkmalWert(merkmal=geheim.id, ziel_id="mia", wert={"wert": "Streng geheim"}))
        s.add(Abwesenheit(mitglied="mia", von=date(2026, 3, 1), bis=date(2026, 3, 2),
                          grund="Krankheit", nur_plantyp="stamm-ui2"))
    anmelden(client, "Administrator")
    aufruf(client, "plantyp_speichern", definition=stamm_definition(), gueltig_ab="2026-01-01")
    aufruf(client, "merkmale_pflegen", plantyp="stamm-ui2", werte=[
        {"ziel": "person", "schluessel": "dirigent", "ziel_id": "mia", "wert": True},
        {"ziel": "sammlung:lieder", "schluessel": "thema", "ziel_id": "lied0", "wert": "Advent"}])
    aufruf(client, "sammlung_pflegen", plantyp="stamm-ui2", sammlung="themen",
           eintraege=[{"daten": {"titel": "Auftakt", "stelle": "Psalm 1", "intern": "privat"}}])
    p = aufruf(client, "plan_anlegen", plantyp="stamm-ui2", titel="Plan A",
               von="2026-01-01", bis="2026-12-31", verantwortlich=verantwortlich)
    return p["id"]


def test_stammdaten_holen_rechte(client, patched_db):
    plan = stamm_setup(client, patched_db, verantwortlich="mitglied")
    anmelden(client, "gast")
    assert client.get(PFAD + "stammdaten_holen", params={"plantyp": "stamm-ui2"}).status_code == 403
    # Planverantwortliche(r) ohne Bereiche: nur mit konkreter Plan-ID.
    anmelden(client, "mitglied")
    assert client.get(PFAD + "stammdaten_holen", params={"plantyp": "stamm-ui2"}).status_code == 403
    assert aufruf(client, "stammdaten_holen", plantyp="stamm-ui2", plan=plan)["plan"] == plan
    # Fremder Bereich, eigener Plan eines anderen Plantyps: 417 statt Daten.
    anmelden(client, "planer_freizeit")
    assert client.get(PFAD + "stammdaten_holen", params={"plantyp": "stamm-ui2"}).status_code == 403
    # Bereicheigentum gilt auch ohne Plan.
    anmelden(client, "planer_chor")
    assert aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")["plan"] is None
    # Plan eines anderen Plantyps ist kein Ersatz.
    anmelden(client, "Administrator")
    fremd = aufruf(client, "plan_anlegen", plantyp="stamm-ui2", titel="Fremd",
                   von="2026-01-01", bis="2026-12-31")
    anmelden(client, "mitglied")
    r = client.post(PFAD + "stammdaten_holen", json={"plantyp": "gibtsnicht", "plan": fremd["id"]})
    assert r.status_code == 417


def test_stammdaten_holen_deklariert_ohne_pii(client, patched_db):
    stamm_setup(client, patched_db)
    anmelden(client, "planer_chor")
    daten = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")
    typ = aufruf(client, "plantypen_liste")[0]
    assert daten["plantyp"] == {"id": typ["id"], "name": "Stamm UI2", "bereich": "Chor"}
    # Nur deklarierte Merkmale, sonstige Werte fehlen.
    assert [m["id"] for m in daten["merkmale"]["person"]] == ["dirigent"]
    assert [m["id"] for m in daten["merkmale"]["lieder"]] == ["thema"]
    assert [m["id"] for m in daten["merkmale"]["themen"]] == ["stelle"]
    personen = {p["kennung"]: p for p in daten["personen"]}
    assert set(personen) >= {"mia", "jonas"}
    assert personen["mia"]["name"] == "Mia Test" and personen["mia"]["vorname"] == "Mia"
    # UXP-R3: Das eingebaute Attribut kuerzel wird aus Vor-/Nachname abgeleitet
    # (nie mehr leer), damit {dirigent.kuerzel} in Formatvorlagen etwas zeigt.
    assert personen["mia"]["kuerzel"] == "M. Test" and personen["mia"]["gruppen"] == ["team-musik"]
    assert personen["mia"]["merkmale"] == {"dirigent": True}
    assert personen["jonas"]["merkmale"] == {}
    gruppen = {g["kennung"]: g for g in daten["gruppen"]}
    assert gruppen["team-musik"]["name"] == "Musik-Team" and gruppen["team-musik"]["mitglieder"] == ["mia"]
    # Eingebaute Lieder: IDs, Titel, deklarierte Werte — inaktive fehlen.
    lieder = {e["kennung"]: e for e in daten["lieder"]}
    assert set(lieder) == {"lied0", "lied1", "lied2"}
    assert lieder["lied0"]["titel"] == "Lied 0" and lieder["lied0"]["merkmale"] == {"thema": "Advent"}
    assert lieder["lied1"]["merkmale"] == {}
    # Eigene Sammlung: Titel + deklarierte Merkmale, nicht-deklarierte Attribute fehlen.
    themen = next(s for s in daten["sammlungen"] if s["schluessel"] == "themen")
    assert themen["umfang"] == "gemeinde" and len(themen["eintraege"]) == 1
    assert themen["eintraege"][0]["titel"] == "Auftakt"
    assert themen["eintraege"][0]["merkmale"] == {}
    # Datenschutz: keine E-Mails, keine Abwesenheitsgründe, keine geheimen Merkmale.
    r = client.post(PFAD + "stammdaten_holen", json={"plantyp": "stamm-ui2"})
    assert "example.org" not in r.text and "Krankheit" not in r.text and "geheim" not in r.text


def test_stammdaten_holen_planumfang_getrennt_und_kein_persistieren(client, patched_db):
    plan_a = stamm_setup(client, patched_db, verantwortlich="mitglied")
    anmelden(client, "Administrator")
    plan_b = aufruf(client, "plan_anlegen", plantyp="stamm-ui2", titel="Plan B",
                    von="2026-01-01", bis="2026-12-31")["id"]
    for plan, titel in ((plan_a, "Sitzung A"), (plan_b, "Sitzung B")):
        aufruf(client, "sammlung_pflegen", plantyp="stamm-ui2", sammlung="tagesordnung",
               plan=plan, eintraege=[{"daten": {"titel": titel}}])
    vorher = zaehle(patched_db)
    anmelden(client, "planer_chor")
    # Ohne Plan-ID bleibt die planbezogene Sammlung unsichtbar (strict).
    ohne = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")
    assert {s["schluessel"] for s in ohne["sammlungen"]} == {"themen"}
    assert ohne["plan"] is None
    # Mit Plan-ID: nur dieser Plan, nicht die Fremd-Fassung.
    mit = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2", plan=plan_a)
    tagesordnung = next(s for s in mit["sammlungen"] if s["schluessel"] == "tagesordnung")
    assert tagesordnung["umfang"] == "plan"
    assert [e["titel"] for e in tagesordnung["eintraege"]] == ["Sitzung A"]
    assert mit["plan"] == plan_a
    # Planverantwortliche(r) sieht die Stammdaten mit eigener Plan-ID.
    anmelden(client, "mitglied")
    assert aufruf(client, "stammdaten_holen", plantyp="stamm-ui2", plan=plan_a)["plan"] == plan_a
    assert zaehle(patched_db) == vorher  # lesen schreibt nichts


# --------------------------------------------------------------------------- #
# Slice 4: plantypen_liste (darf_plantyp_bearbeiten) + einrichten_rechte
# --------------------------------------------------------------------------- #

def test_planverantwortlicher_pflegt_nur_eigenen_kontext(client, patched_db):
    plan = stamm_setup(client, patched_db, verantwortlich="mitglied")
    anmelden(client, "mitglied")
    assert aufruf(client, "bedarf", plantyp="stamm-ui2", plan=plan)
    assert client.post(PFAD + "merkmale_pflegen", json={"plantyp": "stamm-ui2", "plan": plan,
        "werte": [{"ziel": "person", "schluessel": "dirigent", "ziel_id": "jonas", "wert": True}]}).status_code == 403
    assert client.post(PFAD + "sammlung_pflegen", json={"plantyp": "stamm-ui2", "plan": plan,
        "sammlung": "themen", "eintraege": [{"daten": {"titel": "Global verboten"}}]}).status_code == 403
    assert aufruf(client, "stammdaten_holen", plantyp="stamm-ui2", plan=plan)["darf_globale_stammdaten_bearbeiten"] is False
    aufruf(client, "sammlung_pflegen", plantyp="stamm-ui2", plan=plan,
           sammlung="tagesordnung", eintraege=[{"daten": {"titel": "Eigen"}}])
    for methode, args in (("bedarf", {}), ("merkmale_pflegen", {"werte": []}),
                          ("sammlung_pflegen", {"sammlung": "themen", "eintraege": []})):
        assert client.post(PFAD + methode, json={"plantyp": "stamm-ui2", **args}).status_code == 403
    anmelden(client, "Administrator")
    fremd = aufruf(client, "plan_anlegen", plantyp="stamm-ui2", titel="Fremd",
                   von="2026-01-01", bis="2026-12-31")["id"]
    anmelden(client, "mitglied")
    assert client.post(PFAD + "sammlung_pflegen", json={"plantyp": "stamm-ui2", "plan": fremd,
        "sammlung": "tagesordnung", "eintraege": []}).status_code == 403


def test_inaktive_sammlung_sichtbar_und_verdeckte_attribute_erhalten(client, patched_db):
    from diakronos_app.models.planrahmen import SammlungEintrag
    stamm_setup(client, patched_db)
    daten = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")
    e = next(s for s in daten["sammlungen"] if s["schluessel"] == "themen")["eintraege"][0]
    aufruf(client, "sammlung_pflegen", plantyp="stamm-ui2", sammlung="themen", eintraege=[
        {"id": e["kennung"], "daten": {"titel": "Neu"}, "aktiv": False, "reihenfolge": 4}])
    neu = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")
    zeile = next(s for s in neu["sammlungen"] if s["schluessel"] == "themen")["eintraege"][0]
    assert zeile["aktiv"] is False and zeile["reihenfolge"] == 4
    assert zeile["daten"] == {"titel": "Neu"}
    with patched_db() as s:
        assert s.get(SammlungEintrag, e["kennung"]).daten["intern"] == "privat"


def test_plantypen_liste_darf_plantyp_bearbeiten(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "Administrator")
    aufruf(client, "plantyp_speichern", definition=definition("chor-ui2", "Chor UI2", "Chor"),
           gueltig_ab="2026-01-01")
    aufruf(client, "plan_anlegen", plantyp="chor-ui2", titel="Mein Plan", von="2026-01-01",
           bis="2026-12-31", verantwortlich="mitglied")
    anmelden(client, "planer_chor")
    chor = aufruf(client, "plantypen_liste")[0]
    assert chor["darf_plantyp_bearbeiten"] is True
    assert chor["darf_plan_anlegen"] is True and chor["darf_bearbeiten"] is True
    # Planverantwortung ohne Bereich: Plan-Stammdaten ja, Plantyp-Edit nein.
    anmelden(client, "mitglied")
    chor = aufruf(client, "plantypen_liste")[0]
    assert chor["darf_plantyp_bearbeiten"] is False
    assert chor["darf_plan_anlegen"] is False and chor["darf_bearbeiten"] is True


def test_einrichten_rechte_auch_bei_leerer_liste(client, patched_db):
    stammdaten(patched_db)
    # Bereichsverantwortliche(r) ohne jeden Plantyp: anlegbereit.
    anmelden(client, "planer_chor")
    assert aufruf(client, "plantypen_liste") == []  # leer, aber keine 403
    rechte = aufruf(client, "einrichten_rechte")
    assert rechte == {"darf_anlegen": True, "bereiche": ["Chor"],
                      "bereich_liste": [{"kennung": "Chor", "name": "Chor"}],
                      "gruppen": [], "admin": False}
    # Planverantwortung ohne Bereich: sehen ja, anlegen nein.
    anmelden(client, "Administrator")
    aufruf(client, "plantyp_speichern", definition=definition("fz-ui2", "Freizeit UI2", "Freizeit"),
           gueltig_ab="2026-01-01")
    aufruf(client, "plan_anlegen", plantyp="fz-ui2", titel="Mein Plan", von="2026-01-01",
           bis="2026-12-31", verantwortlich="mitglied")
    anmelden(client, "mitglied")
    assert aufruf(client, "einrichten_rechte") == {
        "darf_anlegen": False, "bereiche": [], "bereich_liste": [], "gruppen": [], "admin": False}
    # Ohne jede Verantwortung gibt es keinerlei Auskunft.
    anmelden(client, "gast")
    assert client.get(PFAD + "einrichten_rechte").status_code == 403
    # Admin: alle Bereiche wählbar.
    anmelden(client, "Administrator")
    admin = aufruf(client, "einrichten_rechte")
    assert admin == {"darf_anlegen": True, "bereiche": ["Chor", "Freizeit"],
                     "bereich_liste": [{"kennung": "Chor", "name": "Chor"},
                                       {"kennung": "Freizeit", "name": "Freizeit"}],
                     "gruppen": [], "admin": True}


# --------------------------------------------------------------------------- #
# Slice 5: trockenlauf — Rechte und viewtaugliches Ergebnis
# --------------------------------------------------------------------------- #

def trocken_definition(schluessel, bereich="Chor", wochenbar=True):
    d = {"schema": "diakronos/plantyp@1", "id": schluessel, "name": "Trocken " + schluessel,
         "merkmale": {"person": [{"id": "klavier", "art": "tag", "name": "spielt Klavier"}]},
         "felder": [{"id": "solistin", "art": "person", "rolle": {"merkmal": "klavier"}},
                    {"id": "lied", "art": "eintrag", "sammlung": "lieder"}],
         "termine": ({"regel": "FREQ=WEEKLY;BYDAY=SU"} if wochenbar
                     else {"manuell": [{"datum": "2026-01-04"}]})}
    if bereich:
        d["bereich"] = bereich
    return d


def test_trockenlauf_rechte_neue_und_vorhandene_definition(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "planer_chor")
    neu_chor = trocken_definition("neu-ui2", "Chor")
    assert aufruf(client, "trockenlauf", definition=neu_chor, ab="2026-01-01", wochen=1)
    # Bereiche anderer Verantwortlicher und Bereichslose Definitionen: 403.
    anmelden(client, "planer_freizeit")
    assert client.post(PFAD + "trockenlauf",
                       json={"definition": neu_chor, "ab": "2026-01-01", "wochen": 1}).status_code == 403
    anmelden(client, "planer_chor")
    assert client.post(PFAD + "trockenlauf", json={
        "definition": trocken_definition("neu-bereichlos", None), "ab": "2026-01-01",
        "wochen": 1}).status_code == 403
    anmelden(client, "mitglied")
    assert client.post(PFAD + "trockenlauf",
                       json={"definition": neu_chor, "ab": "2026-01-01", "wochen": 1}).status_code == 403
    anmelden(client, "Administrator")
    assert aufruf(client, "trockenlauf", definition=trocken_definition("neu-bereichlos", None),
                  ab="2026-01-01", wochen=1)
    # Vorhandener Typscope: Rechte gelten am gespeicherten Bereich.
    aufruf(client, "plantyp_speichern", definition=definition("chor-ui2", "Chor UI2", "Chor"),
           gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    vorhanden = trocken_definition("chor-ui2", "Chor", wochenbar=False)
    assert aufruf(client, "trockenlauf", definition=vorhanden, ab="2026-01-01", wochen=1)
    # Bereichswechsel der Definition umgeht den Typscope nicht (nur Admin).
    umweg = trocken_definition("chor-ui2", "Freizeit", wochenbar=False)
    assert client.post(PFAD + "trockenlauf",
                       json={"definition": umweg, "ab": "2026-01-01", "wochen": 1}).status_code == 403
    anmelden(client, "planer_freizeit")
    assert client.post(PFAD + "trockenlauf",
                       json={"definition": umweg, "ab": "2026-01-01", "wochen": 1}).status_code == 403
    anmelden(client, "Administrator")
    assert aufruf(client, "trockenlauf", definition=umweg, ab="2026-01-01", wochen=1)


def test_trockenlauf_ergebnis_viewtauglich_und_kein_persistieren(client, patched_db):
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.psalmos import Lied
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add_all([Mitglied(name=k, email=k + "@example.org", vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in ("mia", "jonas")])
        s.add_all([Lied(name="lied" + str(i), titel="Lied " + str(i), aktiv=True) for i in range(3)])
    anmelden(client, "Administrator")
    d = trocken_definition("trocken-ui2", "Chor")
    d["regeln"] = [{"baustein": "mindestabstand", "feld": "lied", "wochen": 100, "stufe": "sollte"}]
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    aufruf(client, "merkmale_pflegen", plantyp="trocken-ui2", werte=[
        {"ziel": "person", "schluessel": "klavier", "ziel_id": k, "wert": True} for k in ("mia", "jonas")])
    vorher = zaehle(patched_db)
    ergebnis = aufruf(client, "trockenlauf", definition=d, ab="2026-01-01", wochen=4)
    assert zaehle(patched_db) == vorher  # Trockenlauf persistiert nichts
    # Rückwärtskompatible Schlüssel bleiben erhalten.
    assert {"termine", "eintraege", "anzeige", "bedarf", "meldungen", "verstoesse"} <= set(ergebnis)
    termine = ergebnis["termine"]
    assert len(termine) >= 4
    ids = [t["id"] for t in termine]
    assert len(set(ids)) == len(ids)
    for t in termine:
        assert t["plantyp_version"] == "probelauf"
        assert t["datum"] and t["reihe"] == "standard"
        assert t["titel"] == "" and t["uhrzeit"] is None and t["anlaesse"] == []
    # Einträge verweisen über `termin` auf die Termin-IDs; datum/reihe bleiben.
    assert ergebnis["eintraege"]
    for e in ergebnis["eintraege"]:
        assert e["termin"] in ids and e["feld_pfad"] and "datum" in e and "reihe" in e
    assert any(e["wert"] in ("mia", "jonas") for e in ergebnis["eintraege"])
    # Anzeige wie plan_holen: nur eingeteilte Kennungen, mit Namen, ohne PII.
    assert set(ergebnis["anzeige"]) <= {"mia", "jonas"} | {e["wert"] for e in ergebnis["eintraege"]}
    personen = {k: v for k, v in ergebnis["anzeige"].items() if k in ("mia", "jonas")}
    assert all(v["name"].endswith("Test") for v in personen.values())
    assert "example.org" not in client.post(
        PFAD + "trockenlauf", json={"definition": d, "ab": "2026-01-01", "wochen": 4}).text
    # Verstöße tragen die Termin-ID (oder None), wenn sie einen Termin meinen.
    assert ergebnis["verstoesse"]
    assert all(v["termin"] is None or v["termin"] in ids for v in ergebnis["verstoesse"])
    assert any(v["termin"] is not None for v in ergebnis["verstoesse"])
