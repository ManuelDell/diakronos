"""Startpruefung der Anmeldung (SEC1) — fuer den Container-Entrypoint.

Wird per ``python -m diakronos_app.anmeldung.startup`` im Entrypoint VOR dem
eigentlichen Kommando aufgerufen (wie die Erstinstallation). Eine AKTIVIERTE,
aber unvollstaendig konfigurierte Anmeldung ist gefaehrlicher als eine
abgeschaltete: ohne den Issuer wuerde jeder Login ins Leere laufen, ohne
Trusted-IPs waeren die Forward-Auth-Kopfzeilen wirkungslos. Deshalb bricht
dieses Modul bei Fehlkonfiguration mit Exit-Code 1 ab (Start verweigern),
sonst mit 0.

Diese Pruefung ist NICHT bei Import von `main` aktiv — Tests importieren `main`
mit eigenen Flags.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level="INFO")
logger = logging.getLogger("diakronos_app.anmeldung.startup")


def main() -> int:
    """Prueft die Konfiguration. Rueckgabe 0 = ok, 1 = Fehlkonfiguration."""
    from diakronos_app.anmeldung.konfiguration import (
        KonfigurationsFehler,
        pruefe_konfiguration,
    )

    try:
        warnungen = pruefe_konfiguration()
    except KonfigurationsFehler as exc:
        logger.error("Anmeldung fehlkonfiguriert — Start verweigert: %s", exc)
        return 1
    for w in warnungen:
        logger.info("Anmeldung: %s", w)
    logger.info("Anmeldung: Konfiguration ok.")
    return 0


if __name__ == "__main__":  # pragma: no cover — Entrypoint-Aufruf
    sys.exit(main())
