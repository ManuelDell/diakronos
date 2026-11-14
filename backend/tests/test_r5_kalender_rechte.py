"""R-5: Kalender am EINEN Rechte-Kern (Plan ``diakronos-rechte`` Abschnitt 4).

Soll (Manuel 11.11.):
  * Rechte je Kalender und Person: Lesen · Schreiben · Moderieren.
  * Schreiben ohne Moderationsrecht ist ein Vorschlag (P0-3); HV/MV pruefen
    die Gruppenstufe, GL die Untergruppenstufe.
  * „Oeffentlich“ (alle Mitglieder der Gemeinde): jeder neue Termin geht in
    die Gemeinde-Moderation — auch der des Admins (zweite Freigabeschicht).
  * Was eine GL an Gruppe/Gemeinde gibt, prueft zuerst die Gruppenleitung.
  * HV/MV legen Kalender ihrer Gruppe an, GL die ihrer Untergruppe;
    Gemeinde-Kalender Admin und Kalender-Moderation.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from diakronos_app import rechte as R
from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.kronos import Element, Kalender
from diakronos_app.models.rechte import RechteFreigabe, RechteObjekt

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, ANNA, CHORSAENGER, FREMD, GL, MIRA, MODERATOR, REBEKKA, SAMUEL, SOPRAN, unter, welt,
)

KALENDER = ("chorkal", "chor-intern", "jugendkal", "sopran-kal", "sopran-offen",
            "chor-oeffentlich", "gemeinde-kal")


@pytest.fixture()
def kal(unter):
    for name in KALENDER:
        unter.add(Kalender(name=name, calendar_name=name, calendar_color="#123456",
                           selbstverwaltet=0, docstatus=0, idx=0))
    unter.add_all([
        RechteObjekt(typ="kalender", objekt="gemeinde-kal", gruppe=None),
        RechteFreigabe(typ="kalender", objekt="gemeinde-kal", benutzer=ANNA, lesen=True, schreiben=True),
    ])
    unter.commit()
    yield unter
    set_user("Administrator")


def _kal(user):
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    set_user(user)
    return {c["name"]: c for c in get_accessible_calendars()}


def _neu(user, kalender, status="Festgelegt", titel="Probe"):
    from diakronos_app.api.kronos import event_crud

    set_user(user)
    return event_crud.create_event(titel, "2026-12-01 10:00:00", "2026-12-01 11:00:00",
                                   kalender, status=status)


def _freigeben(user, termin):
    from diakronos_app.api.kronos import event_crud

    set_user(user)
    event_crud.update_event(termin, status="Festgelegt")


def _stand(sess, termin):
    sess.expire_all()
    e = sess.get(Element, termin)
    return e.status, e.moderation_offen or ""


# ── Kern: Stufen ────────────────────────────────────────────────────────────

def test_stufen_je_rolle(kal):
    assert R.moderationsstufen(REBEKKA, "kalender", "chorkal") == []
    assert R.moderationsstufen(ANNA, "kalender", "chorkal") == ["gruppe"]      # Schreiben != Freigeben
    assert R.moderationsstufen(GL, "kalender", "chorkal") == ["gruppe"]
    assert R.moderationsstufen(REBEKKA, "kalender", "chor-oeffentlich") == ["gemeinde"]
    assert R.moderationsstufen(ADMIN, "kalender", "chor-oeffentlich") == ["gemeinde"]
    assert R.moderationsstufen(GL, "kalender", "chor-oeffentlich") == ["gruppe", "gemeinde"]
    assert R.moderationsstufen(GL, "kalender", "sopran-kal") == []
    assert R.moderationsstufen(GL, "kalender", "sopran-offen") == ["gruppe"]
    assert R.moderationsstufen(ANNA, "kalender", "gemeinde-kal") == ["gemeinde"]
    assert R.moderationsstufen(MODERATOR, "kalender", "gemeinde-kal") == []


def test_pruefstufen_je_rolle(kal):
    assert R.pruefstufen(REBEKKA, "kalender", "chorkal") == ["gruppe"]
    assert R.pruefstufen(MIRA, "kalender", "chor-oeffentlich") == ["gruppe"]
    assert R.pruefstufen(MODERATOR, "kalender", "chor-oeffentlich") == ["gemeinde"]
    assert R.pruefstufen(MODERATOR, "kalender", "chorkal") == []      # nicht oeffentlich: keine Gemeindestufe
    assert R.pruefstufen(GL, "kalender", "sopran-kal") == ["untergruppe"]
    assert R.pruefstufen(REBEKKA, "kalender", "sopran-kal") == ["untergruppe", "gruppe"]
    assert R.pruefstufen(ANNA, "kalender", "chorkal") == []
    assert R.pruefstufen(CHORSAENGER, "kalender", "chorkal") == []


# ── Adapter get_accessible_calendars ───────────────────────────────────────

def test_adapter_liefert_kern_rechte(kal):
    reb = _kal(REBEKKA)
    assert reb["chorkal"]["write"] and reb["chorkal"]["direkt"] and reb["chorkal"]["is_moderator"]
    assert "chor-intern" in reb
    assert not reb["jugendkal"]["write"]                       # oeffentlich: nur lesen

    saenger = _kal(CHORSAENGER)
    assert not saenger["chorkal"]["write"] and not saenger["chorkal"]["is_moderator"]
    assert "chor-intern" in saenger                            # Einzelfreigabe lesen

    anna = _kal(ANNA)
    assert anna["chorkal"]["write"] and not anna["chorkal"]["direkt"]
    assert anna["chorkal"]["stufen"] == ["gruppe"]

    fremd = _kal(FREMD)
    assert "chorkal" not in fremd and "jugendkal" in fremd


def test_kalender_moderation_hat_keinen_vollzugriff_auf_gruppenkalender(kal):
    """Vorher: Kalenderadministrator sah und schrieb ALLE Kalender."""
    mod = _kal(MODERATOR)
    assert "chorkal" not in mod and "chor-intern" not in mod
    assert mod["chor-oeffentlich"]["is_moderator"]
    assert mod["gemeinde-kal"]["direkt"]


# ── Termine ─────────────────────────────────────────────────────────────────

def test_schreiben_ohne_moderationsrecht_wird_vorschlag_hv_gibt_frei(kal):
    res = _neu(ANNA, "chorkal")
    assert res["status"] == "Vorschlag"
    assert _stand(kal, res["id"]) == ("Vorschlag", "gruppe")
    _freigeben(REBEKKA, res["id"])
    assert _stand(kal, res["id"]) == ("Festgelegt", "")


def test_hv_und_mv_schreiben_direkt(kal):
    assert _neu(REBEKKA, "chorkal")["status"] == "Festgelegt"
    assert _neu(MIRA, "chorkal")["status"] == "Festgelegt"


def test_oeffentlicher_kalender_immer_gemeinde_moderation_auch_admin(kal):
    res = _neu(REBEKKA, "chor-oeffentlich")
    assert _stand(kal, res["id"]) == ("Vorschlag", "gemeinde")
    with pytest.raises(PermErr, match="Gemeinde-Moderation"):
        _freigeben(REBEKKA, res["id"])
    _freigeben(MODERATOR, res["id"])
    assert _stand(kal, res["id"]) == ("Festgelegt", "")

    eigen = _neu(ADMIN, "chor-oeffentlich")
    assert _stand(kal, eigen["id"]) == ("Vorschlag", "gemeinde")
    _freigeben(ADMIN, eigen["id"])                          # bewusster zweiter Schritt
    assert _stand(kal, eigen["id"])[0] == "Festgelegt"


def test_gemeinde_moderation_schreibt_nicht_an_der_gruppe_vorbei(kal):
    """Auch ein Termin der Kalender-Moderation im Gruppenkalender wartet
    zuerst auf die Gruppenleitung — es ist deren Kalender."""
    res = _neu(MODERATOR, "chor-oeffentlich")
    assert _stand(kal, res["id"]) == ("Vorschlag", "gruppe,gemeinde")


def test_gl_vorschlag_erst_gruppenleitung_dann_gemeinde(kal):
    res = _neu(GL, "chor-oeffentlich")
    assert _stand(kal, res["id"]) == ("Vorschlag", "gruppe,gemeinde")
    with pytest.raises(PermErr, match="Gruppenleitung"):
        _freigeben(MODERATOR, res["id"])
    _freigeben(MIRA, res["id"])
    assert _stand(kal, res["id"]) == ("Vorschlag", "gemeinde")
    _freigeben(MODERATOR, res["id"])
    assert _stand(kal, res["id"]) == ("Festgelegt", "")


def test_untergruppe_gl_prueft_eigene_untergruppe(kal):
    assert _neu(GL, "sopran-kal")["status"] == "Festgelegt"
    kal.add(RechteFreigabe(typ="kalender", objekt="sopran-kal", benutzer=SOPRAN, lesen=True, schreiben=True))
    kal.commit()
    res = _neu(SOPRAN, "sopran-kal")
    assert _stand(kal, res["id"]) == ("Vorschlag", "untergruppe")
    _freigeben(GL, res["id"])
    assert _stand(kal, res["id"])[0] == "Festgelegt"


def test_untergruppe_an_gruppe_freigegeben_hv_prueft(kal):
    res = _neu(GL, "sopran-offen")
    assert _stand(kal, res["id"]) == ("Vorschlag", "gruppe")
    _freigeben(REBEKKA, res["id"])
    assert _stand(kal, res["id"])[0] == "Festgelegt"


def test_ablehnen_durch_pruefer_der_aktuellen_stufe(kal):
    from diakronos_app.api.kronos import kanban_api

    res = _neu(ANNA, "chorkal")
    set_user(MIRA)
    kanban_api.resolve_conflict(res["id"], "ablehnen", grund="passt nicht")
    assert _stand(kal, res["id"])[0] == "Abgelehnt"


def test_kanban_freigabe_stufenweise(kal):
    from diakronos_app.api.kronos import kanban_api

    res = _neu(GL, "chor-oeffentlich")
    set_user(MIRA)
    erg = kanban_api.finalize_staged_events([res["id"]])
    assert _stand(kal, res["id"]) == ("Vorschlag", "gemeinde")
    # UI-R4: die Antwort sagt ehrlich, dass der Termin weiterwartet — und worauf.
    assert (erg["festgelegt"], erg["weitergereicht"]) == (0, 1)
    assert erg["ergebnisse"][res["id"]] == {"status": "Vorschlag", "offen": ["gemeinde"],
                                           "naechste_stufe": "gemeinde"}
    set_user(MODERATOR)
    erg = kanban_api.finalize_staged_events([res["id"]])
    assert _stand(kal, res["id"]) == ("Festgelegt", "")
    assert (erg["festgelegt"], erg["weitergereicht"]) == (1, 0)


def test_resolve_conflict_nennt_naechste_stufe(kal):
    """UI-R4: die Oberflaeche rechnet die naechste Stufe nicht selbst aus."""
    from diakronos_app.api.kronos import kanban_api

    res = _neu(GL, "chor-oeffentlich")
    set_user(MIRA)
    erg = kanban_api.resolve_conflict(res["id"], "festlegen")
    assert (erg["new_status"], erg["offen"], erg["naechste_stufe"]) == ("Vorschlag", ["gemeinde"], "gemeinde")
    set_user(MODERATOR)
    erg = kanban_api.resolve_conflict(res["id"], "festlegen")
    assert (erg["new_status"], erg["offen"], erg["naechste_stufe"]) == ("Festgelegt", [], None)


def test_aenderung_im_oeffentlichen_kalender_wartet_auf_gemeinde(kal):
    from diakronos_app.api.kronos import event_crud

    termin = _neu(REBEKKA, "chor-oeffentlich")["id"]
    _freigeben(MODERATOR, termin)
    set_user(REBEKKA)
    antwort = event_crud.update_event(termin, element_start="2026-12-02 10:00:00",
                                      element_end="2026-12-02 11:00:00")
    assert antwort.get("aenderung_wartet") is True

    set_user(REBEKKA)
    assert event_crud.get_offene_aenderungen() == []          # Gemeindestufe ist nicht ihre
    set_user(MODERATOR)
    offen = event_crud.get_offene_aenderungen()
    assert [o["stufe"] for o in offen] == ["gemeinde"]
    set_user(REBEKKA)
    with pytest.raises(PermErr):
        event_crud.aenderung_freigeben(offen[0]["name"])
    set_user(MODERATOR)
    event_crud.aenderung_freigeben(offen[0]["name"])
    kal.expire_all()
    assert str(kal.get(Element, termin).element_start).startswith("2026-12-02")


# ── Kalender anlegen, verwalten, freigeben ─────────────────────────────────

def test_kalender_anlegen_hv_mv_gl_und_gemeinde(kal):
    from diakronos_app.api.kronos import kalender_verwaltung as kv

    set_user(MIRA)
    kv.create_kalender("Chorproben", gruppe="Chor", standard_gruppe_lesen=0)
    obj = kal.execute(select(RechteObjekt).where(RechteObjekt.objekt == "Chorproben")).scalar_one()
    assert obj.gruppe == "Chor" and obj.standard_gruppe_lesen is False
    assert "Chorproben" not in _kal(CHORSAENGER)              # Frage beim Anlegen: nein
    assert "Chorproben" in _kal(REBEKKA)

    set_user(GL)
    kv.create_kalender("Sopranproben", untergruppe="Sopran")
    assert "Sopranproben" in _kal(SOPRAN)

    for user, kw in ((CHORSAENGER, {"gruppe": "Chor"}), (SAMUEL, {"gruppe": "Chor"}),
                     (GL, {"gruppe": "Chor"}), (REBEKKA, {})):
        set_user(user)
        with pytest.raises(PermErr):
            kv.create_kalender(f"Nein-{user}", **kw)

    set_user(MODERATOR)
    kv.create_kalender("Gemeindefeste")
    assert kal.execute(select(RechteObjekt.gruppe).where(
        RechteObjekt.objekt == "Gemeindefeste")).scalar_one() is None


def test_kalender_verwalten_und_loeschen_nur_leitung(kal):
    from diakronos_app.api.kronos import kalender_verwaltung as kv

    set_user(REBEKKA)
    kv.create_kalender("Wegwerf", gruppe="Chor")
    namen = [k["name"] for k in kv.get_kalender_verwaltung()["kalender"]]
    assert "Wegwerf" in namen and "jugendkal" not in namen
    set_user(CHORSAENGER)
    with pytest.raises(PermErr):
        kv.delete_kalender("Wegwerf", bestaetigt=1)
    set_user(MIRA)
    kv.delete_kalender("Wegwerf", bestaetigt=1)
    assert kal.execute(select(RechteObjekt).where(RechteObjekt.objekt == "Wegwerf")).first() is None


def test_moderationsrecht_vergeben_nur_hv_mv(kal):
    from diakronos_app.rechte import verwaltung as V

    with pytest.raises(PermErr):
        V.setze_freigabe(GL, "kalender", "sopran-kal", benutzer=SOPRAN, lesen=True, moderieren=True)
    V.setze_freigabe(GL, "kalender", "sopran-kal", benutzer=SOPRAN, lesen=True, schreiben=True)
    V.setze_freigabe(REBEKKA, "kalender", "chorkal", benutzer=CHORSAENGER, lesen=True, moderieren=True)
    assert "gruppe" in R.pruefstufen(CHORSAENGER, "kalender", "chorkal")
    with pytest.raises(ValidationError):
        V.setze_freigabe(REBEKKA, "wiki", "w1", benutzer=ANNA, moderieren=True)


def test_oeffentlich_beantragen_und_moderieren(kal):
    from diakronos_app.rechte import verwaltung as V

    assert V.beantrage_sichtbarkeit(REBEKKA, "kalender", "chorkal", "gemeinde")["gemeinde_status"] == "beantragt"
    assert "chorkal" not in _kal(FREMD)
    assert V.offene_sichtbarkeits_antraege(REBEKKA) == []
    antraege = V.offene_sichtbarkeits_antraege(MODERATOR)
    assert {(a["objekt"], a["stufe"]) for a in antraege} == {("chorkal", "gemeinde")}
    V.entscheide_sichtbarkeit(MODERATOR, "kalender", "chorkal", "gemeinde", True)
    assert "chorkal" in _kal(FREMD)

    # Ist der HV Admin, entfaellt die Moderation der Freigabe.
    assert V.beantrage_sichtbarkeit(ADMIN, "kalender", "chor-intern", "gemeinde")["gemeinde_status"] == "aktiv"


def test_untergruppe_an_gemeinde_erst_gruppenleitung(kal):
    from diakronos_app.rechte import verwaltung as V

    V.beantrage_sichtbarkeit(GL, "kalender", "sopran-kal", "gemeinde")
    with pytest.raises(ValidationError, match="Gruppenleitung"):
        V.entscheide_sichtbarkeit(MODERATOR, "kalender", "sopran-kal", "gemeinde", True)
    with pytest.raises(PermErr):
        V.entscheide_sichtbarkeit(GL, "kalender", "sopran-kal", "gruppe", True)
    V.entscheide_sichtbarkeit(MIRA, "kalender", "sopran-kal", "gruppe", True)
    V.entscheide_sichtbarkeit(MODERATOR, "kalender", "sopran-kal", "gemeinde", True)
    assert "sopran-kal" in _kal(FREMD)


def test_freigabe_an_person_wirkt_sofort(kal):
    from diakronos_app.rechte import verwaltung as V

    assert "chor-intern" not in _kal(FREMD)
    V.setze_freigabe(MIRA, "kalender", "chor-intern", benutzer=FREMD, lesen=True)
    assert "chor-intern" in _kal(FREMD)
    V.setze_freigabe(MIRA, "kalender", "chor-intern", benutzer=FREMD)
    assert "chor-intern" not in _kal(FREMD)


# ── Bestand: Rollen-Rechte gehen nicht verloren ────────────────────────────

def test_migration_rollenrechte_werden_einzelfreigaben(kal):
    from diakronos_app.models.core import HasRole, UserRole

    from rechte_hilfe import uebernehmen

    kal.add(Kalender(name="alt-kal", calendar_name="alt", calendar_color="#000000",
                     selbstverwaltet=0, docstatus=0, idx=0))
    kal.add(HasRole(name="hr-jm", parent=FREMD, parenttype="User", parentfield="roles", role="Jugendmitarbeiter"))
    kal.add(UserRole(name="ur-alt", parent="alt-kal", parenttype="Kalender", parentfield="schreibrechte",
                     role="Jugendmitarbeiter", docstatus=0, idx=1))
    kal.commit()
    uebernehmen(kal)
    fg = kal.execute(select(RechteFreigabe).where(
        RechteFreigabe.objekt == "alt-kal", RechteFreigabe.benutzer == FREMD)).scalar_one()
    assert fg.lesen and fg.schreiben and not fg.moderieren
    assert _kal(FREMD)["alt-kal"]["write"]


def test_brett_und_zaehler_folgen_der_offenen_stufe(kal):
    """UI-R4: `darf_pruefen` auf dem Brett und der gemeinsame Zaehler
    (Kachel/Seitenleiste/Badge) zeigen, was der Aufrufer auf der OFFENEN Stufe
    pruefen darf — nach der Gruppenstufe ist es nur noch die Gemeinde-Moderation."""
    from diakronos_app.api.kronos import kanban_api

    res = _neu(GL, "chor-oeffentlich")

    def _sicht(user):
        set_user(user)
        brett = {e["id"]: e for e in kanban_api.get_kanban_board_data()["vorschlaege"]}
        return brett.get(res["id"]), kanban_api.get_moderation_count()["count"]

    eintrag, zahl = _sicht(MIRA)
    assert eintrag["stufe"] == "gruppe" and eintrag["darf_pruefen"] is True and zahl == 1
    eintrag, zahl = _sicht(MODERATOR)
    assert eintrag is None or eintrag["darf_pruefen"] is False
    assert zahl == 0

    _freigeben(MIRA, res["id"])
    eintrag, zahl = _sicht(MIRA)
    assert (eintrag is None or eintrag["darf_pruefen"] is False) and zahl == 0
    eintrag, zahl = _sicht(MODERATOR)
    assert eintrag["stufe"] == "gemeinde" and eintrag["darf_pruefen"] is True and zahl == 1
    set_user("Administrator")


def test_antraege_tragen_titel_namen_und_ziel(kal):
    """UI-R4: keine technischen Schluessel in der Pruefliste; das Ziel bleibt
    „gemeinde“, auch wenn zuerst die Gruppenstufe dran ist."""
    from diakronos_app.rechte import verwaltung as V

    V.beantrage_sichtbarkeit(GL, "kalender", "sopran-kal", "gemeinde")
    (antrag,) = V.offene_sichtbarkeits_antraege(MIRA)
    assert antrag["stufe"] == "gruppe" and antrag["ziel"] == "gemeinde"
    assert antrag["titel"] == kal.get(Kalender, "sopran-kal").calendar_name
    assert antrag["gruppe_name"] == "Chor" and antrag["untergruppe_name"] == "Sopran"


def test_anlegen_nennt_offene_stufe_und_schreibbare_kalender_direkt(kal):
    """UI-R5: create_event/create_series nennen Status + offene Stufe;
    get_writable_calendars sagt, ob der Aufrufer direkt schreibt."""
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.api.kronos.permissions import get_writable_calendars

    res = _neu(GL, "chor-oeffentlich")
    assert (res["status"], res["offen"], res["naechste_stufe"]) == ("Vorschlag", ["gruppe", "gemeinde"], "gruppe")
    set_user(MIRA)
    serie = event_crud.create_series("Probe", "2026-12-01 19:00:00", "2026-12-01 20:00:00", "chorkal",
                                     repeat_type="weekly", series_end="2026-12-15", status="Festgelegt")
    assert serie["status"] == "Festgelegt" and serie["offen"] == [] and serie["naechste_stufe"] is None
    schreibbar = {c["name"]: c for c in get_writable_calendars()}
    assert schreibbar["chorkal"]["direkt"] is True and schreibbar["chorkal"]["gruppe"] == "Chor"
    set_user(ANNA)
    assert {c["name"]: c for c in get_writable_calendars()}["chorkal"]["direkt"] is False
    set_user("Administrator")
