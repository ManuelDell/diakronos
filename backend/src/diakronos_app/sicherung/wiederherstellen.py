"""SPEICHER-2: eine Sicherung aus der Ablage LOKAL holen (fuer die Wiederherstellung).

Warum es das gibt
-----------------
Bis BACKUP-1 war die Wiederherstellung ein reiner Kommandozeilen-Vorgang:
Sicherungsverzeichnis suchen, ``pg_restore``/Dateien zurueckholen
(BETRIEBSANLEITUNG). Mit SPEICHER-2 liegt die Sicherung im Nextcloud-Betrieb
aber nicht mehr auf der Platte des Servers — der erste Schritt jeder
Wiederherstellung ist damit zwangslaeufig „hol sie herunter“.

    python -m diakronos_app.sicherung.wiederherstellen --liste
    python -m diakronos_app.sicherung.wiederherstellen 2026-11-18_030000

Was das Werkzeug tut
--------------------
* ``--liste`` nennt die Sicherungen in der Ablage (Name, Groesse, Zeitpunkt) —
  nur, was zur Wiederherstellung gebraucht wird.
* Ohne Namen wird die JUENGSTE Sicherung geholt.
* Jede Datei wird blockweise (``BLOCKGROESSE``) in
  ``<BACKUP_DIR>/<name>/`` geschrieben, danach werden Groesse UND SHA-256
  gegen ``SHA256SUMS`` geprueft — eine halbe Sicherung ist keine Sicherung.
* Es wird NICHTS eingespielt: kein ``pg_restore``, kein Ueberschreiben von
  Dateien. Das bleibt der dokumentierte Vorgang von Hand (BETRIEBSANLEITUNG),
  weil ein Einspielen in eine laufende Datenbank eine Entscheidung des
  Betreibers ist und nicht die eines Hilfsskripts.

Im Lokal-Modus ist der Befehl still erledigt: die Sicherung liegt schon dort.

Aufruf im Container::

    docker compose exec app python -m diakronos_app.sicherung.wiederherstellen --liste
    docker compose exec app python -m diakronos_app.sicherung.wiederherstellen <name>

Exit-Codes: 0 = geholt und geprueft, 1 = Fehler (Meldung im Klartext),
2 = Aufruf-/Einstellungsfehler.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from diakronos_app.sicherung import aufbewahrung, cloud, dump

__all__ = ["hole_lokal", "main"]


def hole_lokal(name: str, *, ziel: Path | None = None) -> Path:
	"""Sicherung ``name`` aus der Ablage nach ``<BACKUP_DIR>/<name>`` holen.

	Rueckgabe: das lokale Verzeichnis. Vorhandene Dateien werden NICHT
	ueberschrieben, wenn sie schon mit Groesse und Pruefsumme stimmen — der
	Vorgang ist damit wiederholbar (Abbruch nach 900 MB kostet beim zweiten
	Lauf nur den Rest).

	``WiederherstellungsFehler`` bei allem, was nicht vollstaendig wird; die
	lokale Kopie bleibt dann als ``.teil``-Datei NICHT liegen.
	"""
	if not aufbewahrung.ist_sicherungsname(name):
		raise WiederherstellungsFehler(
			"Der Name muss die Form JJJJ-MM-TT_HHMMSS haben."
		)
	ablage = cloud._ablage()
	if ablage.name != "nextcloud":
		raise WiederherstellungsFehler(
			"Die Sicherungen liegen lokal — es muss nichts geholt werden."
		)
	ordnung = []
	try:
		ordnung = ablage.auflisten(cloud.schluessel(name))
	except Exception as fehler:  # noqa: BLE001
		raise WiederherstellungsFehler(
			f"Die Ablage ist nicht lesbar ({type(fehler).__name__})."
		) from None
	if not ordnung:
		raise WiederherstellungsFehler(f"Die Sicherung {name} gibt es nicht.")

	zield = Path(ziel) if ziel is not None else dump.ziel_basis() / name
	zield.mkdir(mode=dump.VERZEICHNIS_MODUS, parents=True, exist_ok=True)
	summen_text = None
	# ``FERTIG`` ZULETZT (Review-Befund 7): bricht das Holen ab, sieht der
	# lokale Ordner aus wie ein abgebrochener Lauf — und nicht wie eine
	# vollstaendige Sicherung, die nur zufaellig unvollstaendig ist.
	ordnung.sort(key=lambda schluessel: (
		schluessel.rsplit("/", 1)[-1] == dump.FERTIG_NAME,
		schluessel,
	))
	for schluessel in ordnung:
		dateiname = schluessel.rsplit("/", 1)[-1]
		if not dateiname:
			continue
		try:
			summen_text = _hole_datei(ablage, schluessel, zield / dateiname, summen_text)
		except Exception as fehler:  # noqa: BLE001 — jeder Fehler ist ein Abbruch
			raise WiederherstellungsFehler(
				f"Die Datei {dateiname} konnte nicht geholt werden "
				f"({type(fehler).__name__})."
			) from None
	_pruefe_pruefsummen(zield)
	return zield


def _hole_datei(ablage, schluessel: str, ziel: Path, summen_text: str | None) -> str | None:
	"""Eine Datei holen; gibt den gelesenen ``SHA256SUMS``-Text zurueck (falls sie es ist)."""
	erwartet = ablage.groesse(schluessel)
	if ziel.is_file() and erwartet is not None and ziel.stat().st_size == erwartet:
		return summen_text
	teil = ziel.with_name(ziel.name + ".teil")
	try:
		with ablage.oeffnen(schluessel) as quelle, open(teil, "wb") as datei:
			for block in quelle.strom():
				datei.write(block)
	except Exception:
		teil.unlink(missing_ok=True)
		raise
	teil.chmod(dump.DATEI_MODUS)
	teil.replace(ziel)
	if ziel.name == dump.PRUEFSUMMEN_NAME:
		return ziel.read_text(encoding="utf-8")
	return summen_text


def _pruefe_pruefsummen(verzeichnis: Path) -> None:
	"""Groesse und SHA-256 jeder gelisteten Datei gegen ``SHA256SUMS`` pruefen.

	Fehlt die Pruefsummen-Datei, wird abgebrochen: eine Sicherung ohne
	Pruefsummen ist nicht als vollstaendig belegt (so zaehlt sie auch die
	Aufbewahrung nicht als erfolgreich).
	"""
	summen = dump.lese_pruefsummen(verzeichnis)
	if not summen:
		raise WiederherstellungsFehler(
			"Die Sicherung traegt keine Pruefsummen — sie ist unvollstaendig."
		)
	for dateiname, erwartet in summen.items():
		datei = verzeichnis / dateiname
		if not datei.is_file():
			raise WiederherstellungsFehler(f"Die Datei {dateiname} fehlt.")
		summe = hashlib.sha256()
		with open(datei, "rb") as offen:
			for block in iter(lambda: offen.read(1024 * 1024), b""):
				summe.update(block)
		if summe.hexdigest() != erwartet:
			raise WiederherstellungsFehler(
				f"Die Datei {dateiname} ist beschaedigt (Pruefsumme weicht ab)."
			)


class WiederherstellungsFehler(RuntimeError):
	"""Die Sicherung liess sich nicht (vollstaendig) lokal bereitstellen."""


def main(argv: list[str] | None = None) -> int:
	"""CLI-Einstieg (``python -m diakronos_app.sicherung.wiederherstellen``)."""
	parser = argparse.ArgumentParser(
		prog="python -m diakronos_app.sicherung.wiederherstellen",
		description=(
			"Eine Sicherung aus der Nextcloud lokal bereitstellen "
			"(es wird NICHTS eingespielt)."
		),
	)
	parser.add_argument("name", nargs="?", default=None,
	                    help="Sicherung (JJJJ-MM-TT_HHMMSS). Ohne Angabe: die juengste.")
	parser.add_argument("--liste", action="store_true",
	                    help="Nur die vorhandenen Sicherungen anzeigen.")
	args = parser.parse_args(argv)

	if args.liste:
		vorhanden = cloud.sicherungen_auflisten() if cloud.ist_aktiv() else []
		if not vorhanden:
			print("Keine Sicherung in der Ablage gefunden.")
			return 0
		for name, groesse, zeitpunkt, voll in vorhanden:
			print(f"{name}  {groesse:>14} Bytes  {zeitpunkt}"
			      f"{'' if voll else '  (unvollstaendig)'}")
		return 0

	name = args.name
	if name is None:
		vorhanden = cloud.sicherungen_auflisten() if cloud.ist_aktiv() else []
		# Nur eine VOLLSTAENDIGE Sicherung laesst sich wiederherstellen — ein
		# Rest aus einem abgebrochenen Upload ist keine.
		vorhanden = [eintrag for eintrag in vorhanden if eintrag[3]]
		if not vorhanden:
			print("Keine Sicherung in der Ablage gefunden.", file=sys.stderr)
			return 1
		name = vorhanden[-1][0]
		print(f"Juengste Sicherung: {name}")
	try:
		ziel = hole_lokal(name)
	except WiederherstellungsFehler as fehler:
		print(f"Fehler: {fehler}", file=sys.stderr)
		return 1
	except Exception as fehler:  # noqa: BLE001 — z. B. Ablage nicht erreichbar
		print(f"Fehler: {type(fehler).__name__}: {fehler}", file=sys.stderr)
		return 2
	print(f"Bereitgestellt: {ziel}")
	print("Eingespielt wird nichts — der Weg steht in der Betriebsanleitung.")
	return 0


if __name__ == "__main__":  # pragma: no cover — CLI-Einstieg
	raise SystemExit(main())
