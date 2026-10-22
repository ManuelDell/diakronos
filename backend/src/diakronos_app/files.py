"""Uploaded files: trusted content types, bounded paths and server-side ACLs."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

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
    # A URL is a single filename, never a path (also reject encoded leftovers).
    if not filename or filename in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9._-]+', filename):
        return None
    root = Path(settings.files_dir).resolve()
    candidate = root / filename
    if candidate.is_symlink() or candidate.resolve().parent != root:
        return None
    return candidate if candidate.is_file() else None


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
    try:
        return check_permission(doctype, name, permission).get('allowed') is True
    except FrappeCompatError:
        return False


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


@router.get('/files/{filename:path}')
@router.get('/private/files/{filename:path}')
def serve_file(filename: str):
    if not session.user or session.user == 'Guest':
        return _error_response('Zugriff verweigert.', 'PermissionError', 403)
    path = stored_path(filename)
    if path is None:
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
    return FileResponse(path, media_type=mime, filename=filename,
                        content_disposition_type='inline' if inline else 'attachment',
                        headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})
