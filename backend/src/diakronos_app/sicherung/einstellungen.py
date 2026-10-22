"""BACKUP-1: die Einstellungen der Datensicherung (Single-Zeile in der DB).

Der geltende Wert steht in der Datenbank, **nicht** in der ``.env``: Manuel
hat entschieden, dass die Aufbewahrung in der Oberflaeche einstellbar ist
(„automatische Loeschung soll manuell eingestellt werden, wie lange es behalten
wird"). Die ``.env``-Werte (``BACKUP_*``) sind nur die **Erstbelegung** der
Zeile beim ersten Lesen — danach gilt, was der Administrator gespeichert hat.

Geprueft wird hier UND im Endpunkt, und zwar dieselbe Funktion: eine
Schranke nur im Endpunkt liesse den Scheduler mit einem unmoeglichen Wert
laufen, eine nur im Scheduler liesse die Oberflaeche Unsinn speichern.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from diakronos_app.models.sicherung import (
	MINIMUM_AUFBEWAHRUNG_TAGE,
	SICHERUNGSEINSTELLUNGEN_NAME,
	STANDARD_AUFBEWAHRUNG_TAGE,
	STANDARD_UHRZEIT,
	Sicherungseinstellungen,
)
from diakronos_app.settings import settings

#: ``HH:MM`` in 24-Stunden-Schreibweise (00:00 bis 23:59).
UHRZEIT_MUSTER = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class EinstellungFehler(ValueError):
	"""Ungueltige Einstellung — der Text ist die Meldung fuer die Oberflaeche."""


def jetzt_ortszeit() -> datetime:
	"""Aktuelle Ortszeit in ``settings.calendar_timezone`` (naiv, ohne tz).

	Die Datenbank traegt Zeitstempel ohne Zeitzone (wie alle Frappe-Modelle);
	"03:00" in der Oberflaeche ist Ortszeit, nicht UTC. Deshalb tragen ALLE
	Zeitpunkte der Sicherung (Name, beginn, ende) Ortszeit — manuelle und
	automatische Läufe durften sonst um die Zeitzonen-Differenz auseinander-
	liegen (im Teststack gefunden: manuelle Läufe in UTC, Scheduler-Laeufe in
	Ortszeit).
	"""
	from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

	try:
		zone = ZoneInfo(settings.calendar_timezone)
	except (ValueError, ZoneInfoNotFoundError):
		zone = ZoneInfo("UTC")
	return datetime.now(zone).replace(tzinfo=None)


def pruefe_uhrzeit(wert: str) -> str:
	"""Uhrzeit auf ``HH:MM`` normalisieren oder :class:`EinstellungFehler`."""
	text = str(wert or "").strip()
	if not UHRZEIT_MUSTER.match(text):
		raise EinstellungFehler(
			"Bitte die Uhrzeit als HH:MM angeben, zum Beispiel 03:00."
		)
	return text


def pruefe_aufbewahrung(wert: object) -> int:
	"""Aufbewahrung in Tagen pruefen (Pflicht, ganze Zahl, Minimum 1)."""
	if wert is None or (isinstance(wert, str) and not wert.strip()):
		raise EinstellungFehler("Bitte die Aufbewahrung in Tagen angeben.")
	try:
		tage = int(str(wert).strip())
	except (TypeError, ValueError):
		raise EinstellungFehler("Die Aufbewahrung muss eine ganze Zahl in Tagen sein.") from None
	if tage < MINIMUM_AUFBEWAHRUNG_TAGE:
		raise EinstellungFehler(
			f"Die Aufbewahrung muss mindestens {MINIMUM_AUFBEWAHRUNG_TAGE} Tag betragen."
		)
	# Obergrenze: 10 Jahre. Kein fachlicher Wert, sondern eine Bremse gegen
	# Zahlendreher (30000 statt 300) — die Dateien wuerden den Datentraeger
	# fuellen, und niemand merkt es vorher.
	if tage > 3650:
		raise EinstellungFehler("Die Aufbewahrung darf hoechstens 3650 Tage betragen.")
	return tage


def uhrzeit_teile(wert: str) -> tuple[int, int]:
	"""``"03:00"`` -> ``(3, 0)``; ungueltig -> Standard (fail safe)."""
	text = str(wert or "").strip()
	if not UHRZEIT_MUSTER.match(text):
		text = STANDARD_UHRZEIT
	stunde, minute = text.split(":")
	return int(stunde), int(minute)


def holen_oder_anlegen(session: Session, *, jetzt: datetime | None = None,
                       benutzer: str | None = None) -> Sicherungseinstellungen:
	"""Die Einstellungszeile; beim ersten Aufruf aus ``settings`` angelegt.

	Die Erstbelegung kommt aus ``BACKUP_AUTOMATISCH`` /
	``BACKUP_UHRZEIT`` / ``BACKUP_AUFBEWAHRUNG_TAGE``. Die Migration legt
	bewusst keine Zeile an, damit diese Werte greifen (siehe
	``alembic/versions/bk1_sicherung.py``).
	"""
	zeile = session.get(Sicherungseinstellungen, SICHERUNGSEINSTELLUNGEN_NAME)
	if zeile is not None:
		return zeile

	zeit = jetzt or datetime.now()
	try:
		tage = pruefe_aufbewahrung(settings.backup_aufbewahrung_tage)
	except EinstellungFehler:
		tage = STANDARD_AUFBEWAHRUNG_TAGE
	try:
		uhrzeit = pruefe_uhrzeit(settings.backup_uhrzeit)
	except EinstellungFehler:
		uhrzeit = STANDARD_UHRZEIT

	zeile = Sicherungseinstellungen(
		name=SICHERUNGSEINSTELLUNGEN_NAME,
		automatisch=bool(settings.backup_automatisch),
		uhrzeit=uhrzeit,
		aufbewahrung_tage=tage,
		created=zeit,
		modified=zeit,
		created_by=benutzer,
		modified_by=benutzer,
	)
	session.add(zeile)
	session.commit()
	return zeile


def als_dict(zeile: Sicherungseinstellungen) -> dict:
	"""Darstellung fuer die Oberflaeche (deutsche Feldnamen in snake_case)."""
	return {
		"automatisch": bool(zeile.automatisch),
		"uhrzeit": zeile.uhrzeit,
		"aufbewahrung_tage": int(zeile.aufbewahrung_tage),
	}


def speichern(session: Session, *, automatisch: object, uhrzeit: object,
              aufbewahrung_tage: object, benutzer: str,
              jetzt: datetime | None = None) -> Sicherungseinstellungen:
	"""Einstellungen pruefen und in EINER Transaktion schreiben."""
	if not isinstance(automatisch, bool):
		raise EinstellungFehler("Bitte angeben, ob automatisch gesichert wird.")
	geprueft_uhrzeit = pruefe_uhrzeit(str(uhrzeit))
	gepruefte_tage = pruefe_aufbewahrung(aufbewahrung_tage)

	zeile = holen_oder_anlegen(session, jetzt=jetzt, benutzer=benutzer)
	zeile.automatisch = automatisch
	zeile.uhrzeit = geprueft_uhrzeit
	zeile.aufbewahrung_tage = gepruefte_tage
	zeile.modified = jetzt or datetime.now()
	zeile.modified_by = benutzer
	session.commit()
	return zeile
