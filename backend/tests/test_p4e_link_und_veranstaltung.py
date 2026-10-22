"""P4e — Portierte Module `api.registrierungslink_api` + `api.veranstaltungsanmeldung`.

Quellen (READ-ONLY):
  * `referenz/diakronos-frappe/.../api/registrierungslink_api.py` (4 Endpunkte)
  * `referenz/diakronos-frappe/.../api/veranstaltungsanmeldung.py` (2 Endpunkte)

Abgedeckt:
  * FRAPPE_MODULE gesetzt, alle Original-Pfade aufloesbar.
  * Beide Module sind NUR fuer eingeloggte Nutzer: `Guest` -> 403.
  * Link-Verwaltung nur mit Rolle `Mitgliederadministrator`/`System Manager`.
  * `create_link` (Anlage + Antwortform), `update_link` (Whitelist der Felder),
    `delete_link` (Sperre bei bestaetigten Anmeldungen, Loeschen ausstehender),
    `toggle_link` (Umschalten).
  * `register_mitglied` (Profil-Daten, DSGVO-Snapshot, Zaehler, Typ-Schranke,
    Doppel-Anmeldung), `check_anmeldestatus` (Gast -> False).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User

MODUL_LINK = "diakronos.diakonos.api.registrierungslink_api"
MODUL_VERANST = "diakronos.diakonos.api.veranstaltungsanmeldung"

LINK_ENDPUNKTE = ["create_link", "update_link", "delete_link", "toggle_link"]
VERANST_ENDPUNKTE = ["register_mitglied", "check_anmeldestatus"]

ADMIN = "mitgliederadmin@example.org"
NUTZER = "nutzer@example.org"
LINK = "RL-VERANST"


def _link(**werte):
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": LINK,
        "bezeichnung": "Sommerfest",
        "typ": "Veranstaltung",
        "aktiv": True,
        "max_anmeldungen": 0,
        "anmeldungen_count": 0,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


@pytest.fixture()
def admin_umgebung(patched_db):
    """Admin-Benutzer + Rolle, plus ein normaler Nutzer und ein Veranstaltungslink."""
    sess = patched_db()
    sess.add_all(
        [
            User(name=ADMIN, email=ADMIN, full_name="Mia Admin", enabled=True),
            User(name=NUTZER, email=NUTZER, full_name="Nils Nutzer", enabled=True),
            HasRole(
                name="HR-1", parent=ADMIN, parentfield="roles",
                parenttype="User", role="Mitgliederadministrator", docstatus=0, idx=1,
            ),
        ]
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_admin(admin_umgebung):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


@pytest.fixture()
def als_nutzer(admin_umgebung):
    set_user(NUTZER)
    yield NUTZER
    set_user("Administrator")


def _anmeldungen(patched_db, link=LINK):
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    try:
        return sess.query(Anmeldung).filter(Anmeldung.registrierungslink == link).all()
    finally:
        sess.close()


def _link_zeile(patched_db, name=LINK):
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    try:
        return sess.get(Registrierungslink, name)
    finally:
        sess.close()


# ── Routing ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fn", LINK_ENDPUNKTE)
def test_linkpfade_registriert(fn):
    assert lookup(f"{MODUL_LINK}.{fn}") is not None


@pytest.mark.parametrize("fn", VERANST_ENDPUNKTE)
def test_veranstaltungspfade_registriert(fn):
    assert lookup(f"{MODUL_VERANST}.{fn}") is not None


@pytest.mark.parametrize("fn", LINK_ENDPUNKTE)
def test_linkpfad_ist_geroutet(client, admin_umgebung, fn):
    """Kein 404 — der Pfad ist beim Router registriert.

    Mit den Pflichtargumenten aufgerufen, damit die Antwort aus der
    Fachfunktion kommt (Admin) und nicht aus dem Argument-Check.
    """
    r = client.post(
        f"/api/method/{MODUL_LINK}.{fn}",
        data={"link_id": LINK, "bezeichnung": "X", "typ": "Veranstaltung"},
    )
    assert r.status_code != 404, (fn, r.text)


@pytest.mark.parametrize("fn", VERANST_ENDPUNKTE)
def test_veranstaltungspfad_ist_geroutet(client, admin_umgebung, fn):
    """Der Pfad ist registriert: die Antwort kommt aus dem Fachcode.

    Ein fehlender Link ist fachlich ein `DoesNotExistError` (404) — deshalb
    wird hier NICHT auf "!= 404" geprueft, sondern darauf, dass die Meldung
    NICHT die des Routers ist ("Methode ... nicht gefunden").
    """
    r = client.get(f"/api/method/{MODUL_VERANST}.{fn}", params={"registrierungslink_id": LINK})
    assert "nicht gefunden'" not in r.text or "Registrierungslink" in r.text, (fn, r.text)
    assert not r.text.startswith('{"message":"Methode'), (fn, r.text)


# ── Zugriffsschutz (allow_guest=False) ─────────────────────────────────────


@pytest.mark.parametrize("fn", LINK_ENDPUNKTE)
def test_gast_erreicht_linkverwaltung_nicht(client, admin_umgebung, fn):
    set_user("Guest")
    try:
        r = client.post(f"/api/method/{MODUL_LINK}.{fn}")
        assert r.status_code == 401, (fn, r.text)
    finally:
        set_user("Administrator")


@pytest.mark.parametrize("fn", VERANST_ENDPUNKTE)
def test_gast_erreicht_veranstaltung_nicht(client, admin_umgebung, fn):
    """`allow_guest=False` im Original: der Router weist Gaeste ab (403).

    Der `Guest`-Zweig INNERHALB der Funktionen (PermissionError bzw.
    `{"angemeldet": False}`) ist damit unerreichbar, solange das Flag steht —
    er bleibt als Verhalten des Originals erhalten und wird direkt geprueft
    (siehe `test_check_anmeldestatus_gast_ohne_flag`).
    """
    set_user("Guest")
    try:
        r = client.get(
            f"/api/method/{MODUL_VERANST}.{fn}",
            params={"registrierungslink_id": LINK},
        )
        assert r.status_code == 401, (fn, r.text)
    finally:
        set_user("Administrator")


def test_check_anmeldestatus_gast_ohne_flag(patched_db, admin_umgebung):
    """`check_anmeldestatus` als Gast: Original gibt `{"angemeldet": False}`.

    Direkt aufgerufen, weil das `allow_guest=False`-Flag den Router davor
    abfaengt — die Fachfunktion selbst darf keinen Fehler werfen.
    """
    from diakronos_app.api.veranstaltungsanmeldung import check_anmeldestatus

    set_user("Guest")
    try:
        assert check_anmeldestatus(LINK) == {"angemeldet": False}
    finally:
        set_user("Administrator")


def test_register_mitglied_als_gast_ohne_flag(patched_db, admin_umgebung):
    """`register_mitglied` als Gast: Original wirft PermissionError."""
    from diakronos_app.api.veranstaltungsanmeldung import register_mitglied
    from diakronos_app.frappe_compat.exceptions import PermissionError as _PErr

    set_user("Guest")
    try:
        with pytest.raises(_PErr):
            register_mitglied(LINK)
    finally:
        set_user("Administrator")


@pytest.mark.parametrize("fn", LINK_ENDPUNKTE)
def test_nicht_admin_darf_linkverwaltung_nicht(client, als_nutzer, fn):
    """Ohne Rolle `Mitgliederadministrator` -> PermissionError.

    Mit vollstaendigen Pflichtargumenten, damit die Verweigerung aus
    `require_admin()` kommt und nicht aus dem Argument-Check (417).
    """
    r = client.post(
        f"/api/method/{MODUL_LINK}.{fn}",
        data={"link_id": LINK, "bezeichnung": "X", "typ": "Veranstaltung"},
    )
    assert r.status_code == 403, (fn, r.text)


# ── create_link ────────────────────────────────────────────────────────────


def test_create_link_legt_an_und_liefert_antwortform(client, als_admin, patched_db):
    r = client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        data={
            "bezeichnung": "Sommerfest 2026",
            "typ": "Veranstaltung",
            "max_anmeldungen": 50,
        },
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True

    link = msg["link"]
    assert link["bezeichnung"] == "Sommerfest 2026"
    assert link["typ"] == "Veranstaltung"
    assert link["aktiv"] == 1
    assert link["max_anmeldungen"] == 50
    # P0-4/UXD-R2: der Slug ist ein Zufallstoken (im Original vergab `autoname`
    # ihn) und NICHT aus der Bezeichnung abgeleitet. Der frühere Wert
    # "sommerfest-2026" war die Fehlfunktion: der Link war nie benutzbar.
    assert link["slug"] and link["slug"] != "sommerfest-2026"
    assert link["link_anzeige"].endswith("?token=" + link["slug"])

    # In der DB nachpruefen, nicht nur der Antwort glauben.
    zeile = _link_zeile(patched_db, link["name"])
    assert zeile is not None
    assert zeile.bezeichnung == "Sommerfest 2026"
    assert zeile.aktiv is True


def test_create_link_setzt_leere_optionale_felder_auf_none(client, als_admin, patched_db):
    r = client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        data={"bezeichnung": "Ohne Extras", "typ": "Gast-Anmeldung"},
    )
    assert r.status_code == 200, r.text
    zeile = _link_zeile(patched_db, r.json()["message"]["link"]["name"])
    # M-1 (N9b): gueltig_bis ist NICHT mehr None — ohne ausdruecklichen Wert
    # gilt die gepflegte Laufzeit-Vorgabe (Standard 30 Tage). Die wirklich
    # optionalen Felder bleiben leer.
    assert zeile.gueltig_bis is not None
    assert zeile.anmeldeformular is None
    assert zeile.element is None


# ── update_link ────────────────────────────────────────────────────────────


def test_update_link_schreibt_erlaubte_felder(client, als_admin, patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL_LINK}.update_link",
        data={"link_id": LINK, "bezeichnung": "Sommerfest neu", "max_anmeldungen": 10},
    )
    assert r.status_code == 200, r.text

    zeile = _link_zeile(patched_db)
    assert zeile.bezeichnung == "Sommerfest neu"
    assert zeile.max_anmeldungen == 10


def test_update_link_ignoriert_unerlaubte_felder(client, als_admin, patched_db):
    """`typ`/`slug` stehen NICHT in `allowed` des Originals."""
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = client.post(
        f"/api/method/{MODUL_LINK}.update_link",
        data={"link_id": LINK, "typ": "Gast-Anmeldung", "name": "HACK"},
    )
    assert r.status_code == 200, r.text

    zeile = _link_zeile(patched_db)
    assert zeile.typ == "Veranstaltung"  # unveraendert
    assert _link_zeile(patched_db, "HACK") is None


# ── toggle_link ────────────────────────────────────────────────────────────


def test_toggle_link_schaltet_um(client, als_admin, patched_db):
    sess = patched_db()
    sess.add(_link(aktiv=True))
    sess.commit()
    sess.close()

    r = client.post(f"/api/method/{MODUL_LINK}.toggle_link", data={"link_id": LINK})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"success": True, "aktiv": False}
    assert _link_zeile(patched_db).aktiv is False

    r2 = client.post(f"/api/method/{MODUL_LINK}.toggle_link", data={"link_id": LINK})
    assert r2.json()["message"] == {"success": True, "aktiv": True}
    assert _link_zeile(patched_db).aktiv is True


# ── delete_link ────────────────────────────────────────────────────────────


def test_delete_link_loescht_ausstehende_anmeldungen(client, als_admin, patched_db):
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    sess.add(_link())
    sess.add_all(
        [
            Anmeldung(
                name="AN-1", registrierungslink=LINK, status="Anmeldeanfrage",
                vorname="A", nachname="B", docstatus=0, idx=0,
            ),
            Anmeldung(
                name="AN-2", registrierungslink=LINK, status="Abgelehnt",
                vorname="C", nachname="D", docstatus=0, idx=0,
            ),
        ]
    )
    sess.commit()
    sess.close()

    r = client.post(f"/api/method/{MODUL_LINK}.delete_link", data={"link_id": LINK})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"success": True}

    assert _link_zeile(patched_db) is None
    assert _anmeldungen(patched_db) == []


def test_delete_link_verweigert_bei_bestaetigter_anmeldung(client, als_admin, patched_db):
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    sess.add(_link())
    sess.add(
        Anmeldung(
            name="AN-OK", registrierungslink=LINK, status="Bestätigt",
            vorname="A", nachname="B", docstatus=0, idx=0,
        )
    )
    sess.commit()
    sess.close()

    r = client.post(f"/api/method/{MODUL_LINK}.delete_link", data={"link_id": LINK})
    assert r.status_code != 200, r.text
    assert "bestätigte Anmeldungen" in r.text

    # Link UND Anmeldung bleiben unangetastet.
    assert _link_zeile(patched_db) is not None
    assert len(_anmeldungen(patched_db)) == 1


# ── register_mitglied ──────────────────────────────────────────────────────


def test_register_mitglied_legt_anmeldung_mit_profildaten_an(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link(max_anmeldungen=10))
    sess.commit()
    sess.close()

    r = client.get(
        f"/api/method/{MODUL_VERANST}.register_mitglied",
        params={"registrierungslink_id": LINK},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True

    zeilen = _anmeldungen(patched_db)
    assert len(zeilen) == 1
    anm = zeilen[0]
    assert anm.name == msg["anmeldung"]
    assert anm.email == NUTZER
    assert anm.anmeldungstyp == "Veranstaltung"
    assert anm.status == "Anmeldeanfrage"
    assert anm.dsgvo_zustimmung is True
    assert "Veranstaltungsanmeldung" in anm.dsgvo_text_snapshot

    # Zaehler am Link hochgesetzt, ohne den Link zu "beruehren".
    assert _link_zeile(patched_db).anmeldungen_count == 1


def test_register_mitglied_nutzt_vorname_nachname_aus_full_name(client, als_nutzer, patched_db):
    """Das Modell hat (noch) kein first_name/last_name -> full_name wird geteilt."""
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
               params={"registrierungslink_id": LINK})

    anm = _anmeldungen(patched_db)[0]
    assert anm.vorname == "Nils"
    assert anm.nachname == "Nutzer"


def test_register_mitglied_verweigert_doppelte_anmeldung(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r1 = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                    params={"registrierungslink_id": LINK})
    assert r1.status_code == 200, r1.text

    r2 = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                    params={"registrierungslink_id": LINK})
    assert r2.status_code != 200, r2.text
    assert "bereits" in r2.text
    assert len(_anmeldungen(patched_db)) == 1


def test_register_mitglied_akzeptiert_neuanmeldung_nach_ablehnung(client, als_nutzer, patched_db):
    """Original-Filter: `status != "Abgelehnt"` — abgelehnt zaehlt nicht."""
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    sess.add(_link())
    sess.add(
        Anmeldung(
            name="AN-AB", registrierungslink=LINK, status="Abgelehnt", email=NUTZER,
            vorname="N", nachname="N", docstatus=0, idx=0,
        )
    )
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                   params={"registrierungslink_id": LINK})
    assert r.status_code == 200, r.text
    assert len(_anmeldungen(patched_db)) == 2


def test_register_mitglied_verweigert_falschen_typ(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link(typ="Mitglied-Registrierung"))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                   params={"registrierungslink_id": LINK})
    assert r.status_code == 403, r.text
    assert "Veranstaltungs-Anmeldungen" in r.text
    assert _anmeldungen(patched_db) == []


def test_register_mitglied_verweigert_deaktivierten_link(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link(aktiv=False))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                   params={"registrierungslink_id": LINK})
    assert r.status_code != 200, r.text
    assert _anmeldungen(patched_db) == []


def test_register_mitglied_verweigert_abgelaufenen_link(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link(gueltig_bis=date.today() - timedelta(days=1)))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                   params={"registrierungslink_id": LINK})
    assert r.status_code == 403, r.text
    assert "abgelaufen" in r.text
    assert _anmeldungen(patched_db) == []


def test_register_mitglied_verweigert_vollen_link(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link(max_anmeldungen=2, anmeldungen_count=2))
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                   params={"registrierungslink_id": LINK})
    assert r.status_code == 403, r.text
    assert "maximale Anzahl" in r.text
    assert _anmeldungen(patched_db) == []


def test_register_mitglied_verweigert_unbekannten_link(client, als_nutzer, patched_db):
    r = client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
                   params={"registrierungslink_id": "GIBTS-NICHT"})
    assert r.status_code != 200, r.text
    assert _anmeldungen(patched_db, "GIBTS-NICHT") == []


# ── check_anmeldestatus ────────────────────────────────────────────────────


def test_check_anmeldestatus_false_vor_anmeldung(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.check_anmeldestatus",
                   params={"registrierungslink_id": LINK})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"angemeldet": False}


def test_check_anmeldestatus_true_nach_anmeldung(client, als_nutzer, patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    client.get(f"/api/method/{MODUL_VERANST}.register_mitglied",
               params={"registrierungslink_id": LINK})

    r = client.get(f"/api/method/{MODUL_VERANST}.check_anmeldestatus",
                   params={"registrierungslink_id": LINK})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"angemeldet": True}


def test_check_anmeldestatus_ignoriert_abgelehnte(client, als_nutzer, patched_db):
    """`status != "Abgelehnt"` — eine Ablehnung macht nicht "angemeldet"."""
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    sess.add(_link())
    sess.add(
        Anmeldung(
            name="AN-AB", registrierungslink=LINK, status="Abgelehnt", email=NUTZER,
            vorname="N", nachname="N", docstatus=0, idx=0,
        )
    )
    sess.commit()
    sess.close()

    r = client.get(f"/api/method/{MODUL_VERANST}.check_anmeldestatus",
                   params={"registrierungslink_id": LINK})
    assert r.json()["message"] == {"angemeldet": False}
