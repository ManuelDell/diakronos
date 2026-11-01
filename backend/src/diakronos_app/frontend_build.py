"""ON-0b (F6) — Startpruefung: liegt der Frontend-Build?

Aufruf im Container-Entrypoint: ``python -m diakronos_app.frontend_build``.
VOR dem eigentlichen Kommando, wie die Anmelde- und die Erstinstallations-
Pruefung.

WARUM
-----
Ohne Build liefert `spa.py` für die Server-Seiten (Anmeldung, Passwort setzen,
Fehlerseiten) nur den Rumpf: die beiden Stylesheets unter
`/diakonos/assets/…` gibt es nicht, die Seite erscheint ungestaltet in der
Browser-Schrift. Bisher schwieg der Start dazu; gefunden wurde es erst, als
jemand die Seite ansah.

WAS
---
Eine WARNUNG ins Log — kein Abbruch. Ein Betrieb ohne Gestaltung ist
unschön, aber bedienbar (die Anmeldung funktioniert); ein Startverbot waere
eine härtere Strafe als der Befund. Der Hinweis nennt die Abhilfe.

Der Exitcode ist IMMER 0, damit der Start nie an dieser Pruefung scheitert.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level="INFO")
logger = logging.getLogger("diakronos_app.frontend_build")


def pruefe() -> bool:
    """True = Build vollständig da. False = Warnung geloggt."""
    from diakronos_app import spa

    if spa.SPA_DIST is None:
        logger.warning(spa.FRONTEND_FEHLT_MELDUNG)
        return False
    fehlend = [
        name
        for name in (spa.SEITENRAHMEN_TOKENS, spa.SEITENRAHMEN_STIL)
        if not (spa.SPA_DIST / name).is_file()
    ]
    if fehlend:
        logger.warning(
            "%s — es fehlen: %s (%s)",
            spa.FRONTEND_FEHLT_MELDUNG,
            ", ".join(fehlend),
            spa.SPA_DIST,
        )
        return False
    logger.info("Frontend-Build: Server-Stylesheets vorhanden (%s).", spa.SPA_DIST)
    return True


def main() -> int:
    pruefe()
    return 0


if __name__ == "__main__":  # pragma: no cover — Entrypoint-Aufruf
    sys.exit(main())
