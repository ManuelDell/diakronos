"""P4e — Portiertes Modul `api.registrierung` (3 Endpunkte).

Quelle (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/registrierung.py`

Abgedeckt:
  * FRAPPE_MODULE gesetzt, alle 3 Original-Pfade aufloesbar.
  * `validate_token` / `submit_registrierung` / `submit_gast` sind OEFFENTLICH
    (`allow_guest=True`): ein GAST erreicht sie (nicht 403).
  * `validate_token`: Typ + Formular-Felder, abgelaufener/voller/ungueltiger Link.
  * `submit_registrierung`: Anlage der Anmeldung, Kindzeilen (Antworten/Kinder),
    Zaehler `anmeldungen_count`, Typ-Schranke.
  * `submit_gast`: Anlage, Typ-Schranke.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

MODUL = "diakronos.diakonos.api.registrierung"

ENDPUNKTE = ["validate_token", "submit_registrierung", "submit_gast"]

# Endpunkte mit `@frappe.whitelist(allow_guest=True)` im Original.
OEFFENTLICH = ["validate_token", "submit_registrierung", "submit_gast"]

SLUG = "abc123slug"
LINK = "RL-1"


def _link(**werte):
    """Registrierungslink mit den Feldern des Originals."""
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": LINK,
        "bezeichnung": "Einladung",
        "typ": "Mitglied-Registrierung",
        "aktiv": True,
        "slug": SLUG,
        "max_anmeldungen": 0,
        "anmeldungen_count": 0,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


@pytest.fixture()
def welt(patched_db):
    """Registrierungslink + Anmeldeformular mit zwei Feldern."""
    from diakronos_app.models.diakonos import (
        Anmeldeformular,
        AnmeldeformularFeld,
        Registrierungslink,
    )

    sess = patched_db()
    sess.add(_link())
    sess.add(
        Anmeldeformular(
            name="AF-1",
            bezeichnung="Standard",
            mit_kinder=True,
            mit_gaesten=True,
            docstatus=0,
            idx=0,
        )
    )
    sess.add_all(
        [
            AnmeldeformularFeld(
                name="AFF-1", parent="AF-1", parentfield="felder", parenttype="Anmeldeformular",
                idx=1, label="Ernaehrung", feldtyp="Select", optionen="omnivor,vegan",
                pflichtfeld=True, fuer_gaeste=False, fuer_kinder=True,
                docstatus=0,
            ),
            AnmeldeformularFeld(
                name="AFF-2", parent="AF-1", parentfield="felder", parenttype="Anmeldeformular",
                idx=2, label="Bemerkung", feldtyp="Small Text", optionen="",
                pflichtfeld=False, fuer_gaeste=True, fuer_kinder=False,
                docstatus=0,
            ),
        ]
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def link_mit_formular(patched_db):
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(_link(name="RL-FORMULAR", slug="formular-slug", anmeldeformular="AF-1"))
    sess.commit()
    yield sess
    sess.close()


def _anmeldungen(patched_db):
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    try:
        return sess.query(Anmeldung).all()
    finally:
        sess.close()


def _link_count(patched_db, name=LINK):
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    try:
        return sess.get(Registrierungslink, name).anmeldungen_count
    finally:
        sess.close()


# ── Registrierung / Router ─────────────────────────────────────────────────


@pytest.mark.parametrize("fn", ENDPUNKTE)
def test_original_pfade_registriert(fn):
    assert lookup(f"{MODUL}.{fn}") is not None


@pytest.mark.parametrize("fn", OEFFENTLICH)
def test_gast_erreicht_oeffentliche_endpunkte(client, welt, fn):
    """allow_guest=True: ein GAST darf die Registrierung aufrufen."""
    set_user("Guest")
    try:
        r = client.get(f"/api/method/{MODUL}.{fn}", params={"token": SLUG})
        assert r.status_code != 403, (fn, r.text)
    finally:
        set_user("Administrator")


@pytest.mark.parametrize("fn", ENDPUNKTE)
def test_original_pfad_ist_geroutet(client, welt, fn):
    """Kein 404 — der Pfad ist beim Router registriert."""
    r = client.get(f"/api/method/{MODUL}.{fn}", params={"token": "unbekannt"})
    assert r.status_code != 404, (fn, r.text)


# ── validate_token ─────────────────────────────────────────────────────────


def test_validate_token_liefert_typ_und_felder(client, welt, link_mit_formular):
    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": "formular-slug"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["typ"] == "Mitglied-Registrierung"
    assert msg["mit_kinder"] == 1
    assert msg["mit_gaesten"] == 1
    assert [f["label"] for f in msg["felder"]] == ["Ernaehrung", "Bemerkung"]
    assert msg["felder"][0] == {
        "label": "Ernaehrung",
        "feldtyp": "Select",
        "optionen": "omnivor,vegan",
        "pflichtfeld": True,
        "fuer_gaeste": False,
        "fuer_kinder": True,
    }


def test_validate_token_ohne_formular_liefert_leere_liste(client, welt):
    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["felder"] == []
    assert msg["mit_kinder"] == 0
    assert msg["mit_gaesten"] == 0


def test_validate_token_ohne_token_wird_abgewiesen(client, welt, link_mit_formular):
    """Ohne Token: das Original wirft PermissionError.

    Der Router kann einen FEHLENDEN Parameter noch nicht an die Fachfunktion
    reichen (FastAPI-Pflichtargument -> 417), deshalb wird der Fall mit
    ausdruecklich leerem Token gefahren. Beides ist eine Verweigerung
    (kein 200) — die Fachpruefung selbst wird in `_validate_token` geprueft.
    """
    from diakronos_app.api.registrierung import _validate_token
    from diakronos_app.frappe_compat.exceptions import PermissionError as _PErr

    with pytest.raises(_PErr):
        _validate_token("")

    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": ""})
    assert r.status_code == 403, r.text


def test_validate_token_fehlender_parameter_wird_abgewiesen(client, welt):
    """Ohne `token` im Request: Verweigerung, niemals 200."""
    r = client.get(f"/api/method/{MODUL}.validate_token")
    assert r.status_code != 200, r.text


def test_validate_token_unbekannter_slug_wird_abgewiesen(client, welt):
    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": "gibtsnicht"})
    assert r.status_code == 403, r.text


def test_validate_token_inaktiver_link_wird_abgewiesen(client, patched_db):
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(Registrierungslink(
        name="RL-OFF", bezeichnung="aus", typ="Mitglied-Registrierung",
        aktiv=False, slug="off-slug", max_anmeldungen=0, anmeldungen_count=0,
        docstatus=0, idx=0,
    ))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": "off-slug"})
    assert r.status_code == 403, r.text


def test_validate_token_abgelaufen_wird_abgewiesen(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-ALT", slug="alt-slug",
                   gueltig_bis=date.today() - timedelta(days=1)))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": "alt-slug"})
    assert r.status_code == 403, r.text


def test_validate_token_voller_link_wird_abgewiesen(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-VOLL", slug="voll-slug", max_anmeldungen=3,
                   anmeldungen_count=3))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": "voll-slug"})
    assert r.status_code == 403, r.text


def test_validate_token_grenze_noch_offen(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-REST", slug="rest-slug", max_anmeldungen=3,
                   anmeldungen_count=2))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL}.validate_token", params={"token": "rest-slug"})
    assert r.status_code == 200, r.text


# ── submit_registrierung ───────────────────────────────────────────────────


def test_submit_registrierung_legt_anmeldung_an(client, patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={"token": SLUG, "vorname": "  Anna ", "nachname": "Beispiel",
              "email": "anna@example.org", "telefon": "0711 123",
              "kommentar": "  Hallo  ", "dsgvo": True},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True
    assert msg["anmeldung"]

    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    doc = sess.get(Anmeldung, msg["anmeldung"])
    assert doc.anmeldungstyp == "Mitglied-Registrierung"
    assert doc.status == "Anmeldeanfrage"
    assert doc.vorname == "Anna"          # getrimmt wie im Original
    assert doc.nachname == "Beispiel"
    assert doc.kommentar == "Hallo"
    assert doc.email == "anna@example.org"
    assert doc.registrierungslink == LINK
    assert doc.dsgvo_zustimmung is True
    # N-1 (R-N10): der Beleg traegt einen Kopf `Fassung <nr> (<kennung>)` vor
    # dem Wortlaut — er belegt, WELCHE Fassung angezeigt wurde.
    assert doc.dsgvo_text_snapshot.startswith("Fassung 1 (")
    assert "Ich willige ein" in doc.dsgvo_text_snapshot
    assert doc.anmeldedatum is not None
    sess.close()

    assert _link_count(patched_db) == 1


def test_submit_registrierung_speichert_antworten_und_kinder(client, patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={
            "token": SLUG, "vorname": "Anna", "nachname": "Beispiel",
            "antworten": '[{"label": "Ernaehrung", "wert": "vegan"}]',
            "kinder": '[{"vorname": "Lena", "nachname": "Beispiel", "geburtstag": "2015-03-04"}]',
            "dsgvo": True,
        },
    )
    assert r.status_code == 200, r.text
    anmeldung = r.json()["message"]["anmeldung"]

    from diakronos_app.models.diakonos import AnmeldungAntwort, AnmeldungKind

    sess = patched_db()
    try:
        antworten = sess.query(AnmeldungAntwort).filter_by(parent=anmeldung).all()
        kinder = sess.query(AnmeldungKind).filter_by(parent=anmeldung).all()
        assert [(a.feldlabel, a.antwort) for a in antworten] == [("Ernaehrung", "vegan")]
        assert [(k.vorname, k.nachname) for k in kinder] == [("Lena", "Beispiel")]
        assert kinder[0].geburtstag == date(2015, 3, 4)
    finally:
        sess.close()


def test_submit_registrierung_ohne_vorname_wird_abgewiesen(client, welt):
    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={"token": SLUG, "vorname": "  ", "nachname": "Beispiel", "dsgvo": True},
    )
    assert r.status_code == 417, r.text
    assert "Vorname" in r.text


def test_submit_registrierung_ohne_nachname_wird_abgewiesen(client, welt):
    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={"token": SLUG, "vorname": "Anna", "nachname": "", "dsgvo": True},
    )
    assert r.status_code == 417, r.text
    assert "Nachname" in r.text


def test_submit_registrierung_falscher_typ_wird_abgewiesen(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-GAST", typ="Gast-Anmeldung", slug="gast-slug"))
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={"token": "gast-slug", "vorname": "Anna", "nachname": "Beispiel"},
    )
    assert r.status_code == 403, r.text


def test_submit_registrierung_veranstaltungstyp_erlaubt(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-VA", typ="Veranstaltung", slug="va-slug"))
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={"token": "va-slug", "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True},
    )
    assert r.status_code == 200, r.text

    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    doc = sess.get(Anmeldung, r.json()["message"]["anmeldung"])
    assert doc.anmeldungstyp == "Veranstaltung"
    sess.close()


def test_submit_registrierung_zaehlt_hoch_ohne_modified(client, patched_db):
    """`update_modified=False` des Originals: `modified` bleibt unveraendert."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(_link(anmeldungen_count=5))
    sess.commit()
    vorher = sess.get(Registrierungslink, LINK).modified
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        json={"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True},
    )
    assert r.status_code == 200, r.text

    sess = patched_db()
    doc = sess.get(Registrierungslink, LINK)
    assert doc.anmeldungen_count == 6
    assert doc.modified == vorher
    sess.close()


# ── submit_gast ────────────────────────────────────────────────────────────


def test_submit_gast_legt_anmeldung_an(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-GAST", typ="Gast-Anmeldung", slug="gast-slug"))
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_gast",
        json={"token": "gast-slug", "vorname": "Gustav", "nachname": "Gast", "dsgvo": True},
    )
    assert r.status_code == 200, r.text
    anmeldung = r.json()["message"]["anmeldung"]

    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    doc = sess.get(Anmeldung, anmeldung)
    assert doc.anmeldungstyp == "Gast-Anmeldung"
    assert doc.vorname == "Gustav"
    assert doc.status == "Anmeldeanfrage"
    assert doc.dsgvo_zustimmung is True
    assert doc.registrierungslink == "RL-GAST"
    sess.close()

    assert _link_count(patched_db, "RL-GAST") == 1


def test_submit_gast_falscher_typ_wird_abgewiesen(client, welt):
    r = client.post(
        f"/api/method/{MODUL}.submit_gast",
        json={"token": SLUG, "vorname": "Gustav", "nachname": "Gast"},
    )
    assert r.status_code == 403, r.text


def test_submit_gast_ohne_namen_wird_abgewiesen(client, patched_db):
    sess = patched_db()
    sess.add(_link(name="RL-GAST", typ="Gast-Anmeldung", slug="gast-slug"))
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL}.submit_gast",
        json={"token": "gast-slug", "vorname": "", "nachname": "Gast", "dsgvo": True},
    )
    assert r.status_code == 417, r.text


def test_submit_gast_ungueltiger_link_wird_abgewiesen(client, welt):
    r = client.post(
        f"/api/method/{MODUL}.submit_gast",
        json={"token": "gibtsnicht", "vorname": "Gustav", "nachname": "Gast"},
    )
    assert r.status_code == 403, r.text
