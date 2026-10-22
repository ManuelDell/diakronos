"""P4c3 — Portierte Module `api.kronos.ablaufplan_api` + `api.kronos.kanban_api`.

Quellen (READ-ONLY):
  * `referenz/diakronos-frappe/diakronos/kronos/api/ablaufplan_api.py` (3 Endpunkte)
  * `referenz/diakronos-frappe/diakronos/kronos/api/kanban_api.py` (6 Endpunkte)

Abgedeckt:
  * Login-Pflicht (`allow_guest=False`) — Guest -> 403.
  * Erreichbarkeit unter den ORIGINAL-SPA-Pfaden
    `diakronos.kronos.api.{ablaufplan_api,kanban_api}.<fn>`.
  * `get_ablaufplan`: None ohne Plan, vollstaendige Payload, Positionen nach idx.
  * `save_ablaufplan`: Lazy-Anlage nur bei `hat_ablaufplan=1`, Positionsersatz,
    Schreibrecht-Pflicht, leerer Zeilenfilter.
  * `get_termine_am_tag`: Tagesfenster, Kalender-Whitelist, Ressourcenname.
  * `get_kanban_board_data`: Spalten, Staging-Abzug, Moderationspflicht.
  * `save_staging_state` / `finalize_staged_events`: Zustand + Statuswechsel.
  * `get_conflict_partner`: Overlap-Test der Ressource.
  * `resolve_conflict`: ignore/vorschlag/festlegen.
  * `get_moderation_count`: DISTINCT ueber series_id/name.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole
from diakronos_app.models.kronos import (
    Ablaufplan,
    AblaufplanPosition,
    Element,
    Eventkategorie,
    Kalender,
    KalenderModerator,
    KronosKanbanZustand,
    Ressource,
)

ABLAUFPLAN_MODUL = "diakronos.kronos.api.ablaufplan_api"
KANBAN_MODUL = "diakronos.kronos.api.kanban_api"

ABLAUFPLAN_PFADE = ["get_ablaufplan", "save_ablaufplan", "get_termine_am_tag"]
KANBAN_PFADE = [
    "get_kanban_board_data",
    "save_staging_state",
    "finalize_staged_events",
    "get_conflict_partner",
    "resolve_conflict",
    "get_moderation_count",
]

ANNA = "anna@example.org"
MODERATOR = "moderator@example.org"
KALENDER = "KAL-GOTTESDIENST"
KAL_FREMD = "KAL-FREMD"


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Ein Kalender mit Anna als Moderatorin, Elemente, Kategorien, Ressourcen.

    Zeitbasis fix gegen `_now()`: `tag` liegt in der Zukunft.
    """
    sess = patched_db()

    tag = (datetime.now() + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    start = tag.replace(hour=10)
    ende = tag.replace(hour=12)

    sess.add_all([
        Kalender(name=KALENDER, calendar_name="Gottesdienst", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_FREMD, calendar_name="Fremd", calendar_color="#222222",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])

    # Moderatorin sein -> lesen+schreiben+moderieren in KALENDER.
    sess.add_all([
        KalenderModerator(name="KM-1", parent=KALENDER, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
    ])

    sess.add_all([
        Eventkategorie(name="EK-MIT", event_category_name="Mit Ablaufplan",
                       hat_ablaufplan=1, docstatus=0, idx=0),
        Eventkategorie(name="EK-OHNE", event_category_name="Ohne Ablaufplan",
                       hat_ablaufplan=0, docstatus=0, idx=0),
    ])

    sess.add_all([
        Ressource(name="RES-RAUM", ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, wartung=0, docstatus=0, idx=0),
    ])

    sess.add_all([
        # Element mit Ablaufplan-Kategorie, noch ohne Plan.
        Element(name="ELE-1", element_name="Gottesdienst", element_calendar=KALENDER,
                element_category="EK-MIT", status="Festgelegt",
                element_start=start, element_end=ende, all_day=0, series_id="",
                ressource="RES-RAUM", docstatus=0, idx=0),
        # Element, dessen Kategorie keinen Ablaufplan erlaubt.
        Element(name="ELE-2", element_name="Infoabend", element_calendar=KALENDER,
                element_category="EK-OHNE", status="Vorschlag",
                element_start=start, element_end=ende, all_day=0, series_id="",
                docstatus=0, idx=0),
        # Konflikt-Element, gleiche Ressource, ueberlappt ELE-1.
        Element(name="ELE-3", element_name="Konflikttermin", element_calendar=KALENDER,
                element_category="EK-MIT", status="Konflikt",
                element_start=start + timedelta(hours=1),
                element_end=ende + timedelta(hours=1), all_day=0,
                series_id="SERIE-A", ressource="RES-RAUM", docstatus=0, idx=0),
        # Zweites Element derselben Serie -> zaehlt nur einmal.
        Element(name="ELE-4", element_name="Serientermin", element_calendar=KALENDER,
                element_category="EK-MIT", status="Konflikt",
                element_start=start + timedelta(days=1),
                element_end=ende + timedelta(days=1), all_day=0,
                series_id="SERIE-A", ressource="RES-RAUM", docstatus=0, idx=0),
        # Element in einem FREMDEN Kalender -> fuer Moderatorin unsichtbar.
        Element(name="ELE-5", element_name="Fremdtermin", element_calendar=KAL_FREMD,
                element_category="EK-MIT", status="Vorschlag",
                element_start=start, element_end=ende, all_day=0, series_id="",
                docstatus=0, idx=0),
    ])

    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_moderator(welt):
    set_user(MODERATOR)
    yield MODERATOR
    set_user("Administrator")


@pytest.fixture()
def als_anna(welt):
    set_user(ANNA)
    yield ANNA
    set_user("Administrator")


# ── Registrierung / Router ──────────────────────────────────────────────────


def test_frappe_module_konstanten_gesetzt():
    from diakronos_app.api.kronos import ablaufplan_api, kanban_api

    assert ablaufplan_api.FRAPPE_MODULE == ABLAUFPLAN_MODUL
    assert kanban_api.FRAPPE_MODULE == KANBAN_MODUL


@pytest.mark.parametrize("fn", ABLAUFPLAN_PFADE)
def test_ablaufplan_spa_pfade_registriert(fn):
    assert lookup(f"{ABLAUFPLAN_MODUL}.{fn}") is not None


@pytest.mark.parametrize("fn", KANBAN_PFADE)
def test_kanban_spa_pfade_registriert(fn):
    assert lookup(f"{KANBAN_MODUL}.{fn}") is not None


@pytest.mark.parametrize("fn", ABLAUFPLAN_PFADE)
def test_guest_wird_bei_ablaufplan_abgewiesen(client, fn):
    set_user("Guest")
    try:
        r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.{fn}")
        assert r.status_code == 401, (fn, r.text)
    finally:
        set_user("Administrator")


@pytest.mark.parametrize("fn", KANBAN_PFADE)
def test_guest_wird_bei_kanban_abgewiesen(client, fn):
    set_user("Guest")
    try:
        r = client.get(f"/api/method/{KANBAN_MODUL}.{fn}")
        assert r.status_code == 401, (fn, r.text)
    finally:
        set_user("Administrator")


# ── get_ablaufplan ──────────────────────────────────────────────────────────


def test_get_ablaufplan_ohne_plan_liefert_null(client, als_moderator):
    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                   params={"element": "ELE-1"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] is None


def test_get_ablaufplan_liefert_plan_und_positionen(client, als_moderator, welt):
    ap = Ablaufplan(name="AP-1", titel="Ablauf", element="ELE-1",
                    datum=date(2026, 10, 4), notizen="Notiz", docstatus=0, idx=0)
    welt.add(ap)
    welt.add_all([
        AblaufplanPosition(name="APP-2", parent="AP-1", parenttype="Ablaufplan",
                           parentfield="positionen", bezeichnung="Zweite",
                           reihenfolge=2, idx=2, docstatus=0),
        AblaufplanPosition(name="APP-1", parent="AP-1", parenttype="Ablaufplan",
                           parentfield="positionen", bezeichnung="Erste",
                           reihenfolge=1, idx=1, docstatus=0),
    ])
    welt.commit()

    from diakronos_app.frappe_compat.api_helpers import _update_doc
    _update_doc("Element", "ELE-1", {"ablaufplan": "AP-1"})

    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                   params={"element": "ELE-1"})
    msg = r.json()["message"]
    assert msg["ablaufplan"] == "AP-1"
    assert msg["titel"] == "Ablauf"
    assert msg["notizen"] == "Notiz"
    assert [p["bezeichnung"] for p in msg["positionen"]] == ["Erste", "Zweite"]


def test_get_ablaufplan_element_fehlt(client, als_moderator):
    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                   params={"element": ""})
    assert r.status_code == 417, r.text


def test_get_ablaufplan_fremder_kalender_verboten(client, als_anna, welt):
    """Anna hat kein Leserecht auf KALENDER -> 403."""
    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                   params={"element": "ELE-1"})
    assert r.status_code == 403, r.text


# ── save_ablaufplan ─────────────────────────────────────────────────────────


def test_save_ablaufplan_legt_lazy_an_und_setzt_positionen(client, als_moderator):
    positionen = [
        {"bezeichnung": "Begruessung", "dauer_minuten": 5, "verantwortlicher": "Anna"},
        {"bezeichnung": "Predigt", "dauer_minuten": 30},
    ]
    r = client.post(f"/api/method/{ABLAUFPLAN_MODUL}.save_ablaufplan",
                    data={"element": "ELE-1", "positionen": json.dumps(positionen)})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["success"] is True
    ap_name = msg["ablaufplan"]

    # Element verknuepft?
    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Element", "ELE-1", "ablaufplan") == ap_name

    # Positionen in Reihenfolge?
    r2 = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                    params={"element": "ELE-1"})
    namen = [p["bezeichnung"] for p in r2.json()["message"]["positionen"]]
    assert namen == ["Begruessung", "Predigt"]


def test_save_ablaufplan_ohne_kategorie_recht_verboten(client, als_moderator):
    r = client.post(f"/api/method/{ABLAUFPLAN_MODUL}.save_ablaufplan",
                    data={"element": "ELE-2", "positionen": "[]"})
    assert r.status_code == 417, r.text


def test_save_ablaufplan_ueberschreibt_positionen(client, als_moderator):
    client.post(f"/api/method/{ABLAUFPLAN_MODUL}.save_ablaufplan",
                data={"element": "ELE-1",
                      "positionen": json.dumps([{"bezeichnung": "Alt"}])})
    client.post(f"/api/method/{ABLAUFPLAN_MODUL}.save_ablaufplan",
                data={"element": "ELE-1",
                      "positionen": json.dumps([{"bezeichnung": "Neu"}])})

    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                   params={"element": "ELE-1"})
    namen = [p["bezeichnung"] for p in r.json()["message"]["positionen"]]
    assert namen == ["Neu"]


def test_save_ablaufplan_filtert_leere_bezeichnungen(client, als_moderator):
    r = client.post(f"/api/method/{ABLAUFPLAN_MODUL}.save_ablaufplan",
                    data={"element": "ELE-1", "positionen": json.dumps([
                        {"bezeichnung": "  "},
                        {"bezeichnung": "Gueltig"},
                        {"keine": "bezeichnung"},
                    ])})
    assert r.status_code == 200, r.text
    r2 = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_ablaufplan",
                    params={"element": "ELE-1"})
    namen = [p["bezeichnung"] for p in r2.json()["message"]["positionen"]]
    assert namen == ["Gueltig"]


def test_save_ablaufplan_ohne_schreibrecht_verboten(client, als_anna):
    r = client.post(f"/api/method/{ABLAUFPLAN_MODUL}.save_ablaufplan",
                    data={"element": "ELE-1", "positionen": "[]"})
    assert r.status_code == 403, r.text


# ── get_termine_am_tag ──────────────────────────────────────────────────────


def test_get_termine_am_tag_nur_erlaubte_kalender(client, als_moderator):
    tag = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_termine_am_tag",
                   params={"datum": tag})
    assert r.status_code == 200, r.text
    namen = [e["name"] for e in r.json()["message"]]
    assert "ELE-1" in namen
    assert "ELE-5" not in namen  # fremder Kalender

    e1 = next(e for e in r.json()["message"] if e["name"] == "ELE-1")
    assert e1["ressource_name"] == "Gemeindesaal"
    assert e1["element_category"] == "EK-MIT"


def test_get_termine_am_tag_ohne_zugriff_leer(client, als_anna):
    tag = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_termine_am_tag",
                   params={"datum": tag, "kalender": KALENDER})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == []


def test_get_termine_am_tag_datum_fehlt(client, als_moderator):
    r = client.get(f"/api/method/{ABLAUFPLAN_MODUL}.get_termine_am_tag")
    assert r.status_code == 417, r.text


# ── get_kanban_board_data ───────────────────────────────────────────────────


def test_kanban_board_liefert_spalten(client, als_moderator):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_kanban_board_data")
    assert r.status_code == 200, r.text
    msg = r.json()["message"]

    vorschlaege = [e["id"] for e in msg["vorschlaege"]]
    konflikte = [e["id"] for e in msg["konflikte"]]

    assert "ELE-2" in vorschlaege
    assert "ELE-3" in konflikte
    assert "ELE-5" not in vorschlaege + konflikte  # fremder Kalender

    e3 = next(e for e in msg["konflikte"] if e["id"] == "ELE-3")
    assert e3["calendar_title"] == "Gottesdienst"
    assert e3["calendar_color"] == "#111111"
    assert e3["type"] == "event"
    assert e3["series_id"] == "SERIE-A"


def test_kanban_board_ohne_moderationsrechte_leer(client, als_anna):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_kanban_board_data")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {
        "vorschlaege": [], "konflikte": [], "staging": [], "notifications": {},
        # P1-5b (W-1): Moderations-Historie der abgelehnten Termine.
        "abgelehnt": [],
    }


# ── save_staging_state / finalize_staged_events ─────────────────────────────


def test_save_staging_state_legt_zustand_an(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.save_staging_state",
                    data={"staging_ids": json.dumps(["ELE-3"])})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"ok": True}

    from diakronos_app.frappe_compat.query import get_value
    staging = get_value("Kronos Kanban Zustand", {"user": MODERATOR}, "staging_events")
    assert json.loads(staging) == ["ELE-3"]


def test_staging_entfernt_aus_quellspalte(client, als_moderator):
    client.post(f"/api/method/{KANBAN_MODUL}.save_staging_state",
                data={"staging_ids": json.dumps(["ELE-3"])})
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_kanban_board_data")
    msg = r.json()["message"]
    assert [e["id"] for e in msg["staging"]] == ["ELE-3"]
    assert "ELE-3" not in [e["id"] for e in msg["konflikte"]]


def test_finalize_staged_events_setzt_status_festgelegt(client, als_moderator):
    client.post(f"/api/method/{KANBAN_MODUL}.save_staging_state",
                data={"staging_ids": json.dumps(["ELE-3"])})
    r = client.post(f"/api/method/{KANBAN_MODUL}.finalize_staged_events",
                    data={"event_ids": json.dumps(["ELE-3"])})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"finalized": 1}

    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Element", "ELE-3", "status") == "Festgelegt"

    # Staging geleert?
    staging = get_value("Kronos Kanban Zustand", {"user": MODERATOR}, "staging_events")
    assert json.loads(staging) == []


# ── get_conflict_partner ────────────────────────────────────────────────────


def test_conflict_partner_findet_ueberlappung(client, als_moderator):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_conflict_partner",
                   params={"element_id": "ELE-3"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg is not None
    assert msg["ressource"] == "RES-RAUM"
    assert msg["id"] in ("ELE-1", "ELE-4")


def test_conflict_partner_ohne_ressource_null(client, als_moderator):
    """Ganz ohne Ressource bleibt die Suche leer."""
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_conflict_partner",
                   params={"element_id": "ELE-2"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] is None


def test_conflict_partner_unbekanntes_element_null(client, als_moderator):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_conflict_partner",
                   params={"element_id": "GIBTSNICHT"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] is None


# ── resolve_conflict ────────────────────────────────────────────────────────


def test_resolve_conflict_vorschlag_setzt_status(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-3", "action": "vorschlag"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["new_status"] == "Vorschlag"
    assert msg["action"] == "vorschlag"

    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Element", "ELE-3", "status") == "Vorschlag"
    assert int(get_value("Element", "ELE-3", "ignore_conflict")) == 0


def test_resolve_conflict_ignore_setzt_ignore_flag(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-3", "action": "ignore"})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["new_status"] == "Vorschlag"

    from diakronos_app.frappe_compat.query import get_value
    assert int(get_value("Element", "ELE-3", "ignore_conflict")) == 1
    assert get_value("Element", "ELE-3", "status") == "Vorschlag"


def test_resolve_conflict_festlegen_speichert_aenderungen(client, als_moderator):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-3", "action": "festlegen",
                          "title": "Neuer Titel"})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["new_status"] == "Konflikt"

    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Element", "ELE-3", "element_name") == "Neuer Titel"


# ── get_moderation_count ────────────────────────────────────────────────────


def test_moderation_count_zaehlt_serie_einmal(client, als_moderator):
    """ELE-3 + ELE-4 teilen SERIE-A; ELE-2 ist Vorschlag -> 2 eindeutige."""
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_moderation_count")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"count": 2}


def test_moderation_count_ohne_rechte_null(client, als_anna):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_moderation_count")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"count": 0}


# ── OP-EVENT-1: Moderation/Freigabe nur mit Moderationsrecht ─────────────────
#
# Ausgangsbefund: resolve_conflict/finalize_staged_events/save_staging_state
# prueften nur "nicht Gast". Jedes angemeldete Mitglied konnte fremde Termine
# umbenennen, verschieben, freigeben und den Belegungsschutz abschalten.
# Moderation/Freigabe verlangt jetzt `is_moderator` fuer den Kalender des
# Termins (dieselbe Quelle wie das Moderationsboard).


def test_resolve_conflict_ohne_moderationsrecht_verboten(client, als_anna):
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-3", "action": "ignore",
                          "title": "(von mitglied geaendert)"})
    assert r.status_code == 403, r.text

    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Element", "ELE-3", "element_name") == "Konflikttermin"
    assert int(get_value("Element", "ELE-3", "ignore_conflict")) == 0


def test_finalize_staged_events_ohne_moderationsrecht_verboten(client, als_anna):
    r = client.post(f"/api/method/{KANBAN_MODUL}.finalize_staged_events",
                    data={"event_ids": json.dumps(["ELE-3"])})
    assert r.status_code == 403, r.text

    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Element", "ELE-3", "status") == "Konflikt"


def test_save_staging_state_ohne_moderationsrecht_verboten(client, als_anna):
    r = client.post(f"/api/method/{KANBAN_MODUL}.save_staging_state",
                    data={"staging_ids": json.dumps(["ELE-3"])})
    assert r.status_code == 403, r.text


def test_resolve_conflict_moderator_bleibt_erlaubt(client, als_moderator):
    """Gegenprobe: die Moderatorin darf weiterhin freigeben."""
    r = client.post(f"/api/method/{KANBAN_MODUL}.resolve_conflict",
                    data={"element_id": "ELE-3", "action": "vorschlag"})
    assert r.status_code == 200, r.text


# ── OP-EVENT-R1: keine Termine gesperrter Kalender in Konfliktantworten ──────


def test_conflict_partner_maskiert_fremden_kalender(client, als_anna):
    """Anna liest KALENDER nicht -> kein Titel/Kalender des Partners."""
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_conflict_partner",
                   params={"element_id": "ELE-3"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg is not None
    assert msg.get("belegt") is True
    assert msg["title"] == "Belegt"
    assert msg["calendar"] == ""
    assert "Konflikttermin" not in (msg["title"] or "")


def test_conflict_partner_mit_leserecht_zeigt_titel(client, als_moderator):
    r = client.get(f"/api/method/{KANBAN_MODUL}.get_conflict_partner",
                   params={"element_id": "ELE-3"})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["title"] in ("Gottesdienst", "Serientermin")
    assert msg["calendar"] == "Gottesdienst"
    assert msg.get("belegt") is None
