"""DATEIEN-2 — der Ablage-Baustein (Chat-Anhänge + Gruppendateien), Backend.

Karte DATEIEN-2, Konzept DATEIEN-K, Entscheidungen Manuel 23.11. Geprüft wird
der Baustein ``diakronos_app.ablage`` GEGEN DEN ECHTEN CODE — kein Nachbau der
Regeln:

  * SPERRLISTE (Gruppendateien, F8) weist ab: ELF, PE („MZ"), Shebang-Skript
    mit ``.txt``-Endung, ``.PDF.exe``, ``.SH`` (groß), ``.html``, ``.svg`` —
    per INHALT und per ENDUNG, case-insensitiv, Doppelendung in BEIDE
    Richtungen (``.pdf.exe`` UND ``.exe.pdf`` gesperrt)
  * ERLAUBT im Sperr-Modus: docx, xlsx, ods, odt, csv, txt, zip, pdf, jpg,
    mp3 — und eine unbekannte Binärdatei ohne Endung (als octet-stream)
  * Deckel: höchstens Grenze+1 Byte werden gelesen (zählender Strom)
  * Grenze folgt ``chat_anhanggrenze.anhang_max_mb`` (25 MB eingestellt →
    26 MB abgewiesen, Meldung nennt 25)
  * ``pruefe_inhalt`` (F7-Haken) wird GENAU EINMAL je Upload gerufen; wirft
    er, ist der Upload abgewiesen
  * Ausliefer-Kopfzeilen: inline nur für erkannte Bilder, sonst attachment;
    unbekannter Typ → ``application/octet-stream``; ``nosniff`` immer
  * Chat-Positivliste UNVERÄNDERT: docx im Chat weiterhin abgewiesen
  * Review R1: der GESÄUBERTE Anzeigename wird mitgeprüft (``x.sh\\x00``,
    Zero-Width-Space, Soft Hyphen, ``x.sh:``, ``x.sh"``); Skript-Host-Endungen
    (``.js .jse .mjs .ws .vb .ps1xml .msc .gadget``); echtes PE statt „MZ";
    HTML/SVG auch am INHALT (``.dat``/endungslos); ``name=`` des Aufrufers
    (``dateiname=`` im Chat) hat Vorrang vor ``.filename``
  * Gegenprobe-Beleg: der Ablauf ist im Baustein EINE Fassung, ``api.chat``
    ruft ihn (kein zweiter Lesedeckel, keine zweite Dateinamen-Regel)

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_dateien2_ablage.py
"""

from __future__ import annotations

import importlib
import io
import struct
import zlib
from pathlib import Path

import pytest

from diakronos_app import ablage as A
from diakronos_app.frappe_compat.exceptions import ValidationError

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]
MB = 1024 * 1024

#: Dieselbe Welt wie ``test_chat12a_anhang`` (Chor mit Chat-Modul, HV/MV/GL,
#: Mitglied, Fremder) — Fixture und Konten werden GETELT.
from test_chat2_api import (  # noqa: E402,F401 — Fixture teilen
    SAENGER,
    gespraech,
    welt,
)


# ── Attrappen ──────────────────────────────────────────────────────────────


class _Upload:
    """``UploadFile``-artig: ``.file``/``.filename``/``.content_type``/``.read``."""

    def __init__(self, daten: bytes, filename: str = "datei.bin",
                 content_type: str = "application/octet-stream") -> None:
        self.file = io.BytesIO(daten)
        self.filename = filename
        self.content_type = content_type

    def read(self, *args):  # pragma: no cover — der Baustein liest ``.file``
        return self.file.read(*args)


class _GezaehlterStrom(io.RawIOBase):
    """Ein Strom, der mitzählt, wie viele Bytes WIRKLICH abgeholt wurden."""

    def __init__(self, daten: bytes) -> None:
        self._daten = daten
        self._pos = 0
        self.gelesen = 0

    def readable(self) -> bool:
        return True

    def read(self, n: int = -1) -> bytes:
        """EIN Stück je Aufruf — höchstens ``n`` Byte (wie ein Netzstrom).

        Kein Ziel-Bytes-Klebstoff: ``read(1_000_000)`` liefert hier auch nur
        ``eine`` Portion. Damit prüfen die Deckel-Tests echte Stücklieferung.
        """
        stueck = 64 * 1024
        if n is not None and n >= 0:
            stueck = min(stueck, n)
        rest = self._daten[self._pos:self._pos + stueck]
        self._pos += len(rest)
        self.gelesen += len(rest)
        return rest


class _UploadMitStrom(_Upload):
    def __init__(self, strom, filename: str = "datei.bin",
                 content_type: str = "application/octet-stream") -> None:
        self.file = strom
        self.filename = filename
        self.content_type = content_type


def _png() -> bytes:
    """Ein echtes, minimales PNG (nur Standardbibliothek)."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (struct.pack("!I", len(daten)) + typ + daten
                + struct.pack("!I", zlib.crc32(typ + daten) & 0xFFFFFFFF))

    kopf = struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", kopf)
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
            + chunk(b"IEND", b""))


PNG = _png()
#: Ein echtes ZIP (docx/xlsx/ods/odt/zip beginnen alle so) — ``PK\x03\x04``.
ZIP = b"PK\x03\x04" + b"\x00" * 40
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 40
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 40
ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 40
PE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 40  # nur MZ-Kopf, KEIN PE\0\0
SHEBANG = b"#!/bin/sh\necho harmlos\n"
HTML = b"<!DOCTYPE html>\n<html><script>alert(1)</script></html>\n"
SVG = (b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg">'
       b"<script>alert(1)</script></svg>\n")
TXT = b"Ein ganz gewoehnlicher Text ohne Magie.\n"
CSV = b"spalte;wert\n1;2\n"


def _sperr(daten: bytes, name: str) -> A.UploadInfo:
    return A.nimm_upload(_Upload(daten, name), grenze=None,
                         richtlinie=A.RICHTLINIE_SPERR)


def _abgewiesen(daten: bytes, name: str) -> str:
    """Sperr-Modus-Upload, der abgewiesen werden MUSS — Rückgabe: die Meldung."""
    with pytest.raises(ValidationError) as fehler:
        _sperr(daten, name)
    return str(fehler.value)


# ── 1) Sperrliste: Inhalt ──────────────────────────────────────────────────


def test_elf_wird_abgewiesen():
    """Linux-Programm, harmlos als ``.txt`` getarnt — die MAGIE entscheidet."""
    assert "ELF" in _abgewiesen(ELF, "bericht.txt")


def test_pe_wird_abgewiesen():
    """Windows-Programm — echtes PE: ``e_lfanew`` zeigt auf ``PE\\0\\0``.

    Review R1/KANN 4: der bloße ``MZ``-Kopf genügt NICHT mehr (er sperrte
    jede CSV, die mit „MZ-" beginnt) — geprüft wird der PE-Kopf.
    """
    assert "PE" in _abgewiesen(_mini_pe(), "bericht.dat")
    # ``.exe`` bleibt ohnehin per ENDUNG gesperrt (unabhängig von der Magie).
    _abgewiesen(TXT, "bericht.exe")


def test_shebang_skript_mit_txt_endung_wird_abgewiesen():
    """Shebang ``#!`` am Anfang: ein Skript, das sich ``.txt`` nennt."""
    assert "Shebang" in _abgewiesen(SHEBANG, "notizen.txt")


@pytest.mark.parametrize("name", [
    "bericht.PDF.exe",   # Doppelendung, letzte Endung ist das Programm
    "bericht.pdf.EXE",   # dito, groß
    "bericht.exe.pdf",   # Doppelendung UMGEKEHRT: die erste Endung ist es
    "skript.SH",         # case-insensitiv
    "seite.HTML",
    "seite.htm",
    "bild.svg",          # Stored-XSS-Form
    "bild.SVGZ",
    "installer.msi",
    "setup.ps1",
    "werkzeug.py",
])
def test_gesperrte_endungen(name):
    """Endung gesperrt — bei harmlosem INHALT (Text), also nur die Endung."""
    _abgewiesen(TXT, name)


def test_html_und_svg_werden_abgewiesen():
    """HTML/SVG sind als AUSLIEFERBARE Form gesperrt (Stored XSS).

    Seit Review R1/KANN 5 greift die INHALTS-Erkennung zuerst, deshalb nennt
    die Meldung „HTML/SVG-Markup" statt der Endung — gesperrt ist beides.
    """
    assert "Markup" in _abgewiesen(HTML, "seite.html")
    assert "Markup" in _abgewiesen(SVG, "bild.svg")


def test_doppelendung_pdf_exe_richtig_herum():
    """``bericht.pdf.exe`` gesperrt — ``bericht.exe.pdf`` AUCH (jedes Segment)."""
    assert A.ist_gesperrt("bericht.pdf.exe")
    assert A.ist_gesperrt("bericht.exe.pdf")
    # Und die harmlose Gegenprobe: ein PDF bleibt ein PDF.
    assert not A.ist_gesperrt("bericht.pdf")
    assert not A.ist_gesperrt("noten.final.pdf")


def test_sperrliste_ist_eine_konstante():
    """Kartenauflage: EINE Konstante — Prüfung und Test hängen an ihr."""
    assert isinstance(A.GESPERRTE_ENDUNGEN, frozenset)
    for endung in (".exe", ".sh", ".py", ".html", ".svg", ".dll", ".jar"):
        assert endung in A.GESPERRTE_ENDUNGEN
    assert "exe" not in A.GESPERRTE_ENDUNGEN          # mit Punkt, nicht ohne
    assert not any(e != e.lower() for e in A.GESPERRTE_ENDUNGEN)  # alle klein


# ── 2) Sperrliste: erlaubt ─────────────────────────────────────────────────


@pytest.mark.parametrize("daten,name,typ", [
    (ZIP, "brief.docx", "application/zip"),
    (ZIP, "tabelle.xlsx", "application/zip"),
    (ZIP, "tabelle.ods", "application/zip"),
    (ZIP, "text.odt", "application/zip"),
    (ZIP, "paket.zip", "application/zip"),
    (CSV, "liste.csv", A.UNBEKANNTER_TYP),
    (TXT, "notiz.txt", A.UNBEKANNTER_TYP),
    (PDF, "noten.pdf", "application/pdf"),
    (JPG, "foto.jpg", "image/jpeg"),
    (MP3, "probe.mp3", "audio/mpeg"),
])
def test_dokumentarten_sind_erlaubt(daten, name, typ):
    """F8: ALLE Dokumentarten sind erlaubt — nur Ausführbares ist gesperrt."""
    info = _sperr(daten, name)
    assert info.typ == typ
    assert info.anzeigename == name
    assert info.groesse == len(daten)


def test_unbekannte_binaerdatei_ohne_endung_ist_erlaubt_aber_octet_stream():
    """Unbekannte Binärdatei: erlaubt, aber NIE inline und NIE „geraten"."""
    roh = bytes(range(256)) * 2
    info = _sperr(roh, "datensatz")
    assert info.typ == A.UNBEKANNTER_TYP
    kopf = A.ausliefer_kopf(info.typ, info.anzeigename)
    assert kopf["Content-Disposition"].startswith("attachment;")
    assert kopf["X-Content-Type-Options"] == "nosniff"
    assert A.sicherer_typ(info.typ) == "application/octet-stream"


# ── 3) Positivliste (Chat) bleibt unverändert ──────────────────────────────


def test_chat_positivliste_weist_docx_ab():
    """Chat: docx ist KEIN Chat-Typ — die Positivliste gilt weiter."""
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(ZIP, "brief.docx"), richtlinie=A.RICHTLINIE_POSITIV)
    assert "Dateityp nicht erlaubt" in str(fehler.value)
    assert "Bilder (JPG, PNG, WebP, HEIC)" in str(fehler.value)


@pytest.mark.parametrize("daten,name,typ", [
    (PNG, "a.png", "image/png"),
    (JPG, "a.jpg", "image/jpeg"),
    (PDF, "a.pdf", "application/pdf"),
    (MP3, "a.mp3", "audio/mpeg"),
])
def test_chat_positivliste_laesst_ihre_typen_durch(daten, name, typ):
    info = A.nimm_upload(_Upload(daten, name, typ), richtlinie=A.RICHTLINIE_POSITIV)
    assert info.typ == typ


def test_api_chat_ruft_den_baustein_nicht_eine_zweite_fassung():
    """EINE Fassung: ``api.chat`` importiert den Baustein und ruft ihn.

    Belegt die Umstellung (Karte Punkt 2) ohne die Chat-Tests anzufassen:
    kein zweiter Lesedeckel, keine zweite Dateinamen-Regel im Chat.
    """
    quelle = (BACKEND / "src" / "diakronos_app" / "api" / "chat.py").read_text(
        encoding="utf-8")
    assert "from diakronos_app import ablage" in quelle
    assert "ablage.nimm_upload(" in quelle
    assert "ablage.ausliefer_kopf(" in quelle
    assert "ablage.RICHTLINIE_POSITIV" in quelle
    # Die Bereinigung des Namens steht NUR im Baustein.
    assert "def _anhang_dateiname" in quelle
    assert "basis.rpartition" not in quelle


# ── 4) Lesedeckel und Größe ────────────────────────────────────────────────


def test_deckel_liest_nicht_ueber_grenze_plus_eins():
    """Der Lesevorgang holt höchstens ``Grenze + 1`` Byte — nie mehr."""
    grenze = 2 * MB
    strom = _GezaehlterStrom(PNG + b"\x00" * (grenze))
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_UploadMitStrom(strom), grenze=grenze,
                      richtlinie=A.RICHTLINIE_SPERR)
    assert "zu groß" in str(fehler.value)
    assert strom.gelesen == grenze + 1


def test_genau_die_grenze_geht_durch_und_der_deckel_bleibt():
    grenze = 2 * MB
    # 100 Bytes UNTER der Grenze — der Upload passt, mehr als Grenze+1 wird
    # trotzdem nie geholt.
    gerade = PNG + b"\x00" * (grenze - 100 - len(PNG))
    strom = _GezaehlterStrom(gerade)
    info = A.nimm_upload(_UploadMitStrom(strom), grenze=grenze,
                         richtlinie=A.RICHTLINIE_POSITIV)
    assert info.groesse == len(gerade)
    assert strom.gelesen == len(gerade)      # Strom zu Ende, nichts verschluckt


def test_genau_die_grenze_geht_durch():
    """Grenze Byte GEHEN; erst Grenze+1 wird abgewiesen (Deckel Grenze+1)."""
    grenze = 2 * MB
    gerade = PNG + b"\x00" * (grenze - len(PNG))
    strom = _GezaehlterStrom(gerade)
    info = A.nimm_upload(_UploadMitStrom(strom), grenze=grenze,
                         richtlinie=A.RICHTLINIE_POSITIV)
    assert info.groesse == len(gerade) == grenze
    # Der Strom ist am Ende — kein Byte wurde verschluckt (Stücklieferung!).
    assert strom.gelesen == len(gerade)


def test_deckel_holt_nie_mehr_als_grenze_plus_eins_trotz_stuecken():
    """Ein 5-MB-Strom bei 2-MB-Grenze: geholt werden trotzdem nur Grenze+1."""
    grenze = 2 * MB
    gerade = PNG + b"\x00" * (grenze - len(PNG))
    strom = _GezaehlterStrom(gerade + b"\x00" * (3 * MB))  # 3 MB dahinter
    with pytest.raises(ValidationError):
        A.nimm_upload(_UploadMitStrom(strom), grenze=grenze,
                      richtlinie=A.RICHTLINIE_POSITIV)
    assert strom.gelesen == grenze + 1


def test_grenze_folgt_der_einstellung_anhang_max_mb(gespraech, tmp_path):
    """F9: derselbe Admin-Wert — 25 MB eingestellt → 26 MB abgewiesen mit „25"."""
    from diakronos_app import chat_anhanggrenze as G
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal.begin() as s:
        G.setze_einstellungen(s, mb=25, benutzer=SAENGER if False else "Administrator")
        grenze = G.anhang_max_bytes(s)

    assert grenze == 25 * MB
    sechsundzwanzig = PNG + b"\x00" * (26 * MB - len(PNG))
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(sechsundzwanzig, "gross.png"), grenze=grenze)
    assert "max. 25 MB" in str(fehler.value)
    assert "max. 10 MB" not in str(fehler.value)


def test_leere_datei_und_fehlende_datei():
    with pytest.raises(ValidationError) as leer:
        A.nimm_upload(_Upload(b"", "x.png"))
    assert "leer" in str(leer.value)
    with pytest.raises(ValidationError) as keine:
        A.nimm_upload(None)
    assert "keine Datei" in str(keine.value)


# ── 5) Haken ``pruefe_inhalt`` (F7) ────────────────────────────────────────


def test_pruefe_inhalt_wird_genau_einmal_je_upload_gerufen(monkeypatch):
    """Der Haken hat EINE Aufrufstelle im Ablauf — genau einmal je Upload."""
    aufrufe: list[tuple[int, str | None]] = []

    def zaehle(roh, name=None):
        aufrufe.append((len(roh), name))

    monkeypatch.setattr(A, "pruefe_inhalt", zaehle)
    A.nimm_upload(_Upload(PNG, "foto.png", "image/png"))
    assert aufrufe == [(len(PNG), "foto.png")]

    aufrufe.clear()
    A.nimm_upload(_Upload(ZIP, "brief.docx"), richtlinie=A.RICHTLINIE_SPERR)
    assert aufrufe == [(len(ZIP), "brief.docx")]


def test_pruefe_inhalt_wirft_upload_ist_abgewiesen(monkeypatch):
    """Ein Fund im Haken weist den Upload ab — auch bei harmloser Endung."""
    from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher

    def fund(roh, name=None):
        raise ValidationError("Die Datei wurde von der Virenprüfung abgelehnt.")

    monkeypatch.setattr(A, "pruefe_inhalt", fund)
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(TXT, "notiz.txt"), richtlinie=A.RICHTLINIE_SPERR)
    assert "Virenprüfung" in str(fehler.value)


def test_pruefe_inhalt_ist_heute_ein_no_op():
    """Solange ClamAV fehlt (Folgekarte), tut der Haken nichts."""
    assert A.pruefe_inhalt(TXT, "notizen.txt") is None
    assert A.pruefe_inhalt(b"\x00" * 100) is None


# ── 6) Auslieferung: Kopfzeilen ────────────────────────────────────────────


def test_bilder_inline_alles_andere_attachment():
    for typ in ("image/png", "image/jpeg", "image/webp", "image/heic"):
        kopf = A.ausliefer_kopf(typ, "a.bin")
        assert kopf["Content-Disposition"].startswith("inline;")
        assert kopf["X-Content-Type-Options"] == "nosniff"
    # PDF bleibt ``attachment`` (Chat-Verhalten unverändert, Kartenauflage).
    for typ in ("application/pdf", "audio/mpeg", "application/zip",
                A.UNBEKANNTER_TYP):
        kopf = A.ausliefer_kopf(typ, "a.bin")
        assert kopf["Content-Disposition"].startswith("attachment;")
        assert kopf["X-Content-Type-Options"] == "nosniff"


def test_unbekannter_und_fremder_typ_wird_octet_stream():
    """Was NICHT sicher erkannt ist, geht als octet-stream — nie als HTML."""
    assert A.sicherer_typ(None) == "application/octet-stream"
    assert A.sicherer_typ("") == "application/octet-stream"
    assert A.sicherer_typ("text/html") == "application/octet-stream"
    assert A.sicherer_typ("image/svg+xml") == "application/octet-stream"
    assert A.sicherer_typ("application/x-msdownload") == "application/octet-stream"
    # Sicher erkannte Typen bleiben, wie sie sind.
    assert A.sicherer_typ("image/png") == "image/png"
    assert A.sicherer_typ("application/pdf") == "application/pdf"


def test_disinhaltsangabe_bleibt_rfc6266():
    kopf = A.ausliefer_kopf("image/png", "foto ä.png")["Content-Disposition"]
    assert 'filename="foto _.png"' in kopf
    assert "filename*=UTF-8''foto%20%C3%A4.png" in kopf


# ── 7) Ablegen und Ausliefern über die EINE Ablage ─────────────────────────


@pytest.fixture()
def ablage(tmp_path):
    """Die Ablage NUR für diesen Test auf ein ``tmp_path`` stellen (kein Netz)."""
    from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher

    ordner = tmp_path / "files"
    ordner.mkdir()
    speicher = Lokal(ordner)
    setze_speicher(speicher)
    try:
        yield speicher
    finally:
        vergiss_speicher()


def test_ablegen_und_wieder_ausliefern(ablage):
    """``ablegen`` schreibt über ``hole_speicher()`` — ``strom`` liest zurück."""
    info, key = A.ablegen(_Upload(PDF, "noten.pdf"), "chat-a")
    assert key.startswith("chat-a-")
    assert ablage.existiert(key)

    bloecke, anfang, ende = A.strom(key)
    assert b"".join(bloecke) == PDF
    # ende ist der LETZTE Byte-Index (inklusiv) — wie in speicher.strom.
    assert ende == len(PDF) - 1


def test_lege_ab_nutzt_die_aktive_ablage(ablage):
    info = A.nimm_upload(_Upload(PNG, "a.png", "image/png"))
    key = A.lege_ab(info, "test")
    assert ablage.lesen(key) == PNG


# ── 8) Richtlinie: Tippfehler wird nicht still zur Sperrliste ──────────────


def test_unbekannte_richtlinie_ist_ein_fehler():
    with pytest.raises(ValueError):
        A.nimm_upload(_Upload(PNG, "a.png"), richtlinie="sperliste_")


# ── 9) Review R1: Umgehungen der Sperrliste (MUSS 1) ───────────────────────
#
# Der Anzeigename wird BEREINIGT (Steuerzeichen raus, Zeilenumbrüche raus,
# Backslash/Doppelpunkt raus). Prüfte die Sperrliste den ROHEN Namen, wäre sie
# mit genau dieser Bereinigung umgehbar: der Browser bekommt ``x.sh``, die
# Prüfung sah ``x.sh\x00``/``x.sh:`` — und ließ durch.


@pytest.mark.parametrize("rohname,anzeige", [
    ("x.sh\x00", "x.sh"),          # Nullbyte am Ende
    ("x.s\u200bh", "x.sh"),        # Zero-Width-Space im Namen
    ("x.ex\u00ade", "x.exe"),      # weiches Trennzeichen (Soft Hyphen)
    ("x.sh:", "x.sh"),             # Doppelpunkt (Windows-ADS-Form)
    ('x.sh"', "x.sh"),             # Anführungszeichen (Header-Bruch)
])
def test_bereinigter_name_wird_mitgeprueft(rohname, anzeige):
    """Review R1/MUSS 1: die Sperrliste greift auf dem GESÄUBERTEN Namen."""
    # Vorbedingung: die Bereinigung macht aus dem Roh-Namen wirklich den
    # gesperrten Anzeigenamen — sonst prüfte der Test nichts.
    assert A.dateiname(rohname, A.UNBEKANNTER_TYP) == anzeige
    assert A.ist_gesperrt(anzeige) is True
    meldung = _abgewiesen(TXT, rohname)
    assert "nicht erlaubt" in meldung


def test_anhangsname_mit_gesperrter_endung_nach_bereinigung_endet_abgewiesen():
    """Derselbe Weg über ``nimm_upload`` — der Anzeigename kommt nie an."""
    with pytest.raises(ValidationError):
        _sperr(TXT, "werkzeug.py\x00")
    with pytest.raises(ValidationError):
        _sperr(TXT, "werkzeug\u200b.py")


def test_sauberer_name_bleibt_erlaubt():
    """Gegenprobe: die zusätzliche Prüfung sperrt keine harmlosen Namen."""
    for name in ("notiz.txt", "brief.docx", "MINI-Liste.csv", "noten.final.pdf"):
        assert _sperr(TXT if not name.endswith(".pdf") else PDF, name).typ


# ── 10) Review R1: Skript-Hosts (MUSS 3) ───────────────────────────────────


@pytest.mark.parametrize("endung", [
    ".js", ".jse", ".mjs", ".ws", ".vb",       # Windows Script Host / cscript
    ".ps1xml", ".msc", ".gadget",              # PowerShell / Snap-in / Gadget
])
def test_skript_host_endungen_sind_gesperrt(endung):
    """Review R1/MUSS 3: per Doppelklick ausführbare Endungen fehlten."""
    assert endung in A.GESPERRTE_ENDUNGEN
    _abgewiesen(TXT, f"werkzeug{endung}")
    _abgewiesen(TXT, f"WERKZEUG{endung.upper()}")


# ── 11) Review R1: echtes PE statt „MZ" (KANN 4) ───────────────────────────


def _mini_pe(e_lfanew: int = 0x80) -> bytes:
    """Ein echtes PE/COFF: ``MZ``-Kopf, ``e_lfanew`` → ``PE\\0\\0``."""
    kopf = b"MZ" + b"\x00" * 0x3A + struct.pack("<I", e_lfanew)
    return kopf.ljust(e_lfanew, b"\x00") + b"PE\x00\x00" + b"\x00" * 60


def test_echtes_pe_wird_abgewiesen():
    assert "PE" in _abgewiesen(_mini_pe(), "bericht.dat")


def test_mz_als_textanfang_ist_kein_programm():
    """Review R1/KANN 4: „MZ-Liste.csv" ist Text, kein Windows-Programm."""
    csv = b"MZ-Liste;Kostenstelle\n1;2\n"
    info = _sperr(csv, "MZ-Liste.csv")
    assert info.typ == A.UNBEKANNTER_TYP
    # Und auch als ``.dat`` (ohne PE-Kopf dahinter) bleibt es harmlos.
    assert _sperr(b"MZ", "kurz.dat").typ == A.UNBEKANNTER_TYP


# ── 12) Review R1: HTML/SVG am INHALT, nicht nur an der Endung (KANN 5) ────


@pytest.mark.parametrize("daten", [
    b"<!DOCTYPE html>\n<html><script>alert(1)</script></html>",
    b"  \xef\xbb\xbf<!-- x --><!doctype HTML><script>alert(1)</script>",
    b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
    b"<svg><script>alert(1)</script></svg>",
    b"<html><body onload=alert(1)></body></html>",
])
def test_html_svg_wird_auch_am_inhalt_erkannt(daten):
    """Review R1/KANN 5: HTML/SVG als ``.dat``/endungslos wird gesperrt."""
    assert "Markup" in _abgewiesen(daten, "bericht.dat")
    assert "Markup" in _abgewiesen(daten, "ohne-endung")


def test_office_xml_ohne_svg_bleibt_erlaubt():
    """Gegenprobe: XML OHNE SVG ist ein Dokument — nur die Sperr-Richtlinie."""
    xml = (b'<?xml version="1.0"?>\n<w:wordDocument xmlns:w="urn:x">'
           b"<w:body/></w:wordDocument>")
    assert _sperr(xml, "dokument.xml").typ == A.UNBEKANNTER_TYP


def test_chat_positivliste_erkennt_markup_nicht_als_typ():
    """Die Markup-Erkennung gilt NUR der Sperrliste — Chat bleibt unverändert."""
    with pytest.raises(ValidationError) as fehler:
        A.nimm_upload(_Upload(HTML, "seite.html"), richtlinie=A.RICHTLINIE_POSITIV)
    assert A.POSITIVLISTE_TEXT in str(fehler.value)


# ── 13) Review R1: ``name=`` des Aufrufers (MUSS 2) ────────────────────────


def test_name_parameter_hat_vorrang_vor_filename():
    """Review R1/MUSS 2: ``dateiname=`` des Chats kommt an wie zuvor."""
    info = A.nimm_upload(_Upload(PNG, "roh.png", "image/png"),
                         richtlinie=A.RICHTLINIE_POSITIV, name="attest.png")
    assert info.anzeigename == "attest.png"


def test_ohne_name_parameter_gilt_der_dateiname_des_uploads():
    info = A.nimm_upload(_Upload(PNG, "foto.png", "image/png"))
    assert info.anzeigename == "foto.png"


def test_name_parameter_wird_ebenfalls_geprueft():
    """Der Parameter ist kein Schlupfloch an der Sperrliste vorbei."""
    with pytest.raises(ValidationError):
        A.nimm_upload(_Upload(TXT, "harmlos.txt"), richtlinie=A.RICHTLINIE_SPERR,
                      name="werkzeug.sh")


def test_haken_sieht_den_namen_des_aufrufers(monkeypatch):
    """``pruefe_inhalt`` bekommt denselben Namen — eine Wahrheit."""
    gesehen: list[str | None] = []
    monkeypatch.setattr(A, "pruefe_inhalt", lambda roh, name=None: gesehen.append(name))
    A.nimm_upload(_Upload(PNG, "roh.png", "image/png"), name="attest.png")
    assert gesehen == ["attest.png"]


def test_chat_dateiname_parameter_kommt_an(gespraech, ablage):
    """Review R1/MUSS 2, ECHTER Chat-Endpunkt: ``dateiname=`` überschreibt."""
    from diakronos_app.api import chat as C

    _session_mod.set_user(SAENGER)
    antwort = C.anhang_hochladen(gespraech, datei=_Upload(PNG, "roh.png", "image/png"),
                                 dateiname="Attest vom Arzt.png")
    assert antwort["dateiname"] == "Attest vom Arzt.png"
