"""P1-11 — Plaene: Mitglieder-Sicht und Weitergabe (Reparatur-Paket P1-11).

Deckt die Befunde ab:
  UXP-R2    `einrichten_rechte` fuer Mitglieder (403) — die UI faengt es ab und
            zeigt die veroeffentlichten Plaene; der Server bleibt fail-closed.
  UXP-R19   Regelpruefung ist internes Planerwissen (UI-Anteil).
  UXP-R15   Plan-Tabelle mobil (UI-Anteil, Node-Test).
  OP-HANDY-5 Dashboard-Kachel (UI-Anteil, aus beiden Quellen).
  UXP-R17   Abwesenheiten lesen/loeschen.
  OP-HANDY-18 Eigene Einteilung absagen + Konfliktmarkierung.
  OP-CHOR-7 Lied-Titel, Uhrzeit und Mitwirkende in „Meine Dienste".

Die Tests sind zuerst rot gelaufen (die neuen Endpunkte fehlten) und danach
gruen. Isolierte In-Memory-SQLite ueber die Standard-Fixtures; kein Zugriff
auf den Betriebs-Stack.
"""

from __future__ import annotations

import pytest

PFAD = "/api/method/diakronos.planrahmen.api."


# ── Geruest (Muster test_planrahmen_ui1.py) ────────────────────────────────


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
                   for k in ("planer_chor", "mitglied", "dirigent")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in ("planer_chor", "mitglied", "dirigent")])
        s.add(DienstbereichVerantwortlicher(
            name="bv-chor", parent="Chor", parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer_chor"))


def chorplan_definition():
    """Chorplan-artiger Plantyp: Lied mit Dirigent/Klavier/Solo (OP-CHOR-7)."""
    return {
        "schema": "diakronos/plantyp@1", "id": "chor-p111", "name": "Chorplan",
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
    """Plantyp + Plan mit einem Lied, Solo fuer das Mitglied, veroeffentlicht."""
    from diakronos_app.models.psalmos import Lied
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add_all([Lied(name="lied-a", titel="Golgatha", aktiv=True, gesangbuch_nummer="129",
                        buch="JN"),
                   Lied(name="lied-b", titel="Nun danket", aktiv=True, gesangbuch_nummer="17",
                        buch="JN")])
    anmelden(client, "planer_chor")
    aufruf(client, "plantyp_speichern", definition=chorplan_definition(), gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="chor-p111", titel="Chorplan 2026",
               von="2026-11-01", bis="2026-11-30")["id"]
    plan = aufruf(client, "plan_holen", plan=p)
    termin = plan["termine"][0]["id"]
    # Lied + Dirigent + Solo eintragen (Lied stammt aus dem Psalmos-Katalog).
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder", wert="lied-a")
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.dirigent",
           wert="planer_chor")
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.solo",
           wert=["mitglied", "dirigent"])
    aufruf(client, "veroeffentlichen", plan=p)
    return p, termin


# ── UXP-R2: einrichten_rechte bleibt fail-closed, Plaene bleiben lesbar ─────


def test_einrichten_rechte_403_fuer_mitglied_ohne_verantwortung(client, patched_db):
    stammdaten(patched_db)
    anmelden(client, "mitglied")
    r = client.post(PFAD + "einrichten_rechte", json={})
    assert r.status_code == 403


def test_plaene_liste_liefert_veroeffentlichten_plan_trotz_403_einrichten(client, chor_setup):
    """Kern von UXP-R2: der Berechtigungsfehler beim Einrichten darf die
    Planliste nicht verhindern — plaene_liste liefert den veroeffentlichten Plan."""
    anmelden(client, "mitglied")
    assert client.post(PFAD + "einrichten_rechte", json={}).status_code == 403
    plaene = aufruf(client, "plaene_liste")
    assert [p["titel"] for p in plaene] == ["Chorplan 2026"]
    assert plaene[0]["status"] == "veroeffentlicht"
    assert plaene[0]["darf_bearbeiten"] is False


# ── OP-CHOR-7: Lied, Uhrzeit, Mitwirkende in „Meine Dienste" ───────────────


def test_meine_dienste_zeigt_lied_uhrzeit_und_mitwirkende(client, chor_setup):
    anmelden(client, "mitglied")
    dienste = aufruf(client, "meine_dienste")
    solo = [d for d in dienste if d["feld_pfad"] == "lieder.solo"]
    assert len(solo) == 1
    d = solo[0]
    assert d["uhrzeit"] == "10:00:00"
    assert d["termin_id"]
    # Lied-Titel aus der Lied-Sammlung, nicht der Rohwert (Psalmos-Katalog).
    assert d["lied_titel"] == "Golgatha"
    namen = {m["name"] for m in d["mitwirkende"]}
    assert "Planer_chor Test" in namen          # Dirigent
    assert all(m["rolle"] for m in d["mitwirkende"])


def test_meine_dienste_nur_eigenes_mitglied(client, chor_setup):
    """Kein Fremdzugriff: der Dirigent sieht seine Einteilung, das Mitglied nur seine."""
    anmelden(client, "dirigent")
    dienste = aufruf(client, "meine_dienste")
    pfade = {d["feld_pfad"] for d in dienste}
    assert pfade == {"lieder.solo"}   # nur das eigene Solo, nicht der Dirigent-Eintrag


# ── OP-HANDY-18: eigene Einteilung absagen + Konfliktmarkierung ────────────


def test_dienst_absagen_gibt_platz_frei(client, chor_setup, patched_db):
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    aufruf(client, "dienst_absagen", plan=plan, termin=termin, feld_pfad="lieder.solo")
    from sqlalchemy import select
    from diakronos_app.models.planrahmen import Eintrag, Termin
    with patched_db() as s:
        e = s.scalar(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == plan, Eintrag.feld_pfad == "lieder.solo"))
        assert e.wert == ["dirigent"]        # nur das eigene Mitglied entfernt
        assert e.quelle == "abgesagt"
    # Danach: keine eigene Zuordnung mehr sichtbar.
    assert aufruf(client, "meine_dienste") == []


def test_dienst_absagen_verweigert_fremde_einteilung(client, chor_setup):
    """Wer nicht selbst eingeteilt ist, kann die Einteilung nicht absagen."""
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    # „mitglied" steht nicht auf lieder.dirigent (dort planer_chor) — der
    # Server muss die Absage verweigern, statt fremde Einteilungen zu leeren.
    r = client.post(PFAD + "dienst_absagen",
                    json={"plan": plan, "termin": termin, "feld_pfad": "lieder.dirigent"})
    assert r.status_code == 403


def test_meine_dienste_markiert_abwesenheitskonflikt(client, chor_setup):
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    assert aufruf(client, "meine_dienste")[0]["abwesend"] is False
    aufruf(client, "abwesenheit_melden", mitglied="mitglied",
           von="2026-11-10", bis="2026-11-20")
    assert aufruf(client, "meine_dienste")[0]["abwesend"] is True


# ── UXP-R17: Abwesenheiten lesen und loeschen ──────────────────────────────


def test_abwesenheiten_liste_und_loeschen(client, chor_setup, patched_db):
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    gemeldet = aufruf(client, "abwesenheit_melden", mitglied="mitglied",
                      von="2026-11-10", bis="2026-11-20", grund="Urlaub")
    assert gemeldet["abwesenheit"]["grund"] == "Urlaub"

    liste = aufruf(client, "abwesenheiten_liste")
    assert len(liste) == 1
    assert liste[0]["von"] == "2026-11-10" and liste[0]["bis"] == "2026-11-20"
    assert liste[0]["id"]

    aufruf(client, "abwesenheit_loeschen", abwesenheit=liste[0]["id"])
    assert aufruf(client, "abwesenheiten_liste") == []


def test_abwesenheiten_liste_fremd_verweigert(client, chor_setup):
    """Ein Mitglied darf fremde Abwesenheiten weder lesen noch loeschen."""
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    aufruf(client, "abwesenheit_melden", mitglied="mitglied",
           von="2026-11-10", bis="2026-11-20")
    anmelden(client, "dirigent")
    r = client.post(PFAD + "abwesenheiten_liste", json={"mitglied": "mitglied"})
    assert r.status_code in (403, 417)


def test_abwesenheit_loeschen_fremd_verweigert(client, chor_setup):
    plan, termin = chor_setup
    anmelden(client, "mitglied")
    gemeldet = aufruf(client, "abwesenheit_melden", mitglied="mitglied",
                      von="2026-11-10", bis="2026-11-20")
    anmelden(client, "dirigent")
    r = client.post(PFAD + "abwesenheit_loeschen",
                    json={"abwesenheit": gemeldet["abwesenheit"]["id"]})
    assert r.status_code in (403, 417)
    anmelden(client, "mitglied")
    assert len(aufruf(client, "abwesenheiten_liste")) == 1
