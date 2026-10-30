"""Oeffentliche Auslieferung der Formularbilder (REG-1a).

    GET /public/registrierung/<token>/bild/<banner|hintergrund>

Warum eine eigene Route und nicht ``/files/<name>``:

* ``files.serve_file`` verlangt eine Anmeldung. Das ist fuer Mitglieder-Dateien
  richtig, fuer ein Bild auf einer oeffentlichen Anmeldeseite aber unbrauchbar.
* Die Bilder sollen „oeffentlich NUR ueber das Formular abrufbar“ sein: der
  Token ist der Zugang. Deshalb haengt der Pfad am Token, und der Link wird
  ueber dieselbe Fachpruefung aufgeloest wie das Absenden
  (``registrierung._validate_token``).

Sicherheit:

* Gespeichert ist der Dateiname in ``anmeldeformular.bannerbild``/
  ``hintergrundbild`` (``anmeldung/formularbilder``). Pfadanteile, ``..`` und
  fremde Hosts werden dort abgelehnt.
* Ausgeliefert wird nur, was die MAGIC-BYTES als Rasterbild ausweisen
  (PNG/JPEG/GIF/WebP). SVG und andere Markup-Typen bleiben gesperrt —
  derselbe Grundsatz wie beim Upload (``files.validated_content_type``).
* ``Cache-Control: public, max-age=300`` (kurz): die Anmeldeseite darf das Bild
  im Browser halten, ein entferntes Bild ist aber spaetestens nach 5 Minuten
  weg. Kein ``no-store`` wie bei privaten Dateien, sonst laedt jeder Aufruf der
  oeffentlichen Seite das Bild erneut.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

from diakronos_app.frappe_compat.exceptions import FrappeCompatError
from diakronos_app.frappe_compat.router import _error_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["formularbilder"])

__all__ = ["router", "registrierung_formularbild"]


@router.get("/public/registrierung/{token}/bild/{rolle}")
def registrierung_formularbild(token: str, rolle: str):
    """Banner oder Hintergrund des Anmeldeformulars zu einem Link (oeffentlich).

    Antwort: das Bild selbst (``inline``), sonst die uebliche Fehlerform der
    Compat-Schicht (403 bei ungueltigem/abgelaufenem/vollem Link, 404 wenn kein
    oder kein brauchbares Bild hinterlegt ist).
    """
    from diakronos_app.anmeldung.formularbilder import BILD_ROLLEN, oeffne_formularbild
    from diakronos_app.frappe_compat.api_helpers import get_doc
    from diakronos_app.api.registrierung import _validate_token
    from diakronos_app.api.registrierung_vorschau import ist_vorschau_token
    from diakronos_app.frappe_compat.permissions import _has_admin_role

    if rolle not in BILD_ROLLEN:
        return _error_response("Unbekanntes Formularbild.", "DoesNotExistError", 404)

    try:
        # REG-1b: Das Bild der Formular-VORSCHAU im Editor. Der Vorschau-Token
        # gilt nur fuer Angemeldete mit Verwaltungsrolle; `_validate_token`
        # prueft die Rolle zusaetzlich selbst (`admin=True`).
        if ist_vorschau_token(token):
            link = _validate_token(token, admin=_has_admin_role())
        else:
            link = _validate_token(token)
        if not link.get("anmeldeformular"):
            return _error_response("Kein Formularbild vorhanden.", "DoesNotExistError", 404)
        form = get_doc("Anmeldeformular", link["anmeldeformular"])
    except FrappeCompatError as exc:
        # Verweigerung des Links (ungueltig/abgelaufen/voll/bevorstehend) —
        # wie bei jeder anderen oeffentlichen Route als Fehlerform ausgeben.
        status = int(getattr(exc, "http_status", 403) or 403)
        return _error_response(str(exc), type(exc).__name__, status)
    except Exception as exc:  # noqa: BLE001 — nie ein Stacktrace nach aussen
        logger.warning("Formularbild nicht lesbar (%s).", type(exc).__name__)
        return _error_response("Kein Formularbild vorhanden.", "DoesNotExistError", 404)

    wert = getattr(form, BILD_ROLLEN[rolle], None)
    from diakronos_app.anmeldung.formularbilder import dateiname_aus_wert

    name = dateiname_aus_wert(wert)
    if not name:
        return _error_response("Kein Formularbild vorhanden.", "DoesNotExistError", 404)

    treffer = oeffne_formularbild(name)
    if treffer is None:
        return _error_response("Kein Formularbild vorhanden.", "DoesNotExistError", 404)
    pfad, mime = treffer

    return FileResponse(
        pfad,
        media_type=mime,
        filename=name,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=300",
            # Kein Markup, keine Skripte — selbst wenn ein Browser den Typ
            # ignoriert, bleibt ein Rasterbild ein Rasterbild.
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
