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
* :mod:`cloud` — SPEICHER-2: die fertige Sicherung ueber die Ablage-
  Schnittstelle in die Nextcloud legen, Aufbewahrung auf der Nextcloud-Seite,
  lokal nur die juengste Kopie behalten
* :mod:`wiederherstellen` — SPEICHER-2: eine Sicherung aus der Nextcloud
  zuerst lokal bereitstellen (``python -m
  diakronos_app.sicherung.wiederherstellen``)
"""

from __future__ import annotations

__all__ = [
	"aufbewahrung",
	"cloud",
	"dump",
	"einstellungen",
	"lauf",
	"sperre",
	"wiederherstellen",
]
