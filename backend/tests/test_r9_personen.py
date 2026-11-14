"""R-9: Personen (Manuel 11.11.).

Alle Mitglieder sehen Vor- und Nachnamen aller Gemeindemitglieder; weitere
Daten nur nach Freigabe der Person, sonst „Daten anfragen“ -> Meldung an die
Person. Wer kein Gemeindemitglied ist, sieht niemanden.
"""

from __future__ import annotations

import json

import pytest

from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import NotificationLog, User
from diakronos_app.models.diakonos import Mitglied

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ANNA, CHORSAENGER, FREMD, REBEKKA, SAMUEL, welt,
)


@pytest.fixture(autouse=True)
def _zuruecksetzen():
    yield
    set_user("Administrator")


def _eintrag(liste, nachname):
    return next(e for e in liste if e["nachname"] == nachname)


def test_alle_mitglieder_sehen_alle_namen(welt):
    """Vorher: nur ueberlappende ancestor_path (meist niemand außer sich selbst)."""
    from diakronos_app.api.mitglieder import get_adressbuch

    set_user(FREMD)                     # in keiner Gruppe
    namen = {(e["vorname"], e["nachname"]) for e in get_adressbuch()["data"]}
    assert {("Rebekka", "Fink"), ("Samuel", "Fink"), ("Anna", "Beispiel")} <= namen


def test_daten_nur_nach_freigabe(welt):
    from diakronos_app.api.mitglieder import get_adressbuch

    anna = welt.get(Mitglied, "M-Anna")
    anna.telefonnummer = "0151 123"
    anna.adressbuch_sichtbarkeit = json.dumps(
        {"email": False, "telefonnummer": False, "adresse": False, "geburtstag": False})
    rebekka = welt.get(Mitglied, "M-Rebekka")
    rebekka.adressbuch_sichtbarkeit = json.dumps(
        {"email": True, "telefonnummer": True, "adresse": True, "geburtstag": True})
    welt.commit()
    set_user(FREMD)
    eintraege = get_adressbuch()["data"]
    a = _eintrag(eintraege, "Beispiel")
    assert a["email"] is None and a["telefonnummer"] is None
    assert a["daten_anfragbar"] is True
    assert _eintrag([e for e in eintraege if e["vorname"] == "Rebekka"], "Fink")["daten_anfragbar"] is False


def test_ohne_mitglied_datensatz_sieht_niemanden(welt):
    from diakronos_app.api.mitglieder import get_adressbuch

    welt.add(User(name="konto-ohne@example.org", email="konto-ohne@example.org", enabled=1))
    welt.commit()
    set_user("konto-ohne@example.org")
    assert get_adressbuch()["data"] == []


def test_daten_anfragen_meldet_einmal_je_woche(welt):
    from diakronos_app.api.mitglieder import daten_anfragen

    set_user(SAMUEL)
    assert daten_anfragen("M-Anna")["gesendet"] is True
    assert daten_anfragen("M-Anna").get("bereits") is True
    welt.expire_all()
    meldungen = welt.query(NotificationLog).filter_by(for_user=ANNA, type="Datenanfrage").all()
    assert len(meldungen) == 1
    assert "Samuel" in meldungen[0].subject
    # eigene Person und Unbekannte: nichts gesendet, keine Auskunft
    assert daten_anfragen("M-Samuel")["gesendet"] is False
    assert daten_anfragen("gibt-es-nicht")["gesendet"] is False


def test_daten_anfragen_nur_gemeindemitglieder(welt):
    from diakronos_app.api.mitglieder import daten_anfragen

    welt.add(User(name="konto-ohne@example.org", email="konto-ohne@example.org", enabled=1))
    welt.commit()
    set_user("konto-ohne@example.org")
    with pytest.raises(PermErr):
        daten_anfragen("M-Anna")
