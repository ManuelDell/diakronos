"""CHAT-12a: Anhänge an Chat-Nachrichten (Backend, über SPEICHER-1).

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 (Zeile „Anhänge“) + F11. Geprüft
wird gegen die ECHTEN Endpunkte (``api.chat``), den ECHTEN Rechte-Kern und die
ECHTE Datenbank (SQLite in-memory) — die Datei-Ablage ist ein ``Lokal`` auf
``tmp_path`` (``setze_speicher``), NIE eine echte Nextcloud.

  * Typprüfung per MAGIE: umbenanntes Programm (``b"MZ..."`` als `.jpg`) wird
    abgelehnt, ein echtes PNG/PDF/MP3 angenommen; ``binary_content_type`` wird
    WIEDERVERWENDET (Kartenauflage), nicht kopiert
  * 10-MB-Grenze, 3er-Grenze je Nachricht, Tageskontingent (429)
  * fremder/nicht offener Anhang nicht anhängbar (gleiche 400, keine Auskunft)
  * Nachricht darf mit Anhang LEEREN Text haben
  * Herunterladen nur mit Leserecht (fremde Gruppe, Runde vor Eintritt,
    gelöschte Nachricht, offener Anhang, Modul aus → 404) und mit den
    geforderten Kopfzeilen
  * Löschen (selbst, Moderation, Fristen-Job, DSGVO, Gesprächsauflösung)
    entfernt AUCH das Speicherobjekt
  * Aufräumjob für offene Anhänge (> 24 h) und verwaiste Zeilen
  * ``verlauf``/``nachricht_kontext`` liefern ``anhaenge`` ohne N+1
  * Migration ``chat12a_anhang``: up/down/up, genau EIN Kopf
  * DSGVO-Inventar und SEC-11 (POST/GET, Inventar-Eintrag)

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat12a_anhang.py
"""

from __future__ import annotations

import importlib
import json
import struct
import zlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app.models.chat import (
    ANHAENGE_MAX,
    ANHAENGE_PRO_TAG,
    ANHANG_MAX_BYTES,
    ChatAnhang,
    ChatAnhangEntsorgung,
    ChatAnhangHochladung,
    ChatNachricht,
    ChatTeilnehmer,
)

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie die übrigen
#: Chat-Tests).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

#: Dieselbe Welt wie ``test_chat2_api`` (Chor mit Untergruppe, Chat-Modul AN) —
#: Fixture und Konten werden geteilt, nicht nachgebaut. ``test_chat7b_runden``
#: hat das Modul NICHT eingeschaltet (die Welt dort ist für Runden gedacht);
#: für Anhänge braucht es einen ECHTEN Chat.
from test_chat2_api import (  # noqa: E402,F401 — Fixture teilen
    ADMIN,
    FREMD,
    GL,
    HV,
    MV,
    NOTEN,
    SAENGER,
    _set_user,
    gespraech,
    welt,
)


def _set(konto: str) -> None:
    _session_mod.set_user(konto)


#: Mitglied-Kennung je Konto (aus der Chor-Welt von ``test_chat2_api``).
MI = {SAENGER: "M-Sa", NOTEN: "M-No", FREMD: "M-Fr", HV: "M-Hv", MV: "M-Mv",
      GL: "M-Gl", ADMIN: "M-Admin"}
ANNA = SAENGER
BERT = NOTEN
CLARA = MV
DIETER = FREMD


# ── Testdateien (echte Signaturen, keine Attrappen) ─────────────────────────


def _png(breite: int = 4, hoehe: int = 4) -> bytes:
    """Ein echtes, minimales PNG (nur Standardbibliothek)."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (struct.pack("!I", len(daten)) + typ + daten
                + struct.pack("!I", zlib.crc32(typ + daten) & 0xFFFFFFFF))

    ihdr = struct.pack("!IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0)
    roh = b"".join(b"\x00" + b"\xff\x00\x00" * breite for _ in range(hoehe))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(roh)) + chunk(b"IEND", b""))


PNG = _png()
JPG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 48
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
OGG = b"OggS\x00\x02" + b"\x00" * 64
#: HEIC: ISO-BMFF-``ftyp`` mit major brand ``heic`` und ``mif1`` als
#: kompatibles Brand — ``binary_content_type`` meldet dafür ``audio/mp4``;
#: die Erkennung im Endpunkt muss ``image/heic`` daraus machen.
HEIC = (struct.pack("!I", 24) + b"ftyp" + b"heic" + b"\x00\x00\x00\x00"
        + b"mif1heic" + b"\x00" * 32)
#: M4A: derselbe Container, aber Audio-Brand — ``audio/m4a`` ist erlaubt.
M4A = (struct.pack("!I", 24) + b"ftyp" + b"M4A " + b"\x00\x00\x00\x00"
       + b"M4A mp42isom" + b"\x00" * 32)
#: MP4-Video: gleicher ``ftyp`` (``isom``) — der Client deklariert ``video/mp4``
#: und wird abgelehnt.
MP4_VIDEO = (struct.pack("!I", 24) + b"ftyp" + b"isom" + b"\x00\x00\x00\x00"
             + b"isomiso2mp41" + b"\x00" * 32)
#: Ein Windows-Programm, als `.jpg` umbenannt (Kartenfall).
EXE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64


class _Upload:
    """``UploadFile``-artig: ``.read``/``.file``/``.filename``/``.content_type``."""

    def __init__(self, daten: bytes, filename: str, content_type: str) -> None:
        import io

        self.file = io.BytesIO(daten)
        self.filename = filename
        self.content_type = content_type

    def read(self, *args):  # pragma: no cover — der Endpunkt liest ``.file``
        return self.file.read(*args)


# ── Ablage-Attrappe: ``Lokal`` auf tmp_path ─────────────────────────────────


@pytest.fixture()
def ablage(tmp_path):
    """Die Ablage NUR für diesen Test auf ein ``tmp_path`` stellen.

    Kein Netz, keine Nextcloud: ``setze_speicher`` mit einem lokalen Backend
    (die Kartenauflage). Der Speicher wird nach dem Test zurückgesetzt.
    """
    from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher

    ordner = tmp_path / "files"
    ordner.mkdir()
    speicher = Lokal(ordner)
    setze_speicher(speicher)
    try:
        yield speicher
    finally:
        vergiss_speicher()


def _objekte(ablage) -> list[str]:
    """Alle Schluessel in der Ablage (Dateien, rekursiv)."""
    return sorted(ablage.auflisten(""))


# ── Aufruf-Hilfen ───────────────────────────────────────────────────────────


def _hochladen(gespraech: str, konto: str, daten: bytes = PNG,
               filename: str = "foto.jpg", typ: str = "image/jpeg") -> dict:
    from diakronos_app.api import chat as C

    _set(konto)
    return C.anhang_hochladen(gespraech, datei=_Upload(daten, filename, typ))


def _senden(gespraech: str, text, konto: str, anhaenge=None, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set(konto)
    return C.senden(gespraech, text, anhaenge=anhaenge, **kwargs)


def _herunterladen(name: str, konto: str):
    from diakronos_app.api import chat as C

    _set(konto)
    return C.anhang(name)


def _verlauf(gespraech: str, konto: str, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set(konto)
    return C.verlauf(gespraech, **kwargs)


def _schluessel_von(anhang: str) -> str:
    """Der SPEICHER-Schlüssel einer Anhang-Kennung (aus der Zeile, nicht geraten)."""
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatAnhang, anhang)
        assert zeile is not None, anhang
        return str(zeile.schluessel)


def _zeile(gespraech: str, konto: str, name: str) -> dict:
    seite = _verlauf(gespraech, konto)
    return next(n for n in seite["nachrichten"] if n["name"] == name)


def _gespraech(gruppe: str = "Chor", konto: str = ANNA) -> str:
    """Das Gruppen-Gespräch einer Einheit (legt es lazy an)."""
    from diakronos_app.api import chat as C

    _set(konto)
    return C.gespraech_anlegen(gruppe)["name"]


def _untergruppe(konto: str = ANNA) -> str:
    """Das Gespräch der Untergruppe ``UG-Noten`` (eigener Raum, F4)."""
    from diakronos_app.api import chat as C

    _set(konto)
    return C.gespraech_anlegen("Chor", "UG-Noten")["name"]


def _runde(titel: str, mitglieder, konto: str = ANNA) -> dict:
    from diakronos_app.api import chat as C

    _set(konto)
    return C.runde_anlegen(titel, mitglieder)


def _anhang_zeilen(nachricht: str | None = None) -> list[ChatAnhang]:
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        abfrage = s.query(ChatAnhang)
        if nachricht is not None:
            abfrage = abfrage.filter(ChatAnhang.nachricht == nachricht)
        return list(abfrage.all())


def _kopf_und_koerper(antwort) -> tuple[dict, bytes]:
    """Kopfzeilen und Bytes einer ``StreamingResponse`` einsammeln.

    Der Iterator der Antwort ist (Starlette) ein Async-Generator — auch für
    einen synchronen Block-Generator. Gelesen wird er deshalb in einer eigenen
    Ereignisschleife; das ist kein Test-Trick, sondern genau der Weg, den der
    Server beim Ausliefern nimmt.
    """
    import asyncio

    kopf = dict(antwort.headers)
    teile: list[bytes] = []

    async def _sammeln() -> None:
        async for block in antwort.body_iterator:
            teile.append(block.encode("utf-8") if isinstance(block, str) else block)

    asyncio.run(_sammeln())
    return kopf, b"".join(teile)


# ── 1) Hochladen: Typ per Magie, Grenzen ────────────────────────────────────


def test_hochladen_legt_offenen_anhang_an_und_schreibt_in_die_ablage(gespraech, ablage):
    g = gespraech
    antwort = _hochladen(g, ANNA, PNG, "Foto Proberaum.png", "image/png")
    assert antwort["mime"] == "image/png"
    assert antwort["dateiname"] == "Foto Proberaum.png"
    assert antwort["groesse"] == len(PNG)
    assert antwort["gespraech"] == g and antwort["name"]

    zeilen = _anhang_zeilen()
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile.nachricht is None            # „offen“
    assert zeile.angelegt_von == ANNA
    assert zeile.gespraech == g
    # Die DATEI liegt in der Ablage (Schluessel = technische Kennung), NICHT
    # in einem zweiten Speicherweg.
    assert _objekte(ablage) == [zeile.schluessel]
    assert ablage.lesen(zeile.schluessel) == PNG
    # Der Speicherschluessel geht NICHT nach aussen.
    assert "schluessel" not in antwort
    from diakronos_app.models.core import FileModel
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        assert s.query(FileModel).count() == 0


@pytest.mark.parametrize("daten,filename,typ,erwartet", [
    (PNG, "a.png", "image/png", "image/png"),
    (JPG, "a.jpg", "image/jpeg", "image/jpeg"),
    (PDF, "notenblatt.pdf", "application/pdf", "application/pdf"),
    (MP3, "aufnahme.mp3", "audio/mpeg", "audio/mpeg"),
    (OGG, "aufnahme.ogg", "audio/ogg", "audio/ogg"),
    (HEIC, "iphone.heic", "image/heic", "image/heic"),
    (M4A, "aufnahme.m4a", "audio/mp4", "audio/mp4"),
])
def test_erlaubte_typen_werden_per_magie_erkannt(gespraech, ablage, daten, filename,
                                                 typ, erwartet):
    g = gespraech
    antwort = _hochladen(g, ANNA, daten, filename, typ)
    assert antwort["mime"] == erwartet
    assert len(_anhang_zeilen()) == 1


def test_umbenanntes_programm_als_jpg_wird_abgelehnt(gespraech, ablage):
    """Der Kartenfall: eine .exe als .jpg — abgelehnt, KEINE Datei, KEINE Zeile."""
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    with pytest.raises(ValidationError):
        _hochladen(g, ANNA, EXE, "harmlos.jpg", "image/jpeg")
    assert _anhang_zeilen() == []
    assert _objekte(ablage) == []


def test_video_mp4_wird_abgelehnt(gespraech, ablage):
    """Derselbe Container wie .m4a — ein Video-Upload deklariert ``video/mp4``."""
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    with pytest.raises(ValidationError):
        _hochladen(g, ANNA, MP4_VIDEO, "clip.mp4", "video/mp4")
    assert _anhang_zeilen() == []


def test_binary_content_type_wird_wiederverwendet_nicht_kopiert():
    """Kartenauflage: ``files.binary_content_type`` ist die EINE Magazine-Quelle."""
    from diakronos_app.api import chat as C
    from diakronos_app import files as F

    quelle = Path(F.__file__).read_text(encoding="utf-8")
    assert "def binary_content_type" in quelle
    assert C._anhang_typ(PNG) == F.binary_content_type(PNG) == "image/png"
    # Ein Programm hat KEINE der erlaubten Signaturen -> die EINE Pruefung
    # (``binary_content_type``) meldet ``None``, der Endpunkt lehnt ab.
    assert F.binary_content_type(EXE) is None
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        C._anhang_typ(EXE)


def test_leere_datei_wird_abgelehnt(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    with pytest.raises(ValidationError):
        _hochladen(g, ANNA, b"", "leer.png", "image/png")
    assert _anhang_zeilen() == []


def test_groessengrenze_10_mb(gespraech, ablage):
    """Genau an der Grenze geht, ein Byte mehr nicht — und die Zeile fehlt."""
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    gerade = PNG + b"\x00" * (ANHANG_MAX_BYTES - len(PNG))
    antwort = _hochladen(g, ANNA, gerade, "gross.png", "image/png")
    assert antwort["groesse"] == ANHANG_MAX_BYTES

    with pytest.raises(ValidationError):
        _hochladen(g, ANNA, gerade + b"\x00", "zu-gross.png", "image/png")
    assert len(_anhang_zeilen()) == 1


def test_dateiname_wird_bereinigt_und_begrenzt(gespraech, ablage):
    g = gespraech
    antwort = _hochladen(g, ANNA, PNG, "../../etc/pass wort\r\n.png", "image/png")
    name = antwort["dateiname"]
    assert "/" not in name and "\\" not in name
    assert "\r" not in name and "\n" not in name
    assert len(name) <= 120

    lang = "x" * 200 + ".png"
    antwort = _hochladen(g, ANNA, PNG, lang, "image/png")
    assert len(antwort["dateiname"]) <= 120
    assert antwort["dateiname"].endswith(".png")


def test_ohne_datei_ist_400(gespraech, ablage):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    _set(ANNA)
    with pytest.raises(ValidationError):
        C.anhang_hochladen(g)


# ── 2) Rechte beim Hochladen ────────────────────────────────────────────────


def test_hochladen_hat_dieselbe_pruefung_wie_senden(gespraech, ablage):
    """Dieter ist in der Gruppe nicht Mitglied → dieselbe Ablehnung wie ``senden``."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError  # noqa: A004

    g = _gespraech("Chor", ANNA)
    _set(DIETER)
    with pytest.raises(PermissionError):
        C.senden(g, "Hallo")
    with pytest.raises(PermissionError):
        C.anhang_hochladen(g, datei=_Upload(PNG, "a.png", "image/png"))
    assert _anhang_zeilen() == []


def test_hochladen_in_fremde_runde_ist_403(gespraech, ablage):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError  # noqa: A004

    runde = _runde("Deko", [MI[BERT], MI[CLARA]])
    _set(DIETER)
    with pytest.raises(PermissionError):
        C.anhang_hochladen(runde["name"], datei=_Upload(PNG, "a.png", "image/png"))


# ── 3) Anhängen an eine Nachricht ───────────────────────────────────────────


def test_senden_haengt_anhang_an_und_verlauf_zeigt_ihn(gespraech, ablage):
    g = gespraech
    hoch = _hochladen(g, ANNA, PNG, "wand.png", "image/png")
    antwort = _senden(g, "So sieht es aus", ANNA, anhaenge=[hoch["name"]])
    assert [a["name"] for a in antwort["anhaenge"]] == [hoch["name"]]
    assert antwort["anhaenge"][0]["dateiname"] == "wand.png"
    assert antwort["anhaenge"][0]["mime"] == "image/png"
    assert antwort["anhaenge"][0]["groesse"] == len(PNG)

    zeile = _zeile(g, BERT, antwort["name"])
    assert [a["name"] for a in zeile["anhaenge"]] == [hoch["name"]]

    (zeile_db,) = _anhang_zeilen()
    assert zeile_db.nachricht == antwort["name"]


def test_nachricht_mit_anhang_darf_leeren_text_haben(gespraech, ablage):
    g = gespraech
    # JE Nachricht EIN eigener Anhang — ein Anhang haengt genau einmal.
    hoch = _hochladen(g, ANNA, PNG)
    antwort = _senden(g, "", ANNA, anhaenge=[hoch["name"]])
    assert antwort["text"] == ""
    assert len(antwort["anhaenge"]) == 1

    hoch2 = _hochladen(g, ANNA, PNG)
    antwort2 = _senden(g, None, ANNA, anhaenge=[hoch2["name"]])
    assert antwort2["text"] == ""

    # OHNE Anhang bleibt „leer“ ein Fehler (bestehende Regel).
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        _senden(g, "", ANNA)
    with pytest.raises(ValidationError):
        _senden(g, None, ANNA)


def test_drei_anhaenge_gehen_ein_vierter_nicht(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    kennungen = [_hochladen(g, ANNA, PNG, f"a{i}.png", "image/png")["name"]
                 for i in range(4)]
    antwort = _senden(g, "Vier Bilder", ANNA, anhaenge=kennungen[:ANHAENGE_MAX])
    assert len(antwort["anhaenge"]) == ANHAENGE_MAX

    with pytest.raises(ValidationError):
        _senden(g, "Vier Bilder", ANNA, anhaenge=kennungen)
    # Der vierte bleibt OFFEN (nichts halb angehängt).
    offen = [a for a in _anhang_zeilen() if a.nachricht is None]
    assert [a.name for a in offen] == [kennungen[3]]


def test_fremder_offener_anhang_ist_nicht_anhaengbar(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    fremd = _hochladen(g, ANNA)["name"]
    with pytest.raises(ValidationError):
        _senden(g, "Deins ist jetzt meins", BERT, anhaenge=[fremd])
    # Unbekannte Kennung antwortet GLEICH (keine Auskunft).
    with pytest.raises(ValidationError):
        _senden(g, "x", ANNA, anhaenge=["chat-anhang-gibt-es-nicht"])
    assert all(a.nachricht is None for a in _anhang_zeilen())


def test_anhang_aus_anderem_gespraech_ist_nicht_anhaengbar(gespraech, ablage):
    """Derselbe Absender, ein ANDERES Gespräch → dieselbe 400 wie fremd.

    Anna lädt im Chor-Gespräch hoch; gesendet wird im Untergruppen-Gespräch
    (sie ist dort Mitglied: ``M-Sa`` steht in ``gm1``). Der Anhang hängt am
    falschen Gespräch und darf nicht mitwandern.
    """
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.models.diakonos import Untergruppenmitgliedschaft
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal.begin() as s:
        s.add(Untergruppenmitgliedschaft(name="ugm-sa", parent="UG-Noten",
                                         parentfield="mitglieder", mitglied=MI[ANNA]))

    g1 = gespraech
    g2 = _untergruppe(ANNA)
    assert g1 != g2
    fremd = _hochladen(g1, ANNA)["name"]
    with pytest.raises(ValidationError):
        _senden(g2, "Passt nicht", ANNA, anhaenge=[fremd])


def test_bereits_angehaengter_anhang_ist_nicht_zweimal_verwendbar(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    _senden(g, "Einmal", ANNA, anhaenge=[hoch])
    with pytest.raises(ValidationError):
        _senden(g, "Zweimal", ANNA, anhaenge=[hoch])


def test_anhaenge_als_json_zeichenkette_wie_aus_einem_formular(gespraech, ablage):
    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    antwort = _senden(g, "Formular", ANNA, anhaenge=json.dumps([hoch]))
    assert [a["name"] for a in antwort["anhaenge"]] == [hoch]


# ── 4) Herunterladen: Rechte, Header, Streaming ─────────────────────────────


def test_herunterladen_liefert_bytes_und_header(gespraech, ablage):
    g = gespraech
    hoch = _hochladen(g, ANNA, PNG, "foto ä.png", "image/png")
    antwort = _senden(g, "Bild", ANNA, anhaenge=[hoch["name"]])

    ergebnis = _herunterladen(hoch["name"], BERT)
    kopf, koerper = _kopf_und_koerper(ergebnis)
    assert koerper == PNG
    assert kopf["content-type"] == "image/png"
    assert kopf["x-content-type-options"] == "nosniff"
    assert kopf["content-length"] == str(len(PNG))
    # Bilder INLINE (die Oberfläche zeigt sie) …
    assert kopf["content-disposition"].startswith("inline;")
    assert "filename*=UTF-8''" in kopf["content-disposition"]
    assert antwort["name"]  # nur zur Klarheit: es gibt eine Nachricht


def test_pdf_und_audio_gehen_als_attachment(gespraech, ablage):
    g = gespraech
    pdf = _hochladen(g, ANNA, PDF, "noten.pdf", "application/pdf")
    _senden(g, "Noten", ANNA, anhaenge=[pdf["name"]])
    kopf, koerper = _kopf_und_koerper(_herunterladen(pdf["name"], BERT))
    assert koerper == PDF
    assert kopf["content-type"] == "application/pdf"
    assert kopf["content-disposition"].startswith("attachment;")

    audio = _hochladen(g, ANNA, MP3, "probe.mp3", "audio/mpeg")
    _senden(g, "Probe", ANNA, anhaenge=[audio["name"]])
    kopf, _ = _kopf_und_koerper(_herunterladen(audio["name"], BERT))
    assert kopf["content-type"] == "audio/mpeg"
    assert kopf["content-disposition"].startswith("attachment;")


def test_fremde_gruppe_bekommt_404(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    g = _gespraech("Chor", ANNA)
    hoch = _hochladen(g, ANNA)["name"]
    _senden(g, "Nur für die Gruppe", ANNA, anhaenge=[hoch])
    with pytest.raises(DoesNotExistError):
        _herunterladen(hoch, DIETER)


def test_runde_vor_eintritt_bekommt_404(gespraech, ablage, patched_db):
    """Wer erst NACH der Nachricht eintrat, sieht den Anhang nicht (404)."""
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    runde = _runde("Kigo", [MI[BERT], MI[CLARA]])
    hoch = _hochladen(runde["name"], ANNA)["name"]
    _senden(runde["name"], "Vor deinem Eintritt", ANNA, anhaenge=[hoch])

    s = patched_db()
    zeile = s.get(ChatTeilnehmer, (runde["name"], BERT))
    zeile.sichtbar_ab = datetime(2030, 1, 1, 12, 0)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    with pytest.raises(DoesNotExistError):
        _herunterladen(hoch, BERT)
    # Clara (vor dem Eintritt dabei) kommt weiterhin dran.
    kopf, koerper = _kopf_und_koerper(_herunterladen(hoch, CLARA))
    assert koerper == PNG


def test_geloeschte_nachricht_und_offener_anhang_sind_404(gespraech, ablage):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    g = gespraech
    offen = _hochladen(g, ANNA)["name"]
    with pytest.raises(DoesNotExistError):
        _herunterladen(offen, ANNA)

    hoch = _hochladen(g, ANNA)["name"]
    nachricht = _senden(g, "Weg damit", ANNA, anhaenge=[hoch])
    _set(ANNA)
    C.loeschen(nachricht["name"])
    with pytest.raises(DoesNotExistError):
        _herunterladen(hoch, ANNA)


def test_unbekannte_kennung_ist_404_wie_fehlendes_recht(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    with pytest.raises(DoesNotExistError):
        _herunterladen("chat-anhang-gibt-es-nicht", ANNA)
    with pytest.raises(DoesNotExistError):
        _herunterladen("", ANNA)


def test_modul_aus_bekommt_404(gespraech, ablage, patched_db):
    """Dieselbe Prüfung wie der Verlauf: Modul ``chat`` aus → kein Lesen → 404."""
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    g = _gespraech("Chor", ANNA)
    hoch = _hochladen(g, ANNA)["name"]
    _senden(g, "Inhalt", ANNA, anhaenge=[hoch])

    # Das Modul für die Gruppe abschalten (die Zeile IST der Schalter).
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.query(RechteModul).filter(RechteModul.gruppe == "Chor",
                                RechteModul.modul == "chat").delete()
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    with pytest.raises(DoesNotExistError):
        _herunterladen(hoch, BERT)


def test_datei_aus_der_ablage_verschwunden_ist_404(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    _senden(g, "Da war was", ANNA, anhaenge=[hoch])
    (zeile,) = _anhang_zeilen()
    ablage.loeschen(zeile.schluessel)
    with pytest.raises(DoesNotExistError):
        _herunterladen(hoch, BERT)


# ── 5) Löschen entfernt die Datei ───────────────────────────────────────────


def test_loeschen_entfernt_zeile_und_datei(gespraech, ablage):
    from diakronos_app.api import chat as C

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    nachricht = _senden(g, "Wird gelöscht", ANNA, anhaenge=[hoch])
    (zeile,) = _anhang_zeilen()
    assert ablage.existiert(zeile.schluessel)

    _set(ANNA)
    antwort = C.loeschen(nachricht["name"])
    assert antwort["geloescht"] is True and antwort["anhaenge"] == []
    assert _anhang_zeilen() == []
    assert not ablage.existiert(zeile.schluessel)
    assert _objekte(ablage) == []


def test_moderation_entfernt_die_datei(gespraech, ablage):
    from diakronos_app.api import chat as C

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    nachricht = _senden(g, "Böse", ANNA, anhaenge=[hoch])
    (zeile,) = _anhang_zeilen()

    _set(BERT)
    gemeldet = C.meldung_senden(nachricht["name"], "spam")
    _set("Administrator")
    C.meldung_entscheiden(gemeldet["name"], "entfernen", grund="Regelverstoss")
    assert _anhang_zeilen() == []
    assert not ablage.existiert(zeile.schluessel)


def test_fristen_job_entfernt_gespraech_und_dateien(gespraech, ablage):
    """CHAT-8: die Gesprächsauflösung nimmt die Anhang-DATEIEN mit."""
    from diakronos_app import chat_aufbewahrung as A

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    _senden(g, "Alt", ANNA, anhaenge=[hoch])
    (zeile,) = _anhang_zeilen()
    assert ablage.existiert(zeile.schluessel)

    spaeter = datetime(2035, 1, 1, 12, 0)
    ergebnis = A.aufraeumen(jetzt=spaeter)
    assert ergebnis["gespraeche"] == 1
    assert ergebnis["dateien"] == 1
    assert _anhang_zeilen() == []
    assert _objekte(ablage) == []


def test_dsgvo_anonymisierung_entfernt_zeile_und_datei(gespraech, ablage, patched_db):
    """Die Zeile fällt in ``anonymisiere``, die DATEI nach dem Commit.

    Der Endpunkt ruft beides nacheinander (``api.datenschutz``: erst
    ``anonymisiere`` + ``commit``, dann ``dateien_entfernen``). Der Test geht
    DENSELBEN Weg — ein Rollback darf keine Datei gelöscht haben.
    """
    from diakronos_app import dsgvo_anonymisierung as D

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    _senden(g, "Mein Foto", ANNA, anhaenge=[hoch])
    (zeile,) = _anhang_zeilen()

    s = patched_db()
    ergebnis = D.anonymisiere(s, MI[ANNA], [ANNA])
    s.commit()
    # Nach dem Commit: Zeile weg, Datei NOCH da (der Rollback-Fall ist damit
    # ausgeschlossen).
    assert _anhang_zeilen() == []
    assert ablage.existiert(zeile.schluessel)

    assert ergebnis["dateien"] == [zeile.schluessel]
    entfernt = D.dateien_entfernen(ergebnis["dateien"])
    assert entfernt == 1
    assert not ablage.existiert(zeile.schluessel)

    # Der Text der Nachricht bleibt (er gehört den anderen).
    s = patched_db()
    texte = [n.text for n in s.query(ChatNachricht).all()]
    assert "Mein Foto" in texte


# ── 6) Aufräumjob ───────────────────────────────────────────────────────────


def test_aufraeumjob_entfernt_offene_anhaenge_nach_24_stunden(gespraech, ablage):
    from diakronos_app.api import chat as C

    g = gespraech
    alt = _hochladen(g, ANNA)["name"]
    frisch = _hochladen(g, ANNA)["name"]

    # Einen der beiden künstlich altern lassen (Tests schlafen nicht).
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal.begin() as s:
        zeile = s.get(ChatAnhang, alt)
        zeile.angelegt_am = datetime(2026, 1, 1, 8, 0)

    ergebnis = C.chat_anhaenge_aufraeumen(jetzt=datetime(2026, 1, 2, 9, 0))
    assert ergebnis["offen"] == 1
    assert ergebnis["dateien"] == 1
    namen = {a.name for a in _anhang_zeilen()}
    assert namen == {frisch}
    assert len(_objekte(ablage)) == 1

    # Zweiter Lauf: nichts mehr zu tun (idempotent).
    ergebnis2 = C.chat_anhaenge_aufraeumen(jetzt=datetime(2026, 1, 2, 10, 0))
    assert ergebnis2["offen"] == 0


def test_aufraeumjob_raeumt_verwaiste_zeilen_und_dateien(gespraech, ablage):
    from diakronos_app.api import chat as C
    from diakronos_app import db as dbmod

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    nachricht = _senden(g, "Wird hart gelöscht", ANNA, anhaenge=[hoch])
    (zeile,) = _anhang_zeilen()

    # Die Nachricht „endgültig“ entfernen, die Anhang-Zeile bleibt (so sähe es
    # nach einem abgebrochenen Lauf aus) — SQLite erzwingt die FK nicht.
    with dbmod.SessionLocal.begin() as s:
        s.delete(s.get(ChatNachricht, nachricht["name"]))

    ergebnis = C.chat_anhaenge_aufraeumen()
    assert ergebnis["verwaist"] == 1
    assert _anhang_zeilen() == []
    assert not ablage.existiert(zeile.schluessel)


# ── 7) Tageskontingent ──────────────────────────────────────────────────────


def test_tageskontingent_429(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import RateLimitError

    g = gespraech
    for _ in range(ANHAENGE_PRO_TAG):
        _hochladen(g, ANNA)
    assert len(_anhang_zeilen()) == ANHAENGE_PRO_TAG

    with pytest.raises(RateLimitError) as fehler:
        _hochladen(g, ANNA)
    assert getattr(fehler.value, "http_status", None) == 429
    assert len(_anhang_zeilen()) == ANHAENGE_PRO_TAG

    # Ein anderes Konto ist NICHT betroffen (Grenze je Person).
    _hochladen(g, BERT)


def test_kontingent_gilt_je_kalendertag(gespraech, ablage):
    """Review R1/4: die Marken der Person tragen den Tag — „gestern“ ist frei."""
    from diakronos_app import db as dbmod

    g = gespraech
    for _ in range(ANHAENGE_PRO_TAG):
        _hochladen(g, ANNA)
    # Die MARKEN auf „gestern“ schieben (nicht die Anhang-Zeilen: die Marke
    # ist seit R1/4 die Grundlage der Zählung) → heute ist wieder Platz.
    with dbmod.SessionLocal.begin() as s:
        for zeile in s.query(ChatAnhangHochladung).all():
            zeile.angelegt_am = zeile.angelegt_am - timedelta(days=1)
    _hochladen(g, ANNA)


def test_kontingent_zaehlt_marken_nicht_zeichen(gespraech, ablage):
    """Review R1/4 — der Kern des Punktes: Löschen gibt KEIN Kontingent zurück.

    Vorher zählte die Grenze die vorhandenen ``chat_anhang``-Zeilen. Wer
    hochlädt, sendet und die Nachricht löscht, hatte damit ein unbegrenztes
    Kontingent. Jetzt zählt die Hochlade-MARKE, die beim Löschen stehen bleibt:
    hochladen → senden → löschen (öfter als ``ANHAENGE_PRO_TAG``) → der 21.
    Upload ist 429.
    """
    import pytest

    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import RateLimitError

    g = gespraech
    runden = ANHAENGE_PRO_TAG // ANHAENGE_MAX  # 6 Runden à 3 = 18
    for _ in range(runden):
        kennungen = [_hochladen(g, ANNA)["name"] for _ in range(ANHAENGE_MAX)]
        antwort = _senden(g, "mit Anhängen", ANNA, anhaenge=kennungen)
        _set(ANNA)
        C.loeschen(antwort["name"])
    assert ANHAENGE_PRO_TAG - runden * ANHAENGE_MAX == 2
    # Zwei gehen noch — dann ist die Grenze erreicht.
    _hochladen(g, ANNA)
    _hochladen(g, ANNA)
    with pytest.raises(RateLimitError):
        _hochladen(g, ANNA)


# ── 8) Kein N+1 ─────────────────────────────────────────────────────────────


def test_verlauf_laedt_anhaenge_mit_einer_abfrage(gespraech, ablage):
    """20 Nachrichten mit je einem Anhang → genau EINE Anhang-Abfrage."""
    from sqlalchemy import event

    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C

    g = gespraech
    for i in range(20):
        hoch = _hochladen(g, ANNA, PNG, f"b{i}.png", "image/png")["name"]
        _senden(g, f"Nachricht {i}", ANNA, anhaenge=[hoch])

    treffer: list[str] = []

    def _zaehle(conn, cursor, statement, parameter, context, executemany):
        if "chat_anhang" in statement:
            treffer.append(statement)

    _set(BERT)
    motor = dbmod.engine
    event.listen(motor, "before_cursor_execute", _zaehle)
    try:
        seite = C.verlauf(g)
    finally:
        event.remove(motor, "before_cursor_execute", _zaehle)

    assert len(seite["nachrichten"]) == 20
    assert all(len(n["anhaenge"]) == 1 for n in seite["nachrichten"])
    anhang_abfragen = [t for t in treffer if "FROM chat_anhang" in t]
    assert len(anhang_abfragen) == 1, anhang_abfragen


# ── 9) SEC-11, Inventar, Migration ──────────────────────────────────────────


def test_endpunkte_sind_post_bzw_lesend_und_allow_guest_false():
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import registry

    hoch = registry.options_for(C.anhang_hochladen)
    assert hoch.get("allow_guest") is False
    assert hoch.get("methods") == ("POST",)

    herunter = registry.options_for(C.anhang)
    assert herunter.get("allow_guest") is False
    assert herunter.get("methods") is None


def test_inventar_kennt_hochladen_als_schreibend_und_keine_neuen_widersprueche():
    daten = json.loads((BACKEND / "src" / "diakronos_app" / "frappe_compat"
                        / "inventar" / "whitelist.json").read_text(encoding="utf-8"))
    eintrag = next(e for e in daten["eintraege"]
                   if e["funktion"] == "diakronos_app.api.chat.anhang_hochladen")
    assert eintrag["einstufung"] == "schreibend", eintrag
    # Die Deklaration ist POST (der Wächter ``test_sec11_methoden`` prüft es am
    # Register; hier steht der Register-Stand im Inventar).
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import registry

    assert registry.options_for(C.anhang_hochladen).get("methods") == ("POST",)

    text = (BACKEND / "src" / "diakronos_app" / "frappe_compat" / "inventar"
            / "whitelist.md").read_text(encoding="utf-8")
    abschnitt = text.split("## Widersprueche", 1)[1].split("Entschieden ohne", 1)[0]
    zeilen = [z for z in abschnitt.splitlines()
              if z.startswith("| `") and "Funktion" not in z]
    assert len(zeilen) <= 2, zeilen


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_haengt_hinter_chat10a_push_und_es_gibt_einen_kopf():
    """R1/0: seit dem Merge des Web-Push-Zweigs hängt die Kette an ``chat10a_push``.

    Der Kartenauftrag verlangt genau EINEN Kopf. ``chat12a_anhang`` hängt
    deshalb nicht mehr an ``chat9a_erwaehnung``; seit Sammel 9 hängt es
    hinter dem Suchindex ``chat11a_suche`` (der selbst an ``chat10a_push``
    hängt); danach kommen
    ``chat12a_entsorgung`` (Entsorgungsliste + Hochlade-Marken) und
    ``chat12a2_backoff`` (Spalte ``naechster_versuch_am``, CHAT-12a-2) — der
    Kopf ist die letzte.
    """
    skripte = _skripte()
    rev = skripte.get_revision("chat12a_anhang")
    assert rev is not None
    assert rev.down_revision == "chat11a_suche", rev.down_revision
    assert "Revises: chat11a_suche" in Path(rev.path).read_text(encoding="utf-8")
    # Die Entsorgungs-Revision hängt direkt daran.
    entsorgung = skripte.get_revision("chat12a_entsorgung")
    assert entsorgung is not None
    assert entsorgung.down_revision == "chat12a_anhang", entsorgung.down_revision
    # CHAT-12a-2: der Backoff hängt HINTER der Entsorgungs-Revision.
    backoff = skripte.get_revision("chat12a2_backoff")
    assert backoff is not None
    assert backoff.down_revision == "chat12a_entsorgung", backoff.down_revision
    assert "Revises: chat12a_entsorgung" in Path(backoff.path).read_text(encoding="utf-8")
    assert len(skripte.get_bases()) == 1
    heads = skripte.get_heads()
    assert heads == ["chat12a2_backoff"], heads
    # Alle Revisionen liegen in DERSELBEN Kette (keine abgehängte Linie).
    kette = {r.revision for r in skripte.iterate_revisions(heads[0], "base")}
    assert {"chat9a_erwaehnung", "chat10a_push", "chat12a_anhang",
            "chat12a_entsorgung", "chat12a2_backoff"} <= kette


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine mit allen Modelltabellen, ``chat_anhang`` entfernt."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    with eng.begin() as verbindung:
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_anhang"')
    yield eng
    eng.dispose()


def _migration():
    import importlib.util

    pfad = BACKEND / "alembic" / "versions" / "chat12a_anhang.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("chat12a_anhang", pfad))
    modul.__spec__.loader.exec_module(modul)
    return modul


def test_migration_upgrade_downgrade_upgrade(fresh_engine):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    modul = _migration()
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.upgrade()  # idempotent
        insp = inspect(verbindung)
        assert insp.has_table("chat_anhang")
        spalten = {c["name"] for c in insp.get_columns("chat_anhang")}
        assert {"name", "nachricht", "gespraech", "schluessel", "dateiname",
                "mime", "groesse", "angelegt_am", "angelegt_von"} <= spalten
        assert insp.get_pk_constraint("chat_anhang")["constrained_columns"] == ["name"]
        namen = {i["name"] for i in insp.get_indexes("chat_anhang")}
        assert "ix_chat_anhang_nachricht" in namen
        assert "ix_chat_anhang_angelegt_von_am" in namen
        ziele = {(fk["constrained_columns"][0], fk["referred_table"])
                 for fk in insp.get_foreign_keys("chat_anhang")}
        assert ("nachricht", "chat_nachricht") in ziele
        assert ("gespraech", "chat_gespraech") in ziele
        nachricht_fk = next(fk for fk in insp.get_foreign_keys("chat_anhang")
                            if fk["constrained_columns"] == ["nachricht"])
        assert nachricht_fk["options"].get("ondelete", "").upper() == "CASCADE"

    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
        assert not inspect(verbindung).has_table("chat_anhang")
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
        assert inspect(verbindung).has_table("chat_anhang")


def test_downgrade_ist_laut_wenn_anhaenge_existieren(fresh_engine):
    """Eine stille Datenvernichtung gibt es nicht."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    modul = _migration()
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            verbindung.exec_driver_sql(
                "INSERT INTO chat_gespraech (name, art, angelegt_am) "
                "VALUES ('g1', 'gruppe', '2026-01-01 00:00:00')"
            )
            verbindung.exec_driver_sql(
                "INSERT INTO chat_anhang (name, gespraech, schluessel, dateiname, "
                "mime, groesse, angelegt_am) VALUES ('a1', 'g1', 's1', 'x.png', "
                "'image/png', 10, '2026-01-01 00:00:00')"
            )
            with pytest.raises(RuntimeError):
                modul.downgrade()


# ── Review R1/3: Entsorgungsliste ──────────────────────────────────────────
#
# Die Auflage: JEDER Weg, der ``chat_anhang``-Zeilen löscht, schreibt die
# Speicher-Schlüssel in DERSELBEN Transaktion in ``chat_anhang_entsorgung``.
# Ein Job löscht die Datei und danach die Zeile; „nicht vorhanden“ ist Erfolg,
# ein Fehler zählt ``versuche`` hoch und bleibt für den nächsten Lauf stehen.
# Vorher blieb eine Datei nach einem gescheiterten Ablage-Löschen für immer
# liegen („nach dem Commit, nur loggen“).


def _entsorgung(ablage) -> list[str]:
    """Die offenen Entsorgungs-Aufträge (Schlüssel, sortiert)."""
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        return sorted(str(k) for k in s.query(ChatAnhangEntsorgung.schluessel).all()
                      for k in [k[0]])


class _FehlerndeAblage:
    """Ablage-Attrappe: ``loeschen`` scheitert bei den ersten ``fehler`` Aufrufen.

    Alles andere reicht sie an die echte (lokale) Ablage weiter — die Datei
    liegt also wirklich da, und nach den Fehlversuchen ist sie wirklich weg.
    Auch ``loeschen_mit_zeitlimit`` (CHAT-12a-2) läuft über ``loeschen``: sonst
    bediente ``__getattr__`` die Methode der echten Ablage, die nie scheitert —
    der Test prüfte dann gar nichts.
    """

    def __init__(self, echt, fehler: int = 1) -> None:
        self._echt = echt
        self.fehler = fehler
        self.versuche = 0

    def __getattr__(self, name):
        return getattr(self._echt, name)

    def loeschen(self, schluessel: str) -> bool:
        self.versuche += 1
        if self.versuche <= self.fehler:
            from diakronos_app.speicher import AblageFehler

            raise AblageFehler("Netz weg (Attrappe)")
        return self._echt.loeschen(schluessel)

    def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
        """Dieselbe Attrappe für den Weg mit Zeitlimit (der Request-Weg)."""
        return self.loeschen(schluessel)


def test_loeschen_stellt_entsorgungsauftrag_und_job_loescht_datei(gespraech, ablage):
    """Nachricht löschen → Auftrag steht, Datei weg, Auftrag weg.

    CHAT-12a-2: Der Auftrag entsteht in der Transaktion des Löschens; danach
    versucht der REQUEST genau diesen eigenen Schlüssel einmal (die Ablage ist
    hier gesund, also klappt es). Ein fremder Auftrag darf dabeibleiben — der
    Request fasst ihn nie an.
    """
    from diakronos_app.api import chat as C

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    schluessel = _schluessel_von(hoch)
    antwort = _senden(g, "mit Bild", ANNA, anhaenge=[hoch])
    assert schluessel in _objekte(ablage)

    _set(ANNA)
    C.loeschen(antwort["name"])
    # Der eigene Auftrag ist erledigt (der Request hat ihn nach dem Commit
    # einmal versucht) …
    assert _entsorgung(ablage) == []
    # … und die Datei ist wirklich weg.
    assert schluessel not in _objekte(ablage)


def test_gescheitertes_loeschen_bleibt_als_auftrag_und_zweiter_lauf_raeumt(gespraech, ablage):
    """Speicher-Attrappe wirft beim Loeschen -> der Job raeumt ab.

    Genau der Kartenfall (R1/3): die Datei darf NICHT verwaist zurueckbleiben.
    CHAT-12a-2: nach dem Commit versucht der REQUEST nur seine eigenen
    Schluessel einmal (kein Fehlerzaehler - das ist Sache des Jobs). Der
    Auftrag bleibt trotzdem faellig, der erste JOB-Lauf scheitert (``versuche``
    = 1, Backoff steht), der zweite Lauf loescht die Datei und die Zeile.
    """
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    schluessel = _schluessel_von(hoch)
    antwort = _senden(g, "mit Bild", ANNA, anhaenge=[hoch])
    assert _entsorgung(ablage) == [], "vor dem Test darf nichts offen sein"

    # ZWEI Fehlschläge: der erste gehört dem Request (Sofort-Versuch), der
    # zweite dem ersten Job-Lauf — erst der dritte Versuch (zweiter Job-Lauf)
    # kommt durch.
    kaputt = _FehlerndeAblage(ablage, fehler=2)
    setze_speicher(kaputt)
    try:
        _set(ANNA)
        C.loeschen(antwort["name"])       # Auftrag entsteht; Sofort-Versuch scheitert

        assert _entsorgung(ablage) == [schluessel], "Auftrag muss stehen bleiben"
        with dbmod.SessionLocal() as s:
            zeile = s.get(ChatAnhangEntsorgung, schluessel)
            assert zeile is not None
            # Der Request zaehlt KEINEN Fehlversuch (das ist Sache des Jobs) ...
            assert int(zeile.versuche) == 0, zeile.versuche
            # ... stellt den Auftrag aber wieder faellig (jetzt >= vorgemerkt).
            # Massstab ist die Wanduhr der Gemeinde (``_jetzt``), nicht UTC.
            assert zeile.naechster_versuch_am <= C._jetzt()
        assert schluessel in _objekte(ablage), "die Datei liegt noch da"

        erster = C.chat_anhang_entsorgung_abarbeiten()
        assert erster["abgearbeitet"] == 0, erster
        assert erster["fehler"] == 1, erster
        with dbmod.SessionLocal() as s:
            zeile = s.get(ChatAnhangEntsorgung, schluessel)
            assert zeile is not None
            assert int(zeile.versuche) == 1, zeile.versuche
            assert zeile.letzter_fehler, "der Grund muss dranstehen"
            # Backoff: nach dem ersten Fehlschlag 1 Minute.
            assert zeile.naechster_versuch_am >= C._jetzt() + timedelta(seconds=55)
        assert _entsorgung(ablage) == [schluessel]

        zweiter = C.chat_anhang_entsorgung_abarbeiten(
            jetzt=C._jetzt() + timedelta(minutes=2))
        assert zweiter["abgearbeitet"] == 1, zweiter
        assert zweiter["fehler"] == 0, zweiter
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    assert _entsorgung(ablage) == []
    assert schluessel not in _objekte(ablage)


def test_jeder_loeschweg_stellt_einen_auftrag(gespraech, ablage):
    """Vier Wege, ein Ergebnis: der Schlüssel steht in der Entsorgungsliste.

    Geprüft werden die Wege, die die Karte nennt: ``loeschen`` (selbst),
    ``meldung_entscheiden`` (Moderation), Fristen-Job
    (``chat_aufbewahrung``) und Aufräumen offener Anhänge. Die Ablage ist hier
    ABSICHTLICH kaputt (kein Löschen möglich): nur so sieht man, dass der
    Auftrag von JEDEM Weg entsteht und nicht nur vom glücklichen Sofort-Lauf.
    """
    from diakronos_app import chat_aufbewahrung as A
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    g = gespraech
    kaputt = _FehlerndeAblage(ablage, fehler=10_000)
    setze_speicher(kaputt)
    try:
        # 1) selbst löschen
        h1 = _hochladen(g, ANNA)["name"]
        s1 = _schluessel_von(h1)
        n1 = _senden(g, "eins", ANNA, anhaenge=[h1])
        _set(ANNA)
        C.loeschen(n1["name"])
        assert s1 in _entsorgung(ablage)

        # 2) Aufräumen offener Anhänge (hochgeladen, nie gesendet, 25 h alt)
        h2 = _hochladen(g, ANNA)["name"]
        s2 = _schluessel_von(h2)
        with dbmod.SessionLocal.begin() as s:
            s.get(ChatAnhang, h2).angelegt_am = (
                s.get(ChatAnhang, h2).angelegt_am - timedelta(hours=25))
        C.chat_anhaenge_aufraeumen()
        assert s2 in _entsorgung(ablage)

        # 3) Fristen-Job: Gespräch auflösen (Frist 1 Monat, Nachrichten alt)
        with dbmod.SessionLocal.begin() as s:
            A.setze_einstellungen(s, gruppe_monate=1, direkt_monate=1)
        # Alles auf „vor zwei Monaten“ schieben — die Frist greift dann.
        with dbmod.SessionLocal.begin() as s:
            from diakronos_app.models.chat import ChatGespraech
            for zeile in s.query(ChatNachricht).all():
                zeile.erstellt_am = zeile.erstellt_am - timedelta(days=70)
            for zeile in s.query(ChatGespraech).all():
                zeile.angelegt_am = zeile.angelegt_am - timedelta(days=70)
        A.aufraeumen()
        with dbmod.SessionLocal() as s:
            assert s.query(ChatAnhang).count() == 0
        assert s1 in _entsorgung(ablage) or s1 not in _objekte(ablage)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)


def test_moderation_stellt_einen_auftrag(gespraech, ablage):
    """``meldung_entscheiden`` mit „entfernen“ → Auftrag steht."""
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    schluessel = _schluessel_von(hoch)
    nachricht = _senden(g, "gemeldet", ANNA, anhaenge=[hoch])

    _set(BERT)
    meldung = C.meldung_senden(nachricht["name"], "sonstiges")

    kaputt = _FehlerndeAblage(ablage, fehler=10_000)
    setze_speicher(kaputt)
    try:
        _set(HV)
        C.meldung_entscheiden(meldung["name"], "entfernen", grund="geprüft")
        assert schluessel in _entsorgung(ablage)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)


def test_entsorgung_nicht_vorhanden_ist_erfolg(ablage, patched_db):
    """R1/3: „nicht vorhanden“ zählt als Erfolg — Zeile fällt, kein Fehler."""
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C

    with dbmod.SessionLocal.begin() as s:
        jetzt = datetime.utcnow()
        s.add(ChatAnhangEntsorgung(schluessel="chat-a-gibtsnicht",
                                   vorgemerkt_am=jetzt,
                                   naechster_versuch_am=jetzt,
                                   versuche=0, letzter_fehler=None))
    ergebnis = C.chat_anhang_entsorgung_abarbeiten()
    assert ergebnis["abgearbeitet"] == 1, ergebnis
    assert ergebnis["fehler"] == 0, ergebnis
    # ``offen`` ist der Stand NACH dem Lauf: hier 0.
    assert ergebnis["offen"] == 0, ergebnis
    assert _entsorgung(ablage) == []


# ── Review R1/4: Hochlade-Marken ───────────────────────────────────────────


def test_aufraeumen_entfernt_alte_marken(gespraech, ablage):
    """Marken älter als zwei Tage fallen; die von heute bleiben."""
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C

    g = gespraech
    _hochladen(g, ANNA)
    with dbmod.SessionLocal.begin() as s:
        for zeile in s.query(ChatAnhangHochladung).all():
            zeile.angelegt_am = zeile.angelegt_am - timedelta(days=3)
    ergebnis = C.chat_anhaenge_aufraeumen()
    assert ergebnis["marken"] == 1, ergebnis
    with dbmod.SessionLocal() as s:
        assert s.query(ChatAnhangHochladung).count() == 0


def test_marke_gehoert_zum_konto_und_faellt_mit_ihm(gespraech, ablage):
    """Die Marke trägt das Konto — DSGVO: sie fällt mit der Person."""
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C

    g = gespraech
    _hochladen(g, ANNA)
    _hochladen(g, BERT)
    with dbmod.SessionLocal() as s:
        konten = {z.konto for z in s.query(ChatAnhangHochladung).all()}
    assert konten == {ANNA, BERT}, konten


# ── Review R1/1: der DSGVO-Matcher bleibt schmal ───────────────────────────
#
# Die Auflage: der generische ``*_von``-Matcher in ``_zeilen_loeschen`` traf
# auch ``rechte_gruppenrolle.erteilt_von`` und ``rechte_freigabe.erteilt_von``
# — also Rollen und Freigaben, die die Person ANDEREN erteilt hat. Ist das
# Konto der Person schon gelöscht (Schritt 6 nullt dann nichts) und erweitert
# Schritt 6d ``b.konten`` danach um die Mitglieds-Mail, löschte Schritt 7
# diese fremden Zeilen mit. Der generische Matcher gilt deshalb wieder nur für
# ``user``/``nutzer``/``benutzer``; ``chat_anhang`` ist ein ausdrücklicher
# Sonderfall über ``angelegt_von``.


def test_dsgvo_loescht_keine_fremden_rollen_und_freigaben(patched_db):
    """Person ohne ``user``-Zeile, die ANDEREN Rolle + Freigabe erteilt hat.

    Beides muss nach der Anonymisierung NOCH EXISTIEREN — ``erteilt_von`` darf
    genullt sein oder stehen, aber die ZEILE bleibt (sie gehört einer anderen
    Person). Vor der Korrektur löschte der ``*_von``-Matcher sie mit.
    """
    from diakronos_app import dsgvo_anonymisierung as A
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.rechte import RechteFreigabe, RechteGruppenrolle

    s = patched_db()
    # Die Person: Mitglied mit Adresse, aber OHNE ``user``-Zeile (Konto schon
    # weg — genau der Fall aus dem Review).
    s.add(Mitglied(name="M-weg", vorname="Elvira", nachname="Dorn",
                   email="elvira@x.org"))
    # Der ANDERE, der die Rolle/Freigabe bekommt.
    s.add(User(name="andere@x.org", email="andere@x.org", enabled=1, full_name="Andere"))
    s.add(Mitglied(name="M-andere", vorname="Andere", nachname="X",
                   email="andere@x.org", user="andere@x.org"))
    # Beides von der gehenden Person ERTEILT.
    s.add(RechteGruppenrolle(gruppe="Chor", benutzer="andere@x.org",
                             rolle="HV", erteilt_von="elvira@x.org"))
    s.add(RechteFreigabe(typ="gruppe", objekt="Chor", benutzer="andere@x.org",
                         lesen=True, erteilt_von="elvira@x.org"))
    s.commit()

    A.anonymisiere(s, "M-weg", ["elvira@x.org"])

    zeilen = s.query(RechteGruppenrolle).all()
    assert len(zeilen) == 1, f"die fremde Rolle wurde gelöscht ({len(zeilen)} Zeilen)"
    assert zeilen[0].benutzer == "andere@x.org"
    assert zeilen[0].erteilt_von in (None, "elvira@x.org"), zeilen[0].erteilt_von

    freigaben = s.query(RechteFreigabe).all()
    assert len(freigaben) == 1, f"die fremde Freigabe wurde gelöscht ({len(freigaben)} Zeilen)"
    assert freigaben[0].benutzer == "andere@x.org"
    assert freigaben[0].erteilt_von in (None, "elvira@x.org"), freigaben[0].erteilt_von


def test_chat_anhang_ist_ein_ausdruecklicher_sonderfall():
    """R1/1: ``chat_anhang`` steht in der Sonderfall-Tabelle, nicht im Matcher.

    Der Test hält die ENTSCHEIDUNG fest (nicht nur das Verhalten): der
    generische Matcher kennt nur ``user``/``nutzer``/``benutzer``, und die
    Konto-Spalte von ``chat_anhang`` ist dort ausdrücklich genannt.
    """
    import inspect

    from diakronos_app import dsgvo_anonymisierung as A

    assert A.KONTO_SPALTEN_JE_TABELLE.get("chat_anhang") == ("angelegt_von",)
    quelle = inspect.getsource(A._zeilen_loeschen)
    # KEIN ``endswith("_von")`` mehr im CODE (der Kommentar nennt den Befund
    # ausdrücklich) — genau das war die Ursache.
    code = "\n".join(z for z in quelle.splitlines()
                     if not z.strip().startswith("#"))
    assert 'endswith("_von")' not in code, code
    assert "KONTO_SPALTEN_JE_TABELLE" in code


# ── Review R1/2: Reihenfolge auf PostgreSQL ────────────────────────────────
#
# Auf PostgreSQL setzt der FK ``chat_anhang.angelegt_von`` beim Löschen der
# ``user``-Zeile NULL. Fiele die ``user``-Zeile VOR dem Löschen der
# Anhang-Zeilen, stünde ``angelegt_von`` schon NULL und Schritt 7 fände sie
# nicht mehr — ``dateiname``/``mime``/``groesse`` blieben stehen. Der Test
# schaltet die Fremdschlüssel auf SQLite EIN (``PRAGMA foreign_keys=ON``) und
# geht genau diesen Pfad.


def test_dsgvo_anhaenge_fallen_vor_der_user_zeile_fk_aktiv(ablage):
    """Mit aktiven Fremdschlüsseln: Zeile UND Auftrag, kein Rest mit Dateinamen."""
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from diakronos_app import db as dbmod
    from diakronos_app import dsgvo_anonymisierung as A
    from diakronos_app.models.base import Base
    from diakronos_app.models.chat import ChatGespraech
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppe, Mitglied

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _fk_an(dbapi_verbindung, _record):  # noqa: ANN001 — SQLAlchemy-Signatur
        dbapi_verbindung.execute("PRAGMA foreign_keys=ON")

    import diakronos_app.models  # noqa: F401 — Modelle registrieren

    Base.metadata.create_all(eng)
    fabrik = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)

    vorher_engine, vorher_fabrik = dbmod.engine, dbmod.SessionLocal
    dbmod.engine, dbmod.SessionLocal = eng, fabrik
    for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                    "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
        mod = __import__(modname, fromlist=["_"])
        if hasattr(mod, "SessionLocal"):
            mod.SessionLocal = fabrik
    try:
        with fabrik.begin() as s:
            s.add(User(name="anna@x.org", email="anna@x.org", enabled=1, full_name="Anna"))
            s.add(Mitglied(name="M-Anna", vorname="Anna", nachname="X",
                           email="anna@x.org", user="anna@x.org"))
            s.flush()  # ohne Ordnung kennt SQLite die FK-Ziele noch nicht
            s.add(Gruppe(name="Chor", gruppenname="Chor"))
            s.flush()
            s.add(ChatGespraech(name="g-fk", art="gruppe", gruppe="Chor",
                                titel="Chor", angelegt_am=datetime.utcnow()))
            s.flush()
            # Der echte Upload legt die Datei ab — hier von Hand, damit der
            # Test nur die DSGVO-Reihenfolge prüft.
            ablage.schreiben("chat-a-fk1", PNG)
            s.add(ChatAnhang(name="a-fk1", nachricht=None, gespraech="g-fk",
                             schluessel="chat-a-fk1", dateiname="Ausweis Elvira Dorn.png",
                             mime="image/png", groesse=len(PNG),
                             angelegt_am=datetime.utcnow(), angelegt_von="anna@x.org"))
        # Fremdschlüssel sind WIRKLICH aktiv (sonst prüft der Test nichts).
        with fabrik() as s:
            assert s.execute(text("PRAGMA foreign_keys")).scalar() in (1, True)

        with fabrik.begin() as s:
            A.anonymisiere(s, "M-Anna", ["anna@x.org"])

        with fabrik() as s:
            assert s.query(ChatAnhang).count() == 0, "die Anhang-Zeile blieb stehen"
            offen = [z.schluessel for z in s.query(ChatAnhangEntsorgung).all()]
        assert offen == ["chat-a-fk1"], offen
        # Kein Rest mit einem Namen: die Zeile ist ganz weg (nicht: null).
        with fabrik() as s:
            assert s.execute(text(
                "SELECT count(*) FROM chat_anhang WHERE dateiname IS NOT NULL"
            )).scalar_one() == 0
    finally:
        dbmod.engine, dbmod.SessionLocal = vorher_engine, vorher_fabrik
        for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                        "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
            mod = __import__(modname, fromlist=["_"])
            if hasattr(mod, "SessionLocal"):
                mod.SessionLocal = vorher_fabrik
        eng.dispose()


def test_modell_und_migration_stimmen_beim_foreign_key():
    """R1/2: ``angelegt_von`` trägt in Modell UND Migration ``SET NULL``."""
    import importlib.util

    from diakronos_app.models.chat import ChatAnhang

    spalte = ChatAnhang.__table__.c.angelegt_von
    ziele = list(spalte.foreign_keys)
    assert ziele, "kein Fremdschlüssel am Modell"
    assert (ziele[0].ondelete or "").upper() == "SET NULL", ziele[0].ondelete

    pfad = BACKEND / "alembic" / "versions" / "chat12a_anhang.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("chat12a_anhang_fk", pfad))
    modul.__spec__.loader.exec_module(modul)
    quelle = Path(modul.__file__).read_text(encoding="utf-8")
    assert 'ondelete="SET NULL"' in quelle


# ── CHAT-12a-2, Punkt 1: keine Kopfblockade ─────────────────────────────────
#
# Vorher nahm jeder Lauf die 100 ÄLTESTEN Aufträge. Scheiterten 100 Schlüssel
# dauerhaft (403, kaputter Pfad), waren sie in JEDEM Lauf wieder die Auswahl —
# neuere Aufträge kamen nie dran (per Probe belegt). Jetzt wählt der Job nach
# ``naechster_versuch_am <= jetzt`` und schiebt gescheiterte Aufträge mit
# Backoff nach hinten. Gelöscht wird NIE still: es geht um DSGVO-Dateien.


def _auftrag(schluessel: str, *, versuche: int = 0,
             vorgemerkt: datetime | None = None,
             faellig: datetime | None = None) -> None:
    """Einen Entsorgungs-Auftrag von Hand anlegen (Tests steuern die Zeiten)."""
    from diakronos_app import db as dbmod

    zeit = vorgemerkt or datetime.utcnow()
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatAnhangEntsorgung(
            schluessel=schluessel, vorgemerkt_am=zeit, versuche=versuche,
            naechster_versuch_am=faellig or zeit, letzter_fehler=None,
        ))


def _auftrag_stand(schluessel: str):
    """``(versuche, naechster_versuch_am, letzter_fehler)`` einer Zeile."""
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatAnhangEntsorgung, schluessel)
        assert zeile is not None, schluessel
        return (int(zeile.versuche), zeile.naechster_versuch_am,
                zeile.letzter_fehler)


class _ImmerKaputteAblage:
    """Jede Ablage-Operation scheitert (403/kaputter Pfad als Attrappe)."""

    name = "kaputt"

    def schliessen(self) -> None:
        """``hole_speicher`` schliesst die alte Umsetzung beim Wechsel."""

    def loeschen(self, schluessel: str) -> bool:
        from diakronos_app.speicher import AblageFehler

        raise AblageFehler("403 verboten (Attrappe)")

    def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
        return self.loeschen(schluessel)


def test_100_dauerhaft_scheiternde_auftraege_blockieren_den_guten_nicht(
        gespraech, ablage):
    """100 kaputte Schlüssel + 1 guter: der gute ist nach EINEM Lauf weg.

    Genau der Kartenfall. Die 100 stehen mit ``vorgemerkt_am`` VOR dem guten
    Auftrag (so wie früher die Auswahl sortiert war) — nach der alten Logik
    wäre der gute nie drangekommen.
    """
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    jetzt = datetime.utcnow()
    alt = jetzt - timedelta(hours=5)
    for i in range(100):
        _auftrag(f"chat-a-kaputt-{i:03d}", vorgemerkt=alt, faellig=alt)
    # Der gute Auftrag: eine Datei, die WIRKLICH in der Ablage liegt.
    gut = "chat-a-guter"
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatAnhangEntsorgung(schluessel=gut, vorgemerkt_am=jetzt,
                                   naechster_versuch_am=jetzt, versuche=0,
                                   letzter_fehler=None))
    ablage.schreiben(gut, b"inhalt")

    setze_speicher(_ImmerKaputteAblage())
    try:
        # Erster Lauf: Grenze 100 — die kaputten belegen den ganzen Batch.
        erst = C.chat_anhang_entsorgung_abarbeiten()
        assert erst["fehler"] == 100, erst
        assert erst["abgearbeitet"] == 0, erst
        assert gut in _objekte(ablage), "der gute Auftrag darf hier noch liegen"
        # Die kaputten sind jetzt 1 Minute nach hinten gerückt …
        assert _auftrag_stand("chat-a-kaputt-000")[1] >= jetzt + timedelta(seconds=50)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    # … deshalb nimmt der nächste Lauf (2 Minuten später) den GUTEN Auftrag.
    zweiter = C.chat_anhang_entsorgung_abarbeiten(
        jetzt=datetime.utcnow() + timedelta(minutes=2))
    assert zweiter["abgearbeitet"] == 1, zweiter
    assert zweiter["fehler"] == 0, zweiter
    assert gut not in _objekte(ablage), "der gute Auftrag muss weg sein"
    with dbmod.SessionLocal() as s:
        assert s.get(ChatAnhangEntsorgung, gut) is None
        # Die 100 bleiben stehen (DSGVO): nichts wird still gelöscht.
        assert s.query(ChatAnhangEntsorgung).count() == 100


def test_backoff_zeiten_1_5_30_minuten_danach_6_stunden():
    """Der Backoff folgt der Kartenreihe und bleibt ab dem vierten Mal stehen."""
    from diakronos_app.api import chat as C

    assert C.ENTSORGUNG_BACKOFF_MINUTEN == (1, 5, 30, 360)
    assert C.entsorgung_wartezeit(1) == timedelta(minutes=1)
    assert C.entsorgung_wartezeit(2) == timedelta(minutes=5)
    assert C.entsorgung_wartezeit(3) == timedelta(minutes=30)
    assert C.entsorgung_wartezeit(4) == timedelta(hours=6)
    # Danach bleibt es bei 6 Stunden — nicht weiter wachsen.
    assert C.entsorgung_wartezeit(19) == timedelta(hours=6)
    assert C.entsorgung_wartezeit(20) == timedelta(hours=6)
    assert C.entsorgung_wartezeit(500) == timedelta(hours=6)


def test_backoff_wird_beim_fehlschlag_wirklich_so_gesetzt(gespraech, ablage):
    """Vier Fehlschläge nacheinander: 1, 5, 30 Minuten, dann 6 Stunden.

    Geprüft am echten Job (nicht nur an ``entsorgung_wartezeit``): jede Runde
    wartet genau die Zeit ab, die am Auftrag steht, und der Zeitpunkt rückt
    entsprechend.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    schluessel = "chat-a-ein-fehler"
    _auftrag(schluessel)
    jetzt = datetime.utcnow()
    setze_speicher(_ImmerKaputteAblage())
    try:
        for nummer, erwartet in ((1, timedelta(minutes=1)),
                                 (2, timedelta(minutes=5)),
                                 (3, timedelta(minutes=30)),
                                 (4, timedelta(hours=6)),
                                 (5, timedelta(hours=6))):
            lauf = C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
            assert lauf["fehler"] == 1, lauf
            versuche, faellig, _fehler = _auftrag_stand(schluessel)
            assert versuche == nummer, (versuche, nummer)
            assert faellig == jetzt + erwartet, (faellig, jetzt + erwartet)
            # Der Auftrag ist bis dahin NICHT fällig.
            assert C.chat_anhang_entsorgung_abarbeiten(
                jetzt=jetzt + erwartet - timedelta(seconds=1))["fehler"] == 0
            jetzt = jetzt + erwartet
    finally:
        vergiss_speicher()
        setze_speicher(ablage)


def test_logger_error_ab_20_versuchen_und_auftrag_bleibt(gespraech, ablage, caplog):
    """Ab 20 Versuchen EIN ``logger.error`` — der Auftrag bleibt bestehen."""
    import logging

    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    schluessel = "chat-a-dauerfehler"
    _auftrag(schluessel, versuche=C.ENTSORGUNG_WARNUNG_AB - 1)
    jetzt = datetime.utcnow()
    setze_speicher(_ImmerKaputteAblage())
    try:
        caplog.set_level(logging.INFO, logger="diakronos_app.api.chat")
        lauf = C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
        assert lauf["fehler"] == 1, lauf
        assert lauf["offen"] == 1, lauf
        fehler = [r for r in caplog.records
                  if r.levelno >= logging.ERROR and r.name == "diakronos_app.api.chat"]
        assert len(fehler) == 1, [r.getMessage() for r in caplog.records]
        assert schluessel in fehler[0].getMessage()
        assert str(C.ENTSORGUNG_WARNUNG_AB) in fehler[0].getMessage()

        # Unterhalb der Schwelle gibt es KEIN ``logger.error``.
        caplog.clear()
        _auftrag("chat-a-noch-leise", versuche=3)
        C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    # Nie still gelöscht: der Auftrag steht weiter und wird alle 6 h versucht.
    versuche, faellig, fehler_text = _auftrag_stand(schluessel)
    assert versuche == C.ENTSORGUNG_WARNUNG_AB
    assert faellig == jetzt + timedelta(hours=6)
    assert fehler_text


def test_auftrag_ist_nach_20_versuchen_weiter_alle_6_stunden_dran(gespraech, ablage):
    """Ein „hoffnungsloser“ Auftrag wird nicht aufgegeben, nur seltener."""
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    schluessel = "chat-a-hoffentlich"
    _auftrag(schluessel, versuche=30)
    jetzt = datetime.utcnow()
    setze_speicher(_ImmerKaputteAblage())
    try:
        assert C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)["fehler"] == 1
        versuche, faellig, _ = _auftrag_stand(schluessel)
        assert versuche == 31
        assert faellig == jetzt + timedelta(hours=6)
        # Am nächsten 6-Stunden-Takt ist er wieder dran.
        assert C.chat_anhang_entsorgung_abarbeiten(
            jetzt=jetzt + timedelta(hours=6))["fehler"] == 1
    finally:
        vergiss_speicher()
        setze_speicher(ablage)


def test_nicht_faellige_auftraege_werden_nicht_angefasst(gespraech, ablage):
    """``naechster_versuch_am`` in der Zukunft: der Lauf lässt ihn in Ruhe."""
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    jetzt = datetime.utcnow()
    _auftrag("chat-a-spaeter", faellig=jetzt + timedelta(minutes=30))
    ablage.schreiben("chat-a-spaeter", b"x")
    setze_speicher(_ImmerKaputteAblage())
    try:
        lauf = C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
        assert lauf == {"abgearbeitet": 0, "fehler": 0, "offen": 1}, lauf
    finally:
        vergiss_speicher()
        setze_speicher(ablage)
    assert "chat-a-spaeter" in _objekte(ablage), "die Datei wurde angefasst"


def test_migration_legt_die_spalte_an_und_nimmt_sie_zurueck():
    """``chat12a2_backoff``: up → Spalte+Index da, down → wieder weg (idempotent).

    Geprueft an einer eigenen SQLite-Engine mit der VORIGEN Tabellenform: die
    Migration muss bestehende Zeilen aus ``vorgemerkt_am`` fuellen (die Spalte
    ist ``NOT NULL``) und den Fehlerzaehler unberuehrt lassen.
    """
    import importlib.util

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool, future=True)
    with eng.begin() as v:
        v.exec_driver_sql(
            'CREATE TABLE "chat_anhang_entsorgung" ('
            '"schluessel" VARCHAR(255) NOT NULL PRIMARY KEY, '
            '"vorgemerkt_am" DATETIME NOT NULL, '
            '"versuche" INTEGER NOT NULL, '
            '"letzter_fehler" VARCHAR(200))')
        v.exec_driver_sql(
            "INSERT INTO chat_anhang_entsorgung "
            "(schluessel, vorgemerkt_am, versuche) "
            "VALUES ('chat-a-alt', '2026-01-02 03:04:05', 7)")
        v.exec_driver_sql(
            'CREATE INDEX "ix_chat_anhang_entsorgung_am" '
            'ON "chat_anhang_entsorgung" ("vorgemerkt_am")')

    pfad = BACKEND / "alembic" / "versions" / "chat12a2_backoff.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("chat12a2_backoff", pfad))
    modul.__spec__.loader.exec_module(modul)

    def _spalten(verbindung):
        return {c["name"] for c in sa.inspect(verbindung).get_columns(
            "chat_anhang_entsorgung")}

    def _indizes(verbindung):
        return {i["name"] for i in sa.inspect(verbindung).get_indexes(
            "chat_anhang_entsorgung")}

    try:
        with eng.begin() as v:
            with Operations.context(MigrationContext.configure(v)):
                modul.upgrade()
                modul.upgrade()  # idempotent
            assert "naechster_versuch_am" in _spalten(v), v
            assert "ix_chat_anhang_entsorgung_naechster" in _indizes(v)
            wert = v.exec_driver_sql(
                "SELECT naechster_versuch_am, versuche FROM chat_anhang_entsorgung "
                "WHERE schluessel = 'chat-a-alt'").one()
            # Bestehende Zeilen sind gefuellt und behalten ihren Fehlerzaehler.
            assert str(wert[0]).startswith("2026-01-02 03:04:05"), wert
            assert int(wert[1]) == 7
            spalte = [c for c in sa.inspect(v).get_columns("chat_anhang_entsorgung")
                      if c["name"] == "naechster_versuch_am"][0]
            assert spalte["nullable"] is False, spalte

        with eng.begin() as v:
            with Operations.context(MigrationContext.configure(v)):
                modul.downgrade()
                modul.downgrade()  # idempotent
            assert "naechster_versuch_am" not in _spalten(v)
            assert "ix_chat_anhang_entsorgung_naechster" not in _indizes(v)
    finally:
        eng.dispose()


# ── CHAT-12a-2, Punkt 3: Hochlade-Marken ohne FK-Kaskade ────────────────────
#
# Bisher entfernte nur die FK-Kaskade (`chat_anhang_hochladung.konto` →
# `user.name`, ON DELETE CASCADE) die Marken der Person. Ohne
# ``PRAGMA foreign_keys`` (SQLite, Einzelplatz, Tests) griff die Kaskade NICHT —
# die Hochlade-Marken blieben nach einer Anonymisierung stehen. Der Eintrag in
# ``KONTO_SPALTEN_JE_TABELLE`` macht das Löschen unabhängig von der Kaskade.


def test_hochladung_ist_ein_ausdruecklicher_konto_sonderfall():
    """Die Konto-Spalte heißt ``konto`` — der schmale Matcher kennt sie nicht."""
    from diakronos_app import dsgvo_anonymisierung as A
    from diakronos_app.models.chat import ChatAnhangHochladung

    assert A.KONTO_SPALTEN_JE_TABELLE.get("chat_anhang_hochladung") == ("konto",)
    spalten = {c.name for c in ChatAnhangHochladung.__table__.columns}
    assert "konto" in spalten
    # KEINE generische Konto-Spalte: der Sonderfall ist nötig.
    assert not (spalten & {"user", "nutzer", "benutzer"})
    # Die Zeile fällt auch über den generischen Weg (KONTO_ZEILEN).
    assert "chat_anhang_hochladung" in A.KONTO_ZEILEN


def test_dsgvo_entfernt_die_hochlade_marken_auch_ohne_foreign_keys():
    """Ohne ``PRAGMA foreign_keys``: nach der Anonymisierung keine Marke mehr.

    Die Kaskade kann hier NICHT helfen (SQLite prüft FKs standardmäßig nicht) —
    genau der Fall, den der Kartenpunkt beschreibt. Geprüft wird mit der ECHTEN
    Anonymisierung auf einer eigenen Engine mit der VORIGEN Tabellenform.
    """
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from diakronos_app import db as dbmod
    from diakronos_app import dsgvo_anonymisierung as A
    from diakronos_app.models.base import Base
    from diakronos_app.models.chat import ChatAnhangHochladung
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool, future=True)
    import diakronos_app.models  # noqa: F401 — Modelle registrieren

    Base.metadata.create_all(eng)
    fabrik = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)

    vorher_engine, vorher_fabrik = dbmod.engine, dbmod.SessionLocal
    dbmod.engine, dbmod.SessionLocal = eng, fabrik
    for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                    "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
        mod = __import__(modname, fromlist=["_"])
        if hasattr(mod, "SessionLocal"):
            mod.SessionLocal = fabrik
    try:
        # Fremdschlüssel sind AUS — die Kaskade kann nicht greifen.
        with fabrik() as s:
            assert s.execute(text("PRAGMA foreign_keys")).scalar() in (0, False)

        with fabrik.begin() as s:
            s.add(User(name="anna@x.org", email="anna@x.org", enabled=1,
                       full_name="Anna"))
            s.add(Mitglied(name="M-Anna", vorname="Anna", nachname="X",
                           email="anna@x.org", user="anna@x.org"))
            s.flush()
            zeit = datetime.utcnow()
            s.add(ChatAnhangHochladung(name="chat-h-1", konto="anna@x.org",
                                       angelegt_am=zeit))
            s.add(ChatAnhangHochladung(name="chat-h-2", konto="anna@x.org",
                                       angelegt_am=zeit))
            s.add(ChatAnhangHochladung(name="chat-h-3", konto="bert@x.org",
                                       angelegt_am=zeit))
        with fabrik() as s:
            assert s.query(ChatAnhangHochladung).count() == 3

        with fabrik.begin() as s:
            A.anonymisiere(s, "M-Anna", ["anna@x.org"])

        with fabrik() as s:
            konten = [z.konto for z in s.query(ChatAnhangHochladung).all()]
        assert "anna@x.org" not in konten, konten
        # Die Marken der ANDEREN Person bleiben (nur die eigene Person geht).
        assert konten == ["bert@x.org"], konten
        # Die Tabelle existiert weiter — es wurde nichts „weggeräumt“.
        assert inspect(eng).has_table("chat_anhang_hochladung")
    finally:
        dbmod.engine, dbmod.SessionLocal = vorher_engine, vorher_fabrik
        for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
                        "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
            mod = __import__(modname, fromlist=["_"])
            if hasattr(mod, "SessionLocal"):
                mod.SessionLocal = vorher_fabrik
        eng.dispose()


def test_docstrings_sagen_hochlade_versuch_nicht_erfolgreicher_upload():
    """Modell UND Migration: gezählt wird je VERSUCH (bewusst, gegen Umgehung)."""
    from diakronos_app.models.chat import ChatAnhangHochladung

    modell = (ChatAnhangHochladung.__doc__ or "").lower()
    assert "hochlade-versuch" in modell, modell
    assert "fehlversuche" in modell, modell
    # Die alte (falsche) Beschreibung ist weg.
    assert "ein erfolgreicher upload (review r1/4)" not in modell, modell
    assert "je erfolgreichem upload:" not in modell, modell

    quelle = (BACKEND / "alembic" / "versions" / "chat12a_entsorgung.py").read_text(
        encoding="utf-8").lower()
    assert "hochlade-versuch" in quelle
    assert "eine zeile je erfolgreichem" not in quelle
    # Und die Begründung steht da (Fehlversuche sollen nichts umgehen).
    assert "fehlversuche" in quelle


# ── CHAT-12a-2, Punkt 2: der Request arbeitet nur SEINE Schlüssel ab ────────


def test_speicher_wirft_beim_loeschen_und_der_endpunkt_antwortet_erfolgreich(
        gespraech, ablage):
    """Speicher-Attrappe wirft → ``loeschen`` antwortet trotzdem, Auftrag bleibt."""
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    schluessel = _schluessel_von(hoch)
    nachricht = _senden(g, "mit Bild", ANNA, anhaenge=[hoch])

    kaputt = _FehlerndeAblage(ablage, fehler=10_000)
    setze_speicher(kaputt)
    try:
        _set(ANNA)
        antwort = C.loeschen(nachricht["name"])   # KEINE Ausnahme nach außen
        assert antwort["geloescht"] is True, antwort
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    # Der Auftrag steht weiter und ist für den Minuten-Job fällig.
    assert _entsorgung(ablage) == [schluessel]
    assert schluessel in _objekte(ablage), "die Datei liegt noch da"
    versuche, faellig, _ = _auftrag_stand(schluessel)
    assert versuche == 0, "der Request zählt keinen Fehlversuch"
    assert faellig <= C._jetzt()


def test_ablage_nicht_verfuegbar_ist_kein_fehler(gespraech, ablage, monkeypatch):
    """Auch ``hole_speicher()`` steht in ``try``/``except`` — der Request lebt."""
    from diakronos_app import speicher as spmod
    from diakronos_app.api import chat as C

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    schluessel = _schluessel_von(hoch)
    nachricht = _senden(g, "mit Bild", ANNA, anhaenge=[hoch])

    def kaputt():
        raise RuntimeError("Ablage lässt sich nicht bauen (Attrappe)")

    monkeypatch.setattr(spmod, "hole_speicher", kaputt)
    _set(ANNA)
    antwort = C.loeschen(nachricht["name"])
    assert antwort["geloescht"] is True
    assert _entsorgung(ablage) == [schluessel]


def test_fremde_alte_auftraege_werden_im_request_nicht_angefasst(gespraech, ablage):
    """Ein offener FREMDER Auftrag bleibt liegen — der Request fasst ihn nie an.

    Die Ablage ist gesund: der fremde Auftrag würde also gelingen, wenn der
    Request ihn (wie früher der Job-Lauf) mit abarbeiten würde. Genau das darf
    nicht passieren.
    """
    from diakronos_app.api import chat as C

    fremd = "chat-a-ganz-alt"
    _auftrag(fremd, vorgemerkt=datetime.utcnow() - timedelta(days=3))
    ablage.schreiben(fremd, b"fremd")

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    eigener = _schluessel_von(hoch)
    nachricht = _senden(g, "mit Bild", ANNA, anhaenge=[hoch])

    _set(ANNA)
    C.loeschen(nachricht["name"])

    # Der EIGENE Auftrag ist erledigt (Datei weg, Zeile weg) …
    assert eigener not in _objekte(ablage)
    # … der FREMDE steht unberührt da: Datei liegt, Auftrag offen.
    assert fremd in _objekte(ablage), "der Request hat einen fremden Auftrag gelöscht"
    assert _entsorgung(ablage) == [fremd]


def test_request_versucht_hoechstens_drei_schluessel(gespraech, ablage):
    """Mehr als ``ANHAENGE_MAX`` (3) Schlüssel bearbeitet der Request nie.

    Der Deckel ist die Zusage der Karte; er hängt nicht an der Nachricht,
    sondern an ``ENTSORGUNG_JE_ANFRAGE``.
    """
    from diakronos_app.api import chat as C

    assert C.ENTSORGUNG_JE_ANFRAGE == 3
    for i in range(5):
        ablage.schreiben(f"chat-a-viel-{i}", b"x")
    geloescht = C._entsorgung_sofort(
        [f"chat-a-viel-{i}" for i in range(5)],
        limit_sekunden=C.ENTSORGUNG_ZEITLIMIT_SEKUNDEN)
    assert geloescht == 3, geloescht
    # Die letzten beiden Dateien sind unberührt (kein Auftrag dazu → bleibt).
    assert "chat-a-viel-3" in _objekte(ablage)
    assert "chat-a-viel-4" in _objekte(ablage)


def test_speicher_zeitlimit_nutzt_die_ablage_wenn_sie_es_kann(gespraech, ablage):
    """Der Request nutzt ``loeschen_mit_zeitlimit`` — und zwar mit dem kurzen Limit.

    ``Lokal`` kennt kein eigenes Limit (es bleibt bei der Vorgabe von
    ``Basis``), deshalb wird hier eine Ablage eingesetzt, die das Limit
    mitschreibt. So ist belegt, dass der Weg wirklich genommen wird (und nicht
    der unbegrenzte ``loeschen``).
    """
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    gesehen: list[tuple[str, float]] = []

    class _MitLimit:
        name = "mitlimit"

        def schliessen(self) -> None:
            pass

        def loeschen(self, schluessel):  # pragma: no cover — darf nicht laufen
            raise AssertionError("ohne Zeitlimit gelöscht")

        def loeschen_mit_zeitlimit(self, schluessel, sekunden):
            gesehen.append((schluessel, sekunden))
            return True

    setze_speicher(_MitLimit())
    try:
        _set(ANNA)
        C._entsorgung_sofort(["chat-a-limit"], limit_sekunden=2.0)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)
    assert gesehen == [("chat-a-limit", 2.0)], gesehen
    assert C.ENTSORGUNG_ZEITLIMIT_SEKUNDEN == 2.0


def test_lokal_und_nextcloud_zeitlimit_schnittstelle():
    """``Lokal`` kennt kein Limit (Vorgabe), ``Nextcloud`` setzt eines (MockTransport)."""
    import httpx

    from diakronos_app.speicher import Lokal
    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    # Lokal: die Vorgabe aus ``Basis`` — kein Netz, kein Limit nötig.
    assert "loeschen_mit_zeitlimit" not in vars(Lokal)

    gesehen: list[float | None] = []

    def _antwort(request: httpx.Request) -> httpx.Response:
        zeitlimit = request.extensions.get("timeout")
        gesehen.append(None if not zeitlimit else max(float(v) for v in zeitlimit.values()))
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(_antwort))
    nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D"),
                   client=client)
    nc.wartezeiten = ()
    assert nc.loeschen_mit_zeitlimit("chat-a-x", 2.0) is True
    # Genau EIN Aufruf (keine Wiederholung) und mit dem kurzen Limit.
    assert len(gesehen) == 1, gesehen
    assert gesehen[0] is not None and gesehen[0] <= 2.0, gesehen
    # Ohne Limit gilt das eingestellte Zeitlimit weiter.
    gesehen.clear()
    assert nc.loeschen("chat-a-y") is True
    assert len(gesehen) == 1


# ── CHAT-12a-2 R1: Nachbesserungen aus dem Operator-Review ───────────────────


class _Transaktionszaehler:
    """Zählt offene Transaktionen/Sitzungen über SQLAlchemy-Ereignisse.

    CHAT-12a-3, Punkt 2: Der alte Test war auf SQLite wertlos. Mit
    ``StaticPool`` teilen sich alle Sitzungen EINE Verbindung, ``SELECT 1``
    bekommt immer sofort eine Antwort, und eine zweite Sitzung sieht sogar
    Uncommittetes — ein Test über ``engine.connect()`` wäre mit dem fehlerhaften
    Code grün geblieben.

    Hier wird stattdessen mitgezählt, was WIRKLICH passiert: jede offene
    Sitzung (``after_begin``/``after_commit``/``after_rollback`` auf der
    ``Session``) und jede offene Verbindungstransaktion (``begin``/``commit``/
    ``rollback`` auf der ``Engine``). Die Ablage-Attrappe fragt den Zähler
    während des Netzaufrufs ab.

    Zusätzlich wird die Ereignisfolge mitschrieben (``ereignisse``) — damit
    lässt sich prüfen, ob zwischen Auswahl und Belegung ein Commit liegt.
    """

    def __init__(self) -> None:
        from sqlalchemy import event as sa_event
        from sqlalchemy.orm import Session

        from diakronos_app import db as dbmod

        self.offen = 0
        self.ereignisse: list[str] = []
        self._sa_event = sa_event
        self._session_cls = Session
        self._engine = dbmod.engine
        self._hoerer: list[tuple[object, str, object]] = []
        self._an(true=True)

    # -- An-/Abmelden ------------------------------------------------------
    def _an(self, *args, true: bool = True) -> None:
        for ziel, name, funktion in (
            (self._session_cls, "after_begin", self._session_begin),
            (self._session_cls, "after_commit", self._session_commit),
            (self._session_cls, "after_rollback", self._session_rollback),
            (self._session_cls, "after_soft_rollback", self._session_soft_rollback),
            (self._engine, "begin", self._conn_begin),
            (self._engine, "commit", self._conn_commit),
            (self._engine, "rollback", self._conn_rollback),
        ):
            self._sa_event.listen(ziel, name, funktion)
            self._hoerer.append((ziel, name, funktion))

    def stoppen(self) -> None:
        for ziel, name, funktion in self._hoerer:
            self._sa_event.remove(ziel, name, funktion)
        self._hoerer.clear()

    # -- Sitzungs-Ebene ----------------------------------------------------
    def _session_begin(self, *args) -> None:
        self.offen += 1
        self.ereignisse.append("begin")

    def _session_commit(self, *args) -> None:
        self.offen -= 1
        self.ereignisse.append("commit")

    def _session_rollback(self, *args) -> None:
        self.offen -= 1
        self.ereignisse.append("rollback")

    def _session_soft_rollback(self, *args) -> None:
        self.ereignisse.append("soft_rollback")

    # -- Verbindungs-Ebene -------------------------------------------------
    def _conn_begin(self, *args) -> None:
        self.ereignisse.append("conn_begin")

    def _conn_commit(self, *args) -> None:
        self.ereignisse.append("conn_commit")

    def _conn_rollback(self, *args) -> None:
        self.ereignisse.append("conn_rollback")

    # -- Auskunft ----------------------------------------------------------
    def offene_transaktionen(self) -> int:
        return self.offen


@pytest.fixture()
def transaktionen():
    """Zähler für offene Transaktionen — hängt an der ECHTEN Test-Engine."""
    zaehler = _Transaktionszaehler()
    try:
        yield zaehler
    finally:
        zaehler.stoppen()


class _HaengendeAblage:
    """Ablage-Attrappe: ``loeschen`` prüft, ob eine Transaktion offen ist.

    Review R1/1c: Der Job darf WÄHREND des Netzaufrufs KEINE Transaktion offen
    halten (sonst hinge der Request eines Benutzers an der Zeilensperre).

    CHAT-12a-3, Punkt 2: Die Prüfung läuft über den Ereigniszähler
    (``_Transaktionszaehler``) — NICHT mehr über ``engine.connect()``. Auf
    SQLite mit ``StaticPool`` wäre ``SELECT 1`` immer gelungen, der Test also
    blind. Erwartet werden bei JEDEM Netzaufruf **0** offene Transaktionen.
    Alles andere reicht die Attrappe an die echte (lokale) Ablage weiter.
    """

    name = "haengend"

    def __init__(self, echt, zaehler) -> None:
        self._echt = echt
        self._zaehler = zaehler
        self.waehrend: list[int] = []
        self.gesehen: list[str] = []

    def __getattr__(self, name):
        return getattr(self._echt, name)

    def schliessen(self) -> None:
        pass

    def loeschen(self, schluessel: str) -> bool:
        self.gesehen.append(schluessel)
        self.waehrend.append(self._zaehler.offene_transaktionen())
        return self._echt.loeschen(schluessel)

    def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
        return self.loeschen(schluessel)


def test_job_haelt_keine_transaktion_waehrend_des_netzaufrufs(gespraech, ablage,
                                                              transaktionen):
    """Review R1/1c / CHAT-12a-3: auswählen+belegen → COMMIT → löschen → verbuchen.

    Belegt dreierlei am echten Job:
    * die Ablage wird wirklich aufgerufen (zwei Aufträge),
    * WÄHREND des Netzaufrufs ist KEINE Transaktion offen — gemessen am
      Ereigniszähler (0), nicht an einem ``SELECT 1``, das auf SQLite immer
      gelingt,
    * die Belegung steht vorher in der Datenbank (``naechster_versuch_am``
      jetzt + ``ENTSORGUNG_BELEGUNG_MINUTEN``) — ein zweiter Lauf nimmt die
      Zeile nicht doppelt.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    jetzt = datetime.utcnow()
    for wert in ("chat-a-r1a", "chat-a-r1b"):
        _auftrag(wert, vorgemerkt=jetzt - timedelta(hours=1),
                 faellig=jetzt - timedelta(hours=1))
        ablage.schreiben(wert, b"x")

    haengend = _HaengendeAblage(ablage, transaktionen)
    setze_speicher(haengend)
    try:
        lauf = C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    assert lauf["abgearbeitet"] == 2, lauf
    assert lauf["fehler"] == 0, lauf
    assert sorted(haengend.gesehen) == ["chat-a-r1a", "chat-a-r1b"]
    # Bei BEIDEN Netzaufrufen ist keine Transaktion dieses Jobs mehr offen:
    # der Belegungs-Commit liegt davor.
    assert haengend.waehrend == [0, 0], haengend.waehrend
    assert _entsorgung(ablage) == []
    assert _objekte(ablage) == []


def test_job_belegt_vor_dem_netzaufruf(gespraech, ablage, transaktionen):
    """Review R1/1a / CHAT-12a-3: die Belegung ist COMMITTET, bevor gelöscht wird.

    Der Fake sieht im Netzaufruf nach, was die Datenbank sagt: ``versuche`` = 0
    (kein Fehlversuch verbucht) und ``naechster_versuch_am`` =
    ``jetzt + ENTSORGUNG_BELEGUNG_MINUTEN``. Der Zähler beweist zusätzlich, dass
    die Belegung nicht bloß in einer offenen Transaktion steht: beim
    Netzaufruf sind 0 Transaktionen offen, es gab also einen Commit.
    """
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    jetzt = datetime.utcnow()
    wert = "chat-a-belegt"
    _auftrag(wert, vorgemerkt=jetzt - timedelta(hours=2),
             faellig=jetzt - timedelta(hours=2))
    ablage.schreiben(wert, b"x")

    gesehen: list[tuple[datetime, int, int, int]] = []
    zaehler_ref = transaktionen

    class _Spaehende:
        name = "spaehend"

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def loeschen(self, schluessel: str) -> bool:
            commits_vorher = zaehler_ref.ereignisse.count("commit")
            # WICHTIG: die Zahl VOR dem Öffnen der Beobachtungs-Sitzung lesen —
            # deren eigenes ``begin``/``commit`` zählt sonst mit.
            offen_vorher = zaehler_ref.offene_transaktionen()
            with dbmod.SessionLocal() as s:
                zeile = s.get(ChatAnhangEntsorgung, schluessel)
                gesehen.append((zeile.naechster_versuch_am, int(zeile.versuche),
                                offen_vorher, commits_vorher))
            return ablage.loeschen(schluessel)

        def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
            return self.loeschen(schluessel)

    setze_speicher(_Spaehende())
    try:
        C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    assert len(gesehen) == 1, gesehen
    faellig, versuche, offen, commits_vorher = gesehen[0]
    assert faellig == jetzt + timedelta(minutes=C.ENTSORGUNG_BELEGUNG_MINUTEN), gesehen
    assert versuche == 0, gesehen
    # Die Belegung ist COMMITTET (keine offene Transaktion beim Netzaufruf) …
    assert offen == 0, gesehen
    # … und es gab vorher mindestens einen Commit: die Belegung selbst.
    assert commits_vorher >= 1, gesehen


def test_belegung_und_auswahl_sind_atomar(gespraech, ablage, transaktionen):
    """CHAT-12a-3, Punkt 1: zwischen Auswahl und Belegung liegt KEIN Commit.

    Der alte Ablauf wählte in ``SessionLocal.begin()`` (Commit #1), belegte
    danach in einer zweiten Transaktion (Commit #2). Genau in diesem
    Zwischenraum war die Zeile für einen parallelen Lauf wieder frei.

    Hier wird die Ereignisfolge geprüft: zwischen dem ERSTEN Commit des Jobs
    und dem BEGIN der Belegung darf nichts liegen — Auswahl und Belegung
    gehören zu DERSELBEN Transaktion. Das SQL selbst wird beim postgresql-
    Dialekt mitgeprüft: ``FOR UPDATE SKIP LOCKED`` und das
    ``UPDATE … naechster_versuch_am`` kommen aus EINER Funktion.
    """
    import inspect

    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    jetzt = datetime.utcnow()
    _auftrag("chat-a-atomar", vorgemerkt=jetzt - timedelta(hours=1),
             faellig=jetzt - timedelta(hours=1))
    ablage.schreiben("chat-a-atomar", b"x")

    # Netzaufruf markiert den Punkt, ab dem die Belegung fertig sein MUSS.
    marken: list[int] = []

    class _Markierend:
        name = "markierend"

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def loeschen(self, schluessel: str) -> bool:
            marken.append(len(transaktionen.ereignisse))
            return ablage.loeschen(schluessel)

        def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
            return self.loeschen(schluessel)

    transaktionen.ereignisse.clear()
    setze_speicher(_Markierend())
    try:
        C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    assert len(marken) == 1, marken
    folge = transaktionen.ereignisse[:marken[0]]
    # Vor dem Netzaufruf: genau EIN Commit (die Belegung) — kein zweiter
    # dazwischen. Mit dem alten Ablauf standen hier ZWEI Commits: einer für die
    # Auswahl, einer für die Belegung; dazwischen konnte ein paralleler Lauf
    # dieselben Zeilen wählen (Mutationsprobe, s. Karten-Kommentar).
    assert folge.count("commit") == 1, folge
    # Der Commit schließt die Transaktion, in der ausgewählt UND belegt wurde:
    # unmittelbar davor steht genau EIN ``begin`` ohne ``commit`` dazwischen.
    assert folge[:folge.index("commit")].count("begin") == 1, folge

    # PG-SQL: SKIP LOCKED und das UPDATE kommen aus DERSELBEN Funktion —
    # geprüft wird die Abfrage, die der CODE baut (SPEICHER-3, Punkt 5),
    # nicht eine im Test nachgebaute:
    #   * ``_entsorgung_auswahl_mit_sperre`` ist der PG-Zweig des Jobs und
    #     wird vom eingeengten Kern aufgerufen,
    #   * diese Funktion baut ihrerseits nur ``_entsorgung_auswahl_abfrage``
    #     (denselben Bau wie der SQLite-Zweig) plus ``FOR UPDATE SKIP LOCKED``.
    quelle = inspect.getsource(C._entsorgung_waehlen_und_belegen_eng)
    assert "_entsorgung_auswahl_mit_sperre(" in quelle, quelle
    assert "_entsorgung_auswahl_abfrage(" in quelle, quelle
    sperre_quelle = inspect.getsource(C._entsorgung_auswahl_mit_sperre)
    assert "with_for_update" in sperre_quelle, sperre_quelle
    assert "skip_locked=True" in sperre_quelle, sperre_quelle
    assert "_entsorgung_auswahl_abfrage(" in sperre_quelle, sperre_quelle
    assert "naechster_versuch_am=belegung" in quelle, quelle
    assert "SessionLocal.begin()" in quelle, quelle
    # Und die öffentliche Funktion fängt — sie reicht nur weiter (Punkt 2).
    oeffentlich = inspect.getsource(C._entsorgung_waehlen_und_belegen)
    assert "_entsorgung_waehlen_und_belegen_eng(" in oeffentlich, oeffentlich
    assert "except Exception" in oeffentlich, oeffentlich
    assert "return []" in oeffentlich, oeffentlich

    sql = str(C._entsorgung_auswahl_mit_sperre(jetzt, C.ENTSORGUNG_BATCH).compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": False}))
    assert "FOR UPDATE SKIP LOCKED" in sql.upper(), sql
    # Gegenprobe: der SQLite-Zweig (ohne Sperre) trägt sie NICHT — sonst wäre
    # die Prüfung oben auch bei einer dialektblinden Abfrage grün.
    ohne_sperre = str(C._entsorgung_auswahl_abfrage(jetzt, C.ENTSORGUNG_BATCH).compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": False}))
    assert "FOR UPDATE" not in ohne_sperre.upper(), ohne_sperre
    # Und beide wählen wirklich nach Fälligkeit, begrenzt auf ``anzahl``.
    assert "naechster_versuch_am <=" in ohne_sperre, ohne_sperre
    assert "LIMIT" in ohne_sperre.upper(), ohne_sperre


def test_pg_sql_waehlt_mit_skip_locked_und_der_request_mit_lock_timeout(gespraech, ablage):
    """Review R1/1c: das PG-SQL wird gegen den postgresql-Dialekt geprüft.

    Kein PostgreSQL im Test — deshalb die ANWEISUNGEN selbst: die Auswahl des
    Jobs muss ``FOR UPDATE SKIP LOCKED`` tragen, das ``DELETE`` des Requests
    davor ``SET LOCAL lock_timeout`` setzen. Beides wird hier kompiliert, also
    mit derselben SQLAlchemy-Fassung, die im Betrieb läuft. Die Auswahl kommt
    aus dem CODE (SPEICHER-3, Punkt 5) — nicht im Test nachgebaut.
    """
    from sqlalchemy.dialects import postgresql

    from diakronos_app.api import chat as C

    abfrage = C._entsorgung_auswahl_mit_sperre(datetime.utcnow(),
                                               C.ENTSORGUNG_BATCH)
    sql = str(abfrage.compile(dialect=postgresql.dialect(),
                              compile_kwargs={"literal_binds": False}))
    assert "FOR UPDATE SKIP LOCKED" in sql.upper(), sql

    # ... und der Request setzt sein Zeitlimit wirklich (Quelltext der Naht).
    import inspect

    quelle = inspect.getsource(C._entsorgung_lock_timeout)
    assert "SET LOCAL lock_timeout" in quelle
    assert "ENTSORGUNG_LOCK_TIMEOUT_MS" in quelle
    assert C.ENTSORGUNG_LOCK_TIMEOUT_MS <= 1000, C.ENTSORGUNG_LOCK_TIMEOUT_MS


def test_nextcloud_wartet_nicht_ohne_folgeversuch(monkeypatch):
    """Review R1/2: 503 + ``Retry-After: 30`` im Request-Pfad: < 3 s, kein Schlaf.

    ``time.sleep`` und die Uhr werden gemockt — der Test wartet NICHT. Geprüft
    wird ausserdem, dass ``_warte`` bei ``versuches=1`` (DELETE wie HEAD)
    überhaupt nicht aufgerufen wird.
    """
    import time

    import httpx

    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    geschlafen: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda sekunden: geschlafen.append(sekunden))

    antworten = [httpx.Response(503, headers={"Retry-After": "30"})] * 3

    def _antwort(request: httpx.Request) -> httpx.Response:
        return antworten.pop(0) if antworten else httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(_antwort))
    nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D"),
                   client=client)
    # Auch die Vorgabe-Wartezeiten dürfen nicht greifen.
    nc.wartezeiten = (5.0, 5.0, 5.0)

    from diakronos_app.speicher import AblageFehler, SpeicherNichtErreichbar

    start = time.monotonic()
    with pytest.raises((AblageFehler, SpeicherNichtErreichbar)):
        nc.loeschen_mit_zeitlimit("chat-a-503", 2.0)
    assert time.monotonic() - start < 3.0
    assert geschlafen == [], f"es wurde gewartet: {geschlafen}"

    # ``_noch_da`` (HEAD nach einer Zeitüberschreitung) ebenso: kein Schlaf.
    # Der dritte Aufruf der Attrappe antwortet 503 — ``_noch_da`` wertet das
    # als "noch da" und WARTET dabei nicht.
    assert nc._noch_da("chat-a-503", zeitlimit=2.0) is True
    assert geschlafen == [], f"es wurde gewartet: {geschlafen}"

    # Gegenprobe: MIT Wiederholung wird weiterhin gewartet (Verhalten bleibt).
    nc2 = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D",
                                    versuche=2),
                    client=httpx.Client(transport=httpx.MockTransport(
                        lambda r: httpx.Response(503, headers={"Retry-After": "3"}))))
    nc2.wartezeiten = ()
    with pytest.raises((AblageFehler, SpeicherNichtErreichbar)):
        nc2.loeschen("chat-a-503")
    # Zwei Aufrufe (DELETE scheitert → Kontroll-HEAD scheitert), je zwei
    # Versuche: gewartet wird nur zwischen den Versuchen, nie danach.
    # Ein unnötiger Schlaf nach dem jeweils letzten Versuch wären 4 Einträge.
    assert geschlafen == [3.0, 3.0], geschlafen


def test_logger_error_genau_einmal_bei_20_21_22(gespraech, ablage, caplog):
    """Review R1/3: Versuche 20 → 21 → 22 erzeugen GENAU EINEN Error.

    Die Bedingung ist ``== ENTSORGUNG_WARNUNG_AB`` (nicht ``>=``): sonst käme
    alle 6 Stunden dieselbe Zeile ins Protokoll.
    """
    import logging

    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    schluessel = "chat-a-error-einmal"
    _auftrag(schluessel, versuche=C.ENTSORGUNG_WARNUNG_AB - 1)
    setze_speicher(_ImmerKaputteAblage())
    try:
        caplog.set_level(logging.INFO, logger="diakronos_app.api.chat")
        jetzt = datetime.utcnow()
        for _ in range(3):                      # 20, 21, 22
            lauf = C.chat_anhang_entsorgung_abarbeiten(jetzt=jetzt)
            assert lauf["fehler"] == 1, lauf
            jetzt += timedelta(hours=6)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    fehler = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(fehler) == 1, [r.getMessage() for r in fehler]
    assert "20" in fehler[0].getMessage(), fehler[0].getMessage()
    versuche, _faellig, _ = _auftrag_stand(schluessel)
    assert versuche == 22, versuche


def test_dsgvo_vormerken_nutzt_dieselbe_uhr_wie_der_job(gespraech, ablage):
    """Review R1/4: ``vorgemerkt_am``/``naechster_versuch_am`` = Wandzeit.

    Mit ``datetime.utcnow()`` stand im DSGVO-Weg UTC; in einer Zeitzone vor
    UTC wäre ein frischer Auftrag erst Stunden später fällig gewesen.
    """
    from diakronos_app import db as dbmod
    from diakronos_app import dsgvo_anonymisierung as D
    from diakronos_app.api import chat as C

    vorher = C._jetzt()
    with dbmod.SessionLocal.begin() as s:
        assert D._entsorgung_vormerken(s, ["chat-a-uhr"]) == 1
    nachher = C._jetzt()

    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatAnhangEntsorgung, "chat-a-uhr")
        assert zeile is not None
        assert vorher <= zeile.vorgemerkt_am <= nachher, (zeile.vorgemerkt_am, vorher, nachher)
        assert zeile.vorgemerkt_am == zeile.naechster_versuch_am
    # Die UTC-Fassung läge um den Zeitzonen-Versatz daneben.
    assert abs((zeile.vorgemerkt_am - datetime.utcnow()).total_seconds()) < 24 * 3600


def test_dsgvo_hochlade_fehlerpfad_stellt_einen_auftrag(gespraech, ablage, monkeypatch):
    """Review R1/5: Datei abgelegt, DB-Zeile scheitert → Auftrag statt Waisen.

    Der Auftrag entsteht in einer EIGENEN Transaktion (hier scheitert die
    Ablage beim Löschen — ``_ImmerKaputteAblage``); er bleibt damit für den
    Minuten-Job stehen, und DER räumt die Datei ab. Nichts bleibt verwaist,
    auch wenn der direkte Löschversuch im Request scheitert.
    """
    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C

    g = gespraech
    # Einfügen der chat_anhang-Zeile scheitern lassen (der Fehlerpfad).
    echt_add = dbmod.Session.add

    def kein_add(self, obj, *args, **kwargs):
        if isinstance(obj, ChatAnhang):
            raise RuntimeError("Zeile kaputt (Attrappe)")
        return echt_add(self, obj, *args, **kwargs)

    # ``api.chat`` hält ``db`` als Modul — der Patch muss dort wirken, wo der
    # Endpunkt nachschlägt (``Session`` aus ``diakronos_app.db``).
    monkeypatch.setattr(dbmod.Session, "add", kein_add)

    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    class _KaputtNachAblage:
        """Ablage, bei der das Schreiben noch klappt und das Löschen scheitert."""

        name = "kaputt-nach-ablage"

        def __init__(self) -> None:
            self.abgelegt: list[str] = []

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def schreiben(self, schluessel: str, daten) -> None:
            self.abgelegt.append(schluessel)
            ablage.schreiben(schluessel, daten)

        def loeschen(self, schluessel: str) -> bool:
            from diakronos_app.speicher import AblageFehler

            raise AblageFehler("403 verboten (Attrappe)")

        def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
            return self.loeschen(schluessel)

    kaputt = _KaputtNachAblage()
    setze_speicher(kaputt)
    try:
        _set(ANNA)
        with pytest.raises(RuntimeError):
            C.anhang_hochladen(g, datei=_Upload(PNG, "foto.jpg", "image/jpeg"))
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    # ``Session.add`` wieder freigeben — OHNE ``monkeypatch.undo()``: das würde
    # auch die DB-Naht der Test-Suite zurücknehmen (Reihenfolge der Fixtures).
    monkeypatch.setattr(dbmod.Session, "add", echt_add)

    # Genau EIN Auftrag für den abgelegten Schlüssel, Datei noch da.
    assert len(kaputt.abgelegt) == 1, kaputt.abgelegt
    offen = _entsorgung(ablage)
    assert offen == kaputt.abgelegt, offen
    schluessel = offen[0]
    assert schluessel.startswith("chat-a"), schluessel
    assert schluessel in _objekte(ablage)

    # Der Job räumt sie ab (die lokale Ablage gelingt).
    lauf = C.chat_anhang_entsorgung_abarbeiten()
    assert lauf["abgearbeitet"] == 1, lauf
    assert schluessel not in _objekte(ablage)
    assert _entsorgung(ablage) == []


def test_zeitlimit_gilt_fuer_netzaufruf_auch_bei_haengender_ablage(gespraech, ablage):
    """Review R1/2 (Ende-zu-Ende): ein hängender Speicher verzögert die Antwort nicht.

    Die Ablage wirft beim Löschen sofort eine Zeitüberschreitung; der Endpunkt
    antwortet trotzdem erfolgreich und der Auftrag bleibt offen. (Der echte
    Netzweg mit ``Retry-After`` ist in
    ``test_nextcloud_wartet_nicht_ohne_folgeversuch`` geprüft.)
    """
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import SpeicherNichtErreichbar, setze_speicher, vergiss_speicher

    g = gespraech
    hoch = _hochladen(g, ANNA)["name"]
    schluessel = _schluessel_von(hoch)
    nachricht = _senden(g, "mit Bild", ANNA, anhaenge=[hoch])

    class _ZeitAus:
        name = "zeitaus"

        def __init__(self) -> None:
            self.limits: list[float] = []

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def loeschen(self, key):  # pragma: no cover — nur mit Limit
            raise SpeicherNichtErreichbar("Zeitüberschreitung (Attrappe)")

        def loeschen_mit_zeitlimit(self, key, sekunden):
            self.limits.append(sekunden)
            raise SpeicherNichtErreichbar("Zeitüberschreitung (Attrappe)")

    zeitaus = _ZeitAus()
    setze_speicher(zeitaus)
    try:
        _set(ANNA)
        antwort = C.loeschen(nachricht["name"])
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    assert antwort["geloescht"] is True
    assert zeitaus.limits == [C.ENTSORGUNG_ZEITLIMIT_SEKUNDEN], zeitaus.limits
    assert _entsorgung(ablage) == [schluessel]
    assert schluessel in _objekte(ablage)


# ── CHAT-12a-3: Belegung atomar, wirksame Transaktionstests ─────────────────


def test_upload_fehlerweg_loescht_auch_ohne_auftrag(gespraech, ablage, monkeypatch,
                                                    caplog):
    """CHAT-12a-3, Punkt 3: Löschversuch auch dann, wenn das Vormerken scheitert.

    Scheitert die ``chat_anhang``-Zeile (hier: ``Session.add``), ist der
    DB-Fehler der wahrscheinliche Fall — und dann scheitert auch das Vormerken
    des Auftrags. Vorher hing der Löschversuch an ``try``/``except`` um BEIDE
    Schritte: die Datei blieb als Waise OHNE Auftrag liegen, niemand hätte sie
    je wieder gesucht.

    Geprüft wird der Fehlerweg von ``anhang_hochladen``:
    * die Datei wird WIRKLICH gelöscht (die Ablage zählt die Aufrufe),
    * es bleibt kein Objekt in der Ablage,
    * beides (Vormerken und Löschen) scheitert → ``logger.error`` mit dem
      Schlüssel im Protokoll (manuelle Nacharbeit).
    """
    import logging

    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    g = gespraech
    echt_add = dbmod.Session.add

    def kein_add(self, obj, *args, **kwargs):
        if isinstance(obj, ChatAnhang):
            raise RuntimeError("Zeile kaputt (Attrappe)")
        return echt_add(self, obj, *args, **kwargs)

    monkeypatch.setattr(dbmod.Session, "add", kein_add)

    from diakronos_app.speicher import AblageFehler

    class _ZaehlendeAblage:
        """Schreiben klappt, Löschen klappt — die Aufrufe werden gezählt."""

        name = "zaehlend"

        def __init__(self) -> None:
            self.abgelegt: list[str] = []
            self.geloescht: list[str] = []

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def schreiben(self, schluessel: str, daten) -> None:
            self.abgelegt.append(schluessel)
            ablage.schreiben(schluessel, daten)

        def loeschen(self, schluessel: str) -> bool:
            self.geloescht.append(schluessel)
            return ablage.loeschen(schluessel)

        def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
            return self.loeschen(schluessel)

    zaehlend = _ZaehlendeAblage()
    setze_speicher(zaehlend)
    try:
        _set(ANNA)
        with pytest.raises(RuntimeError):
            C.anhang_hochladen(g, datei=_Upload(PNG, "foto.jpg", "image/jpeg"))
    finally:
        vergiss_speicher()
        setze_speicher(ablage)
        monkeypatch.setattr(dbmod.Session, "add", echt_add)

    assert len(zaehlend.abgelegt) == 1, zaehlend.abgelegt
    # Der Löschversuch lief TROTZ gescheitertem Vormerken.
    assert zaehlend.geloescht == zaehlend.abgelegt, zaehlend.geloescht
    assert zaehlend.abgelegt[0] not in _objekte(ablage)
    # Kein Auftrag entstanden (die DB war ja kaputt) — aber die Datei ist weg.
    assert _entsorgung(ablage) == []

    # Beides scheitert → Error mit dem Schlüssel (manuelle Nacharbeit).
    #
    # Damit das Vormerken WIRKLICH scheitert, muss die Datenbank wirklich
    # kaputt sein (das ist der Kartenfall: „beim DB-Fehler der wahrscheinliche
    # Fall“). Ein Fehler nur in ``Session.add`` genügt nicht — die
    # Vormerk-Transaktion ist eine EIGENE Sitzung und liefe glatt durch. Die
    # Attrappe wirft deshalb bei JEDEM ``execute`` innerhalb einer Sitzung,
    # die ``chat_anhang_entsorgung`` schreibt (also auch beim ``INSERT … ON
    # CONFLICT`` des Vormerkens).
    from sqlalchemy import event as sa_event

    class _AuchNichtLoeschend(_ZaehlendeAblage):
        def loeschen(self, schluessel: str) -> bool:
            # Auch der scheiternde Weg wird GEZÄHLT — sonst belegt der Test nur,
            # dass nichts passiert ist.
            self.geloescht.append(schluessel)
            raise AblageFehler("403 verboten (Attrappe)")

        def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
            return self.loeschen(schluessel)

    def _db_kaputt(conn, cursor, statement, *args) -> None:
        if "chat_anhang_entsorgung" in statement:
            raise RuntimeError("DB kaputt (Attrappe)")

    kaputt = _AuchNichtLoeschend()
    monkeypatch.setattr(dbmod.Session, "add", kein_add)
    setze_speicher(kaputt)
    # Ob die Zeile überhaupt geschrieben wurde, VOR dem kaputten Zustand prüfen:
    # ``abgelegt`` wird in ``schreiben`` gefüllt, und das läuft vor dem
    # ``Session.add``. Deshalb unten ein eigener Zähler über die Attrappe.
    schreibversuche: list[str] = []

    class _MitZaehler(_AuchNichtLoeschend):
        def schreiben(self, schluessel: str, daten) -> None:
            schreibversuche.append(schluessel)
            super().schreiben(schluessel, daten)

    kaputt = _MitZaehler()
    setze_speicher(kaputt)
    sa_event.listen(dbmod.engine, "before_cursor_execute", _db_kaputt)
    try:
        caplog.set_level(logging.INFO, logger="diakronos_app.api.chat")
        _set(ANNA)
        with pytest.raises(RuntimeError):
            C.anhang_hochladen(g, datei=_Upload(PNG, "foto.jpg", "image/jpeg"))
    finally:
        sa_event.remove(dbmod.engine, "before_cursor_execute", _db_kaputt)
        vergiss_speicher()
        setze_speicher(ablage)
        monkeypatch.setattr(dbmod.Session, "add", echt_add)

    assert len(schreibversuche) == 1, schreibversuche
    assert kaputt.geloescht == schreibversuche, kaputt.geloescht
    fehler = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(schreibversuche[0] in text for text in fehler), fehler


def test_erneut_vormerken_hebt_die_belegung_nicht_auf(gespraech, ablage):
    """CHAT-12a-3, Punkt 4: ein Request macht die Belegung eines Jobs nicht kaputt.

    Die Belegung ist eine Sperre (``naechster_versuch_am`` in der ZUKUNFT), kein
    Backoff. ``_entsorgung_erneut_vormerken`` darf sie deshalb nicht auf „jetzt“
    zurückziehen — sonst nähme der nächste Minuten-Takt dieselbe Zeile, während
    der laufende Job sie noch bearbeitet.

    Zwei Fälle:
    * belegte Zeile (Zukunft) → bleibt unverändert,
    * fällige Zeile (``naechster_versuch_am`` in der Vergangenheit) → wird auf
      ``jetzt`` gezogen (der Auftrag ist dann sofort dran).
    """
    from diakronos_app.api import chat as C

    jetzt = datetime.utcnow()
    belegt = jetzt + timedelta(minutes=C.ENTSORGUNG_BELEGUNG_MINUTEN)
    _auftrag("chat-a-belegung-bleibt", vorgemerkt=jetzt - timedelta(hours=2),
             faellig=belegt)
    _auftrag("chat-a-faellig-wird-jetzt", vorgemerkt=jetzt - timedelta(hours=2),
             faellig=jetzt - timedelta(minutes=3))

    C._entsorgung_erneut_vormerken("chat-a-belegung-bleibt", jetzt)
    C._entsorgung_erneut_vormerken("chat-a-faellig-wird-jetzt", jetzt)

    _v, belegt_stand, _f = _auftrag_stand("chat-a-belegung-bleibt")
    assert belegt_stand == belegt, belegt_stand
    _v, faellig_stand, _f = _auftrag_stand("chat-a-faellig-wird-jetzt")
    assert faellig_stand == jetzt, faellig_stand


def test_request_hebt_belegung_nicht_auf_speicher_scheitert(gespraech, ablage):
    """CHAT-12a-3, Punkt 4 (Ende-zu-Ende): Löschen im Request scheitert → Belegung bleibt.

    Der Job hat die Zeile belegt (``naechster_versuch_am`` in der Zukunft).
    Der Sofort-Versuch eines Requests scheitert (Ablage-Fehler) und ruft
    ``_entsorgung_erneut_vormerken`` — die Belegung muss stehenbleiben, sonst
    griffe der nächste Minuten-Takt dieselbe Datei ein zweites Mal.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    # Die Uhr des JOB-Elfchens: ``_entsorgung_sofort`` rechnet mit ``_jetzt()``
    # (Wandzeit der Gemeinde, im Container lokal) — nicht mit ``utcnow()``.
    jetzt = C._jetzt()
    belegt = jetzt + timedelta(minutes=C.ENTSORGUNG_BELEGUNG_MINUTEN)
    schluessel = "chat-a-request-belegung"
    _auftrag(schluessel, vorgemerkt=jetzt - timedelta(hours=1), faellig=belegt)
    ablage.schreiben(schluessel, b"x")

    setze_speicher(_ImmerKaputteAblage())
    try:
        entfernt = C._entsorgung_sofort([schluessel],
                                        limit_sekunden=C.ENTSORGUNG_ZEITLIMIT_SEKUNDEN)
    finally:
        vergiss_speicher()
        setze_speicher(ablage)

    assert entfernt == 0
    _v, stand, _f = _auftrag_stand(schluessel)
    assert stand == belegt, stand


def test_belegung_scheitert_ergibt_leere_liste_und_keinen_job_abbruch(
        gespraech, ablage, caplog):
    """SPEICHER-3, Punkt 2: Docstring sagt „leere Liste bei Fehler“ — jetzt stimmt es.

    ``_entsorgung_waehlen_und_belegen`` versprach das schon, hatte aber kein
    ``try``/``except``: ein Fehler bei Auswahl/Belegung flog aus dem
    Scheduler-Job heraus. Auf SQLite ist genau das erreichbar — zwei
    gleichzeitige Läufe ergeben ``SQLITE_BUSY``.

    Geprüft am echten Job: die Belegung scheitert (``SessionLocal`` wirft),
    der Job endet trotzdem mit einem ERGEBNIS (keine Ausnahme), die Ablage
    wird NICHT angefasst (ohne Belegung darf dieser Lauf nichts löschen) und
    es steht genau EINE ``warning`` im Protokoll.
    """
    import logging

    from diakronos_app import db as dbmod
    from diakronos_app.api import chat as C

    schluessel = "chat-a-belegung-kaputt"
    _auftrag(schluessel, vorgemerkt=datetime.utcnow() - timedelta(hours=1),
             faellig=datetime.utcnow() - timedelta(hours=1))
    beruehrt: list[str] = []

    class _Mitschreibend:
        name = "mitschreibend"

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def loeschen(self, wert: str) -> bool:
            beruehrt.append(wert)
            return ablage.loeschen(wert)

        def loeschen_mit_zeitlimit(self, wert: str, sekunden: float) -> bool:
            return self.loeschen(wert)

    class _BelegungKaputt:
        """``SessionLocal``, bei dem nur ``begin()`` mit ``SQLITE_BUSY`` abbricht.

        ``begin()`` ist der Weg der Belegung (``with SessionLocal.begin()``).
        Die reine LESESITZUNG des Jobs am Ende (``with SessionLocal() as s``)
        muss weiterlaufen — sonst wäre es nicht derselbe Fehlerpfad.
        """

        def __getattr__(self, name):
            return getattr(dbmod.SessionLocal, name)

        def begin(self):
            raise RuntimeError("database is locked (SQLITE_BUSY, Attrappe)")

        def __call__(self, *args, **kwargs):
            return echt(*args, **kwargs)

    echt = dbmod.SessionLocal
    C.dbmod.SessionLocal = _BelegungKaputt()
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    setze_speicher(_Mitschreibend())
    try:
        caplog.set_level(logging.INFO, logger="diakronos_app.api.chat")
        lauf = C.chat_anhang_entsorgung_abarbeiten()
    finally:
        C.dbmod.SessionLocal = echt
        vergiss_speicher()
        setze_speicher(ablage)

    # Kein Absturz, kein Löschen ohne Belegung.
    assert lauf["abgearbeitet"] == 0, lauf
    assert lauf["fehler"] == 0, lauf
    assert beruehrt == [], beruehrt
    # Die Zeile bleibt unbelegt und damit für den nächsten Takt fällig.
    _v, stand, _f = _auftrag_stand(schluessel)
    assert stand <= datetime.utcnow(), stand
    warnungen = [r for r in caplog.records if r.levelno == logging.WARNING
                 and "nicht belegt" in r.getMessage()]
    assert len(warnungen) == 1, [r.getMessage() for r in caplog.records]


def test_belegung_fehler_wird_im_job_nicht_zur_ausnahme(gespraech, ablage,
                                                        monkeypatch):
    """Punkt 2, zweite Auflage: „leere Liste“ direkt an der Funktion.

    Der eingeengte Kern darf werfen, die öffentliche Funktion nicht: sie gibt
    ``[]`` zurück und protokolliert einmal. Zusätzlich bleibt der Vertrag
    „leere Liste heißt: nichts löschen“ an der Direktgrenze sichtbar.
    """
    import logging

    from diakronos_app.api import chat as C

    jetzt = datetime.utcnow()
    _auftrag("chat-a-leer", vorgemerkt=jetzt - timedelta(hours=1),
             faellig=jetzt - timedelta(hours=1))

    def _kaputt(*args, **kwargs):
        raise RuntimeError("SQLITE_BUSY (Attrappe)")

    echt_kern = C._entsorgung_waehlen_und_belegen_eng
    monkeypatch.setattr(C, "_entsorgung_waehlen_und_belegen_eng", _kaputt)
    protokoll = []
    monkeypatch.setattr(
        C.logger, "warning",
        lambda text, *a: protokoll.append(text % a if a else text))

    assert C._entsorgung_waehlen_und_belegen(
        jetzt, 10, jetzt + timedelta(minutes=5)) == []
    assert len(protokoll) == 1, protokoll
    assert "nicht belegt" in protokoll[0], protokoll
    assert "SQLITE_BUSY" in protokoll[0], protokoll

    # Gegenprobe: ohne den Fehler liefert dieselbe Funktion weiterhin die
    # Schlüssel — das ``except`` schluckt nicht pauschal.
    from diakronos_app.api import chat as ChatModul

    ChatModul._entsorgung_waehlen_und_belegen_eng = echt_kern
    assert C._entsorgung_waehlen_und_belegen(
        jetzt, 10, jetzt + timedelta(minutes=5)) == ["chat-a-leer"]
    assert len(protokoll) == 1, protokoll


def test_erneut_vormerken_zieht_nichts_vor(gespraech, ablage):
    """SPEICHER-3, Punkt 3: ``<= jetzt`` bleibt wirkungslos — Verhalten unverändert.

    Der alte Kommentar sagte, die Funktion rücke ``naechster_versuch_am``
    vor, damit der Minuten-Job den Auftrag „nicht bis zum nächsten Takt“
    liegen lässt. Tatsächlich ändert das für den Job NICHTS: die Auswahl
    lautet selbst ``naechster_versuch_am <= jetzt``, ein bereits fälliger
    Auftrag wird also so oder so genommen. Die Anweisung schreibt lediglich
    ``jetzt`` über eine Zeit, die schon in der Vergangenheit lag — und lässt
    alles in der Zukunft unangetastet.

    Beide Richtungen werden festgehalten, damit „Verhalten nicht geändert“
    (Kartenauflage) belegt ist:
    * fällige Zeile: wird auf ``jetzt`` gesetzt — aber NICHT weiter vor, und
      für den Job bleibt sie derselbe fällige Auftrag,
    * belegte Zeile (Zukunft): bleibt unangetastet.
    """
    from diakronos_app.api import chat as C

    jetzt = datetime.utcnow()
    alt = jetzt - timedelta(hours=3)
    belegt = jetzt + timedelta(minutes=C.ENTSORGUNG_BELEGUNG_MINUTEN)
    _auftrag("chat-a-faellig", vorgemerkt=alt, faellig=alt)
    _auftrag("chat-a-belegt", vorgemerkt=alt, faellig=belegt)

    C._entsorgung_erneut_vormerken("chat-a-faellig", jetzt)
    C._entsorgung_erneut_vormerken("chat-a-belegt", jetzt)

    _v, stand_faellig, _f = _auftrag_stand("chat-a-faellig")
    # Genau auf „jetzt“ und nicht darüber hinaus (also kein Vorziehen der
    # Fälligkeit an einem laufenden Takt vorbei).
    assert stand_faellig == jetzt, stand_faellig
    assert stand_faellig <= jetzt, stand_faellig
    # Die belegte Zeile bleibt, wie sie ist — die Sperre des Jobs gilt.
    _v, stand_belegt, _f = _auftrag_stand("chat-a-belegt")
    assert stand_belegt == belegt, stand_belegt


def test_upload_fehler_vormerken_allein_ist_nur_eine_warnung(gespraech, ablage,
                                                             caplog):
    """SPEICHER-3, Punkt 4: gescheitertes Vormerken + gelungenes Löschen → warning.

    Vorher meldete allein das gescheiterte Vormerken „manuelle Nacharbeit“ als
    ``error`` — auch wenn die Datei gleich darauf gelöscht war und es nichts
    nachzuarbeiten gab. Jetzt: ``warning`` für das Vormerken, ``error`` NUR,
    wenn BEIDES scheitert.
    """
    import logging

    from diakronos_app.api import chat as C

    befunde = _hochladen_mit_kaputter_zeile(
        gespraech, ablage, caplog,
        vormerken_kaputt=True, loeschen_kaputt=False)

    assert befunde["error"] == [], (
        f"es steht ein error im Protokoll, obwohl die Datei weg ist: "
        f"{befunde['error']}")
    assert any("nicht vorgemerkt" in text for text in befunde["warning"]), befunde
    assert befunde["datei_weg"] is True


def test_upload_fehler_beides_kaputt_ist_genau_ein_error(gespraech, ablage,
                                                         caplog):
    """Punkt 4, zweite Hälfte: Vormerken UND Löschen scheitern → genau EIN ``error``."""
    befunde = _hochladen_mit_kaputter_zeile(
        gespraech, ablage, caplog,
        vormerken_kaputt=True, loeschen_kaputt=True)

    assert len(befunde["error"]) == 1, befunde["error"]
    assert "verwaist" in befunde["error"][0], befunde["error"]
    assert befunde["datei_weg"] is False


def _hochladen_mit_kaputter_zeile(gespraech, ablage, caplog, *,
                                  vormerken_kaputt: bool,
                                  loeschen_kaputt: bool) -> dict:
    """Upload, bei dem die ``chat_anhang``-Zeile scheitert — Fehlerweg messen.

    Der Ablauf ist der echte: ``anhang_hochladen`` schreibt die Datei, die
    Zeile scheitert, darauf folgen Vormerken und Sofort-Löschversuch. Nur die
    beiden Störungen werden eingeschaltet (Vormerken / Ablage-Löschen); die
    Zählung kommt aus ``caplog``.

    ``loeschen_kaputt`` wirkt NUR auf den Löschversuch NACH dem Fehlschlag:
    die Ablage-Attrappe lässt das Schreiben durch (sonst gäbe es keine Datei)
    und scheitert erst beim Löschen.
    """
    import logging

    from diakronos_app.api import chat as C
    from diakronos_app.speicher import setze_speicher, vergiss_speicher

    geschrieben: list[str] = []

    class _AblageMitSchreibrecht:
        name = "test"

        def schliessen(self) -> None:
            pass

        def __getattr__(self, name):
            return getattr(ablage, name)

        def schreiben(self, schluessel: str, daten) -> int:
            geschrieben.append(schluessel)
            return ablage.schreiben(schluessel, daten)

        def loeschen(self, schluessel: str) -> bool:
            if loeschen_kaputt:
                from diakronos_app.speicher import AblageFehler

                raise AblageFehler("403 verboten (Attrappe)")
            return ablage.loeschen(schluessel)

        def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
            return self.loeschen(schluessel)

    echt_zeile = C.ChatAnhang
    echt_vormerken = C._entsorgung_vormerken

    class _ZeileKaputt:
        """``ChatAnhang``, das beim Anlegen scheitert — der Fehlerweg."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError("chat_anhang-Zeile kaputt (Attrappe)")

    # Das Scheitern der Zeile entsteht über die Modellklasse im Modul: das
    # ``s.add(ChatAnhang(...))`` des Endpunkts wirft, der ``except``-Zweig
    # läuft an — Vormerken und Löschversuch wie im Betrieb.
    C.ChatAnhang = _ZeileKaputt
    if vormerken_kaputt:
        def _kaputt(session, schluessel):
            raise RuntimeError("Vormerken kaputt (Attrappe)")

        C._entsorgung_vormerken = _kaputt
    setze_speicher(_AblageMitSchreibrecht())
    befunde = {"error": [], "warning": [], "datei_weg": None}
    try:
        caplog.set_level(logging.INFO, logger="diakronos_app.api.chat")
        # Angemeldet wie bei jedem echten Upload — sonst scheitert der
        # Endpunkt an der Benutzerprüfung, lange bevor der Fehlerweg läuft.
        _set(SAENGER)
        with pytest.raises(Exception):  # noqa: B017 — der Upload MUSS scheitern
            C.anhang_hochladen(
                gespraech=gespraech, datei=_Upload(PNG, "x.png", "image/png"))
        for rekord in caplog.records:
            if rekord.name != "diakronos_app.api.chat":
                continue
            text = rekord.getMessage()
            if rekord.levelno >= logging.ERROR:
                befunde["error"].append(text)
            elif rekord.levelno == logging.WARNING:
                befunde["warning"].append(text)
        schluessel = geschrieben[-1] if geschrieben else None
        befunde["datei_weg"] = (
            schluessel is not None and schluessel not in _objekte(ablage))
    finally:
        C.ChatAnhang = echt_zeile
        C._entsorgung_vormerken = echt_vormerken
        vergiss_speicher()
        setze_speicher(ablage)
    assert geschrieben, "die Datei wurde nicht einmal geschrieben — Fehlerweg verfehlt"
    return befunde


def test_nextcloud_wartet_beim_5xx_nur_einmal_mit_dem_maximum(monkeypatch):
    """CHAT-12a-3, Punkt 5: ``Retry-After`` UND Backoff — nur EINMAL, das Maximum.

    Vorher schlief der 429/5xx-Zweig nach ``Retry-After`` und danach noch
    einmal den Backoff (bis 5 s + Backoff fuer EINEN Versuch). Jetzt wird pro
    Versuch genau einmal gewartet, mit der grösseren der beiden Zeiten.

    Geprüft wird direkt an ``_anfrage`` (ohne den Kontroll-HEAD von
    ``_loeschen``, der selbst ein zweiter, eigener Netzaufruf ist) — so zählt
    die Liste der Schlafaufrufe exakt die Wartezeit dieses Versuchs.
    """
    import time

    import httpx

    from diakronos_app.speicher import AblageFehler, SpeicherNichtErreichbar
    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    geschlafen: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda sekunden: geschlafen.append(sekunden))

    def _ablage(status: int, kopf: dict[str, str], *, versuche: int, wartezeiten):
        antwort = httpx.Response(status, headers=kopf)
        client = httpx.Client(transport=httpx.MockTransport(lambda r: antwort))
        nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D",
                                       versuche=versuche), client=client)
        nc.wartezeiten = wartezeiten
        return nc

    # Retry-After (3 s) ist KLEINER als der Backoff (5 s) → 5 s, einmal.
    nc = _ablage(503, {"Retry-After": "3"}, versuche=2, wartezeiten=(5.0,))
    with pytest.raises((AblageFehler, SpeicherNichtErreichbar)):
        nc._anfrage("DELETE", "https://cloud.example/x/a.png", aktion="Datei loeschen")
    assert geschlafen == [5.0], geschlafen

    geschlafen.clear()

    # Retry-After (4 s) ist GRÖSSER als der Backoff (0.5 s) → 4 s, einmal.
    nc2 = _ablage(429, {"Retry-After": "4"}, versuche=2, wartezeiten=(0.5,))
    with pytest.raises((AblageFehler, SpeicherNichtErreichbar)):
        nc2._anfrage("DELETE", "https://cloud.example/x/a.png", aktion="Datei loeschen")
    assert geschlafen == [4.0], geschlafen

    geschlafen.clear()

    # Kein Retry-After: der Backoff gilt (unverändert).
    nc3 = _ablage(500, {}, versuche=2, wartezeiten=(0.7,))
    with pytest.raises((AblageFehler, SpeicherNichtErreichbar)):
        nc3._anfrage("DELETE", "https://cloud.example/x/a.png", aktion="Datei loeschen")
    assert geschlafen == [0.7], geschlafen


def test_5xx_wiederholung_setzt_die_quelle_zurueck_und_wartet_einmal(monkeypatch):
    """CHAT-12a-3, Punkt 5: das ``continue`` darf das ``seek(0)`` nicht verschlucken.

    Der 429/5xx-Zweig überspringt nach dem Warten die gemeinsame Wartephase —
    dabei muss die Quelle trotzdem zurückgesetzt werden (``wiederholbar``).
    Sonst schickte der zweite Versuch 0 Bytes und die Datei käme leer an (genau
    der Fall aus ``test_speicher2_sicherung``). Geprüft wird beides zusammen:
    EIN Schlaf (Maximum) und ein vollständiger zweiter Upload.
    """
    import io
    import time

    import httpx

    from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

    geschlafen: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda sekunden: geschlafen.append(sekunden))

    gesehen: list[bytes] = []
    status = [500]

    def _antwort(request: httpx.Request) -> httpx.Response:
        gesehen.append(request.read())
        if status:
            return httpx.Response(status.pop(0))
        return httpx.Response(204)

    nc = Nextcloud(NextcloudZugang("https://cloud.example/x", "u", "p", "/D",
                                   versuche=2),
                   client=httpx.Client(transport=httpx.MockTransport(_antwort)))
    nc.wartezeiten = (0.5,)
    nc._angelegte_ordner.update(nc._alle_ebenen("a.png"))

    inhalt = b"r" * 100
    laenge = nc.schreiben("a.png", io.BytesIO(inhalt))
    assert laenge == len(inhalt)
    # Genau EIN Schlaf (Backoff, kein Retry-After am Fake), nicht zwei.
    assert geschlafen == [0.5], geschlafen
    # Der zweite Versuch begann wieder am DATEIANFANG (nicht leer).
    assert len(gesehen) == 2, [len(g) for g in gesehen]
    assert gesehen[1] == inhalt, [len(g) for g in gesehen]
