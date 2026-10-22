"""Dienst-Slices: echte Transaktionen mit isolierter Testdatenbank."""
from datetime import date

import pytest
from sqlalchemy import select

from diakronos_app.models.planrahmen import Eintrag, Termin, Verlauf
from diakronos_app.planrahmen import dienste


def definition():
    return {"schema": "diakronos/plantyp@1", "id": "einfach", "name": "Einfach",
            "termine": {"manuell": [{"datum": "2026-01-04"}, {"datum": "2026-07-05"}]},
            "felder": [{"id": "notiz", "art": "text", "fuellen": "manuell"}]}


def test_version_fixierung_undo(session_factory):
    with session_factory.begin() as s:
        d = dienste.Dienste(s, "Administrator")
        typ = d.plantyp_speichern(definition(), date(2026, 1, 1))
        p = d.plan_anlegen(typ["plantyp"], "Test", date(2026, 1, 1), date(2026, 12, 31))
        ts = s.scalars(select(Termin).where(Termin.plan == p["id"]).order_by(Termin.datum)).all()
        d.eintrag_setzen(p["id"], ts[0].id, "notiz", "eins")
        d.eintrag_setzen(p["id"], ts[0].id, "notiz", "zwei")
        d.undo(p["id"])
        assert s.scalar(select(Eintrag.wert)) == "eins"
        d.undo(p["id"])
        assert s.scalar(select(Eintrag)) is None
        vorher = ts[0].plantyp_version
        neu = definition()
        neu["felder"].append({"id": "zusatz", "art": "text"})
        version = d.plantyp_speichern(neu, date(2026, 7, 1))
        assert ts[0].plantyp_version == vorher
        assert ts[1].plantyp_version == version["id"]
        assert all(v.gruppe_id for v in s.scalars(select(Verlauf)).all())


def test_vorschau_und_veroeffentlichter_stand(session_factory):
    with session_factory.begin() as s:
        d = dienste.Dienste(s, "Administrator")
        typ = d.plantyp_speichern(definition(), date(2026, 1, 1))
        p = d.plan_anlegen(typ["plantyp"], "Test", date(2026, 1, 1), date(2026, 12, 31))
        t = s.scalar(select(Termin).where(Termin.plan == p["id"]))
        d.eintrag_setzen(p["id"], t.id, "notiz", "sichtbar")
        d.veroeffentlichen(p["id"])
        stand = d.plan_holen(p["id"])["veroeffentlichter_stand"]
        d.eintrag_setzen(p["id"], t.id, "notiz", "entwurf")
        assert d.plan_holen(p["id"])["veroeffentlichter_stand"] == stand
        anzahl = len(s.scalars(select(Verlauf)).all())
        d.plan_generieren(p["id"], nur_vorschau=True)
        assert len(s.scalars(select(Verlauf)).all()) == anzahl


def test_fremder_termin_und_unbekannter_pfad(session_factory):
    with session_factory.begin() as s:
        d = dienste.Dienste(s, "Administrator")
        typ = d.plantyp_speichern(definition(), date(2026, 1, 1))
        a = d.plan_anlegen(typ["plantyp"], "A", date(2026, 1, 1), date(2026, 12, 31))
        b = d.plan_anlegen(typ["plantyp"], "B", date(2026, 1, 1), date(2026, 12, 31))
        t = s.scalar(select(Termin).where(Termin.plan == b["id"]))
        with pytest.raises(dienste.DienstFehler):
            d.eintrag_setzen(a["id"], t.id, "notiz", "fremd")
        with pytest.raises(dienste.DienstFehler):
            d.eintrag_setzen(b["id"], t.id, "unbekannt", "falsch")
