"""Review-Regressionsfaelle: wirksame Ressourcenwerte und Absagen."""
import pytest
from sqlalchemy import select

from diakronos_app.models.core import HasRole, User
from diakronos_app.models.kronos import Element, ElementAenderung, ElementRessource
from test_p2_4b_benachrichtigungen import (
    _moderator_welt, _notifications, _speichere_termin, anmelden,
)

API = "/api/method/diakronos.kronos.api.event_crud."


def speichern(client, zeilen):
    return _speichere_termin(client, element_name="Gottesdienst",
        element_start="2026-12-06 10:00:00", element_end="2026-12-06 11:00:00",
        zusaetzliche_ressourcen=zeilen)


def test_zusatzressource_wirksame_aenderung(client, patched_db):
    _moderator_welt(patched_db)
    anmelden(client, "moderator")
    speichern(client, [{"freitext_ressource": "Anderer Veranstaltungsort"}])
    with patched_db() as s:
        assert s.scalar(select(ElementRessource.freitext_ressource)) == "Anderer Veranstaltungsort"
    assert len(_notifications(patched_db, "talente")) == 1
    # Zeilen-IDs/Sortierung/Leerraum/Notiz sind keine Ortsaenderung.
    speichern(client, [{"name": "andere-id", "idx": 9,
                       "freitext_ressource": " Anderer Veranstaltungsort ", "notiz": "neu"}])
    assert len(_notifications(patched_db, "talente")) == 1
    speichern(client, [])
    assert len(_notifications(patched_db, "talente")) == 2


def test_zusatzressource_wartend_erst_freigabe(client, patched_db):
    _moderator_welt(patched_db)
    with patched_db.begin() as s:
        s.add(User(name="schreiber", email="schreiber", enabled=True))
        s.add(HasRole(name="r-sch", parent="schreiber", parenttype="User",
                      parentfield="roles", role="Mitglied"))
    anmelden(client, "schreiber")
    speichern(client, [{"freitext_ressource": "Neuer Ort"}])
    with patched_db() as s:
        assert not s.scalar(select(ElementRessource.name))
        vorschlag = s.scalar(select(ElementAenderung.name))
    assert _notifications(patched_db, "talente") == []
    anmelden(client, "moderator")
    r = client.post(API + "aenderung_freigeben", json={"name": vorschlag})
    assert r.status_code == 200, r.text
    with patched_db() as s:
        assert s.scalar(select(ElementRessource.freitext_ressource)) == "Neuer Ort"
    assert len(_notifications(patched_db, "talente")) == 1


@pytest.mark.parametrize("fall,anzahl", [("festgelegt", 1), ("entwurf", 0),
                                        ("ohne_leserecht", 0), ("fehler", 0)])
def test_absage_beim_loeschen(client, patched_db, monkeypatch, fall, anzahl):
    _moderator_welt(patched_db)
    with patched_db.begin() as s:
        if fall == "entwurf":
            s.get(Element, "E-1").status = "Vorschlag"
        if fall == "ohne_leserecht":
            # Schreibrecht beinhaltet Lesen; nur den Leserollen-Eintrag zu
            # entfernen reicht in dieser Welt (Mitglied darf schreiben) nicht.
            s.delete(s.get(HasRole, "r-tal"))
    anmelden(client, "moderator")
    if fall == "fehler":
        from diakronos_app.api.kronos import event_crud
        def scheitert(*args, **kwargs):
            raise ValueError("Loeschen fehlgeschlagen")
        monkeypatch.setattr(event_crud, "_delete_doc", scheitert)
    r = client.post(API + "delete_event", json={"name": "E-1"})
    assert (r.status_code == 200) == (fall != "fehler"), r.text
    with patched_db() as s:
        assert (s.get(Element, "E-1") is None) == (fall != "fehler")
    nachrichten = _notifications(patched_db, "talente")
    assert len(nachrichten) == anzahl
    if anzahl:
        assert "abgesagt" in nachrichten[0].lower()
        assert "Gottesdienst" in nachrichten[0]


def test_fehlgeschlagene_kindschreibung_meldet_nichts(client, patched_db, monkeypatch):
    _moderator_welt(patched_db)
    anmelden(client, "moderator")
    from diakronos_app.api.kronos import event_crud
    def scheitert(*args, **kwargs):
        raise ValueError("Kindschreibung fehlgeschlagen")
    monkeypatch.setattr(event_crud, "_apply_additional_resources", scheitert)
    r = client.post(API + "save_event", json={"name": "E-1", "element_name": "Gottesdienst",
        "element_start": "2026-12-06 10:00:00", "element_end": "2026-12-06 11:00:00",
        "element_calendar": "K-GD", "zusaetzliche_ressourcen": [{"freitext_ressource": "Neu"}]})
    assert r.status_code != 200, r.text
    assert _notifications(patched_db, "talente") == []


@pytest.mark.parametrize("freigabe", [False, True])
def test_unveraenderte_ressourcen_und_reihenfolge_still(client, patched_db, freigabe):
    from diakronos_app.api.kronos.event_crud import _apply_additional_resources
    from diakronos_app.frappe_compat.api_helpers import _create
    import json
    _moderator_welt(patched_db)
    _apply_additional_resources("E-1", [{"freitext_ressource": "Saal"}, {"freitext_ressource": "Bühne"}])
    anmelden(client, "moderator")
    zeilen = [{"freitext_ressource": " Bühne ", "idx": 99}, {"freitext_ressource": "Saal"}]
    if freigabe:
        name = _create("Element Aenderung", {"element": "E-1", "element_calendar": "K-GD",
            "vorschlag": json.dumps({"zusaetzliche_ressourcen": zeilen}), "status": "Offen"})
        r = client.post(API + "aenderung_freigeben", json={"name": name})
    else:
        r = client.post(API + "update_event", json={"name": "E-1", "zusaetzliche_ressourcen": zeilen})
    assert r.status_code == 200, r.text
    assert _notifications(patched_db, "talente") == []


def test_zusatzressource_ohne_leserecht_still(client, patched_db):
    _moderator_welt(patched_db)
    with patched_db.begin() as s:
        s.delete(s.get(HasRole, "r-tal"))
    anmelden(client, "moderator")
    speichern(client, [{"freitext_ressource": "Geheimer Ort"}])
    assert _notifications(patched_db, "talente") == []
