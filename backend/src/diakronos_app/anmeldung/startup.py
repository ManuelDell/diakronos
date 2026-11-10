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
import os
import sys

logging.basicConfig(level="INFO")
logger = logging.getLogger("diakronos_app.anmeldung.startup")


def main() -> int:
    """Prueft die Konfiguration. Rueckgabe 0 = ok, 1 = Fehlkonfiguration."""
    # SEC-DEF1: konfigurationsschutz importiert die Settings NICHT. Die
    # Pruefung muss VOR dem Import von `konfiguration` laufen — der zieht
    # `settings` (Modul-Ebene `get_settings()`), und dessen Modellpruefung
    # wuerde sonst mit einem pydantic-Traceback abbrechen, bevor die deutsche
    # Meldung unten erscheint.
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    # SEC-DEF1 ZUERST: ohne tragfaehigen Schluessel ist jede Signatur
    # faelschbar. Die Settings pruefen das schon beim Anlegen
    # (Modellpruefung); hier wird daraus eine lesbare deutsche Meldung mit
    # Exit-Code 1 statt eines pydantic-Validierungsfehlers.
    probleme = unsichere_standardwerte(
        os.environ.get("APP_ENV", "development"),
        os.environ.get("SECRET_KEY", ""),
        os.environ.get("DATABASE_URL", ""),
    )
    if probleme:
        logger.error(
            "Konfiguration unsicher — Start verweigert: %s", " ".join(probleme)
        )
        return 1

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
