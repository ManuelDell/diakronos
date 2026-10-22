"""G1a: original HTTP paths, isolated DB/Redis; no Google network calls."""
import base64
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import select

from diakronos_app.models.kronos import GoogleKalenderEinstellungen

PATH = "/api/method/diakronos.kronos.api.google_import."


def test_empty_credentials_status(client):
    response = client.get(PATH + "get_credentials_status")
    assert response.status_code == 200
    assert response.json()["message"] == {
        "configured": False, "authorized": False, "redirect_uri": ""
    }


@pytest.mark.parametrize("endpoint", ["get_credentials_status", "save_credentials", "upload_ical"])
def test_guest_denied(guest_client, endpoint):
    assert guest_client.get(PATH + endpoint).status_code == 401


@pytest.mark.parametrize("endpoint", ["get_credentials_status", "save_credentials", "upload_ical"])
def test_nonadmin_denied(client, set_user, endpoint):
    set_user("unknown@example.org")
    assert client.get(PATH + endpoint).status_code == 403


def test_save_encrypted_credentials(client, patched_db):
    response = client.post(PATH + "save_credentials", json={
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "test-secret-" * 30,
    })
    assert response.status_code == 200
    assert response.json()["message"] == {
        "success": True, "redirect_uri": "http://testserver/google-calendar-callback"
    }
    with patched_db() as db:
        row = db.scalar(select(GoogleKalenderEinstellungen))
        assert row.client_secret.startswith("fernet:v1:")
        assert "test-secret" not in row.client_secret
        from diakronos_app.google_secrets import decrypt_secret, encrypt_secret
        assert decrypt_secret(row.client_secret) == "test-secret-" * 30
        row.authorized = True
        row.token_data = encrypt_secret('{"access_token":"test-token"}')
        db.commit()
    status = client.get(PATH + "get_credentials_status")
    assert status.json()["message"]["authorized"] is True
    assert "test-secret" not in status.text and "test-token" not in status.text
    client.post(PATH + "save_credentials", json={"client_id": "new", "client_secret": "new"})
    with patched_db() as db:
        row = db.scalar(select(GoogleKalenderEinstellungen))
        assert not row.authorized and not row.token_data


@pytest.mark.parametrize("method,suffix", [
    ("get", ""), ("get", "/Google Kalender Einstellungen"),
    ("post", ""), ("put", "/Google Kalender Einstellungen"),
    ("delete", "/Google Kalender Einstellungen"),
])
def test_settings_never_accessible_as_resource(client, method, suffix):
    response = getattr(client, method)("/api/resource/Google Kalender Einstellungen" + suffix)
    assert response.status_code == 403


def test_encryption_wrong_key_and_plaintext_rejected(monkeypatch):
    from diakronos_app.google_secrets import decrypt_secret, encrypt_secret
    from diakronos_app.settings import settings
    from diakronos_app.frappe_compat.exceptions import ValidationError
    encrypted = encrypt_secret("test-sensitive-value")
    monkeypatch.setattr(settings, "secret_key", "another-isolated-test-key")
    for value in [encrypted, "plaintext", "fernet:v1:broken"]:
        with pytest.raises(ValidationError, match="entschluesselt"):
            decrypt_secret(value)


ICS = (Path(__file__).parent / "fixtures/google_import.ics").read_bytes()


def upload(client, data=ICS, **kwargs):
    return client.post(PATH + "upload_ical", json={
        "file_content_b64": base64.b64encode(data).decode(), **kwargs,
    })


def test_real_ics_new_calendar_events_and_duplicate_import(client, patched_db):
    from diakronos_app.models.kronos import Element, Kalender
    from diakronos_app.models.core import UserRole
    response = upload(client, calendar_name_new="Importprüfung")
    assert response.status_code == 200
    result = response.json()["message"]
    assert result["imported"] == 5 and result["skipped"] == 0
    calendar = result["kalender"]
    with patched_db() as db:
        rows = db.scalars(select(Element).order_by(Element.element_start)).all()
        assert len(rows) == 5
        assert rows[0].element_name == "Frühstück, Grüße"
        assert rows[0].description == "Erste Zeile\nZweite Zeile"
        assert rows[0].element_start == datetime(2026, 10, 1, 11)
        assert rows[1].all_day and rows[1].element_end == datetime(2026, 10, 3)
        assert rows[2].element_start == datetime(2026, 10, 5, 18)  # Local calendar wall time
        assert len({r.google_event_id for r in rows}) == 5
        assert all(r.status == "Festgelegt" and r.element_calendar == calendar for r in rows)
        assert db.get(Kalender, calendar).calendar_name == "Importprüfung"
        roles = db.scalars(select(UserRole.role).where(UserRole.parent == calendar)).all()
        assert set(roles) == {"Administrator", "Kalenderadministrator"}
    again = upload(client, create_new="false", target_kalender=calendar)
    assert again.json()["message"] == {
        "success": True, "imported": 0, "skipped": 5, "kalender": calendar,
    }
    with patched_db() as db:
        assert len(db.scalars(select(Kalender)).all()) == 1


@pytest.mark.parametrize("start,end,rule,expected", [
    (";TZID=Europe/Berlin:20261005T180000", ";TZID=Europe/Berlin:20261005T190000", "",
     [("2026-10-05 18:00:00", "2026-10-05 19:00:00")]),
    (":20261005T160000Z", ":20261005T170000Z", "",
     [("2026-10-05 18:00:00", "2026-10-05 19:00:00")]),
    (";TZID=America/New_York:20261005T120000", ";TZID=America/New_York:20261005T130000", "",
     [("2026-10-05 18:00:00", "2026-10-05 19:00:00")]),
    (";TZID=Europe/Berlin:20261018T180000", ";TZID=Europe/Berlin:20261018T190000",
     "RRULE:FREQ=WEEKLY;COUNT=3\n",
     [("2026-10-18 18:00:00", "2026-10-18 19:00:00"),
      ("2026-10-25 18:00:00", "2026-10-25 19:00:00"),
      ("2026-11-01 18:00:00", "2026-11-01 19:00:00")]),
    (":20261018T160000Z", ":20261018T170000Z", "RRULE:FREQ=WEEKLY;COUNT=3\n",
     [("2026-10-18 18:00:00", "2026-10-18 19:00:00"),
      ("2026-10-25 17:00:00", "2026-10-25 18:00:00"),
      ("2026-11-01 17:00:00", "2026-11-01 18:00:00")]),
    (":20261005T180000", ":20261005T190000", "",
     [("2026-10-05 18:00:00", "2026-10-05 19:00:00")]),
    (";VALUE=DATE:20261005", ";VALUE=DATE:20261006", "",
     [("2026-10-05 00:00:00", "2026-10-06 00:00:00")]),
])
def test_import_calendar_read_preserves_local_display_time(client, patched_db, start, end, rule, expected):
    from diakronos_app.api.kronos.event_crud import parse_iso_datetime_raw
    from diakronos_app.models.kronos import Element
    data = ("BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:time-contract\n"
            f"DTSTART{start}\nDTEND{end}\n{rule}SUMMARY:Time contract\n"
            "END:VEVENT\nEND:VCALENDAR\n").encode()
    response = upload(client, data)
    assert response.status_code == 200
    calendar = response.json()["message"]["kalender"]
    # An existing manually created local event must not be changed or suffixed Z.
    with patched_db.begin() as db:
        db.add(Element(name="manual-local", element_name="Manual local", status="Festgelegt",
                       element_calendar=calendar, element_start=datetime(2026, 10, 5, 18),
                       element_end=datetime(2026, 10, 5, 19)))
    response = client.get("/api/method/diakronos.kronos.api.calendar_get.get_calendar_events",
                          params={"start_date": "2026-10-01", "end_date": "2026-11-02"})
    assert response.status_code == 200
    events = response.json()["message"]
    imported = sorted((e["start"], e["end"]) for e in events if e["title"] == "Time contract")
    assert imported == expected
    for event in events:
        # Vue/FullCalendar treat these offsetless values as browser-local wall times.
        assert event["start"] == event["extendedProps"]["element_start"]
        assert datetime.fromisoformat(event["start"]).tzinfo is None
    manual = next(e for e in events if e["id"] == "manual-local")
    assert manual["start"] == parse_iso_datetime_raw("2026-10-05T18:00:00+02:00")


@pytest.mark.parametrize("zone,hour", [("Europe/Berlin", 18), ("UTC", 16), ("America/New_York", 12)])
def test_import_uses_configured_calendar_zone(client, monkeypatch, zone, hour):
    from diakronos_app.settings import Settings, settings
    monkeypatch.setenv("CALENDAR_TIMEZONE", zone)
    configured = Settings(_env_file=None)
    assert configured.calendar_timezone == zone
    monkeypatch.setattr(settings, "calendar_timezone", configured.calendar_timezone)
    data = b"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:configured-zone\nDTSTART:20261005T160000Z\nSUMMARY:Configured zone\nEND:VEVENT\nEND:VCALENDAR\n"
    assert upload(client, data).status_code == 200
    response = client.get("/api/method/diakronos.kronos.api.calendar_get.get_calendar_events",
                          params={"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert response.status_code == 200
    assert response.json()["message"][0]["start"] == f"2026-10-05 {hour:02d}:00:00"


@pytest.mark.parametrize("zone", ["", "Not/AZone", "/etc/localtime"])
def test_invalid_calendar_timezone_fails_at_configuration(monkeypatch, zone):
    from pydantic import ValidationError
    from diakronos_app.settings import Settings
    monkeypatch.setenv("CALENDAR_TIMEZONE", zone)
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        Settings(_env_file=None)


def test_duplicate_uid_allowed_in_different_calendar(client):
    first = upload(client, calendar_name_new="Same")
    second = upload(client, calendar_name_new="Same")
    assert second.json()["message"]["imported"] == 5
    assert first.json()["message"]["kalender"] != second.json()["message"]["kalender"]


@pytest.mark.parametrize("data", [
    b"not a calendar", b"<svg></svg>", b"BEGIN:VCALENDAR\nEND:VCALENDAR",
    ICS.replace(b"END:VCALENDAR", b""), ICS.replace(b"20261001T090000Z", b"invalid"),
    ICS.replace(b"COUNT=3", b"COUNT=10001"), ICS.replace(b"COUNT=3", b"COUNT=0"),
    b"\xff" + ICS,
])
def test_bad_ics_no_partial_writes(client, patched_db, data):
    from diakronos_app.models.kronos import Element, Kalender
    assert upload(client, data).status_code == 417
    with patched_db() as db:
        assert not db.scalars(select(Element)).all()
        assert not db.scalars(select(Kalender)).all()


@pytest.mark.parametrize("value", [None, 123, [], "%%%%", "data:text/calendar;base64,AAAA"])
def test_invalid_base64(client, value):
    response = client.post(PATH + "upload_ical", json={"file_content_b64": value})
    assert response.status_code == 417


def test_upload_size_limit(client, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    assert upload(client).status_code == 417


def test_missing_existing_calendar_rejected(client):
    assert upload(client, create_new=False, target_kalender="missing").status_code == 404
    assert upload(client, create_new=False).status_code == 417


@pytest.mark.parametrize("role", ["System Manager", "Mitgliederadministrator", "Kalenderadministrator"])
def test_allowed_roles(client, set_user, patched_db, role):
    from diakronos_app.models.core import HasRole
    with patched_db() as db:
        db.add(HasRole(name="test-role", parent="importer", role=role))
        db.commit()
    set_user("importer")
    assert client.get(PATH + "get_credentials_status").status_code == 200
    assert upload(client).status_code == 200


def test_generic_insert_cannot_store_plaintext(client, patched_db, set_user):
    from diakronos_app.models.core import HasRole
    with patched_db() as db:
        db.add(HasRole(name="insert-admin", parent="importer", role="System Manager"))
        db.commit()
    set_user("importer")
    response = client.post("/api/method/frappe.client.insert", json={"doc": {
        "doctype": "Google Kalender Einstellungen", "name": "bypass",
        "client_secret": "test-plaintext-bypass",
    }})
    assert response.status_code == 403
    assert "test-plaintext-bypass" not in response.text
    with patched_db() as db:
        assert not db.scalars(select(GoogleKalenderEinstellungen)).all()


def test_occurrence_limit_is_checked_before_exdates(client):
    data = b"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT" + ICS.split(b"BEGIN:VEVENT")[3]
    data = data.replace(b"FREQ=WEEKLY;COUNT=3", b"FREQ=DAILY;UNTIL=20551201T000000Z\nEXDATE;TZID=Europe/Berlin:20261005T180000")
    assert upload(client, data).status_code == 417


@pytest.mark.parametrize("uri", ["https://[bad/google-calendar-callback", "javascript:alert(1)",
                                "https://user:password@example.org/google-calendar-callback"])
def test_invalid_redirect_is_sanitized(client, uri):
    response = client.post(PATH + "save_credentials", json={
        "client_id": "test-client", "client_secret": "test-sensitive-redirect", "redirect_uri": uri,
    })
    assert response.status_code == 417
    assert "test-sensitive-redirect" not in response.text


def test_duration_folded_text_and_exdate(client, patched_db):
    from diakronos_app.models.kronos import Element
    data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:folded-series
DTSTART:20261001T090000Z
DURATION:PT1H
RRULE:FREQ=DAILY;COUNT=3
EXDATE:20261002T090000Z
SUMMARY:Long
  folded
END:VEVENT
END:VCALENDAR
"""
    result = upload(client, data)
    assert result.json()["message"]["imported"] == 2
    with patched_db() as db:
        rows = db.scalars(select(Element).order_by(Element.element_start)).all()
        assert rows[0].element_name == "Long folded"
        assert rows[0].element_end == datetime(2026, 10, 1, 12)
        assert rows[1].element_start == datetime(2026, 10, 3, 11)


def test_all_day_without_end_defaults_to_next_day(client, patched_db):
    from diakronos_app.models.kronos import Element
    data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:date-series
DTSTART;VALUE=DATE:20261001
RRULE:FREQ=DAILY;UNTIL=20261003
SUMMARY:All day series
END:VEVENT
END:VCALENDAR
"""
    response = upload(client, data)
    assert response.json()["message"]["imported"] == 3
    with patched_db() as db:
        rows = db.scalars(select(Element).order_by(Element.element_start)).all()
        assert all(row.all_day for row in rows)
        assert rows[0].element_end == datetime(2026, 10, 2)


@pytest.mark.parametrize("kwargs", [
    {"color": "not-color"}, {"calendar_name_new": "x" * 131},
    {"create_new": "not-bool"}, {"target_kalender": []},
])
def test_invalid_calendar_args(client, kwargs):
    assert upload(client, **kwargs).status_code == 417


def test_import_transaction_rolls_back_on_write_error(client, patched_db, monkeypatch):
    from diakronos_app.api.kronos import google_import
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.models.kronos import Element, Kalender
    create = google_import._create_element_from_dict
    count = 0
    def failing(fields, db):
        nonlocal count
        count += 1
        if count == 2:
            raise ValidationError("test write failed")
        create(fields, db)
    monkeypatch.setattr(google_import, "_create_element_from_dict", failing)
    assert upload(client).status_code == 417
    with patched_db() as db:
        assert not db.scalars(select(Element)).all()
        assert not db.scalars(select(Kalender)).all()


def test_insecure_default_key_rejected(client, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "secret_key", "insecure-dev-key")
    response = client.post(PATH + "save_credentials", json={
        "client_id": "test-id", "client_secret": "test-private-value",
    })
    assert response.status_code == 417 and "test-private-value" not in response.text


@pytest.mark.parametrize("interval", ["0", "-1"])
def test_invalid_rrule_interval_rejected(client, interval):
    assert upload(client, ICS.replace(b"COUNT=3", b"COUNT=3;INTERVAL=" + interval.encode())).status_code == 417


def test_element_helper_accepts_original_frappe_datetime_fields(patched_db, set_user):
    from diakronos_app.api.kronos.google_import import _create_element_from_dict
    from diakronos_app.models.kronos import Element
    set_user("Administrator")
    _create_element_from_dict({
        "element_name": "Google mapped event", "element_start": "2026-10-01 09:00:00",
        "element_end": "2026-10-01 10:00:00", "all_day": 0,
    })
    with patched_db() as db:
        assert db.scalar(select(Element)).element_start == datetime(2026, 10, 1, 9)
