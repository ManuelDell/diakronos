"""SPEICHER-1c — Auslieferung streamt WIRKLICH, Schreiben ist robust.

Review Runde 3 zu SPEICHER-1. Je Befund ein Test, der am Ausgangsstand
(``wt/t_9b14ee2f``) rot war:

1. **Kein echtes Streaming.** ``Nextcloud._anfrage`` holte die Antwort ohne
   ``stream=True``; ``httpx`` las den ganzen Koerper, BEVOR ``iter_bytes`` den
   ersten Block lieferte (Probe: 10 MB vor dem ersten Block). Hier zaehlt der
   Fake-Transport die Bytes, die beim ersten Block schon uebertragen sind, und
   ob die Antwort geschlossen wird, wenn der Verbraucher abbricht.
2. **Kopf-Lesen laedt die ganze Datei.** ``files._datei_daten_begrenzt`` las
   den 4096-Byte-Kopf ueber ``oeffnen`` -> ``BytesQuelle(antwort.content)``:
   ein ganzer GET fuer 4 KiB. Jetzt ein gestreamter GET mit
   ``Range: bytes=0-4095``, der nach dem Ausschnitt abbricht (Server ohne
   Range-Unterstuetzung werden nicht ausgelesen).
3. **Leere Datei** ist ``200`` mit 0 Bytes — nicht ``416``.
4. **Temp-Name je Prozess geteilt** (``.<name>.teil-<pid>``): zwei Threads,
   dieselbe Datei -> gemischte Bytes bzw. ``FileNotFoundError``.
5. **Aufraeumen nur bei ``OSError``**: bei ``ValueError``/Abbruch der Quelle
   blieb ``.x.png.teil-*`` liegen.
6. **Ungueltiger Range** (``bytes=0-0,5-9``, ``items=0-5``) ergibt die GANZE
   Datei (200), nicht 416 (RFC 9110: 416 nur fuer syntaktisch gueltige,
   unerfuellbare Einzelbereiche).
7. **Datei schrumpft zwischen HEAD und GET**: kein ``206 bytes 0--1/N``.
8. **Range an WebDAV** nur, wenn der Client einen geschickt hat.
9. **``_ist_ordner``**: ``text/html`` versteckt keine Datei.

Kein Netz, kein echter Nextcloud-Server.
"""

from __future__ import annotations

import threading

import httpx
import pytest

from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher
from diakronos_app.speicher.basis import AblageFehler, _parse_bereich
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

from test_speicher1_vertrag import BASIS, URL, FakeWebDAV, nextcloud_ablage

ZUGANG = ("diakronos", "geheim-app-passwort")
BLOCK = 256 * 1024  # ``basis.BLOCKGROESSE``


# ── Zaehlender Datenstrom (ein echter Strom, kein ``content=``) ────────────


class ZaehlStrom(httpx.SyncByteStream):
    """Ein Antwortkoerper, der mitzaehlt, wie viele Bytes der Abnehmer geholt hat.

    ``httpx.Response(content=...)`` wird im Konstruktor KOMPLETT gelesen und
    ist damit ein fertiger Puffer — genau der Fall, den diese Karte behebt.
    Deshalb hier ein echter ``SyncByteStream``: er liefert Block fuer Block und
    merkt sich alles, was der Abnehmer tatsaechlich abholt.
    """

    def __init__(self, daten: bytes, block: int = BLOCK) -> None:
        self.daten = daten
        self.block = block
        self.gelesen = 0
        self.bloecke = 0
        self.geschlossen = False
        #: Statuscode der Antwort, zu der dieser Strom gehoert (nur Diagnose).
        self.status_code = 200

    @property
    def gesamt(self) -> int:
        return len(self.daten)

    def __iter__(self):
        while self.gelesen < len(self.daten):
            anfang = self.gelesen
            self.gelesen = min(len(self.daten), anfang + self.block)
            self.bloecke += 1
            yield self.daten[anfang:self.gelesen]

    def close(self) -> None:
        self.geschlossen = True


class StromFake(FakeWebDAV):
    """``FakeWebDAV``, der Dateien als ECHTEN Strom ausliefert.

    Kopfzeilen und Statuscodes kommen unveraendert vom Vertrags-Fake; nur der
    Koerper eines ``GET`` auf eine vorhandene Datei ist ein ``ZaehlStrom``,
    damit ein Test sehen kann, wie viel vor dem ersten Block uebertragen wurde.
    """

    def __init__(self) -> None:
        super().__init__()
        #: Der Strom der letzten GET-Antwort mit Koerper.
        self.letzter_strom: ZaehlStrom | None = None
        self.stroeme: list[ZaehlStrom] = []
        #: Wenn True, antwortet der Server NICHT auf ``Range`` (200 alles).
        self.ignoriert_range = False
        #: Blockgroesse des ausgelieferten Stroms. Klein wie ein echter
        #: Socket-Lesevorgang — ``iter_bytes(n)`` kann einen Block NICHT
        #: weiter zerteilen, ein 256-KiB-Block waere also immer ganz weg.
        self.block = 16 * 1024

    def __call__(self, request: httpx.Request) -> httpx.Response:
        antwort = super().__call__(request)
        if request.method != "GET" or antwort.status_code not in (200, 206):
            return antwort
        # Der Koerper des Vertrags-Fakes ist die (ggf. gekuerzte) Datei.
        daten = antwort.content
        if self.ignoriert_range and request.headers.get("Range"):
            # Ein Server ohne Range-Unterstuetzung: 200 und die GANZE Datei.
            daten = self.dateien[request.url.path]
            antwort = httpx.Response(
                200,
                headers={"Content-Length": str(len(daten)), "Accept-Ranges": "none"},
            )
        strom = ZaehlStrom(daten, self.block)
        strom.status_code = antwort.status_code  # nur zur Diagnose
        self.letzter_strom = strom
        self.stroeme.append(strom)
        return httpx.Response(
            antwort.status_code,
            headers=dict(antwort.headers),
            stream=strom,
        )


def strom_ablage(fake: FakeWebDAV, **kwargs) -> Nextcloud:
    zugang = NextcloudZugang(
        URL, fake.benutzer, fake.passwort, "/Diakronos",
        timeout=5.0, transfer_timeout=5.0, versuche=kwargs.pop("versuche", 1),
    )
    client = httpx.Client(transport=httpx.MockTransport(fake),
                          auth=(zugang.benutzer, zugang.passwort),
                          trust_env=False)
    ablage = Nextcloud(zugang, client=client)
    ablage.wartezeiten = (0.0,)
    return ablage


@pytest.fixture()
def fake() -> FakeWebDAV:
    return FakeWebDAV()


# ── 1. Echtes Streaming ────────────────────────────────────────────────────


def test_erster_block_kommt_bevor_der_rest_gelesen_ist():
    """10 MB: beim ersten Block sind nur ein paar Bloecke uebertragen.

    Ohne ``stream=True`` laese ``httpx`` vor dem ersten Block die ganzen
    10 MB — der Test misst genau das.
    """
    fake = StromFake()
    daten = b"x" * (10 * 1024 * 1024)
    fake.dateien[BASIS + "/gross.bin"] = daten
    ablage = strom_ablage(fake)

    strom, von, bis = ablage.strom("gross.bin")
    iterator = iter(strom)
    erster = next(iterator)
    assert erster, "der Strom lieferte keinen Block"
    # Vor dem ersten Block darf hoechstens ein Block (plus Puffer) geflogen sein.
    assert fake.letzter_strom is not None
    assert fake.letzter_strom.gelesen <= 2 * len(erster), (
        f"{fake.letzter_strom.gelesen} Bytes vor dem ersten Block — "
        "die Antwort wurde komplett gelesen (kein Streaming)"
    )
    rest = b"".join(iterator)
    assert len(erster) + len(rest) == len(daten)


def test_strom_wird_bei_abbruch_des_abnehmers_geschlossen():
    """``StreamingResponse`` bricht den Generator ab -> Antwort ``close()``."""
    fake = StromFake()
    fake.dateien[BASIS + "/gross.bin"] = b"y" * (4 * 1024 * 1024)
    ablage = strom_ablage(fake)

    strom, _, _ = ablage.strom("gross.bin")
    iterator = iter(strom)
    next(iterator)  # genau ein Block, dann aufgeben
    iterator.close()  # wie es StreamingResponse bei einem Client-Abbruch tut

    assert fake.letzter_strom is not None
    assert fake.letzter_strom.geschlossen is True, "die WebDAV-Antwort blieb offen"
    assert fake.letzter_strom.gelesen < fake.letzter_strom.gesamt


def test_kompletter_strom_wird_am_ende_geschlossen():
    fake = StromFake()
    fake.dateien[BASIS + "/klein.bin"] = b"z" * 1000
    ablage = strom_ablage(fake)
    strom, _, _ = ablage.strom("klein.bin")
    assert b"".join(strom) == b"z" * 1000
    assert fake.letzter_strom is not None
    assert fake.letzter_strom.geschlossen is True


def test_lesen_schliesst_die_antwort(fake):
    """Auch der einfache Weg (``lesen``) laesst keine Verbindung offen."""
    fake2 = StromFake()
    fake2.dateien[BASIS + "/a.png"] = b"inhalt"
    ablage = strom_ablage(fake2)
    assert ablage.lesen("a.png") == b"inhalt"
    assert fake2.letzter_strom is not None
    assert fake2.letzter_strom.geschlossen is True


# ── 2. Kopf-Lesen laedt nicht die ganze Datei ──────────────────────────────


def test_kopf_lesen_uebertraegt_nur_den_ausschnitt():
    """4 KiB Kopf aus einer 5-MB-Datei: hoechstens Bereich + 4096 Bytes."""
    from diakronos_app import files

    fake = StromFake()
    daten = b"\x89PNG\r\n\x1a\n" + b"q" * (5 * 1024 * 1024)
    fake.dateien[BASIS + "/bild.png"] = daten
    setze_speicher(strom_ablage(fake))
    try:
        kopf = files._datei_daten_begrenzt("bild.png", 4096)
    finally:
        vergiss_speicher()

    assert kopf == daten[:4096]
    uebertragen = sum(s.gelesen for s in fake.stroeme)
    assert uebertragen <= 4096 + 4096, (
        f"{uebertragen} Bytes fuer einen 4096-Byte-Kopf — die ganze Datei wurde geholt"
    )


def test_kopf_lesen_bricht_bei_einem_server_ohne_range_ab():
    """Ein Server, der ``Range`` ignoriert, wird nach dem Ausschnitt verlassen."""
    from diakronos_app import files

    fake = StromFake()
    fake.ignoriert_range = True
    daten = b"\x89PNG\r\n\x1a\n" + b"r" * (3 * 1024 * 1024)
    fake.dateien[BASIS + "/ohne.png"] = daten
    setze_speicher(strom_ablage(fake))
    try:
        kopf = files._datei_daten_begrenzt("ohne.png", 4096)
    finally:
        vergiss_speicher()

    assert kopf == daten[:4096]
    # Grenze: der angefragte Bereich plus EINE Socket-Lesung (16 KiB im
    # Fake) — ``iter_bytes(n)`` kann einen fertigen Block nicht zerteilen.
    assert fake.stroeme[0].gelesen <= 4096 + fake.block
    assert fake.stroeme[0].gelesen < len(daten)
    assert fake.stroeme[0].geschlossen is True


def test_kopf_lesen_kleiner_datei_bleibt_korrekt():
    """Kuerzer als der Ausschnitt: es kommt die ganze (kurze) Datei."""
    from diakronos_app import files

    fake = StromFake()
    fake.dateien[BASIS + "/kurz.png"] = b"\x89PNG-kurz"
    setze_speicher(strom_ablage(fake))
    try:
        assert files._datei_daten_begrenzt("kurz.png", 4096) == b"\x89PNG-kurz"
    finally:
        vergiss_speicher()


# ── 3. Leere Datei ─────────────────────────────────────────────────────────


def test_leere_datei_ist_ein_200_mit_null_bytes(client, set_user, tmp_path):
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    ablage = Lokal(tmp_path)
    ablage.schreiben("leer.txt", b"")
    setze_speicher(ablage)
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-leer", file_name="leer.txt",
                               file_url="/files/leer.txt", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")
        antwort = client.get("/files/leer.txt")
    finally:
        vergiss_speicher()
    assert antwort.status_code == 200, antwort.text
    assert antwort.content == b""
    assert antwort.headers["content-length"] == "0"


def test_leere_datei_mit_range_ist_416(client, set_user, tmp_path):
    """``bytes=0-`` auf 0 Bytes ist unerfuellbar -> 416 mit ``bytes */0``."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    ablage = Lokal(tmp_path)
    ablage.schreiben("leer.txt", b"")
    setze_speicher(ablage)
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-leer2", file_name="leer.txt",
                               file_url="/files/leer.txt", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")
        antwort = client.get("/files/leer.txt", headers={"Range": "bytes=0-"})
    finally:
        vergiss_speicher()
    assert antwort.status_code == 416
    assert antwort.headers["content-range"] == "bytes */0"


# ── 4. Zwei Threads, dieselbe Datei ────────────────────────────────────────


def test_zwei_threads_schreiben_dieselbe_datei_ohne_mischung(tmp_path):
    """Zwei parallele Schreibvorgaenge: am Ende steht EINE der beiden Fassungen.

    Mit dem geteilten Namen ``.<name>.teil-<pid>`` schrieben beide in dieselbe
    Temp-Datei: der erste ``os.replace`` nimmt sie weg, der zweite scheitert
    (``FileNotFoundError``) oder die Bytes sind gemischt.
    """
    ablage = Lokal(tmp_path)
    a = b"A" * (2 * 1024 * 1024)
    b = b"B" * (2 * 1024 * 1024)
    fehler: list[BaseException] = []
    start = threading.Barrier(2)

    def schreibe(daten: bytes) -> None:
        try:
            start.wait(timeout=10)
            for _ in range(5):
                ablage.schreiben("gleich.bin", daten)
        except BaseException as ausnahme:  # noqa: BLE001 — Test sammelt
            fehler.append(ausnahme)

    faden = [threading.Thread(target=schreibe, args=(a,)),
             threading.Thread(target=schreibe, args=(b,))]
    for t in faden:
        t.start()
    for t in faden:
        t.join(timeout=60)

    assert fehler == [], f"paralleles Schreiben scheiterte: {fehler[:2]}"
    inhalt = ablage.lesen("gleich.bin")
    assert inhalt in (a, b), "die Datei enthaelt gemischte Bytes"
    assert not [p for p in tmp_path.rglob("*") if ".teil" in p.name]


# ── 5. Aufraeumen bei JEDEM Fehler der Quelle ──────────────────────────────


def test_teil_datei_wird_auch_bei_valueerror_aufgeraeumt(tmp_path):
    """Eine Quelle, die mittendrin ``ValueError`` wirft, hinterlaesst nichts."""

    class KaputteQuelle:
        def __init__(self) -> None:
            self.rufe = 0

        def read(self, _anzahl: int) -> bytes:
            self.rufe += 1
            if self.rufe == 1:
                return b"halb"
            raise ValueError("Quelle kaputt")

    ablage = Lokal(tmp_path)
    with pytest.raises(ValueError):
        ablage.schreiben("x.png", KaputteQuelle())
    reste = [p for p in tmp_path.rglob("*") if ".teil" in p.name]
    assert reste == [], f"Temp-Rest liegengeblieben: {reste}"
    assert not (tmp_path / "x.png").exists()


def test_teil_datei_wird_auch_bei_abbruch_der_quelle_aufgeraeumt(tmp_path):
    """Auch ein Abbruch (``KeyboardInterrupt``/``BaseException``) raeumt auf."""

    class AbbrechendeQuelle:
        def __init__(self) -> None:
            self.rufe = 0

        def read(self, _anzahl: int) -> bytes:
            self.rufe += 1
            if self.rufe == 1:
                return b"halb"
            raise KeyboardInterrupt

    ablage = Lokal(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        ablage.schreiben("y.png", AbbrechendeQuelle())
    assert [p for p in tmp_path.rglob("*") if ".teil" in p.name] == []


def test_schreiben_laesst_die_rechte_wie_open(tmp_path):
    """``mkstemp`` legt 0600 an — die Ablage bleibt trotzdem umask-gleich."""
    import os
    import stat

    ablage = Lokal(tmp_path)
    ablage.schreiben("rechte.png", b"x")
    modus = stat.S_IMODE(os.stat(tmp_path / "rechte.png").st_mode)
    umask = os.umask(0)
    os.umask(umask)
    assert modus == 0o666 & ~umask, oct(modus)


# ── 6. Ungueltiger Range ergibt die ganze Datei ────────────────────────────


@pytest.mark.parametrize("kopf", [
    "bytes=0-0,5-9",   # Mehrfachbereich: nicht unterstuetzt -> ganze Datei
    "items=0-5",       # falsche Einheit
    "bytes=abc",       # kein Bereich
    "bytes=",          # leer
    "0-5",             # ohne Einheit
])
def test_ungueltiger_range_ergibt_200_mit_allem(client, set_user, tmp_path, kopf):
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    daten = b"0123456789" * 10
    ablage = Lokal(tmp_path)
    ablage.schreiben("ganz.txt", daten)
    setze_speicher(ablage)
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-ung", file_name="ganz.txt",
                               file_url="/files/ganz.txt", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")
        antwort = client.get("/files/ganz.txt", headers={"Range": kopf})
    finally:
        vergiss_speicher()
    assert antwort.status_code == 200, f"{kopf!r} ergab {antwort.status_code}"
    assert antwort.content == daten
    assert "content-range" not in antwort.headers


@pytest.mark.parametrize("wert,gesamt,art,bereich", [
    ("bytes=0-0,5-9", 100, "ungueltig", None),   # Mehrfachbereich
    ("items=0-5", 100, "ungueltig", None),       # falsche Einheit
    ("bytes=abc", 100, "ungueltig", None),       # kein Bereich
    ("bytes=100-", 100, "gueltig", None),        # ok, aber unerfuellbar
    ("bytes=0-", 0, "ungueltig", None),          # leere Datei
    ("bytes=-0", 100, "ungueltig", None),        # "die letzten 0 Bytes"
    ("bytes=0-9", 100, "gueltig", (0, 9)),
    ("bytes=-10", 100, "gueltig", (90, 99)),
    ("bytes=50-", 100, "gueltig", (50, 99)),
    ("bytes=0-9999", 100, "gueltig", (0, 99)),
])
def test_parse_bereich_unterscheidet_ungueltig_und_unerfuellbar(
    wert, gesamt, art, bereich
):
    """``ungueltig`` (nicht unterstuetzt) ist NICHT ``unerfuellbar`` (416)."""
    gelesen, von, bis = _parse_bereich(wert, gesamt)
    assert gelesen == art, f"{wert!r} -> {gelesen}"
    if art == "ungueltig":
        assert (von, bis) == (0, -1)
    elif bereich is None:
        assert (von, bis) == (0, -1), "unerfuellbar muss (0, -1) ergeben"
    else:
        assert (von, bis) == bereich


# ── 7. Datei schrumpft zwischen Kopf und GET ───────────────────────────────


def test_schrumpfende_datei_liefert_keinen_206_mit_leerem_bereich():
    """HEAD nennt 100 Bytes, GET trifft 10: kein ``bytes 0--1/100``."""

    class Schrumpfend(FakeWebDAV):
        def __call__(self, request):
            if request.method == "GET":
                self.dateien[BASIS + "/schrumpf.bin"] = b"0123456789"
            return super().__call__(request)

    fake = Schrumpfend()
    fake.dateien[BASIS + "/schrumpf.bin"] = b"n" * 100
    ablage = nextcloud_ablage(fake, versuche=1)
    gesamt, von, bis = ablage.groesse_und_bereich("schrumpf.bin", None)
    assert (gesamt, von, bis) == (100, 0, 99)

    strom, anfang, ende = ablage.strom("schrumpf.bin", von=0, bis=99)
    inhalt = b"".join(strom)
    assert inhalt == b"0123456789", "der Strom lieferte nicht die echte Datei"
    assert (anfang, ende) == (0, 9), "der Bereich ist nicht der GELIEFERTE"


def test_schrumpfende_datei_auf_null_ergibt_keinen_206_bereich():
    """Schrumpft die Datei auf 0 Bytes, liefert ``strom`` (0, -1) — kein 206."""

    class AufNull(FakeWebDAV):
        def __call__(self, request):
            if request.method == "GET":
                self.dateien[BASIS + "/weg.bin"] = b""
            return super().__call__(request)

    fake = AufNull()
    fake.dateien[BASIS + "/weg.bin"] = b"n" * 100
    ablage = nextcloud_ablage(fake, versuche=1)
    strom, anfang, ende = ablage.strom("weg.bin", von=0, bis=99)
    assert b"".join(strom) == b""
    assert ende < anfang == 0, f"kein leerer Bereich: {(anfang, ende)}"


def test_schrumpfende_datei_an_der_route(client, set_user, tmp_path):
    """Die Route antwortet nie mit ``206`` und einem leeren Bereich.

    Lokale Ablage: der Weg ist ``FileResponse``. Schrumpft die Datei
    zwischen Pruefung und Auslieferung auf 0 Bytes, darf ``FileResponse``
    nicht ``206`` mit leerem Koerper schicken — es gibt ``416`` mit der
    ECHTEN Groesse.
    """
    from diakronos_app import files
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    ablage = Lokal(tmp_path)
    ablage.schreiben("spaet.txt", b"0123456789")
    setze_speicher(ablage)
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-spaet", file_name="spaet.txt",
                               file_url="/files/spaet.txt", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")

        # Genau vor der Auslieferung schrumpft die Datei auf 0 Bytes.
        vom_ablage_weg = files._dateigroesse

        def geschrumpft(pfad):
            (tmp_path / "spaet.txt").write_bytes(b"")
            return vom_ablage_weg(pfad)

        files._dateigroesse = geschrumpft
        try:
            antwort = client.get("/files/spaet.txt", headers={"Range": "bytes=5-7"})
        finally:
            files._dateigroesse = vom_ablage_weg
    finally:
        vergiss_speicher()

    assert antwort.status_code == 416, f"{antwort.status_code} {antwort.headers}"
    assert antwort.headers["content-range"] == "bytes */0", antwort.headers


# ── 8. Range nur weitergeben, wenn der Client einen geschickt hat ──────────


def test_ohne_client_range_geht_kein_range_an_die_nextcloud():
    """Ein einfacher GET ist ein einfacher GET — kein ``bytes=0-`` an WebDAV."""
    gesehen: list[str | None] = []

    class Mitschreibend(FakeWebDAV):
        def __call__(self, request):
            if request.method == "GET":
                gesehen.append(request.headers.get("Range"))
            return super().__call__(request)

    fake = Mitschreibend()
    fake.dateien[BASIS + "/a.bin"] = b"inhalt"
    ablage = nextcloud_ablage(fake, versuche=1)
    assert b"".join(ablage.strom("a.bin")[0]) == b"inhalt"
    assert gesehen == [None], f"Range wurde ohne Auftrag gesendet: {gesehen}"


def test_route_ohne_range_schickt_keinen_range_an_die_nextcloud(
    client, set_user
):
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    gesehen: list[str | None] = []

    class Mitschreibend(StromFake):
        def __call__(self, request):
            if request.method == "GET":
                gesehen.append(request.headers.get("Range"))
            return super().__call__(request)

    fake = Mitschreibend()
    daten = b"RIFF\x00\x00\x00\x00WAVE" + b"a" * 500
    fake.dateien[BASIS + "/ton.wav"] = daten
    setze_speicher(strom_ablage(fake))
    try:
        with SessionLocal() as sess:
            sess.add(FileModel(name="f-ton", file_name="ton.wav",
                               file_url="/files/ton.wav", is_private=0,
                               owner="Administrator", modified_by="Administrator"))
            sess.commit()
        set_user("Mitglied A")
        antwort = client.get("/files/ton.wav")
    finally:
        vergiss_speicher()

    assert antwort.status_code == 200, antwort.text
    assert antwort.content == daten
    # Der einzige GET MIT Range ist der Kopf-Ausschnitt (``bytes=0-4095``);
    # der GET fuer den Koerper traegt keinen Range-Kopf (sonst kaeme ein 206
    # fuer die ganze Datei an die Route, die mit 200 antworten will).
    assert "bytes=0-4095" in gesehen, f"kein Kopf-GET gesehen: {gesehen}"
    assert [r for r in gesehen if r is None], (
        f"der volle GET schickte einen Range-Kopf: {gesehen}"
    )


# ── 9. text/html versteckt keine Datei ─────────────────────────────────────


def test_html_datei_ist_eine_datei_und_kein_ordner(fake):
    """``seite.html``: ``HEAD`` mit ``text/html`` ist eine DATEI."""
    fake.dateien[BASIS + "/seite.html"] = b"<html>hallo</html>"
    ablage = nextcloud_ablage(fake, versuche=1)
    assert ablage.existiert("seite.html") is True
    assert ablage.groesse("seite.html") == 18


def test_echter_ordner_wird_weiterhin_erkannt(fake):
    fake.ordner = {"/remote.php/dav/files/diakronos/"} | {BASIS + "/"}
    ablage = nextcloud_ablage(fake, versuche=1)
    ablage.schreiben("ordner/x.png", b"1")
    assert ablage.existiert("ordner") is False
    assert ablage.existiert("ordner/x.png") is True


# ── 10. Wiederholung spult an die STARTPOSITION (SPEICHER-3, Punkt 1) ──────


def _put_mitschreiber(status_folge: list[int]):
    """Transport, der jeden PUT-Koerper mitschreibt und Statuscodes vorgibt.

    ``status_folge`` wird der Reihe nach verbraucht; danach ``201``.
    """
    gesehen: list[bytes] = []
    folge = list(status_folge)

    def _antwort(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            gesehen.append(request.read())
            if folge:
                return httpx.Response(folge.pop(0))
        return httpx.Response(201 if request.method == "PUT" else 200)

    return gesehen, _antwort


def test_wiederholung_schickt_die_bytes_ab_der_startposition(monkeypatch):
    """SPEICHER-3, Punkt 1: Strom ab Position 10, erster PUT 500 → [10, ende).

    ``_strom_laenge`` misst ``ende - position``. Stand der Strom nicht am
    Anfang und sprang ``spulen`` auf 0, schickte der ZWEITE PUT die Bytes
    ``[0, laenge)`` — die Laenge stimmte, der Inhalt war ein anderer. Der
    Upload meldete Erfolg, und unter dem richtigen Dateinamen lag
    stillschweigend eine falsche Datei.

    Mutationsprobe (belegt im Karten-Kommentar): ``seek(self.start)`` →
    ``seek(0)`` in ``_DateiStrom.spulen`` macht diesen Test rot (der zweite
    PUT beginnt dann mit ``KOPF`` statt mit ``AB``).
    """
    import io
    import time

    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    monkeypatch.setattr(time, "sleep", lambda sekunden: None)

    kopf = b"KOPF-1234-"                      # 10 Bytes Vorspann
    inhalt = bytes(range(0, 200))             # der eigentliche Inhalt
    # ``laenge`` ist ``ende - 10``. Der letzte Teil der Datei gehoert damit zum
    # Inhalt — die Datei hat KEINEN Anhang, sonst waere die Laenge groesser
    # als ``inhalt`` (das prueft ``laenge == 200`` unten mit).
    datei = io.BytesIO(kopf + inhalt)
    assert datei.seek(len(kopf)) == 10

    gesehen, antwort = _put_mitschreiber([500])
    nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D",
                                   versuche=2),
                   client=httpx.Client(transport=httpx.MockTransport(antwort)))
    nc.wartezeiten = (0.0,)
    nc._angelegte_ordner.update(nc._alle_ebenen("a.png"))

    laenge = nc.schreiben("a.png", datei)

    assert len(gesehen) == 2, [len(g) for g in gesehen]
    # Beide Versuche schicken GENAU den Inhalt ab Position 10 — Laenge und
    # Inhalt. ``[0, laenge)`` waere ``kopf + inhalt[:190]``.
    assert gesehen[1] == inhalt, (
        "der zweite PUT begann nicht an der Startposition: "
        f"{gesehen[1][:12]!r} statt {inhalt[:12]!r}"
    )
    assert gesehen[1] == gesehen[0], "die beiden Versuche schickten verschiedenes"
    assert laenge == len(inhalt) == 200
    # Der Vorspann geht in KEINEM Versuch mit hinaus.
    assert kopf not in gesehen[0] and kopf not in gesehen[1]


def test_wiederholung_bei_position_null_bleibt_unveraendert(monkeypatch):
    """Gegenprobe zu Punkt 1: Strom am Anfang → beide PUTs die ganze Datei.

    Der Fix darf den Normalfall (Position 0) nicht verbiegen: ``start`` ist 0,
    ``seek(0)`` und ``seek(start)`` sind dasselbe.
    """
    import io
    import time

    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    monkeypatch.setattr(time, "sleep", lambda sekunden: None)

    inhalt = b"r" * 100
    gesehen, antwort = _put_mitschreiber([500])
    nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D",
                                   versuche=2),
                   client=httpx.Client(transport=httpx.MockTransport(antwort)))
    nc.wartezeiten = (0.0,)
    nc._angelegte_ordner.update(nc._alle_ebenen("b.png"))

    laenge = nc.schreiben("b.png", io.BytesIO(inhalt))

    assert laenge == len(inhalt)
    assert len(gesehen) == 2, [len(g) for g in gesehen]
    assert gesehen[0] == inhalt and gesehen[1] == inhalt


def test_nicht_spulbare_quelle_bricht_weiterhin_sauber_ab(monkeypatch):
    """Punkt 1, dritte Auflage: ohne ``seek`` wird NICHT wiederholt.

    Ein Strom mit ``tell()``, aber ohne brauchbares ``seek`` (Rohr) darf nach
    einem 500 nicht ein zweites Mal mit REST-Bytes hinausgehen — er bricht mit
    ``SpeicherNichtErreichbar`` ab, und es bleibt bei EINEM PUT.
    """
    import time

    from diakronos_app.speicher import SpeicherNichtErreichbar
    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    monkeypatch.setattr(time, "sleep", lambda sekunden: None)

    class Rohr:
        """Wie eine Pipe: ``tell()`` geht, ``seek()`` nicht."""

        def __init__(self, daten: bytes) -> None:
            self._daten = daten
            self._pos = 0

        def tell(self) -> int:
            return self._pos

        def read(self, n: int = -1) -> bytes:
            rest = self._daten[self._pos:]
            stueck = rest if n is None or n < 0 else rest[:n]
            self._pos += len(stueck)
            return stueck

        def seek(self, *args, **kwargs):
            raise OSError("nicht spulbar")

        def __len__(self) -> int:
            return len(self._daten) - self._pos

    gesehen, antwort = _put_mitschreiber([500])
    nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D",
                                   versuche=2),
                   client=httpx.Client(transport=httpx.MockTransport(antwort)))
    nc.wartezeiten = (0.0,)
    nc._angelegte_ordner.update(nc._alle_ebenen("c.png"))

    with pytest.raises(SpeicherNichtErreichbar):
        nc.schreiben("c.png", Rohr(b"x" * 64))  # type: ignore[arg-type]

    assert len(gesehen) == 1, [len(g) for g in gesehen]
    assert gesehen[0] == b"x" * 64
