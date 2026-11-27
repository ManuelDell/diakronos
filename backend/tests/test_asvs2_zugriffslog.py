"""ASVS2-4: Geheimnisse in protokollierten Adressen werden maskiert."""
from __future__ import annotations

import logging

import pytest

from diakronos_app.zugriffslog import GeheimnisFilter, einschalten, maskiere


@pytest.mark.parametrize("roh, erwartet", [
    ("/diakonos/gast?token=abcDEF123_-x", "/diakonos/gast?token=***"),
    ("/auth/oidc/callback?code=xyz&state=s1", "/auth/oidc/callback?code=***&state=***"),
    ("/public/registrierung?lang=de&TOKEN=geheim#teil", "/public/registrierung?lang=de&TOKEN=***#teil"),
    ("/api/method/x?seite=2&key=k1", "/api/method/x?seite=2&key=***"),
])
def test_maskiere(roh, erwartet) -> None:
    assert maskiere(roh) == erwartet


def test_harmlose_parameter_bleiben() -> None:
    assert maskiere("/kalender?monat=2026-11&ansicht=woche") == "/kalender?monat=2026-11&ansicht=woche"
    # Ein Parametername, der nur so AEHNLICH heisst, bleibt (kein Teilwort-Treffer).
    assert maskiere("/x?tokenliste=1&mycode=2") == "/x?tokenliste=1&mycode=2"


def test_filter_bearbeitet_uvicorn_zeile_und_laesst_sie_durch() -> None:
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                            '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/gast?token=geheim", "1.1", 200), None)
    assert GeheimnisFilter().filter(rec) is True
    assert "geheim" not in rec.getMessage() and "token=***" in rec.getMessage()


def test_einschalten_haengt_filter_einmal_an() -> None:
    log = logging.getLogger("uvicorn.access")
    einschalten(); einschalten()
    assert sum(isinstance(f, GeheimnisFilter) for f in log.filters) == 1


def test_app_erzeugung_schaltet_den_filter_ein() -> None:
    import diakronos_app.main  # noqa: F401 — erzeugt die App
    log = logging.getLogger("uvicorn.access")
    assert any(isinstance(f, GeheimnisFilter) for f in log.filters)
