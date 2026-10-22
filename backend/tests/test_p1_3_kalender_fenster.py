"""P1-3 — Kalender: Fenster-Filter (Ueberlappung) und Historie.

Jeder Test hier ist einem Befund des Nachtberichts zugeordnet und prueft die
BEHEBUNG, nicht die Fehlerbeschreibung. Vorher-rot/nachher-gruen ist in den
Test-Docstrings jeweils benannt.

Befunde in dieser Datei:
  BLD-R6   Mehrtägige/ganztägige Termine verschwinden in Monats- und
           Tagesansicht (Containment- statt Ueberlappungsfilter)
  BF1b-W5  Der Fensterfilter liegt jetzt VOLLSTAENDIG in SQL (vorher lud jeder
           Kalenderaufruf die gesamte Termin-Historie) und die Serien-Anzahl
           kommt aus EINER Abfrage
  BLD-R5   Serien-Endpunkte mit nicht-ISO-Datum liefern 417 statt HTTP 500
"""
from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.kronos import Element

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren laufen beim Import

# Kalenderwelt (Kalender, Rollen) — dieselbe echte DB-Welt wie in BF1c.
from test_p4b_kronos_kern import kalenderwelt  # noqa: E402,F401

KAL_PFAD = "/api/method/diakronos.kronos.api.calendar_get."
SERIE_PFAD = "/api/method/diakronos.kronos.api.series."


@pytest.fixture()
def fensterwelt(kalenderwelt):
    """Termine ueber die Fenstergrenzen (Oktober 2026) hinweg."""
    sess = kalenderwelt
    sess.add_all([
        # Ueberlappt BEIDE Fenstergrenzen: 30.10. – 02.11.
        Element(name="EL-MONAT", element_name="Mehrtaegig Monatswechsel",
                element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 30, 9, 0),
                element_end=datetime(2026, 11, 2, 17, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=0),
        # Ganztags mit FullCalendar-Konvention „Ende = Folgetag 00:00“.
        Element(name="EL-GANZ", element_name="Ganztags 28.",
                element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 28, 0, 0),
                element_end=datetime(2026, 10, 29, 0, 0),
                all_day=True, status="Festgelegt", docstatus=0, idx=1),
        # Punkttermin OHNE Ende — darf nicht aus dem Fenster fallen.
        Element(name="EL-PUNKT", element_name="Punkttermin",
                element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 12, 9, 0),
                element_end=None,
                all_day=False, status="Festgelegt", docstatus=0, idx=2),
        # Weit vor dem Fenster: darf nicht mehr geladen werden (W5).
        Element(name="EL-ALT", element_name="Alt",
                element_calendar="KAL-PUB",
                element_start=datetime(2001, 1, 1, 10, 0),
                element_end=datetime(2001, 1, 1, 11, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=3),
        # Endet VOR dem Fensterbeginn -> kein Kontakt.
        Element(name="EL-VOR", element_name="Vor",
                element_calendar="KAL-PUB",
                element_start=datetime(2026, 9, 20, 10, 0),
                element_end=datetime(2026, 9, 20, 11, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=4),
    ])
    sess.commit()
    return sess


def _ids(client, start, ende):
    r = client.post(KAL_PFAD + "get_calendar_events",
                    json={"start_date": start, "end_date": ende,
                          "calendar_filter": '["KAL-PUB"]'})
    assert r.status_code == 200, r.text
    return {e["id"] for e in r.json()["message"]}


# ── BLD-R6: Ueberlappung statt Containment ─────────────────────────────────


def test_r6_mehrtaegig_ueber_monatsgrenze_in_beiden_monaten(client, kalenderwelt, fensterwelt):
    """BLD-R6: Der Termin 30.10.–02.11. lag in KEINER Ansicht (weder Start noch
    Ende lagen vollstaendig im Fenster). Er muss in Oktober UND November und
    an einem Tag mitten drin erscheinen."""
    set_user("admin-kal@example.org")
    assert "EL-MONAT" in _ids(client, "2026-10-01", "2026-10-31"), \
        "Termin fehlt in der Oktober-Ansicht."
    assert "EL-MONAT" in _ids(client, "2026-11-01", "2026-11-30"), \
        "Termin fehlt in der November-Ansicht."
    assert "EL-MONAT" in _ids(client, "2026-11-01", "2026-11-01"), \
        "Termin fehlt im Tagesfenster des 01.11. (Tages-Popup)."


def test_r6_ganztags_mit_folgetag_null_uhr_am_selben_tag(client, kalenderwelt, fensterwelt):
    """BLD-R6: Ein ganztägiger Termin mit Ende = Folgetag 00:00 fehlte in der
    Tagesabfrage genau dieses Tages."""
    set_user("admin-kal@example.org")
    assert "EL-GANZ" in _ids(client, "2026-10-28", "2026-10-28")
    # Am Folgetag selbst laeuft er nicht mehr (Mitternachtsende ist exklusiv).
    assert "EL-GANZ" not in _ids(client, "2026-10-29", "2026-10-29")


def test_r6_punkttermin_ohne_ende_bleibt_sichtbar(client, kalenderwelt, fensterwelt):
    """BLD-R6: Ein Termin OHNE Ende ist ein Punkttermin — die Ueberlappung darf
    ihn nicht wegschneiden (er darf nur ueber seinen Start verglichen werden)."""
    set_user("admin-kal@example.org")
    assert "EL-PUNKT" in _ids(client, "2026-10-01", "2026-10-31")
    assert "EL-PUNKT" in _ids(client, "2026-10-12", "2026-10-12")


def test_r6_termine_ausserhalb_des_fensters_bleiben_draussen(client, kalenderwelt, fensterwelt):
    """BLD-R6 (Gegenprobe): Die Ueberlappung darf nicht zu weit greifen."""
    set_user("admin-kal@example.org")
    ids = _ids(client, "2026-10-01", "2026-10-31")
    assert "EL-ALT" not in ids
    assert "EL-VOR" not in ids


# ── BF1b-W5: Fensterfilter vollstaendig in SQL, Serien-Anzahl in EINER Abfrage ──


def test_w5_sql_filter_laedt_keine_termine_aus_der_historie(client, kalenderwelt, fensterwelt, monkeypatch):
    """BF1b-W5: Die untere Zeitgrenze muss in SQL stehen. Ohne sie laedt jeder
    Kalenderaufruf die gesamte Termin-Historie bis zum Fensterende."""
    set_user("admin-kal@example.org")
    from diakronos_app.api.kronos import calendar_get as cg

    gelesene_ids: list[str] = []
    echtes_get_all = cg.get_all

    def beobachtend(doctype, **kwargs):
        zeilen = echtes_get_all(doctype, **kwargs)
        if doctype == "Element":
            gelesene_ids.extend(str(z.get("name")) for z in (zeilen or []))
        return zeilen

    monkeypatch.setattr(cg, "get_all", beobachtend)
    _ids(client, "2026-10-01", "2026-10-31")
    assert "EL-ALT" not in gelesene_ids, (
        "Kalenderabfrage laedt die Historie vor dem Fenster — die SQL-Grenze fehlt."
    )
    assert "EL-VOR" not in gelesene_ids, "Termin vor dem Fenster wurde geladen."


def test_w5_serienanzahl_kommt_aus_einer_abfrage(client, kalenderwelt, monkeypatch):
    """BF1b-W5: Die Serien-Anzahl wurde je Serie mit einer EIGENEN Abfrage
    ermittelt. Jetzt holt der Kalender alle Serientermine in einem Zug."""
    sess = kalenderwelt
    sess.add_all([
        Element(name="S1-1", element_name="Serie 1 a", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 6, 9, 0),
                element_end=datetime(2026, 10, 6, 10, 0), all_day=False,
                status="Festgelegt", series_id="SERIE-1", docstatus=0, idx=0),
        Element(name="S1-2", element_name="Serie 1 b", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 13, 9, 0),
                element_end=datetime(2026, 10, 13, 10, 0), all_day=False,
                status="Festgelegt", series_id="SERIE-1", docstatus=0, idx=0),
        Element(name="S2-1", element_name="Serie 2 a", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 7, 9, 0),
                element_end=datetime(2026, 10, 7, 10, 0), all_day=False,
                status="Festgelegt", series_id="SERIE-2", docstatus=0, idx=0),
    ])
    sess.commit()

    set_user("admin-kal@example.org")
    from diakronos_app.api.kronos import calendar_get as cg

    element_abfragen: list[dict] = []
    echtes_get_all = cg.get_all

    def beobachtend(doctype, **kwargs):
        if doctype == "Element":
            element_abfragen.append(kwargs)
        return echtes_get_all(doctype, **kwargs)

    monkeypatch.setattr(cg, "get_all", beobachtend)
    r = client.post(KAL_PFAD + "get_calendar_events",
                    json={"start_date": "2026-10-01", "end_date": "2026-10-31",
                          "calendar_filter": '["KAL-PUB"]'})
    assert r.status_code == 200, r.text
    events = {e["id"]: e for e in r.json()["message"]}
    assert events["S1-1"]["extendedProps"]["series_count"] == 2, "Seriengroesse falsch."
    assert events["S2-1"]["extendedProps"]["series_count"] == 1, "Seriengroesse falsch."

    serien_abfragen = [
        a for a in element_abfragen
        if isinstance(a.get("filters"), dict) and "series_id" in a["filters"]
    ]
    assert len(serien_abfragen) == 1, (
        f"Die Serien-Anzahl wurde in {len(serien_abfragen)} Abfragen geholt "
        "(erwartet: genau 1)."
    )
    assert serien_abfragen[0]["filters"]["series_id"] == ["in", ["SERIE-1", "SERIE-2"]]


@pytest.fixture()
def serienwelt(kalenderwelt):
    """Eine kleine Serie im Kalender (fuer die Loesch-Endpunkte)."""
    sess = kalenderwelt
    sess.add_all([
        Element(name="SR-1", element_name="Serie 1 a", element_calendar="KAL-PUB",
                element_start=datetime(2026, 11, 8, 10, 0),
                element_end=datetime(2026, 11, 8, 11, 0), all_day=False,
                status="Festgelegt", series_id="SERIE-1", docstatus=0, idx=0),
        Element(name="SR-2", element_name="Serie 1 b", element_calendar="KAL-PUB",
                element_start=datetime(2026, 11, 15, 10, 0),
                element_end=datetime(2026, 11, 15, 11, 0), all_day=False,
                status="Festgelegt", series_id="SERIE-1", docstatus=0, idx=0),
    ])
    sess.commit()
    return sess


# ── BLD-R5: Serien-Endpunkte mit nicht-ISO-Datum ───────────────────────────


def test_r5_nicht_iso_startdatum_liefert_417_statt_500(client, kalenderwelt, serienwelt):
    """BLD-R5: `from_date` lief ungeprueft in die SQL-Abfrage; PostgreSQL kann
    `timestamp >= varchar` nicht casten -> unbehandelter 500er. Jetzt 417 mit
    verstaendlicher Meldung.

    Vorher-rot (HEAD-Stand, PostgreSQL): HTTP 500 + Logzeile
    „operator does not exist: timestamp without time zone >= character varying“.
    """
    set_user("admin-kal@example.org")
    r = client.post(SERIE_PFAD + "delete_future_series_events",
                    json={"series_id": "SERIE-1", "from_date": "08.11.2026"})
    assert r.status_code == 417, f"Erwartet 417, bekam {r.status_code}: {r.text}"
    assert "JJJJ-MM-TT" in r.text


def test_r5_iso_zeitstempel_wird_auf_den_tag_gekuerzt(client, kalenderwelt):
    """BLD-R5: Ein Zeitstempel ist als Startdatum zulaessig (die SPA sendete
    frueher genau das) — er wird auf den Tag gekuerzt.

    Vorher-rot: `_series_datum` gab es nicht, der Zeitstempel lief roh in die
    Abfrage."""
    from diakronos_app.api.kronos.series import _series_datum

    assert _series_datum("2026-11-08 10:00:00", "Startdatum") == "2026-11-08"
    assert _series_datum("2026-11-08T10:00:00", "Startdatum") == "2026-11-08"
    assert _series_datum(" 2026-11-08 ", "Startdatum") == "2026-11-08"


def test_r5_leeres_und_kaputtes_datum_werden_abgelehnt(client, kalenderwelt, serienwelt):
    set_user("admin-kal@example.org")
    for wert in ("", "kein-datum", "2026-13-99"):
        r = client.post(SERIE_PFAD + "delete_future_series_events",
                        json={"series_id": "SERIE-1", "from_date": wert})
        assert r.status_code == 417, f"{wert!r}: erwartet 417, bekam {r.status_code}: {r.text}"


def test_r5_leere_serien_kennung_loescht_keine_einzeltermine(client, kalenderwelt):
    """BLD-R5: Ein leeres Serien-Id ist keine Serie. Frueher lief der Aufruf
    weiter und die Abfrage `series_id = NULL` traf JEDEN Termin ohne Serie —
    ein versehentlicher Aufruf haette alle Einzeltermine geloescht."""
    sess = kalenderwelt
    sess.add(Element(name="EL-EINZEL", element_name="Einzeltermin",
                     element_calendar="KAL-PUB",
                     element_start=datetime(2026, 10, 5, 9, 0),
                     element_end=datetime(2026, 10, 5, 10, 0),
                     all_day=False, status="Festgelegt", docstatus=0, idx=0))
    sess.commit()

    set_user("admin-kal@example.org")
    with pytest.raises(ValidationError):
        from diakronos_app.api.kronos.series import delete_series_batch_fast

        delete_series_batch_fast("null")

    from diakronos_app.frappe_compat.api_helpers import get_all

    assert get_all("Element", filters={"name": "EL-EINZEL"}, fields=["name"]), \
        "Der Einzeltermin wurde geloescht — der Aufruf haette ihn ueberleben muessen."
