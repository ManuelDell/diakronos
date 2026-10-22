"""P1-11b — Nacharbeit P1-11: Absage nur fuer die eigene Einteilung,
Regelmeldungen serverseitig filtern (Reparatur-Paket P1-11b).

Reproduziert die beiden MITTLEREN Befunde des vorausgehenden Reviews:

  M2  „Absage in einer Zelle mit MEHREREN Personen darf nur die eigene
      Einteilung entfernen, nie den Dienst der anderen." Der alte Filter in
      ``meine_dienste`` lief ueber ``(termin, feld_pfad)`` gegen ALLE
      Absagen des Plans: stand A und B in derselben Zelle und sagte A ab,
      verschwand der Dienst auch bei B.

  M1  „Regelmeldungen serverseitig filtern": ``veroeffentlichter_stand`` wird
      ueber ``zeile()`` als Snapshot gespeichert und enthaelt die Spalte
      ``meldungen`` (interne Regelpruefungen). Nicht-Bearbeitungsberechtigte
      bekamen sie per ``plan_holen``/``meine_dienste`` unveraendert geliefert;
      das Frontend versteckte sie nur (UXP-R19).

Die Tests sind zuerst rot gelaufen (Filter bzw. Schwärzung fehlten) und
danach gruen. Isolierte In-Memory-SQLite ueber die Standard-Fixtures; kein
Zugriff auf den Betriebs-Stack.
"""

from __future__ import annotations

import pytest

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


def stammdaten(sf):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Mitglied,
    )
    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        s.add_all([User(name=k, email=k, enabled=True)
                   for k in ("planer_chor", "mitglied", "zweites", "dirigent")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in ("planer_chor", "mitglied", "zweites", "dirigent")])
        s.add(DienstbereichVerantwortlicher(
            name="bv-chor", parent="Chor", parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer_chor"))


def chorplan_definition():
    """Chorplan-artiger Plantyp: Lied mit Dirigent/Klavier/Solo."""
    return {
        "schema": "diakronos/plantyp@1", "id": "chor-p111b", "name": "Chorplan",
        "bereich": "Chor",
        "termine": {"manuell": [{"datum": "2026-11-15", "uhrzeit": "10:00:00"}]},
        "felder": [
            {"id": "lieder", "art": "eintrag", "sammlung": "lieder", "name": "Lied",
             "inhalt": [
                 {"id": "dirigent", "art": "person", "name": "Dirigent"},
                 {"id": "klavier", "art": "person", "name": "Klavier"},
                 {"id": "solo", "art": "personen", "name": "Solo", "fuellen": "manuell"},
             ]},
        ],
    }


@pytest.fixture()
def chor_setup(client, patched_db):
    """Plantyp + Plan mit einer Liedzeile, veroeffentlicht.

    Die Zelle ``lieder.solo`` traegt ZWEI Personen (mitglied, zweites) —
    genau der Fall aus Befund M2. Zusaetzlich ist der Dirigent gesetzt.
    """
    from diakronos_app.models.psalmos import Lied
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add(Lied(name="lied-a", titel="Golgatha", aktiv=True, gesangbuch_nummer="129",
                   buch="JN"))
    anmelden(client, "planer_chor")
    aufruf(client, "plantyp_speichern", definition=chorplan_definition(), gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="chor-p111b", titel="Chorplan 2026",
               von="2026-11-01", bis="2026-11-30")["id"]
    plan = aufruf(client, "plan_holen", plan=p)
    termin = plan["termine"][0]["id"]
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder", wert="lied-a")
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.dirigent",
           wert="planer_chor")
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.solo",
           wert=["mitglied", "zweites"])
    aufruf(client, "veroeffentlichen", plan=p)
    return p, termin


# ── M2: Absage trifft nur die eigene Einteilung ────────────────────────────


def test_absage_in_mehrpersonen_zelle_laesst_andere_dienste_stehen(client, chor_setup, patched_db):
    """Befund M2: A und B stehen in ``lieder.solo``; A sagt ab.

    Erwartet: nur A verschwindet aus seiner Sicht — B sieht seinen Dienst
    unveraendert weiter. Vorher (Filter ueber den ganzen Plan) verschwand
    der Dienst auch bei B.
    """
    plan, termin = chor_setup

    anmelden(client, "mitglied")
    assert len(aufruf(client, "meine_dienste")) == 1
    aufruf(client, "dienst_absagen", plan=plan, termin=termin, feld_pfad="lieder.solo")
    assert aufruf(client, "meine_dienste") == []          # A ist raus

    # B steht weiter in derselben Zelle und muss seinen Dienst noch sehen.
    anmelden(client, "zweites")
    dienste = aufruf(client, "meine_dienste")
    assert [d["feld_pfad"] for d in dienste] == ["lieder.solo"], dienste

    # Und der Entwurfseintrag traegt weiterhin B (nicht geleert).
    from sqlalchemy import select
    from diakronos_app.models.planrahmen import Eintrag, Termin
    with patched_db() as s:
        e = s.scalar(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == plan, Eintrag.feld_pfad == "lieder.solo"))
        assert e.wert == ["zweites"]


def test_absage_verschwindet_auch_bei_dritter_person_nicht(client, chor_setup):
    """Befund M2, zweite Auspraegung: drei Personen in der Zelle, EINE sagt ab.

    Die uebrigen zwei muessen ihren Dienst weiter sehen.
    """
    plan, termin = chor_setup
    aufruf(client, "plan_holen", plan=plan)  # Planer-Sicht (liest Entwurf)
    # Dritte Person in dieselbe Zelle aufnehmen (Planer-Editor).
    anmelden(client, "planer_chor")
    aufruf(client, "eintrag_setzen", plan=plan, termin=termin, feld_pfad="lieder.solo",
           wert=["mitglied", "zweites", "dirigent"])
    aufruf(client, "veroeffentlichen", plan=plan)

    anmelden(client, "mitglied")
    aufruf(client, "dienst_absagen", plan=plan, termin=termin, feld_pfad="lieder.solo")

    for benutzer in ("zweites", "dirigent"):
        anmelden(client, benutzer)
        assert [d["feld_pfad"] for d in aufruf(client, "meine_dienste")] == ["lieder.solo"], benutzer


def test_absage_in_einzelzelle_bleibt_wirksam(client, chor_setup):
    """Gegenprobe: Einzelbesetzte Zelle — nach der Absage sieht niemand mehr
    den Dienst (der Regressionstest darf die Wirkung nicht aufheben)."""
    plan, termin = chor_setup
    anmelden(client, "planer_chor")
    aufruf(client, "eintrag_setzen", plan=plan, termin=termin, feld_pfad="lieder.dirigent",
           wert="mitglied")
    aufruf(client, "veroeffentlichen", plan=plan)

    anmelden(client, "mitglied")
    aufruf(client, "dienst_absagen", plan=plan, termin=termin, feld_pfad="lieder.dirigent")
    assert [d["feld_pfad"] for d in aufruf(client, "meine_dienste")] == ["lieder.solo"]


# ── M1: Regelmeldungen nur fuer Bearbeitungsberechtigte ────────────────────


def test_plan_holen_ohne_bearbeitungsrecht_enthaelt_keine_meldungen(client, chor_setup, patched_db):
    """Befund M1: der veroeffentlichte Stand fuer Mitglieder traegt in den
    Eintraegen KEINE Regel-``meldungen`` (internes Planerwissen, UXP-R19)."""
    from sqlalchemy import select
    from diakronos_app.models.planrahmen import Eintrag, Termin
    plan, termin = chor_setup

    # Regelmeldung am Eintrag erzeugen (interne Sicht des Planers).
    anmelden(client, "planer_chor")
    aufruf(client, "eintrag_setzen", plan=plan, termin=termin, feld_pfad="lieder.solo",
           wert=["mitglied", "zweites"])
    with patched_db.begin() as s:
        e = s.scalar(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == plan, Eintrag.feld_pfad == "lieder.solo"))
        e.meldungen = [{"stufe": "sollte", "code": "probe.meldung",
                        "meldung": "Interne Regelpruefung"}]
    aufruf(client, "veroeffentlichen", plan=plan)

    # Planer sieht die Meldung (Gegenprobe: Filtern duerfen wir nicht alles).
    anmelden(client, "planer_chor")
    planer = aufruf(client, "plan_holen", plan=plan)
    assert planer["darf_bearbeiten"] is True
    assert any(e.get("meldungen") for e in planer["eintraege"]), planer["eintraege"]

    # Mitglied sieht denselben Eintrag — ohne meldungen.
    anmelden(client, "mitglied")
    mitglied = aufruf(client, "plan_holen", plan=plan)
    assert mitglied["darf_bearbeiten"] is False
    assert mitglied["eintraege"], "Eintraege muessen sichtbar bleiben"
    for e in mitglied["eintraege"]:
        assert not e.get("meldungen"), f"meldungen lecken: {e}"


def test_meine_dienste_enthaelt_keine_meldungen(client, chor_setup, patched_db):
    """Befund M1 fuer die Mitglieder-Sicht (OP-CHOR-7)."""
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    for d in aufruf(client, "meine_dienste"):
        assert "meldungen" not in d, d


def test_veroeffentlichten_stand_nach_veroeffentlichen_ohne_meldungen(client, chor_setup, patched_db):
    """Befund M1 an der Wurzel: der Snapshot selbst traegt keine
    Regel-``meldungen`` mehr — sonst waere der Leak nur an einer Stelle
    zugedeckt und die naechste Ansicht leckt wieder."""
    from sqlalchemy import select
    from diakronos_app.models.planrahmen import Eintrag, Termin
    plan, termin = chor_setup
    anmelden(client, "planer_chor")
    with patched_db.begin() as s:
        e = s.scalar(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == plan, Eintrag.feld_pfad == "lieder.solo"))
        e.meldungen = [{"stufe": "sollte", "code": "probe", "meldung": "intern"}]
    aufruf(client, "veroeffentlichen", plan=plan)

    from diakronos_app.models.planrahmen import Plan
    with patched_db() as s:
        p = s.get(Plan, plan)
        assert p.veroeffentlichter_stand is not None
        for e in p.veroeffentlichter_stand["eintraege"]:
            assert not e.get("meldungen"), e
