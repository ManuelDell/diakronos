"""DM2 — Reparaturen am Dev-Modus.

1. UXM-R12: Befund-Bilder werden ueber ``/api/method/diakronos.devmodus.api.bild``
   ausgeliefert (der generische ``/files``-Weg verlangt eine ``File``-Zeile, die
   es fuer Dev-Modus-Bilder nie gibt) — mit Rechtepruefung und Pfadmuster.
2. UXM-R13: Der Listentitel eines Befunds kommt aus der ersten Kommentarzeile
   statt immer aus dem Fenstertitel („Meine Gemeinde“).

Vorher rot: ``/files/devmodus/...`` liefert 404, der Titel ist immer
„Meine Gemeinde“.
"""

from __future__ import annotations

import base64

import pytest

from diakronos_app.devmodus import einstellungen

PFAD = "/api/method/diakronos.devmodus.api."


@pytest.fixture()
def an(monkeypatch):
    monkeypatch.setenv("DEVMODE_ENABLED", "1")
    monkeypatch.setattr(einstellungen.settings, "devmode_enabled", True, raising=False)


def _png() -> str:
    roh = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
    return base64.b64encode(roh).decode()


@pytest.fixture()
def bildpfad(client, an, tmp_path, monkeypatch):
    """Legt ein echtes Befund-Bild ab und liefert ``devmodus/<datum>/<name>``."""
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    antwort = client.post(PFAD + "bild_hochladen", json={"daten": _png(), "typ": "image/png"})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["message"]["pfad"]


# ── UXM-R12: Bild-Endpunkt ─────────────────────────────────────────────────

def test_bild_endpunkt_liefert_das_bild(client, bildpfad):
    """Der neue Endpunkt liefert das Bild als PNG mit Rechtepruefung (UXM-R12)."""
    antwort = client.get(PFAD + "bild", params={"pfad": bildpfad})
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["content-type"].startswith("image/png")
    assert antwort.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert antwort.headers.get("x-content-type-options") == "nosniff"


def test_bild_endpunkt_ohne_anmeldung_verboten(client, an, bildpfad):
    """Ohne angemeldeten Nutzer bleibt der Endpunkt zu (Rechtepruefung)."""
    # Achtung: `from ... import session as x` liefert das session-OBJEKT, nicht
    # das Modul (frappe_compat/__init__.py bindet den Namen um) — siehe conftest.
    import importlib

    session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

    session_mod.session.user = "Guest"
    antwort = client.get(PFAD + "bild", params={"pfad": bildpfad})
    assert antwort.status_code in (401, 403), antwort.text


def test_bild_endpunkt_lehnt_fremde_pfade_ab(client, an, tmp_path, monkeypatch):
    """Nur Pfade aus UNSEREM Muster werden ausgeliefert (kein Pfadausbruch)."""
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    for boese in ("devmodus/2026-01-01/../../etc/passwd",
                  "devmodus/2026-01-01/aaaaaaaaaaaaaaaa.txt",
                  "devmodus/2026-01-01/aaaaaaaaaaaaaaaa.png",
                  "", "../secret.png"):
        antwort = client.get(PFAD + "bild", params={"pfad": boese})
        assert antwort.status_code == 404, f"{boese!r}: {antwort.status_code}"


def test_bild_endpunkt_ohne_schalter_weg(client, bildpfad, monkeypatch):
    """Ohne ``DEVMODE_ENABLED`` existiert der Endpunkt nicht (404)."""
    monkeypatch.delenv("DEVMODE_ENABLED", raising=False)
    monkeypatch.setattr(einstellungen.settings, "devmode_enabled", False, raising=False)
    antwort = client.get(PFAD + "bild", params={"pfad": bildpfad})
    assert antwort.status_code == 404, antwort.text


def test_generischer_files_weg_bleibt_zu(client, bildpfad):
    """Belegt die Ursache: ``/files/<devmodus-pfad>`` ist (weiterhin) 404."""
    antwort = client.get("/files/" + bildpfad)
    assert antwort.status_code == 404, antwort.text


# ── UXM-R13: Titel aus dem Kommentar ───────────────────────────────────────

def test_titel_kommt_aus_der_ersten_kommentarzeile(client, an, patched_db):
    """Der Titel ist die erste Zeile des Kommentars, nicht der Fenstertitel."""
    client.post(PFAD + "sitzung_starten", json={})
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "Knopf ohne Wirkung\nZweite Zeile mit Details",
        "seitentitel": "Meine Gemeinde", "seite": "Lieder", "route": "#/lieder",
    })
    assert antwort.status_code == 200, antwort.text
    befund = antwort.json()["message"]
    assert befund["titel"] == "Knopf ohne Wirkung", befund["titel"]


def test_titel_faellt_auf_element_und_route_zurueck(client, an, patched_db):
    """Ohne Kommentar: „Element – Route“ (elementEtikett kommt vom Client)."""
    client.post(PFAD + "sitzung_starten", json={})
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "", "seitentitel": "Meine Gemeinde", "seite": "DkButton button.dk-btn",
        "route": "#/lieder",
    })
    assert antwort.status_code == 200, antwort.text
    titel = antwort.json()["message"]["titel"]
    assert titel != "Meine Gemeinde", titel
    assert "DkButton button.dk-btn" in titel and "#/lieder" in titel, titel


def test_titel_wird_gekuerzt(client, an, patched_db):
    """Sehr lange erste Zeilen werden fuer die Liste gekuerzt."""
    client.post(PFAD + "sitzung_starten", json={})
    lang = "X" * 500
    antwort = client.post(PFAD + "befund_speichern", json={"text": lang, "seite": "S"})
    assert antwort.status_code == 200, antwort.text
    assert len(antwort.json()["message"]["titel"]) == 120
