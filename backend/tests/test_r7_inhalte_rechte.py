"""R-7: Beitraege, Wiki und Lieder am EINEN Rechte-Kern (Plan Abschnitt 6/7).

Soll (Manuel 11.11.):
  * Beitraege und Wiki sind gruppengebunden: HV/MV legen an und pflegen,
    Gruppenmitglieder lesen; Inhalte fuer die ganze Gemeinde legt der Admin an.
  * Lieder: Bearbeiten duerfen HV/MV der Gruppen mit Modul „Lieder“; wer das
    Modul in keiner Gruppe hat, sieht „Lieder“ nicht.
  * Eine Gruppe im Papierkorb verleiht keine Rechte.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.exceptions import DoesNotExistError, PermissionError as PermErr
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, ANNA, CHORSAENGER, FREMD, GL, MIRA, REBEKKA, SAMUEL, unter, welt,
)


@pytest.fixture(autouse=True)
def _zuruecksetzen():
    yield
    set_user("Administrator")


def _ids(liste, schluessel="id"):
    return {e[schluessel] for e in liste}


def test_gruppenbeitrag_lesen_nur_die_gruppe(welt):
    from diakronos_app.api import beitraege as B

    set_user(REBEKKA)
    bid = B.create_beitrag("Probe", "Text", gruppe="Chor")["beitrag_id"]
    set_user(CHORSAENGER)
    assert bid in _ids(B.get_beitraege_liste())
    assert B.get_beitrag_detail(bid)["id"] == bid
    for fremd in (FREMD, SAMUEL):
        set_user(fremd)
        assert bid not in _ids(B.get_beitraege_liste())
        with pytest.raises(DoesNotExistError):
            B.get_beitrag_detail(bid)


def test_gruppenbeitrag_pflegen_hv_mv_nicht_mitglieder(welt):
    from diakronos_app.api import beitraege as B

    set_user(MIRA)
    bid = B.create_beitrag("MV-Beitrag", "Text", gruppe="Chor")["beitrag_id"]
    set_user(REBEKKA)
    assert B.update_beitrag(bid, titel="Neu")["success"]
    set_user(CHORSAENGER)
    with pytest.raises(PermErr):
        B.update_beitrag(bid, titel="Nein")
    with pytest.raises(PermErr):
        B.create_beitrag("Nein", "Text", gruppe="Chor")
    set_user(SAMUEL)
    with pytest.raises(PermErr):
        B.create_beitrag("Fremd", "Text", gruppe="Chor")


def test_gemeindebeitrag_nur_admin_nicht_mitgliederverwaltung(welt):
    from diakronos_app.api import beitraege as B

    welt.add(HasRole(name="hr-ma-r7", parent=FREMD, parenttype="User", role="Mitgliederadministrator"))
    welt.commit()
    for wer in (REBEKKA, FREMD):
        set_user(wer)
        with pytest.raises(PermErr):
            B.create_beitrag("Gemeinde", "Text")
    set_user(ADMIN)
    bid = B.create_beitrag("Gemeinde", "Text")["beitrag_id"]
    set_user(SAMUEL)
    assert bid in _ids(B.get_beitraege_liste())                 # alle Mitglieder lesen


def test_wiki_gruppe_und_gemeinde(welt):
    from diakronos_app.api import wiki as W

    set_user(REBEKKA)
    aid = W.create_wiki_artikel("Chor-Wiki", "Inhalt", gruppe="Chor")["artikel_id"]
    set_user(CHORSAENGER)
    assert aid in _ids(W.get_wiki_artikel_liste())
    set_user(FREMD)
    assert aid not in _ids(W.get_wiki_artikel_liste())
    with pytest.raises(DoesNotExistError):
        W.get_wiki_artikel_detail(aid)
    with pytest.raises(PermErr):
        W.create_wiki_artikel("Gemeinde-Wiki", "Inhalt")


def test_lieder_nur_mit_modul(welt):
    from diakronos_app.api.psalmos import musik as M

    set_user(CHORSAENGER)                                         # Chor hat Modul Lieder
    assert isinstance(M.get_lieder(), (list, dict))
    for wer in (SAMUEL, FREMD):                                   # Jugend ohne Modul / keine Gruppe
        set_user(wer)
        with pytest.raises(PermErr):
            M.get_lieder()
    assert M._is_musikverantwortlicher(REBEKKA)
    assert M._is_musikverantwortlicher(MIRA)
    assert not M._is_musikverantwortlicher(CHORSAENGER)
    assert not M._is_musikverantwortlicher(SAMUEL)


def test_gruppe_im_papierkorb_verleiht_keine_rechte(welt):
    from datetime import datetime

    from diakronos_app import rechte as R
    from diakronos_app.api.psalmos import musik as M
    from diakronos_app.models.diakonos import Gruppe

    assert R.gruppenrolle(REBEKKA, "Chor") == "HV"
    welt.get(Gruppe, "Chor").geloescht_am = datetime(2026, 11, 11, 12, 0)
    welt.commit()
    assert R.gruppenrolle(REBEKKA, "Chor") is None
    assert not R.modul_aktiv("Chor", "lieder")
    assert not M._is_musikverantwortlicher(REBEKKA)
    assert not R.darf(CHORSAENGER, R.LESEN, "kalender", "chorkal")


def test_anlegeorte_eine_abfrage_gleiche_regel_wie_einzelabfrage(unter):
    """UI-R6: „Wo darf ich anlegen?“ in EINER Abfrage — dieselbe Antwort wie
    get_meine_rechte je Einheit; Gemeinde nur fuer den Admin."""
    from diakronos_app.api import rechte as R

    einheiten = [("Chor", None), ("Chor", "Sopran"), ("Jugend", None)]
    for wer in (ADMIN, REBEKKA, MIRA, SAMUEL, GL, CHORSAENGER, FREMD):
        set_user(wer)
        for typ in ("beitrag", "wiki"):
            orte = R.get_anlegeorte(typ)["orte"]
            erwartet = [(g, u) for g, u in einheiten
                        if R.get_meine_rechte(typ, gruppe=g, untergruppe=u)["anlegen"]]
            assert {(o["gruppe"], o["untergruppe"]) for o in orte if not o["gemeinde"]} \
                == set(erwartet), (wer, typ)
            assert any(o["gemeinde"] for o in orte) == (wer == ADMIN)

    set_user(ADMIN)
    orte = R.get_anlegeorte("beitrag")["orte"]
    assert [o["titel"] for o in orte] == [
        "Alle Mitglieder der Gemeinde", "Chor", "Sopran", "Jugendkreis"]
    assert [o["tiefe"] for o in orte] == [0, 0, 1, 0]
    set_user(GL)
    assert [(o["gruppe"], o["untergruppe"]) for o in R.get_anlegeorte("wiki")["orte"]] == [("Chor", "Sopran")]
    set_user(CHORSAENGER)
    assert R.get_anlegeorte("beitrag")["orte"] == []


def test_r12l_detail_sagt_darf_bearbeiten_wie_die_liste(welt):
    """R-12l (Review UI-R6d): Die Leseseite braucht ``darf_bearbeiten`` aus dem Detail.

    Vorher kam das Feld nur aus der Liste — die Leseseite musste sie zusaetzlich
    laden, und aeltere Eintraege jenseits des Listenlimits bzw. unveroeffentlichte
    Beitraege bekamen keine Knoepfe. Erwartet: Detail und Liste sagen dasselbe.
    """
    from diakronos_app.api import beitraege as B
    from diakronos_app.api import wiki as W

    set_user(REBEKKA)
    bid = B.create_beitrag("Probe", "Text", gruppe="Chor")["beitrag_id"]
    aid = W.create_wiki_artikel("Chor-Wiki", "Inhalt", gruppe="Chor")["artikel_id"]
    for wer, erwartet in ((REBEKKA, True), (MIRA, True), (CHORSAENGER, False)):
        set_user(wer)
        liste_b = {x["id"]: x for x in B.get_beitraege_liste()}
        liste_w = {x["id"]: x for x in W.get_wiki_artikel_liste()}
        assert B.get_beitrag_detail(bid)["darf_bearbeiten"] is erwartet, wer
        assert W.get_wiki_artikel_detail(aid)["darf_bearbeiten"] is erwartet, wer
        assert liste_b[bid]["darf_bearbeiten"] is erwartet, wer
        assert liste_w[aid]["darf_bearbeiten"] is erwartet, wer
