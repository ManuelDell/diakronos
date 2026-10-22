"""`/` fuehrt in die SPA statt in ein FastAPI-404 (Betrieb hinter NPM ohne stack-nginx)."""

from __future__ import annotations


def test_wurzel_leitet_relativ_auf_diakonos(client):
    antwort = client.get("/", follow_redirects=False)
    assert antwort.status_code == 302
    assert antwort.headers["location"] == "/diakonos"
