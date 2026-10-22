"""P1-10b Befund 7 — Dublettenschutz serverseitig.

Reproduktion des offen gefuehrten Befunds aus dem vorausgehenden Review:

  Befund 7  Der Dublettenschutz lag nur im Frontend (Warnung vor dem Anlegen).
            Ein zweiter Aufruf, ein alter SPA-Stand oder ein direkter API-Aufruf
            konnte dasselbe Lied beliebig oft anlegen.

Erwartung nach der Behebung:
  * Anlegen ohne `name` mit gleichem Titel (ohne Gross-/Kleinschreibung) oder
    gleicher Buch+Nummer -> 417 mit verstaendlicher Meldung, KEIN neues Lied.
  * Mit `dublette_bestaetigt` bleibt das bewusste Doppel moeglich.
  * Ein Aendern (`name` uebergeben) loest die Pruefung NICHT aus.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.session import set_user

MUSIK = "diakronos.psalmos.api.musik"

BRUNO = "bruno@example.org"  # Verantwortlicher im Dienstbereich Musik und Worship


@pytest.fixture()
def welt(patched_db):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        Gruppe,
        GruppeVerantwortlicher,
    )
    from diakronos_app.models.psalmos import Lied

    sess = patched_db()
    sess.add_all([
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        Dienstbereich(name="Musik und Worship", ministry="Musik und Worship",
                      docstatus=0, idx=0),
        Gruppe(name="GRP-WORSHIP", gruppenname="Worship-Band",
               dienstbereich="Musik und Worship", docstatus=0, idx=0),
        GruppeVerantwortlicher(name="GV-1", parent="GRP-WORSHIP",
                               parenttype="Gruppe", parentfield="verantwortliche",
                               user=BRUNO, docstatus=0, idx=1),
        Lied(name="LIED-1", titel="Grosser Gott", gesangbuch_nummer="1",
             buch="JN", quelle="buch", aktiv=1,
             rechte_status="gemeinfrei", docstatus=0, idx=0),
        Lied(name="LIED-2", titel="Amazing Grace", gesangbuch_nummer="1297",
             buch="JN", quelle="buch", aktiv=1,
             rechte_status="gemeinfrei", docstatus=0, idx=0),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_bruno(welt):
    set_user(BRUNO)
    yield BRUNO
    set_user("Administrator")


def test_gleicher_titel_wird_serverseitig_abgewiesen(client, welt, als_bruno):
    """Vorher: zweites 'Grosser Gott' entstand still. Jetzt: 417, kein Doppel."""
    from diakronos_app.models.psalmos import Lied

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "Grosser Gott", "quelle": "ohne",
    }})
    assert r.status_code == 417, r.text
    assert "Grosser Gott" in r.text

    welt.expire_all()
    assert welt.query(Lied).filter(Lied.titel == "Grosser Gott").count() == 1


def test_titel_vergleich_ignoriert_gross_klein(client, welt, als_bruno):
    from diakronos_app.models.psalmos import Lied

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "grosser gott", "quelle": "ohne",
    }})
    assert r.status_code == 417, r.text
    welt.expire_all()
    assert welt.query(Lied).count() == 2


def test_gleiche_buch_nummer_wird_abgewiesen(client, welt, als_bruno):
    from diakronos_app.models.psalmos import Lied

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "Voellig anderer Titel", "quelle": "buch",
        "buch": "JN", "gesangbuch_nummer": "1297",
    }})
    assert r.status_code == 417, r.text
    assert "JN" in r.text and "1297" in r.text
    welt.expire_all()
    assert welt.query(Lied).count() == 2


def test_bestaetigtes_doppel_ist_erlaubt(client, welt, als_bruno):
    """Mit `dublette_bestaetigt` legt der Server das bewusste Doppel an."""
    from diakronos_app.models.psalmos import Lied

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "Grosser Gott", "quelle": "ohne", "dublette_bestaetigt": 1,
    }})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True
    welt.expire_all()
    assert welt.query(Lied).filter(Lied.titel == "Grosser Gott").count() == 2


def test_aendern_loest_keine_dublettenpruefung_aus(client, welt, als_bruno):
    """Ein Update (mit `name`) darf am eigenen Titel nicht scheitern."""
    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "name": "LIED-1", "titel": "Grosser Gott", "notiz": "geprueft",
    }})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True


# ── K-2: Wildcards `%` und `_` im Titel sind Zeichen, keine Platzhalter ──────

def test_prozentzeichen_im_titel_ist_kein_platzhalter(client, welt, als_bruno):
    """Vorher: `like`-'100 %' traf JEDES Lied -> falsche Dublette (417).

    Nachher: nur ein Lied mit demselben Text gilt als Dublette; ein anderes
    Lied mit einem `%` im Titel steht dem Anlegen nicht im Weg.
    """
    from diakronos_app.models.psalmos import Lied

    # Ein fremdes Lied, das ein naiver `%`-Platzhalter mit erfassen wuerde.
    r1 = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "100 Prozent Freude", "quelle": "ohne",
    }})
    assert r1.status_code == 200, r1.text

    # Anlegen mit einem `%` im Titel: darf NICHT als Dublette gelten.
    r2 = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "100 % Freude", "quelle": "ohne",
    }})
    assert r2.status_code == 200, r2.text

    welt.expire_all()
    assert welt.query(Lied).filter(Lied.titel == "100 % Freude").count() == 1


def test_gleicher_titel_mit_prozentzeichen_gilt_weiter_als_dublette(client, welt, als_bruno):
    """Der maskierte Vergleich erkennt denselben Text weiterhin."""
    from diakronos_app.models.psalmos import Lied

    r1 = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "Lob _ Dank", "quelle": "ohne",
    }})
    assert r1.status_code == 200, r1.text

    r2 = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "lob _ dank", "quelle": "ohne",
    }})
    assert r2.status_code == 417, r2.text
    welt.expire_all()
    assert welt.query(Lied).filter(Lied.titel == "Lob _ Dank").count() == 1
