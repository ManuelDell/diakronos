"""SPEICHER-1 — Vertrag der Datei-Ablage, gegen BEIDE Umsetzungen.

Was hier geprueft wird (Kartenvorgabe 6):

1. **Derselbe Vertrag** laeuft gegen ``Lokal`` (echtes tmp-Verzeichnis) und
   gegen ``Nextcloud`` (In-Process-WebDAV-Fake ueber ``httpx.MockTransport``).
   Kein Netz, kein echter Nextcloud-Server: der Transport antwortet im
   Prozess, die Adressen sind erfunden.
2. **Pfad-Traversal** — dieselben boesen Schluessel muessen in BEIDEN
   Umsetzungen abgewiesen werden, und zwar bevor irgendetwas geschrieben wird.
3. **Fehlerfaelle**: 401 (Zugangsdaten), 404 (fehlt), 507 (Speicher voll),
   Zeitueberschreitung, 5xx mit Wiederholung.
4. **Nextcloud-Besonderheiten**: MKCOL legt Elternordner an, eine
   Wiederholung nach 5xx gelingt, ``pfad()`` gibt es nicht (nur ``None``),
   und das App-Passwort taucht in keiner Fehlermeldung auf.

Der Fake
--------
``FakeWebDAV`` haelt einen kleinen Dateibaum im Speicher und beantwortet
PUT/GET/HEAD/DELETE/MKCOL/PROPFIND wie Nextcloud. Er ist absichtlich streng:
ein PUT in einen fehlenden Ordner ergibt 409 (so verhaelt sich WebDAV), damit
der MKCOL-Weg wirklich geprueft wird und nicht zufaellig durchgeht.
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable

import httpx
import pytest

from diakronos_app.speicher import (
    Lokal,
    NichtErlaubt,
    NichtGefunden,
    SpeicherNichtErreichbar,
    UngueltigerSchluessel,
)
from diakronos_app.speicher.basis import AblageFehler
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang
from diakronos_app.speicher.schluessel import normalisiere

BASIS = "/remote.php/dav/files/diakronos/Diakronos"
URL = "https://cloud.example.org"

#: Boese Schluessel — in BEIDEN Umsetzungen gleich abzuweisen.
BOESE = [
    "../ausserhalb.png",
    "a/../../b.png",
    "/etc/passwd",
    "//fremder-host/x.png",
    "C:/windows/x.png",
    "a\\b.png",
    "",
    "   ",
    "a/\x00b.png",
    "x" * 2000,
]


# ── Der WebDAV-Fake ────────────────────────────────────────────────────────


class FakeWebDAV:
    """Minimaler WebDAV-Server im Prozess (nur was die Ablage benutzt)."""

    def __init__(self) -> None:
        #: Pfad -> Bytes. Ordnernamen tragen einen abschliessenden Schraegstrich.
        self.dateien: dict[str, bytes] = {}
        self.ordner: set[str] = {BASIS + "/"}
        #: Erzwingt Statuscodes je Methode (Reihenfolge: erster Treffer gilt).
        self.antworten: list[tuple[str, int]] = []
        self.anfragen: list[tuple[str, str]] = []
        self.passwort = "geheim-app-passwort"
        self.benutzer = "diakronos"
        self.zeitueberschreitung = False
        self.speicher_voll = False

    # — Hilfen fuer den Aufbau eines Bestands —
    def lege_an(self, pfad: str, daten: bytes) -> None:
        self.dateien[BASIS + "/" + pfad] = daten
        teile = (BASIS + "/" + pfad).split("/")
        for i in range(3, len(teile)):
            self.ordner.add("/".join(teile[:i]) + "/")

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen.append((request.method, request.url.path))
        if self.zeitueberschreitung:
            raise httpx.ReadTimeout("Zeitueberschreitung", request=request)
        # Anmeldung wie bei Nextcloud: Basic-Auth gegen das App-Passwort.
        import base64

        kopf = request.headers.get("Authorization", "")
        erwartet = "Basic " + base64.b64encode(
            f"{self.benutzer}:{self.passwort}".encode()
        ).decode()
        if kopf != erwartet:
            return httpx.Response(401, text="Unauthorized")
        for methode, status in list(self.antworten):
            if methode == request.method:
                self.antworten.remove((methode, status))
                if status == 500 and request.method in ("PUT", "GET"):
                    # Beim Wiederholen soll es klappen: nur EIN Fehler.
                    pass
                return httpx.Response(status, text="erzwungen")
        if self.speicher_voll and request.method == "PUT":
            return httpx.Response(507, text="Insufficient Storage")
        pfad = request.url.path
        if request.method == "MKCOL":
            ziel = pfad.rstrip("/") + "/"
            if ziel in self.ordner:
                return httpx.Response(405)
            # Der Elternordner ist die naechste Ebene darueber. Fehlt sie,
            # antwortet WebDAV mit 409 (Conflict) — genau der Fall, den
            # ``_ordner_anlegen`` durch die Reihenfolge von oben nach unten
            # vermeidet.
            eltern = ziel.rstrip("/").rsplit("/", 1)[0] + "/"
            if eltern not in self.ordner:
                return httpx.Response(409)
            self.ordner.add(ziel)
            return httpx.Response(201)
        if request.method in ("PUT", "GET", "HEAD", "DELETE"):
            ist_ordner = pfad.rstrip("/") + "/" in self.ordner
            if ist_ordner and request.method == "DELETE":
                return httpx.Response(204)
            if ist_ordner and request.method in ("GET", "HEAD"):
                # Wie Nextcloud: ein Ordner antwortet mit 200 und dem Typ
                # ``httpd/unix-directory`` — KEINE Datei (Review-Punkt 10).
                return httpx.Response(
                    200, content=b"" if request.method == "HEAD" else b"<html>",
                    headers={"Content-Type": "httpd/unix-directory"},
                )
            if pfad not in self.dateien and request.method != "PUT":
                return httpx.Response(404)
            if request.method == "PUT":
                eltern = pfad.rsplit("/", 1)[0] + "/"
                if eltern not in self.ordner:
                    return httpx.Response(409)
                self.dateien[pfad] = request.content
                return httpx.Response(201)
            if request.method == "DELETE":
                del self.dateien[pfad]
                return httpx.Response(204)
            daten = self.dateien[pfad]
            bereich = request.headers.get("Range")
            if bereich and request.method == "GET":
                m = re.match(r"bytes=(\d*)-(\d*)$", bereich.strip())
                if not m:
                    return httpx.Response(416, headers={
                        "Content-Range": f"bytes */{len(daten)}"})
                anfang, ende = m.group(1), m.group(2)
                if not anfang:
                    teil = daten[max(0, len(daten) - int(ende)):]
                else:
                    von = int(anfang)
                    bis = int(ende) if ende else len(daten) - 1
                    if von >= len(daten):
                        return httpx.Response(416, headers={
                            "Content-Range": f"bytes */{len(daten)}"})
                    teil = daten[von:bis + 1]
                von_eff = len(daten) - len(teil) if not anfang else int(anfang)
                return httpx.Response(
                    206, content=teil,
                    headers={"Content-Length": str(len(teil)),
                             "Content-Range": f"bytes {von_eff}-{von_eff + len(teil) - 1}/{len(daten)}",
                             "Accept-Ranges": "bytes"},
                )
            return httpx.Response(
                200, content=daten,
                headers={"Content-Length": str(len(daten)), "Accept-Ranges": "bytes"},
            )
        if request.method == "PROPFIND":
            ordner = pfad if pfad.endswith("/") else pfad + "/"
            if ordner not in self.ordner:
                return httpx.Response(404)
            tiefe = request.headers.get("Depth", "0")
            eintraege = [ordner]
            if tiefe != "0":
                for o in sorted(self.ordner):
                    if o != ordner and o.startswith(ordner):
                        if "/" not in o[len(ordner):].rstrip("/"):
                            eintraege.append(o)
                for d in sorted(self.dateien):
                    if d.startswith(ordner) and "/" not in d[len(ordner):]:
                        eintraege.append(d)
            xml = ['<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">']
            for e in eintraege:
                ist_ordner = e.endswith("/")
                xml.append(
                    f"<d:response><d:href>{e}</d:href><d:propstat><d:prop>"
                    + ("<d:resourcetype><d:collection/></d:resourcetype>"
                       if ist_ordner else "<d:resourcetype/>")
                    + "</d:prop><d:status>HTTP/1.1 200 OK</d:status>"
                    "</d:propstat></d:response>"
                )
            xml.append("</d:multistatus>")
            return httpx.Response(207, text="".join(xml))
        return httpx.Response(405)


def nextcloud_ablage(fake: FakeWebDAV, **kwargs) -> Nextcloud:
    """``Nextcloud`` gegen den Fake (kein Netz)."""
    zugang = NextcloudZugang(
        URL, fake.benutzer, fake.passwort, "/Diakronos",
        timeout=5.0, transfer_timeout=5.0, versuche=kwargs.pop("versuche", 3),
    )
    client = httpx.Client(transport=httpx.MockTransport(fake),
                          auth=(zugang.benutzer, zugang.passwort),
                          trust_env=False)
    ablage = Nextcloud(zugang, client=client)
    ablage.wartezeiten = (0.0, 0.0, 0.0)  # keine echten Pausen im Test
    return ablage


@pytest.fixture(params=["lokal", "nextcloud"])
def ablage(request, tmp_path):
    """Dieselben Tests gegen BEIDE Umsetzungen (der Vertrag)."""
    if request.param == "lokal":
        return Lokal(tmp_path)
    return nextcloud_ablage(FakeWebDAV())


@pytest.fixture()
def fake() -> FakeWebDAV:
    return FakeWebDAV()


# ── 1. Der Vertrag ─────────────────────────────────────────────────────────


def test_schreiben_lesen_rundlauf(ablage):
    assert ablage.schreiben("foto.png", b"\x89PNG-kopf") == 9
    assert ablage.existiert("foto.png") is True
    assert ablage.groesse("foto.png") == 9
    assert ablage.lesen("foto.png") == b"\x89PNG-kopf"


def test_unterordner_werden_angelegt(ablage):
    ablage.schreiben("devmodus/2026-10-15/bild.png", b"inhalt")
    assert ablage.existiert("devmodus/2026-10-15/bild.png")
    assert "devmodus/2026-10-15/bild.png" in ablage.auflisten()
    assert "devmodus/2026-10-15/bild.png" in ablage.auflisten("devmodus")


def test_auflisten_sortiert_und_ist_vollstaendig(ablage):
    for name in ("b.png", "a.png", "devmodus/x/c.png"):
        ablage.schreiben(name, name.encode())
    assert ablage.auflisten() == sorted(["b.png", "a.png", "devmodus/x/c.png"])


def test_oeffnen_liefert_kopf_und_ganzes(ablage):
    ablage.schreiben("text.txt", b"0123456789")
    with ablage.oeffnen("text.txt") as quelle:
        assert quelle.lesen_vorn(3) == b"012"
        # Zweiter Aufruf beginnt wieder vorn (Schnueffel-Fall).
        assert quelle.lesen_vorn(5) == b"01234"
        assert quelle.ganz() == b"0123456789"
        assert quelle.groesse == 10


def test_oeffnen_strom_liefert_alles(ablage):
    roh = bytes(range(256)) * 1000
    ablage.schreiben("gross.bin", roh)
    with ablage.oeffnen("gross.bin") as quelle:
        gesammelt = b"".join(quelle.strom())
    assert gesammelt == roh


def test_loeschen_meldet_ob_es_etwas_gab(ablage):
    ablage.schreiben("weg.png", b"x")
    assert ablage.loeschen("weg.png") is True
    assert ablage.loeschen("weg.png") is False
    assert ablage.existiert("weg.png") is False


def test_lesen_fehlender_datei_ist_nichtgefunden(ablage):
    with pytest.raises(NichtGefunden):
        ablage.oeffnen("gibtsnicht.png")
    assert ablage.groesse("gibtsnicht.png") is None


def test_ueberschreiben_ersetzt_den_inhalt(ablage):
    ablage.schreiben("a.txt", b"alt")
    ablage.schreiben("a.txt", b"neu-und-laenger")
    assert ablage.lesen("a.txt") == b"neu-und-laenger"
    assert ablage.groesse("a.txt") == 15


def test_gesundheit_meldet_erreichbar(ablage):
    zustand = ablage.gesundheit()
    assert zustand["backend"] == ablage.name
    assert zustand["erreichbar"] is True


# ── 2. Pfad-Traversal ──────────────────────────────────────────────────────


@pytest.mark.parametrize("boese", BOESE)
def test_boese_schluessel_werden_abgewiesen(ablage, boese):
    with pytest.raises(UngueltigerSchluessel):
        ablage.schreiben(boese, b"x")


@pytest.mark.parametrize("boese", BOESE)
def test_boese_schluessel_werden_auch_beim_lesen_abgewiesen(ablage, boese):
    """Lesen, Pruefen, Loeschen: derselbe Schluessel ist ueberall ungueltig."""
    # ``pfad`` gibt es nur lokal (Nextcloud: immer ``None``) — deshalb hier
    # die vier Methoden, die JEDE Umsetzung hat.
    for aufruf in (ablage.existiert, ablage.groesse, ablage.loeschen, ablage.oeffnen):
        with pytest.raises(UngueltigerSchluessel):
            aufruf(boese)


@pytest.mark.parametrize("boese", BOESE)
def test_boese_schluessel_auch_fuer_pfad_auf_lokal(tmp_path, boese):
    with pytest.raises(UngueltigerSchluessel):
        Lokal(tmp_path).pfad(boese)


def test_normalisierung_ist_eindeutig():
    assert normalisiere("a//b/./c.png") == "a/b/c.png"
    # Leerraum aussen wird entfernt — er entsteht beim Zusammensetzen und
    # bedeutet nichts. Ein fuehrender Schraegstrich bleibt dagegen ABSOLUT
    # (siehe eigener Test): aus "/etc/passwd" darf nie ein Dateiname werden.
    assert normalisiere(" a/b.png ") == "a/b.png"
    with pytest.raises(UngueltigerSchluessel):
        normalisiere("/a/b.png")
    with pytest.raises(UngueltigerSchluessel):
        normalisiere(" /a/b.png ")


def test_lokal_schreibt_nichts_ausserhalb(tmp_path):
    ablage = Lokal(tmp_path)
    with pytest.raises(UngueltigerSchluessel):
        ablage.schreiben("../draussen.png", b"x")
    assert not (tmp_path.parent / "draussen.png").exists()


def test_nextcloud_schreibt_bei_boesem_schluessel_gar_nicht(fake):
    ablage = nextcloud_ablage(fake)
    with pytest.raises(UngueltigerSchluessel):
        ablage.schreiben("../../etc/passwd", b"x")
    assert fake.anfragen == []


def test_lokal_weist_symlink_nach_draussen_ab(tmp_path):
    """Ein Symlink INNERHALB der Wurzel, der nach draussen zeigt, gilt nicht.

    Review-Punkt 2: ``main`` wies JEDEN Symlink ab (``stored_path``,
    ``formularbilder._zielpfad``, ``dsgvo.dateien_entfernen``). ``_ziel``
    prueft die Pfadstuecke deshalb VOR ``resolve()`` — sonst loeste es den
    Link auf und lieferte (bzw. loeschte!) die Datei dahinter.

    ``pfad()`` meldet dann ``None`` („hier ist keine Datei“), ``oeffnen``
    wirft ``AblageFehler``. Gelesen wird nie eine Datei von ausserhalb.
    """
    draussen = tmp_path / "draussen.png"
    draussen.write_bytes(b"geheim")
    wurzel = tmp_path / "files"
    wurzel.mkdir()
    (wurzel / "link.png").symlink_to(draussen)
    ablage = Lokal(wurzel)
    assert ablage.pfad("link.png") is None
    with pytest.raises(AblageFehler):
        ablage.lesen("link.png")
    assert draussen.read_bytes() == b"geheim"


# ── 3. Fehlerfaelle der Nextcloud ──────────────────────────────────────────


def test_nextcloud_falsches_passwort_ist_nicht_erlaubt(fake):
    """Ein falsches App-Passwort ergibt 401 -> ``NichtErlaubt``, keine Kopie."""
    falsch = NextcloudZugang(URL, fake.benutzer, "ein-anderes", "/Diakronos",
                             versuche=1)
    client = httpx.Client(transport=httpx.MockTransport(fake),
                          auth=(falsch.benutzer, falsch.passwort), trust_env=False)
    ablage = Nextcloud(falsch, client=client)
    ablage.wartezeiten = (0.0,)
    with pytest.raises(NichtErlaubt):
        ablage.schreiben("a.png", b"x")


def test_nextcloud_403_ist_nicht_erlaubt(fake):
    fake.antworten = [("PUT", 403)]
    ablage = nextcloud_ablage(fake)
    with pytest.raises(NichtErlaubt):
        ablage.schreiben("a.png", b"x")


def test_nextcloud_507_speicher_voll_ist_verstaendlich(fake):
    fake.speicher_voll = True
    ablage = nextcloud_ablage(fake)
    with pytest.raises(AblageFehler) as fehler:
        ablage.schreiben("a.png", b"x")
    assert "Speicher" in str(fehler.value)
    assert "507" in str(fehler.value)


def test_nextcloud_507_wird_nicht_wiederholt(fake):
    """Ein voller Speicher wird in den naechsten Sekunden nicht leerer."""
    fake.speicher_voll = True
    ablage = nextcloud_ablage(fake)
    with pytest.raises(AblageFehler):
        ablage.schreiben("a.png", b"x")
    assert [m for m, _ in fake.anfragen].count("PUT") == 1


def test_nextcloud_zeitueberschreitung_ist_nicht_erreichbar(fake):
    fake.zeitueberschreitung = True
    ablage = nextcloud_ablage(fake, versuche=2)
    with pytest.raises(SpeicherNichtErreichbar) as fehler:
        ablage.schreiben("a.png", b"x")
    assert "nicht erreichbar" in str(fehler.value)


def test_nextcloud_5xx_wird_wiederholt_und_gelingt(fake):
    fake.antworten = [("PUT", 503), ("PUT", 502)]
    ablage = nextcloud_ablage(fake, versuche=3)
    assert ablage.schreiben("a.png", b"inhalt") == 6
    assert ablage.lesen("a.png") == b"inhalt"
    assert [m for m, _ in fake.anfragen].count("PUT") == 3


def test_nextcloud_dauerhaftes_5xx_ergibt_nicht_erreichbar(fake):
    fake.antworten = [("PUT", 503)] * 5
    ablage = nextcloud_ablage(fake, versuche=2)
    with pytest.raises(SpeicherNichtErreichbar):
        ablage.schreiben("a.png", b"x")


def test_nextcloud_404_beim_lesen_ist_nichtgefunden(fake):
    ablage = nextcloud_ablage(fake)
    with pytest.raises(NichtGefunden):
        ablage.oeffnen("fehlt.png")
    assert ablage.existiert("fehlt.png") is False
    assert ablage.loeschen("fehlt.png") is False


def test_nextcloud_nicht_eingerichtet_meldet_fehlende_angaben():
    """Ohne Adresse/Benutzer/Passwort: klare Meldung, KEIN Wert im Text."""
    zugang = NextcloudZugang("", "", "")
    ablage = Nextcloud(zugang)
    ablage.wartezeiten = (0.0,)
    with pytest.raises(NichtErlaubt) as fehler:
        ablage.schreiben("a.png", b"x")
    text = str(fehler.value)
    assert "NEXTCLOUD_URL" in text and "NEXTCLOUD_APP_PASSWORT" in text
    # Der Wert selbst steht nirgends (es ist keiner gesetzt — und bliebe es).
    assert zugang.passwort == ""


def test_nextcloud_passwort_erscheint_in_keiner_meldung(fake):
    fake.antworten = [("PUT", 500)] * 3
    ablage = nextcloud_ablage(fake, versuche=2)
    with pytest.raises(AblageFehler) as fehler:
        ablage.schreiben("a.png", b"x")
    assert fake.passwort not in str(fehler.value)


def test_nextcloud_hat_keinen_lokalen_pfad(fake):
    """Bei Nextcloud gibt es keinen Dateipfad — wer ihn braucht, holt Kopie."""
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("a.png", b"inhalt")
    assert ablage.pfad("a.png") is None
    pfad, kopiert = ablage.temporaerdatei("a.png")
    try:
        assert kopiert is True
        with open(pfad, "rb") as fh:  # noqa: PTH123
            assert fh.read() == b"inhalt"
    finally:
        import os

        os.unlink(pfad)


def test_lokal_temporaerdatei_kopiert_nicht(tmp_path):
    ablage = Lokal(tmp_path)
    ablage.schreiben("a.png", b"inhalt")
    pfad, kopiert = ablage.temporaerdatei("a.png")
    assert kopiert is False
    assert pfad.read_bytes() == b"inhalt"


# ── 4. MKCOL: Ordner bei Bedarf ────────────────────────────────────────────


def test_nextcloud_legt_fehlende_ordner_an(fake):
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("devmodus/2026-10-15/tief/bild.png", b"x")
    assert BASIS + "/devmodus/" in fake.ordner
    assert BASIS + "/devmodus/2026-10-15/" in fake.ordner
    assert BASIS + "/devmodus/2026-10-15/tief/" in fake.ordner
    assert fake.dateien[BASIS + "/devmodus/2026-10-15/tief/bild.png"] == b"x"


def test_nextcloud_angelegter_ordner_wird_gemerkt(fake):
    """Zweites Schreiben in denselben Ordner schickt kein MKCOL mehr."""
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("devmodus/a.png", b"1")
    vorher = [m for m, _ in fake.anfragen].count("MKCOL")
    ablage.schreiben("devmodus/b.png", b"2")
    assert [m for m, _ in fake.anfragen].count("MKCOL") == vorher


def test_nextcloud_vorhandener_ordner_ist_kein_fehler(fake):
    """405 auf MKCOL heisst „gibt es schon“ (RFC 4918, 9.3.1) — kein Fehler."""
    fake.ordner.add(BASIS + "/devmodus/")
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("devmodus/x.png", b"1")
    assert BASIS + "/devmodus/x.png" in fake.dateien
    # Das MKCOL lief und wurde als „gibt es schon“ verbucht.
    assert ("MKCOL", BASIS + "/devmodus") in fake.anfragen or \
           ("MKCOL", BASIS + "/devmodus/") in fake.anfragen


# ── 5. Adressbau (Nextcloud-Links bleiben im Backend) ──────────────────────


def test_webdav_adresse_wird_korrekt_gebaut():
    zugang = NextcloudZugang(URL, "diakronos", "x", "/Diakronos")
    assert zugang.basis() == URL + BASIS
    assert zugang.datei_url("devmodus/a b.png") == (
        URL + BASIS + "/devmodus/a%20b.png"
    )


def test_ordner_mit_punkt_punkt_ist_ein_konfigurationsfehler():
    with pytest.raises(ValueError):
        NextcloudZugang(URL, "diakronos", "x", "/Diakronos/../../etc")


def test_leerer_ordner_bleibt_erlaubt():
    zugang = NextcloudZugang(URL, "diakronos", "x", "")
    assert zugang.basis() == URL + "/remote.php/dav/files/diakronos"


def test_lesen_und_schreiben_nutzt_die_konfigurierte_basis(fake):
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("a.png", b"1")
    assert fake.anfragen[0][0] == "MKCOL" or fake.anfragen[0][0] == "PUT"
    assert all(p.startswith("/remote.php/dav/files/diakronos") for _, p in fake.anfragen)


# ── 6. Bestandsliste ueber PROPFIND ────────────────────────────────────────


def test_nextcloud_auflisten_geht_ueber_ordner(fake):
    ablage = nextcloud_ablage(fake)
    ablage.schreiben("a.png", b"1")
    ablage.schreiben("devmodus/b.png", b"2")
    assert ablage.auflisten() == ["a.png", "devmodus/b.png"]
    assert ablage.auflisten("devmodus") == ["devmodus/b.png"]


def test_nextcloud_auflisten_fehlender_ordner_ist_leer(fake):
    ablage = nextcloud_ablage(fake)
    assert ablage.auflisten("gibtsnicht") == []


# ── 7. Grosser Inhalt (Strom) ──────────────────────────────────────────────


def test_grosse_datei_geht_durch_beide_ablagen(tmp_path, fake):
    """2 MB durch beide Umsetzungen — Pruefsumme muss stimmen."""
    roh = hashlib.sha256(b"x").digest() * 65300  # ~2 MB
    for ablage in (Lokal(tmp_path), nextcloud_ablage(fake)):
        ablage.schreiben("gross.bin", roh)
        assert hashlib.sha256(ablage.lesen("gross.bin")).digest() == hashlib.sha256(roh).digest()
