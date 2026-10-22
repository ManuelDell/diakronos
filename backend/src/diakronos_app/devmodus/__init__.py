"""Dev-Modus (DM1) — ersetzt die Testsuite.

Der Dev-Modus umrahmt das Browserfenster (roter Rahmen) und erlaubt es, ein
beliebiges Element anzuklicken, einen Screenshot zu erzeugen, einen Kommentar
(mit Sprache) zu geben und das Ganze als Befund abzulegen — mit Text, Bild,
Element, URL und dem Fehlerumfeld der letzten 60 Sekunden.

Zugriff: Administratoren und die Rolle ``Tester`` (siehe ``rechte.py``).
Ohne ``DEVMODE_ENABLED`` existieren weder Endpunkte noch Middleware noch
Overlay — normale Nutzer haben dann keinerlei Mehraufwand.
"""

from __future__ import annotations

__all__ = ["api", "bericht", "dienste", "einstellungen", "rechte", "redaktion", "ueberwachung"]
