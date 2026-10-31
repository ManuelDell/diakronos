"""WEB-7 — ungültige Registrierungs-/Gast-Links führen auf die Hauptseite.

Karte WEB-7 (Manuel 2026-10-30): „Überall wo man keine Rückmeldung braucht,
die Umleitung (auf die Hauptseite).“ Hauptseite ist die Wurzel der DOMAIN
(`/`), nicht das Diakronos-Präfix.

Der Server entscheidet NICHT selbst über die Weiterleitung (die Seite hat den
Token und die Adresse); er stuft den Fehler ein und schickt den Grund im
Boot-Objekt `window.__diakronos.linkGrund` mit. Diese Datei friert die
Einstufung ein — sie ist die einzige Stelle mit dem Wissen, WARUM die
Prüfung abgelehnt hat:

    unbekannt      Token unbekannt/deaktiviert, kein `?token=`   → U1/U2
    rate_limit     429 der Registrierungsbremse                  → U3
    serverfehler   5xx / unerwarteter Fehler                     → U3
    ab_gleich / abgelaufen / voll  zeitliche Grenze des Links    → U3

Läuft IM Image (`-o timeout_method=signal`, Regel 9) und im Worktree.
"""

from __future__ import annotations

import json
import re

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte

MODUL = "diakronos.diakonos.api.registrierung"
SLUG = "web7-slug"
LINK = "RL-WEB7"

OEFFENTLICHE_SEITEN = [("registrierung", "Mitglied-Registrierung"),
                       ("gast", "Gast-Anmeldung")]


# ── Fixtures ────────────────────────────────────────────────────────────────

def _link(**werte):
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": LINK,
        "bezeichnung": "Einladung",
        "typ": "Mitglied-Registrierung",
        "aktiv": True,
        "slug": SLUG,
        "max_anmeldungen": 0,
        "anmeldungen_count": 0,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


@pytest.fixture()
def welt(patched_db):
    """Ein gültiger Link + ein inaktiver (`deaktiviert`) zum Vergleich."""
    sess = patched_db()
    sess.add(_link())
    sess.add(_link(name="RL-AUS", slug="aus-slug", aktiv=False))
    sess.commit()
    yield sess
    sess.close()


def _daten(html: str) -> dict:
    """`window.__diakronos` aus dem HTML der öffentlichen Seite lesen."""
    m = re.search(r"window\.__diakronos\s*=\s*(\{.*?\});", html, re.S)
    assert m, "window.__diakronos fehlt im HTML der oeffentlichen Seite"
    return json.loads(m.group(1))


@pytest.mark.parametrize("seite,_typ", OEFFENTLICHE_SEITEN)
def test_unbekannter_token_wird_als_toter_link_eingestuft(guest_client, welt, seite, _typ):
    """U1/U2: „Ungültiger oder deaktivierter Registrierungslink“ → `unbekannt`."""
    r = guest_client.get(f"/diakonos/{seite}", params={"token": "gibt-es-nicht"})
    assert r.status_code == 200, r.text
    daten = _daten(r.text)
    assert daten["linkGrund"] == "unbekannt", daten["linkGrund"]
    assert daten["linkFehler"], "der Hinweistext bleibt im Boot-Objekt (U3-Fälle)"
    assert daten["token"] == ""


@pytest.mark.parametrize("seite,_typ", OEFFENTLICHE_SEITEN)
def test_deaktivierter_link_wird_als_toter_link_eingestuft(guest_client, welt, seite, _typ):
    """U1/U2: `aktiv = 0` → derselbe Grund wie ein erfundener Token."""
    r = guest_client.get(f"/diakonos/{seite}", params={"token": "aus-slug"})
    assert r.status_code == 200, r.text
    daten = _daten(r.text)
    assert daten["linkGrund"] == "unbekannt", daten["linkGrund"]


@pytest.mark.parametrize("seite,_typ", OEFFENTLICHE_SEITEN)
def test_ohne_token_grund_unbekannt(guest_client, welt, seite, _typ):
    """U1: Seite ohne `?token=` ist kein Link → Weiterleitung."""
    r = guest_client.get(f"/diakonos/{seite}")
    assert r.status_code == 200, r.text
    assert _daten(r.text)["linkGrund"] == "unbekannt"


@pytest.mark.parametrize("seite,_typ", OEFFENTLICHE_SEITEN)
def test_gueltiger_link_ohne_grund(guest_client, welt, seite, _typ):
    """Gültiger Link → kein Grund, kein Fehler, Token im Boot-Objekt."""
    r = guest_client.get(f"/diakonos/{seite}", params={"token": SLUG})
    assert r.status_code == 200, r.text
    daten = _daten(r.text)
    assert daten["linkGrund"] == "", "gültiger Link darf nicht weiterleiten"
    assert daten["linkFehler"] == ""
    assert daten["token"] == SLUG


def test_abgelaufener_link_bleibt_hinweis(guest_client, welt):
    """U3: abgelaufener Link ist umkehrbar → Meldung bleibt (Grund `abgelaufen`)."""
    from datetime import date, timedelta

    sess = welt
    link = sess.get(type(_link()), LINK)
    link.gueltig_bis = date.today() - timedelta(days=1)
    sess.commit()
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    daten = _daten(r.text)
    assert daten["linkGrund"] == "abgelaufen", daten["linkGrund"]
    assert "abgelaufen" in daten["linkFehler"]


def test_link_vor_start_bleibt_hinweis(guest_client, welt):
    """U3: „Anmeldung ab …“ nennt das Datum → Meldung bleibt."""
    from datetime import date, timedelta

    sess = welt
    link = sess.get(type(_link()), LINK)
    link.gueltig_ab = date.today() + timedelta(days=7)
    sess.commit()
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    daten = _daten(r.text)
    assert daten["linkGrund"] == "ab_gleich", daten["linkGrund"]
    assert "Anmeldung ab" in daten["linkFehler"]


def test_kontingent_erschoepft_bleibt_hinweis(guest_client, welt):
    """U3: Link voll → Meldung bleibt (die Gemeinde legt einen neuen an)."""
    sess = welt
    link = sess.get(type(_link()), LINK)
    link.max_anmeldungen = 3
    link.anmeldungen_count = 3
    sess.commit()
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    daten = _daten(r.text)
    assert daten["linkGrund"] == "voll", daten["linkGrund"]
    assert "maximale Anzahl" in daten["linkFehler"]


def test_rate_limit_bleibt_hinweis(guest_client, welt, monkeypatch):
    """U3: 429 der Bremse → Meldung bleibt (die Person soll es erneut versuchen)."""
    from diakronos_app.anmeldung import registrierungsbremse
    from diakronos_app.frappe_compat.exceptions import RateLimitError

    monkeypatch.setattr(
        registrierungsbremse, "zaehle_validierung", lambda *a, **k: False
    )
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    assert r.status_code == 200, r.text
    daten = _daten(r.text)
    assert daten["linkGrund"] == "rate_limit", daten["linkGrund"]
    assert registrierungsbremse.fehlermeldung() in daten["linkFehler"]
    assert RateLimitError.http_status == 429


def test_serverfehler_bleibt_hinweis(guest_client, welt, monkeypatch):
    """U3: unerwarteter Fehler (Diakronos nicht erreichbar) → Meldung bleibt."""
    from diakronos_app.api import registrierung as modul

    def kaputt(*a, **k):
        raise RuntimeError("Datenbank weg")

    monkeypatch.setattr(modul, "validate_token", kaputt)
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    assert r.status_code == 200, r.text
    daten = _daten(r.text)
    assert daten["linkGrund"] == "serverfehler", daten["linkGrund"]
    assert daten["linkFehler"], "ohne Meldung waere die Seite stumm"


def test_einstufung_kennt_alle_wortlaute_der_pruefung():
    """Die Einstufung und `_validate_token` dürfen nicht auseinanderlaufen.

    Ändert jemand einen Satz in `api/registrierung.py`, fällt die Einstufung
    auf `serverfehler` zurück (fail safe: Meldung statt stiller Weiterleitung).
    Dieser Test macht die Abweichung sichtbar, statt sie zu verstecken.
    """
    from pathlib import Path

    from diakronos_app import spa

    quelle = Path(spa.__file__).with_name("api") / "registrierung.py"
    text = quelle.read_text(encoding="utf-8")
    for wortlaut, _grund in spa._LINK_GRUENDE:
        assert wortlaut in text, f"Wortlaut „{wortlaut}“ steht nicht mehr in der Pruefung"


def test_keine_tokenausgabe_im_log(guest_client, welt, caplog):
    """U6: beim Ablehnen landet kein Token im Log der ANWENDUNG.

    (Die Zeile des Test-Clients `httpx … GET …?token=…` ist der Aufruf des
    Tests selbst, nicht unsere Ausgabe — nur die App-Logger zaehlen.)
    """
    with caplog.at_level("DEBUG"):
        guest_client.get("/diakonos/registrierung", params={"token": "geheim-123"})
        guest_client.get("/diakonos/gast", params={"token": "geheim-123"})
    app_eintraege = [
        e for e in caplog.records if not e.name.startswith(("httpx", "httpcore"))
    ]
    for eintrag in app_eintraege:
        assert "geheim-123" not in eintrag.getMessage()
    # Und auch die Meldung selbst traegt nie den Token.
    r = guest_client.get("/diakonos/registrierung", params={"token": "geheim-123"})
    assert "geheim-123" not in _daten(r.text)["linkFehler"]
