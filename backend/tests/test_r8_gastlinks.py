"""R-8: Gast-Links fuer Wiki und Beitraege (Manuel 11.11.).

Ein Gast kommt nur per Passwort-Link hinein, immer mit Ablauf (Standard 3
Tage, einstellbar). Freigeben darf, wer den Inhalt verwaltet.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.rechte import RechteGastlink
from diakronos_app.rechte import gastlinks as G

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, CHORSAENGER, MIRA, REBEKKA, SAMUEL, welt,
)

PFAD = "/api/method/diakronos_app.api.rechte.gast_inhalt"
PASSWORT = "geheim-123"


@pytest.fixture()
def beitrag(welt):
    from diakronos_app.api import beitraege as B

    set_user(REBEKKA)
    bid = B.create_beitrag("Chor intern", "<p>Probe</p><script>alert(1)</script>", gruppe="Chor")["beitrag_id"]
    set_user("Administrator")
    return bid


def _oeffnen(guest_client, token, passwort=PASSWORT):
    return guest_client.post(PFAD, json={"token": token, "passwort": passwort})


def test_anlegen_nur_wer_verwaltet(beitrag):
    for wer in (CHORSAENGER, SAMUEL):
        with pytest.raises(PermErr):
            G.erstellen(wer, "beitrag", beitrag, PASSWORT)
    erg = G.erstellen(MIRA, "beitrag", beitrag, PASSWORT)
    assert len(erg["token"]) >= 40


def test_standard_drei_tage_und_grenzen(beitrag, welt):
    erg = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)
    zeile = welt.get(RechteGastlink, erg["id"])
    assert timedelta(days=2, hours=23) < zeile.ablauf - datetime.utcnow() <= timedelta(days=3)
    assert G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT, tage=14)["success"]
    for tage in (0, 31):
        with pytest.raises(ValidationError):
            G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT, tage=tage)
    with pytest.raises(ValidationError):
        G.erstellen(REBEKKA, "beitrag", beitrag, "kurz")
    with pytest.raises(ValidationError):
        G.erstellen(ADMIN, "kalender", "chorkal", PASSWORT)


def test_token_wird_nicht_gespeichert_und_nicht_gelistet(beitrag, welt):
    erg = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)
    zeile = welt.get(RechteGastlink, erg["id"])
    assert erg["token"] not in (zeile.token_hash, zeile.passwort_hash)
    assert PASSWORT not in zeile.passwort_hash
    eintraege = G.liste(MIRA, "beitrag", beitrag)
    assert eintraege and "token" not in eintraege[0] and eintraege[0]["aktiv"]
    with pytest.raises(PermErr):
        G.liste(CHORSAENGER, "beitrag", beitrag)


def test_gast_liest_bereinigten_inhalt(beitrag, guest_client):
    token = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)["token"]
    r = _oeffnen(guest_client, token)
    assert r.status_code == 200, r.text
    inhalt = r.json()["message"]
    assert inhalt["titel"] == "Chor intern"
    assert "Probe" in inhalt["inhalt"] and "<script" not in inhalt["inhalt"]
    assert set(inhalt) == {"typ", "titel", "inhalt", "datum"}


def test_falsches_passwort_und_sperre(beitrag, guest_client):
    token = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)["token"]
    for _ in range(G.MAX_FEHLVERSUCHE):
        assert _oeffnen(guest_client, token, "falsch-falsch").status_code == 403
    # gesperrt — auch mit dem richtigen Passwort
    assert _oeffnen(guest_client, token).status_code == 403


def test_widerrufen_abgelaufen_geloescht_unbekannt(beitrag, guest_client, welt):
    from diakronos_app.api import beitraege as B

    erg = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)
    assert _oeffnen(guest_client, "gibt-es-nicht").status_code == 404
    with pytest.raises(PermErr):
        G.widerrufen(CHORSAENGER, erg["id"])
    G.widerrufen(MIRA, erg["id"])
    assert _oeffnen(guest_client, erg["token"]).status_code == 404

    abgelaufen = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)
    welt.get(RechteGastlink, abgelaufen["id"]).ablauf = datetime.utcnow() - timedelta(minutes=1)
    welt.commit()
    assert _oeffnen(guest_client, abgelaufen["token"]).status_code == 404

    aktiv = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)
    set_user(REBEKKA)
    B.delete_beitrag(beitrag)
    set_user("Administrator")
    assert _oeffnen(guest_client, aktiv["token"]).status_code == 404


def test_wiki_ueber_gastlink(welt, guest_client):
    from diakronos_app.api import wiki as W

    set_user(MIRA)
    aid = W.create_wiki_artikel("Chor-Wiki", "Noten liegen im Schrank.", gruppe="Chor")["artikel_id"]
    set_user("Administrator")
    token = G.erstellen(MIRA, "wiki", aid, PASSWORT)["token"]
    r = _oeffnen(guest_client, token)
    assert r.status_code == 200, r.text
    assert "Schrank" in r.json()["message"]["inhalt"]


def test_aufraeumen_entfernt_nur_alte(beitrag, welt):
    """R-11f: abgelaufen/widerrufen laenger als 30 Tage -> weg; sonst bleibt."""
    frisch = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)["id"]
    alt_abgelaufen = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)["id"]
    alt_widerrufen = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)["id"]
    kurz_abgelaufen = G.erstellen(REBEKKA, "beitrag", beitrag, PASSWORT)["id"]
    jetzt = datetime.utcnow()
    welt.get(RechteGastlink, alt_abgelaufen).ablauf = jetzt - timedelta(days=31)
    welt.get(RechteGastlink, alt_widerrufen).widerrufen_am = jetzt - timedelta(days=31)
    welt.get(RechteGastlink, kurz_abgelaufen).ablauf = jetzt - timedelta(days=2)
    welt.commit()
    assert G.aufraeumen() == 2
    welt.expire_all()
    assert {z.id for z in welt.query(RechteGastlink)} == {frisch, kurz_abgelaufen}
    assert G.aufraeumen() == 0
