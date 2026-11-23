"""DATEIEN-2 — der Upload-Baustein: lesen, prüfen, benennen, ausliefern.

Chat-Anhänge (``api.chat.anhang_hochladen``/``anhang``, Karte CHAT-12a) und
später Gruppendateien (Karte DATEIEN-3) hochladen und ausliefern — bis hierher
stand diese Logik inline im Chat. Sie ist jetzt EIN Baustein mit zwei
RICHTLINIEN (Entscheidungen Manuel 23.11., Konzept DATEIEN-K):

``RICHTLINIE_POSITIV``
    Chat: nur was in der Positivliste steht (Bilder, PDF, Audio). Das ist das
    heutige Chat-Verhalten — unverändert.
``RICHTLINIE_SPERRLISTE``
    Gruppendateien (F8): ALLE Dokumentarten sind erlaubt, gesperrt sind nur
    ausführbare Dateien und Skripte (``GESPERRTE_ENDUNGEN``/``GESPERRTE_TYPEN``)
    — geprüft wird per MAGIE **und** per Endung.

Was der Baustein NICHT tut
--------------------------
* **Rechte.** Wer hochladen oder herunterladen darf, entscheiden die Aufrufer
  über den Rechte-Kern (``rechte.darf``/``api.chat._erlaube``). Hier steht
  keine Rechteregel.
* **Speicher.** Gelesen/geschrieben wird ausschließlich über
  ``speicher.hole_speicher()``. Dieses Modul kennt keinen zweiten Weg.
* **Datenbank.** Kein Modell, keine Zeile, keine Migration — das ist Sache der
  Aufrufer (DATEIEN-3).

Der Ablauf eines Uploads (genau eine Stelle je Schritt):

    grenze = anhanggrenze.anhang_max_bytes(s)      # EINE Wahrheit (F9)
    info = ablage.nimm_upload(datei, grenze, richtlinie)   # Deckel+Typ+Name
    ablage.lege_ab(info, "chat-a")                 # Speicher, inkl. Haken

``nimm_upload`` liest höchstens ``grenze + 1`` Byte, prüft leer/zu groß, den
Typ nach der Richtlinie, den Dateinamen und ruft ``pruefe_inhalt`` **genau
einmal** je Upload. Danach ist ``UploadInfo.inhalt`` die Wahrheit über die
Datei; ``typ`` ist immer ein sicher erkannter Typ oder ``UNBEKANNTER_TYP``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from diakronos_app.frappe_compat.exceptions import ValidationError, throw
from diakronos_app.models.chat import (
    ANHANG_BILDER,
    ANHANG_MAX_BYTES,
    ANHANG_NAME_MAX,
    ANHANG_TYPEN,
)

logger = logging.getLogger(__name__)

__all__ = [
    "GESPERRTE_ENDUNGEN",
    "GESPERRTE_MAGIE",
    "GESPERRTE_TYPEN",
    "POSITIVLISTE_TEXT",
    "RICHTLINIE_POSITIV",
    "RICHTLINIE_SPERR",
    "RICHTLINIEN",
    "UNBEKANNTER_TYP",
    "UploadInfo",
    "ablegen",
    "ablage_fehler",
    "ausliefern",
    "ausliefer_kopf",
    "dateiname",
    "erkenne_typ",
    "ist_gesperrt",
    "lege_ab",
    "nimm_upload",
    "pruefe_inhalt",
    "schluessel",
    "sicherer_typ",
    "zu_gross_text",
]

#: Der Typ, wenn die Magie NICHTS Sichereres kennt. Er wird nie inline
#: ausgeliefert: ``application/octet-stream`` + ``attachment`` + ``nosniff``.
UNBEKANNTER_TYP = "application/octet-stream"

#: Die beiden Richtlinien der Typ-Prüfung (F8).
RICHTLINIE_POSITIV = "positiv"   # Chat: ``ANHANG_TYPEN``
RICHTLINIE_SPERR = "sperrliste"  # Gruppendateien: alles außer Ausführbarem
RICHTLINIEN = (RICHTLINIE_POSITIV, RICHTLINIE_SPERR)

#: Was der Chat an Text sagt, wenn die Positivliste greift — EINE Meldung für
#: alle Ablehnungen (Typ, Magie, ``audio/mp4``-Video). Bestehender Wortlaut.
POSITIVLISTE_TEXT = (
    "Dateityp nicht erlaubt. Erlaubt sind Bilder (JPG, PNG, WebP, HEIC), "
    "PDF und Audio (MP3, M4A, OGG, OPUS)."
)

# ── Sperrliste (F8: „alle Dokumentarten, nur Ausführbares gesperrt") ────────
#
# Geprüft wird DOPPELT: der INHALT (Magie, Shebang) und die ENDUNG. Warum
# beides?
#
# * Die Endung ist die Zusage an den Menschen („das ist ein Skript") — sie
#   fängt auch Formate, deren Magie wir nicht kennen (Skripte haben keine).
#   Deshalb wird JEDES Segment geprüft, nicht nur das letzte: ``bericht.pdf.exe``
#   und ``bericht.exe.pdf`` sind beide gesperrt (Doppelendung, Kartenauflage).
#   Case-insensitiv (``.SH``), weil Windows-Endungen das nicht unterscheiden.
# * Die Magie fängt den umgekehrten Fall: ein ELF/PE/Mach-O-Binary oder ein
#   Shebang-Skript, das als ``.txt``/ohne Endung hochgeladen wird.
#
# HTML/SVG stehen mit auf der Liste, obwohl sie KEINE Programme sind: sie
# werden aus der Ablage mit ihrem Typ ausgeliefert, und ein im Browser
# geöffnetes HTML/SVG führt JavaScript in der Herkunft der Anwendung aus
# (Stored XSS). Gesperrt wird deshalb die AUSLIEFERBARE Form (``.html .htm
# .xhtml .svg .svgz``) — ein Dokument, das nur Text enthält, verliert nichts.
#
# Die Liste ist bewusst eine ENDUNGS-Liste und keine MIME-Liste: Skripte haben
# keinen verlässlichen Typ, ``mimetypes`` kennt sie nur halb, und der Client
# darf hier nichts mitreden.

#: Endungen (klein, MIT Punkt), die im Modus ``RICHTLINIE_SPERR`` gesperrt
#: sind. EINE Konstante — Prüfung und Test hängen an ihr, keine zweite Liste.
GESPERRTE_ENDUNGEN: frozenset[str] = frozenset({
    # Shell und Kommandozeilen
    ".sh", ".bash", ".zsh", ".ksh", ".csh", ".fish",
    # Windows: Programme, Batch, PowerShell, Skript-Hosts
    # ``.js``/``.jse``/``.mjs``/``.ws``/``.vb`` stehen hier, weil der Windows
    # Script Host bzw. cscript sie per DOPPELKLICK ausführt (``.js`` ist auch
    # serverseitig nie ein „Dokument"); ``.ps1xml``/``.msc``/``.gadget`` sind
    # Startpunkte für PowerShell/Snap-ins/Minianwendungen.
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".ps1xml", ".vbs", ".vbe",
    ".js", ".jse", ".mjs", ".ws", ".vb",
    ".wsf", ".wsh", ".msi", ".msp", ".scr", ".pif", ".cpl", ".lnk", ".reg",
    ".hta", ".msc", ".gadget",
    # Fremdcode-Container (.NET, Java, Android, macOS, AppImage)
    ".jar", ".apk", ".app", ".dmg", ".appimage",
    # Pakete, die beim Installieren Code ausführen
    ".deb", ".rpm", ".run", ".bin",
    # Programme und Bibliotheken
    ".elf", ".so", ".dll", ".dylib",
    # Skriptsprachen
    ".py", ".pyc", ".pyo", ".pl", ".rb", ".php", ".phar",
    # Desktop-Starter
    ".desktop",
    # Auslieferbare Formen mit Skriptanteil (Stored XSS, s. oben)
    ".html", ".htm", ".xhtml", ".svg", ".svgz",
})

#: Magie-Präfixe ausführbarer Dateien. ``\x7fELF`` Linux, die
#: ``cafebabe``-Sippe Java-Klassen und Mach-O-Fat, die vier Mach-O-Signaturen
#: für 32/64 Bit in beiden Bytereihenfolgen. **PE/COFF (``MZ``) steht NICHT
#: hier** — siehe ``_ist_pe``: ``MZ`` allein ist nur ein Textanfang, ein echtes
#: PE erkennt man erst am ``PE\0\0``-Kopf hinter ``e_lfanew``.
GESPERRTE_MAGIE: tuple[tuple[bytes, str], ...] = (
    (b"\x7fELF", "ELF-Programm"),
    (b"\xca\xfe\xba\xbe", "Java/Mach-O-Fat-Binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O-Programm"),
    (b"\xfe\xed\xfa\xcf", "Mach-O-Programm"),
    (b"\xce\xfa\xed\xfe", "Mach-O-Programm"),
    (b"\xcf\xfa\xed\xfe", "Mach-O-Programm"),
)

#: Dateitypen, die im Sperr-Modus NIE erlaubt sind, auch wenn die Magie sie
#: kennt — die auslieferbare Form mit Skriptanteil (s. ``GESPERRTE_ENDUNGEN``).
GESPERRTE_TYPEN: frozenset[str] = frozenset({"text/html", "image/svg+xml"})


@dataclass(frozen=True)
class UploadInfo:
    """Ergebnis von ``nimm_upload`` — alles, was die Aufrufer brauchen.

    ``inhalt`` sind die gelesenen Bytes (höchstens ``grenze``), ``typ`` der
    GEPRÜFTE Typ (oder ``UNBEKANNTER_TYP``), ``anzeigename`` der bereinigte
    Name für Anzeige und ``Content-Disposition``. ``groesse`` ist
    ``len(inhalt)`` — eine eigene Zahl gibt es nicht (zwei Zahlen wären zwei
    Wahrheiten).
    """

    inhalt: bytes
    typ: str
    anzeigename: str
    deklariert: str = ""

    @property
    def groesse(self) -> int:
        return len(self.inhalt)


# ── Lesen ──────────────────────────────────────────────────────────────────


def nimm_upload(datei, grenze: int | None = None,
                richtlinie: str = RICHTLINIE_POSITIV,
                name: str | None = None) -> UploadInfo:
    """Einen Upload lesen und prüfen — Deckel, leer, Größe, Typ, Name, Haken.

    ``grenze`` ist die WIRKSAME Grenze in Bytes (``chat_anhanggrenze.
    anhang_max_bytes`` — F9: derselbe Admin-Wert für Chat und Gruppendateien;
    ohne Angabe der Standard ``ANHANG_MAX_BYTES``). Gelesen wird
    ``grenze + 1``: ein zu großer Upload wird abgewiesen, ohne vollständig in
    den Speicher zu wandern.

    ``name`` ist der Name VOM AUFRUFER und hat Vorrang vor ``datei.filename``
    (der Chat übergibt so seinen Multipart-Parameter ``dateiname=``). Der Name
    wird EINMAL hier aufgelöst — es gibt keinen zweiten Weg.

    Gelesen wird am ``UploadFile`` VORBEI auf dem dahinterliegenden synchronen
    Datenstrom (``.file``) — ``UploadFile.read`` wäre in Starlette eine
    Coroutine, und die Endpunkte laufen synchron in einem Arbeitsfaden (dasselbe
    Muster wie ``frappe_core.upload_file``/``gemeinde_logo``).

    Reihenfolge und Meldungen sind die des Chats (Karte: VERHALTENSGLEICH):
    keine Datei → „keine Datei übergeben", leer → „Die Datei ist leer.",
    zu groß → ``zu_gross_text``, Typ → ``POSITIVLISTE_TEXT`` bzw. die
    Sperr-Meldung. ``pruefe_inhalt`` läuft GENAU EINMAL, nach der
    Größenprüfung und VOR dem Typ (ein Fund ist ein Fund, auch wenn die
    Endung harmlos wäre).

    Die ENDUNG wird nur in der Sperr-Richtlinie geprüft (``pruefe_endungen``)
    — im Chat entscheidet heute allein die Magie, das bleibt so. Geprüft wird
    der GESÄUBERTE Anzeigename (UND zusätzlich der rohe, falls er sich
    unterscheidet): sonst wäre die Sperrliste mit ``x.sh\\x00`` oder einem
    Zero-Width-Space umgehbar — der Browser bekommt aus der Bereinigung genau
    ``x.sh``, die Prüfung sähe aber etwas anderes (Review R1, MUSS 1).
    """
    if datei is None:
        throw("Es wurde keine Datei übergeben.")
    roh: bytes = b""
    deckel = (ANHANG_MAX_BYTES if grenze is None else int(grenze)) + 1
    deklariert = str(getattr(datei, "content_type", "") or "")
    if hasattr(datei, "read"):
        quelle = getattr(datei, "file", None) or datei
        try:
            # Der Deckel ist ``Grenze + 1``: ein knapp passendes Upload wird
            # vollständig gelesen (auch wenn der Strom in Stücken liefert), ein
            # zu großer endet nach Grenze+1 Byte — nie mehr im Speicher.
            gelesen = _lies_gedeckelt(quelle, deckel)
        except Exception as fehler:  # noqa: BLE001 — kaputter Upload ist eine Eingabe
            throw(f"Die Datei konnte nicht gelesen werden: {fehler}")
        roh = bytes(gelesen or b"")
    elif isinstance(datei, (bytes, bytearray)):
        roh = bytes(datei)
    else:
        throw("Es wurde keine Datei übergeben.")

    # Der Name: Aufrufer-Parameter vor ``.filename`` (Chat: ``dateiname or
    # datei.filename`` — dasselbe Vorrecht, eine Zeile früher).
    roher_name = str(name) if name else datei_name_roh(datei)
    if not roh:
        throw("Die Datei ist leer.")
    wirksam = ANHANG_MAX_BYTES if grenze is None else int(grenze)
    if len(roh) > wirksam:
        raise ValidationError(zu_gross_text(wirksam))

    # F7: der EINE Haken der Virenprüfung (heute tut er nichts, s. dort).
    pruefe_inhalt(roh, roher_name)

    richtlinie = _pruefe_richtlinie(richtlinie)
    typ = erkenne_typ(roh, deklariert, richtlinie)
    anzeigename = dateiname(roher_name, typ)
    if richtlinie == RICHTLINIE_SPERR:
        # Endung NACH dem Typprüfen: ``.pdf.exe`` soll zuerst als Programm
        # auffallen (Inhalt und Endung sagen dasselbe), nicht erst der Name.
        # Geprüft wird der Name, der WIRKLICH ausgeliefert wird — und der rohe
        # zusätzlich, damit keine Bereinigung eine Endung wegzaubern kann.
        pruefe_endungen(anzeigename)
        if roher_name != anzeigename:
            pruefe_endungen(roher_name)
    return UploadInfo(inhalt=roh, typ=typ, anzeigename=anzeigename,
                      deklariert=deklariert)


def _lies_gedeckelt(quelle, deckel: int) -> bytes:
    """Bis zu ``deckel`` Byte lesen — auch wenn der Strom in Stücken liefert.

    ``quelle.read(n)`` darf (IO-Konvention) WENIGER als ``n`` liefern. Ein
    knapp passender Upload wäre dann stillschweigend abgeschnitten — gelesen
    wird deshalb in Stücken, bis der Deckel erreicht ist oder der Strom nichts
    mehr hergibt. Am Deckel selbst bricht die Schleife ab: mehr als Grenze+1
    Byte wandern nie in den Speicher.
    """
    stuecke: list[bytes] = []
    rest = int(deckel)
    while rest > 0:
        stueck = bytes(quelle.read(rest) or b"")
        if not stueck:
            break
        stuecke.append(stueck)
        rest -= len(stueck)
    return b"".join(stuecke)


def datei_name_roh(datei) -> str | None:
    """Der Name, den der Client mitschickt (``dateiname=``/``.filename``)."""
    return getattr(datei, "filename", None)


def zu_gross_text(grenze: int) -> str:
    """Dieselbe Meldung wie heute im Chat — MB aus der EINSTELLUNG (CHAT-12c)."""
    return f"Die Datei ist zu groß (max. {int(grenze) // (1024 * 1024)} MB)."


# ── Typ erkennen ───────────────────────────────────────────────────────────


def erkenne_typ(roh: bytes, deklariert: str = "",
                richtlinie: str = RICHTLINIE_POSITIV) -> str:
    """Der GEPRÜFTE Typ einer Datei — aus INHALT und ENDUNG, nie blind vom Client.

    ``RICHTLINIE_POSITIV`` (Chat): Wiederverwendet wird ``files.
    binary_content_type`` (Kartenauflage: nicht kopieren) und der deklarierte
    Typ nur dort, wo er NÖTIG ist, weil die Magie mehrere Formate deckt:

    * **HEIC/HEIF** (``image/heic``): ISO-BMFF-``ftyp`` mit HEIF-Brand;
      ``binary_content_type`` kennt HEIC nicht.
    * **``audio/mp4``** (``.m4a``): dieselbe Magie deckt ``.mp4``-VIDEO.
      Deklariert der Client ``audio/…``, ist es ein M4A, sonst abgelehnt.

    Alles andere entscheidet AUSSCHLIESSLICH die Magie; was nicht in
    ``ANHANG_TYPEN`` steht, ist abgelehnt (``ValidationError`` mit
    ``POSITIVLISTE_TEXT``).

    ``RICHTLINIE_SPERR`` (Gruppendateien): gesperrt sind nur ``GESPERRTE_MAGIE``
    (ELF/PE/Mach-O), ein Shebang am Anfang und ``GESPERRTE_TYPEN``; der
    Rückfall ist ``UNBEKANNTER_TYP`` (wird als ``attachment`` ausgeliefert).
    ``name`` wird hier NICHT gebraucht — die Endung prüft ``ist_gesperrt``
    über ``name``… s. ``pruefe_endungen`` im Aufruf von ``nimm_upload``.
    """
    from diakronos_app.files import binary_content_type

    richtlinie = _pruefe_richtlinie(richtlinie)
    if richtlinie == RICHTLINIE_SPERR:
        gesperrt = _sperrgrund_inhalt(roh)
        if gesperrt:
            raise ValidationError(
                f"Dateityp nicht erlaubt: {gesperrt}. Ausführbare Dateien und "
                "Skripte sind gesperrt."
            )

    erkannt = binary_content_type(roh)
    deklariert = str(deklariert or "").split(";")[0].strip().lower()

    if _ist_heic(roh):
        erkannt = "image/heic"
    elif erkannt == "audio/mp4" and richtlinie == RICHTLINIE_POSITIV \
            and not deklariert.startswith("audio/"):
        erkannt = None

    if richtlinie == RICHTLINIE_POSITIV:
        if erkannt is None or erkannt not in ANHANG_TYPEN:
            raise ValidationError(POSITIVLISTE_TEXT)
        return erkannt

    if erkannt is not None and erkannt in GESPERRTE_TYPEN:
        raise ValidationError(
            f"Dateityp nicht erlaubt: {erkannt}. HTML und SVG sind gesperrt."
        )
    return erkannt or UNBEKANNTER_TYP


def pruefe_endungen(name: str | None) -> None:
    """Sperrliste gegen den NAMEN: JEDES Segment, case-insensitiv.

    ``bericht.pdf.exe`` UND ``bericht.exe.pdf`` sind gesperrt — geprüft wird
    jede Endung der Kette, nicht nur die letzte. Punkte am Anfang (``.bashrc``)
    zählen ebenfalls: der Name ist ``.bashrc``, das erste Segment ist leer,
    das zweite ``bashrc``… deshalb wird zusätzlich der GANZE Name als Endung
    geprüft (``"." + basis``).
    """
    basis = str(name or "").replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    if not basis:
        return
    segmente = [segment for segment in basis.split(".")[1:] if segment]
    kandidaten = {f".{segment}" for segment in segmente}
    kandidaten.add(f".{basis}")
    treffer = sorted(kandidaten & GESPERRTE_ENDUNGEN)
    if treffer:
        raise ValidationError(
            f"Dateityp nicht erlaubt ({treffer[0]}). Ausführbare Dateien und "
            "Skripte sind gesperrt."
        )


def ist_gesperrt(name: str | None) -> bool:
    """``True``, wenn die ENDUNG des Namens auf der Sperrliste steht."""
    try:
        pruefe_endungen(name)
    except ValidationError:
        return True
    return False


def _sperrgrund_inhalt(roh: bytes) -> str | None:
    """Sperrgrund aus dem INHALT (Magie, PE, Shebang, HTML/SVG) — ``None`` = ok."""
    for praefix, bezeichnung in GESPERRTE_MAGIE:
        if roh.startswith(praefix):
            return bezeichnung
    if _ist_pe(roh):
        return "PE/COFF-Programm (Windows)"
    # Shebang: ``#!`` in der ERSTEN Zeile (Skripte ohne Endung, ``.txt``-Tarnung).
    if roh.startswith(b"#!"):
        return "Skript (Shebang)"
    # HTML/SVG an der auslieferbaren Form: eine Datei, die der Browser als
    # Markup liest und deren Skripte in UNSERER Herkunft liefen (Stored XSS).
    if _ist_markup(roh):
        return "HTML/SVG-Markup"
    return None


def _ist_pe(roh: bytes) -> bool:
    """Echtes PE/COFF (Windows-Programm) — NICHT jedes ``MZ``.

    Der ``MZ``-Kopf allein ist zu billig: jede CSV, die mit „MZ-…" beginnt,
    trüge ihn (Review R1, KANN 4). Ein PE steht im ``e_lfanew``-Feld bei
    Offset ``0x3C`` (4 Byte, little-endian): es zeigt auf den ``PE\\0\\0``-Kopf.
    Nur wenn dort die Signatur steht, ist es ein Programm.
    """
    if len(roh) < 0x40 or roh[0:2] != b"MZ":
        return False
    e_lfanew = int.from_bytes(roh[0x3C:0x40], "little")
    return roh[e_lfanew:e_lfanew + 4] == b"PE\0\0"


#: Wie weit in die Datei geschaut wird, um Markup zu erkennen (nach BOM und
#: Leerraum reicht das dicke — ein ``<script>`` weiter hinten braucht ein
#: HTML/SVG-Dokument davor).
_MARKUP_BLICK = 4096
#: Dokument-Anfänge, die der Browser als Markup liest. ``<!doctype html``,
#: ``<html``, ``<head``, ``<body`` — und SVG auch hinter einer XML-Deklaration
#: oder Kommentar (``<?xml …?><svg``, ``<!--…--><svg``).
_MARKUP_START = (
    b"<!doctype html", b"<!doctype svg", b"<html", b"<head", b"<body",
    b"<svg", b"<script", b"<iframe", b"<object", b"<embed", b"<frame",
)
_MARKUP_SPAETER = (b"<svg", b"<script")


def _ohne_leerraum(roh: bytes) -> bytes:
    """Anfang ohne Leerraum und BOM (UTF-8/16), klein geschrieben.

    Beides in einer Schleife: ein BOM darf AUCH hinter Leerraum stehen (manche
    Editoren schreiben es so), deshalb erst Leerraum, dann BOM, dann wieder
    Leerraum — bis sich nichts mehr ändert.
    """
    anfang = roh[: _MARKUP_BLICK + 16]
    vorher = None
    while anfang != vorher:
        vorher = anfang
        anfang = anfang.lstrip()
        for bom in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):
            if anfang.startswith(bom):
                anfang = anfang[len(bom):]
                break
    return anfang.lower()


def _ist_markup(roh: bytes) -> bool:
    """``True`` für HTML/SVG in auslieferbarer Form — auch hinter XML-Deklaration.

    Gesperrt wird nur, was der Browser als Dokument ausführen könnte: die
    Dokument-Anfänge aus ``_MARKUP_START``, SVG hinter ``<?xml``/Kommentar.
    Ein Stück XML-OHNE SVG (Office-XML, ``<?xml …?><w:wordDocument>``) bleibt
    erlaubt — es ist ein Dokument, kein Skript.
    """
    kopf = _ohne_leerraum(roh)
    if not kopf:
        return False
    if kopf.startswith(_MARKUP_START):
        return True
    # ``<?xml …?><svg`` / ``<!--…--><svg`` / ``<svg:svg`` in den ersten Bytes.
    erstes = kopf[:512]
    if kopf.startswith((b"<?xml", b"<!--")):
        return any(marke in erstes for marke in _MARKUP_SPAETER)
    return False


def _pruefe_richtlinie(richtlinie: str) -> str:
    wert = str(richtlinie or "").strip().lower()
    if wert not in RICHTLINIEN:
        # Ein Tippfehler darf NIE zur Sperrliste werden, ohne dass es auffällt.
        raise ValueError(f"Unbekannte Richtlinie {richtlinie!r} (erlaubt: {RICHTLINIEN}).")
    return wert


#: Die HEIF-Brands (ISO/IEC 23008-12). ``mif1``/``msf1`` sind HEIF-Container,
#: die auch AVIF tragen können — AVIF ist hier NICHT erlaubt (das Konzept nennt
#: heic), deshalb zählt ``mif1`` nur, wenn KEIN AVIF-Brand daneben steht.
_HEIC_BRANDS = frozenset({b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx"})
_HEIF_BRANDS = frozenset({b"mif1", b"msf1"})
_AVIF_BRANDS = frozenset({b"avif", b"avis"})


def _ist_heic(roh: bytes) -> bool:
    """HEIC/HEIF-Erkennung an der ``ftyp``-Box (Video/AVIF sind es NICHT).

    ``[0:4]`` = Box-Länge, ``[4:8]`` = ``ftyp``, ``[8:12]`` = major brand,
    danach die compatible brands. ``audio/mp4``-Dateien (``isom``, ``mp42``,
    ``M4A ``) und MP4-Video (``isom``/``mp41``) fallen hier durch.
    """
    if len(roh) < 12 or roh[4:8] != b"ftyp":
        return False
    brands = {roh[8:12]} | {
        roh[i:i + 4] for i in range(16, min(len(roh), 40), 4)
    }
    if brands & _AVIF_BRANDS:
        return False
    return bool(brands & _HEIC_BRANDS or brands & _HEIF_BRANDS and roh[8:12] in _HEIF_BRANDS)


# ── Dateiname ──────────────────────────────────────────────────────────────


def dateiname(name: str | None, typ: str) -> str:
    """Anzeigename bereinigen: kein Pfad, keine Steuerzeichen, ≤ 120 Zeichen.

    ``../../etc/passwd`` → ``passwd``. Der Name ist REINE ANZEIGE — er wird
    nie als Speicherpfad benutzt (der Schlüssel ist technisch, ``schluessel``),
    aber er landet in ``Content-Disposition`` und darf dort weder Zeilen noch
    Pfade öffnen. Steuerzeichen (auch ``\\r``/``\\n``) fliegen ganz raus,
    Backslash und Doppelpunkt ebenso; Leerzeichen INNEN bleiben.
    """
    basis = str(name or "").strip().replace("\\", "/")
    basis = basis.rsplit("/", 1)[-1]
    basis = "".join(z for z in basis if z.isprintable() and z not in '\\/:*?"<>|').strip()
    basis = basis.lstrip(".").strip()
    if not basis:
        basis = f"anhang{ANHANG_TYPEN.get(typ, '')}"
    if len(basis) > ANHANG_NAME_MAX:
        stamm, punkt, endung = basis.rpartition(".")
        if punkt and endung and len(endung) <= 8:
            basis = stamm[: ANHANG_NAME_MAX - len(endung) - 1] + "." + endung
        else:
            basis = basis[:ANHANG_NAME_MAX]
    return basis


# ── Haken: Virenprüfung (F7, eigene Folgekarte ClamAV) ─────────────────────


def pruefe_inhalt(roh: bytes, name: str | None = None) -> None:
    """Der EINE Haken für die Inhaltsprüfung — heute ein No-Op.

    Entscheidung F7 (Manuel 23.11.): Die Virenprüfung kommt als EIGENE Karte
    (ClamAV). Damit sie später NICHT an drei Stellen eingebaut werden muss,
    steht hier die Naht: ``nimm_upload`` ruft sie **genau einmal** je Upload
    auf, nach der Größenprüfung und vor der Typ-Prüfung. Wirft sie, ist der
    Upload abgewiesen — die Aufrufer ändern sich dafür nicht.

    Signatur-Zusage an die Folgekarte: wirft ``ValidationError`` bei einem
    Fund (Menschen-Meldung, kein interner Pfad, kein Virusname), sonst
    ``None``. Kein Netz, kein Zeitlimit hier — das bringt die Folgekarte mit.
    """
    return None


# ── Ablage (immer über ``speicher.hole_speicher()``) ───────────────────────


def schluessel(praefix: str) -> str:
    """Ein technischer, eindeutiger Ablage-Schlüssel (``<praefix>-<uuid>``)."""
    return f"{praefix}-{uuid.uuid4().hex}"


def lege_ab(info: UploadInfo, praefix: str) -> str:
    """Die geprüften Bytes in die EINE Ablage schreiben — Rückgabe: der Schlüssel.

    ``praefix`` ist die Herkunft (``"chat-a"`` im Chat, später
    ``"datei"``/``"gruppe-a"`` für Gruppendateien). Fehler sind die des
    Speichers (``AblageFehler``) — die Aufrufer übersetzen sie in ihre Meldung;
    hier wird nichts erfunden und nichts verschluckt.
    """
    from diakronos_app.speicher import hole_speicher

    key = schluessel(praefix)
    hole_speicher().schreiben(key, info.inhalt)
    return key


def ablegen(datei, praefix: str, *, grenze: int | None = None,
            richtlinie: str = RICHTLINIE_POSITIV) -> tuple[UploadInfo, str]:
    """``nimm_upload`` + ``lege_ab`` in EINEM Schritt — ``(infos, schlüssel)``.

    Der kurze Weg für neue Aufrufer (DATEIEN-3): prüfen, ablegen, Schlüssel
    zurück. Wer die Prüfung und das Schreiben trennen muss (der Chat macht das:
    erst Kontingent, dann Ablage, dann Zeile), nimmt die beiden Schritte
    einzeln.
    """
    info = nimm_upload(datei, grenze=grenze, richtlinie=richtlinie)
    return info, lege_ab(info, praefix)


def oeffne(key: str):
    """Den Lese-Kontext eines gespeicherten Objekts — ``speicher.oeffnen``."""
    from diakronos_app.speicher import hole_speicher

    return hole_speicher().oeffnen(key)


def strom(key: str):
    """Blocks of a stored object — ``(bloecke, anfang, ende)`` aus dem Speicher.

    Fehlt das Objekt, kommt ``speicher.NichtGefunden`` (bzw. ``AblageFehler``)
    unverändert durch: die Aufrufer machen daraus ihre 404 — der Baustein
    erfindet keine eigene Ausnahme.
    """
    from diakronos_app.speicher import hole_speicher

    return hole_speicher().strom(key, von=0, bis=None)


# ── Ausliefern ─────────────────────────────────────────────────────────────


def sicherer_typ(typ: str | None) -> str:
    """Der Typ, den der Browser zu sehen bekommt — nie leer, nie ungeprüft.

    Nur ein Typ, den der Baustein selbst festgestellt hat (``ANHANG_TYPEN``
    oder ein bekannter ``files.binary_content_type``-Wert), wird
    durchgelassen; alles andere — leer, ``application/octet-stream``, ein
    gespeicherter Fremdwert — wird ``application/octet-stream``.
    """
    from diakronos_app.files import binary_content_type  # noqa: F401 — Doku

    wert = str(typ or "").strip().lower()
    if wert in ANHANG_TYPEN or wert in _BEKANNTE_TYPEN:
        return wert
    return UNBEKANNTER_TYP


#: Die Typen, die ``files.binary_content_type`` selbst sicher erkennt — ein
#: gespeicherter Wert aus dieser Menge ist „sicher erkannt", alles andere wird
#: als ``application/octet-stream`` ausgeliefert.
_BEKANNTE_TYPEN: frozenset[str] = frozenset(
    set(ANHANG_TYPEN) | {
        "image/gif", "audio/wav", "audio/flac", "application/zip",
    }
)


def ausliefer_kopf(typ: str, dateiname: str) -> dict[str, str]:
    """Die Kopfzeilen JEDER Auslieferung (Karte: inline/attachment, nosniff).

    * ``Content-Type`` = ``typ`` — steht der Typ NICHT sicher fest
      (``UNBEKANNTER_TYP``), wird ``application/octet-stream`` gesendet.
    * ``X-Content-Type-Options: nosniff`` — IMMER. Der Browser darf nicht
      raten, was eine Datei ist.
    * ``Content-Disposition`` = ``inline`` nur für ERKANNTE BILDER
      (``ANHANG_BILDER`` — die Oberfläche zeigt sie, wie heute im Chat);
      ``attachment`` für alles andere — auch PDF (das Chat-Verhalten bleibt:
      PDF ist heute ``attachment``, das ändert dieser Baustein nicht).
    * ``Cache-Control: private, no-store`` — der Inhalt gehört dem Gespräch,
      nicht dem Netz dazwischen.

    ``Content-Length`` setzt der Aufrufer (eine leere Datei braucht ehrlich
    ``0``; die Zahl kommt aus seiner Zeile bzw. aus dem Strom).
    """
    sicher = typ if typ and typ != UNBEKANNTER_TYP else UNBEKANNTER_TYP
    art = "inline" if sicher in ANHANG_BILDER else "attachment"
    return {
        "Content-Disposition": disposition(art, dateiname),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }


def disposition(art: str, dateiname: str) -> str:
    """``Content-Disposition`` mit ASCII-Rückfall und UTF-8-Name (RFC 6266).

    Ein Dateiname mit Umlauten darf keine kaputte Kopfzeile erzeugen: der
    ``filename``-Wert trägt nur ASCII (Sonderzeichen → ``_``), der echte Name
    steht als ``filename*`` nach RFC 5987.
    """
    from urllib.parse import quote

    einfach = "".join(z if (z.isascii() and z.isprintable() and z not in '"\\')
                      else "_" for z in dateiname) or "anhang"
    erweitert = quote(dateiname or "anhang", safe="")
    return f"{art}; filename=\"{einfach}\"; filename*=UTF-8''{erweitert}"
