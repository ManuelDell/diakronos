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


# R-4 (Manuel 11.11.): Leitung = HV/MV (Bereichsverantwortliche sind per Migration
# MV ihrer Gruppen) und Administrator. Die Mitgliederverwaltung ist ein Fach und
# hat in Gruppen KEIN Schreibrecht mehr — eigener Test unten.
@pytest.mark.parametrize("user", ["gruppenverantw@example.org", "bereichsverantw@example.org", "admin@example.org"])
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


def test_inhalte_ohne_eltern_verweigert(hierarchie):
    set_user("admin@example.org")
    with pytest.raises(PermissionError):
        G.create_ankuendigung(titel="Ohne Eltern")


def test_aufgabe_ohne_eltern_ist_eigene_aufgabe(hierarchie):
    """R-7b (Manuel 11.11.): eine Aufgabe ohne Gruppe ist eine eigene Aufgabe —
    sie landet nicht in einer Gruppe und wird nicht im Rechtesystem angemeldet."""
    set_user("admin@example.org")
    name = G.create_aufgabe(titel="Ohne Eltern")["name"]
    zeile = hierarchie.get(GruppenAufgabe, name)
    assert zeile.gruppe is None and zeile.untergruppe is None and zeile.owner == "admin@example.org"


def test_mitgliederverwaltung_schreibt_nicht_in_gruppen(hierarchie):
    """R-4: Mitgliederadministrator ist ein Fach, kein Gruppen-Admin."""
    set_user("mitarbadmin@example.org")
    for scope in ({"gruppe_id": "G-A1"}, {"untergruppe_id": "UG-A1"}):
        with pytest.raises(PermissionError):
            G.create_aufgabe("Nicht erlaubt", **scope)
        with pytest.raises(PermissionError):
            G.create_ankuendigung("Nicht erlaubt", **scope)


def test_hierarchie_zeigt_alle_gruppen_detail_bleibt_geschlossen(hierarchie):
    """R-4 (Manuel 11.11.): Organigramm/Baum zeigt ALLE Gruppen; der Inhalt einer
    Gruppe (Detail) bleibt fuer Nicht-Mitglieder fail closed — auch ohne Pfad."""
    hierarchie.add(Gruppe(name="zz-b-leerer-pfad", gruppenname="Privat", status="Aktiv", ancestor_path="|"))
    hierarchie.commit()
    set_user("mitglied-a@example.org")
    assert "zz-b-leerer-pfad" in {g["name"] for g in G.get_gruppen_hierarchie()["gruppen"]}
    with pytest.raises(PermissionError):
        G.get_gruppe_detail("zz-b-leerer-pfad")


def test_orgchart_zeigt_alle_gruppen_mit_hv_aber_keine_mitglieder(hierarchie):
    """R-4 (Manuel 11.11.): Organigramm mit Gruppen und HV fuer ALLE sichtbar;
    die Mitglieder einer Gruppe stehen dort nicht (nur Zahlen)."""
    set_user("mitglied-a@example.org")
    nodes = {n["id"]: n for n in G.get_gruppen_for_orgchart()["nodes"]}
    assert {"db_DB-A", "db_DB-B", "g_G-A1", "g_G-B1", "ug_UG-B1"} <= set(nodes)
    assert nodes["g_G-A1"]["hv"]  # HV der Gruppe ist benannt
    for n in nodes.values():
        assert "mitglieder" not in n


def test_hv_sieht_untergruppen_seiner_gruppe(hierarchie):
    """R-4 (Manuel 11.11.): HV/MV sind in jeder Untergruppe ihrer Gruppe berechtigt."""
    set_user("gruppenverantw@example.org")
    assert "UG-A1" in {u["name"] for u in G.get_gruppe_detail("G-A1")["untergruppen"]}


def test_gruppenmitglied_ohne_ug_mitgliedschaft_sieht_untergruppe_nicht(hierarchie):
    """R-4: Inhalte einer Untergruppe sieht die uebrige Gruppe erst nach Freigabe."""
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    hierarchie.add(Gruppenmitgliedschaft(name="zz-b-gm-b", parent="G-A1", parenttype="Gruppe",
                                         parentfield="mitglieder", mitglied="M-eigen-b", status="Aktiv"))
    hierarchie.commit()
    set_user("mitglied-b@example.org")
    assert "UG-A1" not in {u["name"] for u in G.get_gruppe_detail("G-A1")["untergruppen"]}
    with pytest.raises(PermissionError):
        G.get_untergruppe_detail("UG-A1")


def test_untergruppenleitung_darf_nur_eigene_untergruppe_schreiben(hierarchie):
    hierarchie.add(UntergruppeVerantwortlicher(name="zz-b-ug-leitung", parent="UG-A1",
                      parenttype="Untergruppe", parentfield="verantwortliche", user="ohne-mitglied@example.org"))
    hierarchie.commit()
    # R-4: Untergruppen-Verantwortliche werden Gruppenleiter (GL) — Uebernahme
    # wie im Betrieb (Migration r1_rechte_kern).
    from rechte_hilfe import uebernehmen

    uebernehmen(hierarchie)
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
        # R-4: Untergruppen-Inhalte nur fuer ihre Mitglieder -> M-eigen-b in UG-B1.
        from diakronos_app.models.diakonos import Untergruppenmitgliedschaft

        hierarchie.add(Untergruppenmitgliedschaft(name="zz-b-ugm-b", parent="UG-B1", parenttype="Untergruppe",
                                                  parentfield="mitglieder", mitglied="M-eigen-b", status="Aktiv"))
        hierarchie.commit()
        set_user("mitglied-b@example.org")
        result = G.get_untergruppe_detail("UG-B1")
    else:
        set_user("mitglied-a@example.org")
        result = getattr(G, endpoint)(gruppe_id="G-A1")
    rows = result["data"] if "data" in result else result["aufgaben"] + result["ankuendigungen"]
    assert not {"zz-b-alt-aufgabe", "zz-b-alt-ankuendigung"} & {r["name"] for r in rows}
