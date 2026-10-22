"""P4c1 — Portierte Ressourcen-/Anmelde-Kalender-Endpunkte.

Prueft die 4 portierten Endpunkte der zwei Module
`diakronos.kronos.api.ressource_api` und `diakronos.diakonos.api.kalender`
gegen eine eigene Ressourcen-/Element-Fixture.

Abgedeckt:
  * Registrierung unter den exakten SPA-dotted-paths.
  * Login-Pflicht jedes Endpunkts (`@whitelist(allow_guest=False)`).
  * `get_ressources`: Optionsliste, Sortierung (COALESCE), Feldabbildung.
  * `get_kronos_settings`: Defaults bei fehlendem Single, Werte bei vorhandenem.
  * `check_resource_conflict`: Leerlauf, Ueberlappung (direkt + Kind-Tabelle),
    `exclude_id`, `zusaetzliche_ressourcen` (JSON-String + Liste), Buchungen.
  * `kalender.get_events`: Status-Filter, Datumsfenster, Limit, Slug-Lookup,
    Guest-Verhalten.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.diakonos import Registrierungslink, RessourcenBuchung
from diakronos_app.models.kronos import (
    Element,
    ElementRessource,
    Kalender,
    KronosEinstellungen,
    Ressource,
)

# Der Router laedt die API-Module erst beim ersten Request (`router._get_registry`).
# Im Test importieren wir sie explizit, damit die Registrierung stattfindet.
import diakronos_app.api  # noqa: E402,F401


# ── Fixture ────────────────────────────────────────────────────────────────
#
# Ressourcen:
#   RES-RAUM   typ "Raum"       -> primaere Belegung an EL-1 (direktes Feld)
#   RES-AUTO   typ "Fahrzeug"   -> Zusatzressource via Kind-Tabelle an EL-2
#   RES-FREI   typ "Gegenstand" -> nie belegt
#
# Elemente:
#   EL-1  RES-RAUM, 01.06.2025 09:00-10:30, Festgelegt
#   EL-2  RES-AUTO via Element Ressource, 01.06.2025 11:00-12:00
#   EL-PENDING  status "Vorschlag" -> fuer get_events unsichtbar
#
# Buchungen:
#   BUCH-1  RES-RAUM, "Bestätigt", 01.06.2025 10:00-11:00 (ueberlappt 09:30-10:30)


@pytest.fixture()
def ressourcenwelt(patched_db):
    sess = patched_db()

    sess.add_all([
        User(name="admin@example.org", email="admin@example.org",
             full_name="Admin", enabled=True),
        User(name="mitglied-a@example.org", email="mitglied-a@example.org",
             full_name="Mitglied A", enabled=True),
    ])
    # `kalender.get_events` filtert seit OP-EVENT-R1 nach Leserecht; die
    # Frueheres-Fixture kannte gar keinen Kalender. KAL-1 ist fuer "Mitglied"
    # lesbar, KAL-GEHEIM nicht -> Regression belegbar.
    sess.add_all([
        HasRole(name="HR-MIT", parent="mitglied-a@example.org", parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name="KAL-1", calendar_name="Gemeinde", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name="KAL-GEHEIM", calendar_name="Gemeinschaftsteam",
                 calendar_color="#222222", selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        UserRole(name="UR-K1", parent="KAL-1", parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Ressource(name="RES-RAUM", ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, beschreibung="Grosser Saal", bild="/files/saal.png",
                  docstatus=0, idx=0),
        Ressource(name="RES-AUTO", ressource_name="Bulli", typ="Fahrzeug",
                  kapazitaet=9, docstatus=0, idx=0),
        Ressource(name="RES-FREI", ressource_name="Beamer", typ="Gegenstand",
                  docstatus=0, idx=0),
        # Ohne typ -> muss in der Sortierung und im Fallback "Sonstiges" landen.
        Ressource(name="RES-OHNE", ressource_name="Zelt",
                  docstatus=0, idx=0),
    ])
    sess.add_all([
        KronosEinstellungen(name="Kronos Einstellungen",
                            ressource_pflichtfeld=1, standard_ressource="RES-RAUM",
                            docstatus=0, idx=0),
    ])
    sess.flush()

    sess.add_all([
        Element(name="EL-1", element_name="Gottesdienst", element_calendar="KAL-1",
                element_start=datetime(2025, 6, 1, 9, 0, 0),
                element_end=datetime(2025, 6, 1, 10, 30, 0), all_day=False,
                status="Festgelegt", ressource="RES-RAUM",
                registrierungslink="RL-1", anmeldung_aktiv=1,
                docstatus=0, idx=0),
        Element(name="EL-2", element_name="Ausflug", element_calendar="KAL-1",
                element_start=datetime(2025, 6, 1, 11, 0, 0),
                element_end=datetime(2025, 6, 1, 12, 0, 0), all_day=False,
                status="Festgelegt", docstatus=0, idx=0),
        Element(name="EL-PENDING", element_name="Vorschlag Termin",
                element_calendar="KAL-1",
                element_start=datetime(2025, 6, 1, 14, 0, 0),
                element_end=datetime(2025, 6, 1, 15, 0, 0), all_day=False,
                status="Vorschlag", docstatus=0, idx=0),
        # Ueberlappt NICHT (liegt vor dem Fenster).
        Element(name="EL-FRUEH", element_name="Frueh", element_calendar="KAL-1",
                element_start=datetime(2025, 6, 1, 6, 0, 0),
                element_end=datetime(2025, 6, 1, 7, 0, 0), all_day=False,
                status="Festgelegt", ressource="RES-RAUM", docstatus=0, idx=0),
        # Storniert (docstatus 2) und ueberlappt -> darf NICHT zaehlen.
        Element(name="EL-CANCEL", element_name="Storniert", element_calendar="KAL-1",
                element_start=datetime(2025, 6, 1, 9, 30, 0),
                element_end=datetime(2025, 6, 1, 10, 0, 0), all_day=False,
                status="Festgelegt", ressource="RES-RAUM", docstatus=2, idx=0),
    ])
    sess.add_all([
        # Zusatzressource RES-AUTO haengt via Kind-Tabelle an EL-2.
        ElementRessource(name="ER-1", parent="EL-2", parenttype="Element",
                         parentfield="zusaetzliche_ressourcen",
                         ressource="RES-AUTO", status="Bestätigt",
                         docstatus=0, idx=1),
        RessourcenBuchung(name="BUCH-1", ressource="RES-RAUM", status="Bestätigt",
                          zweck="Putzdienst",
                          datum_von=datetime(2025, 6, 1, 10, 0, 0),
                          datum_bis=datetime(2025, 6, 1, 11, 0, 0),
                          docstatus=0, idx=0),
        Registrierungslink(name="RL-1", bezeichnung="Anmeldung", typ="Element",
                           aktiv=1, slug="gottesdienst-2025", docstatus=0, idx=0),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_session_user():
    yield
    set_user("Administrator")


# ── Registrierung unter den SPA-Pfaden ─────────────────────────────────────

SPA_PFADE = [
    "diakronos.kronos.api.ressource_api.get_ressources",
    "diakronos.kronos.api.ressource_api.get_kronos_settings",
    "diakronos.kronos.api.ressource_api.check_resource_conflict",
    "diakronos.diakonos.api.kalender.get_events",
]


@pytest.mark.parametrize("pfad", SPA_PFADE)
def test_spa_pfad_ist_registriert(pfad):
    """Jeder Port muss unter seinem Original-dotted-path aufloesbar sein."""
    from diakronos_app.frappe_compat.registry import lookup

    assert lookup(pfad) is not None, f"{pfad} nicht registriert"


ENDPUNKTE = [
    ("diakronos_app.api.kronos.ressource_api", "get_ressources"),
    ("diakronos_app.api.kronos.ressource_api", "get_kronos_settings"),
    ("diakronos_app.api.kronos.ressource_api", "check_resource_conflict"),
    ("diakronos_app.api.kronos.kalender", "get_events"),
]


def _options(fn):
    from diakronos_app.frappe_compat.registry import options_for

    return options_for(fn)


@pytest.mark.parametrize("modul,name", ENDPUNKTE)
def test_endpunkte_sind_nicht_guest(modul, name):
    """`@whitelist(allow_guest=False)` muss am Port haengen (Kartensperre)."""
    import importlib

    fn = getattr(importlib.import_module(modul), name)
    assert _options(fn).get("allow_guest") is False, f"{modul}.{name} ist guest-erlaubt"


def test_frappe_module_konstante():
    """Jedes Modul traegt seinen Original-Pfad (Registry-Schluessel)."""
    from diakronos_app.api.kronos import kalender, ressource_api

    assert ressource_api.FRAPPE_MODULE == "diakronos.kronos.api.ressource_api"
    assert kalender.FRAPPE_MODULE == "diakronos.diakonos.api.kalender"


def test_typ_options_match_referenz_doctype():
    """Drift-Guard: `_TYPE_OPTIONS_RAW` == Select-Optionen des Alt-DocTypes.

    Die Optionsliste ist im Port als Konstante hinterlegt (das Deployment
    schliesst `referenz/` aus, `.dockerignore`), muss aber identisch zum
    Alt-DocType bleiben. Fehlt der Referenzbaum (Deployment/CI), wird
    uebersprungen.
    """
    from diakronos_app.api.kronos.ressource_api import _TYPE_OPTIONS_RAW

    ref = Path(__file__).resolve().parents[2] / "referenz" / "diakronos-frappe" \
        / "diakronos" / "kronos" / "doctype" / "ressource" / "ressource.json"
    if not ref.exists():
        pytest.skip("Referenzbaum nicht vorhanden (Deployment)")
    doctype = json.loads(ref.read_text(encoding="utf-8"))
    options = next(f["options"] for f in doctype["fields"] if f["fieldname"] == "typ")
    assert _TYPE_OPTIONS_RAW == options


# ── HTTP-Envelope unter den SPA-Pfaden ─────────────────────────────────────
#
# Die direkten Funktionsaufrufe oben beweisen die Logik; diese vier Aufrufe
# beweisen, dass die Original-dotted-paths wirklich durch den Router
# aufloesen (genau der Fehler, den main 33c296a behoben hat).


def test_http_get_ressources(ressourcenwelt):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user("mitglied-a@example.org")
    with TestClient(app) as c:
        r = c.get("/api/method/diakronos.kronos.api.ressource_api.get_ressources")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["types"] == ["Raum", "Fahrzeug", "Gegenstand"]


def test_http_get_kronos_settings(ressourcenwelt):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user("mitglied-a@example.org")
    with TestClient(app) as c:
        r = c.get("/api/method/diakronos.kronos.api.ressource_api.get_kronos_settings")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["standard_ressource"] == "RES-RAUM"


def test_http_check_resource_conflict(ressourcenwelt):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user("mitglied-a@example.org")
    with TestClient(app) as c:
        r = c.get(
            "/api/method/diakronos.kronos.api.ressource_api.check_resource_conflict",
            params={"ressource": "RES-RAUM",
                    "element_start": "2025-06-01 09:15:00",
                    "element_end": "2025-06-01 09:45:00"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["has_conflict"] is True


def test_http_get_events(ressourcenwelt):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user("mitglied-a@example.org")
    with TestClient(app) as c:
        r = c.get("/api/method/diakronos.diakonos.api.kalender.get_events",
                  params={"start_date": "2025-06-01", "end_date": "2025-06-30"})
    assert r.status_code == 200, r.text
    ids = {e["id"] for e in r.json()["message"]}
    assert "EL-1" in ids


# ── get_ressources ─────────────────────────────────────────────────────────


def test_get_ressources_optionsliste(ressourcenwelt):
    """Die Select-Optionen des Altcode-DocType `Ressource` (Feld `typ`)."""
    from diakronos_app.api.kronos import ressource_api

    data = ressource_api.get_ressources()
    assert data["types"] == ["Raum", "Fahrzeug", "Gegenstand"]


def test_get_ressources_sortierung_coalesce(ressourcenwelt):
    """Order: typ (leer zuerst) dann ressource_name.

    Erwartet: "" (Zelt) < "Fahrzeug" (Bulli) < "Gegenstand" (Beamer) < "Raum".
    """
    from diakronos_app.api.kronos import ressource_api

    ids = [r["id"] for r in ressource_api.get_ressources()["resources"]]
    assert ids == ["RES-OHNE", "RES-AUTO", "RES-FREI", "RES-RAUM"]


def test_get_ressources_feldabbildung(ressourcenwelt):
    from diakronos_app.api.kronos import ressource_api

    by_id = {r["id"]: r for r in ressource_api.get_ressources()["resources"]}
    raum = by_id["RES-RAUM"]
    assert raum == {
        "id": "RES-RAUM",
        "title": "Gemeindesaal",
        "typ": "Raum",
        "kapazitaet": 80,
        "beschreibung": "Grosser Saal",
        "bild": "/files/saal.png",
    }


def test_get_ressources_typ_fallback_sonstiges(ressourcenwelt):
    """Ressource ohne `typ` -> "Sonstiges" im Ergebnis."""
    from diakronos_app.api.kronos import ressource_api

    by_id = {r["id"]: r for r in ressource_api.get_ressources()["resources"]}
    assert by_id["RES-OHNE"]["typ"] == "Sonstiges"


def test_get_ressources_beschreibung_leer(ressourcenwelt):
    """Fehlende Beschreibung -> "" (nicht None)."""
    from diakronos_app.api.kronos import ressource_api

    by_id = {r["id"]: r for r in ressource_api.get_ressources()["resources"]}
    assert by_id["RES-AUTO"]["beschreibung"] == ""


def test_get_ressources_title_fallback_name(ressourcenwelt):
    """Ohne ressource_name ist der Titel der Docname."""
    from diakronos_app.api.kronos import ressource_api

    sess = ressourcenwelt
    sess.add(Ressource(name="RES-NONAME", typ="Raum", docstatus=0, idx=0))
    sess.commit()
    by_id = {r["id"]: r for r in ressource_api.get_ressources()["resources"]}
    assert by_id["RES-NONAME"]["title"] == "RES-NONAME"


# ── get_kronos_settings ────────────────────────────────────────────────────


def test_get_kronos_settings_liest_single(ressourcenwelt):
    from diakronos_app.api.kronos import ressource_api

    assert ressource_api.get_kronos_settings() == {
        "ressource_pflichtfeld": 1,
        "standard_ressource": "RES-RAUM",
    }


def test_get_kronos_settings_defaults_ohne_single(patched_db):
    """Fehlt der Single, greifen die Original-Defaults (0 / "")."""
    from diakronos_app.api.kronos import ressource_api

    patched_db().commit()
    assert ressource_api.get_kronos_settings() == {
        "ressource_pflichtfeld": 0,
        "standard_ressource": "",
    }


# ── check_resource_conflict ────────────────────────────────────────────────


def test_conflict_ohne_argumente_ist_leer(ressourcenwelt):
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(None, None, None)
    assert res == {"has_conflict": False, "conflict": False,
                   "events": [], "conflicts": []}


def test_conflict_ohne_zeitraum_ist_leer(ressourcenwelt):
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict("RES-RAUM", None, None)
    assert res["has_conflict"] is False


def test_conflict_freie_ressource(ressourcenwelt):
    """RES-FREI ist nie belegt -> kein Konflikt."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-FREI", "2025-06-01 09:00:00", "2025-06-01 10:00:00")
    assert res["has_conflict"] is False
    assert res["conflict"] is False
    assert res["events"] == []


def test_conflict_direkte_ueberlappung(ressourcenwelt):
    """Fenster ueberlappt EL-1 (RES-RAUM direktes Feld)."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 09:15:00", "2025-06-01 09:45:00")
    assert res["has_conflict"] is True
    assert res["conflict"] is True
    names = {e["name"] for e in res["events"]}
    assert "EL-1" in names
    # Storniertes Element (docstatus=2) darf nicht auftauchen.
    assert "EL-CANCEL" not in names
    # Ausserhalb liegendes Element ebenfalls nicht.
    assert "EL-FRUEH" not in names


def test_conflict_ueber_kind_tabelle(ressourcenwelt):
    """RES-AUTO haengt nur via `Element Ressource` an EL-2."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-AUTO", "2025-06-01 11:30:00", "2025-06-01 11:45:00")
    assert res["has_conflict"] is True
    names = {e["name"] for e in res["events"]}
    assert "EL-2" in names


def test_conflict_beruehrung_zaehlt_nicht(ressourcenwelt):
    """Fenster endet genau am Start von EL-1 -> keine Ueberlappung (< / >)."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 08:00:00", "2025-06-01 09:00:00")
    assert res["has_conflict"] is False


def test_conflict_exclude_id(ressourcenwelt):
    """`exclude_id` blendet das eigene Element aus."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 09:00:00", "2025-06-01 10:30:00",
        exclude_id="EL-1")
    # EL-1 ist ausgeschlossen; die Buchung BUCH-1 liegt aber im Fenster
    # (10:00-11:00 <-> 09:00-10:30) -> harter Konflikt bleibt.
    assert res["has_conflict"] is True
    assert res["events"] == []
    assert any(b.get("buchungen") for b in res["conflicts"])


def test_conflict_exclude_id_ohne_buchung(ressourcenwelt):
    """Ohne Buchung und mit exclude_id bleibt kein Konflikt."""
    from diakronos_app.api.kronos import ressource_api

    # Nur EL-1 ueberlappt in diesem engen Fenster; ausschliessen -> leer.
    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 09:00:00", "2025-06-01 09:30:00",
        exclude_id="EL-1")
    assert res["has_conflict"] is False


def test_conflict_buchung_erzeugt_harten_konflikt(ressourcenwelt):
    """Bestaetigte Buchung im Fenster -> has_conflict mit `buchungen`-Eintrag."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 10:15:00", "2025-06-01 10:45:00")
    assert res["has_conflict"] is True
    buchungen = [b for entry in res["conflicts"] for b in entry.get("buchungen", [])]
    assert {b["name"] for b in buchungen} == {"BUCH-1"}
    assert buchungen[0]["zweck"] == "Putzdienst"


def test_conflict_zusaetzliche_als_json_string(ressourcenwelt):
    """`zusaetzliche_ressourcen` als JSON-String wird geparst."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        None, "2025-06-01 11:30:00", "2025-06-01 11:45:00",
        zusaetzliche_ressourcen='[{"ressource": "RES-AUTO", '
                               '"freitext_ressource": "egal"}]')
    assert res["has_conflict"] is True
    assert {e["name"] for e in res["conflicts"][0]["events"]} == {"EL-2"}


def test_conflict_zusaetzliche_als_liste(ressourcenwelt):
    """`zusaetzliche_ressourcen` als Liste von dicts."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        None, "2025-06-01 09:15:00", "2025-06-01 09:45:00",
        zusaetzliche_ressourcen=[{"ressource": "RES-RAUM"}])
    assert res["has_conflict"] is True
    assert any(e["name"] == "EL-1" for e in res["conflicts"][0]["events"])


def test_conflict_nur_freitext_wird_ignoriert(ressourcenwelt):
    """Nur-Freitext-Zusatzressourcen (ohne `ressource`) -> nichts zu pruefen."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        None, "2025-06-01 09:15:00", "2025-06-01 09:45:00",
        zusaetzliche_ressourcen=[{"freitext_ressource": "irgendein Raum"}])
    assert res["has_conflict"] is False


def test_conflict_ungueltiger_json_string(ressourcenwelt):
    """Kaputter JSON-String -> wie leer behandelt, kein Fehler."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        None, "2025-06-01 09:15:00", "2025-06-01 09:45:00",
        zusaetzliche_ressourcen="{nicht json")
    assert res["has_conflict"] is False


def test_conflict_mehrere_ressourcen(ressourcenwelt):
    """Primaere + Zusatzressource: Konflikte werden pro Ressource gelistet."""
    from diakronos_app.api.kronos import ressource_api

    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 09:00:00", "2025-06-01 12:00:00",
        zusaetzliche_ressourcen=[{"ressource": "RES-AUTO"}])
    rids = {c["ressource"] for c in res["conflicts"]}
    assert {"RES-RAUM", "RES-AUTO"} <= rids
    # `events` (backward compat) betrifft nur die Primaerressource.
    assert {e["name"] for e in res["events"]} <= {"EL-1"}
    assert res["conflict"] is True


def test_conflict_events_tragen_elementfelder(ressourcenwelt):
    """Die Event-Eintraege enthalten die Original-SELECT-Spalten."""
    from diakronos_app.api.kronos import ressource_api

    # Als Administrator (Vollzugriff) sind die Felder ungefiltert sichtbar.
    set_user("Administrator")
    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 09:15:00", "2025-06-01 09:45:00")
    event = next(e for e in res["events"] if e["name"] == "EL-1")
    assert {"name", "element_name", "element_start",
            "element_end", "element_calendar"} <= set(event)
    assert event["element_name"] == "Gottesdienst"
    assert event["element_calendar"] == "KAL-1"


def test_conflict_maskiert_gesperrten_kalender(ressourcenwelt):
    """OP-EVENT-R1: kein Titel/Kalender fremder Termine in Konfliktantworten.

    Als Mitglied (liest KAL-1, nicht KAL-GEHEIM) bleibt von einem Termin im
    gesperrten Kalender nur die Belegung uebrig — kein Titel, kein Kalender.
    """
    from diakronos_app.api.kronos import ressource_api

    sess = ressourcenwelt
    sess.add(Element(name="EL-GEHEIM", element_name="Geheime Leitung",
                     element_calendar="KAL-GEHEIM",
                     element_start=datetime(2025, 6, 1, 9, 15, 0),
                     element_end=datetime(2025, 6, 1, 9, 45, 0),
                     status="Festgelegt", ressource="RES-RAUM",
                     docstatus=0, idx=0))
    sess.commit()

    set_user("mitglied-a@example.org")
    res = ressource_api.check_resource_conflict(
        "RES-RAUM", "2025-06-01 09:20:00", "2025-06-01 09:40:00")
    assert res["has_conflict"] is True
    geheim = next(e for e in res["events"] if e["name"] == "EL-GEHEIM")
    assert geheim["element_name"] == "Belegt"
    assert geheim["element_calendar"] == ""
    # Lesbarer Kalender bleibt vollstaendig.
    lesbar = next(e for e in res["events"] if e["name"] == "EL-1")
    assert lesbar["element_name"] == "Gottesdienst"


# ── kalender.get_events ────────────────────────────────────────────────────


def test_get_events_guest_ist_leer(ressourcenwelt):
    from diakronos_app.api.kronos import kalender

    set_user("Guest")
    assert kalender.get_events("2025-06-01", "2025-06-30") == []


def test_get_events_nur_festgelegt(ressourcenwelt):
    """`status = "Festgelegt"` — Vorschlag-Elemente fehlen."""
    from diakronos_app.api.kronos import kalender

    set_user("mitglied-a@example.org")
    ids = {e["id"] for e in kalender.get_events("2025-06-01", "2025-06-30")}
    assert "EL-1" in ids
    assert "EL-PENDING" not in ids


def test_get_events_feldabbildung(ressourcenwelt):
    from diakronos_app.api.kronos import kalender

    set_user("mitglied-a@example.org")
    ev = next(e for e in kalender.get_events("2025-06-01", "2025-06-30")
              if e["id"] == "EL-1")
    assert ev["title"] == "Gottesdienst"
    assert ev["start"] == "2025-06-01"
    assert ev["end"] == "2025-06-01"
    assert ev["startDatetime"].startswith("2025-06-01 09:00")
    assert ev["endDatetime"].startswith("2025-06-01 10:30")
    assert ev["allDay"] is False
    assert ev["anmeldungAktiv"] is True
    assert ev["registrierungslinkId"] == "RL-1"
    assert ev["registrierungslinkSlug"] == "gottesdienst-2025"


def test_get_events_titel_fallback(ressourcenwelt):
    """Element ohne element_name -> "(Kein Titel)"."""
    from diakronos_app.api.kronos import kalender

    sess = ressourcenwelt
    sess.add(Element(name="EL-UNTITLED", element_calendar="KAL-1",
                     element_start=datetime(2025, 6, 5, 18, 0, 0),
                     element_end=datetime(2025, 6, 5, 19, 0, 0),
                     status="Festgelegt", docstatus=0, idx=0))
    sess.commit()
    set_user("mitglied-a@example.org")
    ev = next(e for e in kalender.get_events("2025-06-01", "2025-06-30")
              if e["id"] == "EL-UNTITLED")
    assert ev["title"] == "(Kein Titel)"


def test_get_events_ohne_registrierungslink(ressourcenwelt):
    """Kein Link -> leere id/slug."""
    from diakronos_app.api.kronos import kalender

    set_user("mitglied-a@example.org")
    ev = next(e for e in kalender.get_events("2025-06-01", "2025-06-30")
              if e["id"] == "EL-2")
    assert ev["registrierungslinkId"] == ""
    assert ev["registrierungslinkSlug"] == ""


def test_get_events_datumsfenster(ressourcenwelt):
    """Nur Ereignisse im Fenster (element_end >= start_date)."""
    from diakronos_app.api.kronos import kalender

    set_user("mitglied-a@example.org")
    ids = {e["id"] for e in kalender.get_events("2025-06-05", "2025-06-30")}
    assert "EL-1" not in ids


def test_get_events_limit_500(ressourcenwelt):
    """`limit=500` ist gesetzt — 600 Elemente liefern hoechstens 500."""
    from diakronos_app.api.kronos import kalender

    sess = ressourcenwelt
    for i in range(600):
        sess.add(Element(name=f"EL-MASS-{i:04d}", element_calendar="KAL-1",
                         element_start=datetime(2025, 6, 10, 0, 0, 0),
                         element_end=datetime(2025, 6, 10, 1, 0, 0),
                         status="Festgelegt", docstatus=0, idx=0))
    sess.commit()
    set_user("mitglied-a@example.org")
    assert len(kalender.get_events("2025-06-10", "2025-06-10")) == 500


def test_get_events_leeres_fenster(ressourcenwelt):
    from diakronos_app.api.kronos import kalender

    set_user("mitglied-a@example.org")
    assert kalender.get_events("2026-01-01", "2026-01-31") == []


# ── OP-EVENT-R1: get_events filtert nach Leserecht ─────────────────────────


def test_get_events_verraet_gesperrten_kalender_nicht(ressourcenwelt):
    """Termine gesperrter Kalender duerfen nicht ausgeliefert werden.

    Regression zum Nachtbefund OP-EVENT-R1: der Endpunkt lieferte ALLE
    Festgelegt-Termine aller Kalender (mitglied@ sah Gemeinschaftsteam).
    """
    from diakronos_app.api.kronos import kalender

    sess = ressourcenwelt
    sess.add(Element(name="EL-GEHEIM", element_name="Geheime Leitung",
                     element_calendar="KAL-GEHEIM",
                     element_start=datetime(2025, 6, 3, 21, 0, 0),
                     element_end=datetime(2025, 6, 3, 22, 0, 0),
                     status="Festgelegt", docstatus=0, idx=0))
    sess.commit()

    set_user("mitglied-a@example.org")
    ids = {e["id"] for e in kalender.get_events("2025-06-01", "2025-06-30")}
    assert "EL-GEHEIM" not in ids, "gesperrter Kalender leakt in get_events"
    assert "EL-1" in ids, "lesbarer Kalender fehlt"

    # Gegenprobe: Administrator (Vollzugriff) sieht den Termin.
    set_user("Administrator")
    ids_admin = {e["id"] for e in kalender.get_events("2025-06-01", "2025-06-30")}
    assert "EL-GEHEIM" in ids_admin


# ═══════════════════════════════════════════════════════════════════════════
# Regression: Filterwerte muessen an die Spaltentypen angepasst werden.
#
# Befund aus dem echten HTTP-Probe gegen den Container (PostgreSQL):
#
#   curl '.../check_resource_conflict?element_start=2025-06-01 09:00:00'
#   -> 500;  asyncpg: operator does not exist:
#      timestamp without time zone <= character varying
#
# `element_start`/`element_end`/`datum_von`/`datum_bis` sind in PostgreSQL
# `timestamp without time zone` (information_schema.columns), `get_all` bindet
# uebergebene Strings aber als `VARCHAR`. SQLite (Test-Fixture) vergleicht
# tolerant, PostgreSQL nicht — daher liefen alle Tests gruen, waehrend der
# Endpunkt live 500 lieferte. `_coerce_filters` schliesst die Luecke.
# ═══════════════════════════════════════════════════════════════════════════


def test_coerce_filters_wandelt_zeitstrings_in_datetime():
    """Operator-Paare und blanke Werte: Zeitstrings werden zu `datetime`."""
    from diakronos_app.api.kronos.ressource_api import _coerce_filters

    out = _coerce_filters(
        "Element",
        {
            "element_start": ["<", "2025-06-01 10:00:00"],
            "element_end": [">", "2025-06-01 09:00:00"],
            "status": "Festgelegt",
        },
    )

    assert isinstance(out["element_start"][1], datetime)
    assert isinstance(out["element_end"][1], datetime)
    # Operator bleibt erhalten, Textspalten bleiben unangetastet.
    assert out["element_start"][0] == "<"
    assert out["element_end"][0] == ">"
    assert out["status"] == "Festgelegt"


def test_coerce_filters_buchungsspalten():
    """`datum_von`/`datum_bis` der Ressourcen Buchung ebenfalls `datetime`."""
    from diakronos_app.api.kronos.ressource_api import _coerce_filters

    out = _coerce_filters(
        "Ressourcen Buchung",
        {
            "datum_von": ["<", "2025-06-01 10:00:00"],
            "datum_bis": [">", "2025-06-01 09:00:00"],
            "ressource": "RES-1",
        },
    )

    assert isinstance(out["datum_von"][1], datetime)
    assert isinstance(out["datum_bis"][1], datetime)
    assert out["ressource"] == "RES-1"


def test_coerce_filters_listen_operator_bleibt_liste():
    """`["in", [...]]` und `["!=", v]` duerfen nicht kaputtgehen."""
    from diakronos_app.api.kronos.ressource_api import _coerce_filters

    out = _coerce_filters(
        "Element",
        {
            "name": ["in", ["EL-1", "EL-2"]],
            "docstatus": ["!=", 2],
        },
    )

    assert out["name"] == ["in", ["EL-1", "EL-2"]]
    assert out["docstatus"] == ["!=", 2]


def test_coerce_filters_kalender_zeitstrings():
    """Auch `kalender._coerce_filters` liefert vergleichbare `datetime`."""
    from diakronos_app.api.kronos.kalender import _coerce_filters

    out = _coerce_filters(
        "Element",
        {
            "element_start": ["<=", "2025-06-30 23:59:59"],
            "element_end": [">=", "2025-06-01"],
            "status": "Festgelegt",
        },
    )

    assert isinstance(out["element_start"][1], datetime)
    assert isinstance(out["element_end"][1], datetime)
    assert out["element_start"][0] == "<="
    assert out["element_end"][0] == ">="
    assert out["status"] == "Festgelegt"

