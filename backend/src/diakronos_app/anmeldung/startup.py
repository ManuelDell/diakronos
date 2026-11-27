"""Startpruefung der Anmeldung (SEC1) — fuer den Container-Entrypoint.

Wird per ``python -m diakronos_app.anmeldung.startup`` im Entrypoint VOR dem
eigentlichen Kommando aufgerufen (wie die Erstinstallation). Eine AKTIVIERTE,
aber unvollstaendig konfigurierte Anmeldung ist gefaehrlicher als eine
abgeschaltete: ohne den Issuer wuerde jeder Login ins Leere laufen, ohne
Trusted-IPs waeren die Forward-Auth-Kopfzeilen wirkungslos. Deshalb bricht
dieses Modul bei Fehlkonfiguration mit Exit-Code 1 ab (Start verweigern),
sonst mit 0.

Diese Pruefung ist NICHT bei Import von `main` aktiv — Tests importieren `main`
mit eigenen Flags. SEC-DEF2: Der Betriebsmodus ist der STANDARD — nur ein
ausdruecklich gesetztes `APP_ENV=development|test|dev` schaltet die
Standardwert-Pruefung ab.
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level="INFO")
logger = logging.getLogger("diakronos_app.anmeldung.startup")


def _wahr(roh: str) -> bool:
    """Liest einen Ja/Nein-Schalter wie `settings` (pydantic bool)."""
    return str(roh or "").strip().lower() in {"1", "true", "yes", "on", "t", "y"}


def _demo_schalter_warnen(app_env: str, environ) -> None:
    """SEC-DEF2: eingeschaltete Demo-/Diagnose-Schalter im Betrieb melden.

    Nur eine MELDUNG, kein Startverbot — siehe
    `konfigurationsschutz.demo_schalter_im_betrieb`. Die Werte werden hier
    roh aus der Umgebung gelesen (kein `settings`-Import: der wuerde bei
    unsicheren Standardwerten mit pydantic-Traceback abbrechen, bevor die
    deutsche Meldung oben erscheint).
    """
    from diakronos_app.konfigurationsschutz import demo_schalter_im_betrieb

    for hinweis in demo_schalter_im_betrieb(
        app_env,
        _wahr(environ.get("DEVMODE_ENABLED", "")),
        _wahr(environ.get("SEC_DOKU_OEFFENTLICH", "")),
    ):
        logger.warning("%s", hinweis)


def main() -> int:
    """Prueft die Konfiguration. Rueckgabe 0 = ok, 1 = Fehlkonfiguration."""
    # SEC-DEF1: konfigurationsschutz importiert die Settings NICHT. Die
    # Pruefung muss VOR dem Import von `konfiguration` laufen — der zieht
    # `settings` (Modul-Ebene `get_settings()`), und dessen Modellpruefung
    # wuerde sonst mit einem pydantic-Traceback abbrechen, bevor die deutsche
    # Meldung unten erscheint.
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    # SEC-DEF2: Fehlt APP_ENV, gilt BETRIEB. Ein leerer Wert zaehlt wie ein
    # fehlender (Compose gibt bei `APP_ENV=` einen leeren String durch) — sonst
    # waere ein leeres `APP_ENV=` eine stille Freigabe.
    app_env = os.environ.get("APP_ENV", "")
    if not str(app_env).strip():
        app_env = "production"

    # SEC-DEF1 ZUERST: ohne tragfaehigen Schluessel ist jede Signatur
    # faelschbar. Die Settings pruefen das schon beim Anlegen
    # (Modellpruefung); hier wird daraus eine lesbare deutsche Meldung mit
    # Exit-Code 1 statt eines pydantic-Validierungsfehlers.
    #
    # SEC-DEF2: KEIN Default hier. Fehlt APP_ENV (oder ist es leer), ist das
    # Betrieb — die Ausnahme gilt nur bei AUSDRUECKLICH gesetztem
    # development/test/dev (`konfigurationsschutz.ist_entwicklung`). Vorher
    # stand hier „development“ als Rueckfall; damit lief die Pruefung in jeder
    # Standardinstallation ins Leere.
    probleme = unsichere_standardwerte(
        app_env,
        os.environ.get("SECRET_KEY", ""),
        os.environ.get("DATABASE_URL", ""),
    )
    if probleme:
        logger.error(
            "Konfiguration unsicher — Start verweigert: %s", " ".join(probleme)
        )
        return 1

    _demo_schalter_warnen(app_env, os.environ)

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
