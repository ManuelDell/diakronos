"""BACKUP-1: eigene Datensicherung (Dump + Dateiablage, einstellbare Aufbewahrung).

Aufbau:

* :mod:`einstellungen` — die Single-Zeile (automatisch an/aus, Uhrzeit,
  Aufbewahrung) und ihre Pruefung
* :mod:`dump` — Dump ``pg_dump -Fc``, Dateiarchiv, Pruefsummen, atomares
  Umbenennen
* :mod:`aufbewahrung` — welche alten Sicherungen wegfallen (die neueste
  erfolgreiche nie)
* :mod:`sperre` — Sperre gegen zwei gleichzeitige Laeufe, Aufraeumen
  abgebrochener Vorgaenger
* :mod:`lauf` — EIN kompletter Lauf inkl. Benachrichtigung an die System
  Manager
"""

from __future__ import annotations

__all__ = ["aufbewahrung", "dump", "einstellungen", "lauf", "sperre"]
