"""Datei-Ablage hinter EINER Schnittstelle (SPEICHER-1).

    from diakronos_app.speicher import hole_speicher

    speicher = hole_speicher()          # je nach Einstellung lokal oder Nextcloud
    speicher.schreiben("foto.png", b"…")

Welche Ablage laeuft, entscheidet ``settings.speicher_backend``:

``lokal`` (Standard)  ``Lokal`` — Dateisystem unter ``settings.files_dir``,
                      exakt wie vor dieser Karte (byte-gleich, gleicher Ort).
``nextcloud``         ``Nextcloud`` — WebDAV in einem Ordner der Gemeinde-
                      Nextcloud, Zugang ueber App-Passwort.

Ohne die Einstellung aendert sich NICHTS: der Default ist ``lokal``, und
``Lokal`` benutzt dieselben Pfade wie die elf Aufrufer vorher.

Die Umsetzung wird EINMAL je Einstellung gebaut und dann geteilt
(``hole_speicher``). Grund: ``Nextcloud`` haelt einen ``httpx.Client`` mit
Verbindungspool — ein Client je Anfrage waere ein TLS-Handschlag je Datei.

Ein Test, der die Ablage umstellt (z. B. auf ein ``tmp_path``), nimmt
``setze_speicher(...)`` oder setzt ``speicher_backend`` und ruft
``vergiss_speicher()``; die Tests der umgestellten Stellen tun genau das.
"""

from __future__ import annotations

import threading
from typing import Any

from diakronos_app.speicher.basis import (
    AblageFehler,
    Basis,
    NichtErlaubt,
    NichtGefunden,
    Quelle,
    SpeicherNichtErreichbar,
    UngueltigerSchluessel,
)
from diakronos_app.speicher.lokal import Lokal
from diakronos_app.speicher.schluessel import normalisiere

__all__ = [
    "AblageFehler",
    "Basis",
    "Lokal",
    "NichtErlaubt",
    "NichtGefunden",
    "Quelle",
    "SpeicherNichtErreichbar",
    "UngueltigerSchluessel",
    "hole_speicher",
    "schluessel_von_dateiname",
    "setze_speicher",
    "vergiss_speicher",
]

#: Die geteilte Umsetzung. ``None`` = noch nicht gebaut.
_speicher: Basis | None = None
_speicher_schloss = threading.Lock()

#: Kennung der zuletzt gebauten Umsetzung — aendert sich die Einstellung,
#: wird neu gebaut. Ohne diese Spur muesste jeder Aufruf die Settings lesen
#: (billig, aber ein Test, der die Einstellung umstellt, merkte die Aenderung
#: nie).
_kennung: tuple[Any, ...] | None = None


def _aktuelle_kennung() -> tuple[Any, ...]:
    """Was die Umsetzung bestimmt (Backend + die zugehoerigen Adressen)."""
    from diakronos_app.settings import settings

    backend = str(settings.speicher_backend or "lokal").strip().lower()
    if backend == "lokal":
        # ``files_dir`` gehoert zur Kennung: ein Test, der das Verzeichnis
        # umstellt, bekommt automatisch eine neue ``Lokal``-Instanz.
        return ("lokal", str(settings.files_dir))
    return (
        backend,
        str(settings.nextcloud_url),
        str(settings.nextcloud_benutzer),
        str(settings.nextcloud_ordner),
    )


def _bauen() -> Basis:
    from diakronos_app.settings import settings

    backend = str(settings.speicher_backend or "lokal").strip().lower()
    if backend == "lokal":
        return Lokal(settings.files_dir)
    if backend == "nextcloud":
        from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

        zugang = NextcloudZugang(
            settings.nextcloud_url,
            settings.nextcloud_benutzer,
            settings.nextcloud_app_passwort_effektiv,
            settings.nextcloud_ordner,
            timeout=settings.nextcloud_timeout_sekunden,
            transfer_timeout=settings.nextcloud_transfer_timeout_sekunden,
            versuche=settings.nextcloud_versuche,
        )
        return Nextcloud(zugang)
    # Unbekannter Wert: ``settings`` laesst ihn nicht durch (Feldpruefer),
    # also kommt das hier nur bei direkt gesetzten Attributen im Test vor.
    raise AblageFehler(
        f"Unbekanntes Speicher-Backend {backend!r} (erlaubt: lokal, nextcloud)."
    )


def hole_speicher() -> Basis:
    """Die aktive Ablage (geteilt, passend zur aktuellen Einstellung)."""
    global _speicher, _kennung
    kennung = _aktuelle_kennung()
    with _speicher_schloss:
        if _speicher is None or _kennung != kennung:
            if _speicher is not None and hasattr(_speicher, "schliessen"):
                try:
                    _speicher.schliessen()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001 — Aufraeumen darf nie werfen
                    pass
            _speicher = _bauen()
            _kennung = kennung
        return _speicher


def setze_speicher(speicher: Basis | None) -> None:
    """Setzt die Ablage fest (Tests, Umzug) — ``None`` = wieder aus der Einstellung."""
    global _speicher, _kennung
    with _speicher_schloss:
        if _speicher is not None and speicher is not _speicher and hasattr(
            _speicher, "schliessen"
        ):
            try:
                _speicher.schliessen()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
        _speicher = speicher
        _kennung = None if speicher is None else _aktuelle_kennung()


def vergiss_speicher() -> None:
    """Baut die Ablage beim naechsten Zugriff neu (nach einer Umstellung)."""
    setze_speicher(None)


def schluessel_von_dateiname(dateiname: str) -> str:
    """Reiner Dateiname -> Schluessel in der Wurzel der Ablage.

    Bequemlichkeit fuer die Stellen, die in der Datenbank nur einen
    Dateinamen fuehren (Fotos, Formularbilder, Gemeinde-Logo). Pfadanteile
    darin sind ein Fehler und werden abgewiesen (``UngueltigerSchluessel``).
    """
    return normalisiere(str(dateiname or "").strip())
