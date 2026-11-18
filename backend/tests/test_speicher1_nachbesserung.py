"""SPEICHER-1 — Nachbesserungen aus dem Review (Operator, Opus, 17.11.).

Je Punkt ein Test, der am Stand VOR der Nachbesserung rot war. Die Punkte
stehen in der Review-Notiz der Karte; hier steht zu jedem:

1. **Basisordner** — ``NEXTCLOUD_ORDNER`` (Default ``/Diakronos``) wird auf
   einer frischen Nextcloud angelegt. Vorher schickte ``schreiben`` nur MKCOL
   fuer die Elternordner DES SCHLUESSELS; der Basisordner selbst fehlte, und
   jeder Upload endete in einem 409.
2. **Symlinks in der Wurzel** — ``Lokal`` loeste einen Symlink auf und lieferte
   bzw. LOESCHTE die Datei dahinter. ``main`` wies JEDEN Symlink ab
   (``stored_path``, ``formularbilder._zielpfad``, ``dsgvo.dateien_entfernen``).
   Hier: ``link.png`` -> ``real.png`` darf weder ausgeliefert noch geloescht
   werden.
3. **Eigen-Eintrag im PROPFIND** — der abgefragte Ordner selbst taucht in der
   Antwort auf; bei gleichem Namen (``a/a/b.png``) wurde der Unterordner
   doppelt gelaufen und die Datei doppelt gelistet.
4. **Ausliefern grosser Dateien** — die Route ``/files/<name>`` las hoechstens
   ``max_upload_bytes_audio`` Bytes und lieferte den Rest STILL abgeschnitten
   mit 200. Stattdessen: streamen, ``Content-Length``, ``Accept-Ranges`` und
   ``Range`` -> 206.
5. **Lokal wieder wie main** — atomares Schreiben (tmp + fsync +
   ``os.replace``) in ``Lokal.schreiben``, ``FileResponse`` fuer das Dev-Bild
   im Lokal-Modus, Namensfilter ``[A-Za-z0-9._-]+`` im Papierkorb.
6. **Pfad-Ausbruch** in ``Lokal._ziel`` -> ``UngueltigerSchluessel``.
7. **DELETE nach Zeitueberschreitung**, zweiter Versuch 404 -> geloescht.
8. **Ordner-Cache** — 404/409 beim Schreiben verwirft den Cache und legt neu an.
9. **Umzug** — ein ungueltiger Schluessel ist ein Fehler DIESER Datei;
   ``.teil-*``-Reste, ``.schreibprobe`` und die ``.schreibprobe-*``-Datei
   werden nicht kopiert.
10. **``existiert``** zaehlt Ordner nicht als Datei (wie ``Lokal``).
11. **``NextcloudZugang``** strippt das App-Passwort wie
    ``settings.nextcloud_konfiguriert``.
12. **CalDAV-Doku-Waechter** — Ausloeser um davx/thunderbird/kalender ergaenzt.

Kein Netz, kein echter Nextcloud-Server: der WebDAV-Fake kommt aus
``test_speicher1_vertrag``.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from diakronos_app.speicher import Lokal, UngueltigerSchluessel
from diakronos_app.speicher.basis import AblageFehler
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang
from diakronos_app.speicher.umzug import umzug

from test_speicher1_vertrag import BASIS, URL, FakeWebDAV, nextcloud_ablage

ZUGANG = ("diakronos", "geheim-app-passwort")

#: Die Dev-Modus-Endpunkte (DEV-Modus, nicht die Ablage).
PFAD_SITZUNG = "/api/method/diakronos.devmodus.api.sitzung_starten"
PFAD_BILD = "/api/method/diakronos.devmodus.api.bild"


@pytest.fixture()
def fake() -> FakeWebDAV:
    """Der WebDAV-Fake aus dem Vertragstest (EIN Fake, keine zweite Wahrheit)."""
    return FakeWebDAV()


@pytest.fixture()
def an(monkeypatch):
    """Dev-Modus an (wie ``test_dm1_devmodus.an``)."""
    from diakronos_app.devmodus import einstellungen

    monkeypatch.setenv("DEVMODE_ENABLED", "1")
    monkeypatch.setattr(einstellungen.settings, "devmode_enabled", True, raising=False)


# ── 1. Basisordner auf einer frischen Nextcloud ────────────────────────────


def test_frischer_basisordner_wird_angelegt(fake):
    """Ohne ``/Diakronos`` im Fake muss der erste Upload es anlegen."""
    fake.ordner = {"/remote.php/dav/files/diakronos/"}
    ablage = nextcloud_ablage(fake)
    assert ablage.schreiben("a.png", b"inhalt") == 6
    assert BASIS + "/a.png" in fake.dateien


def test_mehrstufiger_basisordner_wird_angelegt(fake):
    """``/Diakronos/Dateien``: JEDE Ebene per MKCOL, nicht nur die letzte."""
    fake.ordner = {"/remote.php/dav/files/diakronos/"}
    zugang = NextcloudZugang(URL, *ZUGANG, "/Diakronos/Dateien", versuche=1)
    client = httpx.Client(transport=httpx.MockTransport(fake),
                          auth=ZUGANG, trust_env=False)
    ablage = Nextcloud(zugang, client=client)
    ablage.wartezeiten = (0.0,)
    ablage.schreiben("tief/b.png", b"x")
    assert "/remote.php/dav/files/diakronos/Diakronos/" in fake.ordner
    assert "/remote.php/dav/files/diakronos/Diakronos/Dateien/" in fake.ordner
    assert "/remote.php/dav/files/diakronos/Diakronos/Dateien/tief/b.png" in fake.dateien

def test_basisordner_wird_nicht_doppelt_angelegt(fake):
    """Der zweite Upload schickt fuer den Basisordner kein MKCOL mehr."""
    fake.ordner = {"/remote.php/dav/files/diakronos/"}
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("a.png", b"1")
    vorher = [m for m, p in fake.anfragen if m == "MKCOL" and p.rstrip("/").endswith("Diakronos")]
    ablage.schreiben("b.png", b"2")
    nachher = [m for m, p in fake.anfragen if m == "MKCOL" and p.rstrip("/").endswith("Diakronos")]
    assert len(nachher) == len(vorher) == 1


def test_gesundheit_meldet_fehlenden_basisordner_als_anlegbar(fake):
    """``ordner_vorhanden`` heisst, was es sagt — und die Ablage legt ihn an."""
    fake.ordner = {"/remote.php/dav/files/diakronos/"}
    ablage = nextcloud_ablage(fake)
    zustand = ablage.gesundheit()
    assert zustand["backend"] == "nextcloud"
    assert zustand["erreichbar"] is True
    assert zustand["ordner_vorhanden"] is False


# ── 2. Symlinks in der Wurzel (Lokal) ──────────────────────────────────────


def _wurzel_mit_symlink(tmp_path: Path) -> tuple[Path, Path]:
    wurzel = tmp_path / "files"
    wurzel.mkdir()
    real = wurzel / "real.png"
    real.write_bytes(b"\x89PNG-echt")
    (wurzel / "link.png").symlink_to(real)
    return wurzel, real


def test_lokal_liest_keinen_symlink_in_der_wurzel(tmp_path):
    wurzel, _ = _wurzel_mit_symlink(tmp_path)
    ablage = Lokal(wurzel)
    with pytest.raises(AblageFehler):
        ablage.lesen("link.png")
    assert ablage.pfad("link.png") is None


def test_lokal_existiert_und_loescht_keinen_symlink_in_der_wurzel(tmp_path):
    """``loeschen('link.png')`` darf NICHT ``real.png`` entfernen."""
    wurzel, real = _wurzel_mit_symlink(tmp_path)
    ablage = Lokal(wurzel)
    assert ablage.existiert("link.png") is False
    assert ablage.loeschen("link.png") is False
    assert real.exists(), "der Symlink darf das Ziel nicht mitnehmen"
    assert (wurzel / "link.png").is_symlink()


def test_lokal_weist_symlink_im_unterordner_ab(tmp_path):
    """Auch ein Symlink eine Ebene tiefer ist kein Schluessel dieser Ablage."""
    wurzel = tmp_path / "files"
    (wurzel / "devmodus").mkdir(parents=True)
    real = wurzel / "real.png"
    real.write_bytes(b"x")
    (wurzel / "devmodus" / "link.png").symlink_to(real)
    ablage = Lokal(wurzel)
    with pytest.raises(AblageFehler):
        ablage.lesen("devmodus/link.png")
    assert ablage.loeschen("devmodus/link.png") is False
    assert real.exists()


def test_lokal_echte_datei_neben_dem_symlink_bleibt_nutzbar(tmp_path):
    """Die Abweisung trifft nur den Link, nicht den ganzen Ordner."""
    wurzel, _ = _wurzel_mit_symlink(tmp_path)
    ablage = Lokal(wurzel)
    assert ablage.lesen("real.png") == b"\x89PNG-echt"
    assert ablage.loeschen("real.png") is True


# ── 3. PROPFIND: Eigen-Eintrag und gleiche Namen ───────────────────────────


def test_auflisten_ueberspringt_den_eigenen_eintrag(fake):
    """``auflisten("a")`` listet ``a/b.png`` EINMAL, nicht zweimal."""
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("a/b.png", b"1")
    liste = ablage.auflisten("a")
    assert liste == ["a/b.png"]


def test_gleichnamiger_unterordner_wird_nicht_doppelt_gelaufen(fake):
    """``a/a/b.png``: der Unterordner ``a/a`` traegt denselben Namen wie oben."""
    fake.ordner = {"/remote.php/dav/files/diakronos/"}
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("a/a/b.png", b"inhalt")
    vorher = len([m for m, _ in fake.anfragen if m == "PROPFIND"])
    assert ablage.auflisten("a") == ["a/a/b.png"]
    # Genau zwei PROPFIND fuer ``a`` und ``a/a`` — kein dritter Lauf durch den
    # Eigen-Eintrag des Ordners (der hiesse beim Unterordner ``a/a`` ebenfalls
    # „a“ und wuerde ohne die Pruefung ein zweites Mal gelaufen).
    assert len([m for m, _ in fake.anfragen if m == "PROPFIND"]) - vorher == 2


def test_auflisten_auf_der_wurzel_ist_vollstaendig(fake):
    ablage = nextcloud_ablage(fake)
    for name in ("x.png", "a/b.png", "a/a/c.png"):
        ablage.schreiben(name, b"1")
    assert ablage.auflisten() == sorted(["a/a/c.png", "a/b.png", "x.png"])


# ── 4. Grosse Dateien: nie abschneiden ─────────────────────────────────────


def _datei_kopf(client, set_user, cloud, name: str, daten: bytes):
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    cloud.schreiben(name, daten)
    with SessionLocal() as sess:
        sess.add(FileModel(name="f-" + name[:8], file_name=name,
                           file_url="/files/" + name, is_private=0,
                           owner="Administrator", modified_by="Administrator"))
        sess.commit()
    set_user("Mitglied A")


@pytest.fixture()
def cloud_lokal(client, set_user, tmp_path):
    """Die Ablage fest auf ``Lokal`` (tmp) stellen — fuer die Lokal-Modus-Tests."""
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    ablage = Lokal(tmp_path / "files")
    setze_speicher(ablage)
    try:
        yield ablage
    finally:
        vergiss_speicher()


@pytest.fixture()
def cloud(fake):
    """Die Ablage fest auf Nextcloud stellen — nach dem Test wieder zurueck."""
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    ablage = nextcloud_ablage(fake)
    setze_speicher(ablage)
    try:
        yield ablage
    finally:
        vergiss_speicher()


def test_grosse_audiodatei_wird_nicht_abgeschnitten(client, set_user, cloud,
                                                    monkeypatch):
    """Datei groesser als ``max_upload_bytes_audio``: 200 MIT allen Bytes."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "max_upload_bytes_audio", 1024, raising=False)
    monkeypatch.setattr(settings, "max_upload_bytes", 1024, raising=False)
    daten = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"x" * 5000
    _datei_kopf(client, set_user, cloud, "lang.wav", daten)
    antwort = client.get("/files/lang.wav")
    assert antwort.status_code == 200, antwort.text
    assert antwort.content == daten, "die Datei wurde abgeschnitten"
    assert antwort.headers["content-length"] == str(len(daten))


def test_ausliefern_nennt_die_groesse(client, set_user, cloud, monkeypatch):
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "max_upload_bytes_audio", 1024, raising=False)
    daten = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"y" * 4000
    _datei_kopf(client, set_user, cloud, "tief.wav", daten)
    antwort = client.get("/files/tief.wav")
    assert antwort.headers["content-length"] == str(len(daten))
    assert "bytes" in antwort.headers.get("accept-ranges", "")


def test_range_anfrage_liefert_206_und_den_teil(client, set_user, cloud,
                                                monkeypatch):
    """Safari/Audio spult: ``Range`` muss als 206 mit dem Teil ankommen."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "max_upload_bytes_audio", 1024, raising=False)
    daten = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + bytes(range(256)) * 40
    _datei_kopf(client, set_user, cloud, "spul.wav", daten)
    antwort = client.get("/files/spul.wav", headers={"Range": "bytes=100-199"})
    assert antwort.status_code == 206, antwort.text
    assert antwort.content == daten[100:200]
    assert antwort.headers["content-range"] == f"bytes 100-199/{len(daten)}"


def test_kleine_datei_bleibt_200(client, set_user, cloud):
    daten = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"z" * 100
    _datei_kopf(client, set_user, cloud, "klein.wav", daten)
    antwort = client.get("/files/klein.wav")
    assert antwort.status_code == 200
    assert antwort.content == daten


# ── 5. Lokal wieder wie main ───────────────────────────────────────────────


def test_lokal_schreibt_atomar_ueber_eine_teil_datei(tmp_path, monkeypatch):
    """Kein halbes Ziel bei einem Abbruch: erst ``.teil``, dann ``os.replace``."""
    ablage = Lokal(tmp_path)
    gesetzt: list[tuple[str, str]] = []
    echt = __import__("os").replace

    def merke(quelle, ziel):
        gesetzt.append((str(quelle), str(ziel)))
        return echt(quelle, ziel)

    import diakronos_app.speicher.lokal as modul

    monkeypatch.setattr(modul.os, "replace", merke)
    ablage.schreiben("gemeinde-logo-abc.png", b"\x89PNG-inhalt")
    assert gesetzt, "es wurde nicht atomar ersetzt"
    assert ".teil" in Path(gesetzt[0][0]).name
    assert Path(gesetzt[0][1]).name == "gemeinde-logo-abc.png"
    assert not [p for p in (tmp_path).rglob("*") if ".teil" in p.name]


def test_lokal_schreiben_synct_vor_dem_umbenennen(tmp_path, monkeypatch):
    """``fsync`` vor ``os.replace`` — sonst steht nach einem Stromausfall nichts."""
    import diakronos_app.speicher.lokal as modul

    gerufen: list[int] = []
    monkeypatch.setattr(modul.os, "fsync", lambda fd: gerufen.append(fd))
    Lokal(tmp_path).schreiben("a.png", b"x")
    assert gerufen, "kein fsync vor dem Umbenennen"


def test_dm_1_png_nach_dem_schreiben_an_der_selben_stelle(tmp_path):
    """Byte-gleich am selben Ort: die Datei liegt unter ihrem Schluessel."""
    ablage = Lokal(tmp_path)
    ablage.schreiben("gemeinde-logo-x.png", b"\x89PNG-inhalt")
    assert (tmp_path / "gemeinde-logo-x.png").read_bytes() == b"\x89PNG-inhalt"


def test_devmodus_bild_route_liefert_mit_datei_antwort(client, an, tmp_path,
                                                      monkeypatch):
    """Im Lokal-Modus wieder ``FileResponse`` (ETag, Last-Modified, Range)."""
    from diakronos_app.devmodus import dienste
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "files_dir", str(tmp_path), raising=False)
    import base64

    roh = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
    gespeichert = dienste.bild_speichern(roh, "image/png")
    client.post(PFAD_SITZUNG, json={})
    antwort = client.get(PFAD_BILD, params={"pfad": gespeichert["pfad"]})
    assert antwort.status_code == 200, antwort.text
    assert antwort.content == roh
    assert antwort.headers["content-type"] == "image/png"
    assert "etag" in antwort.headers or "last-modified" in antwort.headers
    assert antwort.headers["accept-ranges"] == "bytes"


def test_papierkorb_loescht_nur_namen_mit_erlaubten_zeichen(tmp_path):
    """``bild_datei_entfernen`` filtert wieder ``[A-Za-z0-9._-]+``."""
    from diakronos_app.speicher import setze_speicher, vergiss_speicher
    from diakronos_app import papierkorb

    ablage = Lokal(tmp_path)
    ablage.schreiben("bild.png", b"x")
    ablage.schreiben("bild zwei.png", b"x")  # Leerzeichen: kein gueltiger Name
    setze_speicher(ablage)
    try:
        papierkorb.bild_datei_entfernen("/files/bild.png")
        papierkorb.bild_datei_entfernen("/files/bild zwei.png")
    finally:
        vergiss_speicher()
    assert not (tmp_path / "bild.png").exists()
    assert (tmp_path / "bild zwei.png").exists(), "fremder Name wurde geloescht"


# ── 6. Pfad-Ausbruch -> UngueltigerSchluessel ──────────────────────────────


def test_lokal_ausbruch_ist_ein_ungueltiger_schluessel(tmp_path):
    """Ein Schluessel, der aus der Wurzel fuehrt, ist ein Programmierfehler."""
    ablage = Lokal(tmp_path)
    with pytest.raises(UngueltigerSchluessel):
        ablage.schreiben("../raus.png", b"x")


def test_lokal_symlink_nach_draussen_ist_ein_ablagefehler(tmp_path):
    """Ein Link, der nach draussen zeigt: abgewiesen, als Ablagezustand."""
    draussen = tmp_path / "draussen.png"
    draussen.write_bytes(b"geheim")
    wurzel = tmp_path / "files"
    wurzel.mkdir()
    (wurzel / "link.png").symlink_to(draussen)
    with pytest.raises(AblageFehler):
        Lokal(wurzel).lesen("link.png")
    assert draussen.read_bytes() == b"geheim"


# ── 7. DELETE nach Zeitueberschreitung ────────────────────────────────────


def test_delete_nach_zeitueberschreitung_und_404_gilt_als_geloescht(fake):
    """Der erste DELETE lief in den Timeout — der zweite sieht 404 = weg."""
    fake.antworten = []
    zustand = {"erster": True}

    class NachTimeout(FakeWebDAV):
        def __call__(self, request):
            if request.method == "DELETE" and zustand["erster"]:
                zustand["erster"] = False
                self.anfragen.append(("DELETE", request.url.path))
                raise httpx.ReadTimeout("Zeitueberschreitung", request=request)
            return super().__call__(request)

    nach = NachTimeout()
    nach.dateien[BASIS + "/a.png"] = b"x"
    ablage = nextcloud_ablage(nach, versuche=2)
    assert ablage.loeschen("a.png") is True
    assert BASIS + "/a.png" not in nach.dateien


def test_delete_nach_zeitueberschreitung_und_204_gilt_als_geloescht(fake):
    zustand = {"erster": True}

    class NachTimeout(FakeWebDAV):
        def __call__(self, request):
            if request.method == "DELETE" and zustand["erster"]:
                zustand["erster"] = False
                self.anfragen.append(("DELETE", request.url.path))
                raise httpx.ReadTimeout("Zeitueberschreitung", request=request)
            return super().__call__(request)

    nach = NachTimeout()
    nach.dateien[BASIS + "/b.png"] = b"x"
    ablage = nextcloud_ablage(nach, versuche=2)
    assert ablage.loeschen("b.png") is True


def test_delete_auf_eine_echt_fehlende_datei_bleibt_false(fake):
    """Kein Timeout, echtes 404: es gab nichts zu loeschen."""
    ablage = nextcloud_ablage(fake)
    assert ablage.loeschen("fehlt.png") is False


# ── 8. Ordner-Cache nach 404/409 ──────────────────────────────────────────


def test_409_beim_schreiben_legt_den_ordner_neu_an(fake):
    """Der Ordner wurde serverseitig entfernt: Cache verwerfen, MKCOL, erneut."""
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("devmodus/a.png", b"1")
    # Jemand loescht den Ordner hinter dem Cache weg.
    fake.ordner = {BASIS + "/"}
    fake.dateien = {}
    antwort = ablage.schreiben("devmodus/b.png", b"2")
    assert antwort == 1
    assert BASIS + "/devmodus/b.png" in fake.dateien


def test_404_beim_schreiben_legt_den_ordner_neu_an(fake):
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("tief/a.png", b"1")
    fake.ordner = {BASIS + "/"}
    fake.dateien = {}
    assert ablage.schreiben("tief/b.png", b"2") == 1
    assert BASIS + "/tief/b.png" in fake.dateien


# ── 9. Umzug: ungueltiger Schluessel, Reste ───────────────────────────────


def test_umzug_meldet_ungueltigen_schluessel_und_macht_weiter(tmp_path, fake):
    """Eine kaputte Quelle haelt die anderen Dateien nicht auf."""
    quelle = Lokal(tmp_path / "files")
    quelle.schreiben("gut.png", b"ok")

    class MitBoesemSchluessel(Lokal):
        def auflisten(self, praefix=""):  # type: ignore[override]
            return ["gut.png", "../boese.png"]

    ergebnis = umzug(MitBoesemSchluessel(tmp_path / "files"), nextcloud_ablage(fake))
    assert ergebnis.uebertragen == 1
    assert [s for s, _ in ergebnis.fehler] == ["../boese.png"]
    assert "ungueltig" in ergebnis.fehler[0][1].lower()


def test_umzug_kopiert_keine_teil_dateien(tmp_path, fake):
    """``.teil``-Reste eines abgebrochenen Schreibens sind keine Dateien."""
    quelle = Lokal(tmp_path / "files")
    quelle.schreiben("echt.png", b"inhalt")
    (tmp_path / "files" / ".echt.png.teil-1234").write_bytes(b"halb")
    ergebnis = umzug(quelle, nextcloud_ablage(fake))
    assert [s for s, _ in ergebnis.fehler] == []
    ziel = nextcloud_ablage(fake)
    assert not any(".teil" in s for s in ziel.auflisten())


def test_umzug_kopiert_keine_schreibprobe(tmp_path, fake):
    quelle = Lokal(tmp_path / "files")
    quelle.schreiben("echt.png", b"inhalt")
    (tmp_path / "files" / ".schreibprobe-4242").write_bytes(b"")
    ziel = nextcloud_ablage(fake)
    umzug(quelle, ziel)
    assert ziel.auflisten() == ["echt.png"]


# ── 10. existiert() zaehlt keinen Ordner ──────────────────────────────────


def test_nextcloud_existiert_zaehlt_ordner_nicht_als_datei(fake):
    fake.ordner = {"/remote.php/dav/files/diakronos/"}
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("ordner/x.png", b"1")
    assert ablage.existiert("ordner") is False
    assert ablage.existiert("ordner/x.png") is True
    assert ablage.groesse("ordner") is None


# ── 11. App-Passwort strippen ─────────────────────────────────────────────


def test_zugang_strippt_das_app_passwort():
    """Ein Passwort mit Leerzeichen (Kopierfehler) muss trotzdem passen."""
    zugang = NextcloudZugang(URL, "diakronos", "  geheim  ")
    assert zugang.passwort == "geheim"
    assert zugang.fehlende_angaben() == []


def test_zugang_nur_leerraum_gilt_als_fehlend():
    zugang = NextcloudZugang(URL, "diakronos", "   ")
    assert zugang.passwort == ""
    assert "NEXTCLOUD_APP_PASSWORT" in zugang.fehlende_angaben()


# ── 12. CalDAV-Doku-Waechter: Ausloeser vollstaendig ──────────────────────


_CALDAV_MODUL = Path(__file__).resolve().parent / "test_login3_doku_caldav.py"


def test_waechter_erkennt_auch_davx_thunderbird_und_kalender():
    """Der Absatz-Filter muss ALLE CalDAV-Ausloeser kennen.

    Sonst genuegte ein Absatz „Kalender-Abos per Thunderbird nutzen
    App-Passwoerter“, um am Waechter vorbeizukommen — genau der Befund
    R-LOGIN-2.
    """
    quelle = _CALDAV_MODUL.read_text(encoding="utf-8")
    treffer = re.search(r"def _caldav_absaetze.*?\n\n\n", quelle, re.S)
    assert treffer, "_caldav_absaetze fehlt"
    rumpf = treffer.group(0)
    for wort in ("davx", "thunderbird", "kalender"):
        assert wort in rumpf.lower(), f"Ausloeser {wort!r} fehlt im Waechter"
