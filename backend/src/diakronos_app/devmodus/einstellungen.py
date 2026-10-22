"""Schalter und Grenzen des Dev-Modus (DM1).

Der globale Schalter ist absichtlich ein eigener Einstellungswert (Default AUS):
auf einer Installation ohne Entwicklungsbetrieb darf kein Endpunkt, keine
Middleware und kein Overlay existieren. Er wird EINMAL je Prozess gelesen —
der Dev-Modus ist damit auch dann vollstaendig weg, wenn jemand den Wert zur
Laufzeit ueberschreibt.
"""

from __future__ import annotations

import os

from diakronos_app.settings import settings

#: Anzeige des Tastenkuerzels (nur Anzeige) und die zu pruefende Kombination.
#: Karte DM1: Strg+Shift+F ("F" wie Fehler) — auch auf macOS Ctrl, nicht Cmd.
KUERZEL_ANZEIGE = os.environ.get("DEVMODE_KUERZEL_ANZEIGE") or "Strg+Shift+F"

#: Erlaubte Bildtypen fuer Befund-Bilder (Inhalt wird geprueft, nicht nur der
#: gemeldete Typ) und ihre Dateiendung.
BILD_TYPEN: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

#: Erlaubte Audiotypen (Sprachaufnahme, MediaRecorder) und ihre Endung.
AUDIO_TYPEN: dict[str, str] = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
}

#: Groessenlimit je Befund-Bild (10 MB) / je Audio (25 MB).
MAX_BILD_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_BILDER = 8
MAX_BEFUND_TEXT = 8000

#: Fehler der letzten N Sekunden werden einem Befund automatisch beigelegt
#: (Karte: "Fehlerumfeld der letzten 60 s").
FENSTER_SEKUNDEN = 60

#: Anfragen ab dieser Dauer gelten als langsam und werden erfasst.
LANGSAM_MS = 1000

#: Kappe fuer gespeicherte Antwort-/Log-Texte (Geheimnisschutz ist davon
#: unabhaengig: redaktion.py laeuft IMMER davor).
MAX_TEXT = 4000
MAX_TRACEBACK = 8000
MAX_PFAD = 500

#: Gueltige Werte fuer Art/Wichtigkeit/Status eines Befunds.
ARTEN = ("fehler", "design", "wunsch", "frage")
WICHTIGKEITEN = ("niedrig", "mittel", "hoch")
STATUS_GUELTIG = ("offen", "an_claude", "behoben", "verworfen")

#: Art der Ereignisse im Fehlerumfeld, die als echte Fehler gelten.
FEHLER_ARTEN = ("http_4xx", "http_5xx", "exception", "browser", "promise")

#: Sprech-zu-Text (optional). Ohne STT_URL gibt es serverseitig keine
#: Transkription — der Browser-Dialog bietet dann die Web-Speech-API an.
STT_URL = (os.environ.get("STT_URL") or "").strip()
STT_MODEL = (os.environ.get("STT_MODEL") or "whisper-1").strip()
STT_API_KEY = (os.environ.get("STT_API_KEY") or "").strip()
STT_SPRACHE = (os.environ.get("STT_SPRACHE") or "de").strip()


def _env_wahr(name: str) -> bool:
    wert = (os.environ.get(name) or "").strip().lower()
    return wert in {"1", "true", "yes", "on", "ja"}


def aktiv() -> bool:
    """Ist der Dev-Modus eingeschaltet?

    Gelesen wird die Einstellung (Compose/`.env`); zusaetzlich akzeptiert der
    Prozess die Umgebungsvariable unmittelbar, damit Tests den Schalter ohne
    Neustart setzen koennen.
    """
    if _env_wahr("DEVMODE_ENABLED"):
        return True
    return bool(getattr(settings, "devmode_enabled", False))


def stt_verfuegbar() -> bool:
    """Ist ein serverseitiger Transkriptions-Endpunkt konfiguriert?"""
    return bool(STT_URL)
