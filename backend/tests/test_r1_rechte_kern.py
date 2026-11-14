"""R-1: der EINE Rechte-Kern (``diakronos_app.rechte``).

Die Faelle stammen aus Manuels Live-Test vom 11.11.2026 (Demo Musterhausen):
Rebekka (HV Chor), Samuel (HV Jugendkreis), Susanne (HV Kinderdienst),
Anna (Mitglied mit Einzelfreigabe), Admin. Sie beschreiben das Soll des neuen
Modells — nicht den Altbestand.
"""

from __future__ import annotations

import pytest

from diakronos_app import rechte as R
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
from diakronos_app.models.rechte import (
    RechteFreigabe,
    RechteGruppenrolle,
    RechteModul,
    RechteObjekt,
)

ADMIN = "admin@example.org"
REBEKKA = "rebekka@example.org"   # HV Chor
SAMUEL = "samuel@example.org"     # HV Jugendkreis
MIRA = "mira@example.org"         # MV Chor
CHORSAENGER = "saenger@example.org"  # Mitglied Chor
ANNA = "anna@example.org"         # kein Chormitglied, Einzelfreigabe
FREMD = "fremd@example.org"       # Mitglied der Gemeinde ohne Gruppe
MODERATOR = "moderator@example.org"  # Systemrolle Kalender-Moderation


@pytest.fixture()
def welt(patched_db):
    s = patched_db()
    for user, vn, nn in [
        (ADMIN, "Ad", "Min"), (REBEKKA, "Rebekka", "Fink"), (SAMUEL, "Samuel", "Fink"),
        (MIRA, "Mira", "Mit"), (CHORSAENGER, "Sa", "Enger"), (ANNA, "Anna", "Beispiel"),
        (FREMD, "Fr", "Emd"), (MODERATOR, "Mo", "Derator"),
    ]:
        s.add(User(name=user, email=user, enabled=1))
        s.add(Mitglied(name=f"M-{vn}", vorname=vn, nachname=nn, email=user, user=user))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User", role="System Manager"))
    s.add(HasRole(name="hr-mod", parent=MODERATOR, parenttype="User", role="Kalenderadministrator"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugendkreis"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor", parentfield="mitglieder", mitglied="M-Sa"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=REBEKKA, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MIRA, rolle="MV"),
        RechteGruppenrolle(gruppe="Jugend", benutzer=SAMUEL, rolle="HV"),
    ])
    for m in ("kalender", "beitraege", "wiki", "aufgaben", "lieder", "dienstplaene"):
        s.add(RechteModul(gruppe="Chor", modul=m))
    for m in ("kalender", "beitraege", "wiki", "aufgaben"):
        s.add(RechteModul(gruppe="Jugend", modul=m))
    s.add_all([
        RechteObjekt(typ="kalender", objekt="chorkal", gruppe="Chor"),
        RechteObjekt(typ="kalender", objekt="chor-intern", gruppe="Chor", standard_gruppe_lesen=False),
        RechteObjekt(typ="kalender", objekt="jugendkal", gruppe="Jugend", gemeinde_status="aktiv"),
        RechteObjekt(typ="dienstplan", objekt="chorplan", gruppe="Chor", eltern_typ="kalender", eltern_objekt="chorkal"),
        RechteObjekt(typ="wiki", objekt="w1", gruppe="Chor"),
        RechteFreigabe(typ="kalender", objekt="chorkal", benutzer=ANNA, lesen=True, schreiben=True),
        RechteFreigabe(typ="kalender", objekt="chor-intern", benutzer=CHORSAENGER, lesen=True),
    ])
    s.commit()
    yield s
    s.close()


def ja(*a, **kw):
    return bool(R.darf(*a, **kw))


# ── Systemebene ─────────────────────────────────────────────────────────────

def test_admin_darf_alles_ohne_verantwortung(welt):
    assert R.gruppenrolle(ADMIN, "Chor") is None
    for aktion in R.AKTIONEN:
        assert ja(ADMIN, aktion, "kalender", "chorkal")
    assert ja(ADMIN, R.ROLLEN, "gruppe", "Chor")


def test_gast_und_unbekannt_duerfen_nichts(welt):
    for b in (None, "", "Guest", "niemand@example.org"):
        assert not ja(b, R.LESEN, "kalender", "jugendkal")


def test_unbekannte_aktion_oder_typ_wird_verweigert(welt):
    assert not ja(REBEKKA, "loeschen_alles", "kalender", "chorkal")
    assert not ja(REBEKKA, R.LESEN, "geheimtyp", "x")


# ── Gruppenrollen ───────────────────────────────────────────────────────────

def test_rollen_werden_erkannt(welt):
    assert R.gruppenrolle(REBEKKA, "Chor") == "HV"
    assert R.gruppenrolle(MIRA, "Chor") == "MV"
    assert R.gruppenrolle(CHORSAENGER, "Chor") == "Mitglied"
    assert R.gruppenrolle(FREMD, "Chor") is None


def test_nur_hv_vergibt_rollen(welt):
    assert ja(REBEKKA, R.ROLLEN, "gruppe", "Chor")
    assert not ja(MIRA, R.ROLLEN, "gruppe", "Chor")
    assert ja(MIRA, R.VERWALTEN, "gruppe", "Chor")


def test_hv_einer_gruppe_darf_in_anderer_gruppe_nichts(welt):
    """Live-Test: Rebekka darf Chor, nicht Jugendkreis."""
    assert ja(REBEKKA, R.SCHREIBEN, "kalender", "chorkal")
    assert not ja(REBEKKA, R.SCHREIBEN, "kalender", "jugendkal")
    assert not ja(REBEKKA, R.VERWALTEN, "gruppe", "Jugend")
    assert not ja(SAMUEL, R.SCHREIBEN, "kalender", "chorkal")


# ── Module ──────────────────────────────────────────────────────────────────

def test_modul_aus_heisst_unsichtbar(welt):
    """Jugend hat kein Modul Lieder/Dienstplaene -> Samuel sieht keine Lieder."""
    assert not ja(SAMUEL, R.LESEN, "lied", "L1")
    assert "lieder" not in R.sichtbare_module(SAMUEL)
    assert "lieder" in R.sichtbare_module(REBEKKA)
    assert R.sichtbare_module(ADMIN) == set(R.MODULE)


def test_lieder_bearbeiten_hv_und_mv_der_modulgruppe(welt):
    """Live-Test 10: Chorleiter konnte kein Lied bearbeiten."""
    assert ja(REBEKKA, R.SCHREIBEN, "lied", "L1")
    assert ja(MIRA, R.SCHREIBEN, "lied", "L1")
    assert ja(CHORSAENGER, R.LESEN, "lied", "L1")
    assert not ja(CHORSAENGER, R.SCHREIBEN, "lied", "L1")


def test_anlegen_nur_hv_mv(welt):
    assert ja(REBEKKA, R.ANLEGEN, "wiki", gruppe="Chor")
    assert ja(MIRA, R.ANLEGEN, "beitrag", gruppe="Chor")
    assert not ja(CHORSAENGER, R.ANLEGEN, "wiki", gruppe="Chor")
    assert not ja(SAMUEL, R.ANLEGEN, "lied")  # Jugend hat kein Modul Lieder
    assert not ja(SAMUEL, R.ANLEGEN, "dienstplan", gruppe="Jugend")  # Modul aus


# ── Lesen: Mitglied, Einzelfreigabe, Gemeinde ───────────────────────────────

def test_gruppenmitglied_liest_standard_aber_nicht_intern(welt):
    assert ja(CHORSAENGER, R.LESEN, "kalender", "chorkal")
    assert not ja(CHORSAENGER, R.SCHREIBEN, "kalender", "chorkal")
    # chor-intern: kein Standard-Lesen, aber Einzelfreigabe -> lesen
    assert ja(CHORSAENGER, R.LESEN, "kalender", "chor-intern")
    assert not ja(FREMD, R.LESEN, "kalender", "chor-intern")


def test_einzelfreigabe_schreiben(welt):
    assert ja(ANNA, R.LESEN, "kalender", "chorkal")
    assert ja(ANNA, R.SCHREIBEN, "kalender", "chorkal")
    assert not ja(ANNA, R.VERWALTEN, "kalender", "chorkal")
    assert not ja(ANNA, R.ANLEGEN, "kalender", gruppe="Chor")


def test_gemeinde_freigabe_lesen_fuer_alle_mitglieder(welt):
    assert ja(FREMD, R.LESEN, "kalender", "jugendkal")
    assert not ja(FREMD, R.SCHREIBEN, "kalender", "jugendkal")
    assert not ja(FREMD, R.LESEN, "kalender", "chorkal")


# ── Moderation ──────────────────────────────────────────────────────────────

def test_moderation_nie_automatisch_durch_hv(welt):
    assert not ja(REBEKKA, R.MODERIEREN, "kalender", "chorkal")
    assert ja(MODERATOR, R.MODERIEREN, "kalender", "chorkal")
    assert ja(ADMIN, R.MODERIEREN, "kalender", "chorkal")


def test_moderationsrecht_als_einzelfreigabe(welt):
    welt.add(RechteFreigabe(typ="kalender", objekt="jugendkal", benutzer=REBEKKA, lesen=True, moderieren=True))
    welt.commit()
    assert ja(REBEKKA, R.MODERIEREN, "kalender", "jugendkal")
    assert not ja(REBEKKA, R.SCHREIBEN, "kalender", "jugendkal")


def test_fachrolle_wirkt_nur_im_fach(welt):
    """Kalender-Moderation gibt kein Schreibrecht und keinen Zugriff auf Wiki."""
    assert not ja(MODERATOR, R.SCHREIBEN, "kalender", "chorkal")
    assert not ja(MODERATOR, R.LESEN, "wiki", "w1")


# ── Dienstplan haengt am Kalender-Schreibrecht ──────────────────────────────

def test_dienstplan_nur_mit_schreibrecht_am_kalender(welt):
    """Live-Test 16: wer nicht in den Kalender schreiben kann, sieht den Plan nicht."""
    assert ja(REBEKKA, R.LESEN, "dienstplan", "chorplan")
    assert ja(ANNA, R.LESEN, "dienstplan", "chorplan")          # Schreibrecht am Kalender
    assert not ja(CHORSAENGER, R.LESEN, "dienstplan", "chorplan")  # nur Leserecht
    assert not ja(ANNA, R.SCHREIBEN, "dienstplan", "chorplan")   # delegieren nur HV/MV


# ── Aufgaben ────────────────────────────────────────────────────────────────

def test_eigene_aufgabe(welt):
    assert ja(FREMD, R.SCHREIBEN, "aufgabe", "A1", besitzer=FREMD)
    assert not ja(ANNA, R.LESEN, "aufgabe", "A1", besitzer=FREMD)


def test_gruppenaufgabe_abhaken_nur_zugewiesen_oder_verantwortlich(welt):
    welt.add(RechteObjekt(typ="aufgabe", objekt="GA1", gruppe="Chor"))
    welt.commit()
    assert ja(CHORSAENGER, R.ERLEDIGEN, "aufgabe", "GA1", zugewiesen=[CHORSAENGER])
    assert not ja(CHORSAENGER, R.ERLEDIGEN, "aufgabe", "GA1", zugewiesen=[ANNA])
    assert ja(MIRA, R.ERLEDIGEN, "aufgabe", "GA1", zugewiesen=[ANNA])


# ── pruefe wirft ────────────────────────────────────────────────────────────

def test_pruefe_wirft_permission_error(welt):
    from diakronos_app.frappe_compat.exceptions import PermissionError

    with pytest.raises(PermissionError):
        R.pruefe(CHORSAENGER, R.SCHREIBEN, "kalender", "chorkal")
    assert R.pruefe(REBEKKA, R.SCHREIBEN, "kalender", "chorkal").grund == "leitung_hv"


def test_ein_hv_je_gruppe_datenbankseitig(welt):
    from sqlalchemy.exc import IntegrityError

    welt.add(RechteGruppenrolle(gruppe="Chor", benutzer=ANNA, rolle="HV"))
    with pytest.raises(IntegrityError):
        welt.commit()
    welt.rollback()


# ── Gemeinde-Kalender + Gruppen-Freigabe (Bestand: gemeinsame Kalender) ────

@pytest.fixture()
def gemeinde(welt):
    welt.add_all([
        RechteObjekt(typ="kalender", objekt="gemeinsam", gruppe=None),
        RechteObjekt(typ="kalender", objekt="gottesdienste", gruppe=None, gemeinde_status="aktiv"),
        RechteFreigabe(typ="kalender", objekt="gemeinsam", gruppe="Chor", lesen=True, schreiben=True),
    ])
    welt.commit()
    return welt


def test_gruppenfreigabe_mitglieder_lesen_verantwortliche_schreiben(gemeinde):
    assert ja(CHORSAENGER, R.LESEN, "kalender", "gemeinsam")
    assert not ja(CHORSAENGER, R.SCHREIBEN, "kalender", "gemeinsam")
    assert ja(REBEKKA, R.SCHREIBEN, "kalender", "gemeinsam")
    assert ja(MIRA, R.SCHREIBEN, "kalender", "gemeinsam")
    assert not ja(SAMUEL, R.LESEN, "kalender", "gemeinsam")


def test_gemeinde_kalender_pflegen_nur_admin_und_kalender_moderation(gemeinde):
    assert not ja(REBEKKA, R.VERWALTEN, "kalender", "gemeinsam")
    assert ja(MODERATOR, R.VERWALTEN, "kalender", "gemeinsam")
    assert ja(MODERATOR, R.SCHREIBEN, "kalender", "gottesdienste")
    assert ja(ADMIN, R.VERWALTEN, "kalender", "gemeinsam")


def test_gemeinde_kalender_alle_mitglieder_lesen(gemeinde):
    assert ja(FREMD, R.LESEN, "kalender", "gottesdienste")
    assert not ja(FREMD, R.SCHREIBEN, "kalender", "gottesdienste")


def test_hv_wechsel_braucht_keine_neue_freigabe(gemeinde):
    """Gruppen-Freigabe folgt der Rolle: neuer HV schreibt sofort."""
    gemeinde.query(RechteGruppenrolle).filter_by(gruppe="Chor", benutzer=REBEKKA).delete()
    gemeinde.add(RechteGruppenrolle(gruppe="Chor", benutzer=ANNA, rolle="HV"))
    gemeinde.commit()
    assert ja(ANNA, R.SCHREIBEN, "kalender", "gemeinsam")
    assert not ja(REBEKKA, R.SCHREIBEN, "kalender", "gemeinsam")


def test_nicht_registriertes_objekt_wird_verweigert(welt):
    assert not ja(REBEKKA, R.LESEN, "kalender", "gibt-es-nicht")
    assert ja(ADMIN, R.LESEN, "kalender", "gibt-es-nicht")


# ── Untergruppen: Gruppenleiter (GL), zwei Moderationsstufen ────────────────
# Manuel 11.11.: GL verantworten ihre Untergruppe; HV/MV sind dort
# mitberechtigt; was an Gruppe/Gemeinde geht, moderiert zuerst HV/MV.
# Genau zwei Ebenen (keine Unter-Untergruppen).

GL = "gl@example.org"            # Gruppenleiterin Untergruppe "Sopran"
SOPRAN = "sopran@example.org"    # Mitglied der Untergruppe "Sopran"


@pytest.fixture()
def unter(welt):
    from diakronos_app.models.diakonos import Untergruppe, Untergruppenmitgliedschaft

    for user, vn in [(GL, "Gabi"), (SOPRAN, "Sophie")]:
        welt.add(User(name=user, email=user, enabled=1))
        welt.add(Mitglied(name=f"M-{vn}", vorname=vn, nachname="U", email=user, user=user))
    welt.add(Untergruppe(name="Sopran", untergruppenname="Sopran", gruppe="Chor"))
    welt.add(Untergruppenmitgliedschaft(name="ugm1", parent="Sopran", parentfield="mitglieder", mitglied="M-Sophie"))
    welt.add(RechteGruppenrolle(gruppe="Chor", untergruppe="Sopran", benutzer=GL, rolle="GL"))
    welt.add_all([
        RechteObjekt(typ="kalender", objekt="sopran-kal", gruppe="Chor", untergruppe="Sopran"),
        RechteObjekt(typ="kalender", objekt="sopran-offen", gruppe="Chor", untergruppe="Sopran", gruppe_status="aktiv"),
        RechteObjekt(typ="kalender", objekt="chor-oeffentlich", gruppe="Chor", gemeinde_status="aktiv"),
    ])
    welt.commit()
    return welt


def test_rollen_in_der_untergruppe(unter):
    assert R.untergruppenrolle(GL, "Sopran") == "GL"
    assert R.untergruppenrolle(REBEKKA, "Sopran") == "HV"   # HV erbt
    assert R.untergruppenrolle(MIRA, "Sopran") == "MV"
    assert R.untergruppenrolle(SOPRAN, "Sopran") == "Mitglied"
    assert R.untergruppenrolle(CHORSAENGER, "Sopran") is None
    # in der Hauptgruppe sind GL und Untergruppen-Mitglieder einfache Mitglieder
    assert R.gruppenrolle(GL, "Chor") == "Mitglied"
    assert R.gruppenrolle(SOPRAN, "Chor") == "Mitglied"


def test_gl_ist_nicht_mv_der_hauptgruppe(unter):
    assert not ja(GL, R.VERWALTEN, "gruppe", "Chor")
    assert not ja(GL, R.SCHREIBEN, "kalender", "chorkal")
    assert not ja(GL, R.ROLLEN, "untergruppe", "Sopran")   # GL ernennt keine GL


def test_gl_ernennen_hv_und_mv(unter):
    assert ja(REBEKKA, R.ROLLEN, "untergruppe", "Sopran")
    assert ja(MIRA, R.ROLLEN, "untergruppe", "Sopran")


def test_gl_verantwortet_untergruppe(unter):
    assert ja(GL, R.VERWALTEN, "untergruppe", "Sopran")
    assert ja(GL, R.ANLEGEN, "kalender", untergruppe="Sopran")
    assert ja(GL, R.SCHREIBEN, "kalender", "sopran-kal")
    assert ja(GL, R.VERWALTEN, "kalender", "sopran-kal")
    assert ja(REBEKKA, R.SCHREIBEN, "kalender", "sopran-kal")  # HV mitberechtigt
    assert not ja(SOPRAN, R.SCHREIBEN, "kalender", "sopran-kal")


def test_untergruppen_inhalt_nur_fuer_untergruppe_bis_freigabe(unter):
    assert ja(SOPRAN, R.LESEN, "kalender", "sopran-kal")
    assert not ja(CHORSAENGER, R.LESEN, "kalender", "sopran-kal")   # anderes Chormitglied
    assert ja(CHORSAENGER, R.LESEN, "kalender", "sopran-offen")     # an Gruppe freigegeben
    assert not ja(FREMD, R.LESEN, "kalender", "sopran-offen")


def test_gl_schlaegt_im_gruppenkalender_vor_hv_moderiert(unter):
    assert ja(GL, R.VORSCHLAGEN, "kalender", "chorkal")
    assert R.moderationsstufen(GL, "kalender", "chorkal") == ["gruppe"]
    assert ja(REBEKKA, R.MODERIEREN, "kalender", "chorkal", stufe="gruppe")
    assert ja(MIRA, R.MODERIEREN, "kalender", "chorkal", stufe="gruppe")
    assert not ja(GL, R.MODERIEREN, "kalender", "chorkal", stufe="gruppe")
    assert not ja(SOPRAN, R.VORSCHLAGEN, "kalender", "chorkal")


def test_stufen_gruppe_dann_gemeinde(unter):
    assert R.moderationsstufen(GL, "kalender", "chor-oeffentlich") == ["gruppe", "gemeinde"]
    assert R.moderationsstufen(REBEKKA, "kalender", "chor-oeffentlich") == ["gemeinde"]
    # Admin: Gruppenstufe nie, Gemeindestufe bei oeffentlichen Kalendern IMMER
    assert R.moderationsstufen(ADMIN, "kalender", "chor-oeffentlich") == ["gemeinde"]
    assert R.moderationsstufen(REBEKKA, "kalender", "chorkal") == []
    assert R.moderationsstufen(GL, "kalender", "sopran-kal") == []
    # GL schreibt in Untergruppen-Kalender, der an die ganze Gruppe geht
    assert R.moderationsstufen(GL, "kalender", "sopran-offen") == ["gruppe"]


def test_freigabe_stufen(unter):
    # GL gibt Untergruppen-Kalender an die Gruppe: HV/MV moderieren
    assert R.freigabe_stufen(GL, "kalender", "sopran-kal", "gruppe") == ["gruppe"]
    # GL an die Gemeinde: erst Gruppe, dann Gemeinde
    assert R.freigabe_stufen(GL, "kalender", "sopran-kal", "gemeinde") == ["gruppe", "gemeinde"]
    # HV (kein Admin) an die Gemeinde: nur Gemeinde-Moderation
    assert R.freigabe_stufen(REBEKKA, "kalender", "chorkal", "gemeinde") == ["gemeinde"]
    # HV, der Admin ist: keine Moderation fuer die Freigabe selbst
    assert R.freigabe_stufen(ADMIN, "kalender", "chorkal", "gemeinde") == []
    # ohne Verwaltungsrecht: nichts
    assert R.freigabe_stufen(SOPRAN, "kalender", "sopran-kal", "gruppe") == []


def test_gl_ueber_gruppenfreigabe_im_gemeindekalender_nur_vorschlag(unter):
    unter.add_all([
        RechteObjekt(typ="kalender", objekt="gemeinsam2", gruppe=None),
        RechteFreigabe(typ="kalender", objekt="gemeinsam2", gruppe="Chor", lesen=True, schreiben=True),
    ])
    unter.commit()
    assert ja(REBEKKA, R.SCHREIBEN, "kalender", "gemeinsam2")
    assert not ja(GL, R.SCHREIBEN, "kalender", "gemeinsam2")
    assert ja(GL, R.VORSCHLAGEN, "kalender", "gemeinsam2")
    # R-5: danach die eigene Stufe des Gemeinde-Kalenders — Schreiben ohne
    # Moderationsrecht ist ein Vorschlag (P0-3), auch fuer den HV.
    assert R.moderationsstufen(GL, "kalender", "gemeinsam2") == ["gruppe", "gemeinde"]
    assert R.moderationsstufen(REBEKKA, "kalender", "gemeinsam2") == ["gemeinde"]


def test_inaktive_mitgliedschaft_zaehlt_nicht(welt):
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft as GM

    welt.add(GM(name="gm-inaktiv", parent="Jugend", parentfield="mitglieder", mitglied="M-Fr", status="Inaktiv"))
    welt.commit()
    assert R.gruppenrolle(FREMD, "Jugend") is None
