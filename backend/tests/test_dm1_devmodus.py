"""DM1 — Dev-Modus: Rechte, Schalter, Befunde, Upload-Typen, Fehlerumfeld, Bericht.

Reihenfolge wie in der Karte:

1. ausgeschaltet (``DEVMODE_ENABLED`` nicht gesetzt) -> Endpunkt nicht erreichbar (404),
2. angemeldet ohne Rolle ``Tester`` -> 403,
3. mit Rolle ``Tester`` -> Zugriff,
4. Administrator -> Zugriff,
5. Bild-/Audio-Typen und Groessenlimits,
6. Fehlerumfeld der letzten 60 s,
7. Bericht-CLI (Markdown + JSON), Uebernahme alter Befunde.
"""

from __future__ import annotations

import base64
import json

import pytest

from diakronos_app.devmodus import einstellungen

PFAD = "/api/method/diakronos.devmodus.api."


@pytest.fixture()
def aus(monkeypatch):
    monkeypatch.delenv("DEVMODE_ENABLED", raising=False)
    monkeypatch.setattr(einstellungen.settings, "devmode_enabled", False, raising=False)


@pytest.fixture()
def an(monkeypatch):
    monkeypatch.setenv("DEVMODE_ENABLED", "1")
    monkeypatch.setattr(einstellungen.settings, "devmode_enabled", True, raising=False)


def _png() -> str:
    # 1x1 PNG (Magic-Bytes entscheiden, nicht der gemeldete Typ).
    roh = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
    return base64.b64encode(roh).decode()


def _jpg() -> str:
    roh = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
        "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
        "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")
    return base64.b64encode(roh).decode()


# ── Schalter ───────────────────────────────────────────────────────────────

def test_schalter_default_ist_aus():
    from diakronos_app.settings import Settings

    assert Settings(_env_file=None).devmode_enabled is False
    assert "devmode_enabled" in Settings.model_fields
    assert "testsuite_enabled" not in Settings.model_fields


def test_aus_heisst_nicht_erreichbar(client, aus):
    antwort = client.post(PFAD + "uebersicht", json={})
    assert antwort.status_code == 404, antwort.text


def test_installiere_ist_ohne_schalter_still(monkeypatch, aus):
    from fastapi import FastAPI

    from diakronos_app.devmodus import ueberwachung

    frisch = FastAPI()
    assert ueberwachung.installiere(frisch) is False


def test_middleware_erfasst_fehler_der_laufenden_sitzung(an, patched_db, set_user):
    """Die Ueberwachung ordnet einen 4xx der laufenden Sitzung des Nutzers zu.

    Laeuft gegen eine FRISCHE App (mit eigener Middleware-Kette), damit die
    Installation selbst mitgeprueft wird. Wichtig: die Schicht muss NACH der
    Session-Aufloesung laufen — deshalb wird hier zuerst geprueft, dass ein
    Aufruf ohne laufende Sitzung NICHTS schreibt, dann mit Sitzung sehr wohl.
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from diakronos_app.devmodus import dienste, ueberwachung

    set_user("Administrator")
    s = patched_db()
    dienste.sitzung_starten(s, "Administrator")
    s.commit()
    s.close()

    app = FastAPI()
    app.add_middleware(ueberwachung.DevmodusMiddleware)

    @app.post("/api/method/boom")
    def boom():
        return JSONResponse(status_code=417, content={"message": "kaputt"})

    client = TestClient(app)
    assert client.post("/api/method/boom").status_code == 417

    kontrolle = patched_db()
    arten = [e["art"] for e in dienste.ereignisse(kontrolle, "Administrator")]
    assert "http_4xx" in arten, arten
    kontrolle.close()

    # Nach dem Beenden der Sitzung wird nichts mehr erfasst.
    kontrolle = patched_db()
    dienste.sitzung_beenden(kontrolle, "Administrator")
    kontrolle.commit()
    kontrolle.close()
    client.post("/api/method/boom")
    kontrolle = patched_db()
    assert len(dienste.ereignisse(kontrolle, "Administrator")) == 1
    kontrolle.close()


# ── Rechte ─────────────────────────────────────────────────────────────────

def test_ohne_rolle_ist_verboten(client, an, set_user, patched_db):
    set_user("normaler.nutzer")
    s = patched_db()
    from diakronos_app.models.core import User

    if s.get(User, "normaler.nutzer") is None:
        s.add(User(name="normaler.nutzer", email="n@example.org",
                   full_name="Normal", enabled=True))
        s.commit()

    antwort = client.post(PFAD + "uebersicht", json={})
    assert antwort.status_code == 403, antwort.text
    s.close()


def test_administrator_hat_zugriff(client, an):
    antwort = client.post(PFAD + "uebersicht", json={})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert "kennzahlen" in daten and "kuerzel" in daten


def test_tester_rolle_hat_zugriff(client, an, set_user, patched_db):
    from diakronos_app.models.core import HasRole, User

    s = patched_db()
    if s.get(User, "tester1") is None:
        s.add(User(name="tester1", email="t@example.org", full_name="Tester", enabled=True))
    s.add(HasRole(name="hase-t1", parent="tester1", parentfield="roles",
                  parenttype="User", role="Tester"))
    s.commit()
    s.close()
    set_user("tester1")

    antwort = client.post(PFAD + "uebersicht", json={})
    assert antwort.status_code == 200, antwort.text


# ── Sitzung + Befund ───────────────────────────────────────────────────────

def test_sitzung_starten_und_beenden(client, an):
    start = client.post(PFAD + "sitzung_starten", json={})
    assert start.status_code == 200, start.text
    assert start.json()["message"]["aktiv"] == 1
    sitzung = client.post(PFAD + "sitzung_status", json={}).json()["message"]["sitzung"]
    assert sitzung is not None
    ende = client.post(PFAD + "sitzung_beenden", json={})
    assert ende.json()["message"]["aktiv"] == 0


def test_befund_anlegen_erscheint_in_liste(client, an):
    client.post(PFAD + "sitzung_starten", json={})
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "Knopf verschwindet bei kleiner Breite.",
        "art": "design", "wichtigkeit": "hoch",
        "url": "http://test/#/lieder", "route": "#/lieder",
        "seitentitel": "Lieder", "seite": "Lieder",
        "viewport": "390x844", "element": {"selektor": "#neu", "tag": "button",
                                           "komponenten": ["Lieder", "DkButton"]},
    })
    assert antwort.status_code == 200, antwort.text
    befund = antwort.json()["message"]
    assert befund["art"] == "design" and befund["status"] == "offen"
    assert befund["element"]["selektor"] == "#neu"

    liste = client.post(PFAD + "befunde_holen", json={}).json()["message"]
    assert any(b["name"] == befund["name"] for b in liste)


def test_element_kontext_wird_redigiert(client, an):
    client.post(PFAD + "sitzung_starten", json={})
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "Login kaputt",
        "element": {"selektor": "#pw", "tag": "input",
                    "formularwerte": {"password": "geheim123", "nutzer": "a"},
                    "outer_html": '<input type="password" value="geheim123">'},
    })
    befund = antwort.json()["message"]
    roh = json.dumps(befund, ensure_ascii=False)
    assert "geheim123" not in roh
    assert "[entfernt]" in roh


def test_befund_status_und_loeschen(client, an):
    client.post(PFAD + "sitzung_starten", json={})
    name = client.post(PFAD + "befund_speichern", json={"text": "x"}
                       ).json()["message"]["name"]
    gesetzt = client.post(PFAD + "befund_setzen", json={"name": name, "status": "behoben"})
    assert gesetzt.json()["message"]["status"] == "behoben"
    geloescht = client.post(PFAD + "befund_loeschen", json={"name": name})
    assert geloescht.status_code == 200, geloescht.text
    liste = client.post(PFAD + "befunde_holen", json={}).json()["message"]
    assert not any(b["name"] == name for b in liste)


def test_ungueltige_art_wird_abgewiesen(client, an):
    client.post(PFAD + "sitzung_starten", json={})
    antwort = client.post(PFAD + "befund_speichern", json={"text": "x", "art": "quatsch"})
    assert antwort.status_code == 417, antwort.text
    assert antwort.json()["meldungen"][0]["pfad"] == "/art"


# ── Upload-Typen ───────────────────────────────────────────────────────────

def test_bild_hochladen_nimmt_png(client, an, tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    antwort = client.post(PFAD + "bild_hochladen", json={"daten": _png(), "typ": "image/png"})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["pfad"].startswith("devmodus/") and daten["pfad"].endswith(".png")


def test_bild_hochladen_lehnt_text_ab(client, an, tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    roh = base64.b64encode(b"kein bild").decode()
    antwort = client.post(PFAD + "bild_hochladen", json={"daten": roh, "typ": "image/png"})
    assert antwort.status_code == 417, antwort.text


def test_befund_mit_bild(client, an, tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    client.post(PFAD + "sitzung_starten", json={})
    bild = client.post(PFAD + "bild_hochladen", json={"daten": _jpg()}).json()["message"]
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "mit Bild", "bilder": [{"pfad": bild["pfad"]}]})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["bilder"] == [bild["pfad"]]


def test_befund_lehnt_fremden_bildpfad_ab(client, an, tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    client.post(PFAD + "sitzung_starten", json={})
    antwort = client.post(PFAD + "befund_speichern", json={
        "text": "x", "bilder": [{"pfad": "devmodus/2026-01-01/../../etc/passwd"}]})
    assert antwort.status_code == 417, antwort.text


def test_audio_hochladen_webm(client, an, tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    # EBML-Kopf (webm/matroska) — binär, hier nur als Base64.
    roh = base64.b64encode(b"\x1a\x45\xdf\xa3" + b"\x00" * 32).decode()
    antwort = client.post(PFAD + "audio_hochladen", json={"daten": roh, "typ": "audio/webm"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["pfad"].endswith(".webm")


# ── Fehlerumfeld ───────────────────────────────────────────────────────────

def test_fehlerumfeld_nimmt_fehler_der_sitzung(client, an, patched_db):
    from diakronos_app.devmodus import dienste

    client.post(PFAD + "sitzung_starten", json={})
    s = patched_db()
    dienste.ereignis_speichern(s, benutzer="Administrator", art="http_4xx",
                               methode="POST", pfad="/api/method/x", status=417,
                               meldung="HTTP 417")
    dienste.ereignis_speichern(s, benutzer="Administrator", art="langsam",
                               pfad="/api/method/y", dauer_ms=1234, meldung="1234 ms")
    s.commit()
    s.close()

    daten = client.post(PFAD + "ereignisse_holen", json={}).json()["message"]
    assert daten["fehler"] == 1
    assert daten["ereignisse"][0]["art"] == "http_4xx"


# ── Bericht ────────────────────────────────────────────────────────────────

def test_bericht_erzeugt_markdown_und_json(client, an, tmp_path, monkeypatch):
    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    monkeypatch.setattr("diakronos_app.devmodus.bericht.settings.files_dir", str(tmp_path))
    client.post(PFAD + "sitzung_starten", json={})
    client.post(PFAD + "befund_speichern", json={
        "text": "Fehler beim Speichern", "url": "http://test/#/planrahmen",
        "route": "#/planrahmen", "seite": "Pläne",
        "element": {"selektor": "#save", "tag": "button",
                    "komponenten": ["Pläne", "DkButton"], "text": "Speichern"}})
    antwort = client.post(PFAD + "bericht_erzeugen", json={})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    md = (tmp_path / daten["bericht"]).read_text(encoding="utf-8")
    assert "Fehler beim Speichern" in md
    assert "#/planrahmen" in md and "#save" in md and "DkButton" in md
    js = json.loads((tmp_path / daten["json"]).read_text(encoding="utf-8"))
    assert js["befunde"][0]["element"]["selektor"] == "#save"


def test_bericht_cli_json(client, an, tmp_path, monkeypatch, capsys):
    from diakronos_app.devmodus import bericht

    monkeypatch.setattr("diakronos_app.devmodus.dienste.settings.files_dir", str(tmp_path))
    monkeypatch.setattr("diakronos_app.devmodus.bericht.settings.files_dir", str(tmp_path))
    befund = bericht.erzeugen
    # Direkter Dienstaufruf statt CLI-Argumente: die CLI liest db.SessionLocal.
    from diakronos_app import db

    with db.SessionLocal.begin() as s:
        s.add(__import__("diakronos_app.models.devmodus", fromlist=["DevBefund"]).DevBefund(
            name="DMB-cli", benutzer="Administrator", text="CLI-Test", art="fehler",
            wichtigkeit="mittel", status="offen", titel="T", seite="Home",
            bilder=[], fehlerumfeld=[]))
    with db.SessionLocal() as s:
        daten = bericht.sammeln(s)
    assert any(b["text"] == "CLI-Test" for b in daten["befunde"])


# ── Uebernahme alter Befunde ───────────────────────────────────────────────

def test_alte_testsuite_befunde_werden_uebernommen(patched_db):
    from sqlalchemy import text

    from diakronos_app.devmodus import dienste

    s = patched_db()
    s.execute(text("CREATE TABLE ts_befund (name TEXT, seite TEXT, titel TEXT, "
                   "meldung TEXT, status TEXT, gemeldet_von TEXT, zeitpunkt TIMESTAMP)"))
    s.execute(text("CREATE TABLE ts_kommentar (name TEXT, text TEXT, seite TEXT, "
                   "route TEXT, benutzer TEXT, bilder TEXT, zeitpunkt TIMESTAMP)"))
    s.execute(text("INSERT INTO ts_befund VALUES ('TSB-1','Lieder','Titel','kaputt',"
                   "'offen','Administrator',NULL)"))
    s.execute(text("INSERT INTO ts_kommentar VALUES ('TSK-1','Anmerkung','Home',"
                   "'#/','Administrator','[]',NULL)"))
    s.commit()

    ergebnis = dienste.alte_testsuite_uebernehmen(s)
    s.commit()
    assert ergebnis["befunde"] == 1 and ergebnis["kommentare"] == 1
    assert s.get(dienste.DevBefund, "alt-TSB-1") is not None
    assert s.get(dienste.DevBefund, "altk-TSK-1") is not None
    # Idempotent: erneuter Lauf legt nichts doppelt an.
    assert dienste.alte_testsuite_uebernehmen(s) == {"befunde": 0, "kommentare": 0}
    s.close()
