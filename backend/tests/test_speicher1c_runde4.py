"""SPEICHER-1c — Review Runde 4: leere Datei aus der Nextcloud, Verbindungsleck.

Review Runde 4 zu SPEICHER-1c (Branch ``wt/t_8c82f907``). Je Befund ein Test,
der am Stand ``0feba4a0`` rot war:

1. **Leere Datei aus der Nextcloud nie 200.** ``Nextcloud.lesen_vorn`` fragte
   mit ``Range: bytes=0-4095`` und liess nur ``404`` durch; die Antwort einer
   leeren Datei ist aber ``416`` (jeder Bereich ist unerfuellbar). Daraus wurde
   ein ``AblageFehler("HTTP 416")`` und an der Route ein ``404`` — die leere
   Datei war nicht auslieferbar. Dazu lieferte ``groesse_und_bereich`` fuer
   0 Bytes ``(0, 0, -1)``, also antwortete ein einfaches GET mit ``416`` statt
   ``200`` mit ``Content-Length: 0``.
2. **Verbindungsleck.** Bricht ``strom`` mangels Bereich ab (``ende <
   anfang``), antwortete die Route ``416``, OHNE den Generator je zu starten —
   das ``finally`` lief nie, die WebDAV-Antwort blieb offen.
3. **GET ohne ``Content-Length``** (chunked, Proxy/HTTP2): die Groesse kam als
   0 an -> ``416 */0``. Jetzt: Groesse aus ``Content-Range``, sonst aus
   ``HEAD``/``PROPFIND``, sonst ohne Laenge durchreichen (200, chunked).
4. **Komprimierung**: ``httpx`` schickt ``Accept-Encoding: gzip``; dann passt
   ``Content-Length`` nicht zu ``iter_bytes``. Lese-GETs verlangen ``identity``.
5. **``groesse()`` nur aus ``HEAD``**: fehlt dort ``Content-Length``, kommt die
   Groesse aus ``PROPFIND`` (``getcontentlength``, Depth 0).
6. **``umask``** wurde je Schreibvorgang prozessweit auf 0 gesetzt (Race in
   Threads) — jetzt EINMAL beim Modulladen gelesen.
7. **``bytes=-0``** ist syntaktisch ungueltig und wird ignoriert (200), nicht
   als 416 gewertet — der Kopf ist kein Einzelbereich (RFC 9110, 14.2).

Kein Netz, kein echter Nextcloud-Server.
"""

from __future__ import annotations

import threading

import httpx
import pytest

from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher
from diakronos_app.speicher.basis import bereich_syntax
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

from test_speicher1_vertrag import BASIS, URL, FakeWebDAV, nextcloud_ablage
from test_speicher1c_streaming import ZaehlStrom, strom_ablage


class StromFake(FakeWebDAV):
    """``FakeWebDAV``, der GET-Koerper als ECHTEN Strom ausliefert (mit close)."""

    def __init__(self) -> None:
        super().__init__()
        self.stroeme: list[ZaehlStrom] = []
        self.gesehen: list[tuple[str, str | None, str | None]] = []
        self.block = 16 * 1024

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            self.gesehen.append((
                request.url.path,
                request.headers.get("Range"),
                request.headers.get("Accept-Encoding"),
            ))
        antwort = super().__call__(request)
        if request.method != "GET" or antwort.status_code not in (200, 206):
            return antwort
        strom = ZaehlStrom(antwort.content, self.block)
        self.stroeme.append(strom)
        return httpx.Response(
            antwort.status_code, headers=dict(antwort.headers), stream=strom,
        )


@pytest.fixture()
def datei_eintrag(client, set_user):
    """Legt einen ``FileModel``-Eintrag fuer ``leer.txt`` an und meldet an."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    def anlegen() -> None:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-leer-nc", file_name="leer.txt",
                               file_url="/files/leer.txt", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")

    return anlegen


# ── 1. Leere Datei aus der NEXTCLOUD ───────────────────────────────────────


def test_leere_datei_aus_der_nextcloud_lesen_vorn_ist_leer_und_kein_fehler():
    """``lesen_vorn`` auf 0 Bytes: ``b""`` — kein ``AblageFehler("HTTP 416")``."""
    fake = fake_leer()
    ablage = nextcloud_ablage(fake, versuche=1)
    assert ablage.lesen_vorn("leer.txt", 4096) == b""


def fake_leer() -> FakeWebDAV:
    fake = FakeWebDAV()
    fake.dateien[BASIS + "/leer.txt"] = b""
    return fake


def test_leere_datei_aus_der_nextcloud_ist_ein_200_mit_null_bytes(
    client, set_user, datei_eintrag
):
    """Einfacher GET auf eine 0-Byte-Datei in der Nextcloud: 200, ``Length: 0``."""
    setze_speicher(nextcloud_ablage(fake_leer(), versuche=1))
    try:
        datei_eintrag()
        antwort = client.get("/files/leer.txt")
    finally:
        vergiss_speicher()
    assert antwort.status_code == 200, antwort.text
    assert antwort.content == b""
    assert antwort.headers["content-length"] == "0"


def test_leere_datei_in_der_nextcloud_mit_range_ist_416(client, set_user, datei_eintrag):
    setze_speicher(nextcloud_ablage(fake_leer(), versuche=1))
    try:
        datei_eintrag()
        antwort = client.get("/files/leer.txt", headers={"Range": "bytes=0-"})
    finally:
        vergiss_speicher()
    assert antwort.status_code == 416
    assert antwort.headers["content-range"] == "bytes */0"


def test_leere_datei_ohne_range_ist_auch_bei_der_ablage_200(client, set_user, datei_eintrag):
    """0 Bytes OHNE Range: ``groesse_und_bereich`` sagt ``(0, 0, -1)``.

    Der ``(0, 0, -1)``-Wert heisst „nichts auszuliefern“. Ohne ``Range`` ist
    das eine leere, aber vorhandene Datei -> ``200`` mit ``Content-Length: 0``
    (nicht ``416``) — auch bei der Nextcloud-Ablage.
    """
    from diakronos_app.speicher.basis import Basis

    ablage = nextcloud_ablage(fake_leer(), versuche=1)
    assert Basis.groesse_und_bereich(ablage, "leer.txt", None) == (0, 0, -1)
    assert Basis.groesse_und_bereich(ablage, "leer.txt", "bytes=0-") == (0, 0, -1)
    setze_speicher(ablage)
    try:
        datei_eintrag()
        antwort = client.get("/files/leer.txt")
    finally:
        vergiss_speicher()
    assert antwort.status_code == 200, f"{antwort.status_code} {antwort.headers}"
    assert antwort.content == b""
    assert antwort.headers["content-length"] == "0"


# ── 2. Verbindungsleck bei ende < anfang ───────────────────────────────────


def test_strom_ohne_bereich_schliesst_die_antwort_sofort():
    """Schrumpft die Datei auf 0 Bytes, ist die Antwort SOFORT zu.

    Die Route antwortet dann ``416`` und startet den Generator nie — ohne
    dieses Schliessen bliebe die WebDAV-Verbindung offen, bis der Garbage
    Collector die Antwort einsammelt. Der Test haelt die Antwort deshalb
    ausdruecklich am Leben (``antworten``): geschlossen ist nur, was
    ``strom`` selbst geschlossen hat.
    """
    antworten: list[httpx.Response] = []

    class AufNull(StromFake):
        """Antwortet auf den GET mit ``206``, aber ohne jeden Koerper.

        Genau der Fall „zwischen ``HEAD`` und ``GET`` geschrumpft“: der
        Server nennt noch den alten Bereich, schickt aber nichts.
        """

        def __call__(self, request):
            antwort = super().__call__(request)
            if request.method != "GET" or antwort.status_code != 206:
                return antwort
            leer = ZaehlStrom(b"", self.block)
            self.stroeme[-1] = leer
            # Der Server meldet fuer den leeren Koerper auch 0 Bytes.
            kopf = {k: v for k, v in antwort.headers.items()
                    if k.lower() != "content-length"}
            kopf["Content-Length"] = "0"
            neu = httpx.Response(206, headers=kopf, stream=leer)
            antworten.append(neu)
            return neu

    fake = AufNull()
    fake.dateien[BASIS + "/weg.bin"] = b"n" * 100
    ablage = nextcloud_ablage(fake, versuche=1)
    strom, anfang, ende = ablage.strom("weg.bin", von=0, bis=99)
    assert ende < anfang, f"kein leerer Bereich: {(anfang, ende)}"
    assert fake.stroeme, "kein GET gesehen"
    assert fake.stroeme[-1].geschlossen is True, (
        "die WebDAV-Antwort blieb offen — die Route startet den Generator nie"
    )
    assert b"".join(strom) == b""
    assert antworten and antworten[-1].is_closed, "die Antwort ist nicht zu"


def test_route_416_schliesst_die_nextcloud_antwort(client, set_user, datei_eintrag):
    """Unerfuellbarer Range aus der Nextcloud: 416, und die Antwort ist zu.

    Die Datei schrumpft zwischen ``HEAD`` (100 Bytes) und ``GET``: der GET
    antwortet ``206`` mit leerem Koerper. ``strom`` meldet dann
    ``ende < anfang``, die Route antwortet ``416`` — und der Generator laeuft
    nie, sein ``finally`` also auch nicht. Geschlossen wird deshalb in
    ``strom`` selbst.
    """
    antworten: list[httpx.Response] = []

    class AufNull(StromFake):
        def __call__(self, request):
            antwort = super().__call__(request)
            if request.method != "GET" or antwort.status_code != 206:
                return antwort
            leer = ZaehlStrom(b"", self.block)
            self.stroeme[-1] = leer
            kopf = {k: v for k, v in antwort.headers.items()
                    if k.lower() != "content-length"}
            kopf["Content-Length"] = "0"
            neu = httpx.Response(206, headers=kopf, stream=leer)
            antworten.append(neu)
            return neu

    fake = AufNull()
    fake.dateien[BASIS + "/leer.txt"] = b"n" * 100
    setze_speicher(nextcloud_ablage(fake, versuche=1))
    try:
        datei_eintrag()
        antwort = client.get("/files/leer.txt", headers={"Range": "bytes=50-"})
    finally:
        vergiss_speicher()
    assert antwort.status_code == 416, f"{antwort.status_code} {antwort.headers}"
    assert fake.stroeme, "kein GET gesehen"
    assert all(s.geschlossen for s in fake.stroeme), (
        "eine WebDAV-Antwort blieb offen"
    )
    assert antworten and all(a.is_closed for a in antworten), (
        "eine Antwort der Ablage ist nicht geschlossen"
    )


# ── 3. GET ohne Content-Length (chunked) ───────────────────────────────────


class OhneLaenge(StromFake):
    """Antwortet auf GET ohne ``Content-Length`` (wie ein Proxy/chunked)."""

    def __init__(self, *, mit_content_range: bool = False) -> None:
        super().__init__()
        self.mit_content_range = mit_content_range
        self.head_laenge = True

    def __call__(self, request):
        antwort = super().__call__(request)
        if request.method != "GET" or antwort.status_code not in (200, 206):
            return antwort
        kopf = {k: v for k, v in antwort.headers.items() if k.lower() != "content-length"}
        if not self.mit_content_range:
            kopf = {k: v for k, v in kopf.items() if k.lower() != "content-range"}
        return httpx.Response(antwort.status_code, headers=kopf,
                              stream=antwort.stream)


def test_get_ohne_content_length_ist_kein_416():
    """Chunked-GET ohne ``Content-Length``: die Datei kommt ganz (200, kein 416)."""
    fake = OhneLaenge()
    daten = b"0123456789"
    fake.dateien[BASIS + "/chunk.bin"] = daten
    ablage = nextcloud_ablage(fake, versuche=1)
    strom, anfang, ende = ablage.strom("chunk.bin")
    assert b"".join(strom) == daten
    assert (anfang, ende) == (0, len(daten) - 1), (
        f"Bereich {anfang}-{ende} statt 0-{len(daten) - 1}: die fehlende "
        "Laenge wurde als 0 gelesen"
    )


def test_get_ohne_content_length_nimmt_die_groesse_aus_content_range():
    fake = OhneLaenge(mit_content_range=True)
    daten = b"abcdefghij"
    fake.dateien[BASIS + "/chunk2.bin"] = daten
    ablage = nextcloud_ablage(fake, versuche=1)
    strom, anfang, ende = ablage.strom("chunk2.bin", von=2, bis=5, bereich=True)
    assert b"".join(strom) == daten[2:6]
    assert (anfang, ende) == (2, 5)


def test_get_ohne_content_length_an_der_route(client, set_user):
    """Die Route liefert die Datei ohne ``Content-Length`` falscher Groesse aus."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    fake = OhneLaenge()
    daten = b"RIFF\x00\x00\x00\x00WAVE" + b"a" * 500
    fake.dateien[BASIS + "/ton.wav"] = daten
    setze_speicher(strom_ablage(fake))
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-chunk", file_name="ton.wav",
                               file_url="/files/ton.wav", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")
        antwort = client.get("/files/ton.wav")
    finally:
        vergiss_speicher()
    assert antwort.status_code == 200, f"{antwort.status_code} {antwort.headers}"
    assert antwort.content == daten


# ── 4. Keine Komprimierung auf dem Lese-GET ────────────────────────────────


def test_lese_get_verlangt_identity():
    """``Accept-Encoding: identity`` — sonst passt ``Content-Length`` nicht."""
    fake = StromFake()
    fake.dateien[BASIS + "/a.bin"] = b"x" * 1000
    ablage = strom_ablage(fake)
    assert b"".join(ablage.strom("a.bin")[0]) == b"x" * 1000
    assert fake.gesehen, "kein GET gesehen"
    assert all(kopf == "identity" for _, _, kopf in fake.gesehen), (
        f"Lese-GET ohne identity: {fake.gesehen}"
    )


def test_lesen_vorn_verlangt_identity():
    fake = StromFake()
    fake.dateien[BASIS + "/b.bin"] = b"y" * 5000
    ablage = strom_ablage(fake)
    assert ablage.lesen_vorn("b.bin", 100) == b"y" * 100
    assert all(kopf == "identity" for _, _, kopf in fake.gesehen)


# ── 5. Groesse ohne HEAD-Content-Length ────────────────────────────────────


def test_groesse_faellt_auf_propfind_zurueck():
    """HEAD ohne ``Content-Length``: die Groesse kommt aus PROPFIND."""
    class OhneHeadLaenge(FakeWebDAV):
        def __call__(self, request):
            antwort = super().__call__(request)
            if request.method == "HEAD" and antwort.status_code == 200:
                return httpx.Response(200, headers=dict(antwort.headers))
            return antwort

    fake = OhneHeadLaenge()
    fake.dateien[BASIS + "/g.bin"] = b"z" * 4321
    ablage = nextcloud_ablage(fake, versuche=1)
    assert ablage.groesse("g.bin") == 4321


def test_groesse_bleibt_none_wenn_es_die_datei_nicht_gibt():
    fake = FakeWebDAV()
    ablage = nextcloud_ablage(fake, versuche=1)
    assert ablage.groesse("fehlt.bin") is None


# ── 6. umask nicht je Schreibvorgang setzen ────────────────────────────────


def test_schreiben_setzt_die_umask_nicht_prozessweit(tmp_path, monkeypatch):
    """``os.umask`` wird beim Schreiben NICHT mehr aufgerufen (Race in Threads)."""
    import diakronos_app.speicher.lokal as lokal_mod

    assert isinstance(getattr(lokal_mod, "_UMASK", None), int), (
        "die umask muss beim Modulladen einmal gelesen werden"
    )
    rufe: list[int] = []
    echt = lokal_mod.os.umask

    def mitzaehlend(maske: int) -> int:
        rufe.append(maske)
        return echt(maske)

    monkeypatch.setattr(lokal_mod.os, "umask", mitzaehlend)
    ablage = Lokal(tmp_path)
    ablage.schreiben("u.png", b"x")
    ablage.schreiben("v.png", b"y")
    assert rufe == [], f"os.umask wurde beim Schreiben aufgerufen: {rufe}"


# ── 7. bytes=-0 ist kein Einzelbereich ─────────────────────────────────────


def test_bytes_minus_null_wird_ignoriert_und_ist_kein_416(client, set_user, tmp_path):
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    daten = b"0123456789"
    ablage = Lokal(tmp_path)
    ablage.schreiben("null.txt", daten)
    setze_speicher(ablage)
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-null", file_name="null.txt",
                               file_url="/files/null.txt", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")
        antwort = client.get("/files/null.txt", headers={"Range": "bytes=-0"})
    finally:
        vergiss_speicher()
    assert antwort.status_code == 200, f"bytes=-0 ergab {antwort.status_code}"
    assert antwort.content == daten
    assert bereich_syntax("bytes=-0") is False
