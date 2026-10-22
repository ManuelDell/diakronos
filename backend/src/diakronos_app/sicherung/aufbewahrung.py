"""BACKUP-1: Aufbewahrung der Sicherungen.

DIE REGEL (Karte BACKUP-1 B2)
-----------------------------
Nach jeder Sicherung werden Sicherungen geloescht, die **aelter als die
Aufbewahrung** sind. Die **neueste erfolgreiche Sicherung wird nie
geloescht** — auch dann nicht, wenn sie selbst schon aelter ist. Ohne diese
Ausnahme waere die Regel bei einem monatelangen Ausfall der automatischen
Sicherung genau das Gegenteil von Sicherheit: nach dem ersten Lauf im Betrieb
waere die letzte vorhandene Kopie weg.

WAS IST EINE SICHERUNG, WENN DIE DATENBANK ES NICHT MEHR WEISS?
--------------------------------------------------------------
Geloescht wird nach **Dateien**, nicht nach Zeilen: eine Zeile in
``sicherungslauf`` ohne Verzeichnis ist ein Rest, ein Verzeichnis ohne Zeile
entsteht bei einem abgebrochenen Lauf. Der Alterstest benutzt deshalb die
**Verzeichnisse** unter ``backup_dir`` und deren Namen (``JJJJ-MM-TT_HHMMSS``);
die zugehoerige Zeile (falls vorhanden) wird mit entfernt. So bleibt kein
Dump liegen, nur weil seine Protokollzeile fehlt.

Ein UNVOLLSTAENDIGES Verzeichnis (Abbruch mitten im Lauf) zaehlt NICHT als
erfolgreiche Sicherung: es traegt keine Pruefsummen-Datei. Es wird nach
Ablauf der Aufbewahrung geloescht, kann aber nie die "neueste erfolgreiche"
Retter-Ausnahme fuer sich beanspruchen.

DAS "NEUESTE ERFOLGREICHE"
--------------------------
Die Zuordnung "erfolgreich" kommt aus der Datenbank (Status ``ok``). Ist die
Zeile weg, gilt ein vollstaendiges Verzeichnis trotzdem als erfolgreich —
lieber eine Sicherung zu viel behalten als die letzte loeschen.

VERWAISTE TEMPORAERE VERZEICHNISSE (BACKUP-1b, M1)
--------------------------------------------------
``dump.sichere`` schreibt in ``.tmp-XXXX`` und raeumt nur im ``except`` auf.
Ein ``SIGKILL``, der OOM-Killer oder ein ``docker compose down`` mitten im
Lauf hinterlaesst den Ordner samt Teil-Dump — und Teil-Dumps enthalten alle
Personendaten. Diese Ordner werden deshalb mit aufgeraeumt, sobald sie
aelter als ``timeout_sekunden`` sind (so lange darf ein Lauf hoechstens
dauern; juenger koennte ein LAUFENDER Lauf sein). Wer aufraeumt, haelt die
Sperre — sie schliesst einen gleichzeitigen Lauf aus.
"""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("diakronos_app.sicherung.aufbewahrung")

#: Verzeichnisname einer Sicherung: ``JJJJ-MM-TT_HHMMSS``.
NAMENSMUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
#: Datei im Sicherungsverzeichnis, an der ein vollstaendiger Lauf erkannt wird.
PRUEFSUMMEN_DATEI = "SHA256SUMS"
#: Fertig-Markierung: erst wenn sie steht, ist der Lauf abgeschlossen.
FERTIG_DATEI = "FERTIG"
#: Praefix der TEMPORAEREN Verzeichnisse eines laufenden Laufs (``dump.py``).
#: Hier doppelt gefuehrt, weil ``dump`` selbst ``aufbewahrung`` importiert.
TEMP_PRAEFIX = ".tmp-"


def ist_sicherungsname(name: str) -> bool:
	"""Sieht der Verzeichnisname nach einer Sicherung aus?"""
	return bool(NAMENSMUSTER.match(name))


def zeitpunkt_aus_name(name: str) -> datetime | None:
	"""``JJJJ-MM-TT_HHMMSS`` -> ``datetime``; sonst ``None``."""
	if not ist_sicherungsname(name):
		return None
	try:
		return datetime.strptime(name, "%Y-%m-%d_%H%M%S")
	except ValueError:  # z. B. 2026-02-31_000000
		return None


def ist_vollstaendig(verzeichnis: Path) -> bool:
	"""Traegt das Verzeichnis Pruefsummen UND die Fertig-Markierung?"""
	try:
		return (verzeichnis / PRUEFSUMMEN_DATEI).is_file() and (
			verzeichnis / FERTIG_DATEI
		).is_file()
	except OSError:
		return False


def sicherungen_im_verzeichnis(basis: Path) -> list[tuple[datetime, Path]]:
	"""Alle Sicherungsverzeichnisse unter ``basis``, **aelteste zuerst**."""
	if not basis.is_dir():
		return []
	gefunden: list[tuple[datetime, Path]] = []
	for eintrag in basis.iterdir():
		try:
			if not eintrag.is_dir():
				continue
		except OSError:
			continue
		zeitpunkt = zeitpunkt_aus_name(eintrag.name)
		if zeitpunkt is not None:
			gefunden.append((zeitpunkt, eintrag))
	gefunden.sort(key=lambda paar: paar[0])
	return gefunden


def zu_loeschen(
	vorhanden: list[tuple[datetime, Path]],
	*,
	jetzt: datetime,
	aufbewahrung_tage: int,
	erfolgreich: set[str] | None = None,
) -> list[Path]:
	"""Welche Sicherungen sind nach der Aufbewahrungsregel zu loeschen?

	``vorhanden`` kommt aus :func:`sicherungen_im_verzeichnis` (aeltere zuerst).
	``erfolgreich`` sind die Namen mit Status ``ok`` aus der Datenbank; ein
	Name, der dort NICHT als fehlgeschlagen gefuehrt wird, gilt als
	erfolgreich (siehe Modulkopf). ``erfolgreich=None`` heisst: keine Auskunft —
	dann zaehlt nur die Vollstaendigkeit des Verzeichnisses.

	Rueckgabe: die zu loeschenden Verzeichnisse, **aelteste zuerst**.
	"""
	if aufbewahrung_tage < 1:
		# Die Aufbewahrung ist Pflicht mit Minimum 1; ein Wert darunter kann
		# nur aus einer Handaenderung an der DB stammen. Dann wird NICHTS
		# geloescht — fail safe statt "alles weg".
		logger.warning(
			"Ungueltige Aufbewahrung (%s Tage) — es wird nichts geloescht.",
			aufbewahrung_tage,
		)
		return []

	grenze = jetzt - timedelta(days=aufbewahrung_tage)

	def erfolgreich_und_vollstaendig(zeitpunkt: datetime, pfad: Path) -> bool:
		if not ist_vollstaendig(pfad):
			return False
		if erfolgreich is None:
			return True
		return pfad.name in erfolgreich

	# Die neueste ERFOLGREICHE Sicherung ist geschuetzt — unabhaengig vom Alter.
	geschuetzt: Path | None = None
	for zeitpunkt, pfad in reversed(vorhanden):
		if erfolgreich_und_vollstaendig(zeitpunkt, pfad):
			geschuetzt = pfad
			break

	return [
		pfad
		for zeitpunkt, pfad in vorhanden
		if zeitpunkt < grenze and (geschuetzt is None or pfad != geschuetzt)
	]


def entferne(pfad: Path) -> bool:
	"""Loescht ein Sicherungsverzeichnis samt Inhalt (rekursiv, nur dieses)."""
	try:
		shutil.rmtree(pfad)
		return True
	except OSError as fehler:
		logger.warning("Sicherung %s konnte nicht entfernt werden: %s", pfad.name, fehler)
		return False


def verwaiste_temp_entfernen(
	basis: Path,
	*,
	jetzt: datetime,
	timeout_sekunden: int,
) -> list[str]:
	"""Reste abgestuerzter Laeufe loeschen. Rueckgabe: Namen der Ordner (M1).

	Betroffen sind nur Verzeichnisse mit dem Praefix ``.tmp-`` direkt unter
	``basis``, deren **Aenderungszeit** aelter als ``timeout_sekunden`` ist.
	Der Zeitstempel des Ordners reicht: ``schreibe_dump`` legt die Datei
	zuletzt an, und der Dump ist der letzte Schreibvorgang eines Laufs, der
	laenger dauert als das Archiv. Juengere Ordner bleiben stehen — sie
	koennen zu einem Lauf gehoeren, der gerade laeuft (Aufrufer haelt die
	Sperre, hier wird trotzdem nicht geraten).
	"""
	if not basis.is_dir():
		return []
	# Ohne Angabe ist die Hoechstdauer die Standardeinstellung des Betriebs.
	frist = int(timeout_sekunden or 1800)
	grenze = jetzt.timestamp() - frist
	entfernt: list[str] = []
	for eintrag in basis.iterdir():
		if not eintrag.name.startswith(TEMP_PRAEFIX):
			continue
		try:
			if not eintrag.is_dir():
				continue
			alter = eintrag.stat().st_mtime
		except OSError:
			continue
		if alter >= grenze:
			continue
		if entferne(eintrag):
			entfernt.append(eintrag.name)
	if entfernt:
		logger.info(
			"Verwaiste Reste abgebrochener Laeufe entfernt: %s", ", ".join(entfernt)
		)
	return entfernt


def aufraeumen(
	basis: Path,
	*,
	jetzt: datetime,
	aufbewahrung_tage: int,
	erfolgreich: set[str] | None = None,
	timeout_sekunden: int = 0,
) -> list[str]:
	"""Aufbewahrung anwenden. Rueckgabe: Namen der geloeschten Sicherungen.

	``timeout_sekunden`` ist die Hoechstdauer eines Laufs
	(``backup_timeout_sekunden``). Verwaiste ``.tmp-*``-Ordner, die aelter
	sind, werden zuerst entfernt (M1) — sie sind keine Sicherung, sondern
	Reste eines abgestuerzten Laufs mit Personendaten. Der Aufrufer haelt
	die Sperre, deshalb kann kein laufender Lauf betroffen sein.
	"""
	verwaiste_temp_entfernen(basis, jetzt=jetzt, timeout_sekunden=timeout_sekunden)
	alte = zu_loeschen(
		sicherungen_im_verzeichnis(basis),
		jetzt=jetzt,
		aufbewahrung_tage=aufbewahrung_tage,
		erfolgreich=erfolgreich,
	)
	entfernt: list[str] = []
	for pfad in alte:
		if entferne(pfad):
			entfernt.append(pfad.name)
	if entfernt:
		logger.info("Aufbewahrung: %s alte Sicherung(en) entfernt.", len(entfernt))
	return entfernt
