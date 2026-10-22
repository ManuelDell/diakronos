"""G1b OAuth: real private Redis, HTTP MockTransport, disposable SQLite."""
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from redis import Redis

from diakronos_app.api.kronos import google_import as g
from diakronos_app.google_secrets import decrypt_secret
from diakronos_app.models.kronos import GoogleKalenderEinstellungen
from diakronos_app.settings import settings

PATH = "/api/method/diakronos.kronos.api.google_import."


@pytest.fixture
def configured(client):
    assert client.post(PATH + "save_credentials", json={
        "client_id": "fake-client", "client_secret": "fake-secret",
    }).status_code == 200
    return client


@pytest.fixture
def google(monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        assert request.url.host in {"oauth2.googleapis.com", "www.googleapis.com"}
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "fake-access", "refresh_token": "fake-refresh", "expires_in": 3600})
        return httpx.Response(200, json={"items": []})
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(g, "_http_client", lambda: httpx.Client(transport=transport))
    return calls


def authorize(client):
    response = client.get(PATH + "get_oauth_url")
    assert response.status_code == 200
    data = response.json()["message"]
    params = parse_qs(urlsplit(data["url"]).query)
    assert params["scope"] == ["https://www.googleapis.com/auth/calendar.readonly"]
    assert "fake-secret" not in data["url"]
    return params["state"][0]


def test_oauth_url_state_expiry_and_session_binding(configured):
    state = authorize(configured)
    assert len(state) >= 40
    redis = Redis.from_url(settings.redis_url)
    keys = list(redis.scan_iter("gcal:oauth:*"))
    assert len(keys) == 1
    assert 0 < redis.ttl(keys[0]) <= 600
    assert configured.get(PATH + "get_oauth_url", cookies={"sid": "foreign"}).status_code == 403


def test_exchange_one_use_encrypted(configured, google, patched_db):
    state = authorize(configured)
    response = configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
    assert response.status_code == 200
    assert response.json()["message"] == {"success": True}
    with patched_db() as db:
        row = db.get(GoogleKalenderEinstellungen, g.SETTINGS_NAME)
        assert row.authorized
        assert row.token_data.startswith("fernet:v1:")
        assert json.loads(decrypt_secret(row.token_data))["access_token"] == "fake-access"
    assert configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state}).status_code == 417
    assert len(google) == 1


def test_callback_returns_spa_without_secrets(configured, google):
    state = authorize(configured)
    response = configured.get("/google-calendar-callback", params={"code": "fake-code", "state": state}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/diakonos?gcal_step=2#/kalender/import"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    response = configured.get("/google-calendar-callback", params={"error": "secret-unsafe-error", "state": state}, follow_redirects=False)
    assert response.status_code == 303
    assert "gcal_error=" in response.headers["location"]
    assert "secret-unsafe-error" not in response.headers["location"]


def test_callback_guest_cannot_exchange(guest_client):
    response = guest_client.get("/google-calendar-callback?code=fake&state=fake", follow_redirects=False)
    assert response.status_code == 403


def test_calendars_paged_and_refresh(configured, google, patched_db, monkeypatch):
    state = authorize(configured)
    configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
    from diakronos_app.google_secrets import encrypt_secret
    with patched_db.begin() as db:
        row = db.get(GoogleKalenderEinstellungen, g.SETTINGS_NAME)
        tokens = json.loads(decrypt_secret(row.token_data))
        tokens["expiry"] = "2000-01-01T00:00:00+00:00"
        row.token_data = encrypt_secret(json.dumps(tokens))
    calls = []
    def handle(request):
        calls.append(request)
        if request.url.path == "/token":
            assert b"grant_type=refresh_token" in request.content
            return httpx.Response(200, json={"access_token": "refreshed", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer refreshed"
        page = request.url.params.get("pageToken")
        return httpx.Response(200, json={"items": [{"id": "two" if page else "one"}],
                                       **({} if page else {"nextPageToken": "next"})})
    monkeypatch.setattr(g, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(handle)))
    response = configured.get(PATH + "get_google_calendars")
    assert response.status_code == 200
    assert [cal["id"] for cal in response.json()["message"]] == ["one", "two"]
    assert len(calls) == 3
    with patched_db() as db:
        tokens = json.loads(decrypt_secret(db.get(GoogleKalenderEinstellungen, g.SETTINGS_NAME).token_data))
        assert tokens["refresh_token"] == "fake-refresh"
        assert tokens["access_token"] == "refreshed"


@pytest.mark.parametrize("abuse", ["other_session", "other_user", "expired", "changed_credentials", "redis_down"])
def test_state_abuse_never_contacts_google(configured, google, monkeypatch, abuse):
    from diakronos_app.frappe_compat import sitzungen, session
    from redis.exceptions import ConnectionError
    state = authorize(configured)
    if abuse == "other_session":
        sid, csrf = sitzungen.anlegen("Administrator")
        configured.cookies.set("sid", sid)
        configured.headers["X-Frappe-CSRF-Token"] = csrf
    elif abuse == "other_user":
        monkeypatch.setattr(g, "get_roles", lambda: ["System Manager"])
        session.user = "another@example.org"
        sid, csrf = sitzungen.anlegen(session.user)
        configured.cookies.set("sid", sid)
        configured.headers["X-Frappe-CSRF-Token"] = csrf
    elif abuse == "expired":
        redis = Redis.from_url(settings.redis_url)
        for key in redis.scan_iter("gcal:oauth:*"):
            redis.delete(key)
    elif abuse == "changed_credentials":
        configured.post(PATH + "save_credentials", json={"client_id": "changed", "client_secret": "changed"})
    else:
        def unavailable():
            raise ConnectionError("private-connection-secret")
        monkeypatch.setattr(g, "_state_store", unavailable)
    response = configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
    assert response.status_code == 417
    assert "private-connection-secret" not in response.text
    assert not google


@pytest.mark.parametrize("status", [401, 403, 429])
@pytest.mark.parametrize("phase", ["exchange", "calendars", "refresh"])
def test_google_failures_are_sanitized(configured, google, patched_db, monkeypatch, status, phase):
    state = authorize(configured)
    if phase != "exchange":
        configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
    if phase == "refresh":
        from diakronos_app.google_secrets import encrypt_secret
        with patched_db.begin() as db:
            row = db.get(GoogleKalenderEinstellungen, g.SETTINGS_NAME)
            tokens = json.loads(decrypt_secret(row.token_data))
            tokens["expiry"] = "2000-01-01T00:00:00+00:00"
            row.token_data = encrypt_secret(json.dumps(tokens))
    monkeypatch.setattr(g, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, text="fake-secret fake-access fake-refresh"))))
    response = (configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
                if phase == "exchange" else configured.get(PATH + "get_google_calendars"))
    assert response.status_code == 417
    assert str(status) in response.text
    for value in ["fake-secret", "fake-access", "fake-refresh", "fake-code"]:
        assert value not in response.text


@pytest.mark.parametrize("role", ["System Manager", "Mitgliederadministrator", "Kalenderadministrator"])
def test_original_roles_allowed(configured, google, patched_db, monkeypatch, set_user, role):
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User, Role, HasRole
    with patched_db.begin() as db:
        db.add(User(name="role@example.org", email="role@example.org", enabled=True))
        db.add(Role(name=role))
        db.flush()
        db.add(HasRole(name="test-role", parent="role@example.org", parenttype="User", parentfield="roles", role=role))
    set_user("role@example.org")
    sid, csrf = sitzungen.anlegen("role@example.org")
    configured.cookies.set("sid", sid)
    configured.headers["X-Frappe-CSRF-Token"] = csrf
    state = authorize(configured)
    assert configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state}).status_code == 200
    assert configured.get(PATH + "get_google_calendars").status_code == 200
    monkeypatch.setattr(g, "enqueue", lambda *a, **kw: None)
    assert configured.post(PATH + "start_import", json={"mappings_json": '[{"google_id":"id"}]'}).status_code == 200


def test_callback_access_log_redacts_code():
    import logging
    from diakronos_app.google_callback import OAuthAccessLogFilter
    record = logging.LogRecord("uvicorn.access", 20, "", 0, '%s - "%s %s HTTP/%s" %s',
                               ("client", "GET", "/google-calendar-callback?code=private&state=private", "1.1", 303), None)
    assert OAuthAccessLogFilter().filter(record)
    assert "private" not in record.getMessage()


@pytest.mark.parametrize("endpoint", ["exchange_code", "start_import"])
def test_google_writes_require_post(configured, endpoint):
    assert configured.get(PATH + endpoint).status_code == 417


@pytest.mark.parametrize("endpoint", ["get_oauth_url", "exchange_code", "get_google_calendars", "start_import"])
def test_oauth_guest_denied(guest_client, endpoint):
    assert guest_client.get(PATH + endpoint).status_code == 401


@pytest.mark.parametrize("endpoint", ["get_oauth_url", "exchange_code", "get_google_calendars", "start_import"])
def test_oauth_nonadmin_denied(client, set_user, endpoint):
    set_user("unknown@example.org")
    assert client.get(PATH + endpoint).status_code == 403
