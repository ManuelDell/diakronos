"""R-6: Plan-Rahmen am EINEN Rechte-Kern (Plan ``diakronos-rechte`` Abschnitt 5).

Soll (Manuel 11.11.):
  * Vorlagen gehoeren Gruppen; HV und MV der Gruppe pflegen sie, der Admin alle.
  * Wer Kalender erstellen darf (HV/MV), darf Dienstplaene erstellen und
    delegieren — Mitglieder mit blossem Schreibrecht nicht.
  * Den Plan sieht nur, wer in einen Kalender der Gruppe schreiben darf; alle
    anderen sehen nur ihre eigenen Dienste.
  * Dienstbereiche entfallen; eine Bestandsvorlage ohne Gruppe gehoert der
    EINEN Gruppe ihres Bereichs — gibt es mehrere, ordnet der Admin zu.
"""

from __future__ import annotations

from datetime import date

import pytest

from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.models.planrahmen import Plan, Plantyp, PlantypVersion
from diakronos_app.models.rechte import RechteFreigabe, RechteModul
from diakronos_app.planrahmen.rechte import Rechte, plantyp_gruppen

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, ANNA, CHORSAENGER, FREMD, GL, MIRA, REBEKKA, SAMUEL, SOPRAN, unter, welt,
)


def _vorlage(s, schluessel, *, gruppen=None, bereich=None) -> Plantyp:
    typ = Plantyp(schluessel=schluessel, name=schluessel, bereich=bereich)
    s.add(typ)
    s.flush()
    definition = {"id": schluessel, "name": schluessel}
    if gruppen is not None:
        definition["gruppen"] = list(gruppen)
    s.add(PlantypVersion(plantyp=typ.id, versionsnummer=1, gueltig_ab=date(2026, 1, 1),
                         definition=definition))
    s.flush()
    return typ


def _plan(s, typ, *, verantwortlich=None, veroeffentlicht=True) -> Plan:
    p = Plan(plantyp=typ.id, titel="Plan", parameter={}, verantwortlich=verantwortlich,
             veroeffentlichter_stand={"termine": [], "eintraege": []} if veroeffentlicht else None)
    s.add(p)
    s.flush()
    return p


@pytest.fixture()
def plaene(unter):
    """Chor hat Modul „Dienstplaene“ (test_r1), Jugend nicht. Kalender chorkal
    gehoert dem Chor; ANNA darf dort schreiben (Freigabe in test_r1)."""
    s = unter
    chor = _vorlage(s, "chorplan", gruppen=["Chor"])
    jugend = _vorlage(s, "jugendplan", gruppen=["Jugend"])
    s.commit()
    return s, chor, jugend


def R(s, wer):
    return Rechte(s, wer)


def test_hv_und_mv_pflegen_vorlage_und_plaene_ihrer_gruppe(plaene):
    s, chor, jugend = plaene
    for wer in (REBEKKA, MIRA):
        assert R(s, wer).darf_plantyp_bearbeiten(chor)
        assert R(s, wer).darf_plan_anlegen(chor)
        assert not R(s, wer).darf_plantyp_bearbeiten(jugend)
    assert R(s, ADMIN).darf_plantyp_bearbeiten(jugend)


def test_schreibrecht_am_kalender_gibt_keine_planrechte(plaene):
    """Manuel: Mitglieder mit Schreibrecht duerfen keine Dienstplaene erstellen."""
    s, chor, _j = plaene
    assert not R(s, ANNA).darf_plan_anlegen(chor)
    assert not R(s, ANNA).darf_plantyp_bearbeiten(chor)
    assert not R(s, GL).darf_plan_anlegen(chor)          # GL der Untergruppe auch nicht


def test_modul_aus_heisst_keine_planrechte(plaene):
    """Jugend hat das Modul „Dienstplaene“ nicht — Samuel (HV) plant dort nicht."""
    s, _c, jugend = plaene
    assert not R(s, SAMUEL).darf_plan_anlegen(jugend)
    s.add(RechteModul(gruppe="Jugend", modul="dienstplaene"))
    s.commit()
    assert R(s, SAMUEL).darf_plan_anlegen(jugend)


def test_delegation_planverantwortliche_nur_dieser_plan(plaene):
    s, chor, _j = plaene
    p = _plan(s, chor, verantwortlich="M-Sa")          # CHORSAENGER
    s.commit()
    assert R(s, CHORSAENGER).darf_plan_bearbeiten(p, chor)
    assert not R(s, CHORSAENGER).darf_plantyp_bearbeiten(chor)
    assert not R(s, CHORSAENGER).darf_plan_bearbeiten(_plan(s, chor), chor)


def test_ganzen_plan_sieht_nur_wer_im_gruppenkalender_schreibt(plaene):
    s, chor, _j = plaene
    p = _plan(s, chor)
    s.commit()
    assert R(s, ANNA).plan(p, chor) is False                    # lesen, nicht bearbeiten
    with pytest.raises(PermErr):
        R(s, CHORSAENGER).plan(p, chor)                         # nur eigene Dienste
    with pytest.raises(PermErr):
        R(s, FREMD).plan(p, chor)
    assert R(s, REBEKKA).plan(p, chor) is True
    s.add(RechteFreigabe(typ="kalender", objekt="chorkal", benutzer=CHORSAENGER, lesen=True, schreiben=True))
    s.commit()
    assert R(s, CHORSAENGER).plan(p, chor) is False


def test_vorlage_anlegen_nur_fuer_eigene_gruppen(plaene):
    s, chor, _j = plaene
    assert R(s, REBEKKA).darf_vorlage_anlegen({"Chor"})
    assert not R(s, REBEKKA).darf_vorlage_anlegen({"Chor", "Jugend"})
    assert not R(s, REBEKKA).darf_vorlage_anlegen(set())
    assert R(s, ADMIN).darf_vorlage_anlegen(set())
    with pytest.raises(PermErr):
        R(s, MIRA).vorlagen_gruppen_pruefen({"Chor"}, {"Chor", "Jugend"})
    with pytest.raises(PermErr):
        R(s, MIRA).vorlagen_gruppen_pruefen({"Chor"}, set())
    R(s, MIRA).vorlagen_gruppen_pruefen({"Chor"}, {"Chor"})


def test_bestandsvorlage_ohne_gruppe_gehoert_der_einzigen_gruppe_des_bereichs(plaene):
    from diakronos_app.models.diakonos import Gruppe

    s, _c, _j = plaene
    s.get(Gruppe, "Chor").dienstbereich = "musik"
    s.commit()
    alt = _vorlage(s, "alt-musik", bereich="musik")
    s.commit()
    assert plantyp_gruppen(s, alt) == {"Chor"}
    assert R(s, REBEKKA).darf_plantyp_bearbeiten(alt)
    # Zweite Gruppe im Bereich -> keine eindeutige Zuordnung, nur der Admin.
    s.add(Gruppe(name="Lobpreis", gruppenname="Lobpreis", dienstbereich="musik"))
    s.commit()
    assert plantyp_gruppen(s, alt) == set()
    assert not R(s, REBEKKA).darf_plantyp_bearbeiten(alt)
    assert R(s, ADMIN).darf_plantyp_bearbeiten(alt)


def test_dienstbereiche_sind_admin_sache(plaene):
    s, _c, _j = plaene
    assert not R(s, REBEKKA).bereich("musik")
    assert R(s, ADMIN).bereich("musik")
