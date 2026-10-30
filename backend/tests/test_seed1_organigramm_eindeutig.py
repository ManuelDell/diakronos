"""SEED-1 — Demo-Seed und Organigramm: Knoten-Kennungen sind eindeutig.

Befund: ``tools/demo/musterhausen_daten.py`` vergab ``dienstbereich.name =
"technik"`` UND ``gruppe.name = "technik"``. ``api/orgchart_api.get_orgchart_data``
setzt die Knoten-``id`` auf den docname des Datensatzes — damit standen zwei
Knoten mit ``id "technik"`` in der Liste, und d3-org-chart bricht mit
„ambiguous: technik“ ab; das Organigramm der Demo laedt nicht.

Geprueft wird hier:
  * die Daten des Seeds (Modul ``musterhausen_daten`` ohne Datenbank),
  * die Antwort des ECHTEN Endpunkts auf den Demo-Daten (``patched_db``).

Die zweite Haelfte ist der Grund, warum der Test in ``backend/tests`` liegt und
nicht neben dem Seed: nur hier laeuft die App-Schicht mit.
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest

#: Fester Referenztag wie in ``test_demo_musterhausen``.
STICHTAG = date(2026, 11, 2)


@pytest.fixture()
def daten():
    """Reine Datendatei des Seeds — kein Datenbankzugriff."""
    return importlib.import_module("musterhausen_daten")


@pytest.fixture()
def demo(patched_db):
    modul = importlib.import_module("musterhausen")
    yield modul


def _kennungen(daten) -> dict[str, str]:
    """Alle Dienstbereichs- und Gruppen-Kennungen mit ihrer Herkunft.

    Ein Eintrag, der zweimal mit UNTERSCHIEDLICHER Herkunft entsteht, ist der
    Fehler aus SEED-1.
    """
    herkunft: dict[str, str] = {}
    for feld, datensaetze in (("dienstbereich", daten.DIENSTBEREICHE),
                              ("gruppe", daten.GRUPPEN)):
        for ds in datensaetze:
            name = ds["name"]
            assert name not in herkunft, (
                f"Kennung {name!r} doppelt: {herkunft[name]} und {feld}")
            herkunft[name] = feld
    return herkunft


def test_seed_kennungen_von_dienstbereichen_und_gruppen_sind_eindeutig(daten):
    """SEED-1: keine Kennung, die Dienstbereich UND Gruppe zugleich ist."""
    herkunft = _kennungen(daten)
    # Der Technik-Bereich darf seine Kennung behalten — die Gruppe daneben
    # muss eine eigene haben (SEED-1: vorher beide "technik").
    assert herkunft.get("technik") == "dienstbereich"


def test_seed_gruppen_kennungen_eindeutig(daten):
    """Auch innerhalb der Gruppen selbst: keine doppelte Kennung."""
    namen = [g["name"] for g in daten.GRUPPEN]
    assert len(namen) == len(set(namen)), namen
    assert daten.MUSIKTEAMS_OBERGRUPPE not in namen


def test_seed_gruppe_verweist_auf_vorhandenen_dienstbereich(daten):
    """Jede Gruppe haengt an einem Dienstbereich, den der Seed anlegt."""
    bereiche = {b["name"] for b in daten.DIENSTBEREICHE}
    for gruppe in daten.GRUPPEN:
        assert gruppe["bereich"] in bereiche, gruppe


def test_seed_gruppe_anzeige_und_kennung_des_technikteams(daten):
    """Der Technik-Bereich heisst weiter „Technik“, das Team bleibt ein Team.

    Die Umbenennung betrifft nur die KENNUNG (docname), nicht den Anzeigenamen:
    der Screenshot der Demo soll „Technik“ und „Technikteam“ zeigen.
    """
    bereich = next(b for b in daten.DIENSTBEREICHE if b["anzeige"] == "Technik")
    team = next(g for g in daten.GRUPPEN if g["anzeige"] == "Technikteam")
    assert team["bereich"] == bereich["name"]
    assert team["typ"] == "team"
    assert team["name"] != bereich["name"]


def test_orgchart_knoten_ids_der_demo_sind_eindeutig(engine, session_factory, demo):
    """Die ECHTE Orgchart-Antwort auf den Demo-Daten hat keine doppelte ``id``.

    Das ist der Fehler, den d3-org-chart als „ambiguous“ meldet: nicht die
    Datenbank, sondern die Knotenliste des Endpunkts.
    """
    from diakronos_app.api.orgchart_api import get_orgchart_data
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    # Der Endpunkt verlangt einen angemeldeten Benutzer (allow_guest=False).
    with session_factory() as s:
        admin_mail = s.query(Mitglied).filter(
            Mitglied.nachname == "Sonnleitner").one().user
    set_user(admin_mail)

    nodes = get_orgchart_data()
    ids = [n["id"] for n in nodes]
    doppelt = {i for i in ids if ids.count(i) > 1}
    assert not doppelt, f"Knoten-IDs mehrfach vergeben: {sorted(doppelt)}"

    # Und jede Elternkante zeigt auf einen vorhandenen Knoten.
    bekannt = set(ids)
    for node in nodes:
        if node.get("parentId"):
            assert node["parentId"] in bekannt, node
