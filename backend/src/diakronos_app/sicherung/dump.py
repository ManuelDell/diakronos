"""BACKUP-1: Datenbank-Dump und Dateiarchiv.

WAS HIER ENTSTEHT
-----------------
Ein Sicherungsverzeichnis ``<backup_dir>/JJJJ-MM-TT_HHMMSS/`` mit

    db.dump            PostgreSQL-Dump im Custom-Format (``pg_dump -Fc``)
    files.tar.gz       Archiv von ``DATA_DIR/files`` (Dateiablage der App)
    SHA256SUMS         Pruefsummen beider Dateien (``sha256sum``-Format)
    FERTIG             leere Markierung: der Lauf ist vollstaendig

Die Reihenfolge ist Absicht: zuerst wird in ein TEMPORAERES Verzeichnis neben
dem Ziel geschrieben (``.tmp-...``), am Ende wird umbenannt. Ein Betrachter
sieht also entweder gar nichts oder eine fertige Sicherung — nie einen halb
geschriebenen Dump unter dem richtigen Namen.

WOHIN DIE DATEN GEHEN
---------------------
``backup_dir`` MUSS im Daten-Bind-Mount liegen. Der gemeinsame Vorfahr von
``files_dir`` und ``backup_dir`` ist der Punkt, der im Container als Volume
haengt; ein Ziel ausserhalb davon waere im Image-Dateisystem und beim
naechsten Container weg (NACHTRAG DOCKER Punkt 4). ``pruefe_ziel`` weist das
ab, statt still zu sichern.

WAS NICHT IM LOG UND NICHT IN DER OBERFLAECHE LANDET (B4)
---------------------------------------------------------
Die Kommandozeile von ``pg_dump`` traegt Benutzer, Host und Port. Deshalb
bekommt ``pg_dump`` die Verbindung ueber ``PG*``-Umgebungsvariablen (nicht als
Argument: ``ps`` zeigt Argumente), und jede Fehlermeldung wird auf den
Exit-Code und die LETZTE Ausgabezeile ohne Zugangsdaten eingekuerzt.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.sicherung.dump")

#: Dateinamen im Sicherungsverzeichnis.
DUMP_NAME = "db.dump"
ARCHIV_NAME = "files.tar.gz"
PRUEFSUMMEN_NAME = "SHA256SUMS"
FERTIG_NAME = "FERTIG"

#: Praefix der temporaeren Verzeichnisse (werden nie als Sicherung gezaehlt).
TEMP_PRAEFIX = ".tmp-"

#: Rechte: Verzeichnis 0700, Dateien 0600 — Dumps enthalten alle
#: Personendaten (B4).
VERZEICHNIS_MODUS = 0o700
DATEI_MODUS = 0o600


class SicherungFehler(RuntimeError):
	"""Sicherung fehlgeschlagen — der Text ist die Meldung fuer die Oberflaeche."""


# ── Zielverzeichnis ────────────────────────────────────────────────────────

def ziel_basis() -> Path:
	"""Das Sicherungsverzeichnis aus den Einstellungen."""
	return Path(settings.backup_dir)


def gemeinsamer_elternpfad(a: Path, b: Path) -> Path:
	"""Tiefster gemeinsamer Vorfahr von ``a`` und ``b`` (ohne Wurzel)."""
	teile_a = a.resolve().parts
	teile_b = b.resolve().parts
	gemeinsam: list[str] = []
	for links, rechts in zip(teile_a, teile_b):
		if links != rechts:
			break
		gemeinsam.append(links)
	if not gemeinsam:
		return Path(teile_a[0] or "/")
	pfad = Path(*gemeinsam)
	return pfad if str(pfad) else Path("/")


def pruefe_ziel(basis: Path | None = None) -> Path:
	"""Stellt sicher, dass ``backup_dir`` im Datenbaum liegt und beschreibbar ist.

	"Im Datenbaum" heisst: der gemeinsame Vorfahr mit ``files_dir`` ist nicht
	die Wurzel ``/``. Liegt ``backup_dir`` z. B. unter ``/app/backups`` (also
	im Image) und ``files_dir`` unter ``/data/files``, ist der gemeinsame
	Vorfahr ``/`` — genau der Fall, den NACHTRAG DOCKER Punkt 4 verbietet.
	"""
	ziel = (basis or ziel_basis()).resolve()
	files = Path(settings.files_dir).resolve()
	if (
		str(ziel) == "/"
		or str(ziel).startswith("/app")
		# `/tmp` ist im Betrieb der verfaengliche Fall: es bietet sich als
		# Ablage an, ist aber nicht im Daten-Bind-Mount und nach einem Neustart
		# weg. Ausnahme: der TEST baut den Datenbaum selbst unter `/tmp` auf —
		# dann liegt `files_dir` ebenfalls dort (gemeinsamer Vorfahr geprueft
		# unten). Ein produktiver Stack hat `files_dir` nie unter `/tmp`.
		or (str(ziel).startswith("/tmp") and not str(files).startswith("/tmp"))
	):
		raise SicherungFehler(
			"Der Ablageort der Sicherungen liegt im Programmverzeichnis. "
			"Bitte BACKUP_DIR auf ein Verzeichnis im Daten-Ordner setzen."
		)
	if gemeinsamer_elternpfad(ziel, files) == Path("/"):
		raise SicherungFehler(
			"Der Ablageort der Sicherungen liegt nicht im Daten-Ordner. Ein "
			"Verzeichnis ausserhalb des Daten-Bind-Mounts ist nach einem "
			"Neustart des Containers verloren — bitte BACKUP_DIR richtig setzen."
		)
	try:
		ziel.mkdir(mode=VERZEICHNIS_MODUS, parents=True, exist_ok=True)
		os.chmod(ziel, VERZEICHNIS_MODUS)
	except OSError as fehler:
		raise SicherungFehler(
			"Der Ablageort der Sicherungen ist nicht beschreibbar."
		) from fehler
	# Schreibprobe: ein read-only Bind-Mount sieht wie ein Verzeichnis aus, ist
	# aber nicht beschreibbar. Ohne Probe faellt das erst mitten im Dump auf.
	probe = ziel / f"{TEMP_PRAEFIX}probe"
	try:
		probe.write_bytes(b"")
	finally:
		probe.unlink(missing_ok=True)
	return ziel


def neue_kennung(jetzt: datetime) -> str:
	"""``JJJJ-MM-TT_HHMMSS`` — Name von Verzeichnis und Protokollzeile."""
	return jetzt.strftime("%Y-%m-%d_%H%M%S")


#: Faktor auf die Groesse der letzten Sicherung, der frei sein muss. Der Dump
#: wird geschrieben, waehrend die Pruefsummen ihn schon lesen; ein Restrisiko
#: bleibt (Datenbank waechst), deshalb ist die Grenze bewusst grosszuegig.
PLATZ_FAKTOR = 2


def pruefe_platz(basis: Path) -> int:
	"""Vor dem Lauf pruefen, ob der freie Platz fuer die naechste Sicherung reicht.

	Vergleichsmass ist die **letzte vollstaendige Sicherung** unter ``basis``
	(``dump.verzeichnisgroesse``). Reicht der freie Platz nicht fuer
	``PLATZ_FAKTOR`` mal diese Groesse, wird abgebrochen — eine volle Platte
	mitten im Dump hinterlaesst einen Teil-Dump, und die *vorherige*
	Sicherung waere dann die letzte gute. Gibt es noch keine Sicherung,
	wird nicht geraten: dann laeuft der Lauf (die Schreibfehler melden sich
	ohnehin).

	Rueckgabe: der freie Platz in Bytes (fuer Log/Tests).
	"""
	frei = shutil.disk_usage(basis).free
	letzte: tuple[float, Path] | None = None
	for eintrag in sorted(basis.iterdir()) if basis.is_dir() else []:
		try:
			if not eintrag.is_dir() or not (eintrag / FERTIG_NAME).is_file():
				continue
			stempel = eintrag.stat().st_mtime
		except OSError:
			continue
		if letzte is None or stempel > letzte[0]:
			letzte = (stempel, eintrag)
	if letzte is None:
		return frei
	noetig = PLATZ_FAKTOR * verzeichnisgroesse(letzte[1])
	if frei < noetig:
		raise SicherungFehler(
			"Zu wenig freier Platz fuer die naechste Sicherung — es wurde "
			"nichts geschrieben. Bitte Platz schaffen (alte Sicherungen "
			"entfernen oder Aufbewahrung verkuerzen) und den Lauf wiederholen."
		)
	return frei


# ── Datenbank ──────────────────────────────────────────────────────────────

def _pg_env() -> dict[str, str]:
	"""``pg_dump``-Umgebung aus ``DATABASE_URL`` — ohne Argumente auf der Zeile.

	Unterstuetzte Form: ``postgresql+psycopg://USER:PASSWORT@HOST:PORT/DB``.
	Alles andere (z. B. SQLite in Tests) wird abgewiesen; dann gibt es keinen
	Datenbank-Dump, den ``pg_dump`` erzeugen koennte.

	DER HOST IM CONTAINER
	---------------------
	Im Betrieb ist ``PGHOST`` der Compose-Dienstname (``db``) — den loesen
	app UND scheduler auf, beide haengen am Compose-Netz (im Teststack am
	2026-10-20 geprueft). Fuer abweichende Verdrahtungen gibt es
	``BACKUP_DB_HOST`` / ``BACKUP_DB_PORT`` / ... Ohne diese Variablen bleibt
	es beim Namen aus der URL — das ist fuer einen Lauf im app-Container und
	fuer Tests richtig.
	"""
	from urllib.parse import unquote, urlparse

	roh = str(settings.database_url or "")
	if not roh.startswith(("postgresql", "postgres")):
		raise SicherungFehler(
			"Die Datenbank-Verbindung zeigt nicht auf PostgreSQL — pg_dump ist nicht anwendbar."
		)
	# SQLAlchemy-Treiberteil entfernen: `postgresql+psycopg://` -> `postgresql://`
	ohne_treiber = re.sub(r"^(postgresql|postgres)\+[^:]+://", r"\1://", roh)
	teile = urlparse(ohne_treiber)
	datenbank = (teile.path or "/").lstrip("/")
	env = {
		"PGHOST": (settings.backup_db_host or teile.hostname or "db"),
		"PGPORT": str(settings.backup_db_port or teile.port or 5432),
		"PGDATABASE": (settings.backup_db_name or datenbank or "diakronos"),
		"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
	}
	benutzer = settings.backup_db_user or (
		unquote(teile.username) if teile.username else ""
	)
	if benutzer:
		env["PGUSER"] = benutzer
	passwort = settings.backup_db_password or (
		unquote(teile.password) if teile.password else ""
	)
	if passwort:
		env["PGPASSWORD"] = passwort
	return env


#: Verzeichnis der PostgreSQL-Programme in den Debian-Images. Das Laufzeit-Image
#: traegt nur ``pg_dump``/``pg_restore`` (kein Paket, kein Perl) — der Wrapper
#: in ``/usr/bin`` fehlt dort, hier steht das Programm (BACKUP-1b, M3).
PG_PROGRAMM_VERZEICHNIS = Path("/usr/lib/postgresql/17/bin")


def pg_programm(name: str) -> str:
	"""Pfad zu ``pg_dump``/``pg_restore`` — Programmpfad zuerst, dann ``PATH``.

	Auf dem Entwicklungsrechner und in der Testumgebung liegt der Wrapper im
	``PATH``; im gebauten Image nicht. Beide Wege bleiben damit gueltig.
	"""
	kandidat = PG_PROGRAMM_VERZEICHNIS / name
	return str(kandidat) if kandidat.is_file() else name


def pg_dump_version() -> str:
	"""Version des mitgelieferten ``pg_dump`` (fuer die Betriebsanleitung)."""
	try:
		ausgabe = subprocess.run(
			[pg_programm("pg_dump"), "--version"], capture_output=True, text=True, timeout=30,
			check=False,
		)
	except (OSError, subprocess.SubprocessError):
		return "nicht vorhanden"
	return ausgabe.stdout.strip() or ausgabe.stderr.strip() or "unbekannt"


def schreibe_dump(ziel: Path, *, timeout: int | None = None) -> None:
	"""``pg_dump -Fc`` nach ``ziel`` (Datei wird per ``os.replace`` gesetzt)."""
	teil = ziel.with_name(ziel.name + ".part")
	kommando = [
		pg_programm("pg_dump"),
		"--format=custom",
		"--no-owner",
		"--no-privileges",
		"--file", str(teil),
	]
	try:
		ausgabe = subprocess.run(
			kommando,
			env=_pg_env(),
			capture_output=True,
			text=True,
			timeout=timeout if timeout and timeout > 0 else None,
			check=False,
		)
	except FileNotFoundError:
		raise SicherungFehler(
			"pg_dump ist im Programm nicht vorhanden — die Sicherung kann nicht laufen."
		) from None
	except subprocess.TimeoutExpired:
		teil.unlink(missing_ok=True)
		raise SicherungFehler("Der Datenbank-Dump hat zu lange gedauert und wurde abgebrochen.") from None
	if ausgabe.returncode != 0:
		teil.unlink(missing_ok=True)
		raise SicherungFehler(_dump_fehlertext(ausgabe))
	if not teil.is_file() or teil.stat().st_size == 0:
		teil.unlink(missing_ok=True)
		raise SicherungFehler("Der Datenbank-Dump ist leer geblieben.")
	os.chmod(teil, DATEI_MODUS)
	os.replace(teil, ziel)


def _dump_fehlertext(ausgabe: subprocess.CompletedProcess) -> str:
	"""Fehlermeldung OHNE Zugangsdaten und ohne Rechnernamen.

	``pg_dump`` schreibt Verbindungsdetails nach stderr — darunter den
	Hostnamen der Datenbank (`could not translate host name "db" ...`). Ein
	System Manager sieht die Meldung in der Oberflaeche; der Name des
	DB-Dienstes und die Ports gehoeren nicht dorthin (N2, BACKUP-1b).
	Gemeldet wird deshalb nur der Exit-Code und eine **Gattung** des Fehlers,
	die letzte Zeile geht ins Log.
	"""
	letzte = ""
	for zeile in (ausgabe.stderr or "").strip().splitlines()[::-1]:
		if zeile.strip():
			letzte = zeile.strip()
			break
	if letzte:
		logger.warning("pg_dump Exit %s: %s", ausgabe.returncode, letzte[:400])
	unten = letzte.lower()
	if "password" in unten or "authentication" in unten:
		grund = "Anmeldung an der Datenbank nicht moeglich"
	elif "translate host name" in unten or "could not connect" in unten or "connection" in unten:
		grund = "Die Datenbank ist nicht erreichbar"
	elif "permission denied" in unten:
		grund = "Keine Berechtigung fuer den Dump"
	else:
		grund = "Ursache siehe Protokoll"
	return f"Der Datenbank-Dump ist fehlgeschlagen (Exit {ausgabe.returncode}): {grund}."


# ── Dateiablage ────────────────────────────────────────────────────────────

def schreibe_dateiarchiv(ziel: Path, quelle: Path | None = None) -> None:
	"""``DATA_DIR/files`` als ``tar.gz`` — Pfade relativ zum Ordner ``files``.

	Ein leeres oder fehlendes Quellverzeichnis ergibt ein Archiv ohne
	Eintraege. Das ist Absicht: eine Gemeinde ohne Uploads soll nicht daran
	scheitern, dass es nichts zu sichern gibt.
	"""
	quelle = Path(quelle or settings.files_dir)
	teil = ziel.with_name(ziel.name + ".part")
	try:
		with tarfile.open(teil, "w:gz") as archiv:
			if quelle.is_dir():
				for eintrag in sorted(quelle.rglob("*")):
					if eintrag.is_file():
						archiv.add(eintrag, arcname=str(eintrag.relative_to(quelle)))
	except (OSError, tarfile.TarError) as fehler:
		teil.unlink(missing_ok=True)
		raise SicherungFehler(
			f"Das Archiv der Dateiablage ist fehlgeschlagen: {type(fehler).__name__}."
		) from fehler
	os.chmod(teil, DATEI_MODUS)
	os.replace(teil, ziel)


# ── Pruefsummen ────────────────────────────────────────────────────────────

def sha256(datei: Path) -> str:
	"""SHA-256 einer Datei, blockweise gelesen (Dumps sind nicht klein)."""
	summe = hashlib.sha256()
	with open(datei, "rb") as fh:
		for block in iter(lambda: fh.read(1024 * 1024), b""):
			summe.update(block)
	return summe.hexdigest()


def schreibe_pruefsummen(verzeichnis: Path) -> str:
	"""``SHA256SUMS`` im ``sha256sum``-Format schreiben (Dateien 0600)."""
	zeilen = []
	for name in (DUMP_NAME, ARCHIV_NAME):
		datei = verzeichnis / name
		if datei.is_file():
			zeilen.append(f"{sha256(datei)}  {name}")
	text = "\n".join(zeilen) + "\n"
	ziel = verzeichnis / PRUEFSUMMEN_NAME
	ziel.write_text(text, encoding="utf-8")
	os.chmod(ziel, DATEI_MODUS)
	return text.splitlines()[0].split()[0] if zeilen else ""


def lese_pruefsummen(verzeichnis: Path) -> dict[str, str]:
	"""Pruefsummen als ``{dateiname: sha256}`` (leer, wenn nicht vorhanden)."""
	datei = verzeichnis / PRUEFSUMMEN_NAME
	if not datei.is_file():
		return {}
	ergebnis: dict[str, str] = {}
	for zeile in datei.read_text(encoding="utf-8").splitlines():
		teile = zeile.split()
		if len(teile) == 2 and re.fullmatch(r"[0-9a-f]{64}", teile[0]):
			ergebnis[teile[1]] = teile[0]
	return ergebnis


def verzeichnisgroesse(verzeichnis: Path) -> int:
	"""Summe aller Dateigroessen in einem Sicherungsverzeichnis."""
	summe = 0
	for datei in verzeichnis.rglob("*"):
		if datei.is_file():
			summe += datei.stat().st_size
	return summe


# ── Der Lauf selbst ────────────────────────────────────────────────────────

def sichere(
	*,
	jetzt: datetime | None = None,
	name: str | None = None,
	timeout: int | None = None,
) -> Path:
	"""Eine vollstaendige Sicherung schreiben. Rueckgabe: fertiges Verzeichnis.

	Es wird NICHTS geschrieben, wenn der Zielort ungeeignet ist: die Pruefung
	laeuft VOR dem temporaeren Verzeichnis.
	"""
	zeit = jetzt or datetime.now()
	basis = pruefe_ziel()
	pruefe_platz(basis)
	kennung = name or neue_kennung(zeit)
	fertig = basis / kennung
	if fertig.exists():
		# N4 (BACKUP-1b): hier wird NICHT mehr umbenannt. Ein Zusatz wie
		# ``-pid`` faellt aus dem Namensmuster, die Aufbewahrung erfasst den
		# Ordner dann nie — und die Protokollzeile behielte den alten Namen.
		# ``lauf._freie_kennung`` vergibt vorher einen freien Namen; kommt der
		# Fall trotzdem, ist etwas anderes im Spiel und darf nicht still
		# danebengeschrieben werden.
		raise SicherungFehler(
			"Fuer diese Sicherung gibt es bereits ein Verzeichnis. "
			"Bitte den Lauf wiederholen."
		)

	temp = Path(tempfile.mkdtemp(prefix=TEMP_PRAEFIX, dir=basis))
	try:
		os.chmod(temp, VERZEICHNIS_MODUS)
		schreibe_dump(temp / DUMP_NAME, timeout=timeout)
		schreibe_dateiarchiv(temp / ARCHIV_NAME)
		schreibe_pruefsummen(temp)
		# FERTIG zuletzt: von jetzt an gilt das Verzeichnis als vollstaendig.
		(temp / FERTIG_NAME).write_bytes(b"")
		os.chmod(temp / FERTIG_NAME, DATEI_MODUS)
		os.replace(str(temp), str(fertig))
	except Exception:
		shutil.rmtree(temp, ignore_errors=True)
		raise
	return fertig


def pruefe_wiederherstellbarkeit(dump: Path, *, timeout: int | None = None) -> str:
	"""Gegenprobe: liest ``pg_restore --list`` den Dump? Rueckgabe: Tabelle.

	Ein Dump, den niemand lesen kann, ist keine Sicherung. Die Gegenprobe ist
	reines LESEN (``--list``), schreibt nichts und braucht keine Datenbank.
	"""
	try:
		ausgabe = subprocess.run(
			[pg_programm("pg_restore"), "--list", str(dump)],
			capture_output=True, text=True, check=False,
			timeout=timeout if timeout and timeout > 0 else None,
		)
	except FileNotFoundError:
		raise SicherungFehler(
			"pg_restore ist im Programm nicht vorhanden — die Sicherung kann nicht geprueft werden."
		) from None
	except subprocess.TimeoutExpired:
		raise SicherungFehler("Die Pruefung der Sicherung hat zu lange gedauert.") from None
	if ausgabe.returncode != 0:
		raise SicherungFehler(
			f"Die erzeugte Sicherung ist nicht lesbar (Exit {ausgabe.returncode})."
		)
	# Die erste Tabellenzeile ist die beste kurze Gegenprobe: sie nennt eine
	# echte Tabelle aus dem Dump — und zugleich, dass der Dump Inhalt hat.
	for zeile in ausgabe.stdout.splitlines():
		if " TABLE " in zeile or zeile.startswith(";     TABLE"):
			return zeile.strip()
	return "keine Tabelle im Dump"
