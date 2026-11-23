"""DATEIEN-R: Gruppendateien im EINEN Rechtesystem (Manuel 23.11.2026).

Entscheidungen F1–F9 (DATEIEN-KONZEPT.md): Reiter der Gruppe; Untergruppen eigene
Dateien (F3); fremde Dateien löschen HV/MV, in der Untergruppe auch GL (F4);
Papierkorb 30 Tage, Wiederherstellen = MODERIEREN (F5). Dieselbe Raum-Regel wie
der Chat — kein eigenes Rechtesystem.
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
        RechteModul(gruppe="Chor", modul="dateien"),
        RechteModul(gruppe="Jugend", modul="chat"),
    ])
    s.commit()
    yield s
    s.close()


def ja(*a, **kw) -> bool:
    return bool(R.darf(*a, **kw))


def grund(*a, **kw) -> str:
    return R.darf(*a, **kw).grund


T = "gruppe_datei"


def test_dateien_ist_ein_modul_des_einen_systems():
    assert "dateien" in R.MODULE
    assert R.TYP_MODUL[T] == "dateien"
    assert T in R.DATEI_TYPEN
    assert "dateien" not in R.STANDARD_MODULE  # Admin schaltet das Modul je Gruppe an


def test_erklaerung_kennt_dateien():
    from diakronos_app.rechte import erklaerung as E
    assert E.MODUL_TITEL["dateien"] == "Dateien"
    assert "Papierkorb" in E.MODULE["dateien"]


@pytest.mark.parametrize("wer", [HV, MV, SAENGER])
def test_mitglieder_lesen_und_laden_hoch(welt, wer):
    assert ja(wer, R.LESEN, T, gruppe="Chor")
    assert ja(wer, R.ANLEGEN, T, gruppe="Chor")


def test_fremde_sehen_nichts(welt):
    for akt in (R.LESEN, R.ANLEGEN, R.SCHREIBEN, R.MODERIEREN):
        assert not ja(FREMD, akt, T, gruppe="Chor")
    assert grund(FREMD, R.LESEN, T, gruppe="Chor") == "kein_mitglied"


def test_eigene_datei_loescht_jede_person(welt):
    assert ja(SAENGER, R.SCHREIBEN, T, gruppe="Chor", besitzer=SAENGER)
    assert grund(SAENGER, R.SCHREIBEN, T, gruppe="Chor", besitzer=SAENGER) == "datei_eigenes"


def test_fremde_datei_nur_leitung(welt):
    assert not ja(SAENGER, R.SCHREIBEN, T, gruppe="Chor", besitzer=HV)
    assert grund(SAENGER, R.SCHREIBEN, T, gruppe="Chor", besitzer=HV) == "fremde_datei"
    assert ja(HV, R.SCHREIBEN, T, gruppe="Chor", besitzer=SAENGER)
    assert ja(MV, R.SCHREIBEN, T, gruppe="Chor", besitzer=SAENGER)


def test_papierkorb_wiederherstellen_ist_moderieren(welt):
    assert ja(HV, R.MODERIEREN, T, gruppe="Chor")
    assert ja(MV, R.MODERIEREN, T, gruppe="Chor")
    assert not ja(SAENGER, R.MODERIEREN, T, gruppe="Chor")
    assert grund(SAENGER, R.MODERIEREN, T, gruppe="Chor") == "nicht_verantwortlich"


def test_verwalten_nur_leitung(welt):
    assert ja(HV, R.VERWALTEN, T, gruppe="Chor")
    assert not ja(SAENGER, R.VERWALTEN, T, gruppe="Chor")


def test_untergruppe_eigener_raum(welt):
    # Mitglied der Untergruppe: liest, lädt hoch, löscht eigenes
    assert ja(NOTEN, R.LESEN, T, untergruppe="UG-Noten")
    assert ja(NOTEN, R.ANLEGEN, T, untergruppe="UG-Noten")
    assert ja(NOTEN, R.SCHREIBEN, T, untergruppe="UG-Noten", besitzer=NOTEN)
    assert not ja(NOTEN, R.SCHREIBEN, T, untergruppe="UG-Noten", besitzer=GL)
    # Chor-Mitglied ohne Untergruppe sieht die Untergruppen-Dateien NICHT (F3)
    assert not ja(SAENGER, R.LESEN, T, untergruppe="UG-Noten")
    # Untergruppen-Mitglieder gehören auch zur Hauptgruppe (Kern, wie im Chat)
    assert ja(NOTEN, R.LESEN, T, gruppe="Chor")
    assert ja(NOTEN, R.LESEN, "chat_gespraech", gruppe="Chor") is False  # Chor hat keinen Chat


@pytest.mark.parametrize("wer", [GL, HV, MV])
def test_untergruppe_leitung_loescht_fremdes(welt, wer):
    assert ja(wer, R.SCHREIBEN, T, untergruppe="UG-Noten", besitzer=NOTEN)
    assert ja(wer, R.MODERIEREN, T, untergruppe="UG-Noten")


def test_gl_ist_in_der_hauptgruppe_keine_leitung(welt):
    assert not ja(GL, R.MODERIEREN, T, gruppe="Chor")


def test_modul_aus_niemand_ausser_admin(welt):
    # Jugend hat nur Chat, nicht Dateien
    assert not ja(JUGEND_HV, R.LESEN, T, gruppe="Jugend")
    assert grund(JUGEND_HV, R.LESEN, T, gruppe="Jugend") == "modul_aus"
    assert ja(ADMIN, R.LESEN, T, gruppe="Jugend")
    assert ja(ADMIN, R.SCHREIBEN, T, gruppe="Chor", besitzer=SAENGER)


def test_ohne_gruppe_nein(welt):
    assert grund(HV, R.LESEN, T) == "keine_gruppe"


def test_unbekannte_aktion_nein(welt):
    assert grund(HV, R.ERLEDIGEN, T, gruppe="Chor") == "aktion_nicht_fuer_dateien"


def test_chat_und_dateien_getrennt(welt):
    # Chor hat Dateien, aber keinen Chat; Jugend umgekehrt
    assert not ja(SAENGER, R.LESEN, "chat_gespraech", gruppe="Chor")
    assert ja(JUGEND_HV, R.LESEN, "chat_gespraech", gruppe="Jugend")
    assert ja(JUGEND_HV, R.SCHREIBEN, "chat_nachricht", gruppe="Jugend", besitzer=JUGEND_HV)
    assert grund(JUGEND_HV, R.SCHREIBEN, "chat_nachricht", gruppe="Jugend",
                 besitzer=JUGEND_HV) == "chat_eigenes"


# ── Schalter je Gruppe (Manuel 21.11.: Hochladen alle, Anpinnen Verantwortliche) ──

from diakronos_app.rechte import verwaltung as V  # noqa: E402


def test_vorgaben_hochladen_alle_anpinnen_leitung(welt):
    assert R.gruppeneinstellung("Chor", "dateien_hochladen_alle") is True
    assert R.gruppeneinstellung("Chor", "dateien_anpinnen_alle") is False
    assert ja(SAENGER, R.ANLEGEN, T, gruppe="Chor")
    assert not ja(SAENGER, R.ANPINNEN, T, gruppe="Chor")
    assert grund(SAENGER, R.ANPINNEN, T, gruppe="Chor") == "nur_verantwortliche"
    assert ja(HV, R.ANPINNEN, T, gruppe="Chor")
    assert ja(MV, R.ANPINNEN, T, gruppe="Chor")
    assert ja(GL, R.ANPINNEN, T, untergruppe="UG-Noten")
    assert not ja(NOTEN, R.ANPINNEN, T, untergruppe="UG-Noten")


def test_schalter_umstellen_wirkt_auch_in_untergruppe(welt):
    V.setze_gruppeneinstellung(HV, "Chor", "dateien_hochladen_alle", False)
    V.setze_gruppeneinstellung(MV, "Chor", "dateien_anpinnen_alle", True)
    assert not ja(SAENGER, R.ANLEGEN, T, gruppe="Chor")
    assert grund(SAENGER, R.ANLEGEN, T, gruppe="Chor") == "nur_verantwortliche"
    assert ja(HV, R.ANLEGEN, T, gruppe="Chor")
    assert not ja(NOTEN, R.ANLEGEN, T, untergruppe="UG-Noten")
    assert ja(GL, R.ANLEGEN, T, untergruppe="UG-Noten")
    assert ja(SAENGER, R.ANPINNEN, T, gruppe="Chor")
    assert ja(NOTEN, R.ANPINNEN, T, untergruppe="UG-Noten")


def test_zurueck_auf_vorgabe_entfernt_zeile(welt):
    from diakronos_app.models.rechte import RechteGruppeneinstellung
    V.setze_gruppeneinstellung(HV, "Chor", "dateien_anpinnen_alle", True)
    assert welt.query(RechteGruppeneinstellung).count() == 1
    V.setze_gruppeneinstellung(HV, "Chor", "dateien_anpinnen_alle", False)
    welt.expire_all()
    assert welt.query(RechteGruppeneinstellung).count() == 0
    assert not ja(SAENGER, R.ANPINNEN, T, gruppe="Chor")


@pytest.mark.parametrize("wer", [SAENGER, GL, NOTEN, FREMD, JUGEND_HV])
def test_schalter_nur_hv_mv_admin(welt, wer):
    with pytest.raises(Exception):
        V.setze_gruppeneinstellung(wer, "Chor", "dateien_hochladen_alle", False)
    assert R.gruppeneinstellung("Chor", "dateien_hochladen_alle") is True


def test_admin_darf_schalter(welt):
    V.setze_gruppeneinstellung(ADMIN, "Chor", "dateien_hochladen_alle", False)
    assert R.gruppeneinstellung("Chor", "dateien_hochladen_alle") is False


def test_unbekannter_schluessel_und_kein_bool(welt):
    with pytest.raises(Exception):
        V.setze_gruppeneinstellung(HV, "Chor", "chat_alles_erlaubt", True)
    with pytest.raises(Exception):
        V.setze_gruppeneinstellung(HV, "Chor", "dateien_hochladen_alle", "nein")
    with pytest.raises(KeyError):
        R.gruppeneinstellung("Chor", "gibt_es_nicht")


def test_einstellungen_lesen(welt):
    lese = V.gruppeneinstellungen(SAENGER, "Chor")
    assert lese == {"werte": {"dateien_hochladen_alle": True, "dateien_anpinnen_alle": False},
                    "darf_aendern": False}
    assert V.gruppeneinstellungen(HV, "Chor")["darf_aendern"] is True
    with pytest.raises(Exception):
        V.gruppeneinstellungen(FREMD, "Chor")


def test_chat_kennt_kein_anpinnen(welt):
    assert grund(JUGEND_HV, R.ANPINNEN, "chat_nachricht", gruppe="Jugend") == "aktion_nicht_fuer_chat"


# ── Review DATEIEN-R ──

def test_fremde_gruppe_ersetzt_nicht_die_hauptgruppe(welt):
    # Jugend hat kein Dateien-Modul; UG-Noten gehört zu Chor
    welt.add(RechteModul(gruppe="Jugend", modul="dateien")); welt.commit()
    V.setze_gruppeneinstellung(HV, "Chor", "dateien_hochladen_alle", False)
    assert not ja(NOTEN, R.ANLEGEN, T, gruppe="Jugend", untergruppe="UG-Noten")
    assert grund(NOTEN, R.ANLEGEN, T, gruppe="Jugend", untergruppe="UG-Noten") == "untergruppe_passt_nicht"
    assert not ja(NOTEN, R.ANLEGEN, T, gruppe="Chor", untergruppe="UG-Noten")
    assert ja(GL, R.ANLEGEN, T, gruppe="Chor", untergruppe="UG-Noten")


def test_chat_fremde_gruppe_ersetzt_nicht_die_hauptgruppe(welt):
    # Jugend hat Chat, Chor nicht: Untergruppe von Chor darf nicht über Jugend in den Chat
    assert not ja(NOTEN, R.LESEN, "chat_gespraech", gruppe="Jugend", untergruppe="UG-Noten")


def test_loeschen_ohne_besitzer_nein(welt):
    assert grund(SAENGER, R.SCHREIBEN, T, gruppe="Chor") == "besitzer_fehlt"
    assert not ja(HV, R.SCHREIBEN, T, gruppe="Chor")
    assert ja(ADMIN, R.SCHREIBEN, T, gruppe="Chor")


def test_vorschlagen_kein_umweg(welt):
    V.setze_gruppeneinstellung(HV, "Chor", "dateien_hochladen_alle", False)
    assert not ja(SAENGER, R.VORSCHLAGEN, T, gruppe="Chor")
