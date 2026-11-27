"""ASVS2-4: Geheimnisse aus Adressen im Zugriffsprotokoll maskieren.

uvicorn schreibt jede Anfrage als ``"GET /pfad?abfrage HTTP/1.1"`` ins Log.
Gast- und Registrierungslinks tragen ihr Zugangs-Token als ``?token=…``, die
OIDC-Rueckkehr ``?code=…&state=…``. Diese Werte gehoeren nicht ins Log (ASVS:
keine sensiblen Daten in protokollierten Adressen). Der Filter ersetzt die
WERTE solcher Parameter durch ``***`` — Pfad und Parametername bleiben sichtbar,
damit das Log weiter zur Fehlersuche taugt.
"""
from __future__ import annotations

import logging
import re

#: Parameternamen, deren Werte nie ins Log gehoeren (Kleinschreibung).
GEHEIME_PARAMETER = ("token", "code", "state", "key", "schluessel", "passwort",
                     "password", "sid", "csrf", "secret", "access_token", "refresh_token")

_MUSTER = re.compile(
    r"([?&](?:" + "|".join(re.escape(n) for n in GEHEIME_PARAMETER) + r")=)[^&#\s\"]*",
    re.IGNORECASE,
)


def maskiere(adresse: str) -> str:
    """Werte geheimer Abfrage-Parameter durch ``***`` ersetzen."""
    return _MUSTER.sub(r"\1***", adresse)


class GeheimnisFilter(logging.Filter):
    """Maskiert Abfrage-Geheimnisse in uvicorn-Zugriffszeilen.

    uvicorn uebergibt die Zeile als ``record.args`` (Client, Methode, Pfad mit
    Abfrage, HTTP-Version, Status). Gefiltert wird jedes Zeichenketten-Argument
    und vorsichtshalber auch ``record.msg`` — der Filter laesst JEDE Zeile durch
    (Rueckgabe True), er veraendert nur ihren Inhalt.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(maskiere(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = maskiere(record.msg)
        return True


def einschalten() -> None:
    """Filter an den uvicorn-Zugriffslogger haengen (idempotent)."""
    log = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, GeheimnisFilter) for f in log.filters):
        log.addFilter(GeheimnisFilter())
