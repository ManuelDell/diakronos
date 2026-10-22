"""ST2 — Lieder richtig pflegen: Kandidaten-Rollenfilter, Lied umbenennen,
Material (Arten/Limits), Tag-Pflege.

Rechte, Dateitypen, Limits und das Umbenennen/Entfernen von Auswahlwerten
werden hier direkt gegen die API geprueft. Die UI-Logik (Auswahl-Filter,
Tag-Filter) hat eigene Node-Tests unter frontend/src/diakonos.
"""
from __future__ import annotations

import io

import pytest

PFAD = "/api/method/diakronos.planrahmen.api."
MPFAD = "/api/method/diakronos.psalmos.api.musik."


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def fehler(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 417, r.text
    return r.json()


def anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


def stammdaten(sf):
    """Bereich Chor, Konten, Mitglieder, Faehigkeiten und Lieder."""
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Gruppe, Gruppenmitgliedschaft, Mitglied,
    )
    from diakronos_app.models.core import User
    from diakronos_app.models.psalmos import Lied
    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        s.add_all([User(name=k, email=k, enabled=True)
                   for k in ("planer_chor", "musikchef", "mitglied")])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k, nachname="Test")
                   for k in ("a", "b", "c", "planer_chor", "musikchef", "mitglied")])
        s.add(DienstbereichVerantwortlicher(name="bv-chor", parent="Chor",
                                            parenttype="Dienstbereich",
                                            parentfield="verantwortliche", user="planer_chor"))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add_all([Gruppenmitgliedschaft(name="gm-" + k, parent="Chor", parenttype="Gruppe",
                                         parentfield="mitglieder", mitglied=k, status="Aktiv")
                   for k in ("a", "b", "c")])
        s.add_all([Lied(name=f"LIED-{i}", titel=f"Lied {i}", aktiv=True) for i in range(1, 5)])


@pytest.fixture()
def chor_def():
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden
    return kochbuch_laden("chorplan")


# ── Aufgabe 1: nur passende Personen als Auswahl ────────────────────────────

def test_merkmal_kandidaten_filtert_nach_rolle(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    # a dirigiert, b spielt Klavier, c hat nichts.
    aufruf(client, "merkmale_pflegen", plantyp="chorplan", werte=[
        {"ziel": "person", "schluessel": "dirigent", "ziel_id": "a", "wert": True},
        {"ziel": "person", "schluessel": "klavier", "ziel_id": "b", "wert": True},
    ])
    erg = aufruf(client, "merkmal_kandidaten", plantyp="chorplan", schluessel="dirigent")
    assert [k["kennung"] for k in erg["kandidaten"]] == ["a"]
    assert erg["art"] == "person"
    erg2 = aufruf(client, "merkmal_kandidaten", plantyp="chorplan", schluessel="klavier")
    assert [k["kennung"] for k in erg2["kandidaten"]] == ["b"]


def test_merkmal_kandidaten_hinweis_bei_leer(client, patched_db, chor_def):
    stammdaten(patched_db)  # niemand ist als Dirigent markiert
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    erg = aufruf(client, "merkmal_kandidaten", plantyp="chorplan", schluessel="dirigent")
    assert erg["kandidaten"] == []
    assert "dirigiert" in erg["hinweis"]


def test_merkmal_kandidaten_unbekannt_oder_falsche_art(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    fehler(client, "merkmal_kandidaten", plantyp="chorplan", schluessel="gibtsnicht")
    # 'thema' ist ein Auswahl-Merkmal, kein Personen-Merkmal.
    fehler(client, "merkmal_kandidaten", plantyp="chorplan", schluessel="thema")


def test_merkmal_kandidaten_rechte(client, patched_db, chor_def):
    """Nur Bereichs-/Planverantwortliche; ein normales Mitglied bekommt 403."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "mitglied")
    r = client.post(PFAD + "merkmal_kandidaten", json={"plantyp": "chorplan", "schluessel": "dirigent"})
    assert r.status_code == 403
    anmelden(client, "planer_chor")
    assert client.post(PFAD + "merkmal_kandidaten",
                       json={"plantyp": "chorplan", "schluessel": "dirigent"}).status_code == 200


def test_personen_angabe_am_lied_speichern_und_ausliefern(client, patched_db, chor_def):
    """Standard-Dirigent eines Liedes setzen; stammdaten_holen liefert den Wert."""
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    aufruf(client, "merkmale_pflegen", plantyp="chorplan", werte=[
        {"ziel": "person", "schluessel": "dirigent", "ziel_id": "a", "wert": True}])
    aufruf(client, "merkmale_pflegen", plantyp="chorplan", werte=[
        {"ziel": "sammlung:lieder", "schluessel": "dirigent", "ziel_id": "LIED-1", "wert": "a"}])
    stub = aufruf(client, "stammdaten_holen", plantyp="chorplan")
    lieder = {l["kennung"]: l for l in stub["lieder"]}
    assert lieder["LIED-1"]["merkmale"].get("dirigent") == "a", lieder["LIED-1"]


# ── Aufgabe 2: Lied umbenennen (Psalmos = eine Wahrheit) ────────────────────

def test_lied_speichern_umbenennen(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    erg = aufruf(client, "lied_speichern", plantyp="chorplan", lied="LIED-1",
                 daten={"titel": "Neuer Titel", "gesangbuch_nummer": "123",
                        "buch": "EG", "seite": "7"})
    assert erg["titel"] == "Neuer Titel"
    assert erg["buch"] == "EG" and erg["seite"] == "7"
    # Eine Wahrheit: Psalmos liefert die Aenderung.
    detail = client.get(MPFAD + "get_lied_detail", params={"lied": "LIED-1"}).json()["message"]
    assert detail["lied"]["titel"] == "Neuer Titel"
    assert detail["lied"]["buch"] == "EG"


def test_lied_speichern_leerer_titel_und_rechte(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    fehler(client, "lied_speichern", plantyp="chorplan", lied="LIED-1", daten={"titel": "   "})
    anmelden(client, "mitglied")
    r = client.post(PFAD + "lied_speichern",
                    json={"plantyp": "chorplan", "lied": "LIED-1", "daten": {"titel": "X"}})
    assert r.status_code in (403, 417)


def test_lied_speichern_musikverantwortlicher_ohne_bereich(client, patched_db, chor_def):
    """Psalmos-Recht reicht: wer im Dienstbereich 'Musik und Worship' verantwortlich ist."""
    from diakronos_app.models.diakonos import Dienstbereich, DienstbereichVerantwortlicher
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied
    stammdaten(patched_db)
    with patched_db.begin() as s:
        s.add(Dienstbereich(name="Musik und Worship"))
        s.add(User(name="musikchef2", email="musikchef2", enabled=True))
        s.add(Mitglied(name="musikchef2", user="musikchef2", email="musikchef2", vorname="M"))
        s.add(DienstbereichVerantwortlicher(name="bv-musik", parent="Musik und Worship",
                                            parenttype="Dienstbereich", parentfield="verantwortliche",
                                            user="musikchef2"))
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    anmelden(client, "musikchef2")
    erg = aufruf(client, "lied_speichern", plantyp="chorplan", lied="LIED-2",
                 daten={"titel": "Von Musik"})
    assert erg["titel"] == "Von Musik"


# ── Aufgabe 3: Material (Noten/Audio/Notensatz) ─────────────────────────────

def _upload(client, inhalt: bytes, name: str, typ: str):
    return client.post("/api/method/upload_file",
                       files={"file": (name, io.BytesIO(inhalt), typ)})


def test_material_arten_und_upload(client, patched_db, chor_def, tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    # PDF + zwei Audios + MuseScore.
    faelle = [(b"%PDF-1.7\nx", "noten.pdf", "application/pdf", "noten_pdf"),
              (b"ID3\x04\x00\x00\x00\x00\x00\x00", "a1.mp3", "audio/mpeg", "audio"),
              (b"OggS\x00\x02\x00\x00", "a2.ogg", "audio/ogg", "audio"),
              (b"PK\x03\x04rest", "satz.mscz", "application/zip", "musescore")]
    ids = []
    for inhalt, name, typ, art in faelle:
        up = _upload(client, inhalt, name, typ)
        assert up.status_code == 200, up.text
        url = up.json()["message"]["file_url"]
        erg = aufruf(client, "lied_material_hinzufuegen", plantyp="chorplan", lied="LIED-1",
                     art=art, dateiname=name, datei_url=url, stimme="Sopran" if art == "audio" else "")
        assert erg["art"] == art
        ids.append(erg["material"])
    detail = client.get(MPFAD + "get_lied_detail", params={"lied": "LIED-1"}).json()["message"]
    mater = detail["fassungen"][0]["material"]
    assert len(mater) == 4
    assert all(m.get("datei", {}).get("datei_url") for m in mater)
    # Audio abspielbar: Datei inline ausgeliefert.
    audio = next(m for m in mater if m["art"] == "audio")
    herunter = client.get(audio["datei"]["datei_url"])
    assert herunter.status_code == 200
    assert herunter.headers["content-type"].startswith("audio/")


def test_material_verkehrte_endung_abgelehnt(client, patched_db, chor_def, tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    up = _upload(client, b"%PDF-1.7\n", "noten.pdf", "application/pdf")
    url = up.json()["message"]["file_url"]
    # Audio-Art mit PDF-Endung -> 417.
    fehler(client, "lied_material_hinzufuegen", plantyp="chorplan", lied="LIED-1",
           art="audio", dateiname="noten.pdf", datei_url=url)
    # Unbekannte Art.
    fehler(client, "lied_material_hinzufuegen", plantyp="chorplan", lied="LIED-1",
           art="video", dateiname="x.mp4", datei_url=url)


def test_material_upload_verkehrter_inhalt_abgelehnt(client, patched_db, tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    # Als PDF deklariert, aber falscher Inhalt -> Upload abgelehnt.
    up = _upload(client, b"kein pdf", "fake.pdf", "application/pdf")
    assert up.status_code == 417


def test_material_audio_limit_konfigurierbar(client, patched_db, chor_def, tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    monkeypatch.setattr(settings, "max_upload_bytes_audio", 1000)
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    # Audio nutzt das hoehere Audio-Limit: 400 Bytes sind erlaubt ...
    mittel = b"ID3" + b"\x00" * 397
    assert _upload(client, mittel, "ok.mp3", "audio/mpeg").status_code == 200
    # ... ein gleich grosser Text wuerde am allgemeinen Limit scheitern.
    assert _upload(client, mittel, "zu_gross.txt", "text/plain").status_code == 417
    # Ueber dem Audio-Limit -> 417.
    gross = b"ID3" + b"\x00" * 1200
    assert _upload(client, gross, "viel_zu_gross.mp3", "audio/mpeg").status_code == 417


def test_material_loeschen(client, patched_db, chor_def, tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    up = _upload(client, b"%PDF-1.7\n", "n.pdf", "application/pdf")
    url = up.json()["message"]["file_url"]
    erg = aufruf(client, "lied_material_hinzufuegen", plantyp="chorplan", lied="LIED-3",
                 art="noten_pdf", dateiname="n.pdf", datei_url=url)
    aufruf(client, "lied_material_loeschen", plantyp="chorplan", lied="LIED-3",
           material=erg["material"])
    detail = client.get(MPFAD + "get_lied_detail", params={"lied": "LIED-3"}).json()["message"]
    assert all(m["art"] != "noten_pdf" for m in detail["fassungen"][0]["material"])


# ── Aufgabe 4: Tags/Auswahlwerte pflegen ────────────────────────────────────

def test_tag_hinzufuegen_zuweisen_umbenennen_entfernen(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    # 'instrument' (Lieder) deklariert Geige/Gitarre/Kontrabass; Floete ergaenzen.
    erg = aufruf(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan",
                 schluessel="instrument", aktion="hinzufuegen", wert="Floete")
    assert "Floete" in erg["werte"]
    # Drei Liedern 'Geige' zuweisen (mehrfach-Merkmal -> Liste).
    for i in (1, 2, 3):
        aufruf(client, "merkmale_pflegen", plantyp="chorplan", werte=[
            {"ziel": "sammlung:lieder", "schluessel": "instrument", "ziel_id": f"LIED-{i}",
             "wert": ["Geige"]}])
    detail = client.get(MPFAD + "get_lieder", params={}).json()["message"]
    geige = [l for l in detail if l["name"] in ("LIED-1", "LIED-2", "LIED-3")]
    assert len(geige) == 3
    # Umbenennen aktualisiert vorhandene Zuordnungen.
    erg = aufruf(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan",
                 schluessel="instrument", aktion="umbenennen", wert="Geige", neu="Violine")
    assert "Violine" in erg["werte"] and "Geige" not in erg["werte"]
    assert erg["betroffen"] == 3
    # Entfernen meldet die Verwendung und entfernt die Zuordnungen.
    erg = aufruf(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan",
                 schluessel="instrument", aktion="entfernen", wert="Violine")
    assert "Violine" not in erg["werte"]
    assert erg["betroffen"] == 3
    assert "3" in erg["hinweis"]


def test_tag_pflege_rechte_und_fehler(client, patched_db, chor_def):
    stammdaten(patched_db)
    aufruf(client, "plantyp_speichern", definition=chor_def, gueltig_ab="2026-01-01")
    fehler(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan",
           schluessel="instrument", aktion="entfernen", wert="GibtsNicht")
    fehler(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan",
           schluessel="instrument", aktion="quatsch", wert="Geige")
    # 'dirigent' ist ein Personen-Merkmal, kein Auswahl-/Tag-Merkmal.
    fehler(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan",
           schluessel="dirigent", aktion="hinzufuegen", wert="X")
    anmelden(client, "mitglied")
    r = client.post(PFAD + "sammlungsmerkmal_werte_pflegen",
                    json={"plantyp": "chorplan", "schluessel": "instrument",
                          "aktion": "hinzufuegen", "wert": "X2"})
    assert r.status_code == 403
