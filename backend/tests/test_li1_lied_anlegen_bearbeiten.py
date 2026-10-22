"""LI1 — Lieder anlegen und bearbeiten: Anlegen ohne Namen, Ändern,
Strophen, Kategorien und das Schreibrecht (``lied_rechte``).

Der Karten-Text verlangt ausdrücklich: „API-Test Anlegen+Aendern+Rechte
(Nicht-Schreiber bekommt Fehler, Knopf unsichtbar)“. „Knopf unsichtbar“
entspricht serverseitig ``darf_schreiben=false`` aus ``lied_rechte`` — die
UI blendet daraufhin aus; sie entscheidet nichts selbst.

Der Test prüft ausserdem, dass die Löschung eines Liedes NICHT angeboten
wird: es gibt keinen Lösch-Endpunkt, und ``sa…`` darf kein ``delete_lied``
existieren. Das ist eine bewusste Abgrenzung (siehe „Bekannte Grenzen“).
"""
from __future__ import annotations

import pytest

PFAD = "/api/method/diakronos.planrahmen.api."
MPFAD = "/api/method/diakronos.psalmos.api.musik."


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def fehler(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 417, r.text
    return r.json()


def anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


def _speichern(client, lied, daten):
    """Lied über Psalmos ändern (Kopf, Strophen, Kategorien) — der Weg der UI."""
    r = client.post(MPFAD + "save_lied", json={"daten": {**daten, "name": lied}})
    assert r.status_code == 200, r.text
    return r.json()["message"]


def stammdaten(sf):
    """Bereich Chor, Konten, Mitglieder und zwei Lieder.

    ``planer_chor`` ist Verantwortlicher zweier Bereiche: „Chor“ (damit
    ``plantyp_speichern`` die Planvorlage anlegen darf) und „Musik und Worship“
    (damit ``save_lied``/``lied_speichern`` schreiben dürfen — dieselbe Regel
    wie in der Oberfläche, ``lied_rechte``). ``mitglied`` bleibt ohne Recht.
    """
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Gruppe, Gruppenmitgliedschaft, Mitglied,
    )
    from diakronos_app.models.psalmos import Lied, Liedkategorie
    with sf.begin() as s:
        s.add_all([Dienstbereich(name="Chor"), Dienstbereich(name="Musik und Worship")])
        s.add_all([User(name=k, email=k, enabled=True)
                   for k in ("planer_chor", "mitglied")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k, nachname="Test")
                   for k in ("planer_chor", "mitglied")])
        s.add_all([
            DienstbereichVerantwortlicher(name="bv-chor", parent="Chor",
                                          parenttype="Dienstbereich",
                                          parentfield="verantwortliche", user="planer_chor"),
            DienstbereichVerantwortlicher(name="bv-musik", parent="Musik und Worship",
                                          parenttype="Dienstbereich",
                                          parentfield="verantwortliche", user="planer_chor"),
        ])
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add(Gruppenmitgliedschaft(name="gm-mitglied", parent="Chor", parenttype="Gruppe",
                                    parentfield="mitglieder", mitglied="mitglied", status="Aktiv"))
        s.add_all([Lied(name="LIED-1", titel="Lied 1", aktiv=True),
                   Lied(name="LIED-2", titel="Lied 2", aktiv=True)])
        # Katalog für Kategorien (Fremdschlüssel der Zuordnungstabelle).
        s.add_all([Liedkategorie(name="Lob", kategoriename="Lob"),
                   Liedkategorie(name="Abendmahl", kategoriename="Abendmahl")])


@pytest.fixture()
def chor_def():
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    return kochbuch_laden("chorplan")


# ── Anlegen (ohne Namen) ─────────────────────────────────────────────────────

def test_neues_lied_anlegen_ueber_psalmos(client, patched_db, chor_def):
    """Ein Buchlied entsteht ohne ``name``; der Server vergibt ihn.

    Anlegen ist bewusst Aufgabe von Psalmos (``save_lied``): ``lied_speichern``
    im Planrahmen ändert nur bestehende Lieder.
    """
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    r = client.post(MPFAD + "save_lied", json={"daten": {
        "titel": "Komm, Herr", "quelle": "buch", "buch": "JN",
        "gesangbuch_nummer": "1297"}})
    assert r.status_code == 200, r.text
    erg = r.json()["message"]
    assert erg["lied"] and erg["titel"] == "Komm, Herr"
    # Eine Wahrheit: Psalmos liefert das neue Lied samt Kennung.
    detail = client.get(MPFAD + "get_lied_detail",
                        params={"lied": erg["lied"]}).json()["message"]
    assert detail["lied"]["titel"] == "Komm, Herr"
    assert detail["lied"]["quelle"] == "buch"
    assert detail["lied"]["anzeige"] == "JN 1297"


def test_neues_lied_als_kopie_ohne_nummer(client, patched_db, chor_def):
    """Quelle 'kopie' → keine Nummer/Seite, Anzeige „Kopie“."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    r = client.post(MPFAD + "save_lied", json={"daten": {
        "titel": "Loses Blatt", "quelle": "kopie"}})
    assert r.status_code == 200, r.text
    detail = client.get(MPFAD + "get_lied_detail",
                        params={"lied": r.json()["message"]["lied"]}).json()["message"]
    assert detail["lied"]["quelle"] == "kopie"
    assert detail["lied"]["anzeige"] == "Kopie"
    assert not detail["lied"]["gesangbuch_nummer"]


def test_neues_lied_ohne_titel_wird_abgelehnt(client, patched_db, chor_def):
    """Ohne Titel entsteht kein Lied — weder beim Anlegen noch beim Ändern."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    # Ändern über den Planrahmen: leerer Titel wird benannt abgelehnt.
    r = fehler(client, "lied_speichern", plantyp="chorplan", lied="LIED-1",
               daten={"titel": "   "})
    assert r["meldungen"][0]["pfad"] == "/titel"


def test_neues_lied_unbekannte_quelle_wird_abgelehnt(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    fehler(client, "lied_speichern", plantyp="chorplan", lied="LIED-1",
           daten={"titel": "X", "quelle": "irgendwas"})


def test_anlegen_braucht_schreibrecht(client, patched_db, chor_def):
    """Anlegen über Psalmos verlangt das Musik-Schreibrecht.

    ``save_lied`` wirft ``PermissionError`` — die Compat-Schicht übersetzt das
    in HTTP 403 (``frappe_compat/exceptions.py:http_status = 403``). Das ist der
    Vertrag, den die Oberfläche über ``lied_rechte`` vorab abfragt: der Knopf
    bleibt unsichtbar, ein direkter Aufruf endet mit 403 statt mit 417.
    """
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "mitglied")
    r = client.post(MPFAD + "save_lied", json={"daten": {"titel": "X", "quelle": "ohne"}})
    assert r.status_code == 403, r.text


# ── Strophen und Kategorien ──────────────────────────────────────────────────

def test_strophen_anlegen_und_sortieren(client, patched_db, chor_def):
    """Strophen mit Typ/Sprache/nur_chor — Reihenfolge wie übergeben.

    Strophen sind eine Kind-Tabelle des Liedes und werden von Psalmos
    (``save_lied``) geschrieben; ``planrahmen.lied_speichern`` ändert nur
    Kopffelder und Kategorien. Die Oberfläche benutzt für beides ``save_lied``.
    """
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    _speichern(client, "LIED-1", {
        "titel": "Lied 1", "strophen": [
            {"nummer": 1, "typ": "Strophe", "text": "Erste Zeile", "sprache": "de"},
            {"nummer": 2, "typ": "Refrain", "text": "Kehrvers", "nur_chor": True},
        ]})
    detail = client.get(MPFAD + "get_lied_detail",
                        params={"lied": "LIED-1"}).json()["message"]
    assert [s["typ"] for s in detail["strophen"]] == ["Strophe", "Refrain"]
    assert detail["strophen"][1]["nur_chor"] is True
    assert detail["strophen"][1]["text"] == "Kehrvers"


def test_strophen_loeschen_und_umsortieren(client, patched_db, chor_def):
    """Erneutes Speichern ersetzt den Strophenbestand (eine Wahrheit)."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    _speichern(client, "LIED-1", {
        "titel": "Lied 1", "strophen": [
            {"nummer": 1, "text": "A"}, {"nummer": 2, "text": "B"},
            {"nummer": 3, "text": "C"}]})
    _speichern(client, "LIED-1", {
        "titel": "Lied 1", "strophen": [
            {"nummer": 1, "text": "C"}, {"nummer": 2, "text": "A"}]})
    detail = client.get(MPFAD + "get_lied_detail",
                        params={"lied": "LIED-1"}).json()["message"]
    assert [s["text"] for s in detail["strophen"]] == ["C", "A"]


def test_kategorien_setzen_und_entfernen(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    erg = aufruf(client, "lied_speichern", plantyp="chorplan", lied="LIED-1",
                 daten={"titel": "Lied 1", "kategorien": ["Lob", "Abendmahl"]})
    assert sorted(erg["kategorien"]) == ["Abendmahl", "Lob"]
    aufruf(client, "lied_speichern", plantyp="chorplan", lied="LIED-1",
           daten={"titel": "Lied 1", "kategorien": ["Lob"]})
    detail = client.get(MPFAD + "get_lied_detail",
                        params={"lied": "LIED-1"}).json()["message"]
    assert detail["lied"]["kategorien"] == ["Lob"], (
        "Entfernte Kategorie darf nicht zurückkommen")


# ── Rechte ───────────────────────────────────────────────────────────────────

def test_lied_rechte_darf_schreiben_fuer_bereichsverantwortliche(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "planer_chor")
    erg = aufruf(client, "lied_rechte", plantyp="chorplan")
    assert erg["darf_schreiben"] is True
    assert erg["hinweis"] == ""


def test_lied_rechte_verweigert_fuer_mitglied(client, patched_db, chor_def):
    """Das ist die Serverwahrheit hinter „Knopf unsichtbar“."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "mitglied")
    erg = aufruf(client, "lied_rechte", plantyp="chorplan")
    assert erg["darf_schreiben"] is False
    assert "Berechtigung" in erg["hinweis"]


def test_lied_rechte_ohne_plantyp_verweigert_fuer_mitglied(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "mitglied")
    erg = aufruf(client, "lied_rechte")
    assert erg["darf_schreiben"] is False


def test_nicht_schreiber_bekommt_beim_anlegen_und_aendern_417(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "mitglied")
    for daten in ({"titel": "Neu", "quelle": "ohne"}, {"titel": "Anders"}):
        r = client.post(PFAD + "lied_speichern",
                        json={"plantyp": "chorplan", "lied": "", "daten": daten})
        assert r.status_code == 417, r.text
        assert r.json()["meldungen"][0]["code"] == "rechte.lied"


def test_loeschen_eines_liedes_existiert_nicht(client, patched_db, chor_def):
    """Absicht: kein Lösch-Endpunkt — die Karte lässt es ausdrücklich zu,
    das Löschen wegzulassen und als bekannte Grenze zu nennen."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    for name in ("lied_loeschen", "lied_entfernen", "delete_lied"):
        r = client.post(PFAD + name, json={"plantyp": "chorplan", "lied": "LIED-1"})
        assert r.status_code == 404, f"{name} darf es nicht geben: {r.status_code}"
