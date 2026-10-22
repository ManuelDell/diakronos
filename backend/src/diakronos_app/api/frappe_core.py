"""Frappe-CORE-Methoden — von der SPA direkt aufgerufen (P2c).

Das sind **keine** Endpunkte der Diakronos-App, sondern Frappe selbst:
`/api/method/logout`, `/api/method/frappe.client.insert`,
`/api/method/upload_file`. Ohne sie bleiben Teile der SPA funktionslos.

Aufrufstellen (belegt):
  logout              public/js/builder/header_build_elements.js:184
                      public/js/psalmos/header_build.js:102
                      public/js/shared/header.js:163
  frappe.client.insert kein SPA-Aufrufer mehr (bis P2-5 legte
                      pages/Registrierung.vue den Link so an; heute laeuft das
                      ueber registrierungslink_api.create_link)
  upload_file          frontend/src/diakonos/pages/Profile.vue:465

Sicherheit: `insert` prueft die Permission (fail closed, siehe
`frappe_compat.permissions`). `upload_file` saeubert den Dateinamen, begrenzt
die Groesse, prueft den Content-Type und uebernimmt NIE einen Client-Pfad.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from diakronos_app.frappe_compat.exceptions import (
    FrappeCompatError,
    ValidationError,
)
from diakronos_app.frappe_compat.registry import _register
from diakronos_app.frappe_compat.registry_gen import column_names, is_known, model_for
from diakronos_app.frappe_compat.session import session
from diakronos_app.settings import settings


def _register_as(fn, *names: str, allow_guest: bool = False) -> None:
    """Registriert `fn` unter expliziten Frappe-Pfaden (z. B. `frappe.client.insert`)."""
    _register(fn, {"allow_guest": allow_guest})
    from diakronos_app.frappe_compat import registry as _r

    for name in names:
        _r._REGISTRY[name] = fn  # noqa: SLF001 — bewusst: Kernnamen sind keine Modulpfade


# ── /api/method/logout ──────────────────────────────────────────────────────


def logout(request=None):
    """Beendet die Session — `/api/method/logout` (A1b1: jetzt echt).

    Frueher ein Platzhalter, der nur `session.user` auf `Guest` setzte. Jetzt
    loescht er die echte Sitzung in Redis und entfernt das `sid`-Cookie.
    Die Implementierung liegt in `api/auth.py` — hier nur der Frappe-Kernpfad
    `logout` (siehe `_register_as`).

    Die SPA erwartet nach dem Aufruf HTTP 200 (sie leitet selbst um).
    `request` wird vom Compat-Router durchgereicht (Cookie-Zugriff).
    """
    from diakronos_app.api.auth import logout as _logout

    return _logout(request=request)


_register_as(logout, "logout", allow_guest=True)


# ── /api/method/frappe.client.insert ────────────────────────────────────────


def insert(doc: Any = None, **fields: Any) -> dict[str, Any]:
    """`frappe.client.insert` — legt genau einen Datensatz an und gibt ihn zurueck.

    Nimmt ein `doc`-Objekt (JSON) mit `doctype` + Feldern. Frappe antwortet mit
    dem angelegten Dokument under `message`. Die SPA nutzt diesen Weg heute
    NICHT mehr (der Registrierungslink laeuft ueber
    `registrierungslink_api.create_link`); der Endpunkt bleibt fuer
    Kompatibilitaet und direkte Aufrufer erhalten.

    **Permission ist Pflicht und fail-closed.** Anlegen ist ein schreibender
    Zugriff auf Fachdaten; ohne ausdrueckliche Admin-Rolle wird verweigert.
    Das ist die restriktive, richtige Voreinstellung (siehe permissions.py).
    """
    from diakronos_app.frappe_compat.permissions import require_admin

    # `doc` kann als JSON-String ankommen (Form-Post) oder als dict (JSON-Body).
    parsed: dict[str, Any] = {}
    if isinstance(doc, str):
        import json

        try:
            loaded = json.loads(doc)
        except ValueError:
            raise ValidationError("`doc` ist kein gültiges JSON.") from None
        if not isinstance(loaded, dict):
            raise ValidationError("`doc` muss ein Objekt sein.")
        parsed = dict(loaded)
    elif doc is None:
        parsed = {}
    elif isinstance(doc, dict):
        parsed = dict(doc)
    else:
        raise ValidationError("`doc` muss ein Objekt sein.")

    # Felder, die als Top-Level-Argumente mitkommen, ergaenzen (SPA schickt nur `doc`).
    for k, v in fields.items():
        parsed.setdefault(k, v)

    doctype = parsed.pop("doctype", None) or parsed.pop("doctype_name", None)
    if not doctype:
        raise ValidationError("`doctype` fehlt.")
    if not is_known(doctype):
        raise ValidationError(f"DocType {doctype!r} nicht gefunden")

    require_admin()
    if doctype == "Google Kalender Einstellungen":
        from diakronos_app.frappe_compat.exceptions import PermissionError
        raise PermissionError("Google-Credentials nur über die Import-API speichern.")
    # Hotfix R-P1-8: dieselbe Rollenmatrix wie /api/resource (User/Has Role nur System Manager).
    from diakronos_app.frappe_compat.router import _resource_denied
    if meldung := _resource_denied(doctype, "write"):
        from diakronos_app.frappe_compat.exceptions import PermissionError
        raise PermissionError(meldung)

    from diakronos_app.db import SessionLocal

    model = model_for(doctype)
    cols = column_names(doctype)
    data = {k: v for k, v in parsed.items() if k in cols}
    from diakronos_app.frappe_compat.api_helpers import (
        _coerce,
        _ist_personen_kennung,
        _new_name,
        _normalisiere_mitglied_email,
    )
    data = _coerce(doctype, data)
    if _ist_personen_kennung(doctype):
        # ID-1d: Die Kennung einer Person vergibt IMMER der Server — ein
        # mitgeschickter `name` („Max Muster“) wird verworfen, statt als
        # Primaerschluessel zu landen. Das geschieht VOR der Schranke
        # darunter, damit sie den geplanten Zustand der NEUEN Zeile sieht.
        data.pop("name", None)
        data["name"] = _new_name()
    elif not data.get("name"):
        data["name"] = _new_name()

    # SEC-c: derselbe Schreibweg wie `_create` — die E-Mail wird an der einen
    # Stelle normalisiert (sonst legt „\tanna@x.org“ eine zweite Person an).
    if doctype == "Mitglied":
        data = _normalisiere_mitglied_email(data)

    # P1-8d (Pflicht b, B1): Auch dieser Weg baut das Modell selbst — er muss
    # dieselbe zentrale Schranke rufen wie `/api/resource` und `_create`. Ohne
    # sie liess sich ein Mitglied mit `user`/`email` eines Verwaltungskontos und
    # `ausgeschlossen=1` anlegen und dieses damit aussperren.
    if doctype == "Mitglied":
        from diakronos_app.frappe_compat.api_helpers import (
            _pruefe_mitglied_schreibzugriff,
        )

        _pruefe_mitglied_schreibzugriff(data, None)
    elif doctype in ("User", "Has Role"):
        # W1 (R-P1-8e): auch das Anlegen einer Zeile laeuft durch die
        # Konto-/Rollen-Schranke. Beim Anlegen ist `name` leer — die Schranke
        # pruefe dann den geplanten `parent`/`role`-Inhalt. Ein NEUES Konto
        # kann den letzten SM nicht aussperren; der Aufruf bleibt dennoch
        # derselbe Weg, damit eine spaetere Erweiterung nicht vergessen wird.
        from diakronos_app.frappe_compat.api_helpers import (
            _pruefe_konto_schreibzugriff,
        )

        _pruefe_konto_schreibzugriff(doctype, None, data)

    sess = SessionLocal()
    try:
        obj = model(**data)
        sess.add(obj)
        sess.commit()
        sess.refresh(obj)
        return {c.name: _jsonable(getattr(obj, c.name)) for c in model.__table__.columns}
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001 — als fachlichen Fehler zurueckgeben
        sess.rollback()
        # SEC-c (W1): NICHT `str(exc)`. Der Treibertext enthaelt `INSERT INTO`,
        # Spalten, Parameter und die Adresse — bei einer gewoehnlichen Dublette
        # (Eindeutigkeits-Index) war das fuer jeden Admin ausloesbar.
        from diakronos_app.frappe_compat.api_helpers import _db_fehler

        raise _db_fehler(exc, doctype) from exc
    finally:
        sess.close()


_register_as(insert, "frappe.client.insert")


# ── /api/method/upload_file ─────────────────────────────────────────────────

# Erlaubte Upload-Typen (Frappe-`File` wird fuer Bilder/Dokumente benutzt).
_ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/pdf",
    "text/plain", "text/csv", "text/markdown",
    "application/zip",
    # ST2: Lied-Material — Audio und Notensatz.
    "audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav", "audio/flac",
    "application/xml", "text/xml",
}
# Diese Typen nutzen das hoehere Audio-/Material-Limit.
_AUDIO_MATERIAL_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav", "audio/flac",
    "application/zip", "application/xml", "text/xml",
}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _upload_limit(content_type: str) -> int:
    """Groessenlimit je Content-Type: Audio/Notensatz nutzen ihr eigenes Limit."""
    if content_type in _AUDIO_MATERIAL_TYPES:
        return int(getattr(settings, "max_upload_bytes_audio", 0)
                   or settings.max_upload_bytes)
    return settings.max_upload_bytes


def _sanitize_filename(name: str) -> str:
    """Dateinamen saeubern: kein Pfadanteil, kein Traversal, keine Sonderzeichen.

    `../../etc/passwd` -> `passwd`. Ein leerer Rest wird zu `datei`.
    """
    # Nur den letzten Pfadanteil betrachten — egal ob `/` oder `\`.
    base = os.path.basename(name.replace("\\", "/")).strip()
    # Fuehrende Punkte sind Traversal-Reste (`.`/`..`); auch versteckte Dateien
    # werden zu einem harmlosen Namen.
    base = base.lstrip(".")
    base = _SAFE_NAME.sub("_", base)
    base = base.strip("._")
    if not base:
        base = "datei"
    # Laenge begrenzen (Dateisystem-Limit mit Reserve fuer Praefix).
    return base[:180]


def _content_type_of(filename: str, declared: str | None) -> str:
    declared = (declared or "").split(";")[0].strip().lower()
    if declared:
        return declared
    import mimetypes

    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def upload_file(
    file: Any = None,
    filename: str | None = None,
    is_private: Any = True,
    folder: str | None = None,
    doctype: str | None = None,
    docname: str | None = None,
    fieldname: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Multipart-Upload: legt ein `File`-Dokument an und liefert `file_url`.

    Die SPA (Profile.vue) schickt `file` (Blob) und liest aus der Antwort
    `message.file_url`.

    Ablauf:
      1. Bytes aus dem Multipart-`file` lesen (UploadFile oder Formdatei).
      2. Groesse gegen `settings.max_upload_bytes` pruefen (Default 10 MB).
      3. Content-Type gegen eine Whitelist pruefen.
      4. Dateinamen saeubern (kein Path-Traversal).
      5. Datei unter `settings.files_dir` ablegen (UUID-Praefix, kein Client-Pfad).
      6. `File`-Dokument mit Metadaten + content_hash anlegen.

    **Es wird niemals ein vom Client gelieferter Pfad uebernommen.**
    """
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.files import attachment_allowed, validated_content_type
    from diakronos_app.frappe_compat.permissions import is_admin

    if not session.user or session.user == "Guest":
        raise PermissionError("Zugriff verweigert.")
    if (doctype or docname) and not (doctype and docname and (
        is_admin() or attachment_allowed(doctype, docname, 'write')
    )):
        raise PermissionError("Kein Schreibzugriff auf das angehaengte Dokument.")
    if file is None:
        raise ValidationError("`file` fehlt.")

    # Multipart-Feld kann ein UploadFile (mit .read()) oder rohe Bytes sein.
    # Der Lese-Deckel richtet sich nach dem **deklarierten** Typ: Audio/Notensatz
    # duerfen bis zum Audio-Limit gelesen werden, alles andere bleibt beim
    # allgemeinen Limit (kein unbegrenztes Einlesen fuer Text/PDF). Der echte
    # Typ wird danach aus den Magic-Bytes bestaetigt.
    raw: bytes | None = None
    ctype: str | None = None
    provided_name: str | None = filename
    if hasattr(file, "read"):
        provided_name = provided_name or getattr(file, "filename", None)
        ctype = getattr(file, "content_type", None)
        deklariert = _content_type_of(_sanitize_filename(provided_name or "datei"), ctype)
        lesedeckel = _upload_limit(deklariert)
        try:
            inner = getattr(file, "file", None)
            source = inner if inner is not None else file
            raw = source.read(lesedeckel + 1)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"Datei konnte nicht gelesen werden: {exc}") from exc
    elif isinstance(file, (bytes, bytearray)):
        raw = bytes(file)
    else:
        raise ValidationError("`file` muss ein Upload sein.")

    if not raw:
        raise ValidationError("Leere Datei.")

    safe_name = _sanitize_filename(provided_name or "datei")
    content_type = _content_type_of(safe_name, ctype)
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"Content-Type {content_type!r} nicht erlaubt (SVG ist gesperrt).")
    # Bei fehlendem/unpassendem Client-Typ leitet validated_content_type aus den
    # Magic-Bytes den echten Typ ab — das Limit wird danach bestimmt.
    content_type = validated_content_type(raw, content_type)
    limit = _upload_limit(content_type)
    size = len(raw)
    if size > limit:
        raise ValidationError(f"Datei zu gross ({size} Bytes, Limit {limit}).")

    if isinstance(is_private, bool):
        is_priv = is_private
    else:
        privacy = str(is_private).lower()
        if privacy not in ('1', 'true', 'yes', 'ja', '0', 'false', 'no', 'nein'):
            raise ValidationError('Ungueltiges is_private.')
        is_priv = privacy in ('1', 'true', 'yes', 'ja')

    # Ablage: UUID-Praefix -> kollisionsfrei und nie der Client-Name als Pfad.
    target_dir = os.path.realpath(settings.files_dir)
    os.makedirs(target_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}-{safe_name}"
    target_path = os.path.realpath(os.path.join(target_dir, stored_name))
    # Guertel-und-Hosentraeger: der Zielpfad MUSS unterhalb von files_dir liegen.
    if not target_path.startswith(target_dir + os.sep):
        raise ValidationError("Ungültiger Dateiname.")

    with open(target_path, "wb") as fh:
        fh.write(raw)

    file_url = f"/files/{stored_name}"
    content_hash = hashlib.sha256(raw).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    sess = SessionLocal()
    try:
        doc = FileModel(
            name=str(uuid.uuid4())[:10],
            file_name=safe_name,
            file_url=file_url,
            is_private=is_priv,
            attached_to_doctype=doctype or None,
            attached_to_name=docname or None,
            attached_to_field=fieldname or None,
            file_size=size,
            content_hash=content_hash,
            folder=folder or None,
            owner=session.user,
            modified_by=session.user,
            creation=now,
            modified=now,
            docstatus=0,
            idx=0,
        )
        sess.add(doc)
        sess.commit()
        sess.refresh(doc)
        return {
            "name": doc.name,
            "file_name": doc.file_name,
            "file_url": doc.file_url,
            "is_private": doc.is_private,
            "file_size": doc.file_size,
            "content_hash": doc.content_hash,
        }
    except FrappeCompatError:
        sess.rollback()
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        # Datei nicht als Waise liegen lassen, wenn der DB-Eintrag scheitert.
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


_register_as(upload_file, "upload_file")


def _jsonable(value: Any) -> Any:
    from datetime import date, datetime as _dt
    from decimal import Decimal

    if isinstance(value, (_dt, date)):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


__all__ = ["insert", "logout", "upload_file"]
