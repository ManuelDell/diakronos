"""Fake Google transport for isolated G1b acceptance subprocesses only."""
import os
import sys

import httpx


def configure():
    assert os.environ.get("G1B_DISPOSABLE_DB") == "1"
    assert "g1b-postgres" in os.environ["DATABASE_URL"]
    from diakronos_app.api.kronos import google_import as g
    def handle(request):
        if request.url.host == "oauth2.googleapis.com" and request.url.path == "/token":
            assert b"fake-secret" in request.content
            return httpx.Response(200, json={"access_token": "fake-access", "refresh_token": "fake-refresh", "expires_in": 3600})
        assert request.url.host == "www.googleapis.com"
        assert request.headers["Authorization"] == "Bearer fake-access"
        page = request.url.params.get("pageToken")
        if request.url.path.endswith("/calendarList"):
            return httpx.Response(200, json={"items": [{"id": "second" if page else "first", "summary": "Fake calendar"}],
                                           **({} if page else {"nextPageToken": "page-two"})})
        assert request.url.path.endswith("/events")
        return httpx.Response(200, json={"items": ([
            {"id": "day", "start": {"date": "2026-10-01"}, "end": {"date": "2026-10-03"}},
            {"id": "cancelled", "status": "cancelled"},
        ] if page else [
            {"id": "timed", "summary": "Fake timed event", "start": {"dateTime": "2026-10-01T09:00:00Z"}, "end": {"dateTime": "2026-10-01T10:00:00Z"}},
        ]), **({} if page else {"nextPageToken": "page-two"})})
    g._http_client = lambda: httpx.Client(transport=httpx.MockTransport(handle))


if __name__ == "__main__":
    configure()
    if sys.argv[1] == "app":
        import uvicorn
        uvicorn.run("diakronos_app.main:app", host="127.0.0.1", port=int(sys.argv[2]), log_level="warning", timeout_graceful_shutdown=2)
    elif sys.argv[1] == "worker":
        from redis import Redis
        from rq import Queue, SimpleWorker
        from diakronos_app.settings import settings
        connection = Redis.from_url(settings.redis_url)
        worker = SimpleWorker([Queue("default", connection=connection)], connection=connection)
        worker.work(burst=True, logging_level="WARNING")
    else:
        raise ValueError("Unknown acceptance mode")
