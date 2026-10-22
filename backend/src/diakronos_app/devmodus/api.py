"""HTTP-Endpunkte des Dev-Modus unter ``diakronos.devmodus.api.<fn>``.

Aufbau bewusst wie ``api/planrahmen.py``: alle Schreibdienste sind POST-only,
jeder Aufruf ist EINE Transaktion, Fachfehler liefern die strukturierte
Meldungsliste ``pfad/code/meldung/hinweis``.

Ist der Dev-Modus ausgeschaltet (``DEVMODE_ENABLED`` nicht gesetzt),
registriert ``registriere()`` NICHTS — die Endpunkte existieren dann nicht
(404), genau wie die Karte es verlangt.
"""

from __future__ import annotations

from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable

from fastapi.responses import JSONResponse

from diakronos_app import db
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.devmodus import dienste, einstellungen, rechte

FRAPPE_MODULE = "diakronos.devmodus.api"


def _fehler(meldung: str, feld: str = "/", code: str = "ungueltig",
            hinweis: str = "") -> JSONResponse:
    return JSONResponse(status_code=417, content={
        "message": meldung, "exc_type": "ValidationError", "exception": "ValidationError",
        "meldungen": [{"pfad": feld, "code": code, "meldung": meldung, "hinweis": hinweis}],
    })


def _endpunkt(schreiben: bool = False) -> Callable:
    """Registriert eine Funktion mit Rechtepruefung und Fehleruebersetzung.

    ``schreiben=True``: nur POST (Antwort als JSON). Dienste ohne ``schreiben``
    sind Lese- oder Dateidienste und antworten auf GET.
    """

    def dekorator(fn: Callable) -> Callable:
        @wraps(fn)
        def aufruf(*args: Any, request: Any = None, **kwargs: Any) -> Any:
            if not einstellungen.aktiv():
                # Ohne Schalter existiert der Dev-Modus nicht.
                return JSONResponse(status_code=404, content={
                    "message": "Nicht gefunden", "exception": "NotFound", "exc_type": "NotFound"})
            if schreiben and (request is None or request.method != "POST"):
                return JSONResponse(status_code=405, content={
                    "message": "Schreibdienst benötigt POST.", "exc_type": "MethodNotAllowed"},
                    headers={"Allow": "POST"})
            try:
                with db.SessionLocal.begin() as s:
                    with db.als_aktuelle_sitzung(s):
                        wer = rechte.pruefen(s)
                        return fn(s, wer, *args, **kwargs)
            except dienste.DevFehler as exc:
                return _fehler(str(exc), exc.meldungen[0].get("pfad", "/"))
            except FrappePermissionError as exc:
                return JSONResponse(status_code=403, content={
                    "message": str(exc), "exc_type": "PermissionError",
                    "exception": "PermissionError"})
        aufruf.__signature__ = _signatur(fn)
        return whitelist(allow_guest=False)(aufruf)

    return dekorator


def _signatur(fn: Callable):
    """Signatur ohne den internen ``s``/``wer``-Vorspann (Frappe-Argumente)."""
    sig = signature(fn)
    params = [p for n, p in sig.parameters.items() if n not in ("s", "wer")]
    params.append(Parameter("request", Parameter.KEYWORD_ONLY, default=None))
    return sig.replace(parameters=params)


# ── Lesen ──────────────────────────────────────────────────────────────────

@_endpunkt()
def uebersicht(s: Any, wer: str) -> dict[str, Any]:
    """Kennzahlen + Konfiguration fuer die Befundliste und den Rahmen."""
    return {
        "kennzahlen": dienste.zaehle(s),
        "kuerzel": einstellungen.KUERZEL_ANZEIGE,
        "stt": einstellungen.stt_verfuegbar(),
        "sitzung": dienste.sitzung_aktiv(s, wer),
        "arten": list(einstellungen.ARTEN),
        "wichtigkeiten": list(einstellungen.WICHTIGKEITEN),
        "status": list(einstellungen.STATUS_GUELTIG),
    }


@_endpunkt()
def sitzung_status(s: Any, wer: str) -> dict[str, Any]:
    """Laeuft fuer diesen Benutzer gerade eine Dev-Sitzung?"""
    return {"sitzung": dienste.sitzung_aktiv(s, wer),
            "kuerzel": einstellungen.KUERZEL_ANZEIGE,
            "stt": einstellungen.stt_verfuegbar()}


@_endpunkt()
def ereignisse_holen(s: Any, wer: str, seit_sekunden: int = 60,
                     grenze: int = 200) -> dict[str, Any]:
    """Fehlerumfeld der letzten Sekunden (Polling des Dev-Rahmens)."""
    liste = dienste.fehlerumfeld(s, wer, seit_sekunden=seit_sekunden)
    return {"ereignisse": liste[:grenze], "fehler": len(liste)}


@_endpunkt()
def befunde_holen(s: Any, wer: str, status: str | None = None, seite: str | None = None,
                  art: str | None = None) -> list[dict[str, Any]]:
    return dienste.befunde(s, status=status, seite=seite, art=art)


@_endpunkt()
def befund_holen(s: Any, wer: str, name: str) -> dict[str, Any]:
    return dienste.befund_holen(s, name)


# ── Dev-Sitzung ────────────────────────────────────────────────────────────

@_endpunkt(True)
def sitzung_starten(s: Any, wer: str) -> dict[str, Any]:
    """Dev-Modus fuer diesen Nutzer einschalten (Herzschlag der Ueberwachung)."""
    return dienste.sitzung_starten(s, wer)


@_endpunkt(True)
def sitzung_beenden(s: Any, wer: str) -> dict[str, Any]:
    return dienste.sitzung_beenden(s, wer)


# ── Befunde ────────────────────────────────────────────────────────────────

@_endpunkt(True)
def befund_speichern(s: Any, wer: str, text: str = "", art: str = "fehler",
                     wichtigkeit: str = "mittel", url: str | None = None,
                     route: str | None = None, seitentitel: str | None = None,
                     seite: str | None = None, viewport: str | None = None,
                     bildschirm: str | None = None, geraet: str | None = None,
                     browser: str | None = None, theme: str | None = None,
                     sprache: str | None = None, element: dict | None = None,
                     bilder: list | None = None, audio: dict | None = None) -> dict[str, Any]:
    """Legt einen Befund an. Fehlerumfeld wird automatisch beigelegt."""
    return dienste.befund_anlegen(
        s, wer, text=text, art=art, wichtigkeit=wichtigkeit, url=url, route=route,
        seitentitel=seitentitel, seite=seite, viewport=viewport, bildschirm=bildschirm,
        geraet=geraet, browser=browser, theme=theme, sprache=sprache, element=element,
        bilder=bilder or [], audio=audio)


@_endpunkt(True)
def befund_setzen(s: Any, wer: str, name: str, status: str) -> dict[str, Any]:
    return dienste.befund_status(s, name, status)


@_endpunkt(True)
def befund_loeschen(s: Any, wer: str, name: str) -> dict[str, Any]:
    if not rechte.ist_admin(s, wer):
        raise FrappePermissionError("Nur für Administratoren.")
    return dienste.befund_loeschen(s, name)


@_endpunkt(True)
def bild_hochladen(s: Any, wer: str, daten: str, typ: str | None = None) -> dict[str, Any]:
    """Nimmt ein Bild als Data-URL oder reines Base64 entgegen."""
    roh, erkannt = dienste.aus_base64(daten)
    return dienste.bild_speichern(roh, typ or erkannt)


@_endpunkt(True)
def audio_hochladen(s: Any, wer: str, daten: str, typ: str | None = None) -> dict[str, Any]:
    """Nimmt eine Sprachaufnahme als Data-URL oder reines Base64 entgegen."""
    roh, erkannt = dienste.aus_base64(daten)
    return dienste.audio_speichern(roh, typ or erkannt)


@_endpunkt()
def bild(s: Any, wer: str, pfad: str) -> Any:
    """Liefert ein Befund-Bild aus (UXM-R12).

    ``/files/<pfad>`` ist fuer Dev-Modus-Bilder nicht nutzbar: dort verlangt
    die Freigabe eine ``File``-Zeile, die es fuer Befund-Bilder nie gibt.
    Dieser Endpunkt prueft stattdessen die Dev-Modus-Rechte und liefert die
    Datei nur aus, wenn der Pfad dem von UNS vergebenen Muster entspricht.
    """
    datei = dienste.bild_pfad(pfad)
    if datei is None:
        return JSONResponse(status_code=404, content={
            "message": "Bild nicht gefunden.", "exception": "DoesNotExistError",
            "exc_type": "DoesNotExistError"})
    from fastapi.responses import FileResponse

    from diakronos_app.files import binary_content_type

    with datei.open("rb") as fh:
        mime = binary_content_type(fh.read(12))
    return FileResponse(datei, media_type=mime or "application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff",
                                 "Cache-Control": "private, no-store"})


@_endpunkt(True)
def bericht_erzeugen(s: Any, wer: str) -> dict[str, Any]:
    """Schreibt den Bericht fuer die KI und liefert die Ablage zurueck."""
    from diakronos_app.devmodus import bericht

    return bericht.erzeugen(s)


@_endpunkt(True)
def aufraeumen(s: Any, wer: str, tage: int = 30) -> dict[str, Any]:
    if not rechte.ist_admin(s, wer):
        raise FrappePermissionError("Nur für Administratoren.")
    return dienste.aufraeumen(s, tage)


def registriere(app) -> bool:
    """Registriert die Endpunkte, wenn der Dev-Modus eingeschaltet ist."""
    if not einstellungen.aktiv():
        return False
    # Die Endpunkte leben in diesem Modul; der Import hat sie bereits per
    # @whitelist registriert. Nichts weiter zu tun — die SPA ruft sie ueber
    # /api/method/diakronos.devmodus.api.<fn>.
    return True
