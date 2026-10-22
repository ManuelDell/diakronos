"""Reproduktionstests fuer P1-14b (Plaene: Archiv wirksam, Loeschen mit Spur).

Jeder Test gehoert zu genau einem Punkt aus dem Kartenpaket P1-14b
(Quellen: zwei vorausgehende Reviews).
Die Tests sind zuerst ROT (Befund reproduziert) und nach der Behebung GRUEN.

- (1) Archivieren wirkt: ``status='archiviert'`` wird ueberall ausgewertet —
  archivierte Plaene sind fuer Mitglieder nicht in der Planliste und nicht in
  „Meine Dienste“; die Planliste meldet den ECHTEN Status; Planer sehen den
  Archiv-Status in ihrer Ansicht.
- (2) Folgeaenderungen an einem archivierten Plan werden abgelehnt (klare
  Meldung „erst aus dem Archiv holen“) statt den Plan still auf 'entwurf' zu
  setzen.
- (3) ``plan_loeschen`` hinterlaesst eine Audit-Spur (wer/wann/welcher Plan)
  und verlangt die serverseitige Bestaetigung ``bestaetigt=True``.
- (4) ``_daten`` (Abstand) unterscheidet nach PLAN, nicht nach Plantyp: nur
  der EIGENE Plan zaehlt beidseitig, ein ueberlappender Fremdplan nur VOR dem
  Termin.
- KLEIN: ``plan_kopieren`` prueft zusaetzlich das Anlegerecht am Plantyp;
  ``_undo_beschreibung`` kennt die Termin-Aktionen.
"""

from __future__ import annotations

from datetime import date

import pytest

PFAD = "/api/method/diakronos.planrahmen.api."


# ── Geruest (Muster test_p1_14_plaene_vorlagen.py) ─────────────────────────


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


def stammdaten(sf, *benutzer, bereich="Chor"):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Mitglied,
    )
    with sf.begin() as s:
        s.add(Dienstbereich(name=bereich))
        s.add_all([User(name=k, email=k, enabled=True) for k in benutzer])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in benutzer])
        s.add(DienstbereichVerantwortlicher(
            name="bv-" + bereich.lower(), parent=bereich, parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer"))


def _progdefinition(id_="prog-p114b", uhrzeit="17:00"):
    return {
        "schema": "diakronos/plantyp@1", "id": id_, "name": "Programmablauf",
        "bereich": "Chor",
        "termine": {"manuell": [{"datum": "2026-12-06", "uhrzeit": "{parameter.uhrzeit}"}]},
        "parameter": [{"id": "uhrzeit", "art": "text", "name": "Uhrzeit"}],
        "felder": [{
            "id": "ablauf", "art": "ablauf",
            "elemente": [{"typ": "lied", "name": "Lied", "inhalt": [
                {"id": "lied", "art": "eintrag", "sammlung": "lieder"},
            ]}],
        }],
    }


@pytest.fixture()
def planer(client, patched_db):
    stammdaten(patched_db, "planer", "mitglied")
    anmelden(client, "planer")
    return client


@pytest.fixture()
def chorplan(client, patched_db):
    """Ein veroeffentlichter Plan samt Termin und einer Personenzuordnung."""
    stammdaten(patched_db, "planer", "mitglied", bereich="Chor")
    anmelden(client, "planer")
    aufruf(client, "plantyp_speichern", definition=_progdefinition(), gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="prog-p114b", titel="Programm",
               von="2026-12-01", bis="2026-12-31", parameter={"uhrzeit": "17:00"})["id"]
    termin = aufruf(client, "plan_holen", plan=p)["termine"][0]["id"]
    return p, termin


# ── (1) Archivieren wirkt ──────────────────────────────────────────────────


def test_p1_14b_archivierter_plan_verschwindet_fuer_mitglieder(chorplan, client, patched_db):
    """Ein archivierter, veroeffentlichter Plan ist fuer Mitglieder unsichtbar.

    Vorher: ``plaene_liste`` meldete fuer Mitglieder hart ``veroeffentlicht``
    und liess den archivierten Plan stehen — der Aushang „verschwand“ nicht.
    """
    p, _termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    aufruf(client, "plan_archivieren", plan=p)

    # Planer sieht ihn (mit ECHTEM Status) ...
    liste_planer = [x for x in aufruf(client, "plaene_liste") if x["id"] == p]
    assert liste_planer and liste_planer[0]["status"] == "archiviert", liste_planer

    # ... Mitglied sieht ihn gar nicht mehr.
    anmelden(client, "mitglied")
    liste_mitglied = [x for x in aufruf(client, "plaene_liste") if x["id"] == p]
    assert liste_mitglied == [], liste_mitglied


def test_p1_14b_archivierter_plan_meldet_echten_status(chorplan, client, patched_db):
    """Die Planliste eines Mitglieds meldet nicht mehr fest 'veroeffentlicht'.

    Bei einem NICHT archivierten, veroeffentlichten Plan bleibt die Aussage
    'veroeffentlicht' — nur der feste Wert war falsch.
    """
    p, _termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    anmelden(client, "mitglied")
    eintrag = [x for x in aufruf(client, "plaene_liste") if x["id"] == p]
    assert eintrag and eintrag[0]["status"] == "veroeffentlicht", eintrag


def test_p1_14b_archivierter_plan_fehlt_in_meine_dienste(chorplan, client, patched_db):
    """Ein archivierter Plan erscheint nicht mehr unter „Meine Dienste“.

    Vorher speiste ``meine_dienste`` sich allein aus ``veroeffentlichter_stand``
    — ein archivierter Plan lieferte weiter Zuordnungen.
    """
    from diakronos_app.models.planrahmen import Eintrag as PrEintrag, Termin as PrTermin

    p, termin = chorplan
    with patched_db.begin() as s:
        t = s.get(PrTermin, termin)
        s.add(PrEintrag(id="E-DIENST", termin=t.id, feld_pfad="ablauf/0.lied",
                        wert="mitglied", quelle="manuell"))
    aufruf(client, "veroeffentlichen", plan=p)
    anmelden(client, "mitglied")
    vorher = [d for d in aufruf(client, "meine_dienste") if d.get("plan") in (p, None)
              or True]
    assert any(d.get("plan") == p for d in vorher), vorher

    anmelden(client, "planer")
    aufruf(client, "plan_archivieren", plan=p)

    anmelden(client, "mitglied")
    nachher = [d for d in aufruf(client, "meine_dienste") if d.get("plan") == p]
    assert nachher == [], nachher


def test_p1_14b_archivierter_plan_bleibt_fuer_planer_lesbar(chorplan, client, patched_db):
    """Die schreibgeschuetzte Planansicht eines ARCHIVIERTEN Plans liest alles.

    Der Planer muss einen archivierten Plan weiterhin SEHEN koennen — nur so
    erreicht er den Archiv-Hinweis und „Aus dem Archiv holen“. Der
    Archiv-Schreibschutz in ``Dienste._plan`` darf deshalb die reinen
    LESE-Endpunkte (``bedarf``, ``stammdaten_holen``, ``merkmal_kandidaten``)
    nicht treffen. Vorher liefen diese ueber den Vorgabewert
    ``schreiben=True`` und scheiterten mit 417 — die ganze Planansicht brach
    ab (Bedienbefund P1-14b, Browser-Abnahme).
    """
    p, _termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    aufruf(client, "plan_archivieren", plan=p)

    assert aufruf(client, "plan_holen", plan=p)["plan"]["status"] == "archiviert"
    # reine Lesewege muessen gruen bleiben (nicht 417).
    r = client.post(PFAD + "bedarf", json={"plantyp": "prog-p114b", "plan": p})
    assert r.status_code == 200, r.text


# ── (2) Folgeaenderungen an archivierten Plaenen ablehnen ──────────────────


def test_p1_14b_termin_aendern_am_archiv_abgelehnt(chorplan, client):
    """``termin_aendern`` an einem archivierten Plan wird abgelehnt.

    Vorher setzte der Dienst den Status still auf 'entwurf' (entarchivierte
    damit unbemerkt).
    """
    p, termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    aufruf(client, "plan_archivieren", plan=p)
    r = client.post(PFAD + "termin_aendern", json={"plan": p, "termin": termin,
                                                   "titel": "Neu"})
    assert r.status_code == 417, r.text
    # Der Plan bleibt archiviert.
    assert aufruf(client, "plan_holen", plan=p)["plan"]["status"] == "archiviert"


def test_p1_14b_termin_hinzufuegen_am_archiv_abgelehnt(chorplan, client):
    p, _termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    aufruf(client, "plan_archivieren", plan=p)
    r = client.post(PFAD + "termin_hinzufuegen", json={"plan": p, "datum": "2026-12-20"})
    assert r.status_code == 417, r.text
    assert aufruf(client, "plan_holen", plan=p)["plan"]["status"] == "archiviert"


def test_p1_14b_termin_entfernen_am_archiv_abgelehnt(chorplan, client):
    p, termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    aufruf(client, "plan_archivieren", plan=p)
    r = client.post(PFAD + "termin_entfernen", json={"plan": p, "termin": termin})
    assert r.status_code == 417, r.text
    assert aufruf(client, "plan_holen", plan=p)["plan"]["status"] == "archiviert"


def test_p1_14b_plan_aendern_am_archiv_abgelehnt(chorplan, client):
    p, _termin = chorplan
    aufruf(client, "veroeffentlichen", plan=p)
    aufruf(client, "plan_archivieren", plan=p)
    r = client.post(PFAD + "plan_aendern", json={"plan": p, "titel": "Neu"})
    assert r.status_code == 417, r.text
    assert aufruf(client, "plan_holen", plan=p)["plan"]["status"] == "archiviert"


# ── (3) plan_loeschen mit Spur und Bestaetigung ────────────────────────────


def test_p1_14b_plan_loeschen_verlangt_bestaetigung(chorplan, client):
    """Ohne ``bestaetigt=True`` loescht der Dienst nicht (Serverpflicht)."""
    p, _termin = chorplan
    entwurf = aufruf(client, "plan_kopieren", plan=p, titel="Wegwerf")["plan"]
    r = client.post(PFAD + "plan_loeschen", json={"plan": entwurf})
    assert r.status_code == 417, r.text
    # Der Entwurf steht noch.
    assert aufruf(client, "plan_holen", plan=entwurf)["plan"]["id"] == entwurf


def test_p1_14b_plan_loeschen_hinterlaesst_audit_spur(chorplan, client, patched_db):
    """Trotz geloeschtem Plan bleibt eine Spur (wer/wann/welcher Plan).

    ``pr_verlauf`` haengt mit ON DELETE CASCADE am Plan — die Spur darf also
    NICHT plangebunden sein, sonst verschwindet sie mit ihm.
    """
    from sqlalchemy import select
    from diakronos_app.models.planrahmen import Verlauf as PrVerlauf

    p, _termin = chorplan
    titel = aufruf(client, "plan_holen", plan=p)["plan"]["titel"]
    entwurf = aufruf(client, "plan_kopieren", plan=p, titel="Wegwerf")["plan"]
    aufruf(client, "plan_loeschen", plan=entwurf, bestaetigt=True)

    with patched_db.begin() as s:
        spuren = s.scalars(select(PrVerlauf).where(
            PrVerlauf.aktion == "plan_loeschen")).all()
        assert spuren, "Keine Audit-Spur fuer die Loeschung"
        spur = spuren[-1]
        daten = {"benutzer": spur.benutzer, "plan": spur.plan,
                 "zeitpunkt": spur.zeitpunkt, "vorher": dict(spur.vorher or {}),
                 "nachher": dict(spur.nachher or {})}
    assert daten["benutzer"] == "planer", daten
    assert daten["plan"] is None, "Spur haengt am geloeschten Plan und faellt mit ihm"
    assert daten["zeitpunkt"] is not None
    assert "Wegwerf" in str(daten["vorher"]) or "Wegwerf" in str(daten["nachher"]), daten


# ── (4) Abstand je Plan statt je Plantyp ───────────────────────────────────


def _chorplan_historien_test():
    """Chorplan-Definition mit Mindestabstand-Regel (Kochbuch)."""
    from diakronos_app.planrahmen import ressourcen
    return ressourcen.kochbuch_laden("chorplan")


def _liedslot_und_quelle():
    from diakronos_app.planrahmen.engine import InMemoryDatenquelle, Person, Sammlungseintrag
    from diakronos_app.planrahmen.engine.modell import Slot

    quelle = InMemoryDatenquelle(personen_liste=[Person(f"p{i}", name=f"Person {i}")
                                                 for i in range(4)])
    quelle.sammlungen["lieder"] = [Sammlungseintrag("l1", "Lied 1"),
                                   Sammlungseintrag("l2", "Lied 2")]
    slot = Slot("lieder[0]", "eintrag", {"id": "lieder[0]", "art": "eintrag",
                                         "sammlung": "lieder"})
    return slot, quelle


def test_p1_14b_abstand_trennt_eigenen_plan_von_fremdplan():
    """Ein ueberlappender FREMDplan zaehlt nur VOR dem eigenen Termin.

    Vorher unterschied ``_daten`` nach PLANTYP: ein zweiter Plan derselben
    Vorlage zaehlte mit seinen SPAETEREN Terminen beidseitig — obwohl ihn die
    Gemeinde nie gehoert hatte.
    """
    from diakronos_app.planrahmen.engine.datenquelle import Historieneintrag
    from diakronos_app.planrahmen.regeln.auswertung import (
        Kontext, bewerte_alle, index_aufbauen,
    )

    chor = _chorplan_historien_test()
    slot, quelle = _liedslot_und_quelle()
    termin = date(2026, 12, 6)
    from diakronos_app.planrahmen.engine.modell import Termin as ETermin
    etermin = ETermin(termin, "standard")
    regel = next(r for r in chor["regeln"] if r["baustein"] == "mindestabstand")

    # Fremdplan: Termin NACH dem eigenen Termin traegt dasselbe Lied.
    fremd = [Historieneintrag(datum=date(2026, 12, 13), plantyp="chorplan",
                              feld_pfad="lieder[0]", wert="l1", plan="PLAN-FREMD")]
    k = Kontext(chor, etermin, quelle, {}, [], fremd)
    k.eigener_plan = "PLAN-EIGEN"
    index_aufbauen(k)
    assert not bewerte_alle("l1", slot, k, [regel]).meldungen, \
        "Spaeterer Termin eines FREMDplans zaehlt faelschlich als Abstand"

    # Eigener Plan: derselbe Termin (spaeter) zaehlt weiter beidseitig.
    eigen = [Historieneintrag(datum=date(2026, 12, 13), plantyp="chorplan",
                              feld_pfad="lieder[0]", wert="l1", plan="PLAN-EIGEN")]
    k = Kontext(chor, etermin, quelle, {}, [], eigen)
    k.eigener_plan = "PLAN-EIGEN"
    index_aufbauen(k)
    assert bewerte_alle("l1", slot, k, [regel]).meldungen, \
        "Frueherer/spaeterer Termin des EIGENEN Plans ging verloren"
