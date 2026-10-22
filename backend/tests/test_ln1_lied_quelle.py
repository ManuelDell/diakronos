"""LN1 — Lieder ohne Nummer: Quelle (Liederbuch/Kopie/ohne), Zerlegung, Anzeige.

Drei Ebenen:

1. **Parser** (rein, ohne DB): ``zerlege_quelle`` und ``anzeige_text`` aus
   ``planrahmen.lieder_pflege`` — alle Muster inkl. Gross-/Kleinschreibung.
2. **API** (SQLite): ``lied_speichern`` nimmt ``quelle`` an, ``get_lieder`` /
   ``get_lied_detail`` liefern Quelle und fertige Anzeige; unbekannte Quelle
   ist ein Fachfehler.
3. **Migration**: eigene Datei ``test_ln1_migration.py`` (Wegwerf-PostgreSQL).
"""
from __future__ import annotations

import pytest

from diakronos_app.planrahmen import lieder_pflege as lp

PFAD = "/api/method/diakronos.planrahmen.api."
MPFAD = "/api/method/diakronos.psalmos.api.musik."


# ── 1. Parser ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("roh", ["KOP", "Kop", "kop", "Kopie", "kopie", "KOPIE", "  kop  "])
def test_zerlege_kopie(roh):
    z = lp.zerlege_quelle(roh)
    assert z == {"quelle": "kopie", "buch": "", "nummer": "", "seite": ""}


@pytest.mark.parametrize("roh,buch,nr", [
    ("JN Nr. 1297", "JN", "1297"),
    ("JN nr 1297", "JN", "1297"),
    ("BUCH Nr. 123", "BUCH", "123"),
    ("PZ5 Nr. 689", "PZ5", "689"),
    ("LZL1 Nr. 91", "LZL1", "91"),
    ("WG Nr. 13", "WG", "13"),
])
def test_zerlege_buch_nummer(roh, buch, nr):
    z = lp.zerlege_quelle(roh)
    assert z["quelle"] == "buch"
    assert z["buch"] == buch
    assert z["nummer"] == nr
    assert z["seite"] == ""


@pytest.mark.parametrize("roh,buch,seite", [
    ("BUCH S. 150", "BUCH", "150"),
    ("EG S.150", "EG", "150"),
    ("WH s. 7", "WH", "7"),
])
def test_zerlege_buch_seite(roh, buch, seite):
    z = lp.zerlege_quelle(roh)
    assert z["quelle"] == "buch"
    assert z["buch"] == buch
    assert z["seite"] == seite
    assert z["nummer"] == ""


def test_zerlege_reiner_buchname():
    z = lp.zerlege_quelle("WH")
    assert z == {"quelle": "buch", "buch": "WH", "nummer": "", "seite": ""}


def test_zerlege_leer_ist_ohne():
    for roh in (None, "", "   "):
        assert lp.zerlege_quelle(roh) == {"quelle": "ohne", "buch": "", "nummer": "", "seite": ""}


def test_zerlege_nichts_verloren_bei_unbekanntem_muster():
    """Ein unsauberes Muster landet als Buch — der Text bleibt sichtbar."""
    z = lp.zerlege_quelle("Sonderheft 2026")
    assert z["quelle"] == "buch"
    assert z["buch"] == "Sonderheft 2026"


def test_quelle_pruefen():
    for q in ("buch", "kopie", "ohne"):
        assert lp.quelle_pruefen(q) == q
    with pytest.raises(Exception):
        lp.quelle_pruefen("gibtsnicht")
    with pytest.raises(Exception):
        lp.quelle_pruefen(None)


@pytest.mark.parametrize("quelle,buch,nummer,seite,erwartet", [
    ("kopie", "", "", "", "Kopie"),
    ("buch", "JN", "1297", "", "JN 1297"),
    ("buch", "WH", "", "150", "WH S. 150"),
    ("buch", "WH", "", "", "WH"),
    ("ohne", "", "", "", ""),
    ("buch", "", "42", "", "42"),
    ("buch", "JN", "7", "3", "JN 7 S. 3"),
])
def test_anzeige_text(quelle, buch, nummer, seite, erwartet):
    assert lp.anzeige_text(quelle, buch, nummer, seite) == erwartet


# ── 2. API ───────────────────────────────────────────────────────────────────

def _anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


def _aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def _fehler(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 417, r.text
    return r.json()


def _stammdaten(sf):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Mitglied,
    )
    from diakronos_app.models.psalmos import Lied
    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        s.add(User(name="planer_chor", email="planer_chor", enabled=True))
        s.flush()
        s.add(Mitglied(name="planer_chor", user="planer_chor", email="planer_chor",
                       vorname="P", nachname="Test"))
        s.add(DienstbereichVerantwortlicher(name="bv-chor", parent="Chor",
                                            parenttype="Dienstbereich",
                                            parentfield="verantwortliche", user="planer_chor"))
        s.add_all([
            Lied(name="KOP-1", titel="Loses Blatt", aktiv=True,
                 gesangbuch_nummer="KOP", quelle="kopie"),
            Lied(name="BUCH-1", titel="Buchlied", aktiv=True,
                 gesangbuch_nummer="1297", buch="JN", quelle="buch"),
            Lied(name="OHNE-1", titel="Ohne Angabe", aktiv=True, quelle="ohne"),
        ])


@pytest.fixture()
def chor_def():
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    return kochbuch_laden("chorplan")


def test_lied_speichern_setzt_quelle(client, patched_db, chor_def):
    _stammdaten(patched_db)
    _aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    erg = _aufruf(client, "lied_speichern", plantyp="chorplan", lied="OHNE-1",
                  daten={"titel": "Jetzt Kopie", "quelle": "kopie"})
    assert erg["quelle"] == "kopie"
    detail = client.get(MPFAD + "get_lied_detail", params={"lied": "OHNE-1"}).json()["message"]
    assert detail["lied"]["quelle"] == "kopie"
    assert detail["lied"]["anzeige"] == "Kopie"


def test_lied_speichern_unbekannte_quelle(client, patched_db, chor_def):
    _stammdaten(patched_db)
    _aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    _fehler(client, "lied_speichern", plantyp="chorplan", lied="OHNE-1",
            daten={"quelle": "zauberbuch"})


def test_get_lieder_anzeige_ohne_nr(client, patched_db):
    _stammdaten(patched_db)
    lieder = {l["name"]: l for l in client.get(
        MPFAD + "get_lieder", params={"limit": 50}).json()["message"]}
    assert lieder["KOP-1"]["anzeige"] == "Kopie"
    assert "Nr." not in lieder["KOP-1"]["anzeige"]
    assert lieder["BUCH-1"]["anzeige"] == "JN 1297"
    assert lieder["OHNE-1"]["anzeige"] == ""


def test_lied_speichern_kopie_exponiert_keine_nummer(client, patched_db, chor_def):
    """Eine Kopie traegt keine Nummer — auch wenn zuvor eine gesetzt war."""
    _stammdaten(patched_db)
    _aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    _aufruf(client, "lied_speichern", plantyp="chorplan", lied="BUCH-1",
            daten={"quelle": "kopie", "gesangbuch_nummer": "", "buch": ""})
    detail = client.get(MPFAD + "get_lied_detail", params={"lied": "BUCH-1"}).json()["message"]
    assert detail["lied"]["quelle"] == "kopie"
    assert detail["lied"]["anzeige"] == "Kopie"
