"""UX2b2 (F3) — jeder Lesepfad filtert den Papierkorb (je Pfad ein HTTP-Test).

Der Befund aus dem Review war nicht „ein Pfad fehlt“, sondern: das Loeschen
setzte zwar ``geloescht_am``, aber eine ganze Reihe von Lesewegen fragte
weiter alle Zeilen ab — die Zeile war in der Liste, in der Suche, im
Organigramm, auf der Website, im Planrahmen und im generischen CRUD wieder
sichtbar. Jeder Pfad unten haette einzeln gereicht, die Loeschung wertlos zu
machen.

Aufbau je Test: Zeile anlegen -> in den Papierkorb legen (der echte
Loesch-Endpunkt bzw. ``papierkorb.loeschen``) -> den LESEWEG ueber HTTP
aufrufen -> der geloeschte Datensatz kommt nicht vor. Danach (wo es einen
Endpunkt gibt) wiederherstellen -> er kommt wieder vor. Nur so ist bewiesen,
dass der Filter den Papierkorb liest und nicht die ganze Abfrage leer laesst.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from diakronos_app.frappe_compat.session import set_user

ADMIN = "ux2b2f3-admin@example.org"
MITGLIED = "ux2b2f3-mitglied@example.org"

DASHBOARD = "diakronos.diakonos.api.dashboard"
GRUPPEN = "diakronos.diakonos.api.gruppen"
ORGCHART = "diakronos.diakonos.api.orgchart_api"
MUSIK = "diakronos.psalmos.api.musik"
PLANUNG = "diakronos.kronos.api.planung"
KANBAN = "diakronos.kronos.api.kanban_api"
WEBSITE = "diakronos.diakonos.api.website"
SUCHE_GLOBAL = "diakronos.diakonos.api.suche.global"


@pytest.fixture()
def welt(patched_db, fake_redis):
    """Admin + Mitglied, eine Gruppe mit Termin/Beitrag/Wiki/Lied."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Beitrag,
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
        WikiArtikel,
    )
    from diakronos_app.models.kronos import Element, Kalender, Ressource
    from diakronos_app.models.psalmos import Lied

    sess = patched_db()
    sess.add_all([
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
        User(name=MITGLIED, email=MITGLIED, full_name="Mia Mitglied", enabled=1),
        HasRole(name="f3-hr-1", parent=ADMIN, parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=0),
        HasRole(name="f3-hr-2", parent=ADMIN, parenttype="User",
                parentfield="roles", role="Kalenderadministrator", docstatus=0, idx=0),
        # „Meine Gruppen“ laeuft ueber Mitglied.user -> Gruppenmitgliedschaft.
        Mitglied(name="MIT-F3", vorname="Mia", nachname="Mitglied",
                 email=MITGLIED, user=MITGLIED, status="Mitglied"),
    ])
    sess.add(Kalender(name="KAL-F3", calendar_name="Gottesdienste",
                      website_freigabe=1, website_slug="gottesdienste",
                      docstatus=0, idx=0))
    sess.add(Gruppe(name="GRU-F3", gruppenname="Jugend", status="Aktiv",
                    sichtbarkeit="Intern", website_freigabe=1,
                    website_slug="jugend", docstatus=0, idx=0))
    sess.add(Gruppenmitgliedschaft(name="GM-F3", parent="GRU-F3",
                                   parenttype="Gruppe", parentfield="mitglieder",
                                   mitglied="MIT-F3", rolle="Mitglied",
                                   status="Aktiv", docstatus=0, idx=0))
    sess.add(Element(name="ELE-F3", element_name="Jugendtreff",
                     element_calendar="KAL-F3", gruppe="GRU-F3",
                     element_start=datetime(2026, 11, 8, 10, 0),
                     element_end=datetime(2026, 11, 8, 11, 0),
                     status="Festgelegt", docstatus=0, idx=0))
    sess.add(Beitrag(name="BEI-F3", titel="Sommerfest", kategorie="gemeinde",
                     datum=date(2026, 7, 1), autor="Ada Admin", autor_email=ADMIN,
                     veroeffentlicht=1, auf_website=1, auszug="Fest im Hof",
                     inhalt="<p>Alle eingeladen.</p>", docstatus=0, idx=0))
    sess.add(WikiArtikel(name="WIK-F3", titel="Beamer", kategorie="technik",
                         tags="Tonanlage", autor="Ada Admin", autor_email=ADMIN,
                         auszug="So geht der Beamer", inhalt="<p>Anleitung</p>",
                         docstatus=0, idx=0))
    sess.add(Lied(name="LIE-F3", titel="Grosser Gott", aktiv=1,
                  rechte_status="frei", docstatus=0, idx=0))
    sess.add(Ressource(name="RES-F3", ressource_name="Gemeindesaal",
                       docstatus=0, idx=0))
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_admin(welt):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


@pytest.fixture()
def als_mitglied(welt):
    set_user(MITGLIED)
    yield MITGLIED
    set_user("Administrator")


def _loeschen(doctype: str, name: str) -> None:
    from diakronos_app import papierkorb

    papierkorb.loeschen(doctype, name, von=ADMIN)


def _holen(doctype: str, name: str) -> None:
    from diakronos_app import papierkorb

    papierkorb.wiederherstellen(doctype, name)


# ── Dashboard ───────────────────────────────────────────────────────────────


def test_dashboard_angeheftete_beitraege(client, als_admin, welt):
    vorher = client.get(f"/api/method/{DASHBOARD}.get_pinned_beitraege").json()["message"]
    assert [b["id"] for b in vorher] == ["BEI-F3"]

    _loeschen("Beitrag", "BEI-F3")
    nachher = client.get(f"/api/method/{DASHBOARD}.get_pinned_beitraege").json()["message"]
    assert nachher == [], "geloeschter Beitrag steht noch im Dashboard"

    _holen("Beitrag", "BEI-F3")
    wieder = client.get(f"/api/method/{DASHBOARD}.get_pinned_beitraege").json()["message"]
    assert [b["id"] for b in wieder] == ["BEI-F3"]


def test_dashboard_wiki_kachel(client, als_admin, welt):
    vorher = client.get(f"/api/method/{DASHBOARD}.get_recent_articles").json()["message"]
    assert [w["id"] for w in vorher] == ["WIK-F3"]

    _loeschen("Wiki Artikel", "WIK-F3")
    nachher = client.get(f"/api/method/{DASHBOARD}.get_recent_articles").json()["message"]
    assert nachher == [], "geloeschter Wiki-Artikel steht noch in der Kachel"

    _holen("Wiki Artikel", "WIK-F3")
    wieder = client.get(f"/api/method/{DASHBOARD}.get_recent_articles").json()["message"]
    assert [w["id"] for w in wieder] == ["WIK-F3"]


# ── Gruppen ─────────────────────────────────────────────────────────────────


def test_gruppen_seite_zeigt_geloeschte_gruppe_nicht(client, als_admin, welt):
    vorher = client.get(f"/api/method/{GRUPPEN}.get_gruppen_page_data").json()["message"]
    assert "GRU-F3" in str(vorher)

    _loeschen("Gruppe", "GRU-F3")
    nachher = client.get(f"/api/method/{GRUPPEN}.get_gruppen_page_data").json()["message"]
    assert "GRU-F3" not in str(nachher), "geloeschte Gruppe steht noch auf der Gruppenseite"

    _holen("Gruppe", "GRU-F3")
    wieder = client.get(f"/api/method/{GRUPPEN}.get_gruppen_page_data").json()["message"]
    assert "GRU-F3" in str(wieder)


def test_meine_gruppen_ohne_papierkorb(client, als_mitglied, welt):
    vorher = client.get(f"/api/method/{GRUPPEN}.get_gruppen_page_data").json()["message"]
    assert "GRU-F3" in str(vorher.get("meine_gruppen"))

    set_user(ADMIN)
    _loeschen("Gruppe", "GRU-F3")
    set_user(MITGLIED)
    nachher = client.get(f"/api/method/{GRUPPEN}.get_gruppen_page_data").json()["message"]
    assert "GRU-F3" not in str(nachher.get("meine_gruppen")), (
        "geloeschte Gruppe steht noch unter „Meine Gruppen“"
    )


def test_gruppen_uebersicht_ohne_papierkorb(client, als_admin, welt):
    _loeschen("Gruppe", "GRU-F3")
    daten = client.get(f"/api/method/{GRUPPEN}.get_gruppen_page_data").json()["message"]
    # Die Uebersicht je Gruppentyp und die Admin-Liste fuehren zusammen jede
    # sichtbare Gruppe — die geloeschte darf in keiner der beiden stehen.
    assert "GRU-F3" not in str(daten.get("typen"))
    assert "GRU-F3" not in str(daten.get("andere_gruppen"))


def test_termine_einer_gruppe_ohne_papierkorb(client, als_admin, welt):
    vorher = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                        params={"gruppe_id": "GRU-F3"}).json()["message"]
    assert "ELE-F3" in str(vorher)

    _loeschen("Element", "ELE-F3")
    nachher = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                         params={"gruppe_id": "GRU-F3"}).json()["message"]
    assert "ELE-F3" not in str(nachher), (
        "geloeschter Termin steht noch in der Terminliste der Gruppe"
    )


# ── Organigramm ─────────────────────────────────────────────────────────────


def _orgchart_gruppenknoten(daten):
    """Nur die Gruppen-Knoten (die Mitglied-Knoten tragen Gruppenkennungen im Namen)."""
    return [n for n in daten if n.get("node_type") in ("gruppe", "untergruppe")]


def test_organigramm_ohne_papierkorb(client, als_admin, welt):
    vorher = client.get(f"/api/method/{ORGCHART}.get_orgchart_data").json()["message"]
    ids = {n["id"] for n in _orgchart_gruppenknoten(vorher)}
    assert "g_GRU-F3" in ids, ids

    _loeschen("Gruppe", "GRU-F3")
    nachher = client.get(f"/api/method/{ORGCHART}.get_orgchart_data").json()["message"]
    ids_nachher = {n["id"] for n in _orgchart_gruppenknoten(nachher)}
    assert "g_GRU-F3" not in ids_nachher, "geloeschte Gruppe steht noch im Organigramm"

    _holen("Gruppe", "GRU-F3")
    wieder = client.get(f"/api/method/{ORGCHART}.get_orgchart_data").json()["message"]
    assert "g_GRU-F3" in {n["id"] for n in _orgchart_gruppenknoten(wieder)}


# ── Planrahmen / Planung ────────────────────────────────────────────────────


def test_planrahmen_waehlt_keine_geloeschten_lieder(client, als_admin, welt):
    """UX2b2 (F3): der Planrahmen bietet kein Lied aus dem Papierkorb an."""
    from diakronos_app.api.planung import _lied_kandidaten

    vorher = _lied_kandidaten(None)
    assert [x["referenz_name"] for x in vorher] == ["LIE-F3"]

    _loeschen("Lied", "LIE-F3")
    nachher = _lied_kandidaten(None)
    assert nachher == [], "Planrahmen bietet ein geloeschtes Lied an"

    _holen("Lied", "LIE-F3")
    wieder = _lied_kandidaten(None)
    assert [x["referenz_name"] for x in wieder] == ["LIE-F3"]


# ── Kanban: Ressourcenkonflikt ──────────────────────────────────────────────


def test_kanban_meldet_keinen_konflikt_mit_geloeschtem_termin(client, als_admin, welt):
    from diakronos_app.models.kronos import Element

    sess = welt
    sess.add(Element(
        name="ELE-F3B", element_name="Anderer Termin", element_calendar="KAL-F3",
        ressource="RES-F3",
        element_start=datetime(2026, 11, 8, 10, 30),
        element_end=datetime(2026, 11, 8, 11, 30),
        status="Festgelegt", docstatus=0, idx=0,
    ))
    sess.commit()
    with sess.begin():
        sess.execute(
            Element.__table__.update().where(Element.name == "ELE-F3")
            .values(ressource="RES-F3")
        )

    r = client.get(f"/api/method/{KANBAN}.get_conflict_partner",
                   params={"element_id": "ELE-F3"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] is not None, "Konflikt mit vorhandenem Termin fehlt"

    _loeschen("Element", "ELE-F3B")
    r2 = client.get(f"/api/method/{KANBAN}.get_conflict_partner",
                    params={"element_id": "ELE-F3"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"] is None, (
        "Konflikt mit einem Termin im Papierkorb gemeldet"
    )


# ── Website-Freigaben ───────────────────────────────────────────────────────


def test_website_freigabelisten_ohne_papierkorb(client, als_admin, welt):
    vorher = client.get(f"/api/method/{WEBSITE}.freigaben_lesen").json()["message"]
    assert "GRU-F3" in str(vorher)
    assert "BEI-F3" in str(vorher)

    _loeschen("Gruppe", "GRU-F3")
    _loeschen("Beitrag", "BEI-F3")
    nachher = client.get(f"/api/method/{WEBSITE}.freigaben_lesen").json()["message"]
    assert "GRU-F3" not in str(nachher), "geloeschte Gruppe steht noch in der Freigabeliste"
    assert "BEI-F3" not in str(nachher), "geloeschter Beitrag steht noch in der Freigabeliste"


def test_oeffentliche_termine_ohne_geloeschten_gruppennamen(client, als_admin, welt):
    """Der Gruppenname einer geloeschten Gruppe darf nicht public erscheinen."""
    from diakronos_app.website import oeffentlich_daten as daten

    sess = welt
    vorher = daten.termine(sess, kalender=["gottesdienste"])
    assert any(
        (t.get("gruppe") or {}).get("name") == "Jugend" for t in vorher
    ), f"Testaufbau: Gruppenname fehlt in den oeffentlichen Terminen ({vorher})"

    _loeschen("Gruppe", "GRU-F3")
    nachher = daten.termine(sess, kalender=["gottesdienste"])
    assert not any(
        (t.get("gruppe") or {}).get("name") == "Jugend" for t in nachher
    ), "Name der geloeschten Gruppe steht noch auf einem oeffentlichen Termin"


# ── Suche ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("doctype,name,begriff,treffer_art", [
    ("Beitrag", "BEI-F3", "Sommerfest", "beitrag"),
    ("Wiki Artikel", "WIK-F3", "Beamer", "wiki"),
    ("Lied", "LIE-F3", "Grosser Gott", "lied"),
    ("Gruppe", "GRU-F3", "Jugend", "gruppe"),
])
def test_suche_findet_geloeschtes_nicht(client, als_admin, welt,
                                        doctype, name, begriff, treffer_art):
    r = client.get(f"/api/method/{SUCHE_GLOBAL}", params={"q": begriff, "limit": 20})
    assert r.status_code == 200, r.text
    treffer = r.json()["message"]["treffer"]
    assert any(t["art"] == treffer_art for t in treffer), (
        f"Testaufbau: {treffer_art!r} nicht gefunden ({treffer})"
    )

    _loeschen(doctype, name)
    r2 = client.get(f"/api/method/{SUCHE_GLOBAL}", params={"q": begriff, "limit": 20})
    assert r2.status_code == 200, r2.text
    treffer2 = r2.json()["message"]["treffer"]
    assert not any(t["art"] == treffer_art for t in treffer2), (
        f"geloeschter {doctype} noch in der Suche"
    )


# ── Generischer CRUD (/api/resource) ────────────────────────────────────────


def test_resource_liste_ohne_papierkorb(client, als_admin, welt):
    vorher = client.get("/api/resource/Lied").json()["data"]
    assert [z["name"] for z in vorher] == ["LIE-F3"]

    _loeschen("Lied", "LIE-F3")
    nachher = client.get("/api/resource/Lied").json()["data"]
    assert nachher == [], "geloeschtes Lied steht noch in /api/resource"


def test_resource_liste_behaelt_eigene_filter(client, als_admin, welt):
    """Der Papierkorb-Filter darf einen uebergebenen Filter nicht verdraengen."""
    _loeschen("Lied", "LIE-F3")
    from diakronos_app.models.psalmos import Lied

    sess = welt
    with sess.begin():
        sess.execute(
            Lied.__table__.insert().values(
                name="LIE-F3B", titel="Anderes Lied", aktiv=1, docstatus=0, idx=0
            )
        )
    daten = client.get("/api/resource/Lied",
                       params={"filters": '{"aktiv": 1}'}).json()["data"]
    assert [z["name"] for z in daten] == ["LIE-F3B"]


def test_resource_einzelabruf_verhaelt_sich_wie_nicht_vorhanden(client, als_admin, welt):
    assert client.get("/api/resource/Lied/LIE-F3").status_code == 200
    _loeschen("Lied", "LIE-F3")
    r = client.get("/api/resource/Lied/LIE-F3")
    assert r.status_code == 404, "geloeschtes Lied ueber /api/resource lesbar"


def test_resource_delete_legt_in_den_papierkorb(client, als_admin, welt):
    """Ein DELETE ueber den generischen CRUD loescht NICHT endgueltig."""
    from diakronos_app.models.psalmos import Lied

    r = client.delete("/api/resource/Lied/LIE-F3")
    assert r.status_code in (200, 202), r.text

    sess = welt
    sess.expire_all()
    zeile = sess.get(Lied, "LIE-F3")
    assert zeile is not None, "generischer DELETE hat die Zeile sofort entfernt"
    assert zeile.geloescht_am is not None, "generischer DELETE setzt kein geloescht_am"


def test_resource_delete_auf_beitrag_haelt_kommentare_am_leben(client, als_admin, welt):
    """Bis zum endgueltigen Entfernen bleiben die Kommentare (Wiederherstellen)."""
    from diakronos_app.models.diakonos import BeitragKommentar

    sess = welt
    with sess.begin():
        sess.execute(
            BeitragKommentar.__table__.insert().values(
                name="BK-F3", parent="BEI-F3", parenttype="Beitrag",
                parentfield="kommentare", autor="Mia", text="Toller Bericht",
                docstatus=0, idx=0,
            )
        )

    assert client.delete("/api/resource/Beitrag/BEI-F3").status_code in (200, 202)
    sess.expire_all()
    assert sess.get(BeitragKommentar, "BK-F3") is not None, (
        "Kommentare bereits beim weichen Loeschen entfernt — Wiederherstellen "
        "waere unvollstaendig"
    )
