"""SEC-10 — Dev-Modus haerten: Audio-Upload validieren + Pfad-Leak im Bericht.

Pentest Runde 4, Befunde F4-1 (MITTEL) und F4-2 (NIEDRIG):

* ``audio_hochladen`` prueft nur das Feld ``typ``, nicht den Inhalt —
  HTML/SVG/EXE/0 Bytes/11 MB wurden mit 200 gespeichert.
* ``bericht_erzeugen`` liefert ``pfad`` als ABSOLUTEN Container-Pfad
  (``/data/files/devmodus/...``) aus.

Der Bildweg (``bild_hochladen``) macht es bereits richtig; Audio wird
spiegelbildlich gebaut: Inhalt per Magic-Bytes pruefen, leere Daten
ablehnen, Groessenlimit durchsetzen.
"""

from __future__ import annotations

import base64

import pytest

from diakronos_app.devmodus import einstellungen
from diakronos_app.settings import settings

PFAD = "/api/method/diakronos.devmodus.api."


@pytest.fixture()
def an(monkeypatch):
    monkeypatch.setenv("DEVMODE_ENABLED", "1")
    monkeypatch.setattr(einstellungen.settings, "devmode_enabled", True, raising=False)


@pytest.fixture()
def ordner(tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    monkeypatch.setattr("diakronos_app.devmodus.bericht.settings.files_dir", str(tmp_path))
    return tmp_path


def _b64(roh: bytes) -> str:
    return base64.b64encode(roh).decode()


#: Echte Signaturen der drei von MediaRecorder gelieferten Container.
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
OGG = b"OggS\x00\x02" + b"\x00" * 32
M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 24


# ── S1: Inhalt statt nur gemeldeter Typ ────────────────────────────────────

@pytest.mark.parametrize("roh,typ,endung", [
    (WEBM, "audio/webm", ".webm"),
    (OGG, "audio/ogg", ".ogg"),
    (M4A, "audio/m4a", ".m4a"),
])
def test_audio_echte_signatur_wird_angenommen(client, an, ordner, roh, typ, endung):
    antwort = client.post(PFAD + "audio_hochladen", json={"daten": _b64(roh), "typ": typ})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["pfad"].startswith("devmodus/") and daten["pfad"].endswith(endung)
    assert (ordner / daten["pfad"]).read_bytes() == roh


@pytest.mark.parametrize("roh", [
    b"<html><script>alert(1)</script></html>",
    b"<svg onload=alert(1)></svg>",
    b"MZ\x90\x00\x03\x00\x00\x00",          # Windows-EXE
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 16,    # Bild statt Audio
    b"kein audio",
])
def test_audio_lehnt_fremdinhalt_ab(client, an, ordner, roh):
    antwort = client.post(PFAD + "audio_hochladen",
                          json={"daten": _b64(roh), "typ": "audio/webm"})
    assert antwort.status_code == 417, antwort.text
    assert not list(ordner.glob("devmodus/**/*")), "abgelehnter Inhalt darf nicht liegen"


def test_audio_lehnt_leere_daten_ab(client, an, ordner):
    antwort = client.post(PFAD + "audio_hochladen", json={"daten": "", "typ": "audio/webm"})
    assert antwort.status_code == 417, antwort.text
    assert not list(ordner.glob("devmodus/**/*"))


def test_audio_lehnt_zu_grosse_datei_ab(client, an, ordner, monkeypatch):
    monkeypatch.setattr(settings, "devmodus_audio_max_bytes", 1024)
    roh = WEBM + b"\x00" * 2048
    antwort = client.post(PFAD + "audio_hochladen",
                          json={"daten": _b64(roh), "typ": "audio/webm"})
    assert antwort.status_code == 417, antwort.text
    assert "gro" in antwort.text.lower()
    assert not list(ordner.glob("devmodus/**/*"))


def test_audio_grenze_ist_zehn_megabyte():
    """Eigene Einstellung mit Default 10 MB (analog Bild-Weg)."""
    assert einstellungen.max_audio_bytes() <= 10 * 1024 * 1024


def test_audio_grenze_kommt_aus_der_einstellung(monkeypatch):
    monkeypatch.setattr(settings, "devmodus_audio_max_bytes", 4096)
    assert einstellungen.max_audio_bytes() == 4096


def test_audio_meldet_gemeldeten_typ_bei_inhaltswiderspruch(client, an, ordner):
    """Inhalt sagt WebM, gemeldet wird OGG -> Ablehnung (wie beim Bild)."""
    antwort = client.post(PFAD + "audio_hochladen",
                          json={"daten": _b64(WEBM), "typ": "audio/ogg"})
    assert antwort.status_code == 417, antwort.text


def test_audio_traegt_erkannten_typ_im_befund(client, an, ordner):
    client.post(PFAD + "sitzung_starten", json={})
    datei = client.post(PFAD + "audio_hochladen",
                        json={"daten": _b64(OGG), "typ": "audio/ogg"}).json()["message"]
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "mit Aufnahme", "audio": {"pfad": datei["pfad"], "typ": datei["typ"]}})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["audio"]["pfad"] == datei["pfad"]


# ── S2: kein absoluter Pfad in bericht_erzeugen ────────────────────────────

def test_bericht_ohne_absoluten_pfad(client, an, ordner):
    client.post(PFAD + "sitzung_starten", json={})
    client.post(PFAD + "befund_speichern", json={"text": "Pfad-Leak pruefen"})
    antwort = client.post(PFAD + "bericht_erzeugen", json={})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert "pfad" not in daten, daten
    for schluessel in ("bericht", "json"):
        wert = daten[schluessel]
        assert not wert.startswith("/"), wert
        assert wert.startswith("devmodus/"), wert
        assert (ordner / wert).is_file(), wert
    # Nirgends im Antwortkoerper steht der absolute Wurzelpfad.
    assert str(ordner) not in antwort.text
