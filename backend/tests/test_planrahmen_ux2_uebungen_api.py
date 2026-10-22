"""UX2 FACH 1 (API/DB): Uebungen vor von Hand festgelegten Singterminen.

Echter Durchstich ueber die HTTP-Dienste: Plan anlegen, einen Singtermin
per ``eintrag_setzen`` fixieren, generieren, danach den Stand lesen. Beweist
den Vorrang ueber die API- und Dienstschicht (nicht nur gegen die Engine).
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
        schema = "pr4_ux2_" + uuid.uuid4().hex
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
        s.add_all([Lied(name=f"lied{i}", titel=f"Lied {i:02d}", aktiv=True) for i in range(40)])


def test_fixierter_singtermin_bekommt_uebungen_davor(client, patched_db):
    """Fixierter Auftritt am So 08.11.2026 erhaelt >= 2 Uebungen davor (API)."""
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    stammdaten(patched_db)
    definition = kochbuch_laden("chorplan")
    definition["termine"] = {"regel": "FREQ=WEEKLY;BYDAY=SU"}
    aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    # Faehigkeiten der Personen pflegen, damit die Rollen besetzt sind.
    werte = [{"ziel": "person", "schluessel": k, "ziel_id": m, "wert": True}
             for m in ("a", "b") for k in ("dirigent", "klavier", "einsingen")]
    aufruf(client, "merkmale_pflegen", plantyp="chorplan", werte=werte)
    p = aufruf(client, "plan_anlegen", plantyp="chorplan", titel="Quartal",
               von="2026-10-01", bis="2026-12-31")
    stand = aufruf(client, "plan_holen", plan=p["id"])
    termin = next(t for t in stand["termine"] if t["datum"] == "2026-11-08")
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=termin["id"],
           feld_pfad="lieder[0]", wert="lied0")
    aufruf(client, "plan_generieren", plan=p["id"])
    stand = aufruf(client, "plan_holen", plan=p["id"])
    daten = {t["id"]: t["datum"] for t in stand["termine"]}
    uebungen = [daten[e["termin"]] for e in stand["eintraege"]
                if e["feld_pfad"].startswith("einueben") and e["wert"] == "lied0"]
    assert len([d for d in uebungen if d < "2026-11-08"]) >= 2, uebungen


def test_zu_knappe_kapazitaet_meldet_ueber_die_api(client, patched_db):
    """Reicht die Kapazitaet nicht, kommt die klare Meldung im Vorschlag an."""
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    stammdaten(patched_db)
    definition = kochbuch_laden("chorplan")
    definition["termine"] = {"regel": "FREQ=WEEKLY;BYDAY=SU"}
    for regel in definition["regeln"]:
        if regel["baustein"] == "vorher_geuebt":
            regel["vorlauf_wochen"] = 1
    aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    aufruf(client, "merkmale_pflegen", plantyp="chorplan",
           werte=[{"ziel": "person", "schluessel": k, "ziel_id": m, "wert": True}
                  for m in ("a", "b") for k in ("dirigent", "klavier", "einsingen")])
    p = aufruf(client, "plan_anlegen", plantyp="chorplan", titel="Quartal",
               von="2026-10-01", bis="2026-12-31")
    stand = aufruf(client, "plan_holen", plan=p["id"])
    termin = next(t for t in stand["termine"] if t["datum"] == "2026-11-08")
    aufruf(client, "eintrag_setzen", plan=p["id"], termin=termin["id"],
           feld_pfad="lieder[0]", wert="lied0")
    erg = aufruf(client, "plan_generieren", plan=p["id"])
    meldungen = [m["meldung"] for m in erg["verstoesse"]
                 if "Uebungsplaetzen" in (m.get("meldung") or "")]
    assert len(meldungen) == 1, erg["verstoesse"]
    assert meldungen[0].startswith("Lied 00 am 08.11.: nur ")
    assert "2026-11-08" not in meldungen[0]
