"""Uploaded files: trusted content types, bounded paths and server-side ACLs."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from diakronos_app.frappe_compat.exceptions import FrappeCompatError, PermissionError, ValidationError
from diakronos_app.frappe_compat.permissions import check_permission, is_admin
from diakronos_app.frappe_compat.router import _error_response
from diakronos_app.frappe_compat.session import session
from diakronos_app.settings import settings

router = APIRouter(tags=['files'])
_TEXT_TYPES = {'text/plain', 'text/csv', 'text/markdown'}
# ST2: unkomprimiertes MusicXML/MuseScore-3 sind XML-Text ohne eigene Magie.
_XML_TYPES = {'application/xml', 'text/xml'}
_ACTIVE_TEXT = re.compile(r'<\s*(?:!doctype\s+html|html\b|script\b|svg\b|\?php\b)', re.I)


def binary_content_type(raw: bytes) -> str | None:
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if raw.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if raw.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if len(raw) >= 12 and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    if raw.startswith(b'%PDF-'):
        return 'application/pdf'
    # ST2: Audio-Magie fuer Lied-Material (Notenbeispiele/Aufnahmen).
    if raw[:4] == b'RIFF' and raw[8:12] == b'WAVE':
        return 'audio/wav'
    if raw.startswith(b'OggS'):
        return 'audio/ogg'
    if raw[:4] == b'fLaC':
        return 'audio/flac'
    if raw[:3] == b'ID3' or raw[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2', b'\xff\xfa'):
        return 'audio/mpeg'
    if len(raw) >= 12 and raw[4:8] == b'ftyp':
        return 'audio/mp4'
    if raw.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')):
        return 'application/zip'
    return None


def validated_content_type(raw: bytes, declared: str) -> str:
    detected = binary_content_type(raw)
    if detected:
        if detected != declared:
            raise ValidationError('Dateiinhalt passt nicht zum Content-Type.')
        return detected
    if declared in _TEXT_TYPES or declared in _XML_TYPES:
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValidationError('Textdatei muss UTF-8 sein.') from None
        if '\x00' not in text and not _ACTIVE_TEXT.search(text):
            # XML-Typen nur, wenn es wirklich nach XML aussieht.
            if declared in _XML_TYPES and not text.lstrip().startswith('<'):
                raise ValidationError('Dateiinhalt passt nicht zum Content-Type.')
            return declared
    raise ValidationError('Dateiinhalt oder Content-Type nicht erlaubt (SVG ist gesperrt).')


def stored_path(filename: str) -> Path | None:
    """Lokaler Dateipfad einer auslieferbaren Datei — nur wenn es ihn gibt.

    SPEICHER-1: Der Pfad kommt aus der Ablage (``speicher``), nicht mehr aus
    ``settings.files_dir``. Bei der Nextcloud-Ablage gibt es keinen lokalen
    Pfad — dort liefert die Funktion ``None``, und die Aufrufer, die zwingend
    eine Datei brauchen, holen sie ueber ``speicher_daten`` bzw.
    ``temporaerdatei``.

    Die Sicherheitspruefung (kein Pfad, kein ``..``, kein Symlink, kein
    Ausbruch) ist unveraendert: der Name muss weiterhin ein reiner
    Dateiname sein, und die Ablage prueft ihre Wurzel selbst.
    """
    # A URL is a single filename, never a path (also reject encoded leftovers).
    if not filename or filename in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9._-]+', filename):
        return None
    from diakronos_app.speicher import hole_speicher

    try:
        return hole_speicher().pfad(filename)
    except Exception:  # noqa: BLE001 — nicht erreichbar = nicht auslieferbar
        return None


def stored_daten(filename: str, *,
                 maximum: int | None = None) -> bytes | None:
    """Inhalt einer Datei aus der Ablage (``None``: gibt es nicht).

    SPEICHER-1: Der Weg fuer alle Aufrufer, die die BYTES brauchen und keinen
    Dateipfad (Nextcloud hat keinen). ``maximum`` begrenzt das Lesen: es
    werden hoechstens ``maximum + 1`` Bytes gelesen, damit der Aufrufer eine
    Ueberschreitung selbst erkennen kann, ohne die ganze Datei zu holen.
    """
    if not filename or filename in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9._-]+', filename):
        return None
    from diakronos_app.speicher import NichtGefunden, hole_speicher

    try:
        speicher = hole_speicher()
        with speicher.oeffnen(filename) as quelle:
            if maximum is None:
                return quelle.ganz()
            return quelle.lesen_vorn(maximum + 1)
    except NichtGefunden:
        return None
    except Exception:  # noqa: BLE001 — nicht erreichbar = nicht auslieferbar
        return None


def attachment_allowed(doctype: str | None, name: str | None, permission: str = 'read',
                       dateiname: str | None = None) -> bool:
    """Darf die Datei gelesen/geschrieben werden?

    `dateiname` ist optional und nur fuer die Urheberrechts-Pruefung noetig
    (Befund 3): nur so laesst sich Audio von Noten unterscheiden. Ohne die
    Angabe bleibt das Verhalten wie bisher (Anhang eines Liedes ist lesbar).
    """
    if not doctype or not name:
        return False
    # UXM-R5: Material (Noten/Audio) haengt an einer Liedfassung. Wer Lieder
    # sehen darf (jede angemeldete Person — so filtert `get_lieder`), darf auch
    # die Noten und Hoerproben oeffnen.
    #
    # Review P1-10 (Befund 3): Der Urheberrechts-Status des Liedes wird
    # beachtet. Ist er gesperrt ODER ist das Abspielen nicht erlaubt, wird
    # Audio nur an Musikverantwortliche/Admins ausgeliefert (Noten/PDF
    # bleiben normal lesbar). Audio wird am Dateinamen erkannt.
    if doctype in _LIED_ANHANG_DOCTYPES and permission == 'read':
        if _ist_audio(dateiname) and _lied_audio_gesperrt(doctype, name):
            return False
        return True
    # R-11a: Registrierungsformulare gehoeren der Mitgliederverwaltung (Fach
    # Personen/Registrierung) — sie pflegt deren Bilder, ohne Admin zu sein.
    if doctype in _VERWALTUNG_ANHANG_DOCTYPES:
        from diakronos_app.frappe_compat.permissions import ist_mitgliederverwaltung

        if ist_mitgliederverwaltung():
            return True
    try:
        return check_permission(doctype, name, permission).get('allowed') is True
    except FrappeCompatError:
        return False


#: R-11a: Anhaenge, die die Mitgliederverwaltung pflegt (Registrierung).
_VERWALTUNG_ANHANG_DOCTYPES = frozenset({'Anmeldeformular'})

#: DocTypes, deren Anhang fuer jede angemeldete Person lesbar ist (UXM-R5).
#: Die Leseregel dieser Objekte ist „jedes eingeloggte Mitglied" (siehe
#: `api.psalmos.musik.get_lieder` / `get_lied_detail`).
_LIED_ANHANG_DOCTYPES = frozenset({'Liedfassung', 'Lied', 'Liedgruppe'})

#: Dateiendungen, die als Audio gelten (Befund 3, Urheberrechts-Status).
_AUDIO_ENDUNGEN = frozenset({'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.opus'})
#: Status-Werte, die eine Auslieferung von Audio sperren.
_GESPERRTE_STATUS = frozenset({'gesperrt', 'gesperrt (ccli fehlt)', 'kein streaming'})


def _ist_audio(name: str | None) -> bool:
    """True, wenn die Endung auf eine Audiodatei schliesst (Befund 3)."""
    return bool(name) and Path(str(name)).suffix.lower() in _AUDIO_ENDUNGEN


def _lied_audio_gesperrt(doctype: str, name: str) -> bool:
    """True, wenn das betroffene Lied Audio NICHT oeffentlich abspielbar machen darf.

    Ein Lied kann direkt (`Lied`) oder ueber seine Fassung (`Liedfassung`) bzw.
    Liedgruppe (`Liedgruppe`) anhaengen. Geprueft wird `rechte_status` (gesperrt
    oder unbekannt) sowie `streaming_erlaubt`; nur Musikverantwortliche/Admins
    duerfen dann noch Audio abrufen (Befund 3).
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.psalmos import Lied, Liedfassung

    lied_name = name
    with SessionLocal() as db:
        if doctype == 'Liedfassung':
            lied_name = db.query(Liedfassung.lied).filter(
                Liedfassung.name == name).scalar()
        elif doctype not in ('Lied', 'Liedfassung'):
            # Liedgruppe: kein eindeutiges Lied — Sperrung kann nicht geprueft
            # werden; das Verhalten bleibt wie bisher.
            return False
        if not lied_name:
            return False
        row = db.query(Lied.rechte_status, Lied.streaming_erlaubt).filter(
            Lied.name == lied_name).first()
    if row is None:
        return False
    status, streaming = row[0], row[1]
    # Beide Schranken gelten unabhängig: fehlende Streaming-Erlaubnis ODER
    # gesperrter Rechtestatus. Ein gesetztes Häkchen hebt keine Sperre auf.
    if streaming and str(status or '').strip().lower() not in _GESPERRTE_STATUS:
        return False
    return not _ist_musikverantwortlich()


def _ist_musikverantwortlich() -> bool:
    """True fuer Musikverantwortliche, Admins und Systemmanager (Befund 3)."""
    try:
        from diakronos_app.api.psalmos.musik import (
            _is_admin,
            _is_musikverantwortlicher,
        )
        user = session.user
        return bool(_is_admin(user) or _is_musikverantwortlicher(user))
    except Exception:  # noqa: BLE001 — im Zweifel kein Sonderrecht
        return False


def _range_kopf() -> str | None:
    """Der ``Range``-Kopf des laufenden Requests — bereinigt (Review-Punkt 6).

    ``FileResponse`` (lokaler Pfad) wertet den ``Range``-Kopf SELBST aus und
    antwortet auf alles, was es nicht versteht, mit ``400``. Richtig ist laut
    RFC 9110 (14.2) aber, einen nicht unterstuetzten Bereich zu IGNORIEREN und
    die ganze Datei zu schicken: ``bytes=0-0,5-9`` (Mehrfachbereich),
    ``items=0-5`` (fremde Einheit) und ``bytes=abc`` werden hier zu ``None``.

    Den ``FileResponse``-Weg bedient ``range_kopf_bereinigen`` in
    ``request_context``: es nimmt denselben Kopf aus dem ASGI-``scope``, weil
    ``FileResponse`` nur dort nachsieht.
    """
    from diakronos_app.request_context import get_header
    from diakronos_app.speicher.basis import bereich_syntax

    roh = (get_header('range') or '').strip()
    if not roh or not bereich_syntax(roh):
        return None
    return roh


@router.get('/files/{filename:path}')
@router.get('/private/files/{filename:path}')
def serve_file(filename: str):
    if not session.user or session.user == 'Guest':
        return _error_response('Zugriff verweigert.', 'PermissionError', 403)
    path = stored_path(filename)
    if path is None:
        # SPEICHER-1: Bei der Nextcloud-Ablage gibt es keinen lokalen Pfad.
        # Ob die Datei existiert, entscheidet die Ablage — der Rest des Wegs
        # (Rechtepruefung, Typbestimmung) ist derselbe.
        if not _datei_vorhanden(filename):
            return _error_response('Datei nicht gefunden.', 'DoesNotExistError', 404)
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    with SessionLocal() as db:
        doc = db.query(FileModel).filter(FileModel.file_url.in_(
            ['/files/' + filename, '/private/files/' + filename])).first()
        if doc is None:
            return _error_response('Datei nicht gefunden.', 'DoesNotExistError', 404)
        # NULL privacy is not public. Owner/Admin/readable attachment only.
        if doc.is_private is not False and not (
            doc.owner == session.user or is_admin() or
            attachment_allowed(doc.attached_to_doctype, doc.attached_to_name,
                               dateiname=doc.file_name)
        ):
            return _error_response('Zugriff verweigert.', 'PermissionError', 403)
    text_content = b''
    if path is not None:
        with path.open('rb') as fh:
            prefix = fh.read(4096)
            mime = binary_content_type(prefix)
            if mime is None:
                # Text muss vollstaendig geprueft werden: ein Sniff-Praefix kann
                # UTF-8-Zeichen zerteilen und unsichere Inhalte hinter der
                # Sniff-Grenze uebersehen. Begrenzt wie beim Upload, inklusive
                # eines Bytes, um eine uebergrosse Datei zu erkennen. Text/XML
                # bleiben beim allgemeinen Limit (Audio/Notensatz-Binaerdateien
                # werden oben schon per Magic erkannt).
                fh.seek(0)
                text_content = fh.read(settings.max_upload_bytes + 1)
                if len(text_content) > settings.max_upload_bytes:
                    return _error_response('Dateityp nicht erlaubt.', 'PermissionError', 403)
    else:
        # SPEICHER-1 / Review-Punkt 4: Nextcloud-Ablage — kein lokaler Pfad.
        # Gelesen wird nur der KOPF zum Bestimmen des Typs (4096 Bytes, wie
        # beim Dateipfad); die Datei selbst wird anschliessend gestreamt.
        # Vorher wurde sie hier auf ``max_upload_bytes_audio`` begrenzt
        # gelesen und STILL abgeschnitten mit 200 ausgeliefert.
        prefix = _datei_daten_begrenzt(filename, 4096)
        if prefix is None:
            return _error_response('Datei nicht gefunden.', 'DoesNotExistError', 404)
        mime = binary_content_type(prefix)
        if mime is None:
            # Text muss vollstaendig geprueft werden (wie beim Dateipfad) —
            # das ist bewusst begrenzt: eine Textdatei ueber dem Limit ist
            # ohnehin nicht erlaubt.
            text_content = _datei_daten_begrenzt(filename, settings.max_upload_bytes + 1) or b''
            if len(text_content) > settings.max_upload_bytes:
                return _error_response('Dateityp nicht erlaubt.', 'PermissionError', 403)
    if mime is None:
        guessed = mimetypes.guess_type(filename)[0] or ''
        # Text hat keine eigene Magie. Unbekannten Text immer als Download
        # ausliefern, nie eine client-gelieferte Endung in einen ausfuehrbaren
        # Medientyp verwandeln. XML nur, wenn der Inhalt wirklich XML ist.
        if guessed not in _TEXT_TYPES and guessed not in _XML_TYPES:
            guessed = 'text/plain'
        try:
            mime = validated_content_type(text_content, guessed)
        except ValidationError:
            return _error_response('Dateityp nicht erlaubt.', 'PermissionError', 403)
    inline = mime.startswith('image/') or mime.startswith('audio/')
    kopfzeilen = {'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'}
    bereich = _range_kopf()
    if path is None:
        # SPEICHER-1 / Review-Punkt 4: Nextcloud-Ablage — die Datei wird
        # GESTREAMT, nie in den Speicher gelesen und nie abgeschnitten.
        # ``Range`` (Audio-Spulen, Safari) geht an die Ablage durch und kommt
        # als 206 mit ``Content-Range`` zurueck.
        return _aus_der_ablage(filename, mime, inline, kopfzeilen, bereich)
    antwort = FileResponse(path, media_type=mime, filename=filename,
                           content_disposition_type='inline' if inline else 'attachment',
                           headers=kopfzeilen)
    # Einen Range, den wir nicht bedienen, hat die Middleware schon aus dem
    # Request genommen (``request_context.range_kopf_bereinigen``) — hier
    # bleibt nur der gueltige Fall, den ``FileResponse`` selbst beantwortet.
    #
    # Review-Punkt 7: schrumpft die Datei zwischen Pruefung und Auslieferung
    # auf 0 Bytes (oder hinter das Bereichsende), ergaebe das einen ``206``
    # mit leerem Koerper. Dann antworten wir selbst: ``416`` mit der ECHTEN
    # Groesse.
    if bereich:
        jetzt = _dateigroesse(path)
        _, von, bis = _bereich_von_kopf(bereich, jetzt)
        if jetzt <= 0 or bis < von:
            return Response(status_code=416, headers={
                **kopfzeilen, 'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes */{max(jetzt, 0)}'})
    return antwort


def _dateigroesse(path) -> int:
    """Groesse einer lokalen Datei (``-1``, wenn sie nicht mehr da ist)."""
    try:
        return int(path.stat().st_size)
    except OSError:  # pragma: no cover — zwischen Pruefung und Stat geloescht
        return -1


def _bereich_von_kopf(bereich: str, gesamt: int) -> tuple[int, int, int]:
    """``(gesamt, von, bis)`` aus einem ``Range``-Kopf — ohne Ablage-Zugriff."""
    from diakronos_app.speicher.basis import _parse_bereich

    if gesamt <= 0:
        return gesamt, 0, -1
    _, von, bis = _parse_bereich(bereich, gesamt)
    return gesamt, von, bis


def _aus_der_ablage(filename: str, mime: str, inline: bool, kopfzeilen: dict,
                    bereich: str | None = None):
    """Datei aus einer pfadlosen Ablage ausliefern (Nextcloud): gestreamt.

    Kopfzeilen unveraendert wie beim lokalen Weg (``nosniff``, ``no-store``,
    ``Content-Disposition``) — zusaetzlich ``Accept-Ranges`` und, auf einen
    ``Range``-Kopf, ``206`` mit ``Content-Range``. Ein unerfuellbarer Bereich
    ergibt ``416`` mit ``Content-Range: bytes */<groesse>``.

    ``bereich`` ist der bereits bereinigte ``Range``-Kopf des Requests
    (``_range_kopf``); ``None`` heisst „ganze Datei“.

    Drei Sonderfaelle:

    * **Leere Datei ohne Range** ist ``200`` mit ``Content-Length: 0``
      (Review Runde 4, Punkt 1) — nicht ``416``; der ``(0, 0, -1)``-Wert der
      Ablage heisst „nichts auszuliefern“, und ohne Range ist das eine leere,
      aber vorhandene Datei.
    * **Unbekannte Gesamtgroesse** (``-1``, chunked-Antwort): es wird OHNE
      ``Content-Length`` durchgereicht (``200``, chunked) — keinen ``416``
      erfinden und keine Laenge behaupten (Punkt 3).
    * Eine Ablage-Antwort, die NICHT ausgeliefert wird (``ende < anfang``),
      wird geschlossen, bevor ``416`` kommt — der Generator laeuft dann nie,
      sein ``finally`` also auch nicht (Punkt 2).
    """
    from fastapi.responses import StreamingResponse

    from diakronos_app.speicher import AblageFehler, NichtGefunden, hole_speicher
    from diakronos_app.speicher.basis import bereich_syntax

    speicher = hole_speicher()
    try:
        gesamt, von, bis = speicher.groesse_und_bereich(filename, bereich)
    except (NichtGefunden, AblageFehler):
        return _error_response('Datei nicht gefunden.', 'DoesNotExistError', 404)

    gemeinsam = {
        **kopfzeilen,
        'Content-Disposition': f'{"inline" if inline else "attachment"}; filename="{filename}"',
        'Accept-Ranges': 'bytes',
    }
    if gesamt == 0 and not bereich:
        # Leere Datei, kein Range: 200 mit 0 Bytes (kein 416).
        return Response(status_code=200, headers={**gemeinsam, 'Content-Length': '0'})
    if bis < von:
        # 416 nur fuer einen syntaktisch GUELTIGEN, unerfuellbaren Bereich
        # (RFC 9110: ``bytes=100-`` bei 100 Bytes) und fuer eine leere Datei.
        # Ein Range, den wir nicht unterstuetzen (``bytes=0-0,5-9``,
        # ``items=0-5``), ist oben schon zur ganzen Datei geworden.
        return Response(status_code=416, headers={
            **gemeinsam, 'Content-Range': f'bytes */{max(gesamt, 0)}'})

    try:
        bloecke, anfang, ende = speicher.strom(
            filename, von=von, bis=bis, bereich=bool(bereich), gesamt=gesamt)
    except (NichtGefunden, AblageFehler):
        return _error_response('Datei nicht gefunden.', 'DoesNotExistError', 404)

    if ende < anfang:
        # Die Datei ist zwischen der Groessenabfrage und dem Lesen auf 0
        # Bytes geschrumpft: KEIN ``206 bytes 0--1/N``. Die Antwort der
        # Ablage ist schon geschlossen (macht ``strom`` selbst); bleibt der
        # ehrliche ``416`` mit der echten Groesse.
        return Response(status_code=416, headers={
            **gemeinsam, 'Content-Range': 'bytes */0'})

    # ``ende`` kommt inklusiv — die Laenge ist die Differenz plus eins.
    laenge = max(0, ende - anfang + 1)
    # 206 nur, wenn der Client einen Range geschickt hat und die Ablage ihn
    # AUCH bedient hat. Ein nicht unterstuetzter Range (``items=0-5``,
    # ``bytes=0-0,5-9``) wurde zur ganzen Datei -> 200 ohne ``Content-Range``.
    bedient = bool(bereich) and bereich_syntax(bereich)
    status = 206 if bedient else 200
    if bedient:
        gemeinsam['Content-Range'] = f'bytes {anfang}-{ende}/{gesamt}'
    if gesamt < 0 and not bedient:
        # Gesamtgroesse unbekannt (chunked aus der Ablage): OHNE
        # ``Content-Length`` durchreichen — der Client bekommt die Datei
        # vollstaendig, statt an einer erfundenen Laenge zu scheitern.
        return StreamingResponse(bloecke, status_code=status, media_type=mime,
                                 headers=gemeinsam)
    gemeinsam['Content-Length'] = str(laenge)
    return StreamingResponse(bloecke, status_code=status, media_type=mime,
                             headers=gemeinsam)


def _datei_vorhanden(filename: str) -> bool:
    """Liegt die Datei in der Ablage? (Auch ohne lokalen Pfad.)"""
    if not filename or filename in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9._-]+', filename):
        return False
    from diakronos_app.speicher import hole_speicher

    try:
        return hole_speicher().existiert(filename)
    except Exception:  # noqa: BLE001 — nicht erreichbar = nicht auslieferbar
        return False


def _datei_daten_begrenzt(filename: str, grenze: int) -> bytes | None:
    """Datei aus der Ablage lesen, hoechstens ``grenze`` Bytes (``None`` = fehlt).

    Review-Punkt 2: hier holte die Nextcloud-Ablage frueher die GANZE Datei
    (``oeffnen`` -> ``BytesQuelle(antwort.content)``), nur um die ersten
    4096 Bytes zu sehen. ``speicher.lesen_vorn`` holt bei ``Nextcloud``
    stattdessen einen gestreamten ``Range``-Ausschnitt (und bricht bei einem
    Server ohne Range ab); ``Lokal`` liest ohnehin von der Platte.
    """
    if not filename or filename in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9._-]+', filename):
        return None
    from diakronos_app.speicher import AblageFehler, hole_speicher

    try:
        return hole_speicher().lesen_vorn(filename, grenze)
    except AblageFehler:
        return None
