"""P4f — Portierte Module `api.beitraege` (6 Endpunkte) und `api.wiki` (7 Endpunkte).

Quelle (READ-ONLY):
  * `referenz/diakronos-frappe/diakronos/diakonos/api/beitraege.py`
  * `referenz/diakronos-frappe/diakronos/diakonos/api/wiki.py`

Abgedeckt:
  * Registrierung: `FRAPPE_MODULE` gesetzt, alle 13 SPA-Pfade aufloesbar.
  * Login-Pflicht (`allow_guest=False`) fuer jeden Endpunkt -> Guest = 403.
  * `get_beitraege_liste`: nur Veroeffentlichtes, Kategorie-Filter, Suche,
    Kommentarzaehler.
  * `get_beitrag_detail`: Inhalt + Kommentarliste, unbekannt -> Fehler.
  * `create_beitrag` / `update_beitrag` / `delete_beitrag`: Adminpflicht (403),
    Feldpflege, Loeschen.
  * `create_kommentar`: Leertext -> Fehler, Kindzeile unter `kommentare`.
  * `get_wiki_artikel_liste`: Kategorie-Filter, Suche ueber Titel/Auszug/Tags,
    Tag-Aufteilung, `isNew`.
  * `get_wiki_artikel_detail`: Inhalt, unbekannt -> Fehler.
  * `create_wiki_artikel` / `update_wiki_artikel` / `delete_wiki_artikel`:
    Adminpflicht (403), Feldpflege, `ist_neu`-Setzung, Loeschen.
  * `get_wiki_kategorien`: statische 5er-Liste (NICHT aus der DB).
  * `get_wiki_tags`: nur nicht-leere Tag-Felder, dedupliziert, sortiert.
  * Schema-Belege: `Wiki Artikel` hat keine `gruppe`-Spalte; es gibt keine
    Bereichs-/Rollenfilterung (Dokumentation der Karten-Anforderung).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

BEITRAEGE = "diakronos.diakonos.api.beitraege"
WIKI = "diakronos.diakonos.api.wiki"

# Die 6 in hooks.py:133-138 gelisteten Originalpfade.
SPA_PFADE_BEITRAEGE = [
    "get_beitraege_liste",
    "get_beitrag_detail",
    "create_beitrag",
    "update_beitrag",
    "delete_beitrag",
    "create_kommentar",
]

# Die 7 in hooks.py:140-146 gelisteten Originalpfade.
SPA_PFADE_WIKI = [
    "get_wiki_artikel_liste",
    "get_wiki_artikel_detail",
    "create_wiki_artikel",
    "update_wiki_artikel",
    "delete_wiki_artikel",
    "get_wiki_kategorien",
    "get_wiki_tags",
]

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
ADMIN = "admin@example.org"


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Zwei Beitraege (1 oeffentlich, 1 Entwurf), 2 Wiki-Artikel, 1 Admin."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Beitrag, BeitragKommentar, WikiArtikel

    sess = patched_db()

    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=1),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
    ])

    sess.add_all([
        Beitrag(name="BEI-1", titel="Sommerfest", kategorie="gemeinde",
                datum=date(2026, 7, 1), autor="Anna Beispiel", autor_email=ANNA,
                veroeffentlicht=1, auszug="Grosses Fest im Hof",
                inhalt="<p>Alle sind eingeladen.</p>", bild="fest.jpg",
                docstatus=0, idx=0),
        Beitrag(name="BEI-2", titel="Interner Entwurf", kategorie="gemeinde",
                datum=date(2026, 7, 2), autor="Bruno Beispiel", autor_email=BRUNO,
                veroeffentlicht=0, auszug="Noch nicht fertig",
                inhalt="<p>Entwurfstext</p>", bild=None,
                docstatus=0, idx=0),
        # Zweiter oeffentlicher Beitrag: macht den Gruppierungsfilter pruefbar.
        Beitrag(name="BEI-3", titel="Jugendtreff", kategorie="jugend",
                datum=date(2026, 7, 3), autor="Anna Beispiel", autor_email=ANNA,
                veroeffentlicht=1, auszug="Jeden Freitag",
                inhalt="<p>Jugendtreff</p>", bild=None,
                docstatus=0, idx=0),
    ])

    sess.add_all([
        BeitragKommentar(name="BK-1", parent="BEI-1", parenttype="Beitrag",
                         parentfield="kommentare", autor="Bruno Beispiel",
                         autor_email=BRUNO, text="Super Sache!", datum=date(2026, 6, 1),
                         docstatus=0, idx=1),
        BeitragKommentar(name="BK-2", parent="BEI-1", parenttype="Beitrag",
                         parentfield="kommentare", autor="Anna Beispiel",
                         autor_email=ANNA, text="Freu mich.", datum=date(2026, 6, 2),
                         docstatus=0, idx=2),
    ])

    sess.add_all([
        WikiArtikel(name="WIK-1", titel="Beamer bedienen", kategorie="technik",
                    tags="beamer, technik, licht", autor="Anna Beispiel",
                    autor_email=ANNA, ist_neu=1, auszug="Kurzanleitung Beamer",
                    inhalt="<p>Schritt 1 bis 5</p>", docstatus=0, idx=0),
        WikiArtikel(name="WIK-2", titel="Schluesselausgabe", kategorie="ablaeufe",
                    tags="schluessel, ablauf", autor="Bruno Beispiel",
                    autor_email=BRUNO, ist_neu=0, auszug="Wer gibt Schluessel aus",
                    inhalt="<p>Ablaufbeschreibung</p>", docstatus=0, idx=0),
        # Leeres Tag-Feld -> darf in get_wiki_tags nicht auftauchen.
        WikiArtikel(name="WIK-3", titel="Ohne Tags", kategorie="faq",
                    tags="", autor="Anna Beispiel", autor_email=ANNA,
                    ist_neu=0, auszug="Ohne Tags", inhalt="<p>-</p>",
                    docstatus=0, idx=0),
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
def als_admin(welt):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


@pytest.fixture()
def als_guest(welt):
    set_user("Guest")
    yield "Guest"
    set_user("Administrator")


# ── Registrierung / Router ──────────────────────────────────────────────────


@pytest.mark.parametrize("modul,erwartet", [(BEITRAEGE, "api.beitraege"),
                                            (WIKI, "api.wiki")])
def test_frappe_module_konstante_ist_gesetzt(modul, erwartet):
    """Ohne FRAPPE_MODULE ist der Endpunkt fuer die SPA unerreichbar."""
    import importlib

    m = importlib.import_module(f"diakronos_app.{erwartet}")
    assert m.FRAPPE_MODULE == modul


@pytest.mark.parametrize("fn", SPA_PFADE_BEITRAEGE)
def test_beitraege_spa_pfade_sind_registriert(fn):
    assert lookup(f"{BEITRAEGE}.{fn}") is not None


@pytest.mark.parametrize("fn", SPA_PFADE_WIKI)
def test_wiki_spa_pfade_sind_registriert(fn):
    assert lookup(f"{WIKI}.{fn}") is not None


@pytest.mark.parametrize("modul,fn", [(BEITRAEGE, f) for f in SPA_PFADE_BEITRAEGE]
                         + [(WIKI, f) for f in SPA_PFADE_WIKI])
def test_guest_wird_ueberall_abgewiesen(client, als_guest, modul, fn):
    """`allow_guest=False` gilt fuer alle 13 Endpunkte."""
    resp = client.get(f"/api/method/{modul}.{fn}")
    assert resp.status_code == 401, (modul, fn, resp.text)


# ── get_beitraege_liste ─────────────────────────────────────────────────────


def test_beitraege_liste_zeigt_nur_veroeffentlichte(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    assert r.status_code == 200, r.text
    ids = [b["id"] for b in r.json()["message"]]
    assert set(ids) == {"BEI-1", "BEI-3"}
    assert "BEI-2" not in ids  # veroeffentlicht=0


def test_beitraege_liste_antwortform(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    b = {x["id"]: x for x in r.json()["message"]}["BEI-1"]

    assert b["title"] == "Sommerfest"
    assert b["excerpt"] == "Grosses Fest im Hof"
    assert b["category"] == "gemeinde"
    assert b["image"] == "fest.jpg"
    assert b["author"] == "Anna Beispiel"
    assert b["date"] == "2026-07-01"
    assert b["comments"] == 2


def test_beitraege_liste_filtert_nach_kategorie(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste",
                   params={"kategorie": "jugend"})
    assert [b["id"] for b in r.json()["message"]] == ["BEI-3"]


def test_beitraege_liste_suche_ueber_titel_auszug_autor(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste",
                   params={"search": "sommer"})
    assert [b["id"] for b in r.json()["message"]] == ["BEI-1"]

    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste",
                   params={"search": "jeden freitag"})
    assert [b["id"] for b in r.json()["message"]] == ["BEI-3"]

    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste",
                   params={"search": "gibtsnicht"})
    assert r.json()["message"] == []


def test_beitraege_liste_hat_keine_bereichsfilterung_belegt(client, als_anna, welt):
    """DOKUMENTATION: das Original filtert NICHT auf Bereich/Gruppe.

    Die Karte fragt ausdruecklich nach der Sichtbarkeitsregel. `beitraege.py`
    kennt weder `check_permission` noch `ancestor_path`; einziger Filter ist
    `veroeffentlicht = 1`. Dieser Test haelt das fest, damit ein spaeterer
    Zusatzfilter nicht unbemerkt die SPA-Sicht aendert: BEI-1 und BEI-3
    gehoeren keinem Bereich an und sind trotzdem sichtbar.
    """
    from diakronos_app.models.diakonos import Beitrag

    assert not hasattr(Beitrag, "bereich")
    assert not hasattr(Beitrag, "gruppe")

    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    assert len(r.json()["message"]) == 2


def test_beitraege_liste_sortiert_nach_datum_absteigend(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    daten = [b["date"] for b in r.json()["message"]]
    assert daten == sorted(daten, reverse=True)


# ── get_beitrag_detail ──────────────────────────────────────────────────────


def test_beitrag_detail_mit_inhalt_und_kommentaren(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitrag_detail",
                   params={"beitrag_id": "BEI-1"})
    assert r.status_code == 200, r.text
    b = r.json()["message"]

    assert b["id"] == "BEI-1"
    assert b["content"] == "<p>Alle sind eingeladen.</p>"
    assert b["comments"] == 2
    assert [k["id"] for k in b["commentList"]] == ["BK-1", "BK-2"]
    assert b["commentList"][0]["author"] == "Bruno Beispiel"
    assert b["commentList"][0]["avatar"] == "BB"
    assert b["commentList"][0]["text"] == "Super Sache!"
    assert b["commentList"][0]["date"] == "2026-06-01"


def test_beitrag_detail_avatar_initialen_zweier_woerter(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitrag_detail",
                   params={"beitrag_id": "BEI-1"})
    assert r.json()["message"]["commentList"][1]["avatar"] == "AB"


def test_beitrag_detail_unbekannt_liefert_fehler(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitrag_detail",
                   params={"beitrag_id": "GIBTSNICHT"})
    assert r.status_code >= 400


# ── create / update / delete beitrag ────────────────────────────────────────


def test_create_beitrag_nur_admin(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.create_beitrag",
                   params={"titel": "Neu", "inhalt": "<p>x</p>"})
    assert r.status_code == 403, r.text


def test_create_beitrag_legt_veroeffentlichten_beitrag_an(client, als_admin, welt):
    r = client.get(f"/api/method/{BEITRAEGE}.create_beitrag",
                   params={"titel": "  Neuer Beitrag  ", "inhalt": "<p>Text</p>",
                           "kategorie": "technik", "auszug": "  Kurz  ",
                           "bild": "neu.jpg"})
    assert r.status_code == 200, r.text
    neu = r.json()["message"]["beitrag_id"]

    from diakronos_app.models.diakonos import Beitrag

    b = welt.get(Beitrag, neu)
    assert b is not None
    assert b.titel == "Neuer Beitrag"       # getrimmt
    assert b.auszug == "Kurz"               # getrimmt
    assert b.kategorie == "technik"
    assert b.bild == "neu.jpg"
    assert b.inhalt == "<p>Text</p>"
    assert b.veroeffentlicht is True        # immer 1
    assert b.autor == "Ada Admin"           # full_name
    assert b.autor_email == ADMIN


def test_create_beitrag_ohne_bild_setzt_null(client, als_admin, welt):
    r = client.get(f"/api/method/{BEITRAEGE}.create_beitrag",
                   params={"titel": "Ohne Bild", "inhalt": "<p>x</p>"})
    neu = r.json()["message"]["beitrag_id"]

    from diakronos_app.models.diakonos import Beitrag

    assert welt.get(Beitrag, neu).bild is None


def test_create_beitrag_erscheint_sofort_in_der_liste(client, als_admin):
    """Belegt: Erstanlage landet direkt in der Liste (veroeffentlicht=1)."""
    client.get(f"/api/method/{BEITRAEGE}.create_beitrag",
               params={"titel": "Frisch", "inhalt": "<p>x</p>"})
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    assert "Frisch" in [b["title"] for b in r.json()["message"]]


def test_update_beitrag_nur_admin(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.update_beitrag",
                   params={"beitrag_id": "BEI-1", "titel": "Geaendert"})
    assert r.status_code == 403, r.text


def test_update_beitrag_schreibt_nur_gesetzte_felder(client, als_admin, welt):
    r = client.get(f"/api/method/{BEITRAEGE}.update_beitrag",
                   params={"beitrag_id": "BEI-1", "titel": "  Sommerfest 2026  ",
                           "kategorie": "jugend"})
    assert r.status_code == 200, r.text

    from diakronos_app.models.diakonos import Beitrag

    b = welt.get(Beitrag, "BEI-1")
    assert b.titel == "Sommerfest 2026"   # getrimmt
    assert b.kategorie == "jugend"
    assert b.inhalt == "<p>Alle sind eingeladen.</p>"  # unberuehrt


def test_delete_beitrag_nur_admin(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.delete_beitrag",
                   params={"beitrag_id": "BEI-1"})
    assert r.status_code == 403, r.text


def test_delete_beitrag_entfernt_zeile(client, als_admin, welt):
    r = client.get(f"/api/method/{BEITRAEGE}.delete_beitrag",
                   params={"beitrag_id": "BEI-1"})
    assert r.status_code == 200, r.text

    from diakronos_app.models.diakonos import Beitrag

    assert welt.get(Beitrag, "BEI-1") is None


# ── create_kommentar ────────────────────────────────────────────────────────


def test_create_kommentar_legt_kindzeile_an(client, als_anna, welt):
    r = client.get(f"/api/method/{BEITRAEGE}.create_kommentar",
                   params={"beitrag_id": "BEI-1", "text": "  Toll!  "})
    assert r.status_code == 200, r.text
    k = r.json()["message"]["kommentar"]

    assert k["author"] == "Anna Beispiel"
    assert k["avatar"] == "AB"
    assert k["text"] == "Toll!"            # getrimmt
    assert k["date"] == date.today().isoformat()

    from diakronos_app.models.diakonos import BeitragKommentar

    zeile = welt.get(BeitragKommentar, k["id"])
    assert zeile is not None
    assert zeile.parent == "BEI-1"
    assert zeile.parentfield == "kommentare"   # Frappe-Kindtabelle
    assert zeile.parenttype == "Beitrag"
    assert zeile.autor_email == ANNA


def test_create_kommentar_zaehlt_in_der_liste_hoch(client, als_anna):
    client.get(f"/api/method/{BEITRAEGE}.create_kommentar",
               params={"beitrag_id": "BEI-3", "text": "Erster!"})
    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    b = {x["id"]: x for x in r.json()["message"]}["BEI-3"]
    assert b["comments"] == 1


def test_create_kommentar_leertext_wird_abgelehnt(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.create_kommentar",
                   params={"beitrag_id": "BEI-1", "text": "   "})
    assert r.status_code >= 400, r.text


def test_create_kommentar_unbekannter_beitrag(client, als_anna):
    r = client.get(f"/api/method/{BEITRAEGE}.create_kommentar",
                   params={"beitrag_id": "GIBTSNICHT", "text": "Hallo"})
    assert r.status_code >= 400, r.text


# ── Wiki: get_wiki_artikel_liste ────────────────────────────────────────────


def test_wiki_liste_antwortform(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste")
    assert r.status_code == 200, r.text
    a = {x["id"]: x for x in r.json()["message"]}["WIK-1"]

    assert a["title"] == "Beamer bedienen"
    assert a["excerpt"] == "Kurzanleitung Beamer"
    assert a["category"] == "technik"
    assert a["tags"] == ["beamer", "technik", "licht"]
    assert a["author"] == "Anna Beispiel"
    assert a["authorAvatar"] == "AB"
    assert a["isNew"] is True
    assert a["updatedAt"] == ""            # modified ist NULL -> Leerstring


def test_wiki_liste_zeigt_alle_kategorien(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste")
    assert {a["id"] for a in r.json()["message"]} == {"WIK-1", "WIK-2", "WIK-3"}


def test_wiki_liste_filtert_nach_kategorie(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste",
                   params={"kategorie": "faq"})
    assert [a["id"] for a in r.json()["message"]] == ["WIK-3"]


def test_wiki_liste_suche_ueber_titel_auszug_tags(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste",
                   params={"search": "beamer"})
    assert [a["id"] for a in r.json()["message"]] == ["WIK-1"]

    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste",
                   params={"search": "schluesselausgabe"})
    assert [a["id"] for a in r.json()["message"]] == ["WIK-2"]

    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste",
                   params={"search": "ablauf"})   # Treffer nur im Tag-Feld
    assert [a["id"] for a in r.json()["message"]] == ["WIK-2"]

    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste",
                   params={"search": "gibtsnicht"})
    assert r.json()["message"] == []


def test_wiki_liste_tag_aufteilung_trimmt_leerraeume(client, als_anna, welt):
    from diakronos_app.models.diakonos import WikiArtikel

    a = welt.get(WikiArtikel, "WIK-2")
    a.tags = " a ,, b , c "
    welt.commit()

    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste",
                   params={"kategorie": "ablaeufe"})
    assert r.json()["message"][0]["tags"] == ["a", "b", "c"]


def test_wiki_liste_hat_keine_gruppe_spalte(client, als_anna, welt):
    """DOKUMENTATION: `tabWiki Artikel` kennt keine `gruppe`-Spalte.

    Die Karte erwaehnt einen `has_column(..., "gruppe")`-Zweig. Der existiert
    in `wiki.py` nicht — belegt per Schema-Abfrage (nicht angenommen) und
    per Attributpruefung am Modell. Waere er da, haetten die Antworten
    zusaetzlich ein `gruppe`-Feld.
    """
    from diakronos_app.models.diakonos import WikiArtikel

    spalten = {row[1] for row in welt.execute(text("PRAGMA table_info(wiki_artikel)"))}
    assert "gruppe" not in spalten
    assert not hasattr(WikiArtikel, "gruppe")

    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste")
    assert "gruppe" not in r.json()["message"][0]


def test_wiki_liste_sichtbarkeit_ohne_bereichsfilter(client, als_anna, welt):
    """DOKUMENTATION: auch das Wiki filtert NICHT auf Bereich/Gruppe.

    Einziger Filter ist die optionale `kategorie`. Alle drei Artikel sind
    ohne Bereichszugehoerigkeit sichtbar — dieselbe Regel wie in `beitraege`.
    """
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_liste")
    assert len(r.json()["message"]) == 3


# ── Wiki: get_wiki_artikel_detail ───────────────────────────────────────────


def test_wiki_detail_mit_inhalt(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_detail",
                   params={"artikel_id": "WIK-1"})
    assert r.status_code == 200, r.text
    a = r.json()["message"]

    assert a["id"] == "WIK-1"
    assert a["content"] == "<p>Schritt 1 bis 5</p>"
    assert a["tags"] == ["beamer", "technik", "licht"]
    assert a["isNew"] is True


def test_wiki_detail_unbekannt_liefert_fehler(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_artikel_detail",
                   params={"artikel_id": "GIBTSNICHT"})
    assert r.status_code >= 400


# ── Wiki: create / update / delete ──────────────────────────────────────────


def test_create_wiki_nur_admin(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.create_wiki_artikel",
                   params={"titel": "Neu", "inhalt": "<p>x</p>"})
    assert r.status_code == 403, r.text


def test_create_wiki_legt_artikel_an(client, als_admin, welt):
    r = client.get(f"/api/method/{WIKI}.create_wiki_artikel",
                   params={"titel": "  Neuer Artikel  ", "inhalt": "<p>Text</p>",
                           "kategorie": "raeume", "tags": "  raum, gross  ",
                           "auszug": "  Kurz  "})
    assert r.status_code == 200, r.text
    neu = r.json()["message"]["artikel_id"]

    from diakronos_app.models.diakonos import WikiArtikel

    a = welt.get(WikiArtikel, neu)
    assert a.titel == "Neuer Artikel"
    assert a.auszug == "Kurz"
    assert a.tags == "raum, gross"
    assert a.kategorie == "raeume"
    assert a.ist_neu is True         # immer 1 bei Anlage
    assert a.autor == "Ada Admin"
    assert a.autor_email == ADMIN


def test_update_wiki_nur_admin(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.update_wiki_artikel",
                   params={"artikel_id": "WIK-1", "titel": "Geaendert"})
    assert r.status_code == 403, r.text


def test_update_wiki_schreibt_gesetzte_felder(client, als_admin, welt):
    r = client.get(f"/api/method/{WIKI}.update_wiki_artikel",
                   params={"artikel_id": "WIK-1", "titel": "Beamer 2.0",
                           "ist_neu": 0})
    assert r.status_code == 200, r.text

    from diakronos_app.models.diakonos import WikiArtikel

    a = welt.get(WikiArtikel, "WIK-1")
    assert a.titel == "Beamer 2.0"
    assert a.ist_neu is False
    assert a.inhalt == "<p>Schritt 1 bis 5</p>"   # unberuehrt


def test_delete_wiki_nur_admin(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.delete_wiki_artikel",
                   params={"artikel_id": "WIK-1"})
    assert r.status_code == 403, r.text


def test_delete_wiki_entfernt_zeile(client, als_admin, welt):
    r = client.get(f"/api/method/{WIKI}.delete_wiki_artikel",
                   params={"artikel_id": "WIK-1"})
    assert r.status_code == 200, r.text

    from diakronos_app.models.diakonos import WikiArtikel

    assert welt.get(WikiArtikel, "WIK-1") is None


# ── Wiki: get_wiki_kategorien / get_wiki_tags ───────────────────────────────


def test_wiki_kategorien_ist_statische_fuenferliste(client, als_anna):
    """Die Liste ist im Original fest verdrahtet — NICHT aus der DB."""
    r = client.get(f"/api/method/{WIKI}.get_wiki_kategorien")
    assert r.status_code == 200, r.text
    kats = r.json()["message"]

    assert [k["id"] for k in kats] == ["technik", "ablaeufe", "raeume", "kontakte", "faq"]
    assert kats[0] == {"id": "technik", "name": "Technik", "icon": "🔧"}
    assert kats[1]["name"] == "Abläufe"
    assert kats[4]["icon"] == "❓"


def test_wiki_tags_nur_nicht_leere_dedupliziert_sortiert(client, als_anna):
    r = client.get(f"/api/method/{WIKI}.get_wiki_tags")
    assert r.status_code == 200, r.text

    tags = r.json()["message"]
    # WIK-3 hat tags="" -> traegt nichts bei.
    assert tags == sorted(set(["beamer", "technik", "licht", "schluessel", "ablauf"]))
    assert "" not in tags


def test_wiki_tags_bei_leerer_datenlage(client, als_anna, welt):
    from diakronos_app.models.diakonos import WikiArtikel

    for name in ("WIK-1", "WIK-2"):
        welt.get(WikiArtikel, name).tags = ""
    welt.commit()

    r = client.get(f"/api/method/{WIKI}.get_wiki_tags")
    assert r.json()["message"] == []


# ── PostgreSQL-Regression: Boolean-Spalten in Filtern ───────────────────────
#
# `veroeffentlicht` (Beitrag) und `ist_neu` (Wiki Artikel) sind in PostgreSQL
# echte `boolean`-Spalten, nicht `int`. Der Altcode uebergibt die
# Frappe-ueblichen `0`/`1`-Werte; PostgreSQL bricht das mit
#   operator does not exist: boolean = integer
# ab (SQLite vergleicht tolerant, deshalb faellt es nur live auf — gefunden
# per HTTP-Probe gegen den echten Container, nicht im Testlauf).
# Gefixt in `_shared._coerce` / `_shared._coerce_filters`.


def test_coerce_wandelt_boolean_zahlen():
    """`_coerce` macht aus 0/1 echte bools, wenn die Spalte boolean ist."""
    from diakronos_app.frappe_compat.api_helpers import _coerce

    assert _coerce("Beitrag", {"veroeffentlicht": 1})["veroeffentlicht"] is True
    assert _coerce("Beitrag", {"veroeffentlicht": 0})["veroeffentlicht"] is False
    assert _coerce("Wiki Artikel", {"ist_neu": 1})["ist_neu"] is True
    assert _coerce("Wiki Artikel", {"ist_neu": 0})["ist_neu"] is False
    # Strings aus dem Request ebenso.
    assert _coerce("Beitrag", {"veroeffentlicht": "1"})["veroeffentlicht"] is True
    assert _coerce("Beitrag", {"veroeffentlicht": "0"})["veroeffentlicht"] is False
    # Nicht-Boolean-Spalten bleiben unberuehrt.
    assert _coerce("Beitrag", {"kategorie": "gemeinde"})["kategorie"] == "gemeinde"


def test_coerce_filters_haelt_operatoren_und_wandelt_werte():
    """`_coerce_filters` wandelt Werte, laesst Operatoren aber stehen."""
    from diakronos_app.frappe_compat.api_helpers import _coerce_filters

    assert _coerce_filters("Beitrag", {"veroeffentlicht": 1}) == {"veroeffentlicht": True}
    assert _coerce_filters("Wiki Artikel", {"ist_neu": 0}) == {"ist_neu": False}

    # Operator-Formen bleiben Operator-Formen.
    f = _coerce_filters("Wiki Artikel", {"tags": ["!=", ""]})
    assert f == {"tags": ["!=", ""]}


def test_beitraege_liste_filter_ist_boolean_typisiert(client, als_anna, welt):
    """Der Listenfilter wird als bool gebunden (PG: boolean = boolean)."""
    from diakronos_app.frappe_compat.query import _compile_filters
    from diakronos_app.frappe_compat.api_helpers import _coerce_filters

    gefiltert = _coerce_filters("Beitrag", {"veroeffentlicht": 1})
    assert gefiltert["veroeffentlicht"] is True
    # Der Compiler muss daraus eine Klausel bauen koennen (kein TypeError).
    from diakronos_app.frappe_compat.registry_gen import model_for

    klauseln = _compile_filters("Beitrag", model_for("Beitrag"), gefiltert)
    assert klauseln


def test_veroeffentlicht_entwurf_bleibt_unsichtbar_auch_mit_bool(client, als_anna, welt):
    """Gegenprobe: Entwurf bleibt draussen, egal ob 0/False im Datensatz steht."""
    from diakronos_app.models.diakonos import Beitrag

    b = welt.get(Beitrag, "BEI-2")
    assert b.veroeffentlicht is False

    r = client.get(f"/api/method/{BEITRAEGE}.get_beitraege_liste")
    assert "BEI-2" not in [x["id"] for x in r.json()["message"]]


def test_create_beitrag_setzt_boolean_veroeffentlicht(client, als_admin, welt):
    """Anlage setzt `veroeffentlicht` als echten bool-Wert."""
    from diakronos_app.models.diakonos import Beitrag

    r = client.get(f"/api/method/{BEITRAEGE}.create_beitrag",
                   params={"titel": "Bool-Test", "inhalt": "<p>x</p>"})
    neu = r.json()["message"]["beitrag_id"]
    assert welt.get(Beitrag, neu).veroeffentlicht is True


def test_create_wiki_setzt_boolean_ist_neu(client, als_admin, welt):
    """Anlage setzt `ist_neu` als echten bool-Wert."""
    from diakronos_app.models.diakonos import WikiArtikel

    r = client.get(f"/api/method/{WIKI}.create_wiki_artikel",
                   params={"titel": "Bool-Wiki", "inhalt": "<p>x</p>"})
    neu = r.json()["message"]["artikel_id"]
    assert welt.get(WikiArtikel, neu).ist_neu is True
