"""CHAT-1: Chat-Rechte im EINEN Rechtesystem (Manuel 17.11.2026).

Konzept docs/konzepte/CHAT-KONZEPT.md (Abschnitt 2, 9, 10):
* Gruppenchat: alle Mitglieder lesen/schreiben/starten Umfragen (F5);
  HV/MV moderieren; Untergruppe eigener Raum (F4) mit GL + HV/MV.
* Modul ``chat`` aus = niemand ausser Admin.
* Personen finden: alle aktiven Gemeindemitglieder; nie Ausgetretene/
  Ausgeschlossene/Verstorbene; ohne Konto auffindbar, aber keine Nachricht.
* Meldestelle Direktnachrichten: nur Administrator (F7).
"""

from __future__ import annotations

import datetime as dt

import pytest

from diakronos_app import rechte as R
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

ADMIN = "admin@x.org"
HV = "hv@x.org"
MV = "mv@x.org"
GL = "gl@x.org"
SAENGER = "saenger@x.org"   # Mitglied Chor (nicht in der Untergruppe)
NOTEN = "noten@x.org"       # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"       # Gemeindemitglied ohne Gruppe
JUGEND_HV = "jhv@x.org"     # HV einer Gruppe ohne Chat-Modul


@pytest.fixture()
def welt(patched_db):
    s = patched_db()
    for user, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (GL, "Gl"), (SAENGER, "Sa"),
                       (NOTEN, "No"), (FREMD, "Fr"), (JUGEND_HV, "Jh")]:
        s.add(User(name=user, email=user, enabled=1))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=user, user=user))
    # Personen fuer die Auffindbarkeit
    s.add(Mitglied(name="M-ohnekonto", vorname="Helga", nachname="Ohne", email=None, user=None))
    s.add(Mitglied(name="M-ausgetreten", vorname="Aus", nachname="T", status="Ausgetreten"))
    s.add(Mitglied(name="M-austrittsdatum", vorname="Aus", nachname="D",
                   austritt_datum=dt.date(2026, 1, 1)))
    s.add(Mitglied(name="M-ausgeschlossen", vorname="Aus", nachname="S", ausgeschlossen=1))
    s.add(Mitglied(name="M-verstorben", vorname="Ver", nachname="S", status="Verstorben"))
    s.add(User(name="gesperrt@x.org", email="gesperrt@x.org", enabled=0))
    s.add(Mitglied(name="M-gesperrt", vorname="Ge", nachname="S", user="gesperrt@x.org"))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User", role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Notenausschuss", gruppe="Chor"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor", parentfield="mitglieder", mitglied="M-Sa"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-Noten", parentfield="mitglieder",
                                     mitglied="M-No"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer=GL, rolle="GL"),
        RechteGruppenrolle(gruppe="Jugend", benutzer=JUGEND_HV, rolle="HV"),
        RechteModul(gruppe="Chor", modul="chat"),
    ])
    s.commit()
    yield s
    s.close()


def ja(*a, **kw) -> bool:
    return bool(R.darf(*a, **kw))


def test_chat_ist_ein_modul_des_einen_systems():
    assert "chat" in R.MODULE
    for typ in ("chat_gespraech", "chat_nachricht", "chat_umfrage"):
        assert R.TYP_MODUL[typ] == "chat"


@pytest.mark.parametrize("wer", [HV, MV, GL, SAENGER, NOTEN])
def test_gruppenchat_mitglieder_lesen_schreiben_umfrage(welt, wer):
    assert ja(wer, "lesen", "chat_gespraech", gruppe="Chor")
    assert ja(wer, "schreiben", "chat_nachricht", gruppe="Chor", besitzer=wer)
    assert ja(wer, "anlegen", "chat_umfrage", gruppe="Chor")  # F5: jedes Mitglied


@pytest.mark.parametrize("wer", [FREMD, JUGEND_HV, "Guest", None, "unbekannt@x.org"])
def test_gruppenchat_fremde_nichts(welt, wer):
    assert not ja(wer, "lesen", "chat_gespraech", gruppe="Chor")
    assert not ja(wer, "schreiben", "chat_nachricht", gruppe="Chor", besitzer=wer)
    assert not ja(wer, "anlegen", "chat_umfrage", gruppe="Chor")


def test_fremde_nachricht_nur_leitung(welt):
    assert not ja(SAENGER, "schreiben", "chat_nachricht", gruppe="Chor", besitzer=HV)
    assert not ja(SAENGER, "moderieren", "chat_nachricht", gruppe="Chor")
    assert not ja(GL, "moderieren", "chat_nachricht", gruppe="Chor"), "GL moderiert nur die Untergruppe"
    for wer in (HV, MV):
        assert ja(wer, "schreiben", "chat_nachricht", gruppe="Chor", besitzer=SAENGER)
        assert ja(wer, "moderieren", "chat_nachricht", gruppe="Chor")
        assert ja(wer, "verwalten", "chat_gespraech", gruppe="Chor")


def test_untergruppe_ist_eigener_raum(welt):
    # F4: Mitglied der Hauptgruppe (nicht der Untergruppe) sieht den Untergruppenchat NICHT.
    assert not ja(SAENGER, "lesen", "chat_gespraech", untergruppe="UG-Noten")
    for wer in (NOTEN, GL, HV, MV):
        assert ja(wer, "lesen", "chat_gespraech", untergruppe="UG-Noten")
        assert ja(wer, "schreiben", "chat_nachricht", untergruppe="UG-Noten", besitzer=wer)
    for wer in (GL, HV, MV):
        assert ja(wer, "moderieren", "chat_nachricht", untergruppe="UG-Noten")
    assert not ja(NOTEN, "moderieren", "chat_nachricht", untergruppe="UG-Noten")


def test_modul_aus_niemand_ausser_admin(welt):
    assert not ja(JUGEND_HV, "lesen", "chat_gespraech", gruppe="Jugend")
    assert R.darf(JUGEND_HV, "lesen", "chat_gespraech", gruppe="Jugend").grund == "modul_aus"
    assert ja(ADMIN, "lesen", "chat_gespraech", gruppe="Jugend")
    assert ja(ADMIN, "moderieren", "chat_nachricht", gruppe="Chor")


def test_geloeschte_gruppe_gibt_kein_chatrecht(welt):
    welt.query(Gruppe).filter_by(name="Chor").update({"geloescht_am": dt.datetime(2026, 11, 1)})
    welt.commit()
    assert not ja(SAENGER, "lesen", "chat_gespraech", gruppe="Chor")
    assert not ja(HV, "moderieren", "chat_nachricht", gruppe="Chor")


def test_personen_finden_alle_aktiven(welt):
    for ziel in ("M-Hv", "M-Fr", "M-Jh", "M-ohnekonto", "M-gesperrt"):
        assert R.darf_person_finden(FREMD, ziel), ziel
    for ziel in ("M-ausgetreten", "M-austrittsdatum", "M-ausgeschlossen", "M-verstorben",
                 "gibt-es-nicht", "geloescht-123", None):
        assert not R.darf_person_finden(FREMD, ziel), ziel


def test_personen_finden_nie_fuer_gaeste(welt):
    for wer in ("Guest", None, "unbekannt@x.org", "gesperrt@x.org"):
        assert not R.darf_person_finden(wer, "M-Hv"), wer


def test_direktnachricht_nur_mit_konto_und_nicht_an_sich(welt):
    assert R.darf_direktnachricht(FREMD, "M-Hv")
    assert R.darf_direktnachricht(FREMD, "M-ohnekonto").grund == "kein_konto"
    assert R.darf_direktnachricht(FREMD, "M-gesperrt").grund == "kein_konto"
    assert R.darf_direktnachricht(FREMD, "M-Fr").grund == "selbst"
    assert not R.darf_direktnachricht(FREMD, "M-ausgetreten")
    assert not R.darf_direktnachricht("Guest", "M-Hv")


def test_meldestelle_nur_admin(welt):
    assert R.ist_meldestelle(ADMIN)
    for wer in (HV, MV, GL, SAENGER, "Guest", None):
        assert not R.ist_meldestelle(wer)


# ── CHAT-7: Direktgespraech/Runde (Kernfrage darf_direktgespraech) ─────────

def _direkt(*a, **kw) -> bool:
    return bool(R.darf_direktgespraech(*a, **kw))


def test_direktgespraech_nur_teilnehmende_lesen(welt):
    runde = [FREMD, HV]
    for wer in runde:
        assert _direkt(wer, "lesen", teilnehmer=runde)
    for wer in (SAENGER, MV, ADMIN, "Guest", None, "unbekannt@x.org"):
        assert not _direkt(wer, "lesen", teilnehmer=runde), wer
    assert R.darf_direktgespraech(ADMIN, "lesen", teilnehmer=runde).grund == "kein_teilnehmer"


def test_direktgespraech_schreiben_braucht_erreichbares_gegenueber(welt):
    assert _direkt(FREMD, "anlegen", teilnehmer=[FREMD, HV])
    # Gegenueber ohne gueltiges Konto: Verlauf bleibt lesbar, aber stumm.
    assert _direkt(FREMD, "lesen", teilnehmer=[FREMD, "gesperrt@x.org"])
    entsch = R.darf_direktgespraech(FREMD, "anlegen", teilnehmer=[FREMD, "gesperrt@x.org"])
    assert not entsch and entsch.grund == "niemand_erreichbar"
    # allein im Gespraech: niemand erreichbar
    assert not _direkt(FREMD, "anlegen", teilnehmer=[FREMD])
    # Runde: ein erreichbares Gegenueber genuegt
    assert _direkt(FREMD, "anlegen", teilnehmer=[FREMD, "gesperrt@x.org", MV])


def test_direktgespraech_ausgetretenes_gegenueber_stumm(welt):
    welt.query(Mitglied).filter_by(name="M-Hv").update({"status": "Ausgetreten"})
    welt.commit()
    assert not _direkt(FREMD, "anlegen", teilnehmer=[FREMD, HV])
    assert _direkt(FREMD, "lesen", teilnehmer=[FREMD, HV])


def test_direktgespraech_eigene_nachricht_und_meldestelle(welt):
    runde = [FREMD, HV]
    assert _direkt(FREMD, "schreiben", teilnehmer=runde, besitzer=FREMD)
    assert not _direkt(FREMD, "schreiben", teilnehmer=runde, besitzer=HV)
    # Moderation nur durch die Meldestelle (F7), nicht durch Gruppenleitung.
    assert _direkt(ADMIN, "moderieren", teilnehmer=runde)
    for wer in (HV, MV, FREMD, SAENGER):
        assert not _direkt(wer, "moderieren", teilnehmer=runde), wer
    assert not _direkt(FREMD, "verwalten", teilnehmer=runde)


def test_direktgespraech_ausgeschlossener_teilnehmer_verliert_zugang(welt):
    welt.query(Mitglied).filter_by(name="M-Fr").update({"ausgeschlossen": 1})
    welt.commit()
    assert not _direkt(FREMD, "lesen", teilnehmer=[FREMD, HV])
    assert not _direkt(FREMD, "anlegen", teilnehmer=[FREMD, HV])


def test_direktgespraech_ausgetretene_person_selbst_nur_lesen(welt):
    """Wer selbst ausgetreten ist (Konto noch aktiv), liest den Verlauf noch,
    beginnt aber nichts Neues und sendet nicht mehr."""
    welt.query(Mitglied).filter_by(name="M-Fr").update({"status": "Ausgetreten"})
    welt.commit()
    assert R.darf_direktnachricht(FREMD, "M-Hv").grund == "selbst_nicht_aktiv"
    assert _direkt(FREMD, "lesen", teilnehmer=[FREMD, HV])
    assert not _direkt(FREMD, "anlegen", teilnehmer=[FREMD, HV])
    # Das Gegenueber kann ihr ebenfalls nicht mehr schreiben.
    assert not _direkt(HV, "anlegen", teilnehmer=[FREMD, HV])


def test_konto_ohne_mitglied_beginnt_kein_direktgespraech(welt):
    """Das Konto ``Administrator`` hat kein Mitglied: es koennte schreiben,
    aber das Gegenueber nie antworten — darum gar nicht."""
    assert R.darf_direktnachricht("Administrator", "M-Hv").grund == "selbst_nicht_aktiv"
    assert not _direkt("Administrator", "anlegen", teilnehmer=["Administrator", HV])
