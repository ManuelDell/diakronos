"""HTTP-Pfade, Rechte, Fehlerformat und CSRF des Plan-Rahmens."""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text, select
from sqlalchemy.pool import StaticPool
from diakronos_app.models.base import Base


@pytest.fixture()
def engine():
    """HTTP-Abnahme optional auf echtem PG, eigenes Schema je Test, nie Betrieb."""
    if os.environ.get("PLANRAHMEN_DISPOSABLE_DB") == "1":
        url = os.environ["DATABASE_URL"]
        assert "wegwerf-postgres-test" in url and url.endswith("/wegwerf")
        admin = create_engine(url)
        schema = "pr4_" + uuid.uuid4().hex
        with admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        eng = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        admin = None
        eng = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import diakronos_app.models
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    if admin:
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

PFAD = "/api/method/diakronos.planrahmen.api."
LESEND = ["schema_holen", "doku_holen", "kochbuch_liste", "kochbuch_holen", "plantyp_pruefen",
          "plantyp_versionen_liste", "plantypen_liste", "einrichten_rechte", "termin_struktur",
          "termin_strukturen", "plan_holen", "stammdaten_holen", "feld_kandidaten",
          "plaene_liste", "meine_dienste", "bedarf", "trockenlauf"]
SCHREIBEND = ["plantyp_speichern", "plan_anlegen", "plan_generieren", "eintrag_setzen",
              "eintrag_loesen", "platz_hinzufuegen", "undo", "veroeffentlichen", "merkmale_pflegen",
              "sammlung_pflegen", "abwesenheit_melden"]


@pytest.mark.parametrize("name", LESEND + SCHREIBEND)
def test_guest_403(guest_client, name):
    assert guest_client.post(PFAD + name, json={}).status_code == 401


@pytest.mark.parametrize("name", SCHREIBEND)
def test_schreibdienst_nicht_per_get(client, name):
    assert client.get(PFAD + name).status_code == 405


@pytest.mark.parametrize("name", SCHREIBEND)
def test_csrf_erzwingt_header(client, name):
    client.headers.pop("X-Frappe-CSRF-Token")
    r = client.post(PFAD + name, json={})
    assert r.status_code == 417
    assert r.json()["exc_type"] == "CSRFTokenError"


def test_ressourcen_und_strukturierte_fehler(client):
    assert client.get(PFAD + "schema_holen").json()["message"]["$schema"]
    assert "Plantyp" in client.get(PFAD + "doku_holen", params={"name": "REFERENZ"}).json()["message"]
    assert "chorplan" in client.get(PFAD + "kochbuch_liste").json()["message"]
    r = client.post(PFAD + "plantyp_speichern", json={"definition": {}, "gueltig_ab": "2026-01-01"})
    assert r.status_code == 417
    assert {"pfad", "code", "meldung", "hinweis"} <= r.json()["meldungen"][0].keys()
    assert client.get(PFAD + "doku_holen", params={"name": "../../settings.py"}).status_code == 417


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def stammdaten(sf):
    from diakronos_app.models.diakonos import Mitglied, Dienstbereich, Gruppe, Gruppenmitgliedschaft
    from diakronos_app.models.psalmos import Lied
    from diakronos_app.models.core import User
    with sf.begin() as s:
        s.add_all([Dienstbereich(name="Chor"), Dienstbereich(name="Freizeit")])
        s.add_all([User(name=k, email=k, enabled=True) for k in ("a", "b", "fremd")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k) for k in ("a", "b", "fremd")])
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add_all([Gruppenmitgliedschaft(name=k, parent="Chor", parenttype="Gruppe", parentfield="mitglieder", mitglied=k,
                                        status="Aktiv") for k in ("a", "b")])
        s.add_all([Lied(name="lied" + str(i), titel="Lied " + str(i), aktiv=True) for i in range(12)])


def test_chor_durchstich(client, patched_db):
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    stammdaten(patched_db)
    definition = kochbuch_laden("chorplan")
    v1 = aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    bed = aufruf(client, "bedarf", plantyp="chorplan")
    assert any(b["einstufung"] != "gut" for b in bed)
    werte = [{"ziel": "person", "schluessel": k, "ziel_id": m, "wert": True}
             for m in ("a", "b") for k in ("dirigent", "klavier", "einsingen")]
    werte += [{"ziel": "sammlung:lieder", "schluessel": k, "ziel_id": "lied" + str(i), "wert": m}
              for i in range(12) for k, m in (("dirigent", "a"), ("klavier", "b"))]
    aufruf(client, "merkmale_pflegen", plantyp="chorplan", werte=werte)
    p = aufruf(client, "plan_anlegen", plantyp="chorplan", titel="2026", von="2026-01-01", bis="2026-12-31")
    stand = aufruf(client, "plan_holen", plan=p["id"])
    termin = stand["termine"][0]["id"]
    aufruf(client, "abwesenheit_melden", mitglied="a", von="2026-01-01", bis="2026-01-31", plantyp="chorplan")
    aufruf(client, "plan_generieren", plan=p["id"])
    stand = aufruf(client, "plan_holen", plan=p["id"])
    assert not any(e["wert"] == "a" and e["feld_pfad"] == "einsingen" for e in stand["eintraege"]
                   if e["termin"] == termin)
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=termin, feld_pfad="lieder[0]", wert="lied11")
    aufruf(client, "plan_generieren", plan=p["id"])
    stand = aufruf(client, "plan_holen", plan=p["id"])
    assert next(e for e in stand["eintraege"] if e["termin"] == termin and e["feld_pfad"] == "lieder[0]")["fixiert"]
    aufruf(client, "undo", plan=p["id"])
    aufruf(client, "undo", plan=p["id"])
    aufruf(client, "veroeffentlichen", plan=p["id"])
    definition["felder"][0]["anzahl"] = 4
    v2 = aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-07-01")
    stand = aufruf(client, "plan_holen", plan=p["id"])
    assert all(t["plantyp_version"] == (v1["id"] if t["datum"] < "2026-07-01" else v2["id"]) for t in stand["termine"])
    for t in (stand["termine"][0], next(t for t in stand["termine"] if t["datum"] >= "2026-07-01")):
        struktur = aufruf(client, "termin_struktur", plan=p["id"], termin=t["id"])
        assert len([s for s in struktur["slots"] if s["art"] == "eintrag" and s["feld_pfad"].startswith("lieder")]) == (3 if t["datum"] < "2026-07-01" else 4)
    # PF1: Der Sammelaufruf liefert je Termin EXAKT dieselbe Struktur wie der
    # Einzelaufruf (Ersatz der N+1-Abfolge der Planseite, gleiches Ergebnis).
    alle = aufruf(client, "termin_strukturen", plan=p["id"])
    assert alle["plan"] == p["id"]
    je_termin = {e["termin"]["id"]: e for e in alle["strukturen"]}
    assert set(je_termin) == {t["id"] for t in stand["termine"]}
    for t in stand["termine"]:
        einzel = aufruf(client, "termin_struktur", plan=p["id"], termin=t["id"])
        assert je_termin[t["id"]]["slots"] == einzel["slots"]
        assert je_termin[t["id"]]["version"]["definition"] == einzel["version"]["definition"]
        assert je_termin[t["id"]]["version"]["id"] == einzel["version"]["id"]
    assert aufruf(client, "plantyp_versionen_liste", plantyp="chorplan")
    assert aufruf(client, "trockenlauf", definition=definition, ab="2026-07-01", wochen=1)
    assert aufruf(client, "plaene_liste")


@pytest.mark.parametrize("fehlend", ["zeitraum_von", "zeitraum_bis", "beide"])
def test_plaene_liste_ohne_zeitraum(client, patched_db, fehlend):
    from diakronos_app.models.planrahmen import Plan
    definition = {"schema": "diakronos/plantyp@1", "id": "ohnezeit", "name": "Ohne Zeitraum",
                  "termine": {"manuell": [{"datum": "2026-01-04"}]}, "felder": []}
    aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="ohnezeit", titel="Ohne Zeitraum", von="2026-01-01", bis="2026-12-31")
    with patched_db.begin() as s:
        plan = s.get(Plan, p["id"])
        for feld in ("zeitraum_von", "zeitraum_bis"):
            if fehlend in (feld, "beide"):
                setattr(plan, feld, None)
    result = next(e for e in aufruf(client, "plaene_liste") if e["id"] == p["id"])
    for feld in ("zeitraum_von", "zeitraum_bis"):
        assert result[feld] == (None if fehlend in (feld, "beide") else {"zeitraum_von": "2026-01-01", "zeitraum_bis": "2026-12-31"}[feld])


def test_freizeit_durchstich(client, patched_db):
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    from diakronos_app.models.diakonos import Anmeldung, AnmeldungAntwort
    from diakronos_app.models.kronos import Element
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add(Element(name="freizeit", status="Freigegeben"))
        s.flush()
        for k in ("a", "b"):
            s.add(Anmeldung(name=k, mitglied=k, element="freizeit", status="Bestätigt", anmeldungstyp="Veranstaltung"))
            s.flush()
            s.add(AnmeldungAntwort(name=k, parent=k, parenttype="Anmeldung", parentfield="antworten", feldlabel="rolle", antwort="mitarbeiter"))
    d = kochbuch_laden("freizeit")
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="freizeit", titel="Herbst", von="2026-10-01", bis="2026-10-03",
               parameter={"zeitraum": ["2026-10-01", "2026-10-03"], "thema": "Freude", "veranstaltung": "freizeit"})
    sam = aufruf(client, "sammlung_pflegen", plantyp="freizeit", sammlung="bibelarbeiten", plan=p["id"],
                  eintraege=[{"daten": {"titel": "Thema " + str(i)}, "reihenfolge": i} for i in range(3)])
    aufruf(client, "undo", plan=p["id"])
    assert not aufruf(client, "plan_holen", plan=p["id"])["sammlung_eintraege"]
    sam = aufruf(client, "sammlung_pflegen", plantyp="freizeit", sammlung="bibelarbeiten", plan=p["id"],
                  eintraege=[{"daten": {"titel": "Thema " + str(i)}, "reihenfolge": i} for i in range(3)])
    aufruf(client, "merkmale_pflegen", plantyp="freizeit", plan=p["id"],
           werte=[{"ziel": "sammlung:bibelarbeiten", "schluessel": "stelle", "ziel_id": sam["eintraege"][0]["id"], "wert": "Psalm 1"}])
    aufruf(client, "plan_generieren", plan=p["id"])
    stand = aufruf(client, "plan_holen", plan=p["id"])
    leitungen = [e["wert"] for e in stand["eintraege"] if e["feld_pfad"] == "tagesleitung"]
    assert set(leitungen) == {"a", "b"}
    assert len(stand["termine"]) == 3
    termin = stand["termine"][0]["id"]
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=termin, feld_pfad="tagesleitung", wert="a")
    aufruf(client, "eintrag_loesen", plan=p["id"], termin=termin, feld_pfad="tagesleitung")
    aufruf(client, "veroeffentlichen", plan=p["id"])


@pytest.mark.parametrize("rolle", ["System Manager", "bereich", "plan", "mitglied", "fremd"])
def test_rechte_mit_echter_sitzung(client, patched_db, rolle):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import HasRole
    from diakronos_app.models.diakonos import DienstbereichVerantwortlicher
    stammdaten(patched_db)
    definition = {"schema": "diakronos/plantyp@1", "id": "rechte", "name": "Rechte", "bereich": "Chor",
                  "termine": {"manuell": [{"datum": "2026-01-04"}]}, "felder": [{"id": "leitung", "art": "person"}]}
    aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="rechte", titel="Privat", von="2026-01-01", bis="2026-12-31", verantwortlich="a")
    stand = aufruf(client, "plan_holen", plan=p["id"])
    t = stand["termine"][0]["id"]
    benutzer = "a" if rolle == "plan" else "b" if rolle != "fremd" else "fremd"
    with patched_db.begin() as s:
        if rolle == "System Manager":
            s.add(HasRole(name="sm", parent=benutzer, role="System Manager"))
        if rolle == "bereich":
            s.add(DienstbereichVerantwortlicher(name="bv", parent="Chor", parenttype="Dienstbereich",
                                                parentfield="verantwortliche", user=benutzer))
    def anmelden(user):
        frappe_compat.reset_user()
        sid, csrf = sitzungen.anlegen(user)
        client.cookies.set("sid", sid)
        client.headers["X-Frappe-CSRF-Token"] = csrf
    anmelden(benutzer)
    berechtigt = rolle in ("System Manager", "bereich", "plan")
    assert client.get(PFAD + "plan_holen", params={"plan": p["id"]}).status_code == (200 if berechtigt else 403)
    r = client.post(PFAD + "eintrag_setzen", json={"plan": p["id"], "termin": t, "feld_pfad": "leitung", "wert": benutzer})
    assert r.status_code == (200 if berechtigt else 403)
    r = client.post(PFAD + "plantyp_speichern", json={"definition": definition, "gueltig_ab": "2026-02-01"})
    assert r.status_code == (200 if rolle in ("System Manager", "bereich") else 403)
    assert client.post(PFAD + "abwesenheit_melden", json={"mitglied": benutzer, "von": "2026-03-01", "bis": "2026-03-02"}).status_code == 200
    r = client.post(PFAD + "abwesenheit_melden", json={"mitglied": "a" if benutzer != "a" else "b", "von": "2026-03-01", "bis": "2026-03-02", "plantyp": "rechte"})
    assert r.status_code == (200 if rolle in ("System Manager", "bereich") else 403)
    anmelden("Administrator")
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=t, feld_pfad="leitung", wert=benutzer)
    aufruf(client, "veroeffentlichen", plan=p["id"])
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=t, feld_pfad="leitung", wert="a")
    anmelden(benutzer)
    assert client.get(PFAD + "plan_holen", params={"plan": p["id"]}).status_code == 200
    assert aufruf(client, "meine_dienste")
    if not berechtigt:
        assert aufruf(client, "plan_holen", plan=p["id"])["eintraege"][0]["wert"] == benutzer
