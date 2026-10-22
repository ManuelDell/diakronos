"""UX2 FACH 2: optionalen Mehrfachplatz vor dem Generieren anlegen.

Der Server legt den naechsten freien Platz ``<feld>[n]`` an (leer, von Hand
festgelegt). Danach ist er ueber ``eintrag_setzen`` normal bearbeitbar,
ueberlebt die Generierung und laesst sich per Undo zuruecknehmen.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from diakronos_app.models.base import Base

PFAD = "/api/method/diakronos.planrahmen.api."


@pytest.fixture()
def engine():
    if os.environ.get("PLANRAHMEN_DISPOSABLE_DB") == "1":
        url = os.environ["DATABASE_URL"]
        assert "wegwerf-postgres-test" in url and url.endswith("/wegwerf")
        admin = create_engine(url)
        schema = "pr4_ux2b_" + uuid.uuid4().hex
        with admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        eng = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        admin = None
        eng = create_engine("sqlite+pysqlite:///:memory:",
                            connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import diakronos_app.models
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    if admin:
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def fehler(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 417, r.text
    return r.json()["meldungen"]


def stammdaten(sf):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Dienstbereich, Gruppe, Gruppenmitgliedschaft, Mitglied
    from diakronos_app.models.psalmos import Lied
    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        s.add_all([User(name=k, email=k, enabled=True) for k in ("a", "b")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k) for k in ("a", "b")])
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add_all([Gruppenmitgliedschaft(name=k, parent="Chor", parenttype="Gruppe",
                                         parentfield="mitglieder", mitglied=k, status="Aktiv")
                   for k in ("a", "b")])
        s.add_all([Lied(name=f"lied{i}", titel=f"Lied {i:02d}", aktiv=True) for i in range(6)])


def _plan_mit_termin(client, patched_db):
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    stammdaten(patched_db)
    definition = kochbuch_laden("chorplan")
    aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="chorplan", titel="Quartal",
               von="2026-10-01", bis="2026-12-31")
    stand = aufruf(client, "plan_holen", plan=p["id"])
    return p["id"], stand["termine"][0]


def test_platz_hinzufuegen_macht_leeres_optionales_feld_waehlbar(client, patched_db):
    pid, termin = _plan_mit_termin(client, patched_db)
    struktur = aufruf(client, "termin_struktur", plan=pid, termin=termin["id"])
    assert not [s for s in struktur["slots"] if s["feld_pfad"].startswith("einueben")]
    erg = aufruf(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="einueben")
    assert erg["feld_pfad"] == "einueben[0]"
    assert erg["gruppe_id"]
    struktur = aufruf(client, "termin_struktur", plan=pid, termin=termin["id"])
    slots = [s for s in struktur["slots"] if s["feld_pfad"] == "einueben[0]"]
    assert slots and slots[0]["art"] == "eintrag"
    # Danach normal bearbeitbar.
    aufruf(client, "eintrag_setzen", plan=pid, termin=termin["id"],
           feld_pfad="einueben[0]", wert="lied0")
    stand = aufruf(client, "plan_holen", plan=pid)
    e = next(e for e in stand["eintraege"]
             if e["termin"] == termin["id"] and e["feld_pfad"] == "einueben[0]")
    assert e["wert"] == "lied0" and e["fixiert"]


def test_platz_hinzufuegen_erzwingt_obergrenze(client, patched_db):
    pid, termin = _plan_mit_termin(client, patched_db)
    aufruf(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="einueben")
    aufruf(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="einueben")
    meldungen = fehler(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="einueben")
    assert "Höchstens 2" in meldungen[0]["meldung"], meldungen


def test_platz_hinzufuegen_nur_fuer_mehrfachfelder(client, patched_db):
    pid, termin = _plan_mit_termin(client, patched_db)
    # 'lieder' hat anzahl 3 (fest) -> keine zusaetzlichen Plaetze.
    meldungen = fehler(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="lieder")
    assert meldungen and meldungen[0]["pfad"] == "/feld_pfad"


def test_platz_hinzufuegen_ist_undo_faehig(client, patched_db):
    pid, termin = _plan_mit_termin(client, patched_db)
    aufruf(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="einueben")
    aufruf(client, "undo", plan=pid)
    stand = aufruf(client, "plan_holen", plan=pid)
    assert not [e for e in stand["eintraege"]
                if e["termin"] == termin["id"] and e["feld_pfad"] == "einueben[0]"]


def test_platz_hinzufuegen_ueberlebt_die_generierung(client, patched_db):
    pid, termin = _plan_mit_termin(client, patched_db)
    aufruf(client, "platz_hinzufuegen", plan=pid, termin=termin["id"], feld_pfad="einueben")
    aufruf(client, "eintrag_setzen", plan=pid, termin=termin["id"],
           feld_pfad="einueben[0]", wert="lied0")
    aufruf(client, "plan_generieren", plan=pid)
    stand = aufruf(client, "plan_holen", plan=pid)
    e = next(e for e in stand["eintraege"]
             if e["termin"] == termin["id"] and e["feld_pfad"] == "einueben[0]")
    assert e["wert"] == "lied0" and e["fixiert"]


def test_platz_hinzufuegen_verlangt_planbearbeitungsrecht(client, patched_db, monkeypatch):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    pid, termin = _plan_mit_termin(client, patched_db)
    # Ein existierendes, aktives Fremdkonto: sonst prüft der Test nur die
    # abgelaufene Sitzung (401), nicht das fehlende Planbearbeitungsrecht (403).
    from diakronos_app.models.core import User
    with patched_db.begin() as s:
        s.add(User(name="fremd", email="fremd@example.invalid", enabled=True))
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen("fremd")
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf
    r = client.post(PFAD + "platz_hinzufuegen",
                    json={"plan": pid, "termin": termin["id"], "feld_pfad": "einueben"})
    assert r.status_code == 403, r.text
