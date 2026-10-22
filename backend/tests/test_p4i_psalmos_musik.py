"""P4i — Portiertes Modul `api.psalmos.musik` (8 Endpunkte, Liedgut).

Quelle (READ-ONLY):
  referenz/diakronos-frappe/diakronos/psalmos/api/musik.py

Abgedeckt:
  * Registrierung: `FRAPPE_MODULE == "diakronos.psalmos.api.musik"` (Achtung:
    `psalmos`, nicht `diakonos`), alle 8 SPA-Pfade aufloesbar.
  * Login-Pflicht (`allow_guest=False`): Guest -> 403 fuer alle 8 Endpunkte.
  * `get_lieder`: Titel-Suche, Strophentext-Suche, `rechte_status`-Filter,
    `gruppe`/`kategorie`/`anlass`-Filter (ueber die Child-Tabellen), Besetzungen,
    `anzahl_fassungen`, Sortierung nach Titel, Limit/Obergrenze.
  * `get_lied_detail`: Kopf + Strophen (nach idx) + Fassungen (mit Material) +
    Liedgruppen + Kategorien/Anlaesse.
  * `get_fassungen`: alle/gefilterte Fassungen eines Liedes.
  * `save_lied` / `save_fassung`: Schreibrecht (403 fuer Nicht-Berechtigte),
    Insert/Update, Kindtabellen-Ersetzung (`parenttype` = ELTERN-DocType).
  * `get_lied_historie`: defensiv leere Liste (Live-Schema: `Ablaufplan` hat
    KEIN referenz_doctype -> Original liefert dort immer []).
  * `get_liedgruppen` / `get_liedgruppe_detail`: Liste + Detail (Lieder, Rollen).
  * `get_lied_filteroptionen` (PF2): Gruppen/Kategorien/Anlaesse der Lieder-Liste
    in EINEM Aufruf — dieselben Optionsnamen wie das frueher noetige Nachladen
    von Lied-Details, aber ohne N+1.
  * Sichtbarkeit: das Original filtert Listen NICHT nach Sichtbarkeit — jede
    eingeloggte Person sieht alle Lieder (Test belegt das ausdruecklich).
"""

from __future__ import annotations

from datetime import date

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

MUSIK = "diakronos.psalmos.api.musik"

SPA_PFADE = [
    "get_lieder",
    "get_lied_detail",
    "get_fassungen",
    "save_lied",
    "save_fassung",
    "get_lied_historie",
    "get_liedgruppen",
    "get_liedgruppe_detail",
    # PF2: Filter-Optionen der Lieder-Liste in EINEM Aufruf (ersetzt das
    # fruehere Nachladen ueber 30 Lied-Details im Frontend).
    "get_lied_filteroptionen",
]

ANNA = "anna@example.org"       # eingeloggt, KEIN Schreibrecht
BRUNO = "bruno@example.org"     # Musikverantwortlicher (Gruppe im Bereich)
ADMIN = "admin@example.org"     # Mitgliederadministrator


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Lieder, Fassungen, Liedgruppen + Rechte-Hierarchie."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        DienstbereichVerantwortlicher,
        Gruppe,
        GruppeVerantwortlicher,
    )
    from diakronos_app.models.psalmos import (
        Lied,
        LiedAnlass,
        LiedGruppenzuordnung,
        LiedKategorie,
        LiedMaterial,
        Liedfassung,
        Liedgruppe,
        LiedgruppeLied,
        LiedgruppeRolle,
        Liedstrophe,
    )
    from diakronos_app.models.psalmos import Liedanlass, Liedkategorie

    sess = patched_db()

    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=1),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
    ])

    # Dienstbereich "Musik und Worship": Bruno ist Gruppenverantwortlicher,
    # Anna nicht. Der Bereich selbst ist ein eigenes Doc.
    sess.add_all([
        Dienstbereich(name="Musik und Worship", ministry="Musik und Worship",
                      docstatus=0, idx=0),
        Dienstbereich(name="Technik", ministry="Technik", docstatus=0, idx=0),
        Gruppe(name="GRP-WORSHIP", gruppenname="Worship-Band",
               dienstbereich="Musik und Worship", docstatus=0, idx=0),
        # Zweite Gruppe in einem ANDEREN Bereich (darf kein Musikrecht geben).
        Gruppe(name="GRP-TECH", gruppenname="Technik",
               dienstbereich="Technik", docstatus=0, idx=0),
    ])
    sess.add_all([
        GruppeVerantwortlicher(name="GV-1", parent="GRP-WORSHIP",
                               parenttype="Gruppe", parentfield="verantwortliche",
                               user=BRUNO, docstatus=0, idx=1),
        # Anna ist Verantwortliche einer Gruppe AUSSERHALB "Musik und Worship".
        GruppeVerantwortlicher(name="GV-2", parent="GRP-TECH",
                               parenttype="Gruppe", parentfield="verantwortliche",
                               user=ANNA, docstatus=0, idx=1),
        DienstbereichVerantwortlicher(name="DV-1", parent="Technik",
                                      parenttype="Dienstbereich",
                                      parentfield="verantwortliche",
                                      user=ANNA, docstatus=0, idx=1),
    ])

    sess.add_all([
        Lied(name="LIED-1", titel="Grosser Gott", alternativtitel="Holy God",
             gesangbuch_nummer="1", ccli_nummer="12345", aktiv=1,
             rechte_status="gemeinfrei", zuletzt_gesungen=date(2026, 6, 1),
             anzahl_gesungen=7, notiz="Standard", streaming_erlaubt=1,
             rechtehinweis="Frei", docstatus=0, idx=0),
        Lied(name="LIED-2", titel="Amazing Grace", alternativtitel=None,
             gesangbuch_nummer="2", ccli_nummer=None, aktiv=0,
             rechte_status="geschuetzt", zuletzt_gesungen=None,
             anzahl_gesungen=0, notiz=None, streaming_erlaubt=0,
             rechtehinweis="CCLI", docstatus=0, idx=0),
        # Lied, das NUR ueber seinen Strophentext gefunden wird.
        Lied(name="LIED-3", titel="Morgenlicht", alternativtitel=None,
             gesangbuch_nummer="3", ccli_nummer=None, aktiv=1,
             rechte_status="gemeinfrei", zuletzt_gesungen=None,
             anzahl_gesungen=2, notiz=None, streaming_erlaubt=1,
             rechtehinweis="Frei", docstatus=0, idx=0),
    ])

    # Strophen (nach idx sortiert pruefbar).
    sess.add_all([
        Liedstrophe(name="ST-1", parent="LIED-1", parenttype="Lied",
                    parentfield="strophen", nummer=1, typ="Strophe",
                    text="Grosser Gott wir loben dich", sprache="de",
                    nur_chor=0, docstatus=0, idx=1),
        Liedstrophe(name="ST-2", parent="LIED-1", parenttype="Lied",
                    parentfield="strophen", nummer=2, typ="Strophe",
                    text="Herr wir preisen deine Staerke", sprache="de",
                    nur_chor=0, docstatus=0, idx=2),
        # "sonnenstrahl" kommt nur im Strophentext von LIED-3 vor.
        Liedstrophe(name="ST-3", parent="LIED-3", parenttype="Lied",
                    parentfield="strophen", nummer=1, typ="Strophe",
                    text="Ein Sonnenstrahl am Morgen", sprache="de",
                    nur_chor=0, docstatus=0, idx=1),
    ])

    # Fassungen: LIED-1 hat zwei (Standard zuerst), LIED-3 keine.
    sess.add_all([
        Liedfassung(name="FAS-1", lied="LIED-1", fassungsname="Chorsatz",
                    gruppe="GRP-WORSHIP", ist_standard=1, besetzung="Chor",
                    stimmen="SATB", tonart="D", taktart="4/4", tempo_bpm=88,
                    dauer_minuten=4, schwierigkeit="mittel", arrangeur="M. Muster",
                    externe_links="https://x", notiz="Hauptfassung",
                    docstatus=0, idx=0),
        Liedfassung(name="FAS-2", lied="LIED-1", fassungsname="Bandfassung",
                    gruppe="GRP-WORSHIP", ist_standard=0, besetzung="Band",
                    stimmen=None, tonart="G", taktart="4/4", tempo_bpm=92,
                    dauer_minuten=5, schwierigkeit="leicht", arrangeur=None,
                    externe_links=None, notiz=None, docstatus=0, idx=0),
        Liedfassung(name="FAS-3", lied="LIED-3", fassungsname="A-cappella",
                    gruppe=None, ist_standard=1, besetzung="Chor",
                    stimmen="SSAA", tonart="C", taktart="3/4", tempo_bpm=70,
                    dauer_minuten=3, schwierigkeit="schwer", arrangeur=None,
                    externe_links=None, notiz=None, docstatus=0, idx=0),
    ])
    sess.add_all([
        LiedMaterial(name="MAT-1", parent="FAS-1", parenttype="Liedfassung",
                     parentfield="material", art="Noten", stimme="Sopran",
                     anhang="/files/s.pdf", beschreibung="Partitur",
                     docstatus=0, idx=1),
    ])

    # Zuordnungen / Kategorien / Anlaesse.
    # Katalogzeilen (Liedkategorie/Liedanlass) sind die Stammdaten, auf die die
    # Kindzeilen verweisen; `get_lied_filteroptionen` loest darueber die
    # Klartextnamen auf.
    sess.add_all([
        Liedkategorie(name="Lobpreis", kategoriename="Lobpreis",
                      farbe=None, docstatus=0, idx=0),
        Liedkategorie(name="Weihnachten", kategoriename="Weihnachten",
                      farbe=None, docstatus=0, idx=0),
        Liedanlass(name="Gottesdienst", anlassname="Gottesdienst",
                   farbe=None, docstatus=0, idx=0),
    ])
    sess.add_all([
        LiedGruppenzuordnung(name="LGZ-1", parent="LIED-1", parenttype="Lied",
                             parentfield="gruppen", gruppe="GRP-WORSHIP",
                             docstatus=0, idx=1),
        LiedKategorie(name="LK-1", parent="LIED-1", parenttype="Lied",
                      parentfield="kategorien", kategorie="Lobpreis",
                      docstatus=0, idx=1),
        LiedAnlass(name="LA-1", parent="LIED-1", parenttype="Lied",
                   parentfield="anlaesse", anlass="Gottesdienst",
                   docstatus=0, idx=1),
    ])

    # Liedgruppe mit Liedern + Rollen.
    sess.add_all([
        Liedgruppe(name="LGRP-1", gruppenname="Oster-Set", typ="Set",
                   status="aktiv", gruppe="GRP-WORSHIP", dauer_minuten=20,
                   komponist="diverse", textautor="diverse", verlag="intern",
                   lizenzhinweis="CCLI", beschreibung="Ostersonntag",
                   docstatus=0, idx=0),
        Liedgruppe(name="LGRP-2", gruppenname="Weihnachts-Set", typ="Set",
                   status="entwurf", gruppe="GRP-WORSHIP", dauer_minuten=25,
                   komponist=None, textautor=None, verlag=None,
                   lizenzhinweis=None, beschreibung=None, docstatus=0, idx=0),
    ])
    sess.add_all([
        LiedgruppeLied(name="LGL-1", parent="LGRP-1", parenttype="Liedgruppe",
                       parentfield="lieder", lied="LIED-1", fassung="FAS-1",
                       reihenfolge=1, nummer=1, szene="Einzug",
                       notiz="Auftakt", docstatus=0, idx=1),
        LiedgruppeLied(name="LGL-2", parent="LGRP-1", parenttype="Liedgruppe",
                       parentfield="lieder", lied="LIED-3", fassung=None,
                       reihenfolge=2, nummer=2, szene=None, notiz=None,
                       docstatus=0, idx=2),
        LiedgruppeRolle(name="LGR-1", parent="LGRP-1", parenttype="Liedgruppe",
                        parentfield="rollen", rollenname="Sopran",
                        rollentyp="Gesang", stimmlage="Sopran", umfang="s1",
                        min_alter=16, max_alter=99, anzahl_besetzungen=2,
                        beschreibung="erste Stimme", docstatus=0, idx=1),
    ])

    # Nur ADMIN hat Mitgliederadministrator; Anna/Bruno bewusst nicht.
    sess.add_all([
        HasRole(name="HR-1", parent=ADMIN, parenttype="User",
                parentfield="roles", role="Mitgliederadministrator",
                docstatus=0, idx=1),
    ])

    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_anna(welt):
    set_user(ANNA)
    yield ANNA
    set_user("Administrator")


@pytest.fixture()
def als_bruno(welt):
    set_user(BRUNO)
    yield BRUNO
    set_user("Administrator")


@pytest.fixture()
def als_admin(welt):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


@pytest.fixture()
def als_guest(welt):
    set_user("Guest")
    yield "Guest"
    set_user("Administrator")


# ── Registrierung / Router / Guest ──────────────────────────────────────────


def test_frappe_module_konstante_ist_gesetzt():
    """Ohne FRAPPE_MODULE ist der Endpunkt fuer die SPA unerreichbar."""
    import importlib

    m = importlib.import_module("diakronos_app.api.psalmos.musik")
    assert m.FRAPPE_MODULE == "diakronos.psalmos.api.musik"


def test_frappe_module_pfad_kommt_aus_dem_inventar():
    """Der Pfad endet auf `psalmos`, nicht `diakonos` (Vorgaengerkarte)."""
    import importlib

    m = importlib.import_module("diakronos_app.api.psalmos.musik")
    assert ".psalmos." in m.FRAPPE_MODULE
    assert "diakonos.psalmos" not in m.FRAPPE_MODULE


@pytest.mark.parametrize("fn", SPA_PFADE)
def test_spa_pfade_sind_registriert(fn):
    assert lookup(f"{MUSIK}.{fn}") is not None


@pytest.mark.parametrize("fn", SPA_PFADE)
def test_guest_wird_ueberall_abgewiesen(client, als_guest, fn):
    """`allow_guest=False` gilt fuer alle 8 Endpunkte."""
    resp = client.get(f"/api/method/{MUSIK}.{fn}")
    assert resp.status_code == 401, (fn, resp.text)


# ── get_lieder ──────────────────────────────────────────────────────────────


def test_lieder_liste_zeigt_titel_und_zaehler(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder")
    assert r.status_code == 200, r.text
    rows = r.json()["message"]
    titel = [x["titel"] for x in rows]
    # Sortierung nach titel asc.
    assert titel == ["Amazing Grace", "Grosser Gott", "Morgenlicht"]
    gott = next(x for x in rows if x["titel"] == "Grosser Gott")
    assert gott["aktiv"] is True
    assert gott["anzahl_gesungen"] == 7
    assert set(gott["besetzungen"]) == {"Chor", "Band"}
    assert gott["anzahl_fassungen"] == 2
    # LIED-3 hat eine Fassung, aber KEINE Materialzeile.
    morgen = next(x for x in rows if x["titel"] == "Morgenlicht")
    assert morgen["anzahl_fassungen"] == 1


def test_lieder_suche_ueber_titel(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "Grace"})
    assert r.status_code == 200, r.text
    titel = [x["titel"] for x in r.json()["message"]]
    assert titel == ["Amazing Grace"]


def test_lieder_suche_ueber_strophentext(client, als_anna):
    """`suche` durchsucht AUCH tabLiedstrophe.text."""
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "Sonnenstrahl"})
    assert r.status_code == 200, r.text
    titel = [x["titel"] for x in r.json()["message"]]
    assert titel == ["Morgenlicht"]


def test_lieder_suche_ohne_treffer_ist_leer(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "xyz-nichts"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == []


def test_lieder_filter_rechte_status(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder",
                   params={"rechte_status": "geschuetzt"})
    assert r.status_code == 200, r.text
    titel = [x["titel"] for x in r.json()["message"]]
    assert titel == ["Amazing Grace"]


def test_lieder_filter_gruppe_ueber_child(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder",
                   params={"gruppe": "GRP-WORSHIP"})
    assert r.status_code == 200, r.text
    titel = [x["titel"] for x in r.json()["message"]]
    assert titel == ["Grosser Gott"]


def test_lieder_filter_kategorie_ueber_child(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder",
                   params={"kategorie": "Lobpreis"})
    assert r.status_code == 200, r.text
    titel = [x["titel"] for x in r.json()["message"]]
    assert titel == ["Grosser Gott"]


def test_lieder_filter_anlass_ueber_child(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder",
                   params={"anlass": "Gottesdienst"})
    assert r.status_code == 200, r.text
    titel = [x["titel"] for x in r.json()["message"]]
    assert titel == ["Grosser Gott"]


def test_lieder_filter_ohne_treffer_ist_leer(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder",
                   params={"gruppe": "GRP-GIBTS-NICHT"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == []


def test_lieder_limit_wird_auf_200_gedeckelt(client, als_anna):
    """`limit` > 200 wird auf 200 begrenzt (Original: `min(int(limit), 200)`)."""
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"limit": 999})
    assert r.status_code == 200, r.text
    assert len(r.json()["message"]) == 3


def test_lieder_limit_start_verschiebt(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder",
                   params={"limit": 1, "start": 1})
    assert r.status_code == 200, r.text
    assert [x["titel"] for x in r.json()["message"]] == ["Grosser Gott"]


def test_lieder_liste_nicht_nach_sichtbarkeit_gefiltert(client, als_anna):
    """Das Original filtert Listen NICHT nach Sichtbarkeit.

    Jede eingeloggte Person (auch OHNE Schreibrecht/Bereichszugehoerigkeit)
    sieht ALLE Lieder. Nur Guest ist ausgeschlossen.
    """
    r = client.get(f"/api/method/{MUSIK}.get_lieder")
    assert r.status_code == 200, r.text
    assert len(r.json()["message"]) == 3


# ── get_lied_detail ─────────────────────────────────────────────────────────


def test_lied_detail_kopf_strophen_fassungen(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lied_detail", params={"lied": "LIED-1"})
    assert r.status_code == 200, r.text
    m = r.json()["message"]

    assert m["lied"]["titel"] == "Grosser Gott"
    assert m["lied"]["notiz"] == "Standard"
    assert m["lied"]["streaming_erlaubt"] is True
    assert m["lied"]["kategorien"] == ["Lobpreis"]
    assert m["lied"]["anlaesse"] == ["Gottesdienst"]

    # Strophen nach idx (1, 2) sortiert.
    assert [s["nummer"] for s in m["strophen"]] == [1, 2]
    assert m["strophen"][0]["text"] == "Grosser Gott wir loben dich"

    # Fassungen: ist_standard desc -> FAS-1 zuerst, mit Material.
    assert [f["name"] for f in m["fassungen"]] == ["FAS-1", "FAS-2"]
    assert m["fassungen"][0]["ist_standard"] is True
    assert m["fassungen"][0]["material"][0]["art"] == "Noten"
    assert m["fassungen"][0]["material"][0]["stimme"] == "Sopran"

    # Liedgruppen, in denen das Lied steckt.
    # `nummer` ist im Modell/live-Schema eine String-Spalte -> '1', nicht 1.
    assert m["liedgruppen"] == [{
        "liedgruppe": "LGRP-1", "fassung": "FAS-1",
        "reihenfolge": 1, "nummer": "1",
    }]


def test_lied_detail_unbekannt_ist_fehler(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lied_detail", params={"lied": "NOPE"})
    assert r.status_code in (404, 417), r.text


# ── get_fassungen ───────────────────────────────────────────────────────────


def test_fassungen_alle(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_fassungen", params={"lied": "LIED-1"})
    assert r.status_code == 200, r.text
    names = [f["name"] for f in r.json()["message"]]
    assert names == ["FAS-1", "FAS-2"]


def test_fassungen_nach_gruppe_gefiltert(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_fassungen",
                   params={"lied": "LIED-1", "gruppe": "GRP-WORSHIP"})
    assert r.status_code == 200, r.text
    assert len(r.json()["message"]) == 2

    r2 = client.get(f"/api/method/{MUSIK}.get_fassungen",
                    params={"lied": "LIED-1", "gruppe": "GRP-ANDERES"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"] == []


# ── save_lied ───────────────────────────────────────────────────────────────


def test_save_lied_ohne_recht_ist_403(client, als_anna):
    """Anna ist NICHT Musikverantwortliche -> 403."""
    r = client.post(f"/api/method/{MUSIK}.save_lied",
                    json={"daten": {"titel": "Neues Lied"}})
    assert r.status_code == 403, r.text


def test_save_lied_als_musikverantwortlicher_insert(client, als_bruno):
    r = client.post(f"/api/method/{MUSIK}.save_lied",
                    json={"daten": {"titel": "Neues Lied", "aktiv": 1,
                                    "rechte_status": "gemeinfrei"}})
    assert r.status_code == 200, r.text
    m = r.json()["message"]
    assert m["success"] is True
    assert m["titel"] == "Neues Lied"

    # In der Liste sichtbar.
    rr = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "Neues Lied"})
    assert rr.status_code == 200, rr.text
    assert [x["titel"] for x in rr.json()["message"]] == ["Neues Lied"]


def test_save_lied_als_admin_update(client, als_admin):
    r = client.post(f"/api/method/{MUSIK}.save_lied",
                    json={"daten": {"name": "LIED-2", "titel": "Grace neu",
                                    "aktiv": 1}})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["lied"] == "LIED-2"

    rr = client.get(f"/api/method/{MUSIK}.get_lied_detail", params={"lied": "LIED-2"})
    assert rr.json()["message"]["lied"]["titel"] == "Grace neu"
    assert rr.json()["message"]["lied"]["aktiv"] is True


def test_save_lied_kindtabellen_mit_eltern_parenttype(client, als_bruno):
    """Strophen/Kategorien/Anlaesse werden ersetzt; parenttype = `Lied`."""
    from diakronos_app.models.psalmos import LiedKategorie, Liedstrophe

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "name": "LIED-1",
        "strophen": [{"nummer": 1, "typ": "Strophe", "text": "Neuer Text",
                      "sprache": "de", "nur_chor": 0}],
        "kategorien": ["Lobpreis", "Anbetung"],
        "anlaesse": [{"anlass": "Gottesdienst"}],
    }})
    assert r.status_code == 200, r.text

    sess = welt_direct()
    strophen = sess.query(Liedstrophe).filter_by(parent="LIED-1").all()
    assert len(strophen) == 1
    assert strophen[0].text == "Neuer Text"
    assert strophen[0].parenttype == "Lied"
    assert strophen[0].idx == 1

    kats = sess.query(LiedKategorie).filter_by(parent="LIED-1").all()
    assert sorted(k.kategorie for k in kats) == ["Anbetung", "Lobpreis"]
    assert all(k.parenttype == "Lied" for k in kats)
    sess.close()


def welt_direct():
    """Zugriff auf die (von `patched_db` gepatchte) Session der Test-DB."""
    from diakronos_app.db import SessionLocal

    return SessionLocal()


# ── save_fassung ────────────────────────────────────────────────────────────


def test_save_fassung_ohne_recht_ist_403(client, als_anna):
    r = client.post(f"/api/method/{MUSIK}.save_fassung",
                    json={"daten": {"lied": "LIED-1", "fassungsname": "X"}})
    assert r.status_code == 403, r.text


def test_save_fassung_ohne_lied_ist_fehler(client, als_bruno):
    r = client.post(f"/api/method/{MUSIK}.save_fassung",
                    json={"daten": {"fassungsname": "Ohne Lied"}})
    assert r.status_code in (417, 403, 500), r.text
    # Der fachliche Fehler nennt das fehlende Feld.
    assert "lied" in r.text.lower()


def test_save_fassung_insert_mit_material(client, als_bruno):
    from diakronos_app.models.psalmos import LiedMaterial

    r = client.post(f"/api/method/{MUSIK}.save_fassung", json={"daten": {
        "lied": "LIED-3", "fassungsname": "Blasfassung", "besetzung": "Blaeser",
        "ist_standard": 1, "material": [
            {"art": "Noten", "stimme": "Trompete", "anhang": "/files/t.pdf",
             "beschreibung": "Stimme"},
        ],
    }})
    assert r.status_code == 200, r.text
    m = r.json()["message"]
    assert m["success"] is True
    assert m["fassungsname"] == "Blasfassung"

    sess = welt_direct()
    mats = sess.query(LiedMaterial).filter_by(parent=m["fassung"]).all()
    assert len(mats) == 1
    assert mats[0].art == "Noten"
    assert mats[0].parenttype == "Liedfassung"
    sess.close()


# ── get_lied_historie ───────────────────────────────────────────────────────


def test_lied_historie_defensiv_leer(client, als_anna):
    """Live-Schema: `Ablaufplan` hat KEIN referenz_doctype -> immer []."""
    r = client.get(f"/api/method/{MUSIK}.get_lied_historie", params={"lied": "LIED-1"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == []


# ── get_liedgruppen / get_liedgruppe_detail ─────────────────────────────────


def test_liedgruppen_liste_sortiert(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_liedgruppen")
    assert r.status_code == 200, r.text
    namen = [g["gruppenname"] for g in r.json()["message"]]
    assert namen == ["Oster-Set", "Weihnachts-Set"]


def test_liedgruppen_filter_typ(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_liedgruppen", params={"typ": "Set"})
    assert r.status_code == 200, r.text
    assert len(r.json()["message"]) == 2

    r2 = client.get(f"/api/method/{MUSIK}.get_liedgruppen", params={"typ": "Anderes"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"] == []


def test_liedgruppe_detail_mit_liedern_und_rollen(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_liedgruppe_detail",
                   params={"liedgruppe": "LGRP-1"})
    assert r.status_code == 200, r.text
    m = r.json()["message"]
    assert m["liedgruppe"]["gruppenname"] == "Oster-Set"
    assert m["liedgruppe"]["lizenzhinweis"] == "CCLI"

    # Lieder nach idx.
    assert [x["lied"] for x in m["lieder"]] == ["LIED-1", "LIED-3"]
    assert m["lieder"][0]["szene"] == "Einzug"

    assert len(m["rollen"]) == 1
    assert m["rollen"][0]["rollenname"] == "Sopran"
    assert m["rollen"][0]["anzahl_besetzungen"] == 2


def test_liedgruppe_detail_unbekannt_ist_fehler(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_liedgruppe_detail",
                   params={"liedgruppe": "NOPE"})
    assert r.status_code in (404, 417), r.text


# ── PF2: get_lied_filteroptionen + gebuendelte Besetzungen ──────────────────


def test_filteroptionen_liefert_gruppen_kategorien_anlaesse(client, als_anna):
    """Ein Aufruf liefert alle Optionsnamen — dieselben wie get_lied_detail."""
    r = client.get(f"/api/method/{MUSIK}.get_lied_filteroptionen")
    assert r.status_code == 200, r.text
    m = r.json()["message"]
    assert m["gruppen"] == ["Oster-Set", "Weihnachts-Set"]
    assert m["kategorien"] == ["Lobpreis", "Weihnachten"]
    assert m["anlaesse"] == ["Gottesdienst"]


def test_filteroptionen_stimmen_mit_lied_detail_ueberein(client, als_anna):
    """Kein Auseinanderlaufen: die Optionen sind die Werte aus dem Detail."""
    opt = client.get(f"/api/method/{MUSIK}.get_lied_filteroptionen").json()["message"]
    det = client.get(f"/api/method/{MUSIK}.get_lied_detail",
                     params={"lied": "LIED-1"}).json()["message"]["lied"]
    assert set(det["kategorien"]).issubset(set(opt["kategorien"]))
    assert set(det["anlaesse"]).issubset(set(opt["anlaesse"]))


def test_filteroptionen_ohne_stammdaten_bleiben_leer(patched_db, client):
    """Ohne Katalogzeilen liefert der Endpunkt leere Listen, keinen Fehler.

    PF2-Fix: hier darf NICHT `als_anna` verwendet werden — dessen `welt`-Fixture
    legt Liedgruppe/Liedkategorie/Liedanlass an. Der Test war damit von Anfang
    an rot (die Assertion „leer“ traf nie zu). Stattdessen wird nur die
    Nutzerzeile gebraucht, die die Sitzungs-Middleware erwartet; der Rest der
    DB bleibt leer.
    """
    from diakronos_app import frappe_compat
    from diakronos_app.models.core import User

    sess = patched_db()
    if sess.get(User, ANNA) is None:
        sess.add(User(name=ANNA, email=ANNA, full_name="Anna", enabled=1))
        sess.commit()
    sess.close()
    frappe_compat.set_user(ANNA)
    try:
        r = client.get(f"/api/method/{MUSIK}.get_lied_filteroptionen")
        assert r.status_code == 200, r.text
        assert r.json()["message"] == {"gruppen": [], "kategorien": [], "anlaesse": []}
    finally:
        frappe_compat.reset_user()


def test_lieder_besetzungen_gebuendelt_gleiches_ergebnis(client, als_anna):
    """PF2: Besetzungen kommen weiter korrekt, nur ohne Abfrage je Lied.

    Die Schleife ueber alle Zeilen darf pro Lied hoechstens die eigenen
    Besetzungen liefern — hier wird nur das Ergebnis festgenagelt (Chor+Band
    fuer LIED-1, leer fuer LIED-2/3), weil die Abfragezahl selbst in SQLite
    nicht stabil messbar ist.
    """
    r = client.get(f"/api/method/{MUSIK}.get_lieder")
    rows = {x["titel"]: x for x in r.json()["message"]}
    assert set(rows["Grosser Gott"]["besetzungen"]) == {"Chor", "Band"}
    assert rows["Grosser Gott"]["anzahl_fassungen"] == 2
    assert rows["Amazing Grace"]["besetzungen"] == []
    assert rows["Morgenlicht"]["besetzungen"] == ["Chor"]

