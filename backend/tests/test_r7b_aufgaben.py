"""R-7b: Aufgaben — eigene Aufgaben und zugewiesene Gruppenaufgaben.

Soll (Manuel 11.11.): „eigene Aufgaben und Aufgaben die man in der Gruppe
zuweisen kann. Abhaken darf der es zugewiesen bekommen hat.“ HV/MV (bzw. GL in
der Untergruppe) weisen zu; zugewiesen wird nur an Personen der Gruppe.
Eine eigene Aufgabe sieht und pflegt nur ihr Besitzer.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    CHORSAENGER, FREMD, MIRA, REBEKKA, SAMUEL, unter, welt,
)
from test_r1_rechte_kern import GL, SOPRAN

SAENGER_ID = "M-Sa"


@pytest.fixture(autouse=True)
def _zuruecksetzen():
    yield
    set_user("Administrator")


def _als(user, fn, *a, **kw):
    set_user(user)
    try:
        return fn(*a, **kw)
    finally:
        set_user("Administrator")


def _aufgabe(gruppe="Chor", **kw):
    from diakronos_app.api import gruppen as G

    return _als(REBEKKA, G.create_aufgabe, "Noten kopieren", gruppe_id=gruppe, **kw)["name"]


def test_zugewiesene_person_hakt_ab_andere_nicht(welt):
    from diakronos_app.api import gruppen as G

    aid = _aufgabe(zugewiesen_an=SAENGER_ID)
    eintrag = _als(CHORSAENGER, G.get_aufgaben, gruppe_id="Chor")["data"][0]
    assert eintrag["zugewiesen_an"] == SAENGER_ID and eintrag["zugewiesen_name"]
    assert eintrag["darf_abhaken"] and not eintrag["darf_bearbeiten"]
    assert _als(CHORSAENGER, G.toggle_aufgabe, aid)["erledigt"] == 1
    # Leitung darf weiterhin (HV meint HV und MV)
    assert _als(MIRA, G.toggle_aufgabe, aid)["erledigt"] == 0

    # nicht zugewiesen: ein Gruppenmitglied hakt nicht ab
    frei = _aufgabe()
    assert not _als(CHORSAENGER, G.get_aufgaben, gruppe_id="Chor")["data"][1]["darf_abhaken"]
    with pytest.raises(PermErr):
        _als(CHORSAENGER, G.toggle_aufgabe, frei)


def test_zuweisen_nur_leitung_und_nur_an_gruppenmitglieder(welt):
    from diakronos_app.api import gruppen as G

    aid = _aufgabe()
    with pytest.raises(PermErr):
        _als(CHORSAENGER, G.aufgabe_zuweisen, aid, SAENGER_ID)
    for fremde_person in ("M-Fr", "M-Samuel", "gibt-es-nicht"):
        with pytest.raises(ValidationError):
            _als(MIRA, G.aufgabe_zuweisen, aid, fremde_person)
    # MV ohne Mitgliedschaftszeile zaehlt ueber die Rolle
    assert _als(REBEKKA, G.aufgabe_zuweisen, aid, "M-Mira")["zugewiesen_an"] == "M-Mira"
    assert _als(MIRA, G.aufgabe_zuweisen, aid, SAENGER_ID)["zugewiesen_an"] == SAENGER_ID
    assert _als(MIRA, G.aufgabe_zuweisen, aid, None)["zugewiesen_an"] is None
    with pytest.raises(ValidationError):
        _aufgabe(zugewiesen_an="M-Fr")
    # fremde Gruppe: weder anlegen noch zuweisen
    with pytest.raises(PermErr):
        _als(SAMUEL, G.aufgabe_zuweisen, aid, SAENGER_ID)


def test_loeschen_nur_leitung(welt):
    from diakronos_app.api import gruppen as G
    from diakronos_app.models.rechte import RechteObjekt

    aid = _aufgabe(zugewiesen_an=SAENGER_ID)
    with pytest.raises(PermErr):
        _als(CHORSAENGER, G.delete_aufgabe, aid)
    assert _als(MIRA, G.delete_aufgabe, aid)["success"]
    assert welt.query(RechteObjekt).filter_by(typ="aufgabe", objekt=aid).count() == 0
    with pytest.raises(PermErr):
        _als(MIRA, G.toggle_aufgabe, aid)


def test_eigene_aufgabe_ist_privat(welt):
    from diakronos_app.api import gruppen as G

    eigene = _als(FREMD, G.create_aufgabe, "Zahnarzt anrufen")["name"]
    with pytest.raises(ValidationError):
        _als(FREMD, G.create_aufgabe, "Kuchen", zugewiesen_an=SAENGER_ID)
    meine = _als(FREMD, G.get_meine_aufgaben)["data"]
    assert [a["name"] for a in meine] == [eigene] and meine[0]["eigene"] and meine[0]["darf_abhaken"]
    assert eigene not in {a["name"] for a in _als(CHORSAENGER, G.get_meine_aufgaben)["data"]}
    for fremd in (CHORSAENGER, REBEKKA):
        for fn in (G.toggle_aufgabe, G.delete_aufgabe):
            with pytest.raises(PermErr):
                _als(fremd, fn, eigene)
        with pytest.raises(PermErr):
            _als(fremd, G.aufgabe_zuweisen, eigene, SAENGER_ID)
    assert _als(FREMD, G.toggle_aufgabe, eigene)["erledigt"] == 1
    assert _als(FREMD, G.delete_aufgabe, eigene)["success"]


def test_meine_aufgaben_enthalten_zugewiesene(welt):
    from diakronos_app.api import gruppen as G

    aid = _aufgabe(zugewiesen_an=SAENGER_ID)
    eigene = _als(CHORSAENGER, G.create_aufgabe, "Eigenes")["name"]
    meine = {a["name"]: a for a in _als(CHORSAENGER, G.get_meine_aufgaben)["data"]}
    assert set(meine) == {aid, eigene}
    assert meine[aid]["gruppe"] == "Chor" and not meine[aid]["eigene"]
    # Modul aus: die Gruppenaufgabe verschwindet auch aus „meine Aufgaben“
    from diakronos_app.models.rechte import RechteModul

    welt.query(RechteModul).filter_by(gruppe="Chor", modul="aufgaben").delete()
    welt.commit()
    assert {a["name"] for a in _als(CHORSAENGER, G.get_meine_aufgaben)["data"]} == {eigene}


def test_untergruppe_gl_weist_eigenen_mitgliedern_zu(unter):
    from diakronos_app.api import gruppen as G

    aid = _als(GL, G.create_aufgabe, "Stimmprobe", untergruppe_id="Sopran",
               zugewiesen_an="M-Sophie")["name"]
    assert _als(SOPRAN, G.toggle_aufgabe, aid)["erledigt"] == 1
    with pytest.raises(ValidationError):
        _als(GL, G.aufgabe_zuweisen, aid, SAENGER_ID)  # Chor, aber nicht Sopran
    with pytest.raises(PermErr):
        _als(CHORSAENGER, G.toggle_aufgabe, aid)


def test_dsgvo_eigene_aufgaben_fallen_zuweisung_wird_neutral(welt):
    from diakronos_app import dsgvo_anonymisierung as modul
    from diakronos_app.api import gruppen as G
    from diakronos_app.models.diakonos import GruppenAufgabe

    eigene = _als(CHORSAENGER, G.create_aufgabe, "Privat")["name"]
    gruppe = _aufgabe(zugewiesen_an=SAENGER_ID)
    ergebnis = modul.anonymisiere(welt, SAENGER_ID, {CHORSAENGER})
    welt.flush()
    assert welt.get(GruppenAufgabe, eigene) is None
    assert welt.get(GruppenAufgabe, gruppe).zugewiesen_an == ergebnis["kennung"]


def test_ui_r9_gruppenseite_liefert_dieselben_aufgabenfelder(unter):
    """UI-R9: Die Gruppen-/Untergruppenseite liest die Aufgaben aus
    get_*_detail — dort fehlten Zuweisung und darf_abhaken/-bearbeiten."""
    from diakronos_app.api import gruppen as G

    _aufgabe(zugewiesen_an=SAENGER_ID)
    _aufgabe()
    for wer in (CHORSAENGER, REBEKKA, MIRA):
        detail = _als(wer, G.get_gruppe_detail, "Chor")["aufgaben"]
        assert detail == _als(wer, G.get_aufgaben, gruppe_id="Chor")["data"], wer
    zeilen = {a["zugewiesen_an"]: a for a in _als(CHORSAENGER, G.get_gruppe_detail, "Chor")["aufgaben"]}
    assert zeilen[SAENGER_ID]["darf_abhaken"] and zeilen[SAENGER_ID]["zugewiesen_name"]
    assert not zeilen[None]["darf_abhaken"]

    _als(GL, G.create_aufgabe, "Stimmprobe", untergruppe_id="Sopran", zugewiesen_an="M-Sophie")
    for wer in (SOPRAN, GL):
        detail = _als(wer, G.get_untergruppe_detail, "Sopran")["aufgaben"]
        assert detail == _als(wer, G.get_aufgaben, untergruppe_id="Sopran")["data"], wer
    assert _als(SOPRAN, G.get_untergruppe_detail, "Sopran")["aufgaben"][0]["darf_abhaken"]


def test_ui_r9_meine_aufgaben_sagt_ob_anlegen_erlaubt(welt):
    """Die Kachel blendet „Eigene Aufgabe“ nur nach dem Server-Flag ein —
    dasselbe, was create_aufgabe ohne Gruppe tatsaechlich erlaubt."""
    from diakronos_app.api import gruppen as G

    for wer in (CHORSAENGER, FREMD, REBEKKA):
        flag = _als(wer, G.get_meine_aufgaben)["darf_anlegen"]
        try:
            _als(wer, G.create_aufgabe, "Probe")
            erlaubt = True
        except PermErr:
            erlaubt = False
        assert flag == erlaubt, wer


def test_r12k_meine_aufgaben_nennen_den_gruppennamen(unter):
    """R-12k (Review UI-R9b): Die Kachel zeigt den NAMEN der Einheit, nicht die Kennung.

    Kennung und Anzeigename unterscheiden sich hier bewusst — sonst waere der
    Test blind (im Demo-Stack sind beide oft gleich).
    """
    from diakronos_app.api import gruppen as G
    from diakronos_app.models.diakonos import Gruppe, Untergruppe

    unter.get(Gruppe, "Chor").gruppenname = "Kirchenchor"
    unter.get(Untergruppe, "Sopran").untergruppenname = "Sopranstimmen"
    unter.commit()
    in_gruppe = _aufgabe(zugewiesen_an="M-Sophie")
    in_ug = _als(GL, G.create_aufgabe, "Stimmprobe", untergruppe_id="Sopran", zugewiesen_an="M-Sophie")["name"]
    eigene = _als(SOPRAN, G.create_aufgabe, "Eigenes")["name"]

    meine = {a["name"]: a for a in _als(SOPRAN, G.get_meine_aufgaben)["data"]}
    assert meine[in_gruppe]["gruppe_name"] == "Kirchenchor"
    assert meine[in_ug]["gruppe_name"] == "Sopranstimmen"
    assert meine[eigene]["gruppe_name"] is None
