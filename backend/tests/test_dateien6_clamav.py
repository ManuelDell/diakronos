"""DATEIEN-6 — Virenpruefung (ClamAV): Haken, Protokoll, fail-closed, Stack.

Geprueft wird der ECHTE Code (``diakronos_app.clamav`` ueber
``ablage.pruefe_inhalt``) gegen einen Fake-clamd auf ``127.0.0.1`` — ein
Thread-Server, der spricht, was clamd spricht (INSTREAM-Rahmen, eine
Antwortzeile). Es geht kein Paket ins Netz; der Server hoert nur auf der
Schleife.

Der EICAR-NAME steht NUR als Fake-ANTWORT hier — keine EICAR-Datei, kein
EICAR-Inhalt im Repo.

Abgedeckt (Karte DATEIEN-6):

* ``CLAMAV_HOST`` leer → No-Op, EINE Protokollzeile „Virenpruefung aus“
* OK / FOUND / Abbruch / Zeitueberschreitung / falsche Antwort / gar kein
  Dienst → genau die vorgeschriebenen Meldungen, fail-closed
* ``StreamMaxLength``: zu grosse Datei wird gar nicht erst geschickt
* der INSTREAM-Rahmen stimmt (Befehl, Laengen, Bloecke, Ende)
* Fund weist den Upload ab — ueber ``nimm_upload`` (beide Richtlinien),
  ``ablegen`` und die ECHTEN Endpunkte (Gruppendatei + Chat-Anhang)
* Compose: Dienst ``clamav``, feste Version, kein Port, Volume, mem_limit,
  Healthcheck, ``CLAMAV_HOST=clamav`` bei app/worker, KEIN depends_on
* Einstellungen: Defaults, Grenzen, ``ziel()``
"""

from __future__ import annotations

import importlib
import io
import socket
import struct
import threading
import time
from pathlib import Path

import pytest
import yaml

from diakronos_app import ablage as A
from diakronos_app import clamav as C
from diakronos_app.frappe_compat.exceptions import ValidationError

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

#: Welt, Ablage und Gespraech der Nachbarkarten TEILEN (kein Nachbau).
# ``test_chat12a_anhang`` reicht ``welt``/``gespraech`` aus ``test_chat2_api``
# weiter und bringt ``ablage`` mit — alle drei zeigen auf DIESELBEN Fixtures.
from test_chat12a_anhang import ablage  # noqa: E402,F401
#: Die Welt der GRUPPENDATEIEN (Modul ``dateien`` an) — NICHT die Chat-Welt
#: (``test_chat12a_anhang.welt`` hat nur ``chat``). Chat und Gruppendateien
#: werden hier NEBENEINANDER gemessen; darum EINE Welt (diese) und ein
#: Gespraech darin — kein zweites Testmodul, das die Welt umbaut.
from test_dateien3_gruppe_datei import welt  # noqa: E402,F401


@pytest.fixture()
def gespraech(welt):
    """Das Chor-Gespraech in DIESER Welt (dieselbe Anlage wie im Chat-Modul).

    Schaltet das Chat-Modul der Gruppe an (die Dateien-Welt schaltet nur
    ``dateien`` an) und legt das Gespraech ueber den ECHTEN Endpunkt an.
    """
    from test_chat12a_anhang import SAENGER, _set

    from diakronos_app.api import chat as C
    from diakronos_app.models.rechte import RechteModul

    welt.add(RechteModul(gruppe="Chor", modul="chat"))
    welt.commit()
    _set(SAENGER)
    name = C.gespraech_anlegen("Chor")["name"]
    _session_mod.reset_user()
    return name

#: Nur der NAME der Signatur — nicht der Teststring selbst.
EICAR = "Eicar-Test-Signature"

TXT = b"Protokoll der Chorprobe\nAlle anwesend.\n"
ZIP = b"PK\x03\x04" + b"\x00" * 40
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class _Upload:
    """``UploadFile``-artig: ``.file``/``.filename``/``.content_type``."""

    def __init__(self, daten: bytes, filename: str, content_type: str = "") -> None:
        self.file = io.BytesIO(daten)
        self.filename = filename
        self.content_type = content_type

    def read(self, *args):  # pragma: no cover — gelesen wird ``.file``
        return self.file.read(*args)


# ── Fake-clamd ─────────────────────────────────────────────────────────────


class FakeClamd:
    """Ein clamd im Kleinen: nimmt Verbindungen an, spricht INSTREAM.

    ``antwort`` ist die Zeile, die zurueckgeht; ``None`` = Verbindung ohne
    Antwort schliessen (Abbruch); ``verzoegern`` haelt die Antwort zurueck
    (Zeitueberschreitung). ``rahmen``/``daten``/``befehl`` belegen das
    gesprochene Protokoll.
    """

    def __init__(self, antwort: bytes | None = b"stream: OK\n", *,
                 verzoegern: float = 0.0, offen_halten: float = 0.0) -> None:
        self.antwort = antwort
        self.verzoegern = verzoegern
        self.offen_halten = offen_halten
        self.rahmen: list[int] = []
        self.daten = b""
        self.befehl = b""
        self.verbindungen = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._sock.settimeout(0.05)
        self.port = self._sock.getsockname()[1]
        self._ende = threading.Event()
        self._thread = threading.Thread(target=self._laufen, daemon=True)
        self._thread.start()

    def _laufen(self) -> None:
        while not self._ende.is_set():
            try:
                verbindung, _ = self._sock.accept()
            except OSError:
                continue
            self.verbindungen += 1
            with verbindung:
                try:
                    self._bedienen(verbindung)
                except OSError:
                    pass

    @staticmethod
    def _genau(verbindung: socket.socket, anzahl: int) -> bytes:
        teile: list[bytes] = []
        while anzahl > 0:
            stueck = verbindung.recv(anzahl)
            if not stueck:
                break
            teile.append(stueck)
            anzahl -= len(stueck)
        return b"".join(teile)

    def _bedienen(self, verbindung: socket.socket) -> None:
        verbindung.settimeout(5.0)
        self.befehl = self._genau(verbindung, len(b"zINSTREAM\x00"))
        while True:
            kopf = self._genau(verbindung, 4)
            if len(kopf) < 4:
                return
            laenge = struct.unpack("!I", kopf)[0]
            self.rahmen.append(laenge)
            if laenge == 0:
                break
            self.daten += self._genau(verbindung, laenge)
        if self.verzoegern:
            time.sleep(self.verzoegern)
        if self.antwort is not None:
            verbindung.sendall(self.antwort)
        if self.offen_halten:
            # Antwort ist raus, die Verbindung bleibt aber offen (z-Modus:
            # der Client MUSS an der Zeile erkennen, dass sie fertig ist).
            try:
                verbindung.settimeout(self.offen_halten)
                verbindung.recv(1)
            except OSError:
                pass

    def schliessen(self) -> None:
        self._ende.set()
        try:
            self._sock.close()
        except OSError:
            pass


class _Umgebung:
    """Die eine Naht: was ``clamav.ziel()`` und die Endpunkte sehen.

    Gepatcht wird ``settings.get_settings`` in den Modulen, die es benutzt —
    alle uebrigen Werte kommen unveraendert aus den echten Einstellungen.
    """

    def __init__(self, echt) -> None:
        self.clamav_host = ""
        self.clamav_port = 65000
        self.clamav_zeitlimit_sekunden = 5.0
        self._echt = echt

    def __getattr__(self, name: str):
        if name.startswith("__") or name == "_echt":
            raise AttributeError(name)
        return getattr(self._echt, name)


MOEGLICHE_ZIELE = ["diakronos_app.settings", "diakronos_app.clamav"]


@pytest.fixture()
def clamp(monkeypatch):
    """Pruefung EIN/AUS schalten und Fake-clamds starten.

    Rueckgabe: ``starte(**kw) -> FakeClamd`` (schaltet auf dessen Port) und
    ``umgebung`` (die Attrappe — Port/Zeitlimit direkt setzen).
    """
    dichtungen = []
    for name in MOEGLICHE_ZIELE:
        modul = __import__(name, fromlist=["get_settings"])
        echt = modul.get_settings()
        umgebung = _Umgebung(echt)
        monkeypatch.setattr(modul, "get_settings", lambda: umgebung)
        dichtungen.append(umgebung)
    monkeypatch.setattr(C, "_aus_gemeldet", False)
    umgebung = dichtungen[0]
    dienste: list[FakeClamd] = []

    def starte(**kw) -> FakeClamd:
        dienst = FakeClamd(**kw)
        dienste.append(dienst)
        for d in dichtungen:
            d.clamav_host = "127.0.0.1"
            d.clamav_port = dienst.port
            d.clamav_zeitlimit_sekunden = 5.0
        return dienst

    yield starte, umgebung

    for dienst in dienste:
        dienst.schliessen()


def _freier_port() -> int:
    """Ein Port, an dem garantiert niemand hoert (belegen, schliessen, merken)."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


# ── 1) HOST leer: No-Op ────────────────────────────────────────────────────


def test_host_leer_ist_no_op_und_meldet_einmal(monkeypatch, caplog):
    """Ohne ``CLAMAV_HOST`` geht nichts raus — und die Zeile kommt EINMAL."""
    from diakronos_app import settings as S

    echt = S.get_settings()
    if echt.clamav_host:
        pytest.skip("CLAMAV_HOST steht in dieser Umgebung — No-Op nicht messbar")
    monkeypatch.setattr(C, "get_settings", lambda: echt)
    monkeypatch.setattr(C, "_aus_gemeldet", False)

    caplog.set_level("WARNING", logger="diakronos_app.clamav")
    assert C.pruefe(TXT, "notizen.txt") is None
    assert C.pruefe(b"\x00" * 100) is None
    aus = [r for r in caplog.records if "Virenpruefung aus" in r.getMessage()]
    assert len(aus) == 1, [r.getMessage() for r in caplog.records]


def test_host_leer_laesst_den_upload_durch(monkeypatch):
    """Der ECHTE Haken (``ablage.pruefe_inhalt``) ist ohne Ziel ein No-Op."""
    from diakronos_app import settings as S

    echt = S.get_settings()
    if echt.clamav_host:
        pytest.skip("CLAMAV_HOST steht in dieser Umgebung")
    monkeypatch.setattr(C, "get_settings", lambda: echt)
    assert A.pruefe_inhalt(TXT, "notizen.txt") is None
    info = A.nimm_upload(_Upload(ZIP, "brief.docx"), richtlinie=A.RICHTLINIE_SPERR)
    assert info.anzeigename == "brief.docx"


# ── 2) OK ──────────────────────────────────────────────────────────────────


def test_ok_ist_sauber_und_die_rahmen_stimmen(clamp):
    starte, _ = clamp
    dienst = starte()
    assert C.pruefe(TXT, "notizen.txt") is None
    assert dienst.verbindungen == 1
    assert dienst.befehl == b"zINSTREAM\x00"
    assert dienst.daten == TXT
    assert dienst.rahmen[-1] == 0          # Ende des Stroms
    assert sum(dienst.rahmen[:-1]) == len(TXT)


def test_ok_ueber_mehrere_bloecke(clamp):
    """Mehr als ein Block: Laengen je Rahmen, Inhalt vollstaendig."""
    starte, _ = clamp
    dienst = starte()
    daten = bytes(range(256)) * (C.BLOCKGROESSE // 128)
    assert len(daten) > C.BLOCKGROESSE
    assert C.pruefe(daten) is None
    assert dienst.daten == daten
    assert all(0 < laenge <= C.BLOCKGROESSE for laenge in dienst.rahmen[:-1])
    assert len(dienst.rahmen) >= 3


# ── 3) FOUND und die Fehlerwege: fail-closed ───────────────────────────────


def test_found_weist_ab_nennt_die_signatur_nur_im_log(clamp, caplog):
    starte, _ = clamp
    starte(antwort=f"stream: {EICAR} FOUND\n".encode())
    caplog.set_level("WARNING", logger="diakronos_app.clamav")
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(TXT, "notizen.txt")
    text = str(fehler.value)
    assert text == C.MELDUNG_FUND
    assert "Schadsoftware" in text
    assert EICAR not in text and "notizen" not in text
    warnungen = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any(EICAR in zeile for zeile in warnungen), warnungen


@pytest.mark.parametrize("antwort", [
    b"stream: UNKNOWN\n", b"nonsense\n", b"\n", b"stream: OK extra\n",
    b"stream: ERROR\n", b"OKdropped\n",
])
def test_falsche_antwort_ist_fail_closed(clamp, caplog, antwort):
    """Alles, was nicht „OK“ ist, ist KEIN Freibrief."""
    starte, _ = clamp
    starte(antwort=antwort)
    caplog.clear()
    caplog.set_level("ERROR", logger="diakronos_app.clamav")
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(TXT, "notizen.txt")
    assert str(fehler.value) == C.MELDUNG_FEHLER, antwort
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_abbruch_der_verbindung_ist_fail_closed(clamp, caplog):
    """clamd schliesst ohne Antwort (Neustart, Absturz) → abweisen."""
    starte, _ = clamp
    starte(antwort=None)
    caplog.set_level("ERROR", logger="diakronos_app.clamav")
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(TXT, "notizen.txt")
    assert str(fehler.value) == C.MELDUNG_FEHLER
    # Eine leere Antwort ist eine unbrauchbare Antwort — auch das ist ERROR.
    assert any(r.levelname == "ERROR" and "clamd" in r.getMessage()
               for r in caplog.records)


def test_zeitueberschreitung_ist_fail_closed(clamp, caplog):
    """Ein haengender clamd blockiert den Upload nicht laenger als das Limit."""
    starte, umgebung = clamp
    starte(verzoegern=2.0)
    umgebung.clamav_zeitlimit_sekunden = 0.3
    caplog.set_level("ERROR", logger="diakronos_app.clamav")
    beginn = time.monotonic()
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(TXT, "notizen.txt")
    gedauert = time.monotonic() - beginn
    assert str(fehler.value) == C.MELDUNG_FEHLER
    assert gedauert < 1.5, gedauert
    assert any("Virenpruefung nicht moeglich" in r.getMessage() for r in caplog.records)


def test_kein_dienst_erreichbar_ist_fail_closed(clamp, caplog):
    """Port zu (Dienst nicht gestartet) → Upload abweisen, nicht durchwinken."""
    _, umgebung = clamp
    umgebung.clamav_host = "127.0.0.1"
    umgebung.clamav_port = _freier_port()
    umgebung.clamav_zeitlimit_sekunden = 1.0
    caplog.set_level("ERROR", logger="diakronos_app.clamav")
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(TXT, "notizen.txt")
    assert str(fehler.value) == C.MELDUNG_FEHLER
    assert any("Virenpruefung nicht moeglich" in r.getMessage() for r in caplog.records)


def test_ok_antwort_mit_nullbyte_beendet_das_lesen(clamp):
    """z-Modus: clamd beendet die Zeile mit ``\\0`` und HAELT die Verbindung.

    Ohne Beenden bei ``\\0`` wartet ``_instream`` auf den Zeitablauf, obwohl
    die Antwort schon da ist — der Test haelt die Verbindung darum offen.
    """
    starte, umgebung = clamp
    dienst = starte(antwort=b"stream: OK\x00", offen_halten=2.5)
    umgebung.clamav_zeitlimit_sekunden = 5.0
    beginn = time.monotonic()
    assert C.pruefe(TXT, "notizen.txt") is None
    gedauert = time.monotonic() - beginn
    assert gedauert < 2.0, gedauert          # nicht auf das Schliessen gewartet
    assert dienst.daten == TXT


def test_fund_antwort_mit_nullbyte(clamp):
    """Dasselbe mit Fund: ``\\0`` beendet, FOUND wird erkannt."""
    starte, _ = clamp
    starte(antwort=f"stream: {EICAR} FOUND\x00".encode(), offen_halten=2.5)
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(TXT, "notizen.txt")
    assert str(fehler.value) == C.MELDUNG_FUND


def test_zu_gross_fuer_clamd_wird_gar_nicht_erst_geschickt(clamp, monkeypatch, caplog):
    """Jenseits ``StreamMaxLength`` nimmt clamd nichts an — also abweisen."""
    starte, _ = clamp
    dienst = starte()
    monkeypatch.setattr(C, "STREAM_MAX_LENGTH", 8)
    caplog.set_level("ERROR", logger="diakronos_app.clamav")
    with pytest.raises(ValidationError) as fehler:
        C.pruefe(b"0123456789")
    assert str(fehler.value) == C.MELDUNG_FEHLER
    assert dienst.verbindungen == 0
    assert any("StreamMaxLength" in r.getMessage() for r in caplog.records)


# ── 4) Der Upload ist abgewiesen (die Naht) ────────────────────────────────


def test_fund_weist_upload_ab_gruppendatei_richtlinie(clamp):
    starte, _ = clamp
    starte(antwort=f"stream: {EICAR} FOUND\n".encode())
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(PDF, "protokoll.pdf"), richtlinie=A.RICHTLINIE_SPERR)
    assert str(fehler.value) == C.MELDUNG_FUND


def test_fund_weist_upload_ab_chat_richtlinie(clamp):
    starte, _ = clamp
    starte(antwort=f"stream: {EICAR} FOUND\n".encode())
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(PDF, "vertrag.pdf", "application/pdf"))
    assert str(fehler.value) == C.MELDUNG_FUND


def test_nicht_erreichbarer_dienst_weist_upload_ab(clamp):
    """fail-closed bis in den Upload: kein stiller Weg an der Pruefung vorbei."""
    _, umgebung = clamp
    umgebung.clamav_host = "127.0.0.1"
    umgebung.clamav_port = _freier_port()
    umgebung.clamav_zeitlimit_sekunden = 1.0
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(TXT, "notiz.txt"), richtlinie=A.RICHTLINIE_SPERR)
    assert str(fehler.value) == C.MELDUNG_FEHLER


def test_sauberer_upload_geht_bei_ok_durch(clamp, tmp_path):
    """Positivprobe: Pruefung AN, clamd sagt OK → Upload laeuft wie bisher."""
    from diakronos_app.speicher import Lokal, vergiss_speicher, setze_speicher

    starte, _ = clamp
    dienst = starte()
    setze_speicher(Lokal(tmp_path))
    try:
        info = A.nimm_upload(_Upload(PDF, "protokoll.pdf"), richtlinie=A.RICHTLINIE_SPERR)
        assert info.anzeigename == "protokoll.pdf"
        assert info.inhalt == PDF
        assert dienst.daten == PDF

        _, schluessel = A.ablegen(_Upload(PDF, "protokoll.pdf"), "datei",
                                  richtlinie=A.RICHTLINIE_SPERR)
        with A.oeffne(schluessel) as quelle:
            assert quelle.ganz() == PDF
        assert dienst.verbindungen == 2
    finally:
        vergiss_speicher()


# ── 5) Die ECHTEN Endpunkte (Gruppendatei + Chat-Anhang) ───────────────────


def test_fund_im_echten_gruppendatei_endpunkt(clamp, welt, ablage):
    """Gruppendatei: Fund → abgewiesen, KEINE Zeile, KEINE Datei."""
    from test_dateien3_gruppe_datei import SAENGER, PDF as GPDF
    from test_dateien3_gruppe_datei import _Upload as _GUpload
    from test_dateien3_gruppe_datei import _set, _zeilen

    starte, _ = clamp
    starte(antwort=f"stream: {EICAR} FOUND\n".encode())
    vorher = set(ablage.objekte()) if hasattr(ablage, "objekte") else set()

    from diakronos_app.api import dateien as D

    _set(SAENGER)
    with pytest.raises(ValidationError) as fehler:
        D.hochladen("Chor", datei=_GUpload(GPDF, "protokoll.pdf"))
    assert str(fehler.value) == C.MELDUNG_FUND
    assert _zeilen() == []
    if hasattr(ablage, "objekte"):
        assert set(ablage.objekte()) == vorher


def test_fund_im_echten_chat_endpunkt(clamp, gespraech, ablage):
    """Chat-Anhang: derselbe Haken, dieselbe Meldung, keine Zeile."""
    from test_chat12a_anhang import ANNA, PNG
    from test_chat12a_anhang import _Upload as _CUpload
    from test_chat12a_anhang import _anhang_zeilen, _set

    starte, _ = clamp
    starte(antwort=f"stream: {EICAR} FOUND\n".encode())
    from diakronos_app.api import chat as CH

    _set(ANNA)
    with pytest.raises(ValidationError) as fehler:
        CH.anhang_hochladen(gespraech, datei=_CUpload(PNG, "foto.png", "image/png"))
    assert str(fehler.value) == C.MELDUNG_FUND
    assert _anhang_zeilen() == []


def test_dienst_weg_im_echten_chat_endpunkt_ist_fail_closed(clamp, gespraech, ablage):
    from test_chat12a_anhang import ANNA, PNG
    from test_chat12a_anhang import _Upload as _CUpload
    from test_chat12a_anhang import _anhang_zeilen, _set

    _, umgebung = clamp
    umgebung.clamav_host = "127.0.0.1"
    umgebung.clamav_port = _freier_port()
    umgebung.clamav_zeitlimit_sekunden = 1.0
    from diakronos_app.api import chat as CH

    _set(ANNA)
    with pytest.raises(ValidationError) as fehler:
        CH.anhang_hochladen(gespraech, datei=_CUpload(PNG, "foto.png", "image/png"))
    assert str(fehler.value) == C.MELDUNG_FEHLER
    assert _anhang_zeilen() == []


# ── 6) Einstellungen und ``ziel()`` ────────────────────────────────────────


def _settings(monkeypatch, **env):
    """Frische ``Settings`` aus der Umgebung (nur Testwerte, keine Secrets)."""
    from diakronos_app import settings as S

    for schluessel in ("CLAMAV_HOST", "CLAMAV_PORT", "CLAMAV_ZEITLIMIT_SEKUNDEN"):
        monkeypatch.delenv(schluessel, raising=False)
    for schluessel, wert in env.items():
        monkeypatch.setenv(schluessel, str(wert))
    return S.Settings(_env_file=None)


def test_defaults_sind_aus(monkeypatch):
    s = _settings(monkeypatch)
    assert s.clamav_host == ""
    assert s.clamav_port == 3310
    assert s.clamav_zeitlimit_sekunden == 15.0


def test_ziel_ohne_host_ist_none(monkeypatch):
    s = _settings(monkeypatch)
    monkeypatch.setattr(C, "get_settings", lambda: s)
    assert C.ziel() is None


def test_ziel_liest_umgebung(monkeypatch):
    s = _settings(monkeypatch, CLAMAV_HOST="clamav", CLAMAV_PORT=3311,
                  CLAMAV_ZEITLIMIT_SEKUNDEN=7)
    monkeypatch.setattr(C, "get_settings", lambda: s)
    z = C.ziel()
    assert z is not None
    assert (z.host, z.port, z.zeitlimit) == ("clamav", 3311, 7.0)


@pytest.mark.parametrize("wert", ["0", "-1", "0.1", "301", "abc"])
def test_zeitlimit_grenzen(monkeypatch, wert):
    with pytest.raises(Exception):
        _settings(monkeypatch, CLAMAV_ZEITLIMIT_SEKUNDEN=wert)


def test_unbrauchbarer_port_aendert_das_ziel_nicht_die_schaerfe(monkeypatch):
    """Ein Tippfehler im Port setzt den Standard-Port — die Pruefung bleibt an."""
    s = _settings(monkeypatch, CLAMAV_HOST="clamav")
    object.__setattr__(s, "clamav_port", 99999)
    monkeypatch.setattr(C, "get_settings", lambda: s)
    z = C.ziel()
    assert z is not None and z.port == C.STANDARD_PORT


# ── 7) Compose: der Dienst im Stack ────────────────────────────────────────

STACK = REPO / "compose" / "stack.yml"


def _stack() -> dict:
    return yaml.safe_load(STACK.read_text(encoding="utf-8"))


def test_stack_hat_den_clamav_dienst():
    dienste = _stack()["services"]
    assert "clamav" in dienste
    image = str(dienste["clamav"]["image"])
    assert image.startswith("clamav/clamav:")
    assert not image.endswith(":latest"), image
    tag = image.split(":", 1)[1]
    assert any(z.isdigit() for z in tag), tag


def test_clamav_hat_keinen_veroeffentlichten_port_und_ein_volume():
    clamav = _stack()["services"]["clamav"]
    assert not clamav.get("ports")
    assert all(str(p) == "3310" for p in clamav.get("expose") or [])
    ziele = " ".join(str(v) for v in clamav.get("volumes") or [])
    assert "/var/lib/clamav" in ziele


def test_clamav_hat_mem_limit_und_healthcheck():
    clamav = _stack()["services"]["clamav"]
    assert str(clamav.get("mem_limit")) == "2g"
    hc = clamav.get("healthcheck") or {}
    assert hc.get("test"), "Healthcheck fehlt"
    assert "start_period" in hc


def test_clamav_einstellungen_ueber_umgebung():
    """`ConcurrentDatabaseReload no` & Co. ueber `CLAMD_CONF_*` (das /init des
    Images schreibt sie in clamd.conf). KEINE eingebundene clamd.conf: am 24.11.
    im Wegwerf-Container gemessen — eine read-only-Datei bricht den Image-Start
    (LogFile-Schleife, `sed -i` auf der Datei)."""
    clamav = _stack()["services"]["clamav"]
    env = clamav.get("environment") or {}
    assert env.get("CLAMD_CONF_ConcurrentDatabaseReload") == "no"
    assert env.get("CLAMD_CONF_StreamMaxLength") == "64M"
    for v in clamav.get("volumes") or []:
        ziel = v.get("target") if isinstance(v, dict) else str(v)
        assert "clamd.conf" not in str(ziel), v


def test_streamgrenze_passt_zur_clamd_konfiguration():
    """Code und Dienst nennen dieselbe Grenze (64 MiB)."""
    assert C.STREAM_MAX_LENGTH == 64 * 1024 * 1024
    env = _stack()["services"]["clamav"]["environment"]
    assert env["CLAMD_CONF_StreamMaxLength"] == "64M"
    from diakronos_app.models.chat import ANHANG_MAX_MB_GRENZE

    assert ANHANG_MAX_MB_GRENZE * 1024 * 1024 < C.STREAM_MAX_LENGTH


def test_app_und_worker_bekommen_clamav_host():
    daten = _stack()
    anker = daten["x-app-env"]
    # `-` statt `:-`: ein ABSICHTLICH leerer Wert bleibt leer (Pruefung aus).
    assert anker["CLAMAV_HOST"] == "${CLAMAV_HOST-clamav}"
    assert ":-" not in anker["CLAMAV_HOST"]
    assert anker["CLAMAV_PORT"] == "${CLAMAV_PORT:-3310}"
    assert anker["CLAMAV_ZEITLIMIT_SEKUNDEN"] == "${CLAMAV_ZEITLIMIT_SEKUNDEN:-15}"
    # app, worker und scheduler haengen ALLE am Anker — eine Fassung.
    dienste = daten["services"]
    for name in ("app", "worker", "scheduler"):
        assert (dienste[name].get("environment") or {})["CLAMAV_HOST"], name
    roh = STACK.read_text(encoding="utf-8")
    assert roh.count("<<: *app-env") >= 3


def test_app_startet_nicht_erst_wenn_clamd_gesund_ist():
    """Signaturladen dauert 1–2 Min: kein ``condition: service_healthy`` fuer app."""
    dienste = _stack()["services"]
    for name in ("app", "worker", "scheduler"):
        abhaengig = dienste[name].get("depends_on") or {}
        if isinstance(abhaengig, dict):
            assert "clamav" not in abhaengig, f"{name} haengt an clamav: {abhaengig['clamav']}"
        else:
            assert "clamav" not in abhaengig, name


def test_clamav_ist_im_selben_netz_wie_app():
    """Kein eigenes Netz: der Dienst steht schlicht im Compose-Netz."""
    daten = _stack()
    assert "networks" not in daten or not daten.get("networks")
    assert "network_mode" not in daten["services"]["clamav"]


def test_env_beispiel_nennt_die_schalter():
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    for name in ("CLAMAV_HOST", "CLAMAV_PORT", "CLAMAV_ZEITLIMIT_SEKUNDEN"):
        assert name in text, name


def test_betriebsanleitung_hat_einen_abschnitt():
    text = (REPO / "docs" / "BETRIEBSANLEITUNG.md").read_text(encoding="utf-8")
    assert "ClamAV" in text and "CLAMAV_HOST" in text
    assert "~1 GB je clamd" in text
    # R1: `-` statt `:-` und "kein Parallelbetrieb beim Reload" stehen drin.
    assert 'CLAMD_CONF_ConcurrentDatabaseReload: "no"' in text
    assert "${CLAMAV_HOST-clamav}" in text