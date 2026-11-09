"""PR-G1: Dienstplan-Stammdaten — Geschlecht normalisiert ausliefern.

Anlass (Manuel): In den Stammdaten muss man nach m/w filtern/sortieren
koennen. Das Mitgliedsfeld ``geschlecht`` ist Freitext („Männlich“,
teils ''/NULL). Die Stammdaten-Antwort (``stammdaten_holen``) liefert es
deshalb NORMALISIERT als ``'m' | 'w' | ''`` (DEV-B3: nur männlich/weiblich).

Geprueft wird:

1. Normalisierung (Schreibweisen, Gross/Klein, Umlaut-Varianten, Unbekanntes
   -> '', NULL -> ''),
2. Rechte unveraendert (gast 403, Planverantwortliche(r) nur mit Plan-ID),
3. keine neuen Felder anderswo (oeffentliche/andere Antworten unberuehrt),
4. der Pool-Planer sieht weiterhin nur seine Pool-Personen.
"""
from __future__ import annotations

import pytest

from test_planrahmen_ui2 import PFAD, anmelden, aufruf, stamm_setup


# --------------------------------------------------------------------------- #
# 1. Normalisierung (reine Funktion — ohne DB)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("roh, erwartet", [
    ("Männlich", "m"), ("männlich", "m"), ("MÄNNLICH", "m"), ("M", "m"), ("m", "m"),
    ("maennlich", "m"), ("  Männlich  ", "m"), ("Mann", "m"), ("male", "m"),
    ("Weiblich", "w"), ("weiblich", "w"), ("WEIBLICH", "w"), ("W", "w"), ("w", "w"),
    ("weiblich ", "w"), ("Frau", "w"), ("female", "w"),
    # DEV-B3 (Entscheidung Manuel 2026-10-29): nur männlich/weiblich. Frühere
    # „Divers"/„inter"-Angaben gelten als „keine Angabe" (Altdaten bleiben
    # in der Datenbank stehen, werden aber nicht mehr als d geliefert).
    ("Divers", ""), ("divers", ""), ("DIVERS", ""), ("D", ""), ("d", ""),
    ("diverse", ""), ("inter", ""), ("intersexuell", ""),
    # Unbekannt/leer -> '' (fail-closed: niemand gilt versehentlich als Mann).
    ("", ""), ("   ", ""), (None, ""), ("k. A.", ""), ("unbekannt", ""),
    ("m/w", ""), ("Herr", "m"),
])
def test_geschlecht_normalisieren(roh, erwartet):
    from diakronos_app.planrahmen.datenquelle_db import geschlecht_normalisieren
    assert geschlecht_normalisieren(roh) == erwartet


def test_geschlecht_normalisieren_nicht_text():
    from diakronos_app.planrahmen.datenquelle_db import geschlecht_normalisieren
    assert geschlecht_normalisieren(1) == ""
    assert geschlecht_normalisieren(["Männlich"]) == ""


# --------------------------------------------------------------------------- #
# 2. Die Stammdaten-Antwort liefert das Geschlecht normalisiert
# --------------------------------------------------------------------------- #

def _geschlechter_setzen(sf, werte: dict[str, str | None]):
    """Geschlecht einzelner Mitglieder setzen (Rohwerte wie im Betrieb)."""
    from sqlalchemy import select
    from diakronos_app.models.diakonos import Mitglied
    with sf.begin() as s:
        for kennung, wert in werte.items():
            m = s.scalar(select(Mitglied).where(Mitglied.name == kennung))
            assert m is not None, kennung
            m.geschlecht = wert


def test_stammdaten_personen_liefert_geschlecht_normalisiert(client, patched_db):
    stamm_setup(client, patched_db)
    _geschlechter_setzen(patched_db, {"mia": "Weiblich", "jonas": "Männlich"})
    anmelden(client, "planer_chor")
    daten = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")
    personen = {p["kennung"]: p for p in daten["personen"]}
    assert personen["mia"]["geschlecht"] == "w"
    assert personen["jonas"]["geschlecht"] == "m"


def test_stammdaten_geschlecht_leer_und_unbekannt(client, patched_db):
    stamm_setup(client, patched_db)
    _geschlechter_setzen(patched_db, {"mia": None, "jonas": "irgendwas"})
    anmelden(client, "planer_chor")
    personen = {p["kennung"]: p for p in
                aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")["personen"]}
    assert personen["mia"]["geschlecht"] == ""
    assert personen["jonas"]["geschlecht"] == ""


def test_stammdaten_geschlecht_nur_ein_buchstabe_im_feld(client, patched_db):
    """Kein Rohwert, keine weiteren Attributfelder — nur 'geschlecht' dazu."""
    stamm_setup(client, patched_db)
    _geschlechter_setzen(patched_db, {"mia": "MÄNNLICH"})
    anmelden(client, "planer_chor")
    person = next(p for p in aufruf(client, "stammdaten_holen", plantyp="stamm-ui2")["personen"]
                  if p["kennung"] == "mia")
    assert person["geschlecht"] == "m"
    assert "MÄNNLICH" not in str(person)
    # Neue Felder gibt es nur als `geschlecht` — kein `familienstand`, kein
    # `foto`, keine E-Mail.
    assert set(person) == {"kennung", "anzeige", "name", "vorname", "nachname",
                           "kuerzel", "geschlecht", "gruppen", "merkmale"}


# --------------------------------------------------------------------------- #
# 3. Rechte unveraendert
# --------------------------------------------------------------------------- #

def test_geschlecht_aendert_die_rechte_nicht(client, patched_db):
    plan = stamm_setup(client, patched_db, verantwortlich="mitglied")
    _geschlechter_setzen(patched_db, {"mia": "Weiblich", "jonas": "Männlich"})
    # Gast: kein Zugriff (wie zuvor).
    anmelden(client, "gast")
    assert client.get(PFAD + "stammdaten_holen", params={"plantyp": "stamm-ui2"}).status_code == 403
    # Planverantwortliche(r) ohne Bereich: nur mit Plan-ID.
    anmelden(client, "mitglied")
    assert client.get(PFAD + "stammdaten_holen", params={"plantyp": "stamm-ui2"}).status_code == 403
    mit_plan = aufruf(client, "stammdaten_holen", plantyp="stamm-ui2", plan=plan)
    assert {p["kennung"]: p["geschlecht"] for p in mit_plan["personen"]}["jonas"] == "m"
    # Fremder Bereich: 403.
    anmelden(client, "planer_freizeit")
    assert client.get(PFAD + "stammdaten_holen", params={"plantyp": "stamm-ui2"}).status_code == 403


def test_pool_planer_sieht_nur_pool_personen_mit_geschlecht(client, patched_db):
    """Gruppenverantwortliche sehen weiterhin nur ihre Pool-Personen (mit Geschlecht)."""
    from sqlalchemy import select
    from diakronos_app.models.diakonos import Mitglied
    from test_planrahmen_st3_gruppen import _chorplan, _welt

    _welt(patched_db)
    with patched_db.begin() as s:
        # m3 trägt ein ALTdatum „Divers" (DEV-B3): es zählt als keine Angabe.
        for kennung, wert in (("m1", "Weiblich"), ("m2", "Männlich"), ("m3", "Divers")):
            m = s.scalar(select(Mitglied).where(Mitglied.name == kennung))
            assert m is not None, kennung
            m.geschlecht = wert
    anmelden(client, "chef")
    aufruf(client, "plantyp_speichern", definition=_chorplan(["Chor"]), gueltig_ab="2026-01-01")

    anmelden(client, "gv_chor")
    alle = aufruf(client, "stammdaten_holen", plantyp="chorplan-st3")
    geschlechter = {p["kennung"]: p["geschlecht"] for p in alle["personen"]}
    assert geschlechter == {"m1": "w", "m2": "m"}, "Pool grenzt weiterhin ein"
    assert alle["pool"]["gruppen"] == ["Chor"]
    assert "m3" not in geschlechter


# --------------------------------------------------------------------------- #
# 4. Keine neuen Felder anderswo
# --------------------------------------------------------------------------- #

def test_geschlecht_nicht_in_planantwort(client, patched_db):
    """`plan_holen` (Anzeige-Pfad) bekommt kein Geschlecht."""
    plan = stamm_setup(client, patched_db, verantwortlich="mitglied")
    _geschlechter_setzen(patched_db, {"mia": "Weiblich", "jonas": "Männlich"})
    anmelden(client, "Administrator")
    r = client.post(PFAD + "plan_holen", json={"plan": plan})
    assert r.status_code == 200, r.text
    text = r.text
    assert '"geschlecht"' not in text
    assert "Männlich" not in text and "Weiblich" not in text


def test_geschlecht_nicht_in_merkmal_kandidaten(client, patched_db):
    """`merkmal_kandidaten` (Kandidatenliste der Planung) bleibt unveraendert."""
    stamm_setup(client, patched_db)
    _geschlechter_setzen(patched_db, {"mia": "Weiblich"})
    anmelden(client, "Administrator")
    # 'dirigent' ist im Test-Plantyp ein Personen-Merkmal (tag), kein
    # Listen-Merkmal — die Ablehnung ist der Bestand und bleibt so.
    r = client.post(PFAD + "merkmal_kandidaten",
                    json={"plantyp": "stamm-ui2", "schluessel": "themen"})
    assert r.status_code == 417, r.text
    assert '"geschlecht"' not in r.text
    assert "Weiblich" not in r.text
