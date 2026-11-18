"""SPEICHER-1 — „ohne Einstellung bleibt alles exakt wie heute“.

Die Karte verlangt fuer die Standard-Ablage (``lokal``):

* **byte-gleich am selben Ort** — eine Datei, die vor dieser Aenderung
  entstand, muss unveraendert gelesen, ausgeliefert und geloescht werden
  koennen; nichts wird umbenannt, umsortiert oder in einen Unterordner
  verschoben;
* **kein zusaetzliches Verzeichnis** — die alten Stellen schrieben direkt
  nach ``FILES_DIR/<name>``, nicht nach ``FILES_DIR/lokal/<name>``.

Belegt wird das hier an den drei Wegen, die die Karte ausdruecklich als
„bleibt gleich“ meint: Upload (``upload_file``), Auslieferung
(``/files/<name>``) und Loeschen (DSGVO/Papierkorb). Zusaetzlich wird der
Inhalt Byte fuer Byte gegen das verglichen, was die alte Fassung schrieb
(``FILES_DIR/<uuid>-<name>`` mit genau den hochgeladenen Bytes).
"""

from __future__ import annotations

import hashlib
import io

import pytest

from diakronos_app.speicher import Lokal, hole_speicher

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ── Die Ablage selbst ──────────────────────────────────────────────────────


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
    """``settings.files_dir`` auf ein tmp-Verzeichnis zeigen (wie P2c).

    Ohne das schrieben die Tests in die echte Ablage. Da die Ablage ihre
    Wurzel bei jedem Zugriff aus den Einstellungen liest, genuegt das
    Umstellen von ``settings`` — es wird nichts zwischengespeichert.
    """
    from diakronos_app import settings as settings_mod

    ziel = tmp_path / "files"
    monkeypatch.setattr(settings_mod.settings, "files_dir", str(ziel))
    return ziel


def test_default_backend_ist_lokal():
    """Ohne Einstellung ist die aktive Ablage ``Lokal``."""
    assert hole_speicher().name == "lokal"


def test_lokal_schreibt_in_die_wurzel_nicht_in_einen_unterordner(tmp_path):
    """``foto.png`` liegt als ``<wurzel>/foto.png`` — wie vorher."""
    ablage = Lokal(tmp_path)
    ablage.schreiben("foto.png", PNG)
    assert (tmp_path / "foto.png").is_file()
    assert (tmp_path / "lokal").exists() is False
    assert ablage.lesen("foto.png") == PNG


def test_lokal_liest_eine_vorhandene_datei_unveraendert(tmp_path):
    """Ein Bestand von VOR der Umstellung ist ohne Zutun lesbar."""
    (tmp_path / "alter-upload.png").write_bytes(PNG)
    ablage = Lokal(tmp_path)
    assert ablage.existiert("alter-upload.png") is True
    assert ablage.groesse("alter-upload.png") == len(PNG)
    assert ablage.lesen("alter-upload.png") == PNG
    assert ablage.pfad("alter-upload.png") == (tmp_path / "alter-upload.png")


def test_lokal_legt_unterordner_wie_bisher_an(tmp_path):
    """Dev-Modus schrieb ``files_dir/devmodus/<datum>/<name>`` — bleibt so."""
    ablage = Lokal(tmp_path)
    ablage.schreiben("devmodus/2026-10-15/x.png", PNG)
    assert (tmp_path / "devmodus" / "2026-10-15" / "x.png").is_file()


# ── Upload ────────────────────────────────────────────────────────────────


def test_upload_bleibt_byte_gleich_am_selben_ort(client, files_dir):
    """Die hochgeladenen Bytes liegen 1:1 unter ``FILES_DIR/<uuid>-<name>``."""
    roh = PNG
    antwort = client.post(
        "/api/method/upload_file",
        files={"file": ("gleich.png", io.BytesIO(roh), "image/png")},
        data={"is_private": "0"},
    )
    assert antwort.status_code == 200, antwort.text
    name = antwort.json()["message"]["file_url"].rsplit("/", 1)[1]

    geschrieben = files_dir / name
    assert geschrieben.is_file(), "Datei liegt nicht dort, wo sie vorher lag"
    assert geschrieben.read_bytes() == roh
    # ``content_hash`` ist der Hexdigest (Text), nicht die Rohbytes.
    assert hashlib.sha256(geschrieben.read_bytes()).hexdigest() == \
           antwort.json()["message"]["content_hash"]


def test_upload_meldet_denselben_pfad_wie_bisher(client, files_dir):
    """``file_url`` ist unveraendert ``/files/<uuid>-<name>``."""
    antwort = client.post(
        "/api/method/upload_file",
        files={"file": ("pfad.txt", io.BytesIO(b"x"), "text/plain")},
        data={"is_private": "0"},
    )
    url = antwort.json()["message"]["file_url"]
    assert url.startswith("/files/")
    assert url.count("/") == 2
    assert (files_dir / url.rsplit("/", 1)[1]).is_file()


# ── Loeschen ──────────────────────────────────────────────────────────────


def test_dsgvo_loeschung_entfernt_die_datei_wie_bisher(client, files_dir):
    """``dateien_entfernen`` loescht aus ``FILES_DIR`` — gleiche Wirkung."""
    from diakronos_app.dsgvo_anonymisierung import dateien_entfernen

    (files_dir).mkdir(parents=True, exist_ok=True)
    (files_dir / "zu-weg.png").write_bytes(PNG)
    assert dateien_entfernen(["/files/zu-weg.png"]) == 1
    assert not (files_dir / "zu-weg.png").exists()


def test_dsgvo_loeschung_ignoriert_pfade_ausserhalb(files_dir):
    """Ein Pfad aus der Datenbank wirkt nie ausserhalb der Wurzel."""
    from diakronos_app.dsgvo_anonymisierung import dateien_entfernen

    draussen = files_dir.parent / "draussen.png"
    draussen.write_bytes(b"geheim")
    files_dir.mkdir(parents=True, exist_ok=True)
    assert dateien_entfernen(["../draussen.png"]) == 0
    assert draussen.exists()


@pytest.mark.parametrize("wert", ["", None, "..", "a/b/c.png"])
def test_dsgvo_loeschung_mit_unsinnigem_wert_ist_folgenlos(files_dir, wert):
    from diakronos_app.dsgvo_anonymisierung import dateien_entfernen

    files_dir.mkdir(parents=True, exist_ok=True)
    assert dateien_entfernen([wert]) == 0


def test_papierkorb_entfernt_die_datei_wie_bisher(files_dir):
    """``bild_datei_entfernen`` nimmt Datei-URL ODER Dateinamen (unveraendert)."""
    from diakronos_app.papierkorb import bild_datei_entfernen

    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "beitrag.png").write_bytes(PNG)
    bild_datei_entfernen("/files/beitrag.png")
    assert not (files_dir / "beitrag.png").exists()
