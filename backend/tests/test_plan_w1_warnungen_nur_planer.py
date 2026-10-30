"""PLAN-W1 — Prüf-Warnungen in Plänen nur für Planer (Befund DMB-7d8e3068c388).

Manuel 2026-10-23: „Nur für Planer“. Wer den Plan BEARBEITEN darf, sieht die
Regelprüfung (PrMeldungen); reine Betrachter sehen sie NIE.

Vorher galt das nur in der Oberfläche (Plan.vue blendete den Warnblock aus).
Die eigentliche Prüf-Meldung hing aber an der Zeile des EINTRAGS
(``Eintrag.meldungen``) und wurde im selben ``eintraege``-Feld ausgeliefert wie
der Wert — ein Betrachter bekam sie also im Datenstrom des veröffentlichten
Stands. Diese Datei hält die Server-Seite fest:

  * Betrachter (Mitglied, kein Bearbeitungsrecht): ``plan_holen`` liefert
    keinen einzigen Eintrag mit ``meldungen``/``bewertung`` — weder im Entwurf
    noch in einem lange veröffentlichten Stand, dessen Snapshot die Spalte
    noch trägt.
  * Planer: die Warnungen kommen unverändert an (Grundlage des Warnblocks).

Isolierte In-Memory-SQLite über die Standard-Fixtures; kein Zugriff auf den
Betriebs-Stack.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

PFAD = "/api/method/diakronos.planrahmen.api."


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
                   for k in ("planer_chor", "mitglied")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in ("planer_chor", "mitglied")])
        s.add(DienstbereichVerantwortlicher(
            name="bv-chor", parent="Chor", parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer_chor"))


def warnplan_definition():
    """Zwei Termine, ein „muss"-Feld, das nie besetzt wird.

    Die Regel ``abwesenheit_beachten`` schlägt damit an jedem Termin an — es
    entsteht genau eine Warnung je Eintrag, die nur Planer sehen dürfen.
    """
    return {
        "schema": "diakronos/plantyp@1", "id": "warn-pw1", "name": "Warnplan",
        "bereich": "Chor",
        "termine": {"manuell": [{"datum": "2026-05-03"}, {"datum": "2026-05-10"}]},
        "regeln": [{"baustein": "abwesenheit_beachten", "stufe": "muss"}],
        "felder": [
            {"id": "leitung", "art": "person", "rolle": {"person": "mitglied"}},
        ],
    }


@pytest.fixture()
def warn_setup(client, patched_db):
    """Plan mit zwei eingetragenen Diensten — den einen absichtlich in der
    Abwesenheit des Mitglieds, damit die Regel wirklich meldet.

    Die Abwesenheit meldet das Mitglied selbst (Planer-Fremdmeldung
    verlangte Bereichsverantwortung und machte "mitglied" zum Planer).
    """
    stammdaten(patched_db)
    # Die Abwesenheit meldet das MITGLIED SELBST — als Planer waere sie eine
    # fremde und verlangte Bereichsverantwortung (die hier bewusst nicht
    # gesetzt ist, sonst waere "mitglied" selbst Planer).
    anmelden(client, "mitglied")
    aufruf(client, "abwesenheit_melden", mitglied="mitglied", von="2026-05-01", bis="2026-05-05")
    anmelden(client, "planer_chor")
    aufruf(client, "plantyp_speichern", definition=warnplan_definition(), gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="warn-pw1", titel="Warnplan 2026",
               von="2026-05-01", bis="2026-05-31")["id"]
    termine = [t["id"] for t in aufruf(client, "plan_holen", plan=p)["termine"]]
    for t in termine:
        aufruf(client, "eintrag_setzen", plan=p, termin=t, feld_pfad="leitung", wert="mitglied")
    stand = aufruf(client, "plan_holen", plan=p)
    assert any(e.get("meldungen") for e in stand["eintraege"]), \
        "Gerüst: die Regelprüfung muss für den Planer Meldungen erzeugen"
    # Betrachter sehen nur den VEROEFFENTLICHTEN Stand. Ohne diese Zeile
    # liefe jeder Betrachter-Test in ein 403 statt in eine echte Pruefung.
    aufruf(client, "veroeffentlichen", plan=p)
    return p


def meldungs_eintraege(stand):
    return [e for e in stand.get("eintraege", ()) if e.get("meldungen")]


def snapshot(p_id):
    """Frisch aus der DB gelesener Veroeffentlichungs-Stand (ohne ORM-Cache)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.planrahmen import Plan
    with SessionLocal.begin() as s:
        return deepcopy(s.get(Plan, p_id).veroeffentlichter_stand)


# ── Betrachter: keine Prüf-Warnungen, nirgends im Datenstrom ───────────────


def test_planer_sieht_pruef_meldungen(client, warn_setup):
    """Gegenprobe: der Planer bekommt die Meldungen (Grundlage des Warnblocks)."""
    stand = aufruf(client, "plan_holen", plan=warn_setup)
    assert stand["darf_bearbeiten"] is True
    assert meldungs_eintraege(stand), "Planer ohne Prüf-Meldungen"


def test_betrachter_sieht_keine_pruef_meldungen(client, warn_setup):
    anmelden(client, "mitglied")
    stand = aufruf(client, "plan_holen", plan=warn_setup)
    assert stand["darf_bearbeiten"] is False
    assert meldungs_eintraege(stand) == []
    assert "meldungen" not in repr(stand), \
        "Prüf-Warnungen stecken noch irgendwo im Betrachter-Stand"


def test_veroeffentlichung_schwaerzt_snapshot_an_der_wurzel(client, warn_setup):
    """Nicht nur die Auslieferung, auch der GESPEICHERTE Stand ist sauber.

    Sonst läge die Regelprüfung in jeder Zukunfts-Auslieferung des Snapshots,
    die ``plan_holen`` nicht kennt — der Befund käme beim nächsten Umbau
    zurück.
    """
    stand = snapshot(warn_setup)
    assert stand["eintraege"]
    assert meldungs_eintraege(stand) == []
    assert "bewertung" not in repr(stand), "Bewertungsspur im gespeicherten Stand"


def test_betrachter_sieht_keine_meldungen_im_veroeffentlichten_stand(client, warn_setup):
    """Auch ein Stand, dessen Snapshot die Spalte noch trägt, bleibt sauber."""
    aufruf(client, "veroeffentlichen", plan=warn_setup)
    anmelden(client, "planer_chor")
    p = aufruf(client, "plan_holen", plan=warn_setup)
    assert {e["id"] for e in p["eintraege"]}
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.planrahmen import Plan
    with SessionLocal.begin() as s:
        plan = s.get(Plan, warn_setup)
        stand = deepcopy(plan.veroeffentlichter_stand)
        for e in stand["eintraege"]:
            e["meldungen"] = [{"stufe": "muss", "meldung": "Altlast aus dem Snapshot"}]
            e["bewertung"] = {"zulaessig": False}
        plan.veroeffentlichter_stand = stand
    anmelden(client, "mitglied")
    stand = aufruf(client, "plan_holen", plan=warn_setup)
    assert meldungs_eintraege(stand) == []
    assert "Altlast" not in repr(stand)


@pytest.mark.parametrize("benutzer", ["planer_chor"])
def test_planer_sieht_meldungen_im_snapshot(client, warn_setup, benutzer):
    """Der Planer liest den Entwurf (mit Meldungen) — der Snapshot selbst
    bleibt sauber, damit kein Betrachter-Weg ihn je traegt."""
    anmelden(client, benutzer)
    stand = aufruf(client, "plan_holen", plan=warn_setup)
    assert stand["darf_bearbeiten"] is True
    assert meldungs_eintraege(stand), "Planer ohne Meldungen im Entwurf"
    assert meldungs_eintraege(snapshot(warn_setup)) == []


@pytest.mark.parametrize("benutzer", ["mitglied"])
def test_betrachter_sieht_warnungen_auch_nicht_ueber_termin_strukturen(client, warn_setup, benutzer):
    """Der zweite Weg zu denselben Zeilen (termin_strukturen) bleibt ebenso sauber."""
    anmelden(client, benutzer)
    strukturen = aufruf(client, "termin_strukturen", plan=warn_setup)["strukturen"]
    assert strukturen
    assert "meldungen" not in repr(strukturen) and "Altlast" not in repr(strukturen)
