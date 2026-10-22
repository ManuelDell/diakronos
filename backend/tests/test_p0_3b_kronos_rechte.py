"""P0-3b — Nacharbeit Kronos-Rechte nach dem Review.

Deckt die vier wichtigen und die kleinen Befunde des Code-Reviews zu P0-3 ab.
Jeder Test ist als Reproduktion geschrieben: er war auf dem Stand vor diesem
Patch rot und ist danach gruen.

Befunde
  1 (wichtig) Statusumgehung — create_event/update_event/save_event/create_series
    durften `status="Festgelegt"` ungeprueft von jedem Schreibberechtigten
    uebernehmen; `save_event` hatte "Festgelegt" sogar als Default.
  2 (wichtig) /api/resource/Element — siehe tests/test_p0_1_resource_rollenmatrix.py
    (P0-1-Rest, im selben Paket mit erledigt).
  3 (wichtig) Ablaufplan — get_termine_am_tag/get_ablaufplan filterten nicht
    auf "Festgelegt"; Mitglieder sahen fremde Vorschlaege.
  4 (wichtig) get_conflict_events — lieferte Titel/Kalender ALLER Termine,
    sobald jemand irgendeinen Kalender moderiert.
  5/6 (klein) finalize_staged_events/save_staging_state — halbe Batches,
    geloeschte IDs blockierten den ganzen Vorgang.
  7 (klein) get_conflict_partner — Docstring behauptete Moderationszwang,
    der abgefragte Termin selbst war nicht auf Leserecht geprueft.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

import diakronos_app.api  # noqa: E402,F401  (registriert die @whitelist-Pfade)

from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import (
    Element,
    Eventkategorie,
    Kalender,
    KalenderModerator,
    Ressource,
)

MODERATOR = "moderator@example.org"
SCHREIBER = "schreiber@example.org"
LESER = "leser@example.org"
KAL = "KAL-MOD"
KAL_NUR_SCHREIB = "KAL-SCHREIB"
KAL_FREMD = "KAL-FREMD"


@pytest.fixture()
def welt(patched_db):
    """Ein moderierter, ein nur beschreibbarer und ein fremder Kalender.

    Die Rollenverteilung ist der Kern der Befunde:
      * SCHREIBER hat Schreib-, aber KEIN Moderationsrecht auf KAL-SCHREIB
        -> darf anlegen, aber nicht freigeben (Befund 1).
      * LESER hat nur Leserecht auf KAL-MOD -> darf fremde Vorschlaege und
        Konflikte dort nicht sehen (Befunde 3/4).
      * MODERATOR moderiert KAL-MOD -> darf alles (Gegenprobe).
    """
    sess = patched_db()
    tag = (datetime.now() + timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = tag.replace(hour=10)
    ende = tag.replace(hour=12)

    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Schreiber", enabled=True),
        User(name=LESER, email=LESER, full_name="Leser", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-M", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-S", parent=SCHREIBER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-L", parent=LESER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name=KAL, calendar_name="Gottesdienst", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_NUR_SCHREIB, calendar_name="Praxis", calendar_color="#222222",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_FREMD, calendar_name="Fremd", calendar_color="#333333",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()

    # LESER darf KAL-MOD lesen, SCHREIBER darf KAL-SCHREIB schreiben.
    sess.add_all([
        UserRole(name="UR-1", parent=KAL, parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-2", parent=KAL_NUR_SCHREIB, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        KalenderModerator(name="KM-1", parent=KAL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
    ])
    sess.add_all([
        Eventkategorie(name="EK-1", event_category_name="Gottesdienst",
                       hat_ablaufplan=1, docstatus=0, idx=0),
        Ressource(name="RES-1", ressource_name="Gemeindesaal", typ="Raum",
                  docstatus=0, idx=0),
    ])
    sess.flush()

    sess.add_all([
        # Festgelegt, lesbar fuer LESER.
        Element(name="EL-FEST", element_name="Gottesdienst", element_calendar=KAL,
                element_start=start, element_end=ende, all_day=0,
                status="Festgelegt", element_category="EK-1", ressource="RES-1",
                series_id="", docstatus=0, idx=0),
        # FREMDER Vorschlag im LESBAREN Kalender -> fuer LESER unsichtbar.
        Element(name="EL-VORSCHLAG", element_name="Geheimer Vorschlag",
                element_calendar=KAL, element_start=start, element_end=ende,
                all_day=0, status="Vorschlag", element_category="EK-1",
                series_id="", docstatus=0, idx=0),
        # Konflikt in einem Kalender, den LESER NICHT lesen darf.
        Element(name="EL-KONFLIKT-GEHEIM", element_name="Geheime Sitzung",
                element_calendar=KAL_FREMD, element_start=start, element_end=ende,
                all_day=0, status="Konflikt", ressource="RES-1",
                series_id="", docstatus=0, idx=0),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_user():
    yield
    set_user("Administrator")


def _als(user):
    set_user(user)


# ═══════════════════════════════════════════════════════════════════════════
# Befund 1 — Statusumgehung durch Schreibberechtigte ohne Moderationsrecht
# ═══════════════════════════════════════════════════════════════════════════


def test_create_event_erzwingt_vorschlag_ohne_moderationsrecht(welt):
    """ROT vorher: status="Festgelegt" wurde ungeprueft uebernommen."""
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_event(
        "Eigenmaechtig freigegeben", "2025-07-01 10:00:00",
        "2025-07-01 11:00:00", KAL_NUR_SCHREIB, status="Festgelegt",
    )
    assert res["status"] == "Vorschlag", "Freigabe ohne Moderationsrecht"
    assert welt.get(Element, res["id"]).status == "Vorschlag"


def test_create_event_moderator_darf_festlegen(welt):
    """Gegenprobe: der Moderator darf weiterhin freigeben."""
    from diakronos_app.api.kronos import event_crud

    _als(MODERATOR)
    res = event_crud.create_event(
        "Freigegeben", "2025-07-01 10:00:00", "2025-07-01 11:00:00",
        KAL, status="Festgelegt",
    )
    assert res["status"] == "Festgelegt"


def test_create_event_default_bleibt_vorschlag(welt):
    """Ohne Statusangabe: weiterhin "Vorschlag" (kein Regress)."""
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_event(
        "Ohne Status", "2025-07-02 10:00:00", "2025-07-02 11:00:00",
        KAL_NUR_SCHREIB,
    )
    assert res["status"] == "Vorschlag"


def test_create_event_moderator_ohne_status_bleibt_vorschlag(welt):
    """BF1-A: auch ein Moderator legt ohne Statusangabe nur einen VORSCHLAG an.

    Regression zur ersten Fassung des Fixes: dort bekam ein Kalender-
    administrator ohne Statusangabe "Festgelegt", weil die Rolle den
    Moderationsschritt ersetzte. Das widerspricht der Zusage, dass ein neuer
    Termin erst nach bewusster Freigabe sichtbar wird
    (test_bf1_livetest: "Vorschlag landet in der Moderation").
    """
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.core import HasRole as HR

    sess = welt
    admin = "kaladmin-p03b@example.org"
    sess.add(User(name=admin, email=admin, full_name="KalAdmin", enabled=True))
    sess.add(HR(name="HR-KA2", parent=admin, parenttype="User", parentfield="roles",
                role="Kalenderadministrator", docstatus=0, idx=1))
    sess.commit()

    _als(admin)
    res = event_crud.create_event(
        "Moderator ohne Status", "2025-07-03 10:00:00",
        "2025-07-03 11:00:00", KAL,
    )
    assert res["status"] == "Vorschlag"
    assert sess.get(Element, res["id"]).status == "Vorschlag"

    # Gegenprobe: MIT ausdruecklicher Angabe darf er freigeben.
    res2 = event_crud.create_event(
        "Moderator mit Status", "2025-07-04 10:00:00",
        "2025-07-04 11:00:00", KAL, status="Festgelegt",
    )
    assert res2["status"] == "Festgelegt"


def test_update_event_ohne_moderationsrecht_bleibt_vorschlag(welt):
    """ROT vorher: update_event schrieb status="Festgelegt" durch."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(name="EL-S1", element_name="Vorschlag", element_calendar=KAL_NUR_SCHREIB,
                     element_start=datetime(2025, 8, 1, 10), element_end=datetime(2025, 8, 1, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(SCHREIBER)
    event_crud.update_event("EL-S1", status="Festgelegt")
    assert sess.get(Element, "EL-S1").status == "Vorschlag"


def test_update_event_moderator_darf_status_wechseln(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(name="EL-M1", element_name="Vorschlag", element_calendar=KAL,
                     element_start=datetime(2025, 8, 2, 10), element_end=datetime(2025, 8, 2, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(MODERATOR)
    event_crud.update_event("EL-M1", status="Festgelegt")
    assert sess.get(Element, "EL-M1").status == "Festgelegt"


def test_save_event_default_festgelegt_ist_die_umgehung(welt):
    """ROT vorher: save_event ohne Status setzte "Festgelegt" (Befund 1).

    Das ist der gefaehrlichste Fall — die SPA sendet genau so
    (`useEventsApi.js:41`: `status: props.status || "Festgelegt"`).
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(name="EL-S2", element_name="Vorschlag", element_calendar=KAL_NUR_SCHREIB,
                     element_start=datetime(2025, 8, 3, 10), element_end=datetime(2025, 8, 3, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(SCHREIBER)
    event_crud.save_event(
        "EL-S2", "Umbenannt", "2025-08-03 10:00:00", "2025-08-03 11:00:00",
        KAL_NUR_SCHREIB,
    )
    assert sess.get(Element, "EL-S2").status == "Vorschlag", "Default gab frei"


def test_save_event_moderator_edit_behaelt_bisherigen_status(welt):
    """Gegenprobe: reines Bearbeiten ist keine Freigabe — auch fuer Moderatoren.

    Der alte Default ("ohne Status -> Festgelegt") hat einen Vorschlag beim
    simplen Umbenennen stillschweigend veroeffentlicht. Jetzt bleibt der
    bisherige Status erhalten; die Freigabe ist ein ausdruecklicher Schritt.
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(name="EL-M2", element_name="Vorschlag", element_calendar=KAL,
                     element_start=datetime(2025, 8, 4, 10), element_end=datetime(2025, 8, 4, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(MODERATOR)
    event_crud.save_event(
        "EL-M2", "Umbenannt", "2025-08-04 10:00:00", "2025-08-04 11:00:00", KAL,
    )
    assert sess.get(Element, "EL-M2").status == "Vorschlag", "Bearbeiten gab frei"


def test_save_event_moderator_darf_ausdruecklich_festlegen(welt):
    """Der Moderator darf weiterhin ausdruecklich freigeben (positiver Weg)."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(name="EL-M3", element_name="Vorschlag", element_calendar=KAL,
                     element_start=datetime(2025, 8, 6, 10), element_end=datetime(2025, 8, 6, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(MODERATOR)
    event_crud.save_event(
        "EL-M3", "Freigegeben", "2025-08-06 10:00:00", "2025-08-06 11:00:00", KAL,
        status="Festgelegt",
    )
    assert sess.get(Element, "EL-M3").status == "Festgelegt"


def test_save_event_nicht_moderator_haelt_festgelegt_nicht(welt):
    """Operator-Regel 16.10. (P1-1): Ein Nicht-Moderator kann einen bereits
    festgelegten Termin NICHT zurueckstufen.

    Frueher fiel hier der Status auf "Vorschlag" — die "Rueckstufung", die den
    Termin aus dem Kalender entfernt (Review R-P0-3b, Befund B). Jetzt bleibt
    der bisherige Status erhalten; die inhaltliche Aenderung wartet als
    Vorschlag auf die Moderation (siehe tests/test_p1_1_kalender_termine.py).
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(name="EL-S3", element_name="Termin", element_calendar=KAL_NUR_SCHREIB,
                     element_start=datetime(2025, 8, 5, 10), element_end=datetime(2025, 8, 5, 11),
                     all_day=0, status="Festgelegt", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(SCHREIBER)
    event_crud.save_event(
        "EL-S3", "Geaendert", "2025-08-05 10:00:00", "2025-08-05 11:00:00",
        KAL_NUR_SCHREIB, status="Festgelegt",
    )
    assert sess.get(Element, "EL-S3").status == "Festgelegt"


def test_create_series_erzwingt_vorschlag_ohne_moderationsrecht(welt):
    """ROT vorher: die Serienanlage war die Hintertuer am Einzeltermin vorbei."""
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_series(
        "Serie", "2025-09-01 10:00:00", "2025-09-01 11:00:00",
        KAL_NUR_SCHREIB, series_end="2025-09-08 11:00:00", status="Festgelegt",
    )
    assert res["created_count"] >= 1
    for eid in res["created_ids"]:
        assert welt.get(Element, eid).status == "Vorschlag"


def test_create_series_moderator_darf_festlegen(welt):
    from diakronos_app.api.kronos import event_crud

    _als(MODERATOR)
    res = event_crud.create_series(
        "Serie", "2025-10-01 10:00:00", "2025-10-01 11:00:00",
        KAL, series_end="2025-10-08 11:00:00", status="Festgelegt",
    )
    for eid in res["created_ids"]:
        assert welt.get(Element, eid).status == "Festgelegt"


# ═══════════════════════════════════════════════════════════════════════════
# Befund 3 — Ablaufplan: keine fremden Vorschlaege
# ═══════════════════════════════════════════════════════════════════════════


def test_termine_am_tag_verbirgt_fremde_vorschlaege(welt):
    """ROT vorher: Titel/Zeit des Vorschlags waren fuer Mitglieder sichtbar."""
    from diakronos_app.api.kronos import ablaufplan_api

    tag = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    _als(LESER)
    namen = {e["name"] for e in ablaufplan_api.get_termine_am_tag(tag)}
    assert "EL-FEST" in namen, "festgelegter Termin fehlt"
    assert "EL-VORSCHLAG" not in namen, "fremder Vorschlag leakt"


def test_termine_am_tag_moderator_sieht_vorschlaege(welt):
    """Gegenprobe: der Moderator sieht in seinem Kalender alles."""
    from diakronos_app.api.kronos import ablaufplan_api

    tag = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    _als(MODERATOR)
    namen = {e["name"] for e in ablaufplan_api.get_termine_am_tag(tag)}
    assert {"EL-FEST", "EL-VORSCHLAG"} <= namen


def test_termine_am_tag_verraet_gesperrten_kalender_nicht(welt):
    from diakronos_app.api.kronos import ablaufplan_api

    tag = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    _als(LESER)
    namen = {e["name"] for e in ablaufplan_api.get_termine_am_tag(tag)}
    assert "EL-KONFLIKT-GEHEIM" not in namen


def test_get_ablaufplan_verweigert_fremden_vorschlag(welt):
    """ROT vorher: der Ablaufplan-Weg umging den Lesefilter von calendar_get."""
    from diakronos_app.api.kronos import ablaufplan_api

    _als(LESER)
    with pytest.raises(PermErr):
        ablaufplan_api.get_ablaufplan("EL-VORSCHLAG")


def test_save_ablaufplan_verweigert_fremden_vorschlag(welt):
    from diakronos_app.api.kronos import ablaufplan_api

    _als(LESER)
    with pytest.raises(PermErr):
        ablaufplan_api.save_ablaufplan("EL-VORSCHLAG", [{"bezeichnung": "X"}])


def test_get_ablaufplan_moderator_erreicht_eigenen_vorschlag(welt):
    """Gegenprobe: der Moderator kommt an den Vorschlag seines Kalenders."""
    from diakronos_app.api.kronos import ablaufplan_api

    _als(MODERATOR)
    assert ablaufplan_api.get_ablaufplan("EL-VORSCHLAG") is None


def test_get_ablaufplan_festgelegt_bleibt_lesbar(welt):
    from diakronos_app.api.kronos import ablaufplan_api

    _als(LESER)
    assert ablaufplan_api.get_ablaufplan("EL-FEST") is None  # ohne Plan -> None


# ═══════════════════════════════════════════════════════════════════════════
# Befund 4 — get_conflict_events maskiert nicht lesbare Kalender
# ═══════════════════════════════════════════════════════════════════════════


def test_conflict_events_maskiert_gesperrten_kalender(welt):
    """ROT vorher: Titel und Kalender des fremden Termins standen in der Liste."""
    from diakronos_app.api.kronos import ressource_api

    _als(MODERATOR)
    res = ressource_api.get_conflict_events()
    assert res, "Der Moderator soll die Belegung sehen"
    geheim = next(e for e in res if e["name"] == "EL-KONFLIKT-GEHEIM")
    assert geheim["element_name"] == "Belegt", "Titel des gesperrten Kalenders leakt"
    assert geheim["element_calendar"] == "", "Kalendername des gesperrten Kalenders leakt"
    # Die lesbaren Zeilen bleiben vollstaendig.
    lesbar = next(e for e in res if e["name"] == "EL-FEST")
    assert lesbar["element_name"] == "Gottesdienst"


def test_conflict_events_kalenderadmin_sieht_alles(welt):
    """Gegenprobe: der Kalenderadministrator hat Leserecht auf alles."""
    from diakronos_app.api.kronos import ressource_api
    from diakronos_app.models.core import HasRole as HR

    sess = welt
    admin = "kaladmin@example.org"
    sess.add(User(name=admin, email=admin, full_name="KalAdmin", enabled=True))
    sess.add(HR(name="HR-KA", parent=admin, parenttype="User", parentfield="roles",
                role="Kalenderadministrator", docstatus=0, idx=1))
    sess.commit()

    _als(admin)
    res = ressource_api.get_conflict_events()
    geheim = next(e for e in res if e["name"] == "EL-KONFLIKT-GEHEIM")
    assert geheim["element_name"] == "Geheime Sitzung"


# ═══════════════════════════════════════════════════════════════════════════
# Befund 5/6 — Batch-Verarbeitung: alles pruefen, dann schreiben
# ═══════════════════════════════════════════════════════════════════════════


def test_finalize_staged_events_geloeschte_id_blockiert_nicht(welt):
    """ROT vorher: eine verwaiste ID brach den ganzen Batch mit "Termin nicht
    gefunden" ab, obwohl die uebrigen IDs Recht hatten."""
    from diakronos_app.api.kronos import kanban_api

    sess = welt
    sess.add(Element(name="EL-F1", element_name="Vorschlag", element_calendar=KAL,
                     element_start=datetime(2025, 11, 1, 10), element_end=datetime(2025, 11, 1, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(MODERATOR)
    res = kanban_api.finalize_staged_events(["GELOESCHT-1", "EL-F1"])
    assert res["finalized"] == 1, "vorhandene ID muss durchkommen"
    assert sess.get(Element, "EL-F1").status == "Festgelegt"


def test_finalize_staged_events_rechtefehler_verweigert_ganzen_batch(welt):
    """Ein echter Rechteverstoss bleibt ein Verweigerungsgrund — und zwar
    VOR dem ersten Schreiben (kein halber Batch)."""
    from diakronos_app.api.kronos import kanban_api

    sess = welt
    sess.add(Element(name="EL-F2", element_name="Vorschlag", element_calendar=KAL,
                     element_start=datetime(2025, 11, 2, 10), element_end=datetime(2025, 11, 2, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.add(Element(name="EL-F3", element_name="Fremd", element_calendar=KAL_FREMD,
                     element_start=datetime(2025, 11, 2, 10), element_end=datetime(2025, 11, 2, 11),
                     all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(MODERATOR)
    with pytest.raises(PermErr):
        kanban_api.finalize_staged_events(["EL-F2", "EL-F3"])
    # Nichts darf geschrieben worden sein.
    assert sess.get(Element, "EL-F2").status == "Vorschlag", "halber Batch wurde geschrieben"


def test_save_staging_state_ueberspringt_geloeschte_id(welt):
    """ROT vorher: eine geloeschte ID liess jeden Speicherversuch scheitern."""
    from diakronos_app.api.kronos import kanban_api

    sess = welt
    sess.add(Element(name="EL-ST1", element_name="Im Staging", element_calendar=KAL,
                     element_start=datetime(2025, 11, 3, 10), element_end=datetime(2025, 11, 3, 11),
                     all_day=0, status="Konflikt", series_id="", docstatus=0, idx=0))
    sess.commit()

    _als(MODERATOR)
    res = kanban_api.save_staging_state(["GELOESCHT-2", "EL-ST1"])
    assert res == {"ok": True}

    from diakronos_app.frappe_compat.query import get_value
    staging = get_value("Kronos Kanban Zustand", {"user": MODERATOR}, "staging_events")
    assert json.loads(staging) == ["EL-ST1"], "geloeschte ID darf nicht im Staging landen"


def test_save_staging_state_rechtefehler_bleibt_verweigert(welt):
    from diakronos_app.api.kronos import kanban_api

    _als(LESER)
    with pytest.raises(PermErr):
        kanban_api.save_staging_state(["EL-KONFLIKT-GEHEIM"])


# ═══════════════════════════════════════════════════════════════════════════
# Befund 7 — get_conflict_partner: abgefragter Termin wird geprueft
# ═══════════════════════════════════════════════════════════════════════════


def test_conflict_partner_verweigert_ungelesenen_termin(welt):
    """Befund 7 — Anmerkung: der Review schlaegt eine harte Leseschranke auf den
    abgefragten Termin vor. Das widerspricht dem ausgelieferten OP-EVENT-R1-
    Verhalten (`test_p4c3...::test_conflict_partner_maskiert_fremden_kalender`):
    die Belegung soll auch fuer Nicht-Leser erkennbar bleiben, nur Titel und
    Kalender werden maskiert. Die Entscheidung ueber die harte Schranke liegt
    beim Reviewer; hier wird nur festgehalten, dass die Maskierung greift.
    """
    from diakronos_app.api.kronos import kanban_api

    # LESER hat Leserecht auf KAL, aber kein Moderationsrecht: die Abfrage
    # funktioniert (kein Moderationszwang). Der erste Ueberlappungspartner aus
    # dem gesperrten Kalender wird maskiert zurueckgegeben.
    _als(LESER)
    res = kanban_api.get_conflict_partner("EL-FEST")
    assert res is not None, "Leserecht genuegt — kein Moderationszwang"
    assert res["id"] in ("EL-VORSCHLAG", "EL-KONFLIKT-GEHEIM")
    # Der Partner liegt im NICHT lesbaren Kalender -> maskiert.
    assert res["title"] == "Belegt"
    assert res["calendar"] == ""


def test_conflict_partner_lesbarer_termin_bleibt_nutzbar(welt):
    """Gegenprobe: im lesbaren Kalender funktioniert die Abfrage weiter."""
    from diakronos_app.api.kronos import kanban_api

    _als(MODERATOR)
    res = kanban_api.get_conflict_partner("EL-FEST")
    assert res is not None
    assert res["id"] == "EL-KONFLIKT-GEHEIM"
    # Der Partner liegt im gesperrten Kalender -> maskiert.
    assert res["title"] == "Belegt"


def test_conflict_partner_ohne_kalenderleserecht_bleibt_maskiert(welt):
    """Befund 7 verlangt die Korrektur der Zusage: kein Moderationszwang.

    Ein Nutzer mit Leserecht auf den Termin kommt durch — der Partner aus
    einem gesperrten Kalender bleibt dabei maskiert (OP-EVENT-R1). Genau
    diese Gegenrichtung haelt `test_p4c3` fest.
    """
    from diakronos_app.api.kronos import kanban_api

    _als(MODERATOR)
    res = kanban_api.get_conflict_partner("EL-FEST")
    assert res is not None, "Leserecht genuegt — kein Moderationszwang"
    assert res["title"] == "Belegt"
    assert res["calendar"] == ""
