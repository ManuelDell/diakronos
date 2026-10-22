"""B4: Gruppen-Inhalte haben dieselben Sicht-/Bearbeitungsschranken wie Eltern."""

import pytest

from test_p4a_gruppen import hierarchie  # noqa: F401 — gemeinsame echte DB-Fixture
from diakronos_app.api import gruppen as G
from diakronos_app.frappe_compat.exceptions import PermissionError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.diakonos import Gruppe, GruppenAufgabe, Untergruppe, UntergruppeVerantwortlicher


@pytest.fixture(autouse=True)
def reset_user():
    yield
    set_user("Administrator")


@pytest.mark.parametrize("scope", [{"gruppe_id": "G-B1"}, {"untergruppe_id": "UG-B1"}])
@pytest.mark.parametrize("endpoint", ["get_aufgaben", "get_ankuendigungen", "create_aufgabe", "create_ankuendigung"])
def test_fremde_inhalte_verweigert(hierarchie, scope, endpoint):
    # Keine direkte Mitgliedschaft (auch keine inaktive Fixture-Zeile).
    set_user("gruppenverantw@example.org")
    args = dict(scope)
    if endpoint.startswith("create"):
        args["titel"] = "Nicht erlaubt"
    with pytest.raises(PermissionError):
        getattr(G, endpoint)(**args)


@pytest.mark.parametrize("scope", [{"gruppe_id": "G-A1"}, {"untergruppe_id": "UG-A1"}])
@pytest.mark.parametrize("endpoint", ["create_aufgabe", "create_ankuendigung"])
def test_einfache_mitglieder_duerfen_nicht_anlegen(hierarchie, scope, endpoint):
    set_user("mitglied-a@example.org")
    with pytest.raises(PermissionError):
        getattr(G, endpoint)(titel="Nicht erlaubt", **scope)


@pytest.mark.parametrize("user", ["gruppenverantw@example.org", "bereichsverantw@example.org", "admin@example.org", "mitarbadmin@example.org"])
@pytest.mark.parametrize("scope", [{"gruppe_id": "G-A1"}, {"untergruppe_id": "UG-A1"}])
def test_leitung_schreibt_mitglied_liest(hierarchie, user, scope):
    set_user(user)
    task = G.create_aufgabe("Erlaubt", **scope)
    announcement = G.create_ankuendigung("Erlaubt", text="Text", **scope)
    assert G.toggle_aufgabe(task["name"]) == {"success": True, "erledigt": 1}
    set_user("mitglied-a@example.org")
    assert {r["name"] for r in G.get_aufgaben(**scope)["data"]} == {task["name"]}
    assert {r["name"] for r in G.get_ankuendigungen(**scope)["data"]} == {announcement["name"]}
    with pytest.raises(PermissionError):
        G.toggle_aufgabe(task["name"])
    hierarchie.expire_all()
    assert hierarchie.get(GruppenAufgabe, task["name"]).erledigt is True


@pytest.mark.parametrize("task_id", ["zz-b-fremde-aufgabe", "zz-b-unbekannt"])
def test_toggle_existenz_ist_nicht_erkennbar(hierarchie, task_id):
    hierarchie.add(GruppenAufgabe(name="zz-b-fremde-aufgabe", gruppe="G-B1", titel="Privat", erledigt=False))
    hierarchie.commit()
    set_user("gruppenverantw@example.org")
    with pytest.raises(PermissionError, match="Keine Berechtigung"):
        G.toggle_aufgabe(task_id)
    hierarchie.expire_all()
    assert hierarchie.get(GruppenAufgabe, "zz-b-fremde-aufgabe").erledigt is False


@pytest.mark.parametrize("endpoint", ["create_aufgabe", "create_ankuendigung", "get_aufgaben", "get_ankuendigungen"])
@pytest.mark.parametrize("scope", [{"gruppe_id": "G-B1", "untergruppe_id": "UG-A1"}, {"gruppe_id": "zz-b-fehlt"}])
def test_unpassende_oder_unbekannte_eltern_verweigert(hierarchie, endpoint, scope):
    set_user("gruppenverantw@example.org")
    args = dict(scope)
    if endpoint.startswith("create"):
        args["titel"] = "Nicht erlaubt"
    with pytest.raises(PermissionError):
        getattr(G, endpoint)(**args)


@pytest.mark.parametrize("endpoint", ["create_aufgabe", "create_ankuendigung"])
def test_inhalte_ohne_eltern_verweigert(hierarchie, endpoint):
    set_user("admin@example.org")
    with pytest.raises(PermissionError):
        getattr(G, endpoint)(titel="Ohne Eltern")


def test_hierarchie_leerer_zielpfad_ist_fail_closed(hierarchie):
    hierarchie.add(Gruppe(name="zz-b-leerer-pfad", gruppenname="Privat", status="Aktiv", ancestor_path="|"))
    hierarchie.commit()
    set_user("mitglied-a@example.org")
    assert "zz-b-leerer-pfad" not in {g["name"] for g in G.get_gruppen_hierarchie()["gruppen"]}


def test_orgchart_fremde_bereiche_nicht_sichtbar(hierarchie):
    set_user("mitglied-a@example.org")
    ids = {n["id"] for n in G.get_gruppen_for_orgchart()["nodes"]}
    assert "db_DB-A" in ids
    assert not {"db_DB-B", "db_DB-C", "g_G-B1", "ug_UG-B1"} & ids


@pytest.mark.parametrize("endpoint", ["get_gruppen_hierarchie", "get_gruppen_for_orgchart", "get_gruppe_detail"])
def test_sichtbare_eltern_oeffnen_keine_unlesbaren_untergruppen(hierarchie, endpoint):
    ug = hierarchie.get(Untergruppe, "UG-A1")
    ug.ancestor_path = "|"
    hierarchie.commit()
    # Sichtbarer Elternpfad, aber KEINE direkte UG-Mitgliedschaft.
    set_user("gruppenverantw@example.org")
    result = getattr(G, endpoint)(gruppe_id="G-A1") if endpoint == "get_gruppe_detail" else getattr(G, endpoint)()
    if endpoint == "get_gruppen_hierarchie":
        assert "UG-A1" not in {u["name"] for g in result["gruppen"] for u in g["untergruppen"]}
    elif endpoint == "get_gruppe_detail":
        assert "UG-A1" not in {u["name"] for u in result["untergruppen"]}
    else:
        assert "ug_UG-A1" not in {n["id"] for n in result["nodes"]}


def test_untergruppenleitung_darf_nur_eigene_untergruppe_schreiben(hierarchie):
    hierarchie.add(UntergruppeVerantwortlicher(name="zz-b-ug-leitung", parent="UG-A1",
                      parenttype="Untergruppe", parentfield="verantwortliche", user="ohne-mitglied@example.org"))
    hierarchie.commit()
    set_user("ohne-mitglied@example.org")
    task = G.create_aufgabe("UG", untergruppe_id="UG-A1")
    assert G.toggle_aufgabe(task["name"])["erledigt"] == 1
    assert G.create_ankuendigung("UG", untergruppe_id="UG-A1")["success"]
    with pytest.raises(PermissionError):
        G.create_aufgabe("Gruppe", gruppe_id="G-A1")
    with pytest.raises(PermissionError):
        G.create_ankuendigung("Fremde UG", untergruppe_id="UG-B1")


@pytest.mark.parametrize("endpoint", ["get_aufgaben", "get_ankuendigungen"])
def test_ancestor_path_leser_ohne_direkte_mitgliedschaft(hierarchie, endpoint):
    set_user("admin@example.org")
    task = G.create_aufgabe("B", gruppe_id="G-B1")
    announcement = G.create_ankuendigung("B", gruppe_id="G-B1")
    set_user("mitglied-b@example.org")
    ids = {row["name"] for row in getattr(G, endpoint)(gruppe_id="G-B1")["data"]}
    assert (task if endpoint == "get_aufgaben" else announcement)["name"] in ids


@pytest.mark.parametrize("endpoint", ["get_aufgaben", "get_ankuendigungen"])
def test_direkte_mitgliedschaft_ohne_pfadoverlap_liest(hierarchie, endpoint):
    from diakronos_app.models.diakonos import Mitglied

    hierarchie.get(Mitglied, "M-gruppe-a1").ancestor_path = "|"
    hierarchie.commit()
    set_user("mitglied-a@example.org")
    assert getattr(G, endpoint)(gruppe_id="G-A1")["success"]


@pytest.mark.parametrize("links", [{}, {"gruppe": "G-B1", "untergruppe": "UG-A1"}, {"gruppe": "zz-b-fehlt"}])
def test_toggle_verwaiste_oder_widerspruechliche_aufgaben_verweigert(hierarchie, links):
    # SQLite erlaubt historische inkonsistente Links; PostgreSQL-FK wuerde
    # neue ungueltige Eltern abweisen. Der Lesepfad bleibt trotzdem geschlossen.
    hierarchie.add(GruppenAufgabe(name="zz-b-inkonsistent", titel="Privat", erledigt=False, **links))
    hierarchie.commit()
    set_user("admin@example.org")
    with pytest.raises(PermissionError):
        G.toggle_aufgabe("zz-b-inkonsistent")


def test_konsistente_doppellinks_bleiben_erlaubt(hierarchie):
    set_user("gruppenverantw@example.org")
    scope = {"gruppe_id": "G-A1", "untergruppe_id": "UG-A1"}
    task = G.create_aufgabe("Beide", **scope)
    assert G.toggle_aufgabe(task["name"])["success"]
    set_user("mitglied-a@example.org")
    assert {r["name"] for r in G.get_aufgaben(**scope)["data"]} == {task["name"]}


@pytest.mark.parametrize("endpoint", ["get_aufgaben", "get_ankuendigungen", "get_gruppe_detail", "get_untergruppe_detail"])
def test_historische_widerspruechliche_links_nicht_ausliefern(hierarchie, endpoint):
    from diakronos_app.models.diakonos import GruppenAnkuendigung

    hierarchie.add_all([
        GruppenAufgabe(name="zz-b-alt-aufgabe", gruppe="G-A1", untergruppe="UG-B1", titel="Privat"),
        GruppenAnkuendigung(name="zz-b-alt-ankuendigung", gruppe="G-A1", untergruppe="UG-B1", titel="Privat"),
    ])
    hierarchie.commit()
    if endpoint == "get_untergruppe_detail":
        set_user("mitglied-b@example.org")
        result = G.get_untergruppe_detail("UG-B1")
    else:
        set_user("mitglied-a@example.org")
        result = getattr(G, endpoint)(gruppe_id="G-A1")
    rows = result["data"] if "data" in result else result["aufgaben"] + result["ankuendigungen"]
    assert not {"zz-b-alt-aufgabe", "zz-b-alt-ankuendigung"} & {r["name"] for r in rows}
