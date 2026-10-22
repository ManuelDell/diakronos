"""BF1d K1: Entfernte leere Felder sind keine Wertänderung."""
from copy import deepcopy

from test_bf1_livetest import plan_aufruf


def test_entfernter_leerer_schluessel_erzeugt_keine_null_zu_null_zeile(client, patched_db):
    from diakronos_app.models.diakonos import Dienstbereich
    from diakronos_app.models.planrahmen import Plan
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden

    with patched_db.begin() as s:
        s.add(Dienstbereich(name="Chor"))
    plan_aufruf(client, "plantyp_speichern", definition=kochbuch_laden("chorplan"), gueltig_ab="2026-01-01")
    p = plan_aufruf(client, "plan_anlegen", plantyp="chorplan", titel="Leerer Plan", von="2026-01-01", bis="2026-12-31")
    erste = plan_aufruf(client, "veroeffentlichen", plan=p["id"])
    assert erste["erstveroeffentlichung"] is True
    assert erste["diff"] == []
    with patched_db.begin() as s:
        plan = s.get(Plan, p["id"])
        stand = deepcopy(plan.veroeffentlichter_stand)
        stand["eintraege"].append({"termin": "entfernt", "feld_pfad": "leer", "wert": None})
        plan.veroeffentlichter_stand = stand
    zweite = plan_aufruf(client, "veroeffentlichen", plan=p["id"])
    assert zweite["erstveroeffentlichung"] is False
    assert zweite["diff"] == []
