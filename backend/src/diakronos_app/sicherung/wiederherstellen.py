"""ABN-2: eine Sicherung wirklich EINSPIELEN — Datenbank UND Dateiablage.

Warum es das gibt
-----------------
Bis hierher konnte dieses Werkzeug eine Sicherung nur BEREITSTELLEN (bei
Nextcloud-Ablage herunterholen, Pruefsummen gegenrechnen) — eingespielt wurde
von Hand nach BETRIEBSANLEITUNG 14.4. Der ABN-2-Befund war genau das: der
beschriebene Weg war unvollstaendig und teilweise falsch

* ``pg_restore ... < db.dump`` las den Dump aus der STANDARD-EINGABE, obwohl
  ``pg_restore`` dort steht, wo ``data/`` **nicht** liegt → leerer Dump, und
  ``pg_restore`` bricht an einem leeren Archiv NICHT zwingend ab;
* er lief im ``db``-Container gegen eine ``DATABASE_URL``, die auf den Host
  ``db`` und ein Passwort zeigt, das es dort nicht gibt;
* die Dateiablage wurde mit ``tar -xzf ... -C data/files`` ausgepackt — der
  Unterordner der App heisst aber ``data/files/files`` (Bind-Mount). Die
  Dateien landeten damit im falschen Baum, die Datenbank verwies ins Leere;
* Migrationen (``alembic upgrade head``) und das Aufraeumen abgebrochener
  Laeufe kamen gar nicht vor.

Dieses Modul macht daraus EINEN wiederholbaren Vorgang mit Pruefungen davor
und Messungen danach::

    python -m diakronos_app.sicherung.wiederherstellen --pruefen 2026-11-26_030000
    python -m diakronos_app.sicherung.wiederherstellen 2026-11-26_030000 --einspielen
    python -m diakronos_app.sicherung.wiederherstellen 2026-11-26_030000 \\
        --einspielen --dateien-ziel /data/files --wiederholen

Ablauf (jeder Schritt mit Vorpruefung, kein stiller Teilerfolg)
---------------------------------------------------------------
1. Namen pruefen (``JJJJ-MM-TT_HHMMSS``), Verzeichnis suchen — im Lokal-Modus
   ``<BACKUP_DIR>/<name>``, im Nextcloud-Modus erst herunterholen
   (:func:`hole_lokal`).
2. ``SHA256SUMS`` gegenrechnen UND ``pg_restore --list`` lesen — ein Dump, den
   niemand lesen kann, ist keine Sicherung (:func:`pruefe_sicherung`).
3. **Vorher sichern**: ohne ``--ohne-vorsicherung`` wird der JETZIGE Stand als
   eigene Sicherung geschrieben — ueber den normalen Sicherungslauf
   (``lauf.fuehre_aus``: Sperre, Protokollzeile ``sicherungslauf``,
   Aufbewahrung), damit sie in der Oberflaeche erscheint und nicht neben dem
   Betrieb liegt. Das ist die Rueckfahrt (:func:`_vorsicherung`.
4. Datenbank: eingespielt wird in eine **NEUE** Datenbank
   ``<ziel>_wiederherstellung`` (``pg_restore --dbname`` **mit der Datei als
   Argument**, ``--exit-on-error --single-transaction``), danach
   ``alembic upgrade head`` und die Zaehlung. **Erst nach Erfolg** wird
   getauscht: die alte Datenbank heisst danach ``<ziel>_vorher_<zeit>``, die
   neue ``<ziel>``. Scheitert irgendetwas vor dem Tausch, bleibt die
   Zieldatenbank unangetastet (:func:`spiele_datenbank_ein`).
5. Dateiablage: Archiv in ein TEMPORAERES Verzeichnis unterhalb des
   Daten-Baums entpacken, jeden Eintrag pruefen (kein absoluter Pfad, kein
   ``..``, keine Geraetedatei), Groesse UND SHA-256 je Datei nachrechnen, dann
   **aufaddierend** in die Ablage schreiben (``speicher.schreiben``) — nichts
   wird vorher geloescht, ein sparsam gesichertes Archiv heilt damit auch eine
   halb verlorene Ablage. ``--wiederholen`` schreibt JEDE Datei neu, auch wenn
   sie schon gleich ist. Geschrieben wird immer in die LOKALE Ablage
   (:func:`spiele_dateien_ein`).
6. Bericht: Dauer je Schritt, Zeilenzahl je Tabelle aus dem Dump-Index,
   ``alembic_version`` und die Zahl der Dateien/Gesamtgroesse in der Ablage.

Der Weg im Image (ABN-2b)
-------------------------
``--einspielen`` laeuft im ``app``-Image OHNE ``psql``: ``DROP``/``CREATE``/
``ALTER DATABASE`` gehen ueber den Datenbanktreiber (psycopg), der fuer die
Anwendung ohnehin im Image ist. Der fruehere Zwang, den Schritt im
``db``-Dienst von Hand zu fahren, entfaellt damit; ``--zeitplan`` druckt ihn
weiterhin (freiwillig) zum Nachvollziehen.

Was das Werkzeug NICHT tut
--------------------------
* Es ersetzt die Datenbank nur mit ``--einspielen`` (ohne den Schalter ist es
  reine Pruefung — der alte Aufruf bleibt damit vertraeglich).
* Es **loescht die alte Datenbank nicht**. Nach dem Tausch steht sie als
  ``<ziel>_vorher_<zeit>`` daneben, bis der Betreiber sie ausdruecklich
  verwirft (BETRIEBSANLEITUNG 14.4, Schritt 8). Platz dafuer muss vorher da
  sein: eine Datenbank braucht das Doppelte ihres Umfangs.
* Es fasst die echte Nextcloud nicht an: im Nextcloud-Modus wird nur
  heruntergeladen. Was in der Nextcloud liegt, sichert deren eigener
  Betreiber (BETRIEBSANLEITUNG 14.5).
* Es schreibt im Nextcloud-Modus **nicht** in die Nextcloud — auch dann nicht,
  wenn ``SPEICHER_BACKEND=nextcloud`` gesetzt ist. ``files.tar.gz`` enthaelt
  nur die LOKALE Ablage; eingespielt wird deshalb nur dort (``FILES_DIR``),
  und der Weg ist derselbe wie im Lokal-Modus. Dateien in der Nextcloud sind
  Sache des Nextcloud-Betreibers (Versionierung/Backup).

Exit-Codes: 0 = erledigt, 1 = Fehler (Meldung im Klartext),
2 = Aufruf-/Einstellungsfehler.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from diakronos_app.sicherung import aufbewahrung, cloud, dump

__all__ = [
	"Dateibericht",
	"Datenbankbericht",
	"Wiederherstellungsbericht",
	"WiederherstellungsFehler",
	"pruefe_dump_inhalt",
	"pruefe_sicherung",
	"spiele_datenbank_ein",
	"spiele_dateien_ein",
	"stelle_wieder_her",
	"hole_lokal",
	"main",
]

#: Hoechstzahl Eintraege im Dump-Index (``pg_restore --list``) fuer die
#: Tabellenzaehlung. Ein Dump mit mehr Tabellen ist kein Diakronos-Dump.
_MAX_INDEX = 20000

#: Endungen, die das Dateiarchiv NICHT enthalten darf (Sicherungsreste).
_REST_MUSTER = re.compile(r"(^|/)\.tmp-|\.[0-9A-Za-z_-]*-?[Tt]eil(-[0-9A-Za-z_]+)?$")

#: Reste des Entpackens (``TemporaryDirectory(prefix=".abn2-")``) — sie
#: duerfen in keinem Bestand und in keinem Bericht auftauchen.
_TEMP_MUSTER = re.compile(r"(^|/)\.abn2-")

#: Bezeichner, die ungeprueft in SQL stehen duerfen. Datenbank- und
#: Rollennamen kommen aus der Konfiguration; ein Anfuehrungszeichen oder ein
#: Semikolon darin waere eine Einschleusung.
_BEZEICHNER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Endung der Datenbank, in die eingespielt wird, bevor getauscht wird.
_NEU_SUFFIX = "_wiederherstellung"

#: Zeitstempel im Namen der alten Datenbank (``<ziel>_vorher_<stempel>``).
_STEMPEL = "%Y%m%d_%H%M%S"

#: Praefix des Namens der alten Datenbank (``<ziel>_vorher_<stempel>``).
_ALT_PRAEFIX = "_vorher_"

#: Hoechstlaenge eines PostgreSQL-Bezeichners in BYTES. Laengere Namen kuerzt
#: PostgreSQL still — danach koennten zwei Namen gleich heissen (ABN-2c/L9).
_MAX_BEZEICHNER = 63


def _neuer_name(ziel: str) -> str:
	"""``<ziel>_wiederherstellung`` — geprueft, nie laenger als 63 Bytes."""
	return _bezeichner(f"{ziel}{_NEU_SUFFIX}",
	                   was="Datenbankname der Wiederherstellung")


def _alter_name(ziel: str, stempel: str) -> str:
	"""``<ziel>_vorher_<stempel>`` — geprueft, nie laenger als 63 Bytes.

	Die Laengenpruefung ist hier WICHTIG (ABN-2c/L9): wuerde PostgreSQL den
	Namen still kuerzen, koennte er mit ``<ziel>`` oder mit
	``<ziel>_wiederherstellung`` zusammenfallen — und der anschliessende
	``ALTER``/``DROP`` traefe die aktive Datenbank.
	"""
	return _bezeichner(f"{ziel}{_ALT_PRAEFIX}{stempel}",
	                   was="Datenbankname der alten Sicherung")


# ── Fehler ─────────────────────────────────────────────────────────────────

class WiederherstellungsFehler(RuntimeError):
	"""Die Sicherung liess sich nicht (vollstaendig) bereitstellen/einspielen."""


# ── Herunterladen (SPEICHER-2, unveraendert) ───────────────────────────────

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


def _sha256_datei(datei: Path) -> str:
	"""SHA-256 einer lokalen Datei, blockweise (grosse Dumps/Archive)."""
	summe = hashlib.sha256()
	with open(datei, "rb") as offen:
		for block in iter(lambda: offen.read(1024 * 1024), b""):
			summe.update(block)
	return summe.hexdigest()


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
		if _sha256_datei(datei) != erwartet:
			raise WiederherstellungsFehler(
				f"Die Datei {dateiname} ist beschaedigt (Pruefsumme weicht ab)."
			)


# ── Pruefungen vor dem Einspielen ──────────────────────────────────────────

def pruefe_dump_inhalt(dump_datei: Path, *, timeout: int | None = None) -> dict[str, int]:
	"""``pg_restore --list`` lesen und je Tabelle die Datensaetze zaehlen.

	Der Index eines ``-Fc``-Dumps nennt je ``TABLE DATA``-Eintrag die
	Datensaetze::

	    4783; 0 16390 TABLE DATA public ablaufplan diakronos 4

	Die ZAHL daraus ist die Sollmenge fuer die Nachpruefung: nach dem
	Einspielen muss die Tabelle genau so viele Zeilen haben (der Dump enthaelt
	nur Datenbloecke, keine Views — ``SEQUENCE SET``-Eintraege werden nicht
	mitgezaehlt).

	WICHTIG (im Wegwerf-Stack ABN-2 gemessen): bei ``pg_dump --no-owner``
	(so sichert die App, ``dump.schreibe_dump``) endet die Zeile NACH dem
	Besitzer und OHNE Zahl...

	    4783; 0 16390 TABLE DATA public ablaufplan diakronos

	...und selbst MIT ``-v`` (verbose) traegt ``pg_restore --list`` hier keine
	Zahl. Eine Zaehlung aus dem Index ist damit nicht zuverlaessig: fehlt sie,
	wird fuer die betroffene Tabelle KEIN Sollwert gefuehrt (statt einer 0,
	die eine volle Tabelle als Abweichung melden wuerde). Der Nachweis der
	Vollstaendigkeit kommt dann aus dem Vergleich A gegen B und der
	Anmeldung/Dateiprobe (docs/abnahmen/ABN-2-RESTORE-PROBE.md); der
	Wiederherstellungsbefehl selbst bricht bei ``--exit-on-error`` ab, wenn
	ein Datenblock nicht eingespielt werden konnte.

	Gibt es ``pg_restore`` nicht, wird das gemeldet statt geraten: eine
	Wiederherstellung ohne lesbaren Dump waere ein Blindflug.
	"""
	try:
		ausgabe = subprocess.run(
			[dump.pg_programm("pg_restore"), "--list", str(dump_datei)],
			capture_output=True, text=True, check=False,
			timeout=timeout if timeout and timeout > 0 else None,
		)
	except FileNotFoundError:
		raise WiederherstellungsFehler(
			"pg_restore ist im Programm nicht vorhanden."
		) from None
	except subprocess.TimeoutExpired:
		raise WiederherstellungsFehler("Der Dump-Index hat zu lange gebraucht.") from None
	if ausgabe.returncode != 0:
		raise WiederherstellungsFehler(
			f"Der Dump ist nicht lesbar (pg_restore Exit {ausgabe.returncode})."
		)
	# Zeilenform des Index: ``<dump-id>; <catalog> <oid> TABLE DATA <schema>
	# <tabelle> <besitzer> [<anzahl>]``. Schema und Besitzer sind optional
	# (``--no-owner`` / kein Schema) — die Zahl fehlt bei ``--no-owner``.
	# ``-1`` heisst danach: Tabelle ist im Dump, ihre Sollzahl ist unbekannt.
	zaehlung: dict[str, int] = {}
	for nummer, zeile in enumerate(ausgabe.stdout.splitlines()):
		if nummer > _MAX_INDEX:
			raise WiederherstellungsFehler("Der Dump-Index ist unerwartet gross.")
		if " TABLE DATA " not in zeile:
			continue
		nach = zeile.split(" TABLE DATA ", 1)[1].split()
		if not nach:
			continue
		# Schema (``public``) weg, dann Tabellenname.
		rest = nach[1:] if len(nach) > 1 else nach
		tabelle = rest[0]
		anzahl = -1
		if len(rest) >= 2 and rest[-1].isdigit():
			anzahl = int(rest[-1])
		bisher = zaehlung.get(tabelle)
		if bisher is None or bisher < 0:
			zaehlung[tabelle] = anzahl
		elif anzahl >= 0:
			zaehlung[tabelle] = bisher + anzahl
	return zaehlung


def pruefe_sicherung(verzeichnis: Path, *, timeout: int | None = None) -> dict[str, int]:
	"""Alles, was VOR dem Einspielen stimmen muss — sonst wird nichts angefasst.

	1. ``FERTIG`` liegt da (Abbruchmarker eines Laufes, der nie fertig wurde).
	2. ``SHA256SUMS`` passt (Groesse + SHA-256 je Datei).
	3. Der Dump ist mit ``pg_restore`` lesbar; Rueckgabe ist die
	   Zeilenzahl je Tabelle aus dem Dump-Index.
	"""
	if not (verzeichnis / dump.FERTIG_NAME).is_file():
		raise WiederherstellungsFehler(
			"Die Sicherung ist unvollstaendig (FERTIG-Markierung fehlt)."
		)
	_pruefe_pruefsummen(verzeichnis)
	dump_datei = verzeichnis / dump.DUMP_NAME
	if not dump_datei.is_file():
		raise WiederherstellungsFehler("Der Datenbank-Dump fehlt in der Sicherung.")
	zaehlung = pruefe_dump_inhalt(dump_datei, timeout=timeout)
	if not zaehlung:
		raise WiederherstellungsFehler(
			"Der Dump enthaelt keine Tabellendaten — das ist keine brauchbare Sicherung."
		)
	return zaehlung

# ── Datenbank einspielen ───────────────────────────────────────────────────

def _bezeichner(wert: str, *,
                was: str = "Name") -> str:
	"""Einen Datenbank-/Rollennamen pruefen: nur ``[A-Za-z0-9_]``, sonst Abbruch.

	Der Name kommt aus der Konfiguration und steht danach in SQL. Geprueft
	wird deshalb AM ANFANG des Vorgangs (nicht erst beim ``DROP``), damit ein
	Tippfehler nichts halb Fertiges hinterlaesst.

	Laengen pruefen (ABN-2c/L9): PostgreSQL kuerzt Bezeichner still auf 63
	Bytes. Waere ein abgeleiteter Name laenger (``<ziel>_wiederherstellung``,
	``<ziel>_vorher_<stempel>``), entstuenden zwei gleiche Namen — und ein
	``DROP``/``ALTER`` traefe die AKTIVE Datenbank. Deshalb ist alles ueber
	``_MAX_BEZEICHNER`` Bytes ein Abbruch mit Klartext.
	"""
	geprueft = str(wert or "")
	if not _BEZEICHNER.fullmatch(geprueft):
		raise WiederherstellungsFehler(
			f"Der {was} {wert!r} ist unbrauchbar (erlaubt: Buchstaben, Ziffern, "
			"Unterstrich; er steht ungeprueft in SQL)."
		)
	if len(geprueft.encode("utf-8")) > _MAX_BEZEICHNER:
		raise WiederherstellungsFehler(
			f"Der {was} {geprueft} ist zu lang "
			f"({len(geprueft.encode('utf-8'))} Bytes, hoechstens "
			f"{_MAX_BEZEICHNER}). PostgreSQL kuerzt laengere Namen STILL — "
			"zwei verschiedene Namen koennten dann gleich heissen und der "
			"Tausch traefe die falsche Datenbank. Bitte BACKUP_DB_NAME "
			"kuerzen."
		)
	return geprueft


def _verbindung_aus_url(roh: str) -> dict[str, object]:
	"""``DATABASE_URL``/``postgresql://…`` in seine Teile zerlegen (ohne Treiber)."""
	ohne_treiber = re.sub(r"^(postgresql|postgres)\+[^:]+://", r"\1://", str(roh or ""))
	teile = urlparse(ohne_treiber)
	return {
		"host": teile.hostname or "",
		"port": teile.port or 5432,
		"datenbank": (teile.path or "/").lstrip("/"),
		"benutzer": unquote(teile.username) if teile.username else "",
	}


def _pg_umgebung(datenbank: str | None = None) -> tuple[dict[str, str], str, str]:
	"""``PG*``-Umgebung, Datenbankname und Besitzerrolle.

	Dieselbe Verbindung benutzt auch :func:`migriere_nach` (ueber
	``DATABASE_URL``) — die Migration MUSS dieselbe Datenbank meinen wie
	``pg_restore``. Deshalb wird beides hier abgeglichen: weichen
	``BACKUP_DB_HOST``/``_PORT``/``_NAME`` von der URL ab, wird abgebrochen,
	statt die Migration woandershin laufen zu lassen (Opus-Befund M4).
	Das Passwort bleibt ein einziges (``BACKUP_DB_PASSWORD`` oder das aus der
	URL, beide aus ``${POSTGRES_PASSWORD}``) — dazu nur eine WARNUNG.

	Gleiche Regel wie beim Dump (B4): Verbindungsdaten nur ueber ``PG*``, nie
	als Argument auf der Kommandozeile — ``ps`` zeigt Argumente.
	"""
	from diakronos_app.settings import settings

	roh = str(settings.database_url or "")
	if not roh.startswith(("postgresql", "postgres")):
		raise WiederherstellungsFehler(
			"Die Datenbank-Verbindung zeigt nicht auf PostgreSQL — "
			"pg_restore ist nicht anwendbar."
		)
	url = _verbindung_aus_url(roh)
	host = settings.backup_db_host or url["host"] or "db"
	port = int(settings.backup_db_port or url["port"] or 5432)
	name = datenbank or settings.backup_db_name or url["datenbank"] or "diakronos"
	benutzer = settings.backup_db_user or str(url["benutzer"]) or "diakronos"
	warnungen: list[str] = []
	if url["host"] and settings.backup_db_host and settings.backup_db_host != url["host"]:
		warnungen.append(
			f"BACKUP_DB_HOST={settings.backup_db_host} und DATABASE_URL zeigen auf "
			f"verschiedene Hosts ({url['host']})."
		)
	if (url["port"] or 5432) != port and (settings.backup_db_port or 0):
		warnungen.append(
			f"BACKUP_DB_PORT={port} und DATABASE_URL nennen verschiedene Ports "
			f"({url['port']})."
		)
	if datenbank is None and settings.backup_db_name and url["datenbank"] \
			and settings.backup_db_name != url["datenbank"]:
		raise WiederherstellungsFehler(
			f"BACKUP_DB_NAME ({settings.backup_db_name}) und DATABASE_URL "
			f"({url['datenbank']}) meinen verschiedene Datenbanken — die Migration "
			"liefe gegen die falsche. Bitte eine Quelle setzen."
		)
	if url["benutzer"] and settings.backup_db_user \
			and settings.backup_db_user != url["benutzer"]:
		warnungen.append(
			f"BACKUP_DB_USER={settings.backup_db_user} weicht vom Benutzer der "
			f"DATABASE_URL ({url['benutzer']}) ab."
		)
	# Ein Passwort, eine Quelle: ``BACKUP_DB_PASSWORD`` oder das der URL —
	# beide kommen in Compose aus derselben Variablen (${POSTGRES_PASSWORD}).
	# Weichen sie ab, ist das ein Hinweis, kein Abbruch: das Passwort laesst
	# sich hier nicht vergleichen (nur ueber einen Anmeldeversuch), und ein
	# Abbruch wuerde jede Installation mit eigener Backup-Variable lahmlegen.
	passwort = settings.backup_db_password or _passwort_aus_url(roh)

	env = {
		"PGHOST": str(host),
		"PGPORT": str(port),
		"PGUSER": _bezeichner(benutzer, was="Benutzer"),
		"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
	}
	if passwort:
		env["PGPASSWORD"] = passwort
	for hinweis in warnungen:
		print(f"Hinweis: {hinweis}", file=sys.stderr)
	return env, _bezeichner(name, was="Datenbankname"), _bezeichner(benutzer, was="Benutzer")


def _passwort_aus_url(roh: str) -> str:
	"""Das Passwort aus einer ``postgresql://``-Adresse (leer, wenn keins)."""
	ohne_treiber = re.sub(r"^(postgresql|postgres)\+[^:]+://", r"\1://", str(roh or ""))
	teile = urlparse(ohne_treiber)
	return unquote(teile.password) if teile.password else ""


def _rufe(kommando: list[str], env: dict[str, str], *, timeout: int | None,
          was: str) -> None:
	"""Ein Unterprozess mit gekuerztem Fehlertext (keine Zugangsdaten, kein Host)."""
	try:
		ausgabe = subprocess.run(
			kommando, env=env, capture_output=True, text=True, check=False,
			timeout=timeout if timeout and timeout > 0 else None,
		)
	except FileNotFoundError:
		raise WiederherstellungsFehler(
			f"{was}: das Programm ist nicht vorhanden."
		) from None
	except subprocess.TimeoutExpired:
		raise WiederherstellungsFehler(f"{was}: Zeitueberschreitung, abgebrochen.") from None
	if ausgabe.returncode != 0:
		letzte = ""
		for zeile in (ausgabe.stderr or "").strip().splitlines()[::-1]:
			if zeile.strip():
				letzte = zeile.strip()
				break
		raise WiederherstellungsFehler(
			f"{was} ist fehlgeschlagen (Exit {ausgabe.returncode}). {letzte[:300]}".strip()
		)


def _psql(env: dict[str, str], datenbank: str, *argumente: str, timeout: int | None) -> str:
	"""Eine Abfrage ausfuehren; gibt stdout zurueck.

	Zwei Wege, aber NUR der zweite wird benutzt: ``psql`` ist im
	Laufzeit-Image nicht vorhanden, deshalb geht praktisch jede Abfrage
	ueber den Datenbanktreiber (:func:`_sql`). Der ``psql``-Aufruf bleibt als
	erster Versuch stehen, damit dasselbe Werkzeug auf einem Rechner mit
	installiertem ``psql`` (db-Dienst, Debian) denselben Weg nimmt.

	Im Image endet der ``psql``-Versuch mit ``FileNotFoundError``; dann laeuft
	dieselbe Anweisung ueber :func:`_sql` — vorher endete der Weg hier mit
	„psql ist im Programm nicht vorhanden“, und damit war ``--einspielen`` im
	Image gar nicht benutzbar (im Wegwerf-Stack ABN-2b gemessen).

	Unterstuetzt wird die Form ``-c <anweisung>``; alles andere ist ein
	Programmfehler und wird gemeldet.
	"""
	teil_env = {**env, "PGDATABASE": datenbank}
	kommando = ["psql", "-v", "ON_ERROR_STOP=1", "-t", "-A", *argumente]
	try:
		ausgabe = subprocess.run(
			kommando, env=teil_env, capture_output=True, text=True, check=False,
			timeout=timeout if timeout and timeout > 0 else None,
		)
	except FileNotFoundError:
		if len(argumente) >= 2 and argumente[-2] == "-c":
			return _sql(env, datenbank, argumente[-1], timeout=timeout)
		raise WiederherstellungsFehler(
			"psql ist im Programm nicht vorhanden (die Wiederherstellung braucht es zum "
			"Anlegen der Datenbank)."
		) from None
	except subprocess.TimeoutExpired:
		raise WiederherstellungsFehler("psql: Zeitueberschreitung, abgebrochen.") from None
	if ausgabe.returncode != 0:
		letzte = (ausgabe.stderr or "").strip().splitlines()
		grund = letzte[-1][:300] if letzte else ""
		raise WiederherstellungsFehler(
			f"psql ist fehlgeschlagen (Exit {ausgabe.returncode}). {grund}".strip()
		)
	return (ausgabe.stdout or "").strip()


def _sql(env: dict[str, str], datenbank: str, anweisung: str, *,
         timeout: int | None, autocommit: bool = True) -> str:
	"""Eine Anweisung per psycopg ausfuehren — ohne ``psql`` im Image.

	Das Laufzeit-Image traegt kein ``psql`` (nur ``pg_dump``/``pg_restore``).
	Verwaltungsbefehle wie ``DROP DATABASE``/``CREATE DATABASE``/
	``ALTER DATABASE … RENAME`` gehen auch ueber den Treiber, der fuer die
	Anwendung ohnehin im Image ist — und die Verbindungsdaten bleiben damit
	in der Umgebung (``PG*``), nie auf einer Kommandozeile.

	Verbindungsdaten (ABN-2c/M5): ``psycopg.connect`` bekommt sie als
	**Schluesselwort-Argumente**, nicht als zusammengesetzte DSN-Zeichenkette.
	Ein Passwort mit Leerzeichen oder Anfuehrungszeichen haette die DSN sonst
	zerlegt (libpq liest sie als ``key=value``-Liste) — und die Verbindung
	waere mit einem unverstaendlichen Fehler gescheitert. ``port`` muss eine
	Zahl sein; ein unbrauchbarer Wert wird gemeldet, nicht geraten.

	``timeout`` gilt jetzt auch fuer die ANWEISUNG (``statement_timeout``),
	nicht nur fuer den Verbindungsaufbau (``connect_timeout``). Ohne das lief
	ein ``ALTER DATABASE``, das auf eine fremde Sitzung wartet, unbegrenzt —
	und ``--timeout`` versprach eine Grenze, die es nicht gab.

	``autocommit=False`` (ABN-2c/H1) schaltet den Autocommit des Treibers ab;
	mehrere Anweisungen in EINEM Aufruf (mit ``;`` getrennt) laufen dann in
	EINER Transaktion — der Tausch der Datenbanken ist damit alles-oder-nichts.

	Rueckgabe wie ``psql -t -A``: je Zeile die erste Spalte, ``"\\n"``-getrennt;
	Anweisungen ohne Ergebnismenge (``DROP``/``CREATE``/``ALTER``) liefern
	``""``. Fehler kommen als ``WiederherstellungsFehler`` mit dem Text der
	Datenbank (ohne Zugangsdaten, ohne Host).
	"""
	import psycopg

	verbindung_teile: dict[str, object] = {
		"host": str(env.get("PGHOST", "db")),
		"user": str(env.get("PGUSER", "diakronos")),
		"dbname": datenbank,
		"connect_timeout": 15,
	}
	try:
		verbindung_teile["port"] = int(env.get("PGPORT", "5432"))
	except (TypeError, ValueError):
		raise WiederherstellungsFehler(
			f"Der Port der Datenbank ist unbrauchbar ({env.get('PGPORT')!r})."
		) from None
	if env.get("PGPASSWORD"):
		verbindung_teile["password"] = str(env["PGPASSWORD"])
	if timeout and timeout > 0:
		# In Millisekunden; gilt serverseitig fuer jede Anweisung der Sitzung.
		verbindung_teile["options"] = f"-c statement_timeout={int(timeout) * 1000}"
	try:
		with psycopg.connect(**verbindung_teile, autocommit=autocommit) as verbindung:
			with verbindung.cursor() as cursor:
				cursor.execute(anweisung)
				# ``psql -t -A`` liefert je Zeile die erste Spalte — genauso
				# hier. Ein SELECT ohne Ergebnis bleibt leer; Anweisungen ohne
				# Ergebnismenge (DROP/CREATE/ALTER) liefern ebenfalls "".
				# (Fehler ABN-2b: hier stand ``if zeilen:`` — dann kam JEDE
				# Zaehlung leer zurueck, und die offenen Verbindungen waren
				# immer „nicht zaehlbar“.)
				if cursor.description is not None:
					ergebnis = "\n".join(
						"" if zeile[0] is None else str(zeile[0])
						for zeile in cursor.fetchall()
					)
					return ergebnis
	except psycopg.Error as fehler:
		raise WiederherstellungsFehler(
			f"Die Anweisung an die Datenbank ist fehlgeschlagen "
			f"({type(fehler).__name__}: {str(fehler).strip()[:250]})."
		) from None
	except OSError as fehler:
		raise WiederherstellungsFehler(
			"Die Datenbank ist nicht erreichbar "
			f"({env.get('PGHOST')}:{env.get('PGPORT')}, {type(fehler).__name__})."
		) from None
	return ""


def _transaktion(env: dict[str, str], *anweisungen: str, timeout: int | None) -> None:
	"""Mehrere Anweisungen ALLES-ODER-NICHTS (eine Transaktion, ABN-2c/H1).

	Zwischen zwei ``ALTER DATABASE … RENAME`` gibt es kein Fenster, in dem
	keine Datenbank ``<ziel>`` heisst: entweder beide Umbenennungen gelten,
	oder keine. ``RENAME DATABASE`` ist transaktional; mit abgeschaltetem
	Autocommit haelt die Verbindung beide Anweisungen bis zum ``COMMIT``.

	Der Treiber schliesst den Block mit ``COMMIT`` ab; scheitert eine
	Anweisung, wird ``ROLLBACK`` ausgefuehrt und ``WiederherstellungsFehler``
	gemeldet.
	"""
	verbund = ";\n".join(anweisung.rstrip().rstrip(";") for anweisung in anweisungen)
	_sql(env, "postgres", verbund, timeout=timeout, autocommit=False)


def _pruefe_keine_sitzung(env: dict[str, str], datenbank: str, *,
                          timeout: int | None) -> None:
	"""Vor dem Verwerfen: haelt noch eine ANDERE Sitzung die Datenbank?

	``DROP ... WITH (FORCE)`` beendet normale Sitzungen selbst. Was es NICHT
	kann, ist eine Datenbank loeschen, mit der die ausfuehrende Sitzung
	verbunden ist — und die eigene Verbindung ist hier ausdruecklich die
	Verwaltungsdatenbank (``postgres``). Diese Pruefung macht den Fall lesbar,
	statt ihn als kryptischen SQL-Fehler zu melden: steht eine Anwendung noch
	auf der Datenbank, wird sie NICHT unter ihr weggerissen, sondern der
	Betreiber stoppt sie zuerst (BETRIEBSANLEITUNG 14.4, Schritt 2).

	Laesst sich die Zahl nicht lesen, wird das GEMELDET (Opus-Befund L2):
	still schlucken hiesse, dem Betreiber eine Pruefung vorzuspiegeln, die
	nicht stattgefunden hat.
	"""
	# Die EIGENE Sitzung zaehlt nicht mit: ``_psql`` verbindet sich fuer die
	# Zaehlung selbst mit ``postgres``, aber ``pg_stat_activity`` fuehrt auch
	# die Verbindung, die den DROP gleich ausfuehrt — und die Meldung „1
	# Verbindung offen“ waere dann das Werkzeug selbst (im Wegwerf-Stack
	# ABN-2b genau so aufgetreten). ``pg_backend_pid()`` schliesst sie aus.
	abfrage = (
		"SELECT count(*) FROM pg_stat_activity "
		f"WHERE datname = {_zitat_literal(datenbank)} "
		"AND pid <> pg_backend_pid() "
		"AND backend_type = 'client backend'"
	)
	# Kurz wiederholen, bevor „app laeuft noch“ gemeldet wird: ein gerade
	# beendeter Einspielversuch schliesst seine Verbindung nicht immer sofort.
	# Ohne dieses Nachfassen meldete das Werkzeug die EIGENE, abklingende
	# Verbindung als „noch 1 Verbindung offen“ und jeder zweite Lauf scheiterte
	# (im Wegwerf-Stack ABN-2b genau so aufgetreten).
	anzahl = 0
	for versuch in range(3):
		try:
			anzahl = int(_psql(env, "postgres", "-c", abfrage, timeout=timeout) or 0)
		except (WiederherstellungsFehler, ValueError) as fehler:
			raise WiederherstellungsFehler(
				"Die offenen Verbindungen auf die Datenbank liessen sich nicht "
				f"zaehlen ({fehler}). Ohne diese Pruefung wird nicht getauscht — "
				"bitte app, worker und scheduler anhalten und den Befehl wiederholen."
			) from None
		if anzahl == 0:
			return
		time.sleep(1.0 + versuch)
	if anzahl > 0:
		# WER haelt sie? Ohne diese Angabe ist die Meldung im Betrieb nicht
		# nachvollziehbar („1 Verbindung“ — und niemand weiss, welche).
		try:
			wer = _psql(env, "postgres", "-c", (
				"SELECT string_agg(coalesce(usename, '?') || '@' || "
				"coalesce(client_addr::text, 'lokal') || ' (' || "
				"coalesce(state, '?') || ')', ', ') FROM pg_stat_activity "
				f"WHERE datname = {_zitat_literal(datenbank)} "
				"AND pid <> pg_backend_pid() AND backend_type = 'client backend'"
			), timeout=timeout)
		except WiederherstellungsFehler:
			wer = ""
		raise WiederherstellungsFehler(
			f"Es sind noch {anzahl} Verbindungen auf die Datenbank offen"
			f"{(' (' + wer + ')') if wer else ''}. "
			"Bitte app, worker und scheduler zuerst anhalten "
			"(docker compose stop app worker scheduler) und den Befehl wiederholen."
		)


def _verwaltung(env: dict[str, str], anweisung: str, *, timeout: int | None) -> str:
	"""``DROP``/``CREATE``/``ALTER DATABASE`` ausfuehren — Verwaltungsdatenbank.

	Der Weg geht AUSSCHLIESSLICH ueber den Datenbanktreiber (:func:`_sql`)
	gegen die Verwaltungsdatenbank ``postgres``: ``psql`` ist im Laufzeit-Image
	nicht vorhanden, und dieser Weg braucht es nicht. (Der Docstring nannte
	frueher einen ``psql``-Vorrang, den es im Code nie gab — ABN-2c/L10.)
	"""
	return _sql(env, "postgres", anweisung, timeout=timeout)


def _datenbanken(env: dict[str, str], *, timeout: int | None) -> set[str]:
	"""Die vorhandenen Datenbanknamen der Instanz."""
	ausgabe = _psql(
		env, "postgres", "-c",
		"SELECT datname FROM pg_database WHERE datallowconn", timeout=timeout,
	)
	return {zeile.strip() for zeile in ausgabe.splitlines() if zeile.strip()}


def _vorher_datenbanken(ziel: str, *, timeout: int | None = None) -> list[str]:
	"""Die vorhandenen ``<ziel>_vorher_*``-Datenbanken (ABN-2c/M6).

	Jeder Tausch laesst die alte Datenbank stehen; nach ein paar Laeufen
	liegen mehrere davon im Cluster. Vor dem Einspielen werden sie AUFGELISTET
	und im Bericht genannt — geloescht wird KEINE (das entscheidet der
	Betreiber nach der Stichprobe, BETRIEBSANLEITUNG 14.4, Schritt 8).

	Laesst sich die Frage nicht beantworten (Datenbank nicht erreichbar),
	bleibt die Liste leer — eine fehlende Liste ist kein Abbruchgrund.
	"""
	try:
		env, standard, _besitzer = _pg_umgebung()
		vorhanden = _datenbanken(env, timeout=timeout)
	except WiederherstellungsFehler:
		return []
	name = ziel or standard
	return sorted(datenbank for datenbank in vorhanden
	              if datenbank.startswith(f"{name}{_ALT_PRAEFIX}"))


def spiele_datenbank_ein(
	dump_datei: Path,
	*,
	timeout: int | None = None,
	datenbank: str | None = None,
) -> str:
	"""Datenbank aus ``dump_datei`` einspielen — ohne die alte zu zerstoeren.

	Reihenfolge (Opus-Befund H2 — der halbe Zustand):

	1. In eine **NEUE** Datenbank ``<ziel>_wiederherstellung`` einspielen:
	   ``pg_restore --dbname <neu> <datei> --exit-on-error --single-transaction``.
	   Bricht das ab, wird die neue Datenbank wieder verworfen — die ALTE ist
	   nie angefasst worden.
	2. Zurueckgeben den Namen der neuen Datenbank. Migrieren und Zaehlen macht
	   der Aufrufer (:func:`migriere_nach`, :func:`tabellenstaende`);
	   :func:`tausche_datenbank` vollzieht erst danach den Wechsel.

	Rueckgabe: der Name der neuen, noch nicht aktiven Datenbank
	(``<ziel>_wiederherstellung``).

	``--single-transaction`` bleibt die eigentliche Zusage: schlaegt ein
	Schritt fehl, wird ALLES zurueckgerollt — es bleibt nie ein halb
	eingespielter Stand stehen. Die Pruefung der Sicherung
	(``pruefe_sicherung``) laeuft VORHER; hier wird der Dump-Inhalt nicht
	mehr nachgesehen.
	"""
	return _spiele_in_neue_datenbank(dump_datei, timeout=timeout, datenbank=datenbank)


def _spiele_in_neue_datenbank(
	dump_datei: Path,
	*,
	timeout: int | None = None,
	datenbank: str | None = None,
) -> str:
	"""``dump_datei`` in ``<ziel>_wiederherstellung`` einspielen; Name zurueck."""
	env, ziel, _besitzer = _pg_umgebung(datenbank)
	# Geprueft MIT Endung: ein zu langer Name bricht HIER ab, bevor irgendetwas
	# angelegt oder geloescht wird (ABN-2c/L9).
	neu = _neuer_name(ziel)
	# Rest eines abgebrochenen Laufs: eine halb gefuellte NEUE Datenbank wird
	# NICHT ueberschrieben, ohne dass es jemand weiss — sie wird verworfen
	# (dort liegen nur Daten aus einem frueheren Versuch, keine Betriebsdaten).
	# Sonst scheitert das ``CREATE`` an „Database already exists“.
	_verwaltung(env, f'DROP DATABASE IF EXISTS "{neu}" WITH (FORCE)', timeout=timeout)
	_verwaltung(env, f'CREATE DATABASE "{neu}"', timeout=timeout)
	try:
		# pg_restore bekommt die DATEI als Argument (nicht per stdin): das war
		# der eigentliche Fehler in BETRIEBSANLEITUNG 14.4.
		_rufe(
			[
				dump.pg_programm("pg_restore"),
				"--dbname", neu,
				"--no-owner",
				# KEIN ``--role``: der Dump ist mit ``--no-owner`` geschrieben,
				# alle Objekte gehoeren damit dem verbindenden Benutzer. Ein
				# ``--role`` verlangt eine VORHANDENE Rolle und brach im
				# Wegwerf-Stack ABN-2b genau daran ab („SET ROLE
				# diakronos_restore“ — Rolle gibt es nicht).
				"--exit-on-error",
				"--single-transaction",
				str(dump_datei),
			],
			env, timeout=timeout, was="pg_restore",
		)
	except WiederherstellungsFehler:
		# Die halb gefuellte NEUE Datenbank wieder weg — die alte bleibt
		# unangetastet stehen.
		try:
			_verwaltung(env, f'DROP DATABASE IF EXISTS "{neu}" WITH (FORCE)',
			            timeout=timeout)
		except WiederherstellungsFehler:
			pass
		raise
	return neu


def tausche_datenbank(neu: str, *, ziel: str | None = None, timeout: int | None = None,
                      stempel: str | None = None) -> str:
	"""Die alte Datenbank zur Seite legen und ``neu`` unter dem Zielnamen aktivieren.

	``ALTER DATABASE ... RENAME TO`` ist die sichere Form: sie aendert nur den
	Katalogeintrag, kopiert nichts, und laesst sich in einem Schritt
	zuruecknehmen (Rueckgabe: der Name, unter dem die ALTE Datenbank jetzt
	steht — ``<ziel>_vorher_<JJJJMMTT_HHMMSS>``).

	BEIDE Umbenennungen laufen in EINER Transaktion (ABN-2c/H1): zwischen
	ihnen gibt es keinen Moment, in dem keine Datenbank ``<ziel>`` heisst.
	Bricht der Tausch ab (Fehler, Kill, OOM), gilt KEINE der beiden — die
	alte Datenbank ist unveraendert aktiv, die neue behaelt ihren Namen.

	``stempel`` setzt den Zeitstempel ausdruecklich (fuer ``--tausch``: der
	Name der neuen Datenbank und der Rueckweg gehoeren zusammen).
	"""
	env, standard, _besitzer = _pg_umgebung()
	zieldb = _bezeichner(ziel or standard, was="Datenbankname")
	neu = _bezeichner(neu, was="Datenbankname der Wiederherstellung")
	stempel = stempel or _stempel_jetzt()
	alt = _alter_name(zieldb, stempel)
	# Fehlt die Zieldatenbank (abgebrochener frueherer Tausch), steht der
	# Rueckweg in der Meldung — nicht ein nacktes „does not exist“ (H1).
	_pruefe_zieldatenbank_da(env, zieldb)
	_pruefe_keine_sitzung(env, zieldb, timeout=timeout)
	_pruefe_keine_sitzung(env, neu, timeout=timeout)
	_transaktion(
		env,
		f'ALTER DATABASE "{zieldb}" RENAME TO "{alt}"',
		f'ALTER DATABASE "{neu}" RENAME TO "{zieldb}"',
		timeout=timeout,
	)
	return alt


def _stempel_jetzt() -> str:
	"""Ortszeit-Stempel fuer Datenbanknamen (``JJJJMMTT_HHMMSS``).

	Ortszeit wie alle Zeitpunkte der Sicherung (:func:`jetzt_ortszeit`) — ein
	Name in UTC neben einem Sicherungsnamen in Ortszeit waere im Betrieb
	irrefuehrend. Faellt die Naht aus (Import-Zeitpunkt), gilt der
	Container-Zeitpunkt derselben Zone.
	"""
	try:
		from diakronos_app.sicherung.einstellungen import jetzt_ortszeit

		return jetzt_ortszeit().strftime(_STEMPEL)
	except Exception:  # noqa: BLE001 — Name, kein Abbruchgrund
		return datetime.now().strftime(_STEMPEL)


def finde_umleitung(ziel: str) -> str | None:
	"""Hat ein frueherer Tausch die Zieldatenbank liegen gelassen?

	ABN-2c/H1: fehlt ``<ziel>``, gibt es aber ``<ziel>_vorher_*``, ist ein
	Lauf in der Mitte stehen geblieben. Rueckgabe ist der JUENGSTE solcher
	Namens (die ausgelagerte Betriebsdatenbank) — ``None``, wenn alles
	gewoehnlich ist oder die Frage nicht beantwortet werden kann (dann
	verhaelt sich der Aufrufer wie bisher).
	"""
	env, standard, _besitzer = _pg_umgebung()
	zieldb = _bezeichner(ziel or standard, was="Datenbankname")
	try:
		vorhanden = _datenbanken(env, timeout=None)
	except WiederherstellungsFehler:
		return None
	if zieldb in vorhanden:
		return None
	ausgelagert = sorted(name for name in vorhanden
	                     if name.startswith(f"{zieldb}{_ALT_PRAEFIX}"))
	return ausgelagert[-1] if ausgelagert else None


def _rueckweg_befehl(ausgelagert: str, ziel: str) -> str:
	"""Der Befehl, der eine ausgelagerte Datenbank wieder aktiv macht."""
	return f'ALTER DATABASE "{ausgelagert}" RENAME TO "{ziel}"'


def _pruefe_zieldatenbank_da(env: dict[str, str], ziel: str) -> None:
	"""Vor dem Tausch: liegt die Datenbank ueberhaupt da, die ersetzt werden soll?

	Fehlt sie (und liegt eine ausgelagerte daneben), steht die Meldung im
	Klartext da — mit dem Rueckweg-Befehl (ABN-2c/H1). Sonst kaeme nur ein
	nichtssagendes ``database "…" does not exist`` aus ``ALTER DATABASE``.
	"""
	vorhanden = _datenbanken(env, timeout=None)
	if ziel in vorhanden:
		return
	ausgelagert = sorted(name for name in vorhanden
	                     if name.startswith(f"{ziel}{_ALT_PRAEFIX}"))
	if ausgelagert:
		juengste = ausgelagert[-1]
		raise WiederherstellungsFehler(
			f"Die Datenbank {ziel} fehlt — ein frueherer Tausch ist in der Mitte "
			f"stehen geblieben (die alte Datenbank liegt als {juengste} daneben). "
			"Dort sind die Betriebsdaten unversehrt. Rueckweg: "
			f"{_rueckweg_befehl(juengste, ziel)} — danach den Vorgang wiederholen. "
			f"Falls die Wiederherstellung doch abgeschlossen werden soll: "
			f'ALTER DATABASE "{juengste}" RENAME TO "{ziel}_vorher_<aelter>" und '
			f"den Tausch erneut starten."
		)
	raise WiederherstellungsFehler(
		f"Die Datenbank {ziel} gibt es nicht (und keine ausgelagerte "
		f"{ziel}{_ALT_PRAEFIX}…). Bitte BACKUP_DB_NAME/DATABASE_URL pruefen."
	)


def migriere_nach(dump_dir: Path | None = None, *, timeout: int | None = None,
                  datenbank: str | None = None) -> str:
	"""``alembic upgrade head`` nach dem Einspielen; gibt die Version zurueck.

	Eine Sicherung ist ein Stand ihres Zeitpunkts — die Anwendung kann
	inzwischen weiter sein. Ohne diesen Schritt liefe ein alter Stand mit
	neuer Software gegen ein altes Schema. ``alembic`` liegt im Programm
	(``/app/alembic.ini`` im Image); im lokalen Import achten wir auf die
	Umgebung: dort, wo es kein alembic gibt, wird das ausdruecklich gemeldet.

	``datenbank`` benennt die Ziel-Datenbank (beim Einspielen die NEUE,
	``<ziel>_wiederherstellung``). Ohne Angabe gilt die aus der
	Konfiguration — und dann muss sie mit ``BACKUP_DB_NAME`` uebereinstimmen,
	sonst waere die Migration in einer anderen Datenbank als ``pg_restore``
	(gleiche Pruefung wie in :func:`_pg_umgebung`).

	``dump_dir`` ist nur noch aus Kompatibilitaet da (aeltere Aufrufer gaben
	das Sicherungsverzeichnis mit); gebraucht wird es nicht.
	"""
	from diakronos_app.settings import settings

	env, standard, _besitzer = _pg_umgebung()
	ziel = datenbank or standard
	if not datenbank and settings.backup_db_name \
			and settings.backup_db_name != standard:
		raise WiederherstellungsFehler(
			"BACKUP_DB_NAME und DATABASE_URL meinen verschiedene Datenbanken — "
			"die Migration liefe gegen die falsche."
		)
	env = {
		**env,
		"DATABASE_URL": _url_fuer(settings.database_url, ziel),
	}
	ini = _alembic_ini()
	_rufe([sys.executable, "-m", "alembic", "-c", str(ini), "upgrade", "head"],
	      env, timeout=timeout, was="alembic upgrade")
	return alembic_version(datenbank=ziel, timeout=timeout)


def _url_fuer(url: str, datenbank: str) -> str:
	"""``DATABASE_URL`` mit einem anderen Datenbanknamen (Rest unveraendert)."""
	from urllib.parse import urlunparse

	ohne_treiber = re.sub(r"^(postgresql|postgres)\+[^:]+://", r"\1://", str(url))
	teile = urlparse(ohne_treiber)
	# Den Treiberteil erhalten: alembic/app braucht ihn.
	treiber = re.match(r"^(postgresql|postgres)\+[^:]+://", str(url))
	praefix = treiber.group(0) if treiber else f"{teile.scheme}://"
	rest = urlunparse(("", "", f"/{datenbank}", teile.query, "", ""))
	return praefix + teile.netloc + rest


def _alembic_ini() -> Path:
	"""Die ``alembic.ini`` finden: Image (``/app``) zuerst, dann der Quellbaum."""
	kandidat = Path("/app/alembic.ini")
	if kandidat.is_file():
		return kandidat
	hier = Path(__file__).resolve()
	# …/backend/src/diakronos_app/sicherung/wiederherstellen.py -> backend/alembic.ini
	for eltern in hier.parents:
		if (eltern / "alembic.ini").is_file():
			return eltern / "alembic.ini"
	raise WiederherstellungsFehler("alembic.ini wurde nicht gefunden.")


def alembic_version(*, timeout: int | None = None, datenbank: str | None = None) -> str:
	"""Die schemagerechte ``alembic_version``-Zeile (leer, wenn es sie nicht gibt)."""
	env, name, _besitzer = _pg_umgebung()
	try:
		zeile = _psql(env, datenbank or name, "-c",
		              "SELECT version_num FROM alembic_version", timeout=timeout)
	except WiederherstellungsFehler:
		return ""
	return zeile.splitlines()[0].strip() if zeile else ""


def tabellenstaende(*, timeout: int | None = None,
                    datenbank: str | None = None) -> dict[str, int]:
	"""Zeilen je Tabelle im ECHTEN Schema (Nachweis nach dem Einspielen).

	Gelesen aus ``pg_catalog``: nur gewoehnliche Tabellen mit Daten
	(``relkind = 'r'``), keine Views/Sequenzen/Fremdschemata. Die Zahlen sind
	deshalb 1:1 mit ``pruefe_dump_inhalt`` vergleichbar.
	"""
	env, name, _besitzer = _pg_umgebung()
	abfrage = (
		"SELECT relname FROM pg_catalog.pg_class c "
		"JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
		"WHERE c.relkind = 'r' AND n.nspname = 'public' ORDER BY relname"
	)
	namen = [zeile for zeile in _psql(env, datenbank or name, "-c", abfrage,
	                                 timeout=timeout).splitlines()
	         if zeile.strip()]
	if not namen:
		return {}
	union = " UNION ALL ".join(
		f'SELECT {_zitat_literal(n)} AS t, count(*) AS n FROM "{_zitat_bezeichner(n)}"'
		for n in namen
	)
	ausgabe = _psql(env, datenbank or name, "-c", union, timeout=timeout)
	staende: dict[str, int] = {}
	for zeile in ausgabe.splitlines():
		teile = zeile.rsplit("|", 1)
		if len(teile) == 2 and teile[1].strip().isdigit():
			staende[teile[0]] = int(teile[1])
	return staende


def _zitat_literal(wert: str) -> str:
	"""Ein Text-Literal fuer SQL (Tabellennamen stehen nicht in der Abfrage)."""
	return "'" + wert.replace("'", "''") + "'"


def _zitat_bezeichner(wert: str) -> str:
	"""Einen Bezeichner fuer ``"..."`` quoten (gespiegelte Anfuehrungszeichen)."""
	return wert.replace('"', '""')


# ── Dateiablage einspielen ─────────────────────────────────────────────────

@dataclass
class Dateibericht:
	"""Was das Zurueckholen der Dateiablage getan hat (fuer Protokoll/Abnahme)."""

	dateien: int = 0
	bytes: int = 0
	uebersprungen: int = 0
	"Dateien, die schon gleich waren (ohne ``--wiederholen`` nicht neu geschrieben)."
	verworfen: list[str] = field(default_factory=list)
	"Eintraege, die NICHT uebernommen wurden (Verzeichnisse, Verweise, unsichere Pfade)."
	eigentuemer_falsch: int = 0
	"Dateien, deren Besitzer nicht der Dienst-Benutzer ist (Warnung, kein Abbruch)."
	"Gesetzt nur, wenn der Prozess als root laeuft und nach dem Schreiben pruefen kann."
	ziel_wurzel: str = ""
	"Die Wurzel, in die geschrieben wurde — im Nextcloud-Modus ausdruecklich lokal."


def _sicherer_archivpfad(name: str) -> str:
	"""Ein tar-Eintrag als Ablage-Schluessel — oder ``WiederherstellungsFehler``.

	Das Archiv stammt aus UNSEREM Lauf, aber es wird nicht darauf gebaut:
	absolute Pfade, ``..``-Segmente, Geraetedateien und Verweise werden
	abgewiesen bzw. verworfen (``dump.schreibe_dateiarchiv`` schreibt nur
	Dateien mit relativen Namen — was hier nicht passt, ist fremd).
	"""
	if name.startswith("/") or name.startswith("\\"):
		raise WiederherstellungsFehler(f"Unsicherer Pfad im Dateiarchiv: {name[:80]}")
	teile = [teil for teil in name.replace("\\", "/").split("/") if teil not in ("", ".")]
	if any(teil == ".." for teil in teile):
		raise WiederherstellungsFehler(f"Unsicherer Pfad im Dateiarchiv: {name[:80]}")
	return "/".join(teile)


def _dienst_fremd(speicher, schluessel: str) -> bool:
	"""Gehoert die geschriebene Datei einem ANDEREN Benutzer als dem Dienst?

	Das ist der Fehler, der im Wegwerf-Stack ABN-2 zugeschlagen hat: wer die
	Wiederherstellung als root ausfuehrt (``docker compose exec -u root`` oder
	ein Aufraeum-Container), legt die Dateien root:root mit 0640 an — der
	Dienst (``appuser``) kann sie danach NICHT mehr lesen, und die Datei
	antwortet in der Oberflaeche mit 500. Die Ablage schreibt atomar mit
	``0o666 & ~umask``; der Besitz kommt dabei aus dem Prozess.

	Die Pruefung ist eine WARNUNG, kein Abbruch: ein einzelner Fehlbesitz soll
	die Wiederherstellung nicht verhindern, aber er darf nicht unerwaehnt
	bleiben. Sie greift nur dort, wo es einen lokalen Pfad gibt (lokale
	Ablage); Nextcloud hat keinen.
	"""
	try:
		pfad = speicher.pfad(schluessel) if hasattr(speicher, "pfad") else None
		uid = pfad.stat().st_uid if pfad is not None else None
	except Exception:  # noqa: BLE001 — Pruefung ist Beiwerk
		return False
	if uid is None:
		return False
	# Als root geschrieben (--user root): der Dienst kann die Datei danach
	# nicht lesen. Als appuser geschrieben: Besitz passt.
	return uid == 0 and os.geteuid() == 0


def _lokale_ablage(wurzel: Path | None = None):
	"""Die LOKALE Ablage — unabhaengig von ``SPEICHER_BACKEND`` (Opus-Befund M3).

	``files.tar.gz`` enthaelt nur die lokale Ablage (``dump.schreibe_dateiarchiv``
	sichert bewusst das Volume, siehe dort). Wird eingespielt ueber
	``hole_speicher()`` — und das liefert bei ``SPEICHER_BACKEND=nextcloud``
	die Nextcloud —, landen die Dateien im WebDAV statt im lokalen Dateibaum,
	und die App sucht sie dort, wo sie NICHT liegen. Deshalb: immer lokal.

	``wurzel`` ist der Zielordner (Default ``FILES_DIR``); ein ausdruecklich
	gesetztes ``--dateien-ziel`` gewinnt.
	"""
	from diakronos_app.settings import settings
	from diakronos_app.speicher.lokal import Lokal

	return Lokal(str(wurzel or settings.files_dir))


def spiele_dateien_ein(
	archiv: Path,
	*,
	ziel_wurzel: Path | None = None,
	wiederholen: bool = False,
) -> Dateibericht:
	"""``files.tar.gz`` in die LOKALE Dateiablage schreiben (aufaddierend, geprueft).

	Geschrieben wird **immer lokal** (``FILES_DIR`` bzw. ``ziel_wurzel``),
	auch bei ``SPEICHER_BACKEND=nextcloud``: das Archiv enthaelt nur die
	lokale Ablage, und ein Schreiben in die Nextcloud wuerde die Dateien
	dorthin legen, wo die App bei ``lokal`` nicht sucht (und den fremden
	Nextcloud-Bestand ueberschreiben). Der Bericht nennt die benutzte Wurzel.

	Reihenfolge je Datei:

	1. in ein TEMPORAERES Verzeichnis UNTERHALB des Daten-Baums entpacken
	   (nicht ``/tmp``: der Datenbaum ist der einzige Ort, der im Betrieb
	   erhalten bleibt und genug Platz hat);
	2. Groesse und SHA-256 aus dem Archiv sind die Sollwerte — die entpackte
	   Datei wird dagegen nachgerechnet, BEVOR sie in die Ablage geht. Ein
	   beschaedigtes Archiv hinterlaesst damit keine halbe Wahrheit;
	3. ueber ``speicher.schreiben`` in die Ablage (atomar, 0644/0600 wie
	   ueberall, ``.teil`` wird nie sichtbar).

	Ohne ``wiederholen`` wird eine Datei uebersprungen, wenn sie in der Ablage
	schon **byte-gleich** ist (gleiche Groesse UND gleiche SHA-256 —
	Wiederaufnahme nach Abbruch).
	"""
	if not archiv.is_file():
		raise WiederherstellungsFehler("Das Dateiarchiv fehlt in der Sicherung.")
	wurzel = Path(ziel_wurzel) if ziel_wurzel is not None else None
	speicher = _lokale_ablage(wurzel)
	bericht = Dateibericht(ziel_wurzel=str(wurzel or _lokale_wurzel()))
	with tempfile.TemporaryDirectory(prefix=".abn2-", dir=bericht.ziel_wurzel) as temp:
		tempdir = Path(temp)
		try:
			with tarfile.open(archiv, "r:gz") as tar:
				for eintrag in tar:
					if eintrag.isdir():
						continue
					schluessel = _sicherer_archivpfad(eintrag.name)
					if not schluessel:
						continue
					if not eintrag.isreg():
						# Verweise/Geraete/… nie uebernehmen (Sicherheit), sondern
						# im Bericht nennen.
						bericht.verworfen.append(f"{eintrag.name} (keine regulaere Datei)")
						continue
					if _REST_MUSTER.search(eintrag.name) or _TEMP_MUSTER.search(eintrag.name):
						bericht.verworfen.append(f"{eintrag.name} (Sicherungsrest)")
						continue
					quelle = tar.extractfile(eintrag)
					if quelle is None:  # pragma: no cover — isreg() schliesst das aus
						bericht.verworfen.append(f"{eintrag.name} (nicht lesbar)")
						continue
					zwischen = tempdir / f"datei-{bericht.dateien + 1:08d}"
					geschrieben = 0
					summe = hashlib.sha256()

					def _block(quelle=quelle) -> bytes:
						# Eigene Schliessung: ``iter(lambda: ...)`` ohne Bindung
						# haette den Leser als ``None`` typisiert.
						return quelle.read(1024 * 1024)

					with open(zwischen, "wb") as datei:
						for block in iter(_block, b""):
							datei.write(block)
							summe.update(block)
							geschrieben += len(block)
					if geschrieben != eintrag.size:
						raise WiederherstellungsFehler(
							f"Die Datei {schluessel[:80]} ist im Archiv abgeschnitten "
							f"({geschrieben} von {eintrag.size} Bytes)."
						)
					if not wiederholen and _ablage_gleich(speicher, schluessel,
					                                     geschrieben, summe.hexdigest()):
						bericht.uebersprungen += 1
						zwischen.unlink(missing_ok=True)
						continue
					with open(zwischen, "rb") as datei:
						speicher.schreiben(schluessel, datei)
					_besitz_richten(speicher, schluessel)
					zwischen.unlink(missing_ok=True)
					bericht.dateien += 1
					bericht.bytes += geschrieben
					if _dienst_fremd(speicher, schluessel):
						bericht.eigentuemer_falsch += 1
		except tarfile.TarError as fehler:
			raise WiederherstellungsFehler(
				f"Das Dateiarchiv ist beschaedigt ({type(fehler).__name__})."
			) from fehler
	# Reste des Entpackens liegen bleiben nie: ``TemporaryDirectory`` raeumt sie.
	return bericht


def _lokale_wurzel() -> str:
	from diakronos_app.settings import settings

	return str(settings.files_dir)


def _lese_ablage(speicher, schluessel: str) -> bytes | None:
	"""Eine Datei der Ablage lesen (``None``, wenn es sie nicht gibt)."""
	if speicher.groesse(schluessel) is None:
		return None
	try:
		with speicher.oeffnen(schluessel) as quelle:
			return b"".join(quelle.strom())
	except Exception:  # noqa: BLE001 — nicht lesbar = nicht gleich
		return None


def _ablage_gleich(speicher, schluessel: str, groesse: int, summe: str) -> bool:
	"""Liegt die Datei in der Ablage schon mit gleicher Groesse UND SHA-256?"""
	if speicher.groesse(schluessel) != groesse:
		return False
	inhalt = _lese_ablage(speicher, schluessel)
	return inhalt is not None and hashlib.sha256(inhalt).hexdigest() == summe


def _besitz_richten(speicher, schluessel: str) -> None:
	"""Eine als root geschriebene Datei dem Dienst-Benutzer uebergeben.

	Der Besitz kommt aus dem Prozess; laeuft dieser als root, gehoert die
	Datei danach root und der Dienst (``appuser``) kann sie nicht lesen. Laeuft
	der Prozess als appuser (der dokumentierte Weg), ist hier nichts zu tun.
	Uebernehmen laesst sich der Besitz nur, wenn auch die nuetzen UID/GID
	erreichbar ist — sonst bleibt die WARNUNG im Bericht.
	"""
	import pwd
	if os.geteuid() != 0:
		return
	try:
		pfad = speicher.pfad(schluessel)
		benutzer = pwd.getpwnam("appuser")
	except (KeyError, AttributeError, OSError):
		return
	try:
		os.chown(pfad, benutzer.pw_uid, benutzer.pw_gid)
	except OSError:
		return


def dateibestand(ziel_wurzel: Path | None = None) -> tuple[int, int]:
	"""Anzahl und Gesamtgroesse der Dateien in der lokalen Ablage (Nachweis).

	Gezaehlt wird immer die lokale Ablage (:func:`_lokale_ablage`) — also
	dieselbe Wurzel, in die :func:`spiele_dateien_ein` schreibt, auch bei
	``SPEICHER_BACKEND=nextcloud``. Nicht-Dateien, Sicherungsreste
	(``.teil``) und Temp-Reste des Entpackens (``.abn2-*``) zaehlen nicht mit.
	"""
	try:
		speicher = _lokale_ablage(ziel_wurzel)
		anzahl = 0
		gesamt = 0
		for eintrag in speicher.auflisten(""):
			if _REST_MUSTER.search(eintrag) or _TEMP_MUSTER.search(eintrag):
				continue
			if eintrag.endswith("/"):
				continue
			groesse = speicher.groesse(eintrag)
			if groesse is None:
				continue
			anzahl += 1
			gesamt += groesse
		return anzahl, gesamt
	except Exception:  # noqa: BLE001 — Nachweis, kein Abbruchgrund
		return 0, 0


# ── Der ganze Vorgang ──────────────────────────────────────────────────────

#: Endung der Datenbank, in die eingespielt wird, bevor getauscht wird.
_NEU_SUFFIX = "_wiederherstellung"


@dataclass
class Datenbankbericht:
	"""Was das Einspielen der Datenbank ergeben hat."""

	dauer_sekunden: float = 0.0
	vorsicherung: str = ""
	vorsicherung_verzeichnis: str = ""
	alembic_vorher: str = ""
	alembic_nachher: str = ""
	soll: dict[str, int] = field(default_factory=dict)
	ist: dict[str, int] = field(default_factory=dict)
	eingespielt_in: str = ""
	"Die Datenbank, in die ``pg_restore`` geschrieben hat (bis zum Tausch)."
	alte_datenbank: str = ""
	"Name der alten Datenbank NACH dem Tausch (``<ziel>_vorher_<zeit>``)."
	getauscht: bool = False
	vorpruefung: dict[str, int] = field(default_factory=dict)
	"Zeilenzahlen der ZIELDATENBANK vor dem Austausch — fuer die Rueckfahrt."
	rueckfahrt_verzeichnis: str = ""
	"Ordner, in den die alte Datenbank Schreibtisch-reif ausgelagert wurde."
	vorher_datenbanken: list[str] = field(default_factory=list)
	"Datenbanken ``<ziel>_vorher_*``, die VOR dem Einspielen schon dastanden (M6)."
	ohne_vorsicherung: bool = False
	"Auf Wunsch des Betreibers OHNE Vorsicherung eingespielt (WARNUNG im Bericht)."
	umleitung: str = ""
	"Fehlt die Zieldatenbank, die ausgelagerte, die sie ersetzt (H1, Meldung)."

	@property
	def abweichungen(self) -> dict[str, tuple[int, int]]:
		"""Tabellen, deren Zeilenzahl nicht zum Dump-Index passt {name: (soll, ist)}.

		Soll ``-1`` heisst: die Tabelle steht im Dump, aber der Index nennt keine
		Datensatzmenge (``pg_dump --no-owner``) — dann gibt es nichts zu
		vergleichen statt einer falschen Abweichung.
		"""
		problem: dict[str, tuple[int, int]] = {}
		for tabelle, soll in self.soll.items():
			if soll < 0:
				continue
			ist = self.ist.get(tabelle, 0)
			if ist != soll:
				problem[tabelle] = (soll, ist)
		return problem


@dataclass
class Wiederherstellungsbericht:
	"""Der ganze Vorgang in Zahlen — Grundlage des Abnahmeprotokolls."""

	sicherung: str = ""
	verzeichnis: str = ""
	zeitpunkt: str = ""
	"Iso-Zeitpunkt des Beginns — Stichtag fuer die Protokollzeilen (M1)."
	dauer_sekunden: float = 0.0
	dauer_dateien: float = 0.0
	datenbank: Datenbankbericht = field(default_factory=Datenbankbericht)
	dateien: Dateibericht = field(default_factory=Dateibericht)
	meldungen: list[str] = field(default_factory=list)


def _vorsicherung(name: str, meldungen: list[str]) -> tuple[str, str]:
	"""Den JETZIGEN Stand sichern (Rueckfahrt) — ueber den normalen Sicherungslauf.

	Opus-Befund H3: ein ``dump.sichere()`` am Sicherungslauf vorbei schreibt
	zwar eine vollstaendige Sicherung, aber OHNE Sperre und OHNE Zeile in
	``sicherungslauf`` — die Oberflaeche zeigt sie nie, und ein gleichzeitiger
	Scheduler-Lauf koennte dazwischenfunken. Deshalb ``lauf.fuehre_aus``:
	``Sicherungssperre``, Protokollzeile, Aufbewahrung, Meldung an die System
	Manager bei Fehlschlag.

	Rueckgabe: ``(Name, Verzeichnis)`` der geschriebenen Sicherung.
	"""
	from diakronos_app.sicherung import lauf as laufmodul

	try:
		ergebnis = laufmodul.fuehre_aus(ausloeser=laufmodul.AUSLOESER_MANUELL)
	except Exception as fehler:  # noqa: BLE001 — Grund nennen, nicht verschweigen
		raise WiederherstellungsFehler(
			"Die Vorsicherung des aktuellen Standes ist fehlgeschlagen "
			f"({type(fehler).__name__}) — es wurde nichts eingespielt. "
			"Mit --ohne-vorsicherung laesst sich das bewusst ueberspringen."
		) from fehler
	if not ergebnis.ok or not ergebnis.name:
		raise WiederherstellungsFehler(
			"Die Vorsicherung des aktuellen Standes ist fehlgeschlagen "
			f"({ergebnis.meldung or 'kein Ergebnis'}) — es wurde nichts eingespielt. "
			"Mit --ohne-vorsicherung laesst sich das bewusst ueberspringen."
		)
	verzeichnis = cloud.lokale_basis() / ergebnis.name
	if not (verzeichnis / dump.FERTIG_NAME).is_file() and not cloud.ist_aktiv():
		raise WiederherstellungsFehler(
			f"Die Vorsicherung {ergebnis.name} liegt nicht als vollstaendige "
			"Sicherung vor — es wurde nichts eingespielt."
		)
	# Verbindungen des Sicherungslaufs SCHLIESSEN: der Lauf oeffnet eine eigene
	# SQLAlchemy-Sitzung und der Prozess haelt danach noch die Verbindung im
	# Pool — auf ``diakronos`` bleibt sie ``idle`` stehen. Fuer den Tausch
	# zaehlt genau das als „offene Verbindung“, und ``ALTER DATABASE`` scheitert
	# (im Wegwerf-Stack ABN-2b gemessen: die Vorsicherung war ihr eigener
	# Blocker). ``dispose()`` gibt den Pool frei; der Lauf ist fertig.
	try:
		from diakronos_app import db as dbmodul

		dbmodul.engine.dispose()
	except Exception:  # noqa: BLE001 — Aufraeumen, kein Abbruchgrund
		pass
	meldungen.append(f"Vorsicherung geschrieben: {ergebnis.name}")
	return ergebnis.name, str(verzeichnis)


def stelle_wieder_her(
	name: str,
	*,
	einspielen: bool = False,
	vorsicherung: bool = True,
	wiederholen: bool = False,
	dateien: bool = True,
	timeout: int | None = None,
	dateien_ziel: Path | None = None,
) -> Wiederherstellungsbericht:
	"""Eine Sicherung pruefen und (mit ``einspielen``) vollstaendig zurueckspielen.

	Ohne ``einspielen`` ist der Aufruf eine reine PRUEFUNG: Suche,
	Pruefsummen, lesbarer Dump, Zeilenzahlen aus dem Index. Es wird nichts
	geschrieben und nichts geloescht.

	Mit ``einspielen`` ist die Reihenfolge (Opus-Befund H2):

	1. Vorsicherung ueber den normalen Sicherungslauf (Pflicht, ausser
	   ``vorsicherung=False`` — dann WARNUNG in Meldungen und Bericht, M4).
	2. Fehlt die Zieldatenbank, wird das mit Rueckweg gemeldet, bevor
	   irgendetwas angelegt wird (H1). Vorhandene ``<ziel>_vorher_*`` werden
	   aufgelistet und genannt (M6) — geloescht wird keine.
	3. Einspielen in ``<ziel>_wiederherstellung``, Migration, Zaehlung — und
	   die PRUEFUNG der Zaehlung, BEVOR getauscht wird (M3).
	4. **Erst nach Erfolg** tauschen (in EINER Transaktion, H1): alte Datenbank
	   heisst danach ``<ziel>_vorher_<zeit>``. Sie wird NICHT geloescht.
	5. Dateiablage (lokal) aufaddierend zurueckschreiben.
	"""
	bericht = Wiederherstellungsbericht(sicherung=name)
	beginn = time.monotonic()
	# Stichtag fuer die Protokollzeilen (Opus-Befund M1): alles, was ab jetzt
	# beginnt, laeuft noch — die Vorsicherung dieses Vorgangs. NAIVE Ortszeit
	# (ABN-2c/H2): ``begonnen_am`` der Laeufe ist ebenfalls naiv, und ein
	# tz-behafteter Wert warf in ``sperre.raeume_abgebrochene_auf`` einen
	# TypeError — der das ganze ``commit`` samt OK-Eintrag verschluckte.
	beginn_zeit = _jetzt_ortszeit_naiv()
	if not aufbewahrung.ist_sicherungsname(name):
		raise WiederherstellungsFehler("Der Name muss die Form JJJJ-MM-TT_HHMMSS haben.")
	verzeichnis = _finde_sicherung(name, bericht.meldungen)
	bericht.verzeichnis = str(verzeichnis)
	bericht.datenbank.soll = pruefe_sicherung(verzeichnis, timeout=timeout)
	bekannt = sum(wert for wert in bericht.datenbank.soll.values() if wert >= 0)
	if bekannt:
		bericht.meldungen.append(
			f"Sicherung geprueft: {len(bericht.datenbank.soll)} Tabellen, "
			f"{bekannt} Datensaetze im Dump-Index."
		)
	else:
		bericht.meldungen.append(
			f"Sicherung geprueft: {len(bericht.datenbank.soll)} Tabellen im Dump "
			"(der Index nennt keine Datensatzmengen — pg_dump --no-owner)."
		)
	if not einspielen:
		bericht.dauer_sekunden = time.monotonic() - beginn
		return bericht

	bericht.datenbank.ohne_vorsicherung = not vorsicherung
	if vorsicherung:
		bericht.datenbank.vorsicherung, bericht.datenbank.vorsicherung_verzeichnis = (
			_vorsicherung(name, bericht.meldungen)
		)
	else:
		bericht.meldungen.append(
			"WARNUNG: Ohne Vorsicherung eingespielt (--ohne-vorsicherung) — es "
			"gibt KEINEN Stand des bisherigen Betriebs. Der bisherige Inhalt "
			"bleibt nur als <ziel>_vorher_<zeit> erhalten und ist ohne "
			"funktionierende Sicherung der einzige Rueckweg."
		)
	try:
		bericht.datenbank.alembic_vorher = alembic_version(timeout=timeout)
	except WiederherstellungsFehler:
		bericht.datenbank.alembic_vorher = ""

	db_beginn = time.monotonic()
	# Ziel-Datenbank aus der Konfiguration — hier zweimal dieselbe Quelle fuer
	# pg_restore und alembic (Opus-Befund M4).
	env, zielname, _besitzer = _pg_umgebung()
	# H1: fehlt die Zieldatenbank, ist ein frueherer Tausch stehen geblieben —
	# das wird JETZT mit Rueckweg gemeldet, nicht als „does not exist“ mitten
	# im Lauf. Liegt eine ausgelagerte daneben, nennt der Bericht sie.
	umleitung = finde_umleitung(zielname)
	if umleitung:
		raise WiederherstellungsFehler(
			f"Die Datenbank {zielname} fehlt — ein frueherer Tausch ist in der "
			f"Mitte stehen geblieben; die alte Datenbank liegt als {umleitung} "
			"daneben und ist unversehrt. Rueckweg: "
			f"{_rueckweg_befehl(umleitung, zielname)} — erst danach wiederholen."
		)
	# M6: liegen schon ausgelagerte Staende daneben, werden sie genannt (und
	# kosten Platz) — geloescht wird KEINE.
	bericht.datenbank.vorher_datenbanken = _vorher_datenbanken(zielname, timeout=timeout)
	if bericht.datenbank.vorher_datenbanken:
		bericht.meldungen.append(
			f"{len(bericht.datenbank.vorher_datenbanken)} fruehere Datenbank(en) "
			"liegen unter " + ", ".join(bericht.datenbank.vorher_datenbanken)
			+ " und belegen Platz. Geloescht wird keine — nach der Stichprobe "
			"ausdruecklich verwerfen (BETRIEBSANLEITUNG 14.4, Schritt 8): "
			"DROP DATABASE \"<name>\"."
		)
	try:
		bericht.datenbank.vorpruefung = tabellenstaende(timeout=timeout)
	except WiederherstellungsFehler:
		bericht.datenbank.vorpruefung = {}
	neu = _spiele_in_neue_datenbank(verzeichnis / dump.DUMP_NAME, timeout=timeout)
	bericht.datenbank.eingespielt_in = neu
	# Migration und Zaehlung laufen gegen die NEUE Datenbank — die alte steht
	# bis zum Tausch unberuehrt daneben.
	bericht.datenbank.alembic_nachher = migriere_nach(
		verzeichnis, timeout=timeout, datenbank=neu,
	)
	bericht.datenbank.ist = tabellenstaende(timeout=timeout, datenbank=neu)
	bericht.datenbank.dauer_sekunden = time.monotonic() - db_beginn

	# M3: die Pruefung VOR dem Tausch. Bisher wurde erst in ``main`` nach dem
	# Tausch gemeckert — dann war die neue (abweichende) Datenbank schon
	# aktiv, und der Rueckweg war Handarbeit. Jetzt bleibt die alte aktiv.
	abweichungen = bericht.datenbank.abweichungen
	fehlend = _fehlende_schemaversion(bericht.datenbank.alembic_nachher)
	if abweichungen or fehlend:
		gruende = []
		if fehlend:
			gruende.append(
				"die eingespielte Datenbank hat keine brauchbare "
				"alembic_version (leer) — das Schema ist nicht belegt"
			)
		if abweichungen:
			gruende.append(
				f"{len(abweichungen)} Tabellen weichen vom Dump-Index ab: "
				+ ", ".join(f"{name_} (Dump {soll}, DB {ist})"
				            for name_, (soll, ist) in sorted(abweichungen.items()))
			)
		raise WiederherstellungsFehler(
			"ABBRUCH VOR DEM TAUSCH — " + "; ".join(gruende) + ". Die "
			f"eingespielte Datenbank {neu} wurde NICHT aktiviert, {zielname} "
			"laeuft unveraendert weiter. Ursache pruefen; die Nachpruefung "
			f"laesst sich mit tabellenstaende(datenbank='{neu}') wiederholen."
		)

	# ERST JETZT tauschen: der Dump ist eingespielt, migriert, gezaehlt und
	# geprueft.
	bericht.datenbank.alte_datenbank = tausche_datenbank(neu, ziel=zielname,
	                                                     timeout=timeout)
	bericht.datenbank.getauscht = True
	bericht.meldungen.append(
		f"Datenbank getauscht: aktiv ist {zielname}, die alte liegt als "
		f"{bericht.datenbank.alte_datenbank} daneben (nicht geloescht)."
	)
	if bericht.datenbank.vorsicherung:
		# WICHTIG (im Wegwerf-Stack ABN-2b gemessen): die Vorsicherung wurde
		# VOR dem Tausch geschrieben — ihre Protokollzeile steht damit in der
		# ALTEN Datenbank und ist nach dem Tausch nicht mehr in der
		# Oberflaeche. Die Sicherung selbst liegt vollstaendig auf der Platte.
		# Deshalb hier ausdruecklich nennen, samt Bedienhinweis: sonst sucht
		# der Betreiber eine Sicherung, die er nur noch im Verzeichnis findet.
		bericht.meldungen.append(
			f"ACHTUNG: Die Vorsicherung {bericht.datenbank.vorsicherung} liegt "
			f"vollstaendig unter {bericht.datenbank.vorsicherung_verzeichnis} — "
			"ihre Protokollzeile steht aber im ausgetauschten (alten) Stand. "
			"Sie erscheint NICHT in der Sicherungsliste; zum Wiederherstellen "
			"den Ordner nach data/sicherungen/ kopieren und dort aufrufen."
		)

	# Die Dateien NACH der Datenbank: erst wenn der Dump steht, ist klar, ob
	# die Verweise der Datenbank zu den Dateien passen (Nachweis im Bericht).
	if dateien:
		datei_beginn = time.monotonic()
		bericht.dateien = spiele_dateien_ein(
			verzeichnis / dump.ARCHIV_NAME, wiederholen=wiederholen,
			ziel_wurzel=dateien_ziel,
		)
		bericht.dauer_dateien = time.monotonic() - datei_beginn
		bericht.meldungen.append(
			f"Dateiablage: {bericht.dateien.dateien} Dateien geschrieben "
			f"({bericht.dateien.bytes} Bytes), {bericht.dateien.uebersprungen} "
			f"unveraendert, {len(bericht.dateien.verworfen)} verworfen "
			f"(lokal: {bericht.dateien.ziel_wurzel})."
		)
		if bericht.dateien.eigentuemer_falsch:
			bericht.meldungen.append(
				f"WARNUNG: {bericht.dateien.eigentuemer_falsch} Dateien gehoeren root — "
				"der Dienst kann sie nicht lesen. Die Wiederherstellung als "
				"Dienst-Benutzer (appuser) ausfuehren, nicht als root."
			)
	bericht.dauer_sekunden = time.monotonic() - beginn
	bericht.zeitpunkt = beginn_zeit.isoformat(timespec="seconds")
	return bericht


def _finde_sicherung(name: str, meldungen: list[str]) -> Path:
	"""Lokales Verzeichnis der Sicherung — im Nextcloud-Modus notfalls holen."""
	kandidat = dump.ziel_basis() / name
	if (kandidat / dump.DUMP_NAME).is_file():
		return kandidat
	if cloud.ist_aktiv():
		meldungen.append(f"Sicherung {name} wird aus der Ablage geholt ...")
		try:
			return hole_lokal(name)
		except WiederherstellungsFehler:
			raise
		except Exception as fehler:  # noqa: BLE001
			raise WiederherstellungsFehler(
				f"Die Sicherung {name} konnte nicht geholt werden "
				f"({type(fehler).__name__})."
			) from None
	raise WiederherstellungsFehler(
		f"Die Sicherung {name} liegt nicht im Sicherungsverzeichnis."
	)


# ── CLI ────────────────────────────────────────────────────────────────────

def _menschengroesse(wert: int) -> str:
	einheiten = ("Bytes", "KiB", "MiB", "GiB", "TiB")
	rest = float(wert)
	for einheit in einheiten:
		if rest < 1024 or einheit == einheiten[-1]:
			return f"{rest:.1f} {einheit}" if einheit != "Bytes" else f"{wert} Bytes"
		rest /= 1024
	return f"{wert} Bytes"  # pragma: no cover


def _drucke_bericht(bericht: Wiederherstellungsbericht) -> None:
	print(f"Sicherung: {bericht.sicherung}")
	print(f"Verzeichnis: {bericht.verzeichnis}")
	for meldung in bericht.meldungen:
		print(f"  - {meldung}")
	bank = bericht.datenbank
	if bank.soll:
		print("Tabelle".ljust(44) + "Dump".rjust(8) + "DB".rjust(10))
		for tabelle in sorted(bank.soll):
			ist = bank.ist.get(tabelle, 0) if bank.ist else 0
			soll = bank.soll[tabelle]
			soll_text = "?" if soll < 0 else str(soll)
			marke = "" if (not bank.ist or soll < 0 or ist == soll) else "  ABWEICHUNG"
			print(f"{tabelle:<44}{soll_text:>8}{ist if bank.ist else '-':>10}{marke}")
	if bank.alembic_vorher or bank.alembic_nachher:
		print(f"alembic: vorher {bank.alembic_vorher or '-'} -> nachher {bank.alembic_nachher or '-'}")
	if bank.vorsicherung:
		print(f"Vorsicherung: {bank.vorsicherung}")
	if bank.ist:
		print(f"Datenbank eingespielt in {bank.dauer_sekunden:.1f} s")
	if bank.alte_datenbank:
		print(f"Alte Datenbank liegt als {bank.alte_datenbank} daneben (nicht geloescht).")
	if bank.vorher_datenbanken:
		print(f"Aeltere ausgelagerte Staende: {', '.join(bank.vorher_datenbanken)} "
		      "(nicht geloescht).")
	if bank.ohne_vorsicherung:
		print("WARNUNG: OHNE VORSICHERUNG eingespielt (--ohne-vorsicherung) — es "
		      "gibt keinen Stand des bisherigen Betriebs.")
	if bericht.dateien.dateien or bericht.dateien.uebersprungen:
		print(
			f"Dateiablage: {bericht.dateien.dateien} Dateien "
			f"({_menschengroesse(bericht.dateien.bytes)}) in "
			f"{bericht.dauer_dateien:.1f} s, {bericht.dateien.uebersprungen} unveraendert"
		)
		for verworfen in bericht.dateien.verworfen[:10]:
			print(f"  verworfen: {verworfen}")
	print(f"Gesamtdauer: {bericht.dauer_sekunden:.1f} s")


def _pg_mass() -> tuple[str, str, str]:
	"""``(Dienstname, Datenbankname, Benutzer)`` aus der Konfiguration (Opus-Befund M5)."""
	try:
		from diakronos_app.settings import settings

		name = settings.backup_db_name or _verbindung_aus_url(
			settings.database_url or "",
		)["datenbank"] or "diakronos"
		benutzer = settings.backup_db_user or _verbindung_aus_url(
			settings.database_url or "",
		)["benutzer"] or "diakronos"
		# Der Verwaltungsweg laeuft im db-Dienst des Stacks; Hostname dort ist
		# der Compose-Dienstname. Bleibt die URL auf `db`, ist es derselbe.
		dienst = "db"
	except Exception:  # noqa: BLE001 — Ersatzplan fuer den Handweg
		return "db", "diakronos", "diakronos"
	return dienst, str(name), str(benutzer)


def _drucke_zeitplan(bericht: Wiederherstellungsbericht) -> None:
	"""Die Schritte, die das Werkzeug NICHT tun kann — zum Abarbeiten von Hand.

	WARUM DAS HIER STEHT (ABN-2b): Das Werkzeug braucht diesen Weg NICHT mehr
	(``DROP``/``CREATE``/``ALTER DATABASE`` gehen ueber den Datenbanktreiber im
	Image). Ausgedruckt wird er auf Wunsch (``--zeitplan``), damit der Ablauf
	auch ohne das Werkzeug nachvollziehbar und im ``db``-Dienst nachfahrbar ist
	— und weil er in der Betriebsanleitung steht.

	Der Handweg ist derselbe Ablauf wie im Werkzeug (Opus-Befund H2): in eine
	NEUE Datenbank einspielen, migrieren, pruefen, erst dann tauschen — die
	alte bleibt unter ``<ziel>_vorher_<zeit>`` stehen. Die Verbindung
	(``-U <benutzer>``) und der Datenbankname kommen aus der Konfiguration,
	die Zeilenfortsetzung ist ein einfacher ``\\`` (Opus-Befund M5).
	"""
	# Der Handweg braucht den Zeilenfortsetzungs-Backslash: ein Literal, das
	# genau EIN Zeichen ist (kein Paar, das die Shell zu einem Backslash macht).
	fortsetzung = chr(92)
	# Doppelte Anfuehrungszeichen fuer die Shell, die den Stempel setzt (L8).
	# Die Zeilen werden in ``sh`` ausgefuehrt: ``"$(date …)"`` wird zur
	# Stempel-Zeichenkette, das SQL bekommt sie ungequotet — der Stempel ist
	# reines ``[0-9_]``, also unbedenklich.
	doppelt = '"'
	dienst, zieldb, benutzer = _pg_mass()
	neu = f"{zieldb}{_NEU_SUFFIX}"
	print()
	print("Weiter mit der Datenbank — im db-Dienst des Stacks (dort liegen psql")
	print("und pg_restore). Reihenfolge: erst einspielen, dann zaehlen/pruefen,")
	print("dann tauschen:")
	print("  # vorher: in der Oberflaeche unter Einstellungen -> Datensicherung")
	print("  #         auf 'Jetzt sichern' (die Vorsicherung)")
	print("  docker compose stop app worker scheduler")
	print(f"  docker compose exec -T {dienst} psql -U {benutzer} -d postgres -c "
	      f"{doppelt}DROP DATABASE IF EXISTS {neu} WITH (FORCE){doppelt}")
	print(f"  docker compose exec -T {dienst} psql -U {benutzer} -d postgres -c "
	      f"{doppelt}CREATE DATABASE {neu}{doppelt}")
	print(f"  docker compose exec -T {dienst} pg_restore -U {benutzer} -d {neu} "
	      f"--no-owner --exit-on-error --single-transaction {fortsetzung}")
	print(f"    < {bericht.verzeichnis or 'data/sicherungen/<name>'}/db.dump")
	print("  # Migrationen und Zaehlung GEGEN DIE NEUE Datenbank — erst pruefen,")
	print("  # dann tauschen (die Zaehlung muss zum Dump-Index passen):")
	print(f"  docker compose exec -T {dienst} psql -U {benutzer} -d {neu} -c "
	      f"{doppelt}SELECT version_num FROM alembic_version{doppelt}")
	print(f"  docker compose exec -T {dienst} psql -U {benutzer} -d {neu} -c "
	      f"{doppelt}SELECT count(*) FROM mitglied{doppelt}")
	print(f"  docker compose exec -T {dienst} psql -U {benutzer} -d {neu} -c "
	      f"{doppelt}SELECT count(*) FROM gruppe{doppelt}")
	print("  # stimmen die Zahlen, dann tauschen (das Werkzeug prueft offene")
	print("  # Verbindungen und tauscht in EINER Transaktion):")
	print(f"  docker compose run --rm --no-deps -u appuser app python -m "
	      f"{__name__} {bericht.sicherung} --tausch {zieldb}")
	print("  # Notausgang ohne das Werkzeug (nur wenn Sie wissen, was Sie tun):")
	print("  #   beide RENAMEs in EINER Transaktion — sonst gibt es einen Moment")
	print("  #   ohne Zieldatenbank. Der Stempel kommt aus der Shell.")
	print(f"  docker compose exec -T {dienst} psql -U {benutzer} -d postgres "
	      f"--single-transaction -c {doppelt}ALTER DATABASE {zieldb} RENAME TO "
	      f"{zieldb}_vorher_$(date +%Y%m%d_%H%M%S); "
	      f"ALTER DATABASE {neu} RENAME TO {zieldb}{doppelt}")
	print("  docker compose start app worker scheduler")
	print()
	print("Die Dump-Datei liegt auf dem HOST (data/sicherungen/...) — im db-Container")
	print("gibt es sie nicht; deshalb die Umleitung aus dem Projektordner.")
	print("Die alte Datenbank wird NICHT geloescht: sie heisst danach")
	print(f"{zieldb}_vorher_... und wird erst nach der Stichprobe verworfen.")


def _jetzt_ortszeit_naiv() -> datetime:
	"""Jetzt in Ortszeit — NAIV, wie ``Sicherungslauf.begonnen_am`` (ABN-2c/H2).

	``datetime.now().astimezone()`` liefert einen tz-BEHAFTETEN Wert; der
	Vergleich mit ``begonnen_am`` (naiv, aus ``einstellungen.jetzt_ortszeit``)
	warf in ``sperre.raeume_abgebrochene_auf`` einen TypeError. Der wurde
	verschluckt — und mit ihm das ``commit``: auch der ``ok``-Eintrag der
	eingespielten Sicherung ging verloren.

	Faellt die Naht ``jetzt_ortszeit`` aus (Import-Zeitpunkt, Testersatz),
	gilt die Ortszeit aus ``datetime.now().astimezone()`` ohne tz-Anteil —
	dieselbe Zone, dieselbe Vergleichbarkeit.
	"""
	try:
		from diakronos_app.sicherung.einstellungen import jetzt_ortszeit

		jetzt = jetzt_ortszeit()
	except Exception:  # noqa: BLE001 — Notnagel, kein Abbruchgrund
		jetzt = datetime.now().astimezone()
	if jetzt.tzinfo is not None:
		jetzt = jetzt.replace(tzinfo=None)
	return jetzt


def _fehlende_schemaversion(alembic_nachher: str) -> bool:
	"""Ist die ``alembic_version`` der eingespielten Datenbank leer (M3)?

	Eine Sicherung ohne lesbare Schemaversion ist kein belegter Stand: die
	Migration hat nichts hinterlassen ODER die Tabelle fehlt. Beides darf nicht
	durch einen Tausch zur aktiven Datenbank werden.
	"""
	return not str(alembic_nachher or "").strip()


def _stichtag(bericht: Wiederherstellungsbericht) -> datetime | None:
	"""Der Beginn des Vorgangs aus dem Bericht (fuer die Protokollzeilen).

	Der Zeitpunkt wird ebenfalls NAIV geliefert (H2): ein tz-behafteter Wert
	warf beim Vergleich mit ``begonnen_am`` einen TypeError.
	"""
	if not bericht.zeitpunkt:
		return None
	try:
		zeitpunkt = datetime.fromisoformat(bericht.zeitpunkt)
	except ValueError:
		return None
	return zeitpunkt.replace(tzinfo=None) if zeitpunkt.tzinfo is not None else zeitpunkt


def _stelle_anzeige_wieder_her(name: str, *,
                               stichtag: datetime | None = None) -> None:
	"""Nach dem Einspielen der Datenbank: die Protokollzeile der Sicherung.

	Der Dump wurde waehrend des Sicherns geschrieben — seine eigene Zeile in
	``sicherungslauf`` steht deshalb oft noch auf ``laeuft``. Ohne diesen
	Schritt meldet die Oberflaeche die Sicherung als abgebrochen und die
	naechste automatische Sicherung meldet „Es laeuft bereits eine Sicherung“.

	``stichtag`` (Opus-Befund M1): der BEGINN der Wiederherstellung. Laeufe,
	die spaeter begannen (die Vorsicherung, die dieser Vorgang gerade
	gestartet hat), laufen noch — sie duerfen NICHT als fehlgeschlagen
	gemeldet werden. Läufe aus dem eingespielten Dump (aelter) werden
	geschlossen; die eingespielte Sicherung selbst ausdruecklich als ``ok``.
	"""
	try:
		from diakronos_app import db
		from diakronos_app.sicherung import sperre

		sitzung = db.SessionLocal()
		try:
			sperre.raeume_abgebrochene_auf(
				sitzung,
				nicht_ab_vor=stichtag,
				abschliessen=(name,) if name else (),
			)
		finally:
			sitzung.close()
	except Exception as fehler:  # noqa: BLE001 — Anzeige, kein Abbruch
		print(
			"Hinweis: die Protokollzeile der Sicherung liess sich nicht "
			f"berichtigen ({type(fehler).__name__}). Die Daten sind eingespielt; "
			"die Oberflaeche zeigt den Lauf ggf. als abgebrochen.",
			file=sys.stderr,
		)
	else:
		print(f"Protokollzeile der Sicherung {name} berichtigt (abgebrochene Laeufe"
		      " geschlossen).")


def main(argv: list[str] | None = None) -> int:
	"""CLI-Einstieg (``python -m diakronos_app.sicherung.wiederherstellen``)."""
	parser = argparse.ArgumentParser(
		prog="python -m diakronos_app.sicherung.wiederherstellen",
		description=(
			"Eine Sicherung pruefen und — mit --einspielen — Datenbank UND "
			"Dateiablage vollstaendig zurueckspielen."
		),
	)
	parser.add_argument("name", nargs="?", default=None,
	                    help="Sicherung (JJJJ-MM-TT_HHMMSS). Ohne Angabe: die juengste.")
	parser.add_argument("--liste", action="store_true",
	                    help="Nur die vorhandenen Sicherungen anzeigen.")
	parser.add_argument("--pruefen", action="store_true",
	                    help="Nur pruefen (Pruefsummen, Dump-Index) — nichts einspielen.")
	parser.add_argument("--einspielen", action="store_true",
	                    help="Datenbank UND Dateiablage wirklich ersetzen.")
	parser.add_argument("--dateien-einspielen", action="store_true",
	                    help=(
	                        "NUR die Dateiablage einspielen (Datenbank bleibt). "
	                        "Der belegte Weg im Betrieb: Datenbank im db-Dienst, "
	                        "Dateien hier."
	                    ))
	parser.add_argument("--zeitplan", action="store_true",
	                    help=(
	                        "Den Handweg im db-Dienst ausdrucken und beenden "
	                        "(zum Nachvollziehen; --einspielen braucht ihn nicht)."
	                    ))
	parser.add_argument("--tausch", default=None, metavar="ZIELDATENBANK",
	                    help=(
	                        "Die zuletzt eingespielte Datenbank '<ziel>_wiederherstellung' "
	                        "gegen die Zieldatenbank tauschen (Handweg im db-Dienst)."
	                    ))
	parser.add_argument("--ohne-vorsicherung", action="store_true",
	                    help="Keine Vorsicherung des aktuellen Standes anlegen (Vorsicht).")
	parser.add_argument("--ohne-dateien", action="store_true",
	                    help="Nur die Datenbank einspielen, die Dateiablage unberuehrt lassen.")
	parser.add_argument("--wiederholen", action="store_true",
	                    help="Jede Datei der Ablage neu schreiben, auch wenn sie gleich ist.")
	parser.add_argument("--dateien-ziel", default=None,
	                    help="Zielordner der Dateiablage (Default: FILES_DIR).")
	parser.add_argument("--timeout", type=int, default=None,
	                    help="Zeitgrenze je Schritt in Sekunden (Default: keine).")
	args = parser.parse_args(argv)

	if args.liste:
		vorhanden = cloud.sicherungen_auflisten() if cloud.ist_aktiv() else []
		if not vorhanden:
			# Lokal-Modus: die Verzeichnisse im Sicherungsordner sind die Liste.
			basis = dump.ziel_basis()
			lokal = sorted(
				p.name for p in basis.iterdir()
				if p.is_dir() and aufbewahrung.ist_sicherungsname(p.name)
			) if basis.is_dir() else []
			if not lokal:
				print("Keine Sicherung gefunden.")
				return 0
			for name in lokal:
				voll = (basis / name / dump.FERTIG_NAME).is_file()
				print(f"{name}{'' if voll else '  (unvollstaendig)'}")
			return 0
		for name, groesse, zeitpunkt, voll in vorhanden:
			print(f"{name}  {groesse:>14} Bytes  {zeitpunkt}"
			      f"{'' if voll else '  (unvollstaendig)'}")
		return 0

	if args.zeitplan:
		_drucke_zeitplan(Wiederherstellungsbericht(sicherung=args.name or "", verzeichnis=""))
		return 0

	if args.tausch:
		try:
			alt = tausche_datenbank(f"{args.tausch}{_NEU_SUFFIX}", ziel=args.tausch,
			                        timeout=args.timeout)
		except WiederherstellungsFehler as fehler:
			print(f"Fehler: {fehler}", file=sys.stderr)
			return 1
		print(f"Datenbank getauscht: aktiv ist {args.tausch}, die alte liegt als "
		      f"{alt} daneben (nicht geloescht).")
		return 0

	name = args.name
	if name is None:
		vorhanden = cloud.sicherungen_auflisten() if cloud.ist_aktiv() else []
		# Nur eine VOLLSTAENDIGE Sicherung laesst sich wiederherstellen — ein
		# Rest aus einem abgebrochenen Upload ist keine.
		vorhanden = [eintrag for eintrag in vorhanden if eintrag[3]]
		if vorhanden:
			name = vorhanden[-1][0]
			print(f"Juengste Sicherung: {name}")
		else:
			name = _juengste_lokale()
			if name is None:
				print("Keine Sicherung gefunden.", file=sys.stderr)
				return 1
			print(f"Juengste Sicherung: {name}")

	if args.dateien_ziel and not (args.einspielen or args.dateien_einspielen):
		print("Fehler: --dateien-ziel wirkt nur zusammen mit --einspielen "
		      "oder --dateien-einspielen.", file=sys.stderr)
		return 2

	if args.dateien_einspielen and args.einspielen:
		print("Fehler: --dateien-einspielen und --einspielen schliessen sich aus "
		      "(--einspielen umfasst beides).", file=sys.stderr)
		return 2

	ziel = Path(args.dateien_ziel) if args.dateien_ziel else None
	if args.dateien_einspielen:
		return _nur_dateien(name, wiederholen=args.wiederholen, timeout=args.timeout,
		                    dateien_ziel=ziel)

	try:
		if not args.einspielen:
			# Reine Pruefung: der bisherige Aufruf bleibt damit vertraeglich
			# (er hat nie etwas eingespielt) — nur mit echten Vorpruefungen.
			bericht = stelle_wieder_her(name, einspielen=False, timeout=args.timeout)
			_drucke_bericht(bericht)
			print(
				"Geprueft, NICHT eingespielt. Zum Einspielen: --einspielen "
				"(ersetzt Datenbank und Dateiablage!) — oder, wenn die Datenbank "
				"im db-Dienst eingespielt wird, --dateien-einspielen."
			)
			return 0
		bericht = stelle_wieder_her(
			name,
			einspielen=True,
			vorsicherung=not args.ohne_vorsicherung,
			wiederholen=args.wiederholen,
			dateien=not args.ohne_dateien,
			timeout=args.timeout,
			dateien_ziel=ziel,
		)
	except WiederherstellungsFehler as fehler:
		print(f"Fehler: {fehler}", file=sys.stderr)
		if args.einspielen and _werkzeug_fehlt(fehler):
			# Kein psql im Image: der Weg ist nicht kaputt, nur im falschen
			# Werkzeug — den dokumentierten Weg nennen statt nur zu meckern.
			bericht = Wiederherstellungsbericht(sicherung=name)
			_drucke_zeitplan(bericht)
		return 1
	except Exception as fehler:  # noqa: BLE001 — z. B. Ablage nicht erreichbar
		print(f"Fehler: {type(fehler).__name__}: {fehler}", file=sys.stderr)
		return 2
	_drucke_bericht(bericht)
	# Protokollzeile berichtigen: der Dump enthaelt sie im Zustand ``laeuft``.
	# Erst JETZT, nach erfolgreichem Tausch — und ohne den gerade laufenden
	# Vorsicherungslauf als Fehlschlag zu markieren (Opus-Befund M1).
	_stelle_anzeige_wieder_her(name, stichtag=_stichtag(bericht))
	# Die Pruefung der Zeilenzahlen ist mit ABN-2c/M3 VOR dem Tausch gelaufen
	# (``stelle_wieder_her`` bricht dort ab). Hier steht nur noch die
	# Bestaetigung — die Schutzpruefung bleibt, falls der Weg sich aendert.
	abweichungen = bericht.datenbank.abweichungen
	if abweichungen:
		print(
			f"ACHTUNG: {len(abweichungen)} Tabellen weichen vom Dump-Index ab: "
			+ ", ".join(f"{name_} (Dump {soll}, DB {ist})"
			            for name_, (soll, ist) in sorted(abweichungen.items())),
			file=sys.stderr,
		)
		return 1
	print("Wiederherstellung abgeschlossen: Zeilenzahlen stimmen mit dem Dump-Index "
	      "ueberein (vor dem Tausch geprueft).")
	if bericht.datenbank.alte_datenbank:
		print(
			f"Die alte Datenbank liegt als {bericht.datenbank.alte_datenbank} daneben. "
			"Sie wird NICHT automatisch geloescht: nach der Stichprobe (BETRIEBSANLEITUNG "
			"14.4, Schritt 8) ausdruecklich verwerfen — DROP DATABASE "
			f"\"{bericht.datenbank.alte_datenbank}\"."
		)
	return 0


def _werkzeug_fehlt(fehler: Exception) -> bool:  # noqa: ARG001 — Aufrufstelle bleibt
	"""Gibt es einen Ersatzplan, den der Aufrufer von Hand gehen muesste?

	Seit ABN-2b: **nein**. Fehlt ``psql`` im Image, gehen ``DROP``/``CREATE``/
	``ALTER DATABASE`` ueber den Datenbanktreiber (:func:`_sql`) — der Weg
	funktioniert dann ohne Zutun. Fruehere Fassungen nannten hier einen
	Handweg im ``db``-Dienst; der wird nur noch freiwillig gedruckt
	(``--zeitplan``), nicht als Ausrede fuer einen Abbruch.
	"""
	return False


def _nur_dateien(name: str, *, wiederholen: bool, timeout: int | None,
                 dateien_ziel: Path | None = None) -> int:
	"""``--dateien-einspielen``: Sicherung pruefen, NUR die Ablage zurueckschreiben.

	Auch hier wird die Protokollzeile berichtigt — aber nur fuer Zeilen, die
	VOR diesem Aufruf begannen (``stichtag``): ein gerade laufender
	Sicherungslauf bleibt ``laeuft`` (Opus-Befund M1).
	"""
	# Stichtag wie in ``stelle_wieder_her``: NAIVE Ortszeit (ABN-2c/H2), sonst
	# wirft der Vergleich mit ``begonnen_am`` einen TypeError.
	stichtag = _jetzt_ortszeit_naiv()
	meldungen: list[str] = []
	try:
		verzeichnis = _finde_sicherung(name, meldungen)
		pruefe_sicherung(verzeichnis, timeout=timeout)
	except WiederherstellungsFehler as fehler:
		print(f"Fehler: {fehler}", file=sys.stderr)
		return 1
	for meldung in meldungen:
		print(f"  - {meldung}")
	beginn = time.monotonic()
	try:
		bericht = spiele_dateien_ein(verzeichnis / dump.ARCHIV_NAME,
		                             wiederholen=wiederholen,
		                             ziel_wurzel=dateien_ziel)
	except WiederherstellungsFehler as fehler:
		print(f"Fehler: {fehler}", file=sys.stderr)
		return 1
	dauer = time.monotonic() - beginn
	print(f"Sicherung: {name}")
	print(f"Dateiablage: {bericht.dateien} Dateien "
	      f"({_menschengroesse(bericht.bytes)}) in {dauer:.1f} s, "
	      f"{bericht.uebersprungen} unveraendert, {len(bericht.verworfen)} verworfen "
	      f"(lokal: {bericht.ziel_wurzel})")
	if bericht.eigentuemer_falsch:
		print(
			f"WARNUNG: {bericht.eigentuemer_falsch} Dateien gehoeren root — der "
			"Dienst kann sie nicht lesen. Als Dienst-Benutzer (appuser) ausfuehren.",
			file=sys.stderr,
		)
	# Protokollzeile berichtigen (der Dump enthaelt sie im Zustand ``laeuft``).
	# Erst NACH dem Einspielen der Datenbank sinnvoll — hier nur, wenn die
	# Datenbank bereits den Stand der Sicherung hat (Aufruf direkt danach).
	_stelle_anzeige_wieder_her(name, stichtag=stichtag)
	print("Dateiablage eingespielt. Die Datenbank ist unberuehrt.")
	return 0


def _juengste_lokale() -> str | None:
	"""Die juengste vollstaendige Sicherung im lokalen Sicherungsordner."""
	basis = dump.ziel_basis()
	if not basis.is_dir():
		return None
	namen = sorted(
		p.name for p in basis.iterdir()
		if p.is_dir() and aufbewahrung.ist_sicherungsname(p.name)
		and (p / dump.FERTIG_NAME).is_file()
	)
	return namen[-1] if namen else None


if __name__ == "__main__":  # pragma: no cover — CLI-Einstieg
	raise SystemExit(main())
