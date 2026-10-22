"""Google event import business rules, fake HTTP only."""
import json
from datetime import datetime

import httpx
import pytest
from sqlalchemy import select

from diakronos_app.api.kronos import google_import as g
from diakronos_app.models.kronos import Element, Kalender
from test_google_oauth import PATH, configured, google, authorize


@pytest.mark.parametrize("payload", ["null", "[]", "{}", "[1]", "not-json", '[{"google_id":"id","create_new":"false"}]', '[{"google_id":"id","color":"#oops!!"}]', '[{"google_id":"id","time_filter":"invalid"}]', '[{"google_id":"id","create_new":false,"target_kalender":"missing"}]'])
def test_invalid_mappings_are_not_queued(configured, monkeypatch, payload):
    queued = []
    monkeypatch.setattr(g, "enqueue", lambda *a, **kw: queued.append(kw))
    assert configured.post(PATH + "start_import", json={"mappings_json": payload}).status_code == 417
    assert not queued


@pytest.mark.parametrize("time_filter,has_min", [("all", False), ("from_today", True), ("last_year", True), ("last_3_years", True)])
def test_time_filter_parameters(client, patched_db, monkeypatch, time_filter, has_min):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"items": []})
    monkeypatch.setattr(g, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(g, "publish_realtime", lambda *a, **kw: None)
    assert g._import_events_from_google("id", "calendar", "fake", time_filter=time_filter) == (0, 0)
    assert ("timeMin" in requests[0].url.params) == has_min


def test_worker_rechecks_roles_and_restores_context(client, patched_db, monkeypatch):
    from diakronos_app.models.core import User
    from diakronos_app.frappe_compat import session
    with patched_db.begin() as db:
        db.add(User(name="revoked@example.org", enabled=True))
    called = []
    emitted = []
    monkeypatch.setattr(g, "_get_valid_access_token", lambda: called.append(True))
    monkeypatch.setattr(g, "publish_realtime", lambda event, data, **kw: emitted.append(data))
    previous = session.user
    g._do_import([{"google_id": "id"}], "revoked@example.org")
    assert session.user == previous
    assert not called
    assert emitted[-1]["status"] == "done" and emitted[-1]["error"]


@pytest.mark.parametrize("event", [
    {}, {"id": "x", "start": {"dateTime": "invalid"}},
    {"id": "x", "start": {"date": "2026-10-03"}, "end": {"date": "2026-10-01"}},
    {"id": "x", "start": {"dateTime": "2026-10-01T10:00:00", "timeZone": "Invalid/Zone"}},
])
def test_invalid_google_events_skipped(event):
    assert g._map_google_event(event, "calendar") is None


def test_start_import_uses_consumed_queue(configured, google, monkeypatch):
    state = authorize(configured)
    configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
    jobs = []
    monkeypatch.setattr(g, "enqueue", lambda *args, **kwargs: jobs.append((args, kwargs)))
    response = configured.post(PATH + "start_import", json={"mappings_json": json.dumps([
        {"google_id": "id", "google_name": "Fake", "create_new": True},
    ])})
    assert response.status_code == 200
    assert response.json()["message"]["queued"]
    assert jobs[0][1]["queue"] == "default"
    assert jobs[0][1]["user"] == "Administrator"
    assert jobs[0][0][0] is g._do_import


def test_import_pages_cancelled_dedupe_and_local_times(client, patched_db, monkeypatch):
    emitted = []
    monkeypatch.setattr(g, "publish_realtime", lambda event, data, **kw: emitted.append((event, data, kw)))
    monkeypatch.setattr(g, "_get_valid_access_token", lambda: "fake-access")
    def handle(request):
        assert request.url.raw_path.split(b"?")[0].endswith(b"/calendars/a%2Fb%40example/events")
        assert request.url.params["singleEvents"] == "true"
        assert request.url.params.get("timeMin")
        if request.url.params.get("pageToken"):
            return httpx.Response(200, json={"items": [
                {"id": "day", "start": {"date": "2026-10-01"}, "end": {"date": "2026-10-03"}},
                {"id": "cancelled", "status": "cancelled"},
            ]})
        return httpx.Response(200, json={"nextPageToken": "next", "items": [
            {"id": "time", "summary": "Test", "start": {"dateTime": "2026-10-01T09:00:00Z"}, "end": {"dateTime": "2026-10-01T10:00:00Z"}},
        ]})
    monkeypatch.setattr(g, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(handle)))
    mapping = {"google_id": "a/b@example", "google_name": "Fake", "create_new": True, "time_filter": "last_year"}
    g._do_import([mapping], "Administrator")
    with patched_db() as db:
        events = db.scalars(select(Element).order_by(Element.element_start)).all()
        assert len(events) == 2
        assert events[0].all_day and events[0].element_end == datetime(2026, 10, 3)
        assert events[1].element_start == datetime(2026, 10, 1, 11)
        assert all(e.owner == "Administrator" for e in events)
        target = events[0].element_calendar
    g._do_import([{**mapping, "create_new": False, "target_kalender": target}], "Administrator")
    assert emitted[-1][1]["total_imported"] == 0
    assert emitted[-1][1]["total_skipped"] == 3
    assert all(e[0] == "gcal_import_progress" and e[2] == {"user": "Administrator"} for e in emitted)


@pytest.mark.parametrize("status", [401, 403, 429])
def test_failed_page_rolls_back_calendar(client, patched_db, monkeypatch, status):
    monkeypatch.setattr(g, "_get_valid_access_token", lambda: "fake-access")
    monkeypatch.setattr(g, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, text="sensitive-google-body"))))
    emitted = []
    monkeypatch.setattr(g, "publish_realtime", lambda event, data, **kw: emitted.append(data))
    g._do_import([{"google_id": "id", "google_name": "Fake", "create_new": True}], "Administrator")
    with patched_db() as db:
        assert not db.scalars(select(Kalender)).all()
        assert not db.scalars(select(Element)).all()
    assert emitted[-1]["status"] == "done" and emitted[-1]["error"]
    assert "sensitive-google-body" not in json.dumps(emitted)
