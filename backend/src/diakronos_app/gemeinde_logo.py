"""ON-2 — Gemeinde-Logo: pruefen, ablegen, oeffentlich ausliefern.

Drei Aufgaben, bewusst in EINEM Modul, damit Upload-Regel und Ausliefer-Regel
nicht auseinanderlaufen koennen:

1. ``pruefe_und_lege_ab`` — nimmt die hochgeladenen Bytes, prueft Typ, Groesse
   und Abmessungen und legt sie unter ``settings.files_dir`` ab.
2. ``logo_pfad`` — findet die hinterlegte Datei.
3. ``registriere`` — die OEFFENTLICHE Route ``GET {Praefix}/gemeinde/logo``.

Sicherheit (Kartenvorgabe D1, Nachtrag Orchestrator 2026-11-01)
--------------------------------------------------------------
* **Erlaubt sind PNG, JPEG, WebP und SVG.** Die drei Rastertypen werden an
  ihren MAGIC-BYTES erkannt (``files.binary_content_type``); der vom Client
  genannte Typ muss dazu passen.
* **SVG ist zugelassen** („Entscheidung 1 aus ON-2“ damit aufgehoben).
  Abgesichert wird NICHT durch Bereinigung — eine eigene Sanitisierung waere
  eine zweite, unvollstaendige HTML-Sanitisierung — sondern durch die
  AUSLIEFERUNG: ``Content-Security-Policy: default-src 'none'; style-src
  'unsafe-inline'; sandbox``, ``X-Content-Type-Options: nosniff``,
  ``Content-Type: image/svg+xml``, ``Content-Disposition: inline``. Die
  Oberflaeche bindet das Logo ausschliesslich per ``<img>`` ein — dort laufen
  keine Skripte. Geprueft wird nur, dass die Datei gueltiges XML mit Wurzel
  ``<svg>`` ist; ein Parser ohne DTD-/Entitaetsaufloesung (``defusedxml``)
  schliesst XXE aus. **Keine eigene Bereinigung.**
* **Hoechstens 2 MB** (``LOGO_MAX_BYTES``), hart beim Lesen begrenzt
  (``limit + 1`` Bytes), nicht erst nach dem vollstaendigen Einlesen.
* **Abmessungen gedeckelt** (``LOGO_MAX_KANTE``): mehr als 4096 px Breite oder
  Hoehe wird abgelehnt. Gelesen aus den Kopfdaten (PNG IHDR; JPEG SOF-Marker;
  WebP VP8X/VP8L/VP8) — ohne die Bilddaten zu dekodieren. Fuer SVG gibt es
  keine Abmessungspruefung (skalierbar).
* Der abgelegte Name ist ein UUID-Praefix mit sauberer Endung — NIE der
  Client-Name, NIE ein Pfad.
* Die Route ist **oeffentlich** (sie steht auf der Anmeldeseite und der
  Website), gibt aber nur das Bild heraus — keinen Namen, keinen Pfad.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.files import binary_content_type
from diakronos_app.frappe_compat.router import _error_response
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.gemeinde_logo")

__all__ = [
    "LOGO_MAX_BYTES",
    "LOGO_MAX_KANTE",
    "LOGO_TYPEN",
    "router",
    "registriere",
    "pruefe_und_lege_ab",
    "logo_pfad",
    "logo_url",
    "entferne_datei",
    "abmessungen",
]

#: Groesse, die der Assistent nennt („max. 2 MB“, Entwurf Frame 04).
LOGO_MAX_BYTES = 2 * 1024 * 1024

#: Groesste zulaessige Kante in Pixeln. Ein 20000-px-Bild ist kein Logo,
#: sondern ein Speicher- und Rechenrisiko fuer jeden Browser, der es anzeigt.
LOGO_MAX_KANTE = 4096

#: Die einzigen zulaessigen Bildtypen — je mit Endung fuer den Ablagenamen.
LOGO_TYPEN = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

#: Endung im Ablagenamen: nur Buchstaben/Ziffern, feste Laenge.
_ABLAGE_NAME = re.compile(r"^gemeinde-logo-[0-9a-f]{32}\.(png|jpg|webp|svg)$")

#: Endung -> MIME-Typ (Rueckweg in ``logo_pfad``).
_ENDUNG_TYP = {endung: typ for typ, endung in LOGO_TYPEN.items()}

#: Text der Typ-Ablehnung — an EINER Stelle, damit Hilfe und Fehler passen.
_TYP_TEXT = "Erlaubt sind PNG, JPEG, WebP oder SVG."

router = APIRouter(tags=["gemeinde"])


def _wurzel() -> Path:
    return Path(settings.files_dir).resolve()


# ── Abmessungen aus den Kopfdaten (ohne Dekodieren) ─────────────────────────


def _png_masse(roh: bytes) -> tuple[int, int] | None:
    """Breite/Hoehe aus dem PNG-IHDR-Chunk."""
    if len(roh) < 24 or roh[12:16] != b"IHDR":
        return None
    return int.from_bytes(roh[16:20], "big"), int.from_bytes(roh[20:24], "big")


#: JPEG-Start-of-Frame-Marker: SOF0..SOF15 ausser DHT (0xC4), JPG (0xC8)
#: und DAC (0xCC) — nur die tragen Breite und Hoehe.
_SOF = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def _jpeg_masse(roh: bytes) -> tuple[int, int] | None:
    """Breite/Hoehe aus dem ersten SOF-Segment (Baseline/Progressiv/…)."""
    i = 2
    n = len(roh)
    while i + 3 < n:
        if roh[i] != 0xFF:
            i += 1
            continue
        marker = roh[i + 1]
        # Fuellbytes (0xFF 0xFF), markergeschuetzte 0x00 und stand-alone
        # Marker (RSTn, SOI, EOI) tragen keine Laenge.
        if marker in (0xFF, 0x00, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > n:
            return None
        laenge = int.from_bytes(roh[i + 2:i + 4], "big")
        if laenge < 2:
            return None
        if marker in _SOF:
            if i + 9 > n:
                return None
            hoehe = int.from_bytes(roh[i + 5:i + 7], "big")
            breite = int.from_bytes(roh[i + 7:i + 9], "big")
            return breite, hoehe
        if marker == 0xDA:  # Bilddaten beginnen — davor kam kein SOF.
            return None
        i += 2 + laenge
    return None


def _webp_masse(roh: bytes) -> tuple[int, int] | None:
    """Breite/Hoehe aus dem ersten WebP-Teilblock (VP8X, VP8L oder VP8)."""
    if len(roh) < 25:
        return None
    teil = roh[12:16]
    if teil == b"VP8X":
        # 1 Byte Flags, 3 Byte reserviert (ab 21), dann Breite-1 und Hoehe-1
        # als 24-Bit little endian.
        if len(roh) < 30:
            return None
        breite = int.from_bytes(roh[24:27], "little") + 1
        hoehe = int.from_bytes(roh[27:30], "little") + 1
        return breite, hoehe
    if teil == b"VP8L":
        if roh[20] != 0x2F:
            return None
        bits = int.from_bytes(roh[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if teil == b"VP8 ":
        # Keyframe-Kopf: Frame-Tag (3 Byte), Sync 0x9D 0x01 0x2A, dann je
        # 2 Byte Breite und Hoehe (14 Bit gueltig).
        if len(roh) < 30 or roh[23:26] != b"\x9d\x01\x2a":
            return None
        breite = int.from_bytes(roh[26:28], "little") & 0x3FFF
        hoehe = int.from_bytes(roh[28:30], "little") & 0x3FFF
        return breite, hoehe
    return None


def abmessungen(roh: bytes, typ: str) -> tuple[int, int] | None:
    """Breite und Hoehe aus den Kopfdaten — ``None``, wenn nicht lesbar.

    Kein vollstaendiger Decoder: nur die Kopfdaten, damit ein 20000-px-Bild
    abgelehnt wird, ohne es zu rechnen. Fuer SVG gibt es keine festen
    Abmessungen (``width``/``height`` sind dort optional) — dort immer ``None``.
    """
    if typ == "image/png":
        return _png_masse(roh)
    if typ == "image/jpeg":
        return _jpeg_masse(roh)
    if typ == "image/webp":
        return _webp_masse(roh)
    return None


def _pruefe_kante(roh: bytes, typ: str) -> None:
    """Lehnt Bilder ab, deren Kante ``LOGO_MAX_KANTE`` ueberschreitet."""
    masse = abmessungen(roh, typ)
    if masse is None:
        return
    breite, hoehe = masse
    if breite > LOGO_MAX_KANTE or hoehe > LOGO_MAX_KANTE:
        raise ValidationError(
            f"Das Bild ist zu gross ({breite}×{hoehe} px, hoechstens "
            f"{LOGO_MAX_KANTE} px je Seite)."
        )


# ── SVG: nur wohlgeformtes XML mit Wurzel <svg> ─────────────────────────────


def _pruefe_svg(roh: bytes) -> None:
    """Prueft, dass die Bytes gueltiges XML mit Wurzelelement ``<svg>`` sind.

    ``defusedxml`` verweigert Entitaeten (jede Deklaration, auch externe) —
    damit ist XXE ausgeschlossen. Eine ausdrueckliche ``<!DOCTYPE``-Deklaration
    wird ZUSAETZLICH abgelehnt: ``defusedxml`` laesst eine reine externe DTD
    ohne Entitaetsbezug durch, ein SVG braucht aber nie einen Dokumenttyp.
    Eine inhaltliche Bereinigung gibt es bewusst NICHT (Nachtrag
    Orchestrator): Skripte im SVG koennen nicht laufen, weil es unter
    ``sandbox``-CSP ausgeliefert und nur als ``<img>`` eingebunden wird.
    """
    try:
        from defusedxml.ElementTree import fromstring as _fromstring
    except ImportError:  # pragma: no cover — defusedxml ist Pflichtabhaengigkeit
        raise ValidationError("SVG kann nicht geprueft werden (Pruefer fehlt).") from None
    # DOCTYPE vor dem Wurzelelement — jede Schreibweise (auch in Kommentaren
    # waere es harmlos, aber ein SVG braucht ihn nie: lieber streng).
    kopf = roh[:4096].lower()
    if b"<!doctype" in kopf:
        raise ValidationError(
            "Die SVG-Datei ist kein zulaessiges XML ohne Dokumenttyp."
        )
    try:
        wurzel = _fromstring(roh, forbid_dtd=True)
    except Exception as exc:  # noqa: BLE001 — Entitaet/kaputtes XML
        logger.info("SVG abgelehnt: %s", type(exc).__name__)
        raise ValidationError(
            "Die SVG-Datei ist kein zulaessiges XML ohne Dokumenttyp."
        ) from None
    # ElementTree liefert den lokalen Namen ohne Namensraum ({ns}svg -> svg).
    name = str(wurzel.tag)
    if "}" in name:
        name = name.rsplit("}", 1)[1]
    if name.lower() != "svg":
        raise ValidationError("Die SVG-Datei hat kein <svg>-Wurzel-Tag.")


def _ist_svg(roh: bytes) -> bool:
    """Sieht der Anfang nach einem XML-Dokument aus? (``binary_content_type``
    kennt XML nicht — es ist Text.) Ein BOM und fuehrender Leerraum sind
    erlaubt (XML erlaubt beides). Die echte Pruefung macht ``_pruefe_svg``.
    """
    kopf = roh[:512]
    if kopf.startswith(b"\xef\xbb\xbf"):
        kopf = kopf[3:]
    return kopf.lstrip(b" \t\r\n").startswith(b"<")


# ── Strukturpruefung der Rastertypen ────────────────────────────────────────


def _pruefe_bildstruktur(roh: bytes, typ: str) -> None:
    """Prueft, dass die Datei WIRKLICH ein vollstaendiges Bild ist.

    Die Magic-Bytes allein genuegen nicht: ein abgeschnittenes PNG beginnt
    korrekt und ist trotzdem kein Bild. Geprueft wird je Typ die billigste
    belastbare Struktur — kein vollstandiger Decoder, aber genug, um Muell
    abzulehnen, der spaeter als „Logo“ in der Kopfzeile steht:

      * PNG: Signatur + IHDR-Chunk mit Breite/Hoehe > 0 + IEND-Chunk am Ende.
      * JPEG: SOI am Anfang, EOI (`\\xff\\xd9`) am Ende, mindestens ein
        Segment-Kopf dazwischen.
      * WebP: RIFF-Block mit korrekter Laenge und einem bekannten VP8-Typ.
    """
    if typ == "image/png":
        if len(roh) < 33 or roh[12:16] != b"IHDR":
            raise ValidationError("Die Bilddatei ist beschaedigt (zu klein).")
        breite = int.from_bytes(roh[16:20], "big")
        hoehe = int.from_bytes(roh[20:24], "big")
        if breite <= 0 or hoehe <= 0:
            raise ValidationError("Die Bilddatei ist beschaedigt (keine Masse).")
        if not roh.rstrip(b"\x00").endswith(b"IEND\xaeB`\x82"):
            raise ValidationError("Die Bilddatei ist beschaedigt (unvollstaendig).")
        return
    if typ == "image/jpeg":
        if len(roh) < 16 or not roh.endswith(b"\xff\xd9"):
            raise ValidationError("Die Bilddatei ist beschaedigt (unvollstaendig).")
        if roh[2:3] != b"\xff":
            raise ValidationError("Die Bilddatei ist beschaedigt.")
        return
    if typ == "image/webp":
        if len(roh) < 16 or roh[12:16] not in (b"VP8 ", b"VP8L", b"VP8X"):
            raise ValidationError("Die Bilddatei ist beschaedigt.")
        riff_laenge = int.from_bytes(roh[4:8], "little")
        if riff_laenge + 8 > len(roh):
            raise ValidationError("Die Bilddatei ist beschaedigt (unvollstaendig).")
        return


def pruefe_und_lege_ab(datei: Any, deklarierter_typ: str | None = None) -> tuple[str, str]:
    """Prueft einen Upload und legt ihn ab. Rueckgabe: (Ablagename, MIME-Typ).

    ``datei`` ist ein ``UploadFile``-artiges Objekt (``.read``) oder ``bytes``.
    Wirft ``ValidationError`` mit einer Meldung, die dem Administrator weiterhilft
    (Typ, Groesse) — und keinen internen Pfad nennt.
    """
    roh: bytes
    if hasattr(datei, "read"):
        # Hart beim Lesen begrenzen — dieselbe Sperrklinke wie
        # ``frappe_core.upload_file``: ``read(limit + 1)``, damit ein
        # Riesen-Upload nicht erst vollstaendig in den Speicher wandert.
        #
        # Gelesen wird am UploadFile VORBEI auf dem dahinterliegenden,
        # synchronen Datenstrom (``.file``): ``UploadFile.read`` ist in
        # Starlette 1.10 eine Coroutine, und der Router ruft diesen Endpunkt
        # synchron in einem Arbeitsfaden auf (``router._read_args`` reicht das
        # ``UploadFile`` roh durch). ``frappe_core.upload_file`` macht es
        # genauso — ein ``asyncio.run`` im Faden waere der Fehler, den cc2de566
        # umgehen wollte.
        quelle = getattr(datei, "file", None) or datei
        gelesen = quelle.read(LOGO_MAX_BYTES + 1)
        roh = bytes(gelesen or b"")
    elif isinstance(datei, (bytes, bytearray)):
        roh = bytes(datei)
    else:
        raise ValidationError("Es wurde keine Datei uebergeben.")

    if not roh:
        raise ValidationError("Die Datei ist leer.")
    if len(roh) > LOGO_MAX_BYTES:
        raise ValidationError(
            f"Die Datei ist zu gross (max. {LOGO_MAX_BYTES // (1024 * 1024)} MB)."
        )

    erkannt = binary_content_type(roh)
    if erkannt is None and _ist_svg(roh):
        erkannt = "image/svg+xml"
    if erkannt is None or erkannt not in LOGO_TYPEN:
        raise ValidationError(f"Dateityp nicht erlaubt. {_TYP_TEXT}")
    deklariert = str(deklarierter_typ or "").split(";")[0].strip().lower()
    # Ein abweichender Client-Typ ist ein Zeichen fuer einen falschen Upload
    # (oder einen Tarntrick) — ablehnen statt raten. Das gilt auch fuer SVG:
    # eine als ``image/svg+xml`` deklarierte XML-Datei ist in Ordnung, eine
    # als ``image/png`` deklarierte SVG-Datei nicht.
    if deklariert and deklariert != erkannt:
        raise ValidationError("Der Dateiinhalt passt nicht zum Dateityp.")

    if erkannt == "image/svg+xml":
        _pruefe_svg(roh)
    else:
        _pruefe_bildstruktur(roh, erkannt)
        _pruefe_kante(roh, erkannt)

    ziel = _wurzel()
    ziel.mkdir(parents=True, exist_ok=True)
    name = f"gemeinde-logo-{uuid.uuid4().hex}{LOGO_TYPEN[erkannt]}"
    pfad = (ziel / name).resolve()
    # Guertel und Hosentraeger: der Zielpfad MUSS unterhalb von files_dir liegen.
    if pfad.parent != ziel:
        raise ValidationError("Ungueltiger Dateiname.")

    # Erst in eine temporaere Datei, dann atomar umbenennen: ein Abbruch
    # hinterlaesst nie ein halbes Logo. Der Temp-Name passt NICHT auf
    # ``_ABLAGE_NAME`` und wird deshalb nie ausgeliefert.
    tmp = pfad.with_suffix(pfad.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(roh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, pfad)

    logger.info("Gemeinde-Logo abgelegt (%s, %d Bytes).", erkannt, len(roh))
    return name, erkannt


def logo_pfad(name: str | None) -> tuple[Path, str] | None:
    """Pfad und MIME-Typ des hinterlegten Logos — ``None``, wenn keins da ist.

    Der gespeicherte Wert wird gegen ein festes Muster geprueft (kein Pfad, kein
    ``..``, keine fremde Datei). Eine Datei, die von Hand aus ``files_dir``
    entfernt wurde, gilt ebenfalls als „kein Logo“ — dann zeigt die Oberflaeche
    das Monogramm, statt eine 500 zu erzeugen.
    """
    wert = str(name or "").strip()
    if not wert or not _ABLAGE_NAME.match(wert):
        return None
    root = _wurzel()
    pfad = (root / wert).resolve()
    if pfad.parent != root or not pfad.is_file():
        return None
    return pfad, _ENDUNG_TYP[pfad.suffix.lower()]


def entferne_datei(name: str | None) -> None:
    """Loescht eine abgelegte Logodatei; fehlende Dateien sind kein Fehler."""
    treffer = logo_pfad(name)
    if treffer is None:
        return
    try:
        treffer[0].unlink()
    except OSError as exc:  # noqa: BLE001 — Aufraeumen darf nicht scheitern
        logger.warning("Logo-Datei nicht entfernbar: %s", type(exc).__name__)


def logo_url() -> str:
    """Die oeffentliche Adresse des Logos — MIT aktivem Praefix (WEB-5a).

    ``?v=<kurzhash>`` haengt am Ende (Cache-Busting): nach einem neuen Logo
    zeigt der Browser sofort das neue Bild statt der 300 s zwischengespeicherten
    alten Fassung. Der Kurzhash kommt aus dem Ablagenamen (je Upload eine neue
    UUID) — es wird dafuer keine Datei gelesen.
    """
    from diakronos_app.base_path import pfad

    basis = pfad("/gemeinde/logo")
    version = _version()
    return f"{basis}?v={version}" if version else basis


def _version() -> str:
    """Kurzhash des hinterlegten Logos fuer ``?v=`` (leer, wenn kein Logo)."""
    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            name = getattr(zeile, "logo_datei", None) if zeile is not None else None
    except Exception as exc:  # noqa: BLE001 — Anzeige darf nicht scheitern
        logger.warning("Logo-Version nicht lesbar: %s", type(exc).__name__)
        return ""
    wert = str(name or "").strip()
    if not wert:
        return ""
    return hashlib.sha256(wert.encode("utf-8")).hexdigest()[:8]


def _logo_bytes() -> tuple[Path, str] | None:
    """Liest den Logo-Verweis aus der Datenbank und loest ihn auf.

    Nie eine Exception nach aussen: eine fehlende/defekte Einstellung darf die
    Anmeldeseite nicht wegkaufen — dann gibt es eben kein Logo (404).
    """
    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            name = getattr(zeile, "logo_datei", None) if zeile is not None else None
    except Exception as exc:  # noqa: BLE001 — oeffentliche Route bleibt bedienbar
        logger.warning("Logo-Verweis nicht lesbar: %s", type(exc).__name__)
        return None
    return logo_pfad(name)


#: Kopfzeilen, unter denen ein Logo ausgeliefert wird. Fuer ALLE Typen gleich:
#: auch ein SVG ist damit ein Bild und kein ausfuehrbares Dokument.
#: ``Content-Disposition: inline`` steht ausdruecklich hier (nicht ueber
#: ``FileResponse(filename=…)``): der Ablagename soll nicht nach aussen, der
#: Kopf aber immer gesetzt sein — auch fuer SVG.
_LOGO_KOPFZEILEN = {
    "Cache-Control": "public, max-age=300",
    "X-Content-Type-Options": "nosniff",
    "Content-Disposition": "inline",
    # Ein Bild, kein Dokument: Skripte im SVG laufen nicht, selbst wenn ein
    # Browser den Typ anders auslegen wollte.
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
}


@router.get("/gemeinde/logo", include_in_schema=False)
def gemeinde_logo():
    """Das hinterlegte Gemeindelogo — OEFFENTLICH, nur das Bild.

    404, wenn kein Logo hinterlegt ist (oder die Datei fehlt). Die Oberflaeche
    zeigt dann das Monogramm aus Kurzname/Gemeindename.
    """
    treffer = _logo_bytes()
    if treffer is None:
        return _error_response("Kein Logo hinterlegt.", "DoesNotExistError", 404)
    pfad, typ = treffer
    return FileResponse(
        pfad,
        media_type=typ,
        headers=dict(_LOGO_KOPFZEILEN),
    )


def registriere(app) -> None:
    """Haengt die Logo-Route ein. Muss VOR der SPA-Auslieferung passieren."""
    app.include_router(router)
